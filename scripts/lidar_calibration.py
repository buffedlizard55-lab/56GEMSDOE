#!/usr/bin/env python3
"""E1c -- the LiDAR calibration the corrections brief asks for: same detector, 3 m versus 100 m.

The 100 m grid cannot say where inside a cell a scarp crest sits, so a measured offset of 0.6 px
could mean either "the catalogue is on the line" or "the coarse grid cannot see". This settles it on
real high-resolution data: the two cached USGS 3DEP 1 m tiles (block-averaged to 3 m by GEMSDOE48's
pilot, receipt ``data/pilot/dem3m/dem_pilot_receipt.json``) that overlap the study area, containing
every catalogue pixel under their footprints.

Reported: (i) the offset distribution measured at 3 m, (ii) per-segment 3 m medians with a robust SE
-- the lane's actual unit of claim, (iii) the coarse-vs-fine agreement, which is the *precision* of
the 100 m estimator and therefore the floor on any corridor-level z test.

Reproduce: python scripts/lidar_calibration.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C, lane_inputs as L   # noqa: E402

TILES = {"x42y425": "/home/user/_lidar/x42y425_3m.tif", "x40y427": "/home/user/_lidar/x40y427_3m.tif"}
SRC_CRS = "EPSG:26911"      # NAD83 / UTM 11N, read from each tile's own CRS
DST_CRS = "EPSG:32611"      # WGS84 / UTM 11N, the competition grid
RES = 3.0
WEST0, NORTH0 = 243350.0, 4508550.0
EDGE = np.arange(-4.0, 4.0001, 0.5)


def summarise_cells(x_m, edges=EDGE):
    """Histogram of an offset expressed in metres, binned in 100 m cells."""
    x = np.asarray(x_m, float) / 100.0
    x = x[np.isfinite(x)]
    if x.size == 0:
        return dict(n=0)
    h, _ = np.histogram(x, bins=edges)
    return dict(n=int(x.size), counts=[int(v) for v in h], edges=[float(v) for v in edges],
                median_cells=float(np.median(x)), mean_cells=float(x.mean()),
                mad_cells=float(np.median(np.abs(x - np.median(x)))),
                p05_cells=float(np.percentile(x, 5)), p95_cells=float(np.percentile(x, 95)),
                frac_abs_ge_1px=float((np.abs(x) >= 1).mean()),
                frac_abs_ge_2px=float((np.abs(x) >= 2).mean()),
                frac_abs_ge_3px=float((np.abs(x) >= 3).mean()))


def load_tile(path):
    """Reproject one cached 3 m tile onto the competition grid's 3 m lattice, in EPSG:32611."""
    with rasterio.open(path) as ds:
        raw = ds.read(1)
        dtype, src_tf, src_crs, nodata = ds.dtypes[0], ds.transform, ds.crs, ds.nodata
        s_bounds = [ds.bounds.left, ds.bounds.bottom, ds.bounds.right, ds.bounds.top]
    src = raw.astype(np.float32)
    src[~np.isfinite(src)] = np.nan
    if dtype == "int16":
        # decoded from the file's own tag ENCODING='z_m = 1000 + value/10'; nodata -32768
        src = np.where(src <= -32767, np.nan, 1000.0 + src / 10.0).astype(np.float32)
    src[~np.isfinite(src)] = np.nan
    lo, hi = float(np.nanmin(src)), float(np.nanmax(src))
    if not (0.0 < lo < hi < 6000.0):
        raise RuntimeError(f"{path}: unexpected elevation range {lo}..{hi} after decoding ({dtype})")
    tr = Transformer.from_crs(src_crs or CRS.from_user_input(SRC_CRS), DST_CRS, always_xy=True)
    xt, yt = tr.transform([s_bounds[0], s_bounds[2]], [s_bounds[1], s_bounds[3]])
    x0, x1, y0, y1 = min(xt), max(xt), min(yt), max(yt)
    c0 = int(np.floor((x0 - WEST0) / RES))
    c1 = int(np.ceil((x1 - WEST0) / RES))
    r0 = int(np.floor((NORTH0 - y1) / RES))
    r1 = int(np.ceil((NORTH0 - y0) / RES))
    # row index grows southward: the north edge of lattice row r0 is NORTH0 - r0*RES. A sign slip
    # here produced an all-NaN destination grid; the valid-fraction guard below catches it.
    dst_tf = from_origin(WEST0 + c0 * RES, NORTH0 - r0 * RES, RES, RES)
    dst = np.full((r1 - r0, c1 - c0), np.nan, np.float32)
    reproject(src, dst, src_transform=src_tf, src_crs=src_crs or CRS.from_user_input(SRC_CRS),
              dst_transform=dst_tf, dst_crs=CRS.from_user_input(DST_CRS),
              resampling=Resampling.bilinear, init_dest_nodata=True,
              src_nodata=None if src.dtype.kind == "f" else nodata)
    vf = float(np.isfinite(dst).mean())
    if vf < 0.9:
        raise RuntimeError(f"{path}: reprojected grid only {vf:.2f} valid -- lattice alignment is wrong")
    return dict(z=dst, tf=dst_tf, shape=dst.shape, src_dtype=dtype, valid_fraction=vf,
                z_range=[lo, hi], src_crs=str(src_crs),
                footprint_rows=[r0, r1], footprint_cols=[c0, c1])


