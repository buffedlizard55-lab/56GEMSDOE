#!/usr/bin/env python3
"""Uniqueness check for the final submission: compare decoded support against
every other TIF in docs/downloads (this repo's earlier attempts) and against
the corrections-lane prior and the h56-dotted-ridge parent (40199 dots) to
confirm it is a distinct pixel set."""
from __future__ import annotations
import sys, json, hashlib
from pathlib import Path
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FINAL = ROOT / "docs" / "downloads" / "h56-final-dotted-ridge-d2p8-20261009T190421Z.tif"
SAMPLE = ROOT / "data" / "grid" / "sample_submission.tif"


def canonical(path):
    with rasterio.open(path) as src:
        a = src.read(1)
    return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype("<f4")


def sha_pix(a):
    return hashlib.sha256(np.ascontiguousarray(a, "<f4").tobytes()).hexdigest()


def main():
    with rasterio.open(SAMPLE) as s:
        tmpl = s.read(1)
    fp = np.isfinite(tmpl)
    cand = canonical(FINAL)
    cand_bin = cand > 0
    cand_sha = sha_pix(cand)
    n_new = int(cand_bin.sum())
    print(f"candidate: {FINAL.name}")
    print(f"  sha256 (file): {hashlib.sha256(FINAL.read_bytes()).hexdigest()}")
    print(f"  sha256 (pixels): {cand_sha}")
    print(f"  dots: {n_new}")
    rows = []
    for tif in sorted((ROOT / "docs" / "downloads").glob("*.tif")):
        if tif.resolve() == FINAL.resolve():
            continue
        try:
            with rasterio.open(tif) as d:
                if d.shape != cand.shape or d.count != 1:
                    rows.append(dict(path=tif.name, error="shape/band mismatch"))
                    continue
            old = canonical(tif)
            binary = bool(np.all((old[fp] == 0) | (old[fp] == 1)))
            old_bin = old > 0 if binary else old >= 0.5
            inter = int((cand_bin & old_bin).sum())
            union = int((cand_bin | old_bin).sum())
            jac = inter / max(union, 1)
            c_in_o = inter / max(n_new, 1)
            o_in_c = inter / max(int(old_bin.sum()), 1)
            same = bool(np.array_equal(cand, old))
            rows.append(dict(path=tif.name, dots=int(old_bin.sum()), jaccard=round(jac,4),
                             cand_in_old=round(c_in_o,4), old_in_cand=round(o_in_c,4),
                             identical=same, sha=sha_pix(old)[:16]))
        except Exception as e:
            rows.append(dict(path=tif.name, error=f"{type(e).__name__}: {e}"))
    for r in rows:
        print(json.dumps(r))
    # Max containment check (parallel-run protocol: >70% within 3 px of another raster = duplicate)
    from scipy.ndimage import binary_dilation
    max_cin = 0.0
    max_cin_path = None
    for r in rows:
        if "error" in r or r.get("identical"):
            continue
        tif = ROOT / "docs" / "downloads" / r["path"]
        old = canonical(tif)
        old_bin = old > 0 if (old[fp].min() == 0 and old[fp].max() == 1) else old >= 0.5
        halo = binary_dilation(old_bin, iterations=3)
        near = float((cand_bin & halo).sum()) / n_new
        if near > max_cin:
            max_cin = near
            max_cin_path = r["path"]
        print(f"  near-3px vs {r['path']}: {near:.4f}")
    print(f"\nworst cand-in-old within 3 px: {max_cin:.4f} ({max_cin_path})")
    print("protocol thresholds: Spearman <= 0.90 and containment <= 0.70")
    print("DUPLICATE?:", bool(max_cin > 0.70))


if __name__ == "__main__":
    main()
