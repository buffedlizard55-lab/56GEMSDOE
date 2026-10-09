"""Write and validate GEMS Prize submission GeoTIFFs.

Format requirements (official, verified 2026-10-09 from the competition page
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/):
  * projected CRS EPSG:32611 (UTM zone 11N), 100 m resolution
  * same bounds as the training data (reference grid below, verified from the
    GeoDAWN-derived rasters in the sibling repositories; the official training file itself
    could NOT be opened from this sandbox - see docs/irregularities.md)
  * single band, float32, values in [0, 1]; data outside the bounds is null or NaN
  * the validator also rejects nodata sentinels (e.g. -3.4028234663852886e+38), which
    would otherwise appear as out-of-range values to the portal.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, asdict

import numpy as np
import rasterio
from rasterio.transform import Affine

REF_CRS = "EPSG:32611"
REF_WIDTH = 3292
REF_HEIGHT = 3730
REF_TRANSFORM = Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


@dataclass
class ValidationReport:
    path: str
    sha256: str
    bytes: int
    ok: bool
    problems: list
    warnings: list
    crs: str | None
    width: int
    height: int
    transform: list
    count: int
    dtype: str
    nodata: float | None
    n_nan: int
    n_nonfinite: int
    n_outside_01: int
    n_positive: int
    vmin: float | None
    vmax: float | None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_submission(path: str, values: np.ndarray) -> None:
    """Write a float32 single-band GeoTIFF on the reference grid. NaN is never written here."""
    if values.shape != (REF_HEIGHT, REF_WIDTH):
        raise ValueError(f"shape must be {(REF_HEIGHT, REF_WIDTH)}, got {values.shape}")
    arr = np.asarray(values, dtype=np.float32)
    if not np.isfinite(arr).all():
        raise ValueError("refusing to write non-finite values; the reference writer keeps every cell finite")
    if arr.min() < 0.0 or arr.max() > 1.0:
        raise ValueError("values must lie in [0, 1]")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    profile = dict(
        driver="GTiff",
        width=REF_WIDTH,
        height=REF_HEIGHT,
        count=1,
        dtype="float32",
        crs=REF_CRS,
        transform=REF_TRANSFORM,
        nodata=None,
        compress="deflate",
        predictor=3,
        tiled=False,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.set_band_description(1, "fault_probability")


def validate_submission(path: str, reference_nan_mask: np.ndarray | None = None) -> ValidationReport:
    """Re-open the file from disk and check every rule the portal enforces.

    reference_nan_mask: optional boolean array (H, W) of cells that the organizer template
    marks as outside the bounds. If given, NaN must occur exactly there. If None, the file
    must contain no NaN at all (the safe default).
    """
    problems, warnings = [], []
    with rasterio.open(path) as ds:
        crs = ds.crs.to_string() if ds.crs else None
        t = ds.transform
        if ds.count != 1:
            problems.append(f"band count {ds.count} != 1")
        if ds.dtypes[0] != "float32":
            problems.append(f"dtype {ds.dtypes[0]} != float32")
        if crs != REF_CRS:
            problems.append(f"CRS {crs} != {REF_CRS}")
        if (ds.width, ds.height) != (REF_WIDTH, REF_HEIGHT):
            problems.append(f"shape {(ds.height, ds.width)} != {(REF_HEIGHT, REF_WIDTH)}")
        if not all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(tuple(t)[:6], tuple(REF_TRANSFORM)[:6])):
            problems.append(f"transform {tuple(t)[:6]} != reference {tuple(REF_TRANSFORM)[:6]}")
        nodata = ds.nodata
        if nodata is not None and not (math.isnan(nodata) or 0.0 <= nodata <= 1.0):
            problems.append(f"nodata sentinel {nodata} lies outside [0, 1]")
        a = ds.read(1).astype(np.float64)

    nan = np.isnan(a)
    n_nan = int(nan.sum())
    finite = np.isfinite(a)
    n_nonfinite = int((~finite & ~nan).sum())
    if n_nonfinite:
        problems.append(f"{n_nonfinite} infinite cells")
    if reference_nan_mask is not None:
        if reference_nan_mask.shape != a.shape:
            problems.append("reference NaN mask has the wrong shape")
        elif not np.array_equal(nan, reference_nan_mask):
            problems.append("NaN cells do not match the organizer footprint")
    elif n_nan:
        problems.append(f"{n_nan} NaN cells but no reference footprint was supplied (write all-finite files)")
    vals = a[finite]
    n_outside = int(((vals < 0.0) | (vals > 1.0)).sum())
    if n_outside:
        problems.append(f"{n_outside} finite values outside [0, 1]")
    if vals.size == 0:
        problems.append("no finite values")
    n_pos = int((vals > 0).sum())
    if n_pos == 0:
        warnings.append("all values are zero: this file predicts no faults and will score 0")

    rep = ValidationReport(
        path=path,
        sha256=sha256_file(path),
        bytes=os.path.getsize(path),
        ok=not problems,
        problems=problems,
        warnings=warnings,
        crs=crs,
        width=REF_WIDTH,
        height=REF_HEIGHT,
        transform=[float(x) for x in tuple(t)[:6]],
        count=1,
        dtype="float32",
        nodata=None if nodata is None else float(nodata),
        n_nan=n_nan,
        n_nonfinite=n_nonfinite,
        n_outside_01=n_outside,
        n_positive=n_pos,
        vmin=float(vals.min()) if vals.size else None,
        vmax=float(vals.max()) if vals.size else None,
    )
    return rep


def write_receipt(report: ValidationReport, out_json: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(asdict(report), f, indent=2)
