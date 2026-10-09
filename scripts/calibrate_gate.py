#!/usr/bin/env python3
"""E1b -- calibrate the "is this crest real?" gate on nulls, then publish the gated histograms.

Why this script exists separately: a "nearest crest within 400 m" measurement does not return zero where
there is no fault. At a random traceless point the detector still finds *some* bump, so the raw offset
histogram is the sum of a real displacement and the estimator's own noise floor. Two nulls bound that
floor (random points, and catalogue points sampled in a random direction), the 90th percentile of the null
crest height becomes the absolute strength gate for believing a crest, and the gated histograms -- the ones
this lane's decision is made from -- are reported next to the nulls they were calibrated against.

Supersedes nothing: this is the same measurement as evidence/offsets_v1.json with the gate applied, and it
is re-run whenever the detector changes (see evidence/irregularities.json IR-56-009).

Reproduce: python scripts/calibrate_gate.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C, lane_inputs as L   # noqa: E402

SIGMA_FLOOR_PX = 1.296      # evidence/lidar_calibration_v1.json pooled coarse_minus_fine.rms_m / 100


def stats(a, signed=True):
    a = np.asarray(a, np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    x = a if signed else np.abs(a)
    med = float(np.median(x))
    cnts, edges = np.histogram(x, bins=16, range=(-4.0, 4.0) if signed else (0.0, 4.0))
    return dict(n=int(x.size), counts=cnts.tolist(), edges=edges.tolist(),
                median=med, mean=float(x.mean()), mad=float(np.median(np.abs(x - med))),
                p05=float(np.percentile(x, 5)), p95=float(np.percentile(x, 95)),
                frac_abs_ge_1=float((np.abs(x) >= 1).mean()), frac_abs_ge_2=float((np.abs(x) >= 2).mean()),
                frac_abs_ge_3=float((np.abs(x) >= 3).mean()))


def main():
    t0 = time.time()
    fields, cat, fp, meta = L.load()
    rec = C.measure(fields, cat, fp)
    out = {"evidence_class": "MEASURED; descriptive statistics and estimator calibration, not a score"}

    # ---- the two nulls
    nulls = {}
    for mode, seed in (("random", 5601), ("rotated", 5602)):
        N = C.control_points(fields, cat, fp, n=60988, seed=seed, mode=mode)
        v = N["valid"]
        nulls[mode] = dict(
            n=int(v.sum()),
            dem_abs_offset=stats(np.abs(N["dem_off_px"][v]), signed=False),
            mag_abs_offset=stats(np.abs(N["mag_off_px"][v]), signed=False),
            dem_hgt_p50_p90_p99=[float(np.nanpercentile(N["dem_hgt"][v], q)) for q in (50, 90, 99)],
            mag_hgt_p50_p90_p99=[float(np.nanpercentile(N["mag_hgt"][v], q)) for q in (50, 90, 99)])
    out["null_random"], out["null_rotated"] = nulls["random"], nulls["rotated"]
    hd = nulls["random"]["dem_hgt_p50_p90_p99"][1]
    hm = nulls["random"]["mag_hgt_p50_p90_p99"][1]
    out["strength_gate"] = dict(
        dem_min_hgt=hd, mag_min_hgt=hm,
        rule="a crest is only believed when its convexity height exceeds the 90th percentile of the same "
             "statistic measured at random traceless points",
        note="units: dem = m per cell^2 of curvature, mag = |tmi_hg| units")

    # ---- gated catalogue measurement
    g = C.measure(fields, cat, fp, min_hgt=(hd, hm, 0.0))
    joint, corr = C.joint_offset(g)
    gv = g["valid"]
    out["gated"] = dict(
        pixels=int(gv.sum()), fraction_of_catalogue=float(gv.sum() / max(1, int((cat & fp).sum()))),
        dem_signed_offset=stats(g["dem_off_px"][gv]),
        mag_signed_offset=stats(g["mag_off_px"][gv]),
        joint_signed_offset=stats(joint[gv & np.isfinite(joint)]),
        corroborated_fraction=float(corr[gv].mean()))
    rows, joint_all, corr_all, u_all = C.corridor_table(g, cat, sigma_floor_px=SIGMA_FLOOR_PX)
    q = [r for r in rows if r["qualifies"]]
    out["corridors"] = dict(components=len(rows), qualifying=len(q),
                            qualifying_pixels=sum(r["n_usable"] for r in q),
                            qualifying_length_m=sum(r["length_m"] for r in q),
                            worst_z=max((r["z"] for r in rows if np.isfinite(r["z"])), default=None),
                            sigma_floor_px=SIGMA_FLOOR_PX,
                            top=sorted(q, key=lambda r: -abs(r["joint_med"]))[:12])
    out["rule_under_this_gate"] = dict(
        emit_if_any_corridor_qualifies=bool(q),
        n_qualifying_corridors=len(q),
        qualifying_components=[r["comp"] for r in q],
        note=("the brief emits dots 'where a consistent offset exceeds ~2 pixels'; consistency is decided "
              "at corridor level with the LiDAR-measured precision floor on the standard error, and the "
              "emission script applies the identical call so the verdict and the raster cannot disagree"))
    out["elapsed_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "calibration_v1.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("strength_gate", "rule_under_this_gate")}, indent=1, default=float))
    print("gated:", json.dumps(out["gated"], default=float)[:600])
    print("corridors:", json.dumps({k: v for k, v in out["corridors"].items() if k != "top"}, default=float))
    print("null |offset| medians:", nulls["random"]["dem_abs_offset"]["median"],
          nulls["rotated"]["dem_abs_offset"]["median"], "| elapsed", out["elapsed_s"], "s")


if __name__ == "__main__":
    main()
