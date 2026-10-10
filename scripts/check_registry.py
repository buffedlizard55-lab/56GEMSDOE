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

Statistics per unique registry raster (over the template's valid footprint):
  * Spearman rank correlation with THIS lane's final dots and with the lane's
    surface (the no-gate crest-line field before the candidate restriction).
  * Directed proximity: fraction of MY final dots within 3 px of nonzero cells
    in that registry raster. Apply this literal threshold to sparse and dense
    rasters alike; Jaccard, reverse containment, support size, and mass ratio
    are diagnostics only and cannot waive a stop.
  * Jaccard and reverse containment are retained for audit, not used to redefine
    the user's one-way duplicate rule.

Verdict logic:
  DUPLICATE - STOP iff Spearman(dots) > 0.90 OR Spearman(surface) > 0.90 OR
  directed final-dot proximity > 0.70 against any registry raster.
  Every literal proximity flag is logged and stops the lane, including a flag
  against a dense habitat/superset raster. No density, reciprocity, or
  diagnostic-statistic exception is permitted.

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
SPARSE_SUPPORT_FRACTION = 0.05   # diagnostic classification only; never waives proximity stop


def _decision_value(stats, name, default=float("-inf")):
    """Use unrounded metrics for literal thresholds; rounded fields are display-only."""
    return stats.get(f"_{name}_raw", stats.get(name, default))


def stop_reasons(stats):
    """Return the literal, fail-closed registry stop reasons for one prior."""
    reasons = []
    if _decision_value(stats, "spearman_dots") > SPEARMAN_MAX:
        reasons.append("spearman_dots>0.90")
    if _decision_value(stats, "spearman_surface") > SPEARMAN_MAX:
        reasons.append("spearman_surface>0.90")
    if _decision_value(stats, "containment", default=0.0) > CONTAINMENT_MAX:
        reasons.append("directed_near3px>0.70")
    return reasons


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
    kind = "dense" if n_reg > _SPARSE_MAX else "sparse"
    if n_reg == 0:
        return dict(path=rel, sha256=sha,
                    spearman_dots=round(sp_d, 4), _spearman_dots_raw=sp_d,
                    spearman_surface=round(sp_s, 4), _spearman_surface_raw=sp_s,
                    kind="empty", n_reg=0,
                    containment=0.0, _containment_raw=0.0,
                    rev_containment=0.0, jaccard_3px=0.0,
                    surface_containment=0.0, mass_ratio=0.0)

    # The literal gate applies to every raster's nonzero pixels, even if it is
    # a dense field. Reverse containment/Jaccard are audit-only diagnostics.
    dist = ndimage.distance_transform_edt(~reg)
    inter = int((dist[_MY_DOT_R, _MY_DOT_C] <= KERNEL_PX).sum())
    containment = inter / _N_MY_DOTS if _N_MY_DOTS else 0.0
    reg_r, reg_c = np.nonzero(reg)
    rev = float((_DIST_MINE[reg_r, reg_c] <= KERNEL_PX).mean())
    union = int(_N_MY_DOTS + n_reg - inter)
    jac = inter / union if union else 1.0
    cont_surf = float((dist[_SURF_R, _SURF_C] <= KERNEL_PX).mean()) if _N_SURF else 0.0
    return dict(path=rel, sha256=sha,
                spearman_dots=round(sp_d, 4), _spearman_dots_raw=sp_d,
                spearman_surface=round(sp_s, 4), _spearman_surface_raw=sp_s,
                kind=kind, n_reg=n_reg,
                containment=round(containment, 4), _containment_raw=containment,
                rev_containment=round(rev, 4),
                jaccard_3px=round(jac, 4), surface_containment=round(cont_surf, 4),
                mass_ratio=round(n_reg / _N_MY_DOTS, 1) if _N_MY_DOTS else None)


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
    comparable = [r for r in results if r["kind"] != "empty"]
    worst_sp_dots = max(results, key=lambda r: r["spearman_dots"])
    worst_sp_surf = max(results, key=lambda r: r["spearman_surface"])
    worst_jac = max(sparse, key=lambda r: r["jaccard_3px"]) if sparse else None
    worst_cont = max(comparable, key=lambda r: r["containment"]) if comparable else None
    worst_rev = max(sparse, key=lambda r: r["rev_containment"]) if sparse else None

    literal_flags = [
        r for r in comparable
        if _decision_value(r, "containment", default=0.0) > CONTAINMENT_MAX
    ]
    duplicates = []
    for r in results:
        reasons = stop_reasons(r)
        if reasons:
            duplicates.append(dict(
                path=r["path"], reason=" OR ".join(reasons),
                **{k: r.get(k) for k in (
                    "spearman_dots", "spearman_surface", "containment",
                    "rev_containment", "jaccard_3px", "kind", "n_reg")},
                spearman_dots_raw=r.get("_spearman_dots_raw"),
                spearman_surface_raw=r.get("_spearman_surface_raw"),
                containment_raw=r.get("_containment_raw"),
            ))

    verdict = ("DUPLICATE - STOP" if duplicates else
               "NO STOP TRIGGER in the readable registry; unreadable entries remain a limitation")

    def public_result(row):
        """Keep private unrounded decision fields out of the ranked summaries."""
        return {key: value for key, value in row.items() if not key.startswith("_")}

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
            spearman_dots_raw=worst_sp_dots["_spearman_dots_raw"],
            spearman_dots_path=worst_sp_dots["path"],
            spearman_surface=worst_sp_surf["spearman_surface"],
            spearman_surface_raw=worst_sp_surf["_spearman_surface_raw"],
            spearman_surface_path=worst_sp_surf["path"],
            jaccard_3px=worst_jac["jaccard_3px"] if worst_jac else None,
            jaccard_3px_path=worst_jac["path"] if worst_jac else None,
            containment=worst_cont["containment"] if worst_cont else None,
            containment_raw=(worst_cont["_containment_raw"] if worst_cont else None),
            containment_path=worst_cont["path"] if worst_cont else None,
            rev_containment=worst_rev["rev_containment"] if worst_rev else None,
            rev_containment_path=worst_rev["path"] if worst_rev else None,
        ),
        literal_containment_flags=[
            dict(path=r["path"], containment=r["containment"],
                 containment_raw=r["_containment_raw"],
                 rev_containment=r["rev_containment"], jaccard_3px=r["jaccard_3px"],
                 mass_ratio=r["mass_ratio"], registry_dots=r["n_reg"],
                 note="literal >0.70 directed-proximity trigger: DUPLICATE/STOP; "
                      "density, Jaccard, and reverse-containment diagnostics do not waive it")
            for r in sorted(
                literal_flags,
                key=lambda r: -_decision_value(r, "containment", default=0.0))],
        n_literal_flags=len(literal_flags),
        duplicates=duplicates,
        n_duplicates=len(duplicates),
        top10_by_containment=[
            public_result(r) for r in sorted(
                comparable,
                key=lambda r: -_decision_value(r, "containment", default=0.0),
            )[:10]
        ],
        top10_by_correlation=[
            public_result(r) for r in sorted(
                results,
                key=lambda r: -max(
                    _decision_value(r, "spearman_dots"),
                    _decision_value(r, "spearman_surface"),
                ),
            )[:10]
        ],
        verdict=verdict,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in (
        "n_registry_rasters", "n_unique_pixel_content", "n_sparse_dot_rasters",
        "n_dense_rasters", "n_lane_dots", "worst", "n_literal_flags",
        "n_duplicates", "verdict")}, indent=1))
    return 1 if duplicates else 0


if __name__ == "__main__":
    raise SystemExit(main())
