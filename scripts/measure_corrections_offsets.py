#!/usr/bin/env python3
"""Corrections lane, deliverable 1: the catalogue-to-evidence offset histogram.

Samples perpendicular transects within +/-400 m of every catalogue trace, locates
the crest of the DEM scarp (det_elev_slope ridge) and of the magnetic gradient
ridge (tmi_hg) - both the dominant ("strongest") crest in the window and the
crest nearest the catalogue line - calibrates against the cached 1 m LiDAR
scarp product, and publishes:

  evidence/corrections/offset_histogram.png    multi-panel histogram + CDF
  evidence/corrections/offset_histogram.csv    binned counts per band/definition
  evidence/corrections/offset_transects.csv    one row per transect
  evidence/corrections/record_offsets_<band>_<def>.csv   per-record consistency
  evidence/corrections/offset_stats.json       robust stats + decision inputs

Run:  python scripts/measure_corrections_offsets.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import corrections as C  # noqa: E402


def plot_histograms(res, stats, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = [(b, d) for b in C.EVIDENCE_BANDS for d in ("strongest", "nearest")]
    colors = {"dem_slope": "#2c7fb8", "mag_hg": "#cb181d"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    bins = np.arange(-4.5, 4.51, 0.5)
    for ax, (band, definition) in zip(axes[0], keys):
        ok = res.ok(band, definition)
        vals = res.t(band, definition)[ok]
        ax.hist(vals, bins=bins, color=colors[band], edgecolor="white", linewidth=0.4)
        ax.axvline(0, color="black", lw=1)
        ax.axvline(np.median(vals), color="#d7301f", lw=1.2)
        ax.set_title(f"{band} {definition} (n={ok.sum():,})\n"
                     f"median {np.median(vals):+.2f} px, MAD "
                     f"{np.median(np.abs(vals - np.median(vals))):.2f} px")
        ax.set_xlabel("signed offset catalogue -> crest (px, 100 m)")
        ax.set_ylabel("transects")
    # |offset| CDF
    ax = axes[1][0]
    for band, definition in keys:
        ok = res.ok(band, definition)
        vals = np.abs(res.t(band, definition)[ok])
        qs = np.linspace(0, 1, 200)
        ax.plot(np.quantile(vals, qs), qs, color=colors[band],
                ls="-" if definition == "strongest" else "--",
                label=f"{band} {definition}")
    for x, lab in ((1, "1 px"), (2, "2 px"), (3, "kernel R=3 px"), (4, "4 px")):
        ax.axvline(x, color="grey", ls=":", lw=0.8)
        ax.text(x, 0.02, lab, rotation=90, fontsize=7, va="bottom")
    ax.set_xlabel("|offset| (px)")
    ax.set_ylabel("quantile")
    ax.set_title("|offset| CDF")
    ax.legend(fontsize=7)
    # record-level median |offset| per band (strongest)
    ax = axes[1][1]
    for band in C.EVIDENCE_BANDS:
        ok = res.ok(band, "strongest")
        rec = C.record_consistency(res.t(band, "strongest")[ok], res.perp_r[ok],
                                   res.perp_c[ok], res.record_ids[ok])
        med = np.array([v["median_offset_px"] for v in rec.values()])
        ax.hist(np.abs(med), bins=np.arange(0, 4.51, 0.25), histtype="step",
                color=colors[band], label=f"{band} strongest", lw=1.4)
    ax.axvline(2, color="black", ls="--", lw=1)
    ax.text(2.02, 0.6, "2 px emission threshold", rotation=90, fontsize=7)
    ax.set_xlabel("|record median offset| (px)")
    ax.set_ylabel("records")
    ax.set_title("per-record consistency (strongest crest)")
    ax.legend(fontsize=7)
    # LiDAR calibration
    ax = axes[1][2]
    if res.lidar_t_strongest is not None and res.lidar_ok_strongest.any():
        lok = res.lidar_ok_strongest
        ax.hist(res.lidar_t_strongest[lok], bins=bins, color="#006d2c",
                edgecolor="white", linewidth=0.4, alpha=0.85,
                label=f"LiDAR strongest (n={lok.sum():,})")
        for band in C.EVIDENCE_BANDS:
            both = lok & res.ok(band, "strongest")
            if both.any():
                ax.hist(res.t(band, "strongest")[both], bins=bins, histtype="step",
                        lw=1.2, color=colors[band], label=f"{band} strongest (same transects)")
        ax.axvline(0, color="black", lw=1)
        ax.set_title("catalogue -> crest, LiDAR-calibrated transects")
        ax.set_xlabel("signed offset (px)")
        ax.legend(fontsize=7)
    else:
        ax.text(0.5, 0.5, "no LiDAR coverage", ha="center", va="center")
    fig.suptitle("Corrections lane: catalogue-to-evidence offset histogram "
                 "(+/-400 m perpendicular transects, 100 m grid)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--features", default="data/training_features.tif")
    ap.add_argument("--records", default="data/cache/fault_px_record.npz")
    ap.add_argument("--lidar", default="data/cache/lidar_scarp_features_u8.tif")
    ap.add_argument("--out", default="evidence/corrections")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("[1/4] measuring catalogue-to-evidence offsets")
    res = C.run_measurement(args.labels, args.features, args.records, args.lidar)
    fault, footprint = C.load_labels(args.labels)
    stats = C.summarise(res, fault)
    print(f"      catalogue fault px: {stats['catalogue_fault_px']:,}  "
          f"records: {stats['n_records']:,}  transects: {stats['n_transects']:,}")

    print("[2/4] writing per-transect and per-record tables")
    pd.DataFrame(C.transect_table(res)).to_csv(out / "offset_transects.csv", index=False)
    for band in C.EVIDENCE_BANDS:
        for definition in ("strongest", "nearest"):
            pd.DataFrame(C.record_table(res, band, definition)).to_csv(
                out / f"record_offsets_{band}_{definition}.csv", index=False)

    print("[3/4] writing offset histogram (png + csv)")
    bins = np.arange(-4.5, 4.51, 0.25)
    rows = []
    for band in C.EVIDENCE_BANDS:
        for definition in ("strongest", "nearest"):
            ok = res.ok(band, definition)
            counts, edges = np.histogram(res.t(band, definition)[ok], bins=bins)
            for i, n in enumerate(counts):
                rows.append(dict(band=band, definition=definition,
                                 bin_lo_px=edges[i], bin_hi_px=edges[i + 1],
                                 bin_lo_m=edges[i] * C.PX_M, bin_hi_m=edges[i + 1] * C.PX_M,
                                 count=int(n)))
    if res.lidar_t_strongest is not None:
        for definition, ok in (("strongest", res.lidar_ok_strongest),
                               ("nearest", res.lidar_ok_nearest)):
            counts, edges = np.histogram(res.lidar_t_strongest[ok] if definition == "strongest"
                                         else res.lidar_t_nearest[ok], bins=bins)
            for i, n in enumerate(counts):
                rows.append(dict(band="lidar_lapneg", definition=definition,
                                 bin_lo_px=edges[i], bin_hi_px=edges[i + 1],
                                 bin_lo_m=edges[i] * C.PX_M, bin_hi_m=edges[i + 1] * C.PX_M,
                                 count=int(n)))
    pd.DataFrame(rows).to_csv(out / "offset_histogram.csv", index=False)
    plot_histograms(res, stats, out / "offset_histogram.png")

    print("[4/4] writing stats json")
    (out / "offset_stats.json").write_text(json.dumps(stats, indent=1))

    # ---- console decision summary -------------------------------------------
    print("\n=== pooled transect offsets (unambiguous crests) ===")
    for band in C.EVIDENCE_BANDS:
        for definition in ("strongest", "nearest"):
            s = stats["bands"][f"{band}_{definition}"]
            o = s["offset"]
            print(f"  {band:9s} {definition:9s} n={o.get('n', 0):6d}  "
                  f"median={o.get('median_px', float('nan')):+.3f} px "
                  f"({o.get('median_m', float('nan')):+.0f} m)  MAD={o.get('mad_px', float('nan')):.3f} px  "
                  f"|d|<=1px {o.get('pct_abs_le_1px', 0) * 100:5.1f}%  <=2px {o.get('pct_abs_le_2px', 0) * 100:5.1f}%  "
                  f">2px {o.get('pct_abs_gt_2px', 0) * 100:5.1f}%  >3px {o.get('pct_abs_gt_3px', 0) * 100:5.1f}%")
    print("\n=== per-record consistency (strongest crest; consistent = |median|>2px & agr>=0.7 & n>=8) ===")
    for band in C.EVIDENCE_BANDS:
        s = stats["records"][f"{band}_strongest"]
        print(f"  {band:9s} records={s.get('n_records', 0):5d}  sampled={s.get('n_records_sampled', 0):5d}  "
              f"consistent>2px={s.get('n_consistent_offset_gt_2px', 0):4d} "
              f"({s.get('frac_consistent_offset_gt_2px', 0) * 100:4.1f}%)  "
              f"median|med|={s.get('median_abs_offset_px', float('nan')):.3f} px  "
              f"|med|>2px:{s.get('records_offset_gt_2px', 0)}  >3px:{s.get('records_offset_gt_3px', 0)}")
    lc = stats["lidar_calibration"]
    if lc:
        print("\n=== LiDAR calibration (1 m 3DEP) ===")
        for definition in ("strongest", "nearest"):
            o = lc.get(f"offset_{definition}", {})
            print(f"  catalogue->LiDAR {definition:9s} n={o.get('n', 0):5d}  "
                  f"median={o.get('median_px', float('nan')):+.3f} px "
                  f"MAD={o.get('mad_px', float('nan')):.3f} px  "
                  f"|d|>2px {o.get('pct_abs_gt_2px', 0) * 100:.1f}%")
        for band in C.EVIDENCE_BANDS:
            a = lc.get(f"agreement_{band}_strongest_vs_lidar_strongest")
            if a and a.get("n"):
                print(f"  {band} strongest crest - LiDAR crest: n={a['n']} "
                      f"median={a['median_px']:+.3f} px  MAD={a['mad_px']:.3f} px  "
                      f"|d|<=1px {a['pct_abs_le_1px'] * 100:.1f}%  <=2px {a['pct_abs_le_2px'] * 100:.1f}%")
    print(f"\nArtifacts in {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
