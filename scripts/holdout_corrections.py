#!/usr/bin/env python3
"""Corrections lane, experiments E2 (leakage canary) and E3 (hide-and-recover
holdout with simulated corrections).

SCORER MODEL (the live scorer's treatment of known faults, per DrivenData forum
thread 11516 and the group's measured 0.2600-family behaviour): known-fault
pixels are masked pixel-exactly - prediction mass ON a known-fault pixel earns
no true-positive credit (whatever is nearby) and is charged as false-positive
mass (alpha = 0.2 per unit).  The GT contains only the (hidden) refined traces.
This script implements exactly that: TP is computed from the prediction with
catalogue pixels zeroed; FP is computed from the full prediction.  The official
metric itself (src/metrics.py) is untouched.

E3 design (documented simulation, NOT real hidden labels)
---------------------------------------------------------
The competition's hidden truth contains "corrections or modifications to existing
fault traces" within 300 m of known traces (organizers, forum thread 11516).
This holdout simulates exactly that situation:

  * withheld labels  : whole records (vector-catalogue trace ids) have their
                       REFINED positions hidden.  The refined position is
                       simulated by the measured evidence-defined trace (the
                       strongest-crest line of that record's transects) for
                       records whose measured offset is > 1 px; records with
                       |median offset| <= 1 px are "uncorrected" (their truth
                       stays on the catalogue, which is masked -> unscored).
  * visible input    : the catalogue itself (labels.tif) - an input, not a label.
  * masking          : visible faults are masked pixel-exactly on BOTH sides
                       (GT excludes the catalogue; prediction on the catalogue
                       earns no TP and costs alpha).
  * folds            : 4 spatial folds over records (k-means on record centroids);
                       DTI is scored POOLED over folds (alpha 0.2, beta 0.8,
                       300 m triangular kernel - the official metric, reused from
                       src/metrics.py), with a 20x20 px spatial-block bootstrap
                       95% CI (bootstrap_from_blocks, same module).

Arms
  A0_catalogue  dots on the visible catalogue line (masked control, 0 expected)
  A1_lane       the lane's emission: dots on the evidence-defined trace for
                records with consistent offset > 2 px (the deliverable)
  A2_nogate     same emission without the consistency gate (all records with an
                unambiguous crest) - tests the gate
  A4_random     uniform-random dots at A1's mass - chance control
  A5_oracle     dots on the simulated truth itself - the ceiling

The simulation is circular BY CONSTRUCTION for A1/A2 (the truth is the measured
crest line); the holdout therefore validates the emission machinery (snapping,
line connection, off-catalogue restriction, kernel credit) and the CONTROLS,
not the geological assumption.  The A1-vs-A2 contrast is additionally biased
toward A2 by the truth construction (it includes crest lines of 1-2 px-offset
records, which the real scorer would only reward if those corrections exist).
The assumption (refined trace = evidence crest) is validated externally by the
1 m LiDAR calibration in scripts/measure_corrections_offsets.py.  Every number
is labelled HOLDOUT-DTI (simulated-corrections truth, evaluator src/metrics.py).

E2 leakage canary
  Each evidence feature alone is tested as a detector of the simulated truth
  (AUC vs an equal-count uniform background).  AUC > 0.90 = leakage until proven
  otherwise.  Controls: the catalogue mask itself MUST read ~0.5 (truth pixels
  are not on catalogue pixels - masking worked); dist_to_catalogue MUST read
  < 0.5 (the simulated truth is displaced away from the catalogue - the
  simulation is not degenerate).

Run:  python scripts/holdout_corrections.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage
from sklearn.cluster import KMeans
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import corrections as C  # noqa: E402
import metrics as M  # noqa: E402

BLOCK = 20  # px, spatial-block bootstrap unit (2 km)


# ------------------------------------------------------- masked DTI scoring --
def masked_score(ctx: M.GtContext, pred, fault_mask):
    """Pooled DTI under the known-fault masking model.

    TP from prediction with catalogue pixels zeroed; FP from the full
    prediction (on-catalogue mass costs alpha and earns nothing).
    """
    pred = M._sanitise(pred, ctx.shape)
    pred_tp = np.where(fault_mask, 0.0, pred)
    credit = ctx.credit_vector(pred_tp)
    TP_w = float(credit.sum())
    FN_w = float(ctx.n_gt - TP_w)
    fpw = ctx.fp_weight()
    pos = pred > 0
    FP_w = float((pred[pos] * fpw[pos]).sum())
    dti = TP_w / (TP_w + M.DEFAULT_ALPHA * FP_w + M.DEFAULT_BETA * FN_w + M.EPS)
    return dti, (TP_w, FP_w, FN_w)


def masked_block_aggregate(ctx: M.GtContext, pred, fault_mask, blocks, n_blocks):
    """Per-block TP/FP/FN under the masking model (lane extension of the
    template's block_aggregate: TP uses the catalogue-zeroed prediction)."""
    pred = M._sanitise(pred, ctx.shape)
    pred_tp = np.where(fault_mask, 0.0, pred)
    credit = ctx.credit_vector(pred_tp)
    gt_blocks = blocks[ctx.gy, ctx.gx]
    TP = np.bincount(gt_blocks, weights=credit, minlength=n_blocks)[:n_blocks]
    NGT = np.bincount(gt_blocks, minlength=n_blocks)[:n_blocks]
    FN = NGT.astype(np.float64) - TP
    fpw = ctx.fp_weight()
    pos = pred > 0
    flat = blocks.ravel()
    FP = np.bincount(flat, weights=np.where(pos, pred * fpw, 0.0).ravel(),
                     minlength=n_blocks)[:n_blocks]
    PXP = np.bincount(flat, weights=pos.astype(np.float64).ravel(),
                      minlength=n_blocks)[:n_blocks]
    return dict(TP=TP, FP=FP, FN=FN, n_gt=NGT.astype(np.int64),
                pred_px=PXP.astype(np.int64))


# ------------------------------------------------------------ simulated truth
def build_simulated_truth(res, fault, footprint):
    """GT raster (bool) = simulated refined traces, catalogue masked pixel-exactly."""
    gt = np.zeros(fault.shape, bool)
    per_record = {}
    ok = res.ok("dem_slope", "strongest")
    rec = C.record_consistency(res.t("dem_slope", "strongest")[ok],
                               res.perp_r[ok], res.perp_c[ok], res.record_ids[ok])
    for rid in sorted(rec):
        v = rec[rid]
        if abs(v["median_offset_px"]) <= C.MIN_SHIFT_PX:
            per_record[rid] = 0
            continue
        line = C.record_crest_line(res, rid)
        if line is None:
            per_record[rid] = 0
            continue
        ri = np.clip(np.round(line[0]).astype(int), 0, C.GRID_H - 1)
        ci = np.clip(np.round(line[1]).astype(int), 0, C.GRID_W - 1)
        keep = footprint[ri, ci] & ~fault[ri, ci]   # mask visible faults pixel-exactly
        ri, ci = ri[keep], ci[keep]
        if ri.size == 0:
            per_record[rid] = 0
            continue
        gt[ri, ci] = True
        per_record[rid] = int(ri.size)
    return gt, per_record


def spatial_folds(res, n_folds=4, seed=0):
    """k-means folds over the contributing records' centroids."""
    ok = res.ok("dem_slope", "strongest")
    rec = C.record_consistency(res.t("dem_slope", "strongest")[ok],
                               res.perp_r[ok], res.perp_c[ok], res.record_ids[ok])
    cents, rids = [], []
    for rid, v in rec.items():
        if abs(v["median_offset_px"]) <= C.MIN_SHIFT_PX:
            continue
        sel = res.record_ids == rid
        cents.append([np.median(res.centers_r[sel]), np.median(res.centers_c[sel])])
        rids.append(rid)
    km = KMeans(n_clusters=n_folds, random_state=seed, n_init=10).fit(np.array(cents))
    return dict(zip(rids, km.labels_.tolist())), km


# ------------------------------------------------------------------- canary --
def leakage_canary(gt, footprint, labels_path, features_path, n_neg=20000, seed=1):
    """Per-feature AUC of the simulated truth + controls."""
    rng = np.random.default_rng(seed)
    pos_r, pos_c = np.nonzero(gt)
    neg_r = rng.integers(0, C.GRID_H, n_neg)
    neg_c = rng.integers(0, C.GRID_W, n_neg)
    keep = footprint[neg_r, neg_c] & ~gt[neg_r, neg_c]
    neg_r, neg_c = neg_r[keep], neg_c[keep]
    n = min(len(pos_r), len(neg_r))
    pos_r, pos_c = pos_r[:n], pos_c[:n]
    neg_r, neg_c = neg_r[:n], neg_c[:n]
    y = np.concatenate([np.ones(n), np.zeros(n)])

    fault, _ = C.load_labels(labels_path)
    dist_cat = ndimage.distance_transform_edt(~fault)

    feats = {}
    for name in ("det_elev_slope", "tmi_hg", "tc", "det_elev"):
        feats[name] = ("evidence", C.load_band(features_path, C.BAND[name]))
    feats["dist_to_catalogue_px"] = ("control_displacement", dist_cat.astype(np.float32))
    feats["catalogue_mask"] = ("control_masking", fault.astype(np.float32))

    out = {}
    for name, (role, arr) in feats.items():
        v = np.concatenate([arr[pos_r, pos_c], arr[neg_r, neg_c]])
        v = np.nan_to_num(v, nan=0.0)
        try:
            auc = float(roc_auc_score(y, v))
        except ValueError:
            auc = None
        out[name] = dict(auc=auc, role=role)
    out["_n_positives"] = int(n)
    out["_n_negatives"] = int(n)
    return out


# --------------------------------------------------------------------- main --
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--features", default="data/training_features.tif")
    ap.add_argument("--records", default="data/cache/fault_px_record.npz")
    ap.add_argument("--lidar", default="data/cache/lidar_scarp_features_u8.tif")
    ap.add_argument("--out", default="evidence/corrections")
    ap.add_argument("--cache", default="data/cache/transect_result.npz")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("[1/6] running lane measurement")
    res = C.run_measurement(args.labels, args.features, args.records, args.lidar)
    fault, footprint = C.load_labels(args.labels)
    np.savez(args.cache,
             centers_r=res.centers_r, centers_c=res.centers_c,
             perp_r=res.perp_r, perp_c=res.perp_c, record_ids=res.record_ids,
             lidar_coverage=(res.lidar_coverage if res.lidar_coverage is not None
                             else np.full(len(res.centers_r), np.nan)))
    for (band, definition), (t, prom, ok) in res.crest.items():
        np.savez(args.cache + f".{band}_{definition}.npz", t=t, prom=prom, ok=ok)

    print("[2/6] building simulated corrections (withheld refined traces)")
    gt, per_record = build_simulated_truth(res, fault, footprint)
    n_gt = int(gt.sum())
    folds, km = spatial_folds(res)
    print(f"      simulated truth px (withheld positives): {n_gt:,}  "
          f"records contributing: {sum(1 for v in per_record.values() if v > 0)}  "
          f"folds: {len(set(folds.values()))}")

    print("[3/6] building arms")
    cands = C.correction_candidates(res)
    print(f"      correction-candidate records (consistent |offset|>2px): {len(cands)}")
    a1, a1_n, a1_per_rec = C.build_emission(res, fault, footprint, candidates=cands)
    a2, a2_n, _ = C.build_emission(res, fault, footprint, candidates=None)
    a0 = np.where(fault, 1.0, np.nan).astype(np.float32)
    rng = np.random.default_rng(7)
    fp_r, fp_c = np.nonzero(footprint)
    sel = rng.choice(len(fp_r), size=a1_n, replace=False)
    a4 = np.full(fault.shape, np.nan, np.float32)
    a4[fp_r[sel], fp_c[sel]] = 1.0
    a4_n = a1_n
    a5 = np.where(gt, 1.0, np.nan).astype(np.float32)
    print(f"      A0 catalogue px: {int(fault.sum()):,}   A1 lane dots: {a1_n:,}   "
          f"A2 no-gate dots: {a2_n:,}   A4 random dots: {a4_n:,}   A5 oracle px: {n_gt:,}")

    print("[4/6] scoring pooled DTI (official metric + known-fault masking model)")
    arms = [("A0_catalogue", a0), ("A1_lane", a1), ("A2_nogate", a2),
            ("A4_random", a4), ("A5_oracle", a5)]
    ctx = M.GtContext(gt.astype(np.float64))
    scores, rows = {}, []
    for name, arr in arms:
        dti, (tp, fp, fn) = masked_score(ctx, arr, fault)
        scores[name] = dti
        print(f"      {name:14s} pooled DTI = {dti:.5f}   (TP_w={tp:.1f} FP_w={fp:.1f} "
              f"FN_w={fn:.1f} |G|={ctx.n_gt})")
        rows.append(dict(name=name, dti=dti, TP_w=tp, FP_w=fp, FN_w=fn))

    print("[5/6] spatial-block bootstrap (20x20 px blocks, 2000 draws)")
    blocks = np.zeros(fault.shape, np.int64)
    bid = 0
    for y0 in range(0, C.GRID_H, BLOCK):
        for x0 in range(0, C.GRID_W, BLOCK):
            blocks[y0:min(C.GRID_H, y0 + BLOCK), x0:min(C.GRID_W, x0 + BLOCK)] = bid
            bid += 1
    n_blocks = bid
    boot_rows = []
    for name, arr in arms:
        agg = masked_block_aggregate(ctx, arr, fault, blocks, n_blocks)
        bl = [dict(TP_w=float(agg["TP"][b]), FP_w=float(agg["FP"][b]),
                   FN_w=float(agg["FN"][b]), n_gt=int(agg["n_gt"][b]),
                   scoreable=bool(agg["n_gt"][b] > 0 or agg["pred_px"][b] > 0))
              for b in range(n_blocks)]
        boot_rows.append(dict(label=name, blocks=bl))
    boot = M.bootstrap_from_blocks(boot_rows, n_boot=2000, seed=0)
    for name, _ in arms:
        b = boot.get(name, {})
        ci = b.get("dti_ci95", [None, None])
        print(f"      {name:14s} DTI {scores[name]:.5f}  95% CI [{ci[0]}, {ci[1]}]")

    print("[6/6] leakage canary (E2)")
    canary = leakage_canary(gt, footprint, args.labels, args.features)
    for name, v in canary.items():
        if name.startswith("_"):
            continue
        flag = "  <-- LEAKAGE?" if (v["auc"] or 0) > 0.90 else ""
        print(f"      {name:24s} AUC={v['auc']:.4f}  ({v['role']}){flag}")
    mask_auc = canary["catalogue_mask"]["auc"]
    disp_auc = canary["dist_to_catalogue_px"]["auc"]
    controls_ok = (0.40 <= mask_auc <= 0.60) and (disp_auc < 0.5)
    print(f"      catalogue_mask AUC ~ 0.5 (masking worked): {0.40 <= mask_auc <= 0.60} "
          f"(AUC={mask_auc:.4f})")
    print(f"      dist_to_catalogue AUC < 0.5 (truth displaced off the catalogue): "
          f"{disp_auc < 0.5} (AUC={disp_auc:.4f})")
    print(f"      controls OK: {controls_ok}")

    # ---- persist -------------------------------------------------------------
    result = dict(
        label="HOLDOUT-DTI (simulated-corrections truth, evaluator src/metrics.py, "
              "alpha 0.2, beta 0.8, 300 m triangular kernel, known-fault masking model)",
        n_withheld_positives=n_gt,
        n_correction_candidates=len(cands),
        candidate_records=sorted(cands),
        arms={r["name"]: dict(dti=r["dti"], TP_w=r["TP_w"], FP_w=r["FP_w"],
                              FN_w=r["FN_w"],
                              dots={"A0_catalogue": int(fault.sum()), "A1_lane": a1_n,
                                    "A2_nogate": a2_n, "A4_random": a4_n,
                                    "A5_oracle": n_gt}[r["name"]],
                              ci95=boot.get(r["name"], {}).get("dti_ci95"))
              for r in rows},
        contrasts={
            "A1_minus_A0": scores["A1_lane"] - scores["A0_catalogue"],
            "A1_minus_A2": scores["A1_lane"] - scores["A2_nogate"],
            "A1_minus_A4": scores["A1_lane"] - scores["A4_random"],
            "A5_minus_A1": scores["A5_oracle"] - scores["A1_lane"],
        },
        contrast_ci95={
            "A1_minus_A0": boot.get("A1_lane", {}).get("contrast_vs_reference_ci95"),
        },
        leakage_canary=canary,
        controls_ok=bool(controls_ok),
        folds={rid: int(f) for rid, f in folds.items()},
        per_record_truth_px=per_record,
        per_record_emission_px=a1_per_rec,
    )
    (out / "holdout_corrections.json").write_text(json.dumps(result, indent=1))
    pd.DataFrame([dict(record=k, simulated_truth_px=v) for k, v in per_record.items()
                  if v > 0]).to_csv(out / "holdout_simulated_truth_records.csv", index=False)
    for name, arr in arms:
        np.save(out / f"holdout_arm_{name}.npy", np.nan_to_num(arr, nan=0.0))
    print(f"\nArtifacts in {out}/ (holdout_corrections.json, holdout_arm_*.npy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
