#!/usr/bin/env python3
"""H57 corrections-lane experiment E2: hide-and-recover holdout with REAL withheld faults.

Why this holdout and not the previous one
-----------------------------------------
The earlier corrections holdout (``scripts/holdout_corrections.py``) built its ground truth
from the *measured crest line itself*, so the lane's own emitter was scored against a target
it had drawn: circular by construction, and documented as such in its own docstring.

This script replaces the target with something the lane did not draw: whole catalogue
components (8-connected traces of ``existing_faults.tif``) are WITHHELD, with a buffer, and
become the hidden positives.  Everything the emitter is allowed to see - the trace geometry it
takes its strike and its transect origins from - is derived from the VISIBLE catalogue only.
Visible catalogue pixels are masked pixel-exactly on both sides of the metric, exactly as
DrivenData describe the live scorer (forum thread 11516).

That makes the test the honest version of the lane's claim:

    "a crest / magnetic ridge a few hundred metres off a mapped trace marks a real fault that
     the mapped trace does not cover"

If the claim is true, dots placed at the measured crest offset around the visible traces should
recover hidden *mapped* faults better than dots placed in the same corridor with no evidence.

Arms (all dot counts matched by seeded subsampling, so no arm wins by spending more mass)
  B0_chance        uniform random dots inside the footprint              - chance floor
  B1_corridor      dots at a FIXED +-3 px offset either side of every visible trace pixel
                   - the geometry-matched null: corridor coverage with ZERO evidence
  B2_evidence      dots at the measured DEM-crest offset where |offset| >= 2 px  - the lane
  B3_corroborated  B2 restricted to transects where the magnetic ridge agrees within 1 px
  B4_catalogue     dots on the visible catalogue line itself             - must score ~0
                   (sanity check that the pixel-exact masking is actually in force)

Numbers are HOLDOUT-DTI (evaluator ``src/metrics.py``, alpha 0.2, beta 0.8, 300 m triangular
kernel, known-fault masking model), pooled over folds, with a 20x20 px spatial-block bootstrap
95 % CI and a paired contrast against B1.  They are NOT competition scores.

Run:  .venv/bin/python scripts/h57_corridor_holdout.py --folds 4
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

import metrics as M                      # noqa: E402  (template tool, unmodified)
from gems56 import corrections as C      # noqa: E402
from gems56 import lane_inputs           # noqa: E402

BLOCK = 20          # px, spatial-block bootstrap unit (2 km)
BUFFER_PX = 3       # withheld segments are hidden together with this buffer of visible trace
MIN_OFFSET_PX = 2.0
R_PX = 3


# --------------------------------------------------------------------------- scoring model --
def masked_score(ctx: M.GtContext, pred, visible_mask):
    """Pooled DTI under the known-fault masking model (shared with holdout_corrections.py).

    TP is computed from the prediction with visible-catalogue pixels zeroed; FP is computed
    from the full prediction, so mass parked on a known fault earns nothing and still costs
    alpha.  The official metric in src/metrics.py is reused unmodified.
    """
    pred = M._sanitise(pred, ctx.shape)
    credit = ctx.credit_vector(np.where(visible_mask, 0.0, pred))
    TP = float(credit.sum())
    FN = float(ctx.n_gt - TP)
    fpw = ctx.fp_weight()
    pos = pred > 0
    FP = float((pred[pos] * fpw[pos]).sum())
    return TP / (TP + M.DEFAULT_ALPHA * FP + M.DEFAULT_BETA * FN + M.EPS), (TP, FP, FN)


def block_terms(ctx: M.GtContext, pred, visible_mask, blocks, n_blocks):
    pred = M._sanitise(pred, ctx.shape)
    credit = ctx.credit_vector(np.where(visible_mask, 0.0, pred))
    gb = blocks[ctx.gy, ctx.gx]
    TP = np.bincount(gb, weights=credit, minlength=n_blocks)[:n_blocks]
    NGT = np.bincount(gb, minlength=n_blocks)[:n_blocks].astype(np.float64)
    fpw = ctx.fp_weight()
    pos = pred > 0
    FP = np.bincount(blocks.ravel(), weights=np.where(pos, pred * fpw, 0.0).ravel(),
                     minlength=n_blocks)[:n_blocks]
    PX = np.bincount(blocks.ravel(), weights=pos.astype(np.float64).ravel(),
                     minlength=n_blocks)[:n_blocks]
    return TP, FP, NGT - TP, NGT, PX


# ------------------------------------------------------------------------------- emission --
def snap(row, col, ty, tx, off, shape):
    """Pixel indices of the point ``off`` pixels along the trace normal from (row, col)."""
    ny, nx = -tx, ty
    r = np.rint(row + off * ny).astype(np.int64)
    c = np.rint(col + off * nx).astype(np.int64)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    return r[ok], c[ok], ok


def dots_from(rows, cols, shape, footprint, forbid, budget=None, seed=0):
    """Deduplicated binary dot raster, inside the footprint, never on a forbidden pixel."""
    keep = footprint[rows, cols] & ~forbid[rows, cols]
    rows, cols = rows[keep], cols[keep]
    flat = np.unique(rows.astype(np.int64) * shape[1] + cols.astype(np.int64))
    if budget is not None and flat.size > budget:
        rng = np.random.default_rng(seed)
        flat = np.sort(rng.choice(flat, size=budget, replace=False))
    out = np.zeros(shape, np.float32)
    out.ravel()[flat] = 1.0
    return out, int(flat.size)


def evidence_dots(rec, shape, corroborated, min_offset=MIN_OFFSET_PX, min_prom=C.MIN_PROM_FRAC):
    """Source pixel list for the lane arms: snapped crest positions."""
    d = rec["dem_off_px"]
    sel = rec["valid"] & np.isfinite(d) & (np.abs(d) >= min_offset) & (rec["dem_prom"] >= min_prom)
    if corroborated:
        m = rec["mag_off_px"]
        sel &= np.isfinite(m) & (np.abs(d - m) <= 1.0) & (np.sign(d) == np.sign(m))
    r, c, _ = snap(rec["row"][sel].astype(np.float64), rec["col"][sel].astype(np.float64),
                   rec["ty"][sel], rec["tx"][sel], d[sel], shape)
    return r, c, int(sel.sum())


def corridor_dots(rec, shape, offset=3.0):
    """Geometry-matched null: a fixed offset either side, no evidence consulted at all."""
    rr, cc = [], []
    for s in (+offset, -offset):
        r, c, _ = snap(rec["row"].astype(np.float64), rec["col"].astype(np.float64),
                       rec["ty"], rec["tx"], np.full(rec["row"].shape, s), shape)
        rr.append(r)
        cc.append(c)
    return np.concatenate(rr), np.concatenate(cc)


def measure_visible(fields, visible, footprint):
    """C.measure plus the strike vectors (needed to snap, and not returned by measure)."""
    rec = C.measure(fields, visible, footprint)
    ty, tx, ok, _ = C.strike_at(visible & footprint, rec["row"].astype(np.int64),
                                rec["col"].astype(np.int64))
    rec["ty"], rec["tx"] = ty, tx
    return rec


# ------------------------------------------------------------------------------------ main --
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["spatial", "neighbour"], default="spatial",
                    help="spatial = whole-component spatial folds (hidden faults end up FAR from "
                         "any visible trace, so a corridor-restricted emitter cannot reach them: "
                         "this mode measures that, see IR-57-001). neighbour = withhold only "
                         "components that have ANOTHER catalogue component within 400 m, which is "
                         "the configuration the corrections claim is actually about.")
    ap.add_argument("--neighbour-px", type=float, default=4.0)
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--seed", type=int, default=5701)
    ap.add_argument("--out", default="evidence/h57_holdout.json")
    args = ap.parse_args()

    t0 = time.time()
    print("[1/5] loading pinned inputs")
    fields, cat, footprint, meta = lane_inputs.load()
    H, W = cat.shape
    print(f"      grid {H}x{W}  footprint {meta['cells']:,}  catalogue {meta['catalogue_cells']:,}")

    lab, n_comp = ndimage.label(cat, structure=np.ones((3, 3), bool))
    cy = ndimage.mean(np.arange(H)[:, None] * np.ones((1, W)), lab, index=np.arange(1, n_comp + 1))
    cx = ndimage.mean(np.ones((H, 1)) * np.arange(W)[None, :], lab, index=np.arange(1, n_comp + 1))
    sizes = ndimage.sum(np.ones_like(cat, np.float64), lab, index=np.arange(1, n_comp + 1))
    # Spatial folds: a deterministic KD-style split of component centroids into `folds`
    # contiguous spatial groups (no sklearn dependency, no RNG, reproducible).
    if args.mode == "neighbour":
        # Candidates: components with ANOTHER component within neighbour_px (<=400 m). Only those
        # can test "the evidence crest beside a mapped trace is a real, separately mapped fault".
        it = int(round(args.neighbour_px))
        cand = []
        objs = ndimage.find_objects(lab)
        for k in range(1, n_comp + 1):
            sl = objs[k - 1]
            if sl is None:
                continue
            y0 = max(0, sl[0].start - it); y1 = min(H, sl[0].stop + it)
            x0 = max(0, sl[1].start - it); x1 = min(W, sl[1].stop + it)
            sub = lab[y0:y1, x0:x1]
            grown = ndimage.binary_dilation(sub == k, iterations=it)
            other = sub[grown]
            if np.any((other != 0) & (other != k)):
                cand.append(k)
        cand = np.array(cand, np.int64)
        print(f"      neighbour-strand candidates: {cand.size:,} components "
              f"({int(sizes[cand - 1].sum()):,} catalogue px) within {args.neighbour_px:g} px "
              f"of another component")
        order = cand[np.lexsort((cx[cand - 1], cy[cand - 1]))] - 1
    else:
        order = np.lexsort((cx, cy))
    fold_of = np.full(n_comp, -1, np.int64)
    chunks = np.array_split(order, args.folds)
    for f, ch in enumerate(chunks):
        fold_of[ch] = f
    print(f"      components {n_comp:,}  folds {args.folds} "
          f"(sizes {[int(sizes[c].sum()) for c in chunks]} catalogue px)")

    blocks = np.zeros((H, W), np.int64)
    bid = 0
    for y0 in range(0, H, BLOCK):
        for x0 in range(0, W, BLOCK):
            blocks[y0:y0 + BLOCK, x0:x0 + BLOCK] = bid
            bid += 1
    n_blocks = bid

    arm_names = ["B0_chance", "B1_corridor", "B2_evidence", "B3_corroborated", "B4_catalogue"]
    acc = {a: dict(TP=np.zeros(n_blocks), FP=np.zeros(n_blocks), FN=np.zeros(n_blocks),
                   dots=0) for a in arm_names}
    totals = {a: dict(TP=0.0, FP=0.0, FN=0.0) for a in arm_names}
    n_withheld = 0
    per_fold = []

    for f in range(args.folds):
        hidden_comp = np.isin(lab, np.flatnonzero(fold_of == f) + 1)
        truth = hidden_comp & cat & footprint
        # buffer: visible trace pixels within BUFFER_PX of a withheld pixel are hidden too, so
        # the emitter cannot simply read the hidden trace off its own visible continuation.
        if args.mode == "neighbour":
            # No buffer erase here ON PURPOSE: the neighbouring strand is a DIFFERENT mapped
            # fault, and hiding it too would delete the very configuration under test. Whole
            # components are still withheld, so no part of a hidden trace is ever visible.
            visible = cat & footprint & ~hidden_comp
        else:
            near_hidden = ndimage.binary_dilation(truth, iterations=BUFFER_PX)
            visible = cat & footprint & ~hidden_comp & ~near_hidden
        print(f"[2/5] fold {f}: withheld {int(truth.sum()):,} px, visible {int(visible.sum()):,} px "
              f"({time.time() - t0:.0f}s)")
        rec = measure_visible(fields, visible, footprint)

        forbid = visible                      # never place a dot on a masked (visible) pixel
        er, ec, n_sel = evidence_dots(rec, (H, W), corroborated=False)
        cr, cc = corridor_dots(rec, (H, W))
        b2, n2 = dots_from(er, ec, (H, W), footprint, forbid)
        budget = n2
        b1, n1 = dots_from(cr, cc, (H, W), footprint, forbid, budget=budget, seed=args.seed + f)
        gr, gc, _ = evidence_dots(rec, (H, W), corroborated=True)
        b3, n3 = dots_from(gr, gc, (H, W), footprint, forbid)
        rng = np.random.default_rng(args.seed + 100 + f)
        fr, fc = np.nonzero(footprint)
        pick = rng.choice(fr.size, size=min(budget, fr.size), replace=False)
        b0, n0 = dots_from(fr[pick], fc[pick], (H, W), footprint, forbid)
        b4 = visible.astype(np.float32)
        n4 = int(visible.sum())
        print(f"      dots: chance {n0:,}  corridor {n1:,}  evidence {n2:,} "
              f"(from {n_sel:,} transects)  corroborated {n3:,}  catalogue {n4:,}")

        ctx = M.GtContext(truth)
        n_withheld += ctx.n_gt
        fold_row = dict(fold=f, withheld_px=int(ctx.n_gt), visible_px=int(visible.sum()))
        for name, arr, nd in (("B0_chance", b0, n0), ("B1_corridor", b1, n1),
                              ("B2_evidence", b2, n2), ("B3_corroborated", b3, n3),
                              ("B4_catalogue", b4, n4)):
            dti, (TP, FP, FN) = masked_score(ctx, arr, visible)
            tb, fb, nb, _, _ = block_terms(ctx, arr, visible, blocks, n_blocks)
            acc[name]["TP"] += tb
            acc[name]["FP"] += fb
            acc[name]["FN"] += nb
            acc[name]["dots"] += nd
            totals[name]["TP"] += TP
            totals[name]["FP"] += FP
            totals[name]["FN"] += FN
            fold_row[name] = dict(dti=round(dti, 6), dots=nd)
            print(f"        {name:16s} fold DTI {dti:.5f}  (TP {TP:.1f} FP {FP:.1f} FN {FN:.1f})")
        per_fold.append(fold_row)

    print(f"[3/5] pooled DTI across folds ({time.time() - t0:.0f}s)")
    pooled = {}
    for name in arm_names:
        t = totals[name]
        pooled[name] = t["TP"] / (t["TP"] + M.DEFAULT_ALPHA * t["FP"]
                                  + M.DEFAULT_BETA * t["FN"] + M.EPS)
        print(f"      {name:16s} pooled HOLDOUT-DTI {pooled[name]:.5f}  dots {acc[name]['dots']:,}")

    print("[4/5] spatial-block bootstrap (20x20 px blocks, 2000 draws, paired vs B1_corridor)")
    ordered = ["B1_corridor"] + [a for a in arm_names if a != "B1_corridor"]
    rows = [dict(label=a, blocks=[dict(TP_w=float(acc[a]["TP"][b]), FP_w=float(acc[a]["FP"][b]),
                                       FN_w=float(acc[a]["FN"][b]),
                                       n_gt=1 if acc[a]["FN"][b] + acc[a]["TP"][b] > 0 else 0,
                                       scoreable=bool(acc[a]["TP"][b] + acc[a]["FN"][b]
                                                      + acc[a]["FP"][b] > 0))
                                  for b in range(n_blocks)]) for a in ordered]
    boot = M.bootstrap_from_blocks(rows, n_boot=2000, seed=0)
    for a in ordered:
        b = boot[a]
        print(f"      {a:16s} CI95 {b['dti_ci95']}  contrast vs B1 "
              f"{b['contrast_vs_reference_p50']:+.5f} {b['contrast_vs_reference_ci95']} "
              f"P(beats B1)={b['prob_beats_reference']}")

    result = dict(
        experiment=f"E2/E3 H57 hide-and-recover holdout ({args.mode} mode), real withheld catalogue components",
        evaluator="src/metrics.py GtContext (official DTI, alpha 0.2, beta 0.8, R=3 px/300 m)"
                  " + pixel-exact visible-fault masking model",
        evaluator_version="h57-hide-and-recover-v1",
        label="HOLDOUT-DTI (never an organizer score)",
        mode=args.mode, neighbour_px=args.neighbour_px, folds=args.folds, buffer_px=(BUFFER_PX if args.mode=="spatial" else 0), min_offset_px=MIN_OFFSET_PX,
        n_withheld_positives=int(n_withheld),
        pooled={k: round(float(v), 6) for k, v in pooled.items()},
        dots={k: int(acc[k]["dots"]) for k in arm_names},
        bootstrap=boot, per_fold=per_fold,
        reference_arm="B1_corridor (geometry-matched, evidence-free corridor coverage)",
        runtime_s=round(time.time() - t0, 1),
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(f"[5/5] wrote {args.out}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