def crest_at_3m(z3, tf, row, col, ty, tx, half_m=400.0, step_m=6.0, smooth_m=30.0):
    """Nearest convex crest of the 3 m DEM along the normal through each catalogue pixel centre."""
    wx = WEST0 + (col + 0.5) * 100.0
    wy = NORTH0 - (row + 0.5) * 100.0
    fx = (wx - tf.c) / tf.a
    fy = (wy - tf.f) / tf.e
    offs = np.arange(-half_m, half_m + 1e-6, step_m)
    ny, nx = -tx, ty                       # normal to strike, in (north, east) metres
    yy = fy[:, None] - (offs[None, :] / RES) * ny[:, None]      # row grows south
    xx = fx[:, None] + (offs[None, :] / RES) * nx[:, None]
    H, W = z3.shape
    inside = (xx >= 0) & (xx < W - 1) & (yy >= 0) & (yy < H - 1)
    yc = np.clip(yy, 0, H - 1)
    xc = np.clip(xx, 0, W - 1)
    z = ndimage.map_coordinates(np.nan_to_num(z3, nan=0.0), np.stack([yc.ravel(), xc.ravel()]),
                                order=1, mode="nearest").reshape(yy.shape)
    ok = inside & np.isfinite(z3[np.rint(yc).astype(int), np.rint(xc).astype(int)])
    z = np.where(ok, z, np.nan)
    curv = C._convexity(z, step_m)
    off_px, hgt, prom, ncand = C.find_crest(curv, offs / RES, smooth=smooth_m / RES,
                                            min_prom=C.MIN_PROM_FRAC)
    # s was passed in 3 m lattice pixels, so metres = lattice index * RES (not * step_m)
    return dict(off_m=off_px * RES, hgt=hgt, prom=prom,
                valid=ok.sum(axis=1) >= (offs.size - 2), n=offs.size)


