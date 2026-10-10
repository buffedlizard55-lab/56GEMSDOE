#!/usr/bin/env python3
"""E1a — turn the official 19-band stack into label-free candidate *fields*, one per physical channel.

Every field is stored as a uint16 percentile-rank raster (0 = lowest fault-likeness in the footprint,
65535 = highest) plus a JSON inventory recording the exact recipe and the source band. Percentile
rank, not z-score, is stored so that combining channels is order-preserving and unit-free; the rank
is a monotone map of the raw value, so a top-K selection on a rank raster is a top-K selection on the
raw field (ties broken by flat index, deterministic).

Nothing here reads a label. The catalogue enters only as (i) the mask of cells that are *excluded*
from emission (the organiser's pixel-exact known-fault mask, plus its 2 px shadow, which is a rule
about where a submission may put mass, not a label), and (ii) the object of the mimicry statistic
reported for the leakage canary.

Reproduce: python scripts/build_fields.py            (~3 min, 2 cores, <2 GB peak)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C  # noqa: E402  (vendored loader: sentinel handling, band asserts)
from gems56 import grid as G  # noqa: E402

OUT = ROOT / "data" / "interim" / "fields"
BANDS = ["mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc", "geod_shearrate",
         "geod_dilaterate", "tmi_vg", "deq_n100a15", "iso_grav_anom_vg", "det_elev", "iso_grav_anom",
         "tmi", "depth_to_base_surf", "ieq_n100a15", "cond_surf", "iso_grav_anom_hg", "det_elev_slope"]
SIGMA_EDGE = 0.8      # px: 80 m smoothing before an edge filter, ~one airborne flight line
SIGMA_SMOOTH = 1.2    # px: 120 m smoothing of a magnitude field


def bands(path: Path) -> dict:
    """``{band_name: float32 grid}`` with NaN where the official sentinel or a hole sits."""
    out = {}
    import rasterio
    with rasterio.open(str(path)) as src:
        desc = {i: (src.descriptions[i - 1] or "").split(" ")[0] for i in range(1, src.count + 1)}
        assert sorted(desc.values()) == sorted(BANDS), f"unexpected band inventory: {sorted(desc.values())}"
        for i, name in desc.items():
            a = src.read(i).astype(np.float32)
            a[(~np.isfinite(a)) | (a < C.NODATA_LIMIT)] = np.nan
            out[name] = a
            del a
    return out


def ridge(a: np.ndarray, sigma: float = SIGMA_EDGE) -> np.ndarray:
    """Second derivative along the gradient direction, normalised -- the Meijster ridge response of a
    signed field, positive on ridges of the input. Separable 1-D passes keep this float32 and cheap on
    the 12.3 M-cell grid; a hole in the source is not a ridge, so NaN is scored as zero response."""
    s = ndimage.gaussian_filter(np.nan_to_num(a, nan=0.0).astype(np.float32), sigma, mode="nearest")
    k1 = np.array([-0.5, 0.0, 0.5], np.float32)
    k2 = np.array([1.0, -2.0, 1.0], np.float32)
    sx = ndimage.convolve1d(s, k1, axis=1, mode="nearest")
    sy = ndimage.convolve1d(s, k1, axis=0, mode="nearest")
    sxx = ndimage.convolve1d(s, k2, axis=1, mode="nearest")
    syy = ndimage.convolve1d(s, k2, axis=0, mode="nearest")
    sxy = ndimage.convolve1d(ndimage.convolve1d(s, k1, axis=0, mode="nearest"), k1, axis=1, mode="nearest")
    den = sx * sx + sy * sy + 1e-12
    r = -(sxx * sx * sx + 2 * sxy * sx * sy + syy * sy * sy) / (den * np.sqrt(den + 1e-12))
    return np.maximum(r, 0.0).astype(np.float32)


def mag(a: np.ndarray, sigma: float = SIGMA_SMOOTH) -> np.ndarray:
    """Smoothed magnitude of a gradient-like band (its own absolute value is the signal)."""
    s = np.abs(np.nan_to_num(a, nan=0.0))
    return ndimage.gaussian_filter(s.astype(np.float32), sigma, mode="nearest").astype(np.float32)


def edge(a: np.ndarray, sigma: float = SIGMA_EDGE) -> np.ndarray:
    """|grad| of a field, i.e. a contact/step detector that is indifferent to which side is up."""
    f = np.nan_to_num(a, nan=0.0)
    g = np.hypot(*np.gradient(f.astype(np.float32)))
    return ndimage.gaussian_filter(g, sigma, mode="nearest").astype(np.float32)


def signed_abs(a: np.ndarray, sigma: float = SIGMA_SMOOTH) -> np.ndarray:
    return mag(np.abs(np.nan_to_num(a, nan=0.0)), sigma)


def as_rank(v: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile rank inside the footprint, uint16. Ties keep their flat-index order (stable sort)."""
    out = np.zeros(v.size, np.uint16)
    idx = np.flatnonzero(valid.ravel())
    x = v.ravel()[idx]
    order = np.argsort(x, kind="stable")
    rank = np.empty(x.size, np.float64)
    rank[order] = np.arange(x.size, dtype=np.float64)
    out[idx] = np.clip(rank / max(1, x.size - 1) * 65535.0, 0, 65535).astype(np.uint16)
    return out.reshape(v.shape)


