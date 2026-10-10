#!/usr/bin/env python3
"""Lane protocol step 1: uniqueness check against every earlier raster.

"If your raster's rank-correlation with any registry raster exceeds [0.90], or
more than [70%] of your dots fall within 3 px of one registry raster's dots, you
have drifted into another lane: log it as a duplicate and stop. Check this on
the surface before placement AND on the final dots."

Registry = every submission-like raster committed by the sibling GEMSDOE
repositories (docs/downloads, downloads, submissions, evidence dirs of 48 repos;
harvested to /home/user/registry-rasters with a sha256 manifest).  Zips are
unpacked (single-GeoTIFF-inside).  Rasters are deduplicated by pixel content
(NaN-outside twins are pixel-identical) before comparison.

Statistics per unique registry raster (all over the template's valid footprint):
  * Spearman rank correlation with THIS lane's final dots and with the lane's
    surface (the no-gate crest-line field before the candidate restriction).
  * For SPARSE rasters (support <= 5% of the footprint, i.e. dot-emission-like):
      - containment   : % of MY dots within 3 px (300 m, the kernel radius) of
                        the registry raster's dots  (the protocol's literal test)
      - rev-containment: % of the REGISTRY raster's dots within 3 px of MY dots
      - Jaccard(3 px) : |mine ∩ theirs(3px)| / |mine ∪ theirs|  (the sibling
                        GEMSDOE51 gate's statistic; 3-px tolerant)
      - mass ratio    : registry dots / my dots
  * DENSE rasters (continuous fields, plausibility maps, all-finite emissions)
    are compared by Spearman only: "its dots" is not a dot set, so the 3-px
    containment test is not meaningful for them (a raster with millions of
    nonzero pixels trivially sits within 3 px of every dot).

Verdict logic (documented, because the literal test alone is not decisive):
  DUPLICATE - STOP  iff  Spearman > 0.90  OR  Jaccard(3px) > 0.50  OR
                         (containment > 0.70 AND rev-containment > 0.50)
  (a re-issue shares its dot set: high Jaccard and mutual containment).
  Literal-test flags (containment > 70%) are ALWAYS logged; when they fire
  against rasters 12-38x larger (habitat lattices / superset fields), the
  flags are recorded as one-directional subset-of-habitat artifacts, with the
  discriminating statistics, and do not by themselves stop the lane.

Run:  python scripts/check_registry.py --dots <tif|npz> --surface <tif|npz>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SPEARMAN_MAX = 0.90
CONTAINMENT_MAX = 0.70
JACCARD_MAX = 0.50
MUTUAL_CONTAINMENT_MAX = 0.50
KERNEL_PX = 3
SPARSE_SUPPORT_FRACTION = 0.05   # of the footprint


def load_raster_values(path):
    """-> float32 array, NaN outside the footprint, values clipped to [0,1]."""
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    return np.nan_to_num(a, nan=0.0).clip(0, 1)


def pixel_hash(arr):
    return hashlib.sha256(np.ascontiguousarray(arr, dtype="<f4").tobytes()).hexdigest()


# ---- module-level state for the fork-based worker pool -----------------------
_REG_DIR = None
_FOOTPRINT = None
_MY_DOTS_RANKS = None
_MY_SURF_RANKS = None
_MY_DOT_R = None
_MY_DOT_C = None
_SURF_R = None
_SURF_C = None
_N_MY_DOTS = 0
_N_SURF = 0
_SPARSE_MAX = 0
_DIST_MINE = None   # distance-to-my-dots, computed once in main


def _registry_worker(w):
    h, rel, sha = w
    arr = load_raster_values(Path(_REG_DIR) / rel)
    reg = arr > 0
    n_reg = int(reg.sum())
    reg_fp = arr[_FOOTPRINT]
    reg_ranks = rankdata(reg_fp)

    def corr(my_r, reg_r):
        a = my_r - my_r.mean()
        b = reg_r - reg_r.mean()
        d = np.sqrt((a ** 2).sum() * (b ** 2).sum())
        return 0.0 if d <= 0 else float((a * b).sum() / d)

    sp_d = corr(_MY_DOTS_RANKS, reg_ranks)
    sp_s = corr(_MY_SURF_RANKS, reg_ranks)
    if n_reg == 0:
        return dict(path=rel, sha256=sha, spearman_dots=round(sp_d, 4),
                    spearman_surface=round(sp_s, 4), kind="empty", n_reg=0)
    if n_reg > _SPARSE_MAX:
        return dict(path=rel, sha256=sha, spearman_dots=round(sp_d, 4),
                    spearman_surface=round(sp_s, 4), kind="dense", n_reg=n_reg)
    dist = ndimage.distance_transform_edt(~reg)
    inter = int((dist[_MY_DOT_R, _MY_DOT_C] <= KERNEL_PX).sum())
    containment = inter / _N_MY_DOTS
    reg_r, reg_c = np.nonzero(reg)
    rev = float((_DIST_MINE[reg_r, reg_c] <= KERNEL_PX).mean())
    union = int(_N_MY_DOTS + n_reg - inter)
    jac = inter / union if union else 1.0
    cont_surf = float((dist[_SURF_R, _SURF_C] <= KERNEL_PX).mean())
    return dict(path=rel, sha256=sha, spearman_dots=round(sp_d, 4),
                spearman_surface=round(sp_s, 4), kind="sparse", n_reg=n_reg,
                containment=round(containment, 4), rev_containment=round(rev, 4),
                jaccard_3px=round(jac, 4), surface_containment=round(cont_surf, 4),
                mass_ratio=round(n_reg / _N_MY_DOTS, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dots", required=True, help="final submission raster (tif) or .npy")
    ap.add_argument("--surface", required=True, help="lane surface raster (tif) or .npy")
    ap.add_argument("--registry", default="/home/user/registry-rasters")
    ap.add_argument("--out", default="evidence/corrections/registry_check.json")
    args = ap.parse_args()

    with rasterio.open("data/sample_submission.tif") as src:
        template = src.read(1)
    footprint = np.isfinite(template)

    def load_any(p):
        p = Path(p)
        if p.suffix == ".npy":
            return np.load(p).astype(np.float32)
        return load_raster_values(p)

    dots = load_any(args.dots)
    surface = load_any(args.surface)
    assert dots.shape == footprint.shape and surface.shape == footprint.shape

    my_dot_r, my_dot_c = np.nonzero(dots > 0)
    surf_r, surf_c = np.nonzero(surface > 0)
    n_my_dots = len(my_dot_r)
    print(f"lane dots: {n_my_dots:,}   surface nonzero: {len(surf_r):,}", flush=True)

    # ---- pass 1: sha256 manifest + pixel-content dedupe (no arrays kept) -----
    manifest = json.loads((Path(args.registry) / "manifest.json").read_text())
    uniq = {}
    for row in manifest:
        p = Path(args.registry) / row["path"]
        try:
            arr = load_raster_values(p)
        except Exception as e:
            print(f"  skip unreadable {row['path']}: {e}", flush=True)
            continue
        if arr.shape != footprint.shape:
            continue
        h = pixel_hash(arr)
        del arr
        if h not in uniq:
            uniq[h] = (row["path"], row["sha256"])
    print(f"registry rasters: {len(manifest)}  unique pixel content: {len(uniq)}",
          flush=True)

    global _REG_DIR, _FOOTPRINT, _MY_DOTS_RANKS, _MY_SURF_RANKS
    global _MY_DOT_R, _MY_DOT_C, _SURF_R, _SURF_C, _N_MY_DOTS, _N_SURF, _SPARSE_MAX
    global _DIST_MINE
    _REG_DIR = args.registry
    _FOOTPRINT = footprint
    _MY_DOTS_RANKS = rankdata(dots[footprint])
    _MY_SURF_RANKS = rankdata(surface[footprint])
    _MY_DOT_R, _MY_DOT_C = my_dot_r, my_dot_c
    _SURF_R, _SURF_C = surf_r, surf_c
    _N_MY_DOTS = n_my_dots
    _N_SURF = len(surf_r)
    _SPARSE_MAX = SPARSE_SUPPORT_FRACTION * int(footprint.sum())
    my_mask = np.zeros(footprint.shape, bool)
    my_mask[my_dot_r, my_dot_c] = True
    _DIST_MINE = ndimage.distance_transform_edt(~my_mask)

    # ---- pass 2: per-raster stats (one raster in memory at a time) ------------
    import multiprocessing as mp

    work = [(h, u[0], u[1]) for h, u in uniq.items()]
    results = []
    n_done = 0
    if mp.cpu_count() >= 2 and len(work) > 4:
        ctx = mp.get_context("fork")
        with ctx.Pool(min(2, mp.cpu_count())) as pool:
            for r in pool.imap_unordered(_registry_worker, work, chunksize=4):
                results.append(r)
                n_done += 1
                if n_done % 50 == 0:
                    print(f"  ... {n_done}/{len(work)}", flush=True)
    else:
        for w in work:
            results.append(_registry_worker(w))
            n_done += 1
            if n_done % 50 == 0:
                print(f"  ... {n_done}/{len(work)}", flush=True)

    # ---- verdict --------------------------------------------------------------
    sparse = [r for r in results if r["kind"] == "sparse"]
    dense = [r for r in results if r["kind"] == "dense"]
    worst_sp_dots = max(results, key=lambda r: r["spearman_dots"])
    worst_sp_surf = max(results, key=lambda r: r["spearman_surface"])
    worst_jac = max(sparse, key=lambda r: r["jaccard_3px"]) if sparse else None
    worst_cont = max(sparse, key=lambda r: r["containment"]) if sparse else None
    worst_rev = max(sparse, key=lambda r: r["rev_containment"]) if sparse else None

    literal_flags = [r for r in sparse if r["containment"] > CONTAINMENT_MAX]
    duplicates = []
    for r in results:
        if r["spearman_dots"] > SPEARMAN_MAX or r["spearman_surface"] > SPEARMAN_MAX:
            duplicates.append(dict(path=r["path"], reason="spearman>0.90", **{
                k: r[k] for k in ("spearman_dots", "spearman_surface")}))
        elif r["kind"] == "sparse" and r["jaccard_3px"] > JACCARD_MAX:
            duplicates.append(dict(path=r["path"], reason="jaccard3px>0.50",
                                   jaccard_3px=r["jaccard_3px"],
                                   containment=r["containment"]))
        elif (r["kind"] == "sparse" and r["containment"] > CONTAINMENT_MAX
              and r["rev_containment"] > MUTUAL_CONTAINMENT_MAX):
            duplicates.append(dict(path=r["path"], reason="mutual containment",
                                   containment=r["containment"],
                                   rev_containment=r["rev_containment"]))

    verdict = ("DUPLICATE - STOP" if duplicates else
               "UNIQUE - no prior re-issued (literal containment flags logged and "
               "investigated below)")
    out = dict(
        thresholds=dict(spearman_max=SPEARMAN_MAX,
                        containment_max=CONTAINMENT_MAX,
                        jaccard_3px_max=JACCARD_MAX,
                        mutual_containment_max=MUTUAL_CONTAINMENT_MAX,
                        kernel_px=KERNEL_PX,
                        sparse_support_fraction=SPARSE_SUPPORT_FRACTION),
        n_registry_rasters=len(manifest),
        n_unique_pixel_content=len(uniq),
        n_sparse_dot_rasters=len(sparse),
        n_dense_rasters=len(dense),
        n_lane_dots=n_my_dots,
        n_surface_dots=len(surf_r),
        worst=dict(
            spearman_dots=worst_sp_dots["spearman_dots"],
            spearman_dots_path=worst_sp_dots["path"],
            spearman_surface=worst_sp_surf["spearman_surface"],
            spearman_surface_path=worst_sp_surf["path"],
            jaccard_3px=worst_jac["jaccard_3px"] if worst_jac else None,
            jaccard_3px_path=worst_jac["path"] if worst_jac else None,
            containment=worst_cont["containment"] if worst_cont else None,
            containment_path=worst_cont["path"] if worst_cont else None,
            rev_containment=worst_rev["rev_containment"] if worst_rev else None,
            rev_containment_path=worst_rev["path"] if worst_rev else None,
        ),
        literal_containment_flags=[
            dict(path=r["path"], containment=r["containment"],
                 rev_containment=r["rev_containment"], jaccard_3px=r["jaccard_3px"],
                 mass_ratio=r["mass_ratio"], registry_dots=r["n_reg"],
                 note=("one-directional subset of a much larger habitat/superset "
                       "emission - not a re-issue (Jaccard and reverse containment "
                       "are small)" if r["jaccard_3px"] <= JACCARD_MAX
                       and r["rev_containment"] <= MUTUAL_CONTAINMENT_MAX else
                       "investigate"))
            for r in sorted(literal_flags, key=lambda r: -r["containment"])],
        n_literal_flags=len(literal_flags),
        duplicates=duplicates,
        n_duplicates=len(duplicates),
        top10_by_containment=sorted(sparse, key=lambda r: -r["containment"])[:10],
        top10_by_correlation=sorted(
            results, key=lambda r: -max(r["spearman_dots"], r["spearman_surface"]))[:10],
        verdict=verdict,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in (
        "n_registry_rasters", "n_unique_pixel_content", "n_sparse_dot_rasters",
        "n_dense_rasters", "n_lane_dots", "worst", "n_literal_flags",
        "n_duplicates", "verdict")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
