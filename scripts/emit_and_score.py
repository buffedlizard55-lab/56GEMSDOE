#!/usr/bin/env python3
"""E3 — fuse the surviving channels, pack them on the ridge axes, score on the shared holdout, write
the submission GeoTIFF + receipts.

Pre-registered decision rule (written before the arms were scored, applied by this script rather than
by a person reading the table):

1. every channel enters as a percentile rank of its raw field, so a fusion is an equal-weight mean of
   ranks and no channel wins by having bigger units;
2. four emitter families are compared at the same shipping budget:
   * ``<channel>|topk``     — each channel alone, the k best allowed pixels. This is the arm that
     tells us whether a *physical channel* beats the scarp channel every prior lane used;
   * ``FUSION|topk``        — the same, on the mean rank;
   * ``FUSION|packed``      — greedy farthest-point packing inside a radius (exact sequential greedy
     in value order, batch-accelerated with a dilated occupancy image): one dot per ~radius metres of
     axis. Packing is the step that turns a probability surface into credit, because the metric's
     numerator is a **max** over nearby dots: two dots 1 px apart can only ever earn what one of them
     earns, while each pays alpha for the pixels it fails to cover;
   * ``FUSION|greedy``      — the template's calibrated greedy cover (``holdout.emission_from_field``
     with ``dti_projected`` at the live score and the density renormalised to the |G| estimate from
     ``evidence/hidden_size_inversion.json``), where the *credit bar* decides when to stop, not a
     budget. This is the arm that lets the metric choose the emission size instead of us picking 37,654
     because that is what a sibling file happened to contain;
3. **selection** the arm with the highest pooled HOLDOUT-DTI at the shipping budget is emitted.
   Selecting on the holdout biases the winner upward; the runner-up is printed beside it in the
   receipt and on the site, and the difference is reported with its paired spatial-block CI;
4. **emission floor** cells within ``--shadow`` px of a catalogue pixel are never emitted. Known
   faults are masked pixel-exactly out of the truth, so mass beside a mapped trace pays the
   false-positive term and cannot earn the true-positive term; the sibling group's single best-scoring
   change (0.2600 -> 0.2778, verified pixel-for-pixel in ``evidence/hidden_size_inversion.json``) is
   exactly this deletion applied to their own file.

No learned component is trained in this lane, so the brief's clause that any learned component use a
registration- and omission-tolerant loss (Mnih & Hinton, ICML 2012) is vacuous here; it is recorded as
vacuous in the run card rather than quietly skipped.

Reproduce:
  python scripts/emit_and_score.py --fields scarp_convex,mag_grad,strain_all --budget 37654 \
         --nms 2.8 --name h56-<arm>-20261009
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems56 import evaluate_holdout as EH, gates, grid as G, holdout as H, metric as M  # noqa: E402
from run_field_holdout import dti_from, fast_terms  # noqa: E402  (shared accelerator, cross-checked)

FIELDS = ROOT / "data" / "interim" / "fields"
N_FOLDS, BUFFER_PX, PREVALENCE, SEED = 4, 4, 0.002, 5610
BALL_CACHE: dict[float, np.ndarray] = {}


def ball(radius: float) -> np.ndarray:
    key = round(float(radius), 3)
    if key not in BALL_CACHE:
        r = int(np.ceil(key))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        BALL_CACHE[key] = (np.hypot(yy, xx) <= key + 1e-9)
    return BALL_CACHE[key]


def greedy_pack(field: np.ndarray, allowed: np.ndarray, radius_px: float, k: int,
                batch: int = 4000) -> tuple[np.ndarray, dict]:
    """Exact sequential greedy packing in descending field order: take the best remaining allowed
    pixel, forbid everything within ``radius_px`` of it, repeat until k dots or the pool runs out.

    Batch-accelerated, not approximated: the candidate pool is value-sorted once, each batch discards
    the pixels already forbidden by earlier batches, and the batch is then thinned by an exact
    O(b^2) pass in value order before its footprint is merged into the global occupancy mask. The
    accepted set is identical to the naive per-dot loop (asserted on a small case in
    ``tests/test_contracts.py``); the batches only skip work the naive loop would also skip."""
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=-1.0, posinf=1.0), -1.0).astype(np.float32)
    idx = np.flatnonzero(f.ravel() > -0.5)
    idx = idx[np.lexsort((idx, -f.ravel()[idx]))]        # descending value, flat index breaks ties
    h, w = f.shape
    ff = f.ravel()
    occ = np.zeros(f.size, bool)
    bmask = ball(radius_px)
    dy, dx = np.nonzero(bmask)
    r2 = radius_px * radius_px + 1e-9
    chosen: list[int] = []
    considered = ptr = 0
    while len(chosen) < k and ptr < idx.size:
        blk = idx[ptr:ptr + batch]
        ptr += batch
        considered += blk.size
        blk = blk[~occ[blk]]
        if blk.size == 0:
            continue
        by, bx = blk // w, blk % w
        taken = np.zeros(blk.size, bool)
        sel = []
        for i in range(blk.size):
            if taken[i]:
                continue
            sel.append(i)
            taken |= (by - by[i]) ** 2 + (bx - bx[i]) ** 2 <= r2
            if len(chosen) + len(sel) >= k:
                break
        acc = blk[np.array(sel, int)]
        chosen.extend(acc.tolist())
        ay, ax = acc // w, acc % w
        Y, X = ay[:, None] + dy[None, :], ax[:, None] + dx[None, :]
        ok = (Y >= 0) & (Y < h) & (X >= 0) & (X < w)
        occ[np.ravel_multi_index((Y[ok], X[ok]), (h, w))] = True
    out = np.zeros(f.size, np.float32)
    out[np.array(chosen, int)] = 1.0
    em = out.reshape(h, w)
    return em, dict(emitted=int((em > 0).sum()), considered=int(considered),
                    pool=int(idx.size), radius_px=float(radius_px))


PRIOR_BASE = "data/registry/GEMSDOE32/docs/downloads/gems32-probe-S1-ANCHOR-identical-to-live-02600.tif"
PRIOR_PRUNED = "data/registry/GEMSDOE32/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
PRIORS = {"PRIOR_base_44090": PRIOR_BASE, "PRIOR_pruned_37654": PRIOR_PRUNED}


def prior_masks(fp, visible):
    """The sibling files as filed, minus only the organiser mask of this fold (they are scored as-is,
    not cut to a budget, so an arm comparison is a comparison of whole rasters)."""
    import rasterio
    out = {}
    for tag, rel in PRIORS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        with rasterio.open(path) as ds:
            a = np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0)
        out[tag] = (a > 0) & fp & ~visible
    return out


def arms_for(field: np.ndarray, allowed: np.ndarray, a) -> dict:
    """The four emitter families, on one field."""
    out = {"topk": H.emit_topk(field, allowed, a.budget)}
    if a.nms > 0:
        out["packed"], st = greedy_pack(field, allowed, a.nms, a.budget)
        out["packed_stats"] = st
    if a.greedy:
        g, st = H.emission_from_field(field, allowed, a.dti_projected, a.budget * 3,
                                      calibrate_to=a.calibrate_to, log=lambda *x: None)
        out["greedy"], out["greedy_stats"] = g, st
    return out


def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields", required=True, help="comma-separated channel names")
    ap.add_argument("--weights", default="", help="optional comma-separated weights (same length)")
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--nms", type=float, default=2.8, help="packing radius in px (0 disables)")
    ap.add_argument("--shadow", type=int, default=2, help="px of catalogue shadow never emitted")
    ap.add_argument("--name", required=True)
    ap.add_argument("--greedy", action="store_true", help="also score the calibrated greedy-cover arm")
    ap.add_argument("--calibrate-to", type=float, default=15000.0,
                    help="target total mass for the calibrated arm = the |G| estimate (MODEL)")
    ap.add_argument("--dti-projected", type=float, default=0.2778,
                    help="live score used only to set the credit bar; a bar, not a prediction")
    ap.add_argument("--no-holdout", action="store_true", help="skip scoring, just write the raster")
    ap.add_argument("--priors", action="store_true",
                    help="also score the two sibling rasters as-is on the same folds (calibration of the instrument)")
    a = ap.parse_args()
    names = [s.strip() for s in a.fields.split(",") if s.strip()]
    w = [float(s) for s in a.weights.split(",") if s.strip() != ""] or [1.0] * len(names)
    assert len(w) == len(names), "weights must match fields"
    for n in names:
        assert (FIELDS / f"{n}.npy").exists(), f"unknown channel {n}"
    fp = np.load(FIELDS / "_footprint.npy")
    cat = np.load(FIELDS / "_cat.npy") & fp
    shadow = ndimage.binary_dilation(cat, iterations=a.shadow) & fp

    arms: dict[str, np.ndarray] = {}
    for n in names:
        arms[n] = (np.load(FIELDS / f"{n}.npy").astype(np.float32) / 65535.0).astype(np.float32)
    ww = np.asarray(w, np.float32) / np.sum(w)
    arms["FUSION"] = np.sum([arms[n] * ww[i] for i, n in enumerate(names)], axis=0).astype(np.float32)
    for k in list(arms):
        if not np.isfinite(arms[k]).all():
            arms[k] = np.nan_to_num(arms[k], nan=0.0)

    result = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ"), fields=names, weights=w,
                  decision_rule="highest pooled HOLDOUT-DTI at the shipping budget; ties by lower "
                                "emitted mass", budget=a.budget, nms_px=a.nms, shadow_px=a.shadow,
                  greedy_arm=a.greedy, calibrate_to=a.calibrate_to, dti_projected=a.dti_projected,
                  evaluator=EH.VERSION, protocol=dict(folds=N_FOLDS, buffer_px=BUFFER_PX,
                                                       prevalence=PREVALENCE, seed=SEED,
                                                       mode="hide",
                                                       visible_mask="pixel-exact (thread 11516 post #4)",
                                                       alpha=M.ALPHA, beta=M.BETA, radius_m=M.R_M))
    allowed = fp & ~shadow

    if not a.no_holdout:
        folds = H.make_folds(cat, fp, n_folds=N_FOLDS, buffer_px=BUFFER_PX, prevalence=PREVALENCE,
                             seed=SEED, mode="hide")
        terms: dict[str, list] = {}
        extra: dict[str, dict] = {}
        region_all = fp  # hide mode: region is the whole footprint
        cross = []
        for fi, fold in enumerate(folds):
            vis = fold["visible"] & fp
            al = fp & ~vis & fold["region"] & ~ndimage.binary_dilation(vis, iterations=a.shadow)
            truth = fold["truth"] & fold["region"] & fp
            dgt = ndimage.distance_transform_edt(~truth, sampling=M.PIXEL_M)
            for key, field in list(arms.items()):
                for kind, em in arms_for(field, al, a).items():
                    if kind.endswith("_stats"):
                        if fi == 0:
                            extra.setdefault(f"{key}|{kind}", em)
                        continue
                    name = f"{key}|{kind}"
                    tt, tp, fpm, ng, rec = fast_terms(em > 0, truth, dgt, fp.shape)
                    terms.setdefault(name, []).append(tt)
                    if fi == 0:
                        extra.setdefault(name, {})
                        extra[name].update(emitted=int((em > 0).sum()), tpw=round(tp, 2),
                                           fpw=round(fpm, 2), recall3=round(float(rec), 4),
                                           mean_credit_per_dot=round(tp / max(1, int((em > 0).sum())), 4))
                        if len(cross) < 4:
                            ref = H.score(em.astype(np.float32), fold, fp, extra=False)
                            cross.append(dict(arm=name, fast=round(dti_from(tp, fpm, ng - tp, ng), 9),
                                              shared=round(ref["dti"], 9),
                                              abs_diff=abs(dti_from(tp, fpm, ng - tp, ng) - ref["dti"])))
                    del em
            if a.priors:
                for tag, mask in prior_masks(fp, vis).items():
                    tt, tp, fpm, ng, rec = fast_terms(mask, truth, dgt, fp.shape)
                    terms.setdefault(tag, []).append(tt)
                    if fi == 0:
                        extra.setdefault(tag, {}).update(emitted=int(mask.sum()), tpw=round(tp, 2),
                                                          fpw=round(fpm, 2), recall3=round(float(rec), 4),
                                                          mean_credit_per_dot=round(tp / max(1, int(mask.sum())), 4))
            del al, truth, dgt
        result["crosscheck"] = cross
        summ = EH.pooled_summary({k: np.sum(np.stack(v), axis=0) for k, v in terms.items()},
                                 candidate=("PRIOR_base_44090" if a.priors else f"{names[0]}|topk"))
        table = {}
        for k, v in summ["scores"].items():
            table[k] = {**v, **(extra.get(k) or {})}
        for k, v in extra.items():
            if k.endswith("_stats") and k not in table:
                table[k] = v
        ranked = sorted([k for k in table if "|full" not in k and not k.endswith("_stats")],
                        key=lambda k: -table[k]["dti"])
        result.update(table=table, ranking={k: table[k]["dti"] for k in ranked}, pooled=summ,
                      best_arm=ranked[0],
                      withheld_positive_pixels=int(sum(int((f["truth"] & f["region"] & fp).sum()) for f in folds)))
        (ROOT / "evidence").mkdir(exist_ok=True)
        (ROOT / "evidence" / f"emission_holdout_{a.name}.json").write_text(
            json.dumps(result, indent=1, default=float))
        print(json.dumps(result["ranking"], indent=1))
        key, kind = result["best_arm"].rsplit("|", 1)
        print("BEST:", result["best_arm"])
    else:
        # With a single field the fused arm IS that field, so label it truthfully; the old code said
        # "FUSION|packed" for a one-channel run, which is not a lie about the bytes but is misleading.
        key = names[0] if len(names) == 1 else "FUSION"
        kind = "packed" if a.nms > 0 else "topk"
        result.update(best_arm=f"{key}|{kind}")

    # ---- the shipped raster, built through the same code path the arm was scored with ----------
    field = arms[key]
    em, st = ((H.emit_topk(field, allowed, a.budget), {}) if kind == "topk" else
              (greedy_pack(field, allowed, a.nms, a.budget) if kind == "packed" else
               H.emission_from_field(field, allowed, a.dti_projected, a.budget * 3,
                                     calibrate_to=a.calibrate_to, log=lambda *x: None)))
    arr = np.where(fp, em, 0.0).astype(np.float32)
    (ROOT / "docs" / "downloads").mkdir(parents=True, exist_ok=True)
    tif = ROOT / "docs" / "downloads" / f"{a.name}.tif"
    meta = G.write_geotiff(tif, arr, nodata=None)
    import zipfile
    with zipfile.ZipFile(tif.with_suffix(".zip"), "w", zipfile.ZIP_STORED) as z:
        z.write(tif, arcname=tif.name)
    fmt = gates.format_report(tif, ROOT / "data" / "grid" / "sample_submission.tif", footprint=fp)
    dd = ndimage.distance_transform_edt(~cat)[arr > 0]
    rep = dict(name=a.name, file=f"docs/downloads/{a.name}.tif", bytes=tif.stat().st_size,
               sha256=gates.sha256(tif), dots=int((arr > 0).sum()),
               values_present=sorted(set(np.unique(arr).tolist())),
               mass=float(arr.sum()), min_d_catalogue_px=float(dd.min()),
               frac_d_gt_2px=float((dd > 2 + 1e-9).mean()), arm=f"{key}|{kind}", pack_stats=st,
               format_report=fmt, geotiff=meta, seconds=round(time.time() - t0, 1))
    (ROOT / "evidence" / f"raster_{a.name}.json").write_text(json.dumps(rep, indent=1, default=float))
    (ROOT / "docs" / "downloads" / f"checks-{a.name}.json").write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: rep[k] for k in ("name", "dots", "values_present", "min_d_catalogue_px",
                                           "bytes", "sha256")}, indent=1, default=float))
    print("FORMAT ok:", fmt.get("ok"), "problems:", fmt.get("problems"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