def main():
    t0 = time.time()
    fields, cat, fp, meta = L.load()
    out = {"evidence_class": "MEASURED on 3 m USGS 1 m-LiDAR tiles; calibration and descriptive "
                             "statistics, not a score",
           "caveats": [
               "Datum: NAD83 (EPSG:26911, the cached tiles' own CRS) to WGS84 (EPSG:32611) via pyproj's "
               "default transform. In Nevada the unmodelled residual is of order 1 m, i.e. ~1 % of one "
               "competition cell and ~0.5 % of the 200 m gate. Logged, not load-bearing.",
               "Strike is inherited from the 100 m catalogue geometry; only the crest position is refined "
               "at 3 m. A 3 m strike estimated from a 100 m rasterisation would be meaningless.",
               "Two tiles (10 km x 10 km each), not the whole survey: the donor lane merged 700 tiles to "
               "the 100 m grid, but only this 3 m pilot pair is cached, so the sub-cell calibration is "
               "local and its sign must not be extrapolated region-wide.",
               "The tiles are an owner-mirrored product of a sibling lane, fetched through the GitHub blob "
               "API on 2026-10-09 and hash-consistent with that repo's receipt; not organizer files.",
           ]}
    row, col = np.nonzero(cat)
    ty, tx, okk, cnt = C.strike_at(cat, row, col)

    # coarse reference, ungated and gated at the null-calibrated strength floor
    null = C.control_points(fields, cat, fp, mode="random", n=20000, seed=5601)
    hd = float(np.nanpercentile(null["dem_hgt"][null["valid"]], 90))
    hm = float(np.nanpercentile(null["mag_hgt"][null["valid"]], 90))
    rec0 = C.measure(fields, cat, fp)
    recg = C.measure(fields, cat, fp, min_hgt=(hd, hm, 0.0))
    out["strength_gate"] = dict(dem_min_hgt=hd, mag_min_hgt=hm, n_null=int(null["valid"].sum()),
                                rule="crest believed only when its peak-to-trough height exceeds the "
                                     "90th percentile of the same statistic at random traceless points")
    out["coarse_100m"] = dict(
        ungated_dem_cells=summarise_cells(rec0["dem_off_px"][rec0["valid"]] * 100.0),
        gated_dem_cells=summarise_cells(recg["dem_off_px"][recg["valid"]] * 100.0),
        gated_mag_cells=summarise_cells(recg["mag_off_px"][recg["valid"]] * 100.0),
        ungated_mag_cells=summarise_cells(rec0["mag_off_px"][rec0["valid"]] * 100.0))

    def dense(rec, key):
        """Scatter a per-transect array back onto the grid, so any pixel subset can be looked up.

        measure() drops pixels whose neighbourhood has no usable strike, so its arrays are shorter
        than the catalogue pixel list; indexing them with a boolean over the full list is an
        off-by-silence bug waiting to happen.
        """
        d = np.full(cat.shape, np.nan, np.float32)
        d[rec["row"], rec["col"]] = np.asarray(rec[key], np.float32)
        return d

    d0_grid, mg_grid = dense(rec0, "dem_off_px"), dense(rec0, "mag_off_px")
    dg_grid = dense(recg, "dem_off_px")
    lab, nl = ndimage.label(cat, structure=np.ones((3, 3), bool))
    all_pairs, segs, n_pix = [], [], 0
    per_tile = {}
    for name, p in TILES.items():
        if not Path(p).exists():
            out.setdefault("missing_tiles", []).append(name)
            continue
        T = load_tile(p)
        fx = (WEST0 + (col + 0.5) * 100.0 - T["tf"].c) / T["tf"].a
        fy = (NORTH0 - (row + 0.5) * 100.0 - T["tf"].f) / T["tf"].e
        sel = (fx > 4) & (fx < T["z"].shape[1] - 5) & (fy > 4) & (fy < T["z"].shape[0] - 5)
        pr = crest_at_3m(T["z"], T["tf"], row[sel], col[sel], ty[sel], tx[sel])
        r_s, c_s = row[sel], col[sel]
        d0 = d0_grid[r_s, c_s] * 100.0
        mg = mg_grid[r_s, c_s] * 100.0
        dg = dg_grid[r_s, c_s] * 100.0
        good = pr["valid"] & np.isfinite(pr["off_m"])
        strong = good & (pr["hgt"] >= np.nanpercentile(pr["hgt"][good], 75)) if good.any() else good
        comp = lab[r_s, c_s]
        dg = dg[good] if False else dg
        tile_segs = []
        for kk in np.unique(comp[good]):
            if kk == 0:
                continue
            sm = good & (comp == kk)
            if sm.sum() >= 8:
                v = pr["off_m"][sm]
                med, mad = float(np.nanmedian(v)), float(np.nanmedian(np.abs(v - np.nanmedian(v))))
                tile_segs.append(dict(comp=int(kk), n=int(sm.sum()), median_m=med,
                                      mad_m=mad,
                                      se_m=float(1.2533 * (mad / 0.6745) / np.sqrt(max(sm.sum(), 1))),
                                      coarse_median_m=float(np.nanmedian(d0[sm])),
                                      frac_ge_200m=float((np.abs(v) >= 200.0).mean())))
        tile_segs.sort(key=lambda r: -abs(r["median_m"]))
        per_tile[name] = dict(
            tile_shape=list(T["shape"]), src_crs=T["src_crs"], src_dtype=T["src_dtype"],
            elevation_range_m=[round(v, 1) for v in T["z_range"]], valid_fraction=round(T["valid_fraction"], 4),
            catalogue_pixels=int(sel.sum()), with_3m_crest=int(good.sum()), with_top_quartile_crest=int(strong.sum()),
            offset_3m_cells=summarise_cells(pr["off_m"][good]),
            offset_3m_strong_cells=summarise_cells(pr["off_m"][strong]),
            offset_3m_m=dict(median=float(np.nanmedian(pr["off_m"][good])),
                             mad=float(np.nanmedian(np.abs(pr["off_m"][good] - np.nanmedian(pr["off_m"][good])))),
                             frac_ge_100m=float((np.abs(pr["off_m"][good]) >= 100).mean()),
                             frac_ge_200m=float((np.abs(pr["off_m"][good]) >= 200).mean()),
                             frac_ge_300m=float((np.abs(pr["off_m"][good]) >= 300).mean()),
                             max_abs=float(np.nanmax(np.abs(pr["off_m"][good])))),
            segments=len(tile_segs), largest_abs_segment_median=tile_segs[:5],
            coarse_vs_fine=dict(
                n=int((good & np.isfinite(d0)).sum()),
                bias_m=float(np.nanmean(d0[good] - pr["off_m"][good])),
                rms_m=float(np.sqrt(np.nanmean((d0[good] - pr["off_m"][good]) ** 2))),
                median_abs_diff_m=float(np.nanmedian(np.abs(d0[good] - pr["off_m"][good]))),
                r=float(np.corrcoef(d0[good], pr["off_m"][good])[0, 1]) if (good & np.isfinite(d0)).sum() > 3 else None,
                mag_vs_dem3m_r=float(np.corrcoef(mg[good], pr["off_m"][good])[0, 1]) if (good & np.isfinite(mg)).sum() > 3 else None))
        keep = good & np.isfinite(d0)
        all_pairs.append(np.stack([d0[keep], pr["off_m"][keep], mg[keep]], 1))
        segs += tile_segs
        n_pix += int(sel.sum())
        print(f"  {name}: {int(sel.sum())} catalogue px, {int(good.sum())} with a 3 m crest", flush=True)
    out["tiles"] = per_tile
    out["coverage"] = dict(catalogue_pixels_under_cached_tiles=n_pix,
                           fraction_of_catalogue=float(n_pix / max(1, int(cat.sum()))))
    if all_pairs:
        A = np.concatenate(all_pairs, 0)
        A = A[np.isfinite(A[:, :2]).all(1)]
        dif = A[:, 0] - A[:, 1]
        out["pooled"] = dict(
            n=int(A.shape[0]), offset_3m_cells=summarise_cells(A[:, 1]),
            coarse_minus_fine=dict(bias_m=float(np.mean(dif)), rms_m=float(np.sqrt(np.mean(dif ** 2))),
                                   p05_m=float(np.percentile(dif, 5)), p95_m=float(np.percentile(dif, 95)),
                                   r=float(np.corrcoef(A[:, 0], A[:, 1])[0, 1])),
            estimator_precision_m=float(np.sqrt(np.mean(dif ** 2))))
        segs = sorted(segs, key=lambda r: -abs(r["median_m"]))
        z = np.array([abs(r["median_m"]) / max(r["se_m"], out["pooled"]["estimator_precision_m"] / np.sqrt(r["n"]))
                      for r in segs]) if segs else np.array([])
        out["segments_3m"] = dict(
            n=len(segs),
            median_abs_segment_median_m=float(np.median([abs(r["median_m"]) for r in segs])) if segs else None,
            segments_with_abs_median_ge_200m=int(sum(abs(r["median_m"]) >= 200 for r in segs)),
            max_z=float(z.max()) if z.size else None,
            segments_with_z_ge_3=int((z >= 3).sum()) if z.size else 0,
            top=segs[:10])
    out["elapsed_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "lidar_calibration_v1.json").write_text(json.dumps(out, indent=1, default=float))
    k = ["strength_gate", "coverage", "pooled", "segments_3m", "elapsed_s"]
    print(json.dumps({x: out.get(x) for x in k}, indent=1, default=float)[:3500])
    print(json.dumps({n: {kk: vv for kk, vv in t.items() if kk != "segments"} for n, t in per_tile.items()},
                     indent=1, default=float)[:2500])


if __name__ == "__main__":
    main()
