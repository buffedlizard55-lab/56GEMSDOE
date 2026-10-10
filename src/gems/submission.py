"""Legacy local writer/validator for the DOE GEMS Prize format.

The public format page (https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
requires EPSG:32611, 100 m, matching bounds, one float32 band, values in [0, 1], and null/NaN
outside the data bounds.  The reference affine below is measured from the pinned bridge copies
in this checkout, not independently authenticated by the organizer.  The sample file in that
mirror contains catalogue values despite the public page describing a total-fault-absence sample;
use only its finite mask as a locally tested footprint and see IR-56-001.  Passing this helper
is a local format check, not proof of uniqueness or organizer acceptance.
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


def write_submission(path: str, values: np.ndarray,
                     reference_valid_mask: np.ndarray | None = None) -> None:
    """Write a float32 GeoTIFF; require the caller to supply an exact mask if using NaN.

    Without a reference mask this legacy helper accepts only all-finite arrays and does
    not claim template conformance.  With one, values must already be finite inside and
    NaN outside; it never repairs, clips, or fills candidate values silently.
    """
    raw = np.asarray(values)
    if raw.shape != (REF_HEIGHT, REF_WIDTH):
        raise ValueError(f"shape must be {(REF_HEIGHT, REF_WIDTH)}, got {raw.shape}")
    if np.isinf(raw).any():
        raise ValueError("submission must not contain infinity")
    finite = np.isfinite(raw)
    if finite.any() and ((raw[finite] < 0.0).any() or (raw[finite] > 1.0).any()):
        raise ValueError("finite values must lie strictly in [0, 1]")
    if reference_valid_mask is None:
        if not finite.all():
            raise ValueError("non-finite values require the organizer template valid mask")
        nodata = None
    else:
        reference_valid_mask = np.asarray(reference_valid_mask, dtype=bool)
        if reference_valid_mask.shape != raw.shape or not reference_valid_mask.any():
            raise ValueError("reference_valid_mask must be nonempty and match the reference grid")
        if not finite[reference_valid_mask].all() or not np.isnan(raw[~reference_valid_mask]).all():
            raise ValueError("finite/NaN mask does not match reference_valid_mask")
        nodata = float("nan")
    arr = raw.astype(np.float32, copy=False)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    profile = dict(
        driver="GTiff",
        width=REF_WIDTH,
        height=REF_HEIGHT,
        count=1,
        dtype="float32",
        crs=REF_CRS,
        transform=REF_TRANSFORM,
        nodata=nodata,
        compress="deflate",
        predictor=3,
        tiled=False,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.set_band_description(1, "fault_probability")


def validate_submission(path: str, reference_nan_mask: np.ndarray | None = None,
                         reference_nodata: float | None = None) -> ValidationReport:
    """Re-open the file and perform a local format check against the pinned grid.

    ``reference_nan_mask`` is a boolean mask of pixels outside the sample's valid area.
    When supplied, NaN must occur exactly there and the nodata tag must match
    ``reference_nodata`` (NaN by default).  Without a template mask, only all-finite
    predictions can be assessed.  Passing this local validator is not organizer acceptance.
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
        reference_nan_mask = np.asarray(reference_nan_mask, dtype=bool)
        if reference_nan_mask.shape != a.shape:
            problems.append("reference NaN mask has the wrong shape")
        elif not np.array_equal(nan, reference_nan_mask):
            problems.append("NaN cells do not match the supplied template footprint")
        expected_nodata = float("nan") if reference_nodata is None else reference_nodata
        nodata_matches = (
            nodata is not None and np.isnan(nodata) and np.isnan(expected_nodata)
            if isinstance(nodata, (float, np.floating))
            else nodata == expected_nodata
        )
        if not nodata_matches:
            problems.append(f"nodata tag {nodata!r} does not match template {expected_nodata!r}")
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
