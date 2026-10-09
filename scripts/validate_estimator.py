#!/usr/bin/env python3
"""Instrument validation: how accurately does the crest locator recover a KNOWN displacement?

Every number this lane publishes is a difference of measured crest positions, so the verdict is only as
good as the locator. The surfaces here have a closed-form crest (the maximum of ``-z''`` for an erf scarp
is one sigma above the inflection), so the answer is known before the estimator sees it. Reported per
scarp width and per true offset: median recovered offset, bias, scatter, and the fraction of transects on
which the detector said anything at all (a miss is recorded as a miss).

Reproduce: python scripts/validate_estimator.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.special import erf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C   # noqa: E402

N = 161
TRACE_COL = 80.0
AMP = 25.0


def scarp(crest_col, sig):
    yy, xx = np.indices((N, N))
    x0 = crest_col - sig                       # -z'' peaks at x0 + sig
    return (AMP * 0.5 * (1.0 + erf((xx - x0) / (sig * np.sqrt(2.0))))).astype(np.float32)


def main():
    cat = np.zeros((N, N), bool)
    cat[:, int(TRACE_COL)] = True
    row, col = np.nonzero(cat)
    ty, tx, ok, _ = C.strike_at(cat, row, col)
    fields0 = {"tmi_hg": np.zeros((N, N), np.float32), "iso_grav_anom_hg": np.zeros((N, N), np.float32)}
    out = {"evidence_class": "MEASURED instrument characterisation on synthetic scarps; not a score",
           "surface": "erf scarp, amplitude 25 m, crest of -d2z/dn2 at the stated column",
           "cells": {}}
    for sig in (0.75, 1.0, 1.5, 2.0):
        for k in (-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0):
            z = scarp(TRACE_COL + k, sig)
            P = C.sample_profiles({**fields0, "det_elev": z}, row[ok], col[ok], ty[ok], tx[ok],
                                  np.ones((N, N), bool))
            off = C.find_crest(P.dem, P.s, max_offset=C.HALF_WINDOW_PX)[0]
            fin = np.isfinite(off)
            rec = dict(n_detected=int(fin.sum()), n_total=int(off.size),
                       frac_detected=round(float(fin.mean()), 4))
            if fin.sum() >= 0.2 * off.size:
                e = off[fin] - k
                rec.update(median_offset_px=round(float(np.median(off[fin])), 4),
                           bias_px=round(float(np.median(e)), 4),
                           mad_px=round(float(np.median(np.abs(e - np.median(e)))), 4),
                           spread_px=round(float(np.percentile(e, 95) - np.percentile(e, 5)), 4))
            out["cells"][f"sig{sig}_k{k:+.1f}"] = rec
    # one-line summary the site and the run card quote
    det = {s: [c["frac_detected"] for k, c in out["cells"].items() if k.startswith(f"sig{s}_") and abs(float(k.split('_k')[1])) <= 2.0]
           for s in ("0.75", "1.0", "1.5", "2.0")}
    bias = [c["bias_px"] for k, c in out["cells"].items() if "bias_px" in c and abs(float(k.split("_k")[1])) <= 2.0]
    out["summary"] = dict(
        detection_complete_within_2px=all(min(v) == 1.0 for v in det.values()),
        max_abs_bias_px_within_2px=round(float(np.max(np.abs(bias))), 4),
        median_abs_bias_px_within_2px=round(float(np.median(np.abs(bias))), 4),
        note=("bias is nearly constant in k for a given scarp width (the 0.75 px gaussian on a curvature "
              "lobe whose trough sits one cell away displaces the smoothed peak), so it is a per-shape "
              "calibration, not scatter; it is bounded by ~0.4 px, which is why the lane quotes corridors "
              "and null-relative distributions rather than any single absolute offset"),
        cells_beyond_crediting_window="|true offset| = 4 px is at the +-400 m window edge; those rows are "
                                       "reported as reduced detection, and a missed far crest can only "
                                       "understate displacement, never invent it")
    (ROOT / "evidence" / "estimator_validation.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out["summary"], indent=1))
    bad = [k for k, v in out["cells"].items() if v["frac_detected"] < 1.0 and abs(float(k.split("_k")[1])) < 3.0]
    print("cells with incomplete detection inside +-2 px:", bad)


if __name__ == "__main__":
    main()
