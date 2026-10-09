#!/usr/bin/env python3
"""E1 -- the corrections-lane measurement: perpendicular transects, offset histograms, nulls.

Reads only the pinned official rasters (evidence/grid.json records the hashes). Writes
``evidence/offsets_v1.json`` (histograms, summary statistics, the lane decision) and
``evidence/offsets_v1_rows.json.gz`` (the per-catalogue-pixel record, for audit).

Reproduce:  python scripts/measure_offsets.py
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C, lane_inputs as L   # noqa: E402

HIST_EDGES = list(np.round(np.arange(-4.0, 4.0001, 0.5), 3))


def hist(x, edges=HIST_EDGES):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    h, _ = np.histogram(x, bins=edges)
    return dict(counts=[int(v) for v in h], edges=[float(v) for v in edges], n=int(x.size),
                mean=float(x.mean()), median=float(np.median(x)),
                p05=float(np.percentile(x, 5)), p95=float(np.percentile(x, 95)),
                frac_abs_ge_1=float((np.abs(x) >= 1).mean()),
                frac_abs_ge_2=float((np.abs(x) >= 2).mean()),
                frac_abs_ge_3=float((np.abs(x) >= 3).mean()))


def main():
    t0 = time.time()
    fields, cat, fp, meta = L.load(with_lidar=True)
    print(f"footprint {meta['cells']} cells, catalogue {meta['catalogue_cells']} px", flush=True)
    rec = C.measure(fields, cat, fp)
    u_dem = C.usable(rec, both=False)
    u_both = C.usable(rec, both=True)
    out = dict(
        experiment="E1 catalogue-to-evidence perpendicular offset",
        evidence_class="MEASURED on this machine; descriptive statistic, not a score",
        grid=dict(shape=list(cat.shape), footprint_cells=meta["cells"], catalogue_cells=meta["catalogue_cells"]),
        method=dict(half_window_px=C.HALF_WINDOW_PX, step_px=C.STEP_PX, smooth_px=C.SMOOTH_PX,
                    min_prominence_frac=C.MIN_PROM_FRAC, strike_window_px=5,
                    dem_field="det_elev band 12, crest = max(-d2z/dn2) nearest to the trace",
                    mag_field="|tmi_hg| band 3, ridge = max nearest to the trace",
                    grav_field="|iso_grav_anom_hg| band 18, corroboration only",
                    sign="+1 = left of strike, along (-tx, ty) in (row, col) space"),
        coverage=dict(
            pixels_with_strike=int(rec["strike_ok"].sum()),
            transects_valid=int(rec["valid"].sum()),
            dem_crest_found=int(u_dem.sum()), mag_crest_found=int(np.isfinite(rec["mag_off_px"]).sum()),
            both_crests_found=int(u_both.sum()),
            usable_fraction_of_catalogue=float(u_both.sum() / max(1, meta["catalogue_cells"]))),
    )
    # ---- the headline histograms, in pixels and metres
    for fam, key in (("dem", "dem_off_px"), ("mag", "mag_off_px"), ("grav", "grv_off_px")):
        out[f"signed_offset_px_{fam}"] = hist(rec[key][rec["valid"]])
        a = np.abs(rec[key][rec["valid"]])
        a = a[np.isfinite(a)]
        out[f"abs_offset_px_{fam}"] = dict(counts=[int(v) for v in np.histogram(a, bins=[0, .5, 1, 1.5, 2, 2.5, 3, 4])[0]],
                                           edges=[0, .5, 1, 1.5, 2, 2.5, 3, 4], n=int(a.size),
                                           median=float(np.median(a)), p90=float(np.percentile(a, 90)),
                                           median_m=float(np.median(a) * 100.0))
    joint, corr = C.joint_offset(rec, C.usable(rec, both=False))
    out["signed_offset_px_joint"] = hist(joint[corr])
    out["corroboration"] = dict(both_families_within_1px_and_same_sign=float(corr[rec["valid"]].mean()),
                                dem_mag_pearson_r=float(np.corrcoef(rec["dem_off_px"][u_both], rec["mag_off_px"][u_both])[0, 1]))
    # ---- nulls
    ctl = C.control_points(fields, cat, fp, mode="random", n=int(u_both.sum()))
    ctlr = C.control_points(fields, cat, fp, mode="rotated", n=0)
    out["null_random"] = dict(n=int(ctl["valid"].sum()),
                              abs_offset_median_px=float(np.median(np.abs(ctl["dem_off_px"][ctl["valid"]]))),
                              abs_offset_median_px_mag=float(np.median(np.abs(ctl["mag_off_px"][ctl["valid"]]))),
                              abs_offset_hist_dem=hist(ctl["dem_off_px"][ctl["valid"]]),
                              note="distance from an arbitrary point with no trace to the nearest crest")
    out["null_rotated"] = dict(n=int(ctlr["valid"].sum()),
                               abs_offset_median_px=float(np.median(np.abs(ctlr["dem_off_px"][ctlr["valid"]]))),
                               abs_offset_median_px_mag=float(np.median(np.abs(ctlr["mag_off_px"][ctlr["valid"]]))))
    # ---- corridors
    rows, joint2, corr2, u2 = C.corridor_table(rec, cat)
    q = [r for r in rows if r["qualifies"]]
    out["corridors"] = dict(components_evaluated=len(rows), qualifying=len(q),
                            qualifying_length_m=float(sum(r["length_m"] for r in q)),
                            qualifying_pixels=int(sum(r["n_usable"] for r in q)),
                            qualifying_joint_median_px=float(np.median([r["joint_med"] for r in q])) if q else None,
                            top=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
                                 for r in sorted(rows, key=lambda r: -abs(r["joint_med"]) if np.isfinite(r["joint_med"]) else 0)[:25]])
    out["decision_input"] = dict(
        global_median_abs_offset_px=float(np.median(np.abs(joint[corr]))),
        rule="emit on the evidence trace only where a corridor's consistent |joint offset| >= 2 px (200 m)",
        emit_anything=bool(q))
    (ROOT / "evidence" / "offsets_v1.json").write_text(json.dumps(out, indent=1, default=float))
    np.savez_compressed(ROOT / "evidence" / "offsets_v1_rows.npz", **{k: v for k, v in rec.items()})
    with gzip.open(ROOT / "evidence" / "offsets_v1_corridors.json.gz", "wt") as fh:
        json.dump(rows, fh)
    print(json.dumps({k: out[k] for k in ("coverage", "corroboration", "null_random", "null_rotated", "decision_input")},
                     indent=1, default=float))
    print("dem signed:", json.dumps(out["signed_offset_px_dem"], default=float)[:400])
    print("corridors:", json.dumps(out["corridors"], default=float)[:600])
    print(f"elapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
