#!/usr/bin/env python3
"""E2 -- does snapping the catalogue onto the evidence crest recover anything the catalogue misses?

Instrument: the shared template evaluator (``gems52-pooled-hide-v1``), whole-component withholding,
visible catalogue masked pixel-exactly, organizer DTI (alpha 0.2, beta 0.8, 300 m triangular
kernel), paired spatial-block bootstrap. No private fork: the folds, the masking and the metric all
come from ``gems52.holdout`` / ``gems52.evaluate_holdout``, vendored byte-identically.

Arms, all derived from the *visible* catalogue of the fold they are scored on:
  A as_is        the visible catalogue line itself. Expected ~0: the organizer mask deletes mass
                 sitting exactly on a visible catalogue pixel. Reported because it proves the mask
                 is doing what thread 11516 says it does inside our own evaluator.
  B snap         every visible pixel moved to its nearest qualifying crest (DEM curvature and
                 magnetic ridge within 1 px of each other, same side).
  C snap_sub     as B, restricted to |offset| in [1, 2) px -- the sub-threshold band the lane's
                 > 2 px gate excludes. This is the arm the shipped file uses, and it is scored here
                 rather than assumed.
  D jitter       same offset *magnitudes* as B, random side. The control that asks whether any
                 perpendicular offset helps, or whether the evidence location specifically helps.

Limitation, stated in the receipt: the holdout target is withheld *catalogue* faults. The organizer's
hidden set is *new* faults. This instrument measures whether a correction rule locates traces better
than the catalogue line; it cannot measure discovery of faults that were never mapped at all.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C, lane_inputs as L, evaluate_holdout as EH, holdout as H, metric as M  # noqa: E402

N_FOLDS, BUFFER_PX = 4, 4


def snap_map(fields, cat_vis, fp, half=C.HALF_WINDOW_PX):
    """Signed per-pixel crest offsets for every pixel of the (already visible) catalogue."""
    row, col = np.nonzero(cat_vis)
    ty, tx, ok, cnt = C.strike_at(cat_vis, row, col)
    P = C.sample_profiles(fields, row[ok], col[ok], ty[ok], tx[ok], fp, half=half)
    d_off, d_h, d_p, _ = C.find_crest(P.dem, P.s)
    m_off, m_h, m_p, _ = C.find_crest(P.mag, P.s)
    r, c = row[ok], col[ok]
    agree = (np.isfinite(d_off) & np.isfinite(m_off) & (d_p >= C.MIN_PROM_FRAC) & (m_p >= C.MIN_PROM_FRAC)
             & (np.sign(d_off) == np.sign(m_off)) & (np.sign(d_off) != 0) & (np.abs(d_off - m_off) <= 1.0))
    joint = np.where(agree, 0.5 * (d_off + m_off), np.nan)
    return r, c, joint, P.origin_valid & agree


def strike_vectors(vis, r, c):
    """(ty, tx) at the given catalogue pixels -- the normal used for both measurement and emission."""
    ty, tx, ok, _ = C.strike_at(vis, r, c)
    return ty, tx


def emit_from(r, c, ty, tx, joint, shape, footprint, visible):
    """Place value 1.0 at origin + offset x normal, snapped to the nearest cell, inside the footprint.

    The normal is the strike rotated 90 degrees in (row, col) index space, exactly as
    ``corrections.sample_profiles`` samples it (``ny, nx = -tx, ty``), so a dot placed at the
    measured offset lands on the cell that the profile's crest was found in -- the emission and the
    measurement cannot drift apart.
    """
    yy = np.rint(r - joint * tx).astype(np.int64)
    xx = np.rint(c + joint * ty).astype(np.int64)
    keep = (yy >= 0) & (yy < shape[0]) & (xx >= 0) & (xx < shape[1])
    yy, xx = yy[keep], xx[keep]
    out = np.zeros(shape, np.float32)
    if yy.size == 0:
        return out
    on_trace = visible[yy, xx]
    yy, xx = yy[~on_trace], xx[~on_trace]                   # never emit back onto the visible line
    ok = footprint[yy, xx]
    out[yy[ok], xx[ok]] = 1.0
    return out


def main():
    t0 = time.time()
    fields, cat, fp, meta = L.load()
    out = {"evidence_class": "HOLDOUT-DTI (catalogue recovery, hide-and-recover; NOT new-fault discovery)",
           "evaluator": {"version": EH.VERSION, "sha256": EH.implementation_hashes(),
                         "alpha": M.ALPHA, "beta": M.BETA, "radius_m": M.R_M},
           "design": dict(folds=N_FOLDS, mode="hide", buffer_px=BUFFER_PX,
                          rule="whole 8-connected catalogue components withheld; visible catalogue "
                               "masked pixel-exactly; prevalence-matched truth",
                          prevalence=None),
           "limitation": "the withheld target is catalogue faults, not the organizer's new faults; "
                         "see gems56/holdout.py docstring and IR-56-004"}
    terms = {k: [] for k in ("A_as_is", "B_snap", "C_snap_sub", "D_jitter")}
    n_truth_total = 0
    rng = np.random.default_rng(560202)
    for f, fold in enumerate(H.make_folds(cat, fp, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                                          prevalence=0.00294, seed=0, mode="hide")):
        vis = fold["visible"] & fp
        r, c, joint, valid = snap_map(fields, vis, fp)
        ty, tx, _, _ = C.strike_at(vis, r, c)
        # A: the visible line as it stands
        pA = np.zeros(cat.shape, np.float32)
        pA[vis] = 1.0
        # B: all concordant crests, |offset| >= 1 px (a snap that stays on the same cell is not a correction)
        gB = valid & np.isfinite(joint) & (np.abs(joint) >= 1.0)
        pB = emit_from(r[gB], c[gB], ty[gB], tx[gB], joint[gB], cat.shape, fp, vis)
        # C: sub-threshold band only
        gC = valid & np.isfinite(joint) & (np.abs(joint) >= 1.0) & (np.abs(joint) < 2.0)
        pC = emit_from(r[gC], c[gC], ty[gC], tx[gC], joint[gC], cat.shape, fp, vis)
        # D: same magnitudes, random side, along the same normal
        gD = gB.copy()
        sgn = np.where(rng.random(gD.sum()) < 0.5, -1.0, 1.0)
        jD = sgn * np.abs(joint[gD])
        pD = emit_from(r[gD], c[gD], ty[gD], tx[gD], jD, cat.shape, fp, vis)
        for k, p in (("A_as_is", pA), ("B_snap", pB), ("C_snap_sub", pC), ("D_jitter", pD)):
            res, tm = EH.evaluate(p, fold, fp)
            terms[k].append(tm)
            out.setdefault("folds", []).append(dict(fold=f, arm=k, dti=round(res["dti"], 5),
                                                     emitted=res["emitted"], n_truth=res["n_truth"]))
        n_truth_total += fold["n_truth"]
        print(f"fold {f}: truth {fold['n_truth']}, dots A/B/C/D = "
              f"{(pA > 0).sum()}/{(pB > 0).sum()}/{(pC > 0).sum()}/{(pD > 0).sum()}", flush=True)
    summary = EH.pooled_summary({k: np.sum(np.stack(v), axis=0) for k, v in terms.items()},
                               candidate="C_snap_sub")
    out["pooled"] = summary
    out["withheld_positives_total"] = n_truth_total
    out["per_fold"] = out.pop("folds")
    out["elapsed_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "holdout_corrections_v1.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(summary, indent=1, default=float)[:2600])


if __name__ == "__main__":
    main()
