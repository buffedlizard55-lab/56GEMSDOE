#!/usr/bin/env python3
"""Assign every catalogue fault pixel to a vector-catalogue record_id.

Source (official, verified): the USGS Quaternary fault + INGENIOUS compilation
shapefile `qfaults_ingenious_nad83conus117_2023-06-27.shp`, exported to UTM zone
11N segments as `trace_segments_utm11.csv` (84,331 segments, 1,126 named records)
in the sibling repository GEMSDOE51 `registry/official/` (sha256-pinned there in
`receipt.json`).  Download origin: GDR submission 1391
https://gdr.openei.org/submissions/1391 (CC BY 4.0) / USGS ScienceBase
https://www.sciencebase.gov/catalog/item/589097b1e4b072a7ac0cae23 (public domain).

Output: data/cache/fault_px_record.npz  (row, col, record, dist_to_segment_px)
for every pixel with labels == 1.

Run:  python scripts/prepare_records.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

GRID_ORIGIN_X, GRID_ORIGIN_Y = 243350.0, 4508550.0   # official grid (EPSG:32611, 100 m)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--segments", default="data/cache/trace_segments_utm11.csv")
    ap.add_argument("--out", default="data/cache/fault_px_record.npz")
    args = ap.parse_args()

    seg = pd.read_csv(args.segments)
    print(f"vector segments: {len(seg):,}  records: {seg.record_id.nunique():,}")

    # segment endpoints -> pixel coords (row = (origin_y - y)/100, col = (x - origin_x)/100)
    r0 = (GRID_ORIGIN_Y - seg.y0.values) / 100.0
    c0 = (seg.x0.values - GRID_ORIGIN_X) / 100.0
    r1 = (GRID_ORIGIN_Y - seg.y1.values) / 100.0
    c1 = (seg.x1.values - GRID_ORIGIN_X) / 100.0

    # densify each segment every 10 m (0.1 px) so nearest-point lookup is accurate
    pts_r, pts_c, pts_id = [], [], []
    for a, b, cc_, d, rid in zip(r0, r1, c0, c1, seg.record_id.values):
        length_px = float(np.hypot(b - a, d - cc_))
        n = max(2, int(length_px / 0.1) + 1)
        for tt in np.linspace(0.0, 1.0, n):
            pts_r.append(a + (b - a) * tt)
            pts_c.append(cc_ + (d - cc_) * tt)
            pts_id.append(rid)
    pts_r = np.asarray(pts_r)
    pts_c = np.asarray(pts_c)
    pts_id = np.asarray(pts_id)
    print(f"densified vector points: {len(pts_r):,}")

    with rasterio.open(args.labels) as src:
        lab = src.read(1)
    fr, fc = np.nonzero(lab == 1)
    print(f"catalogue fault px: {len(fr):,}")

    tree = cKDTree(np.column_stack([pts_r, pts_c]))
    dist, idx = tree.query(np.column_stack([fr, fc]), k=1)
    print("fault px -> nearest vector segment (px): median %.3f  p95 %.3f  max %.3f"
          % (np.median(dist), np.percentile(dist, 95), dist.max()))
    print("within 1.5 px: %.2f%%" % (100.0 * (dist <= 1.5).mean()))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, row=fr, col=fc, record=pts_id[idx].astype(str), dist=dist)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
