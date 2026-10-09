"""Uniqueness audit against every earlier raster in the sibling GEMS repositories (experiment 3 of 3).

Input : a directory of GeoTIFFs mirrored from the account's GEMSDOE* repositories
        (mirror procedure: scripts/mirror_registry.sh).
Output: docs/research/registry-index.json  - one row per TIF: path, sha256, grid check, value stats.
        docs/research/registry-summary.json - duplicate-hash groups and grid statistics.

Why: the brief requires a submission to be uniqueness-checked against every earlier raster,
and the grid check guards against placing a raster on the wrong footprint.
"""

import glob
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import rasterio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from gems.submission import REF_CRS, REF_HEIGHT, REF_WIDTH, REF_TRANSFORM  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(root, out_dir):
    rows = []
    for f in sorted(glob.glob(os.path.join(root, "**", "*.tif"), recursive=True)):
        rel = os.path.relpath(f, root)
        try:
            with rasterio.open(f) as ds:
                a = ds.read(1)
                t = ds.transform
                on_grid = bool(
                    ds.crs and ds.crs.to_string() == REF_CRS and ds.width == REF_WIDTH and ds.height == REF_HEIGHT
                    and all(abs(x - y) < 1e-6 for x, y in zip(tuple(t)[:6], tuple(REF_TRANSFORM)[:6])))
                af = a.astype(np.float64)
                finite = np.isfinite(af)
                rows.append(dict(
                    path=rel, dtype=str(a.dtype), crs=ds.crs.to_string() if ds.crs else None,
                    width=ds.width, height=ds.height, on_reference_grid=on_grid,
                    nodata=None if ds.nodata is None else float(ds.nodata),
                    n_nan=int(np.isnan(af).sum()),
                    vmin=float(af[finite].min()) if finite.any() else None,
                    vmax=float(af[finite].max()) if finite.any() else None,
                    n_positive=int((np.nan_to_num(af) > 0).sum()),
                    bytes=os.path.getsize(f), sha256=sha256(f)))
        except Exception as e:  # keep the audit complete even for unreadable files
            rows.append(dict(path=rel, error=str(e)[:200]))

    by_hash = defaultdict(list)
    for r in rows:
        if "sha256" in r:
            by_hash[r["sha256"]].append(r["path"])
    dup_groups = sorted([v for v in by_hash.values() if len(v) > 1], key=len, reverse=True)
    readable = [r for r in rows if "error" not in r]
    summary = dict(
        files=len(rows), readable=len(readable), unreadable=len(rows) - len(readable),
        on_reference_grid=sum(r["on_reference_grid"] for r in readable),
        off_grid=sum(not r["on_reference_grid"] for r in readable),
        distinct_sha256=len(by_hash),
        files_sharing_a_hash_with_another=sum(len(g) for g in dup_groups),
        duplicate_groups=len(dup_groups),
        largest_duplicate_groups=[g[:6] + (["..."] if len(g) > 6 else []) for g in dup_groups[:10]],
        dtypes=dict(Counter(r["dtype"] for r in readable)),
        crs=dict(Counter(r["crs"] for r in readable)),
        note=("on_reference_grid counts EPSG:32611, 3292x3730, 100 m, origin (243350, 4508550). "
              "Files off-grid cannot be a direct submission for this competition."),
    )
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "registry-index.json"), "w") as f:
        json.dump(rows, f, indent=1)
    with open(os.path.join(out_dir, "registry-summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2)[:3000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