RECIPES = {
    # ---- channels the group has already mined hard (the "scarp family"), as controls ----
    "scarp_convex":   ("crest of -d2(det_elev)/dn2: the DEM curvature scarps every prior lane emits on",
                       lambda b: np.maximum(-ndimage.laplace(np.nan_to_num(b["det_elev"], nan=0.0)), 0.0)),
    "scarp_slope":    ("convex break from the slope band: |grad det_elev| ridge",
                       lambda b: ridge(b["det_elev_slope"])),
    "mag_ridge":      ("ridge of the smoothed |tmi_hg| magnetic gradient",
                       lambda b: ridge(mag(b["tmi_hg"]))),
    "mag_grad":       ("smoothed |tmi_hg| itself (no thinning)",
                       lambda b: mag(b["tmi_hg"])),
    # ---- the contrarian channels: measured deformation, cover-blind, post-dating the mapping ----
    "strain_2ndinv":  ("smoothed second invariant of the geodetic strain-rate tensor (band 4): "
                       "present-day total deformation rate, sign-free",
                       lambda b: signed_abs(b["geod_2ndinv"])),
    "strain_2ndinv_ridge": ("Hessian ridge of geod_2ndinv: a *narrow* zone of concentrated strain",
                       lambda b: ridge(np.abs(b["geod_2ndinv"]))),
    "strain_shear":   ("smoothed |geodetic shear rate| (band 7): the fault-parallel component",
                       lambda b: signed_abs(b["geod_shearrate"])),
    "strain_dilat":   ("smoothed |geodetic dilatation rate| (band 8): volumetric strain, opens basins",
                       lambda b: signed_abs(b["geod_dilaterate"])),
    "strain_all":     ("rank-mean of the three geodetic channels: the deformation-gradient consensus",
                       lambda b: None),  # composed after the per-band pass
    "cover_depth_edge": ("|grad depth_to_base_surf| (band 15): the sediment/basement boundary a "
                         "range-front or concealed-basin fault must step",
                       lambda b: edge(b["depth_to_base_surf"])),
    "cond_edge":      ("|grad cond_surf| (band 17): conductivity front = clay/saline-fluid cap edge",
                       lambda b: edge(b["cond_surf"])),
    "cond_high":      ("smoothed cond_surf itself: conductive (altered, fluid-rich) ground",
                       lambda b: signed_abs(b["cond_surf"])),
    "grav_ridge":     ("ridge of smoothed |iso_grav_anom_hg| (band 18): density step under the cover",
                       lambda b: ridge(mag(b["iso_grav_anom_hg"]))),
    "seis_near":      ("inverse distance to the nearest earthquake (band 10, directional 15 deg bin): "
                       "seismicity proximity, the map-independent activity proxy",
                       lambda b: signed_abs(1.0 / (1.0 + np.abs(np.nan_to_num(b["deq_n100a15"], nan=1e6))))),
    "seis_density":   ("earthquake density (band 16): clustered microseismicity",
                       lambda b: signed_abs(b["ieq_n100a15"])),
    "tilt_edge":      ("|grad tc| tilt/total-curvature of the magnetic field (band 6): source-edge contrast",
                       lambda b: edge(b["tc"])),
    "rtp_ridge":      ("ridge of reduced-to-pole anomaly (band 2): offset of the magnetised units",
                       lambda b: ridge(np.abs(b["rtp"]))),
}
COMPOSE = {"strain_all": ["strain_2ndinv", "strain_shear", "strain_dilat"]}


def main() -> int:
    pins = json.loads((ROOT / "registry" / "input_pins.json").read_text())["files"]
    feats = ROOT / pins["features"]["path"]
    cat = np.zeros(G.SHAPE, bool)
    import rasterio
    with rasterio.open(ROOT / pins["catalogue"]["path"]) as ds:
        cat = ds.read(1) == 1
    with rasterio.open(feats) as ds:
        ok = None
        for i in range(1, ds.count + 1):
            a = ds.read(i)
            k = np.isfinite(a) & (a > C.NODATA_LIMIT)
            ok = k if ok is None else (ok & k)
            del a
    fp = np.isfinite(rasterio.open(ROOT / pins["sample"]["path"]).read(1)) & ok
    del ok
    OUT.mkdir(parents=True, exist_ok=True)
    inv = {"generated_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "footprint_cells": int(fp.sum()), "catalogue_cells": int((cat & fp).sum()),
           "fields": {}}
    b = bands(feats)
    # 2 px catalogue shadow: the organiser masks known faults pixel-exactly, so mass within 1-2 px of
    # a mapped trace can only be scored by a NEW fault pixel; the 0.2778 file (verified in this repo)
    # deleted exactly that mass. The shadow is a rule about emission, recorded here so every arm uses
    # one definition.
    shadow = ndimage.binary_dilation(cat, iterations=2) & fp
    np.save(OUT / "_footprint.npy", fp)
    np.save(OUT / "_shadow.npy", shadow)
    np.save(OUT / "_cat.npy", cat)
    for name, (doc, fn) in RECIPES.items():
        if name in COMPOSE:
            continue
        v = fn(b)
        r = as_rank(np.where(fp, v, -np.inf), fp)
        np.save(OUT / f"{name}.npy", r)
        inv["fields"][name] = dict(description=doc, vmin=float(np.nanmin(v[fp])), vmax=float(np.nanmax(v[fp])))
        del v, r
        print(f"{name}: done", flush=True)
    parts = [np.load(OUT / f"{n}.npy", mmap_mode="r") for n in COMPOSE["strain_all"]]
    comp = np.mean(np.stack([p.astype(np.float32) for p in parts]), axis=0)
    np.save(OUT / "strain_all.npy", as_rank(np.where(fp, comp, -np.inf), fp))
    del comp
    (OUT / "inventory.json").write_text(json.dumps(inv, indent=1))
    print(json.dumps({k: v["description"][:60] for k, v in inv["fields"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
