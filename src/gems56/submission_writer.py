"""Shared fail-closed GeoTIFF packaging, delegates to the grid writer and format gate."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio

from . import gates, grid


def write_submission(path, prediction, sample, footprint, *, note, name, metadata=None):
    """Write the predictions with the sample's exact valid-data mask and record a receipt.

    ``footprint`` is the model's eligible-prediction mask.  It may be a strict subset of
    the official sample footprint when one or more feature bands are missing.  Those
    excluded cells remain finite zeros inside the sample footprint; only cells outside
    the sample's valid region are NaN.  Positive mass outside ``footprint`` is rejected.
    """
    if not name or len(name) > 140 or not note or len(note) > 140:
        raise ValueError("name and note must each have 1..140 characters")
    p = np.asarray(prediction)
    if p.ndim != 2 or p.dtype != np.float32:
        raise ValueError("prediction must be a 2-D float32 array")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("prediction must already be normalized, finite and in [0,1]; no silent repair")
    if not np.any(p > 0):
        raise ValueError("prediction is empty; emit nothing rather than package a blank submission")

    fp = np.asarray(footprint, bool)
    if fp.shape != p.shape or np.any((p > 0) & ~fp):
        raise ValueError("invalid footprint or positive mass outside the eligible footprint")
    sample = Path(sample)
    with rasterio.open(sample) as ref:
        if ref.count != 1:
            raise ValueError(f"sample template must be single-band, got {ref.count} bands")
        template = ref.read(1)
    if template.shape != p.shape:
        raise ValueError(f"prediction {p.shape} does not match sample template {template.shape}")
    sample_valid = np.isfinite(template)
    if np.any(fp & ~sample_valid):
        raise ValueError("eligible footprint includes cells outside the sample template")

    # Preserve every prediction inside the organizer's footprint, and encode only the
    # outside-of-footprint cells as NaN.  A feature-only gap is not the same as outside bounds.
    output = p.copy()
    output[~sample_valid] = np.nan
    path = Path(path)
    grid.write_geotiff(path, output, nodata=float("nan"), valid_mask=sample_valid)
    report = gates.format_report(path, sample, footprint=fp)
    if not report["ok"]:
        raise ValueError(f"on-disk validator rejected output: {report['problems']}")

    # A submission ZIP contains ONLY the one TIFF; notes/evidence are adjacent downloads.
    zip_path = path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(path.name, date_time=(2026, 10, 8, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != [path.name] or archive.read(path.name) != path.read_bytes():
            raise IOError("single-TIFF ZIP roundtrip failed")

    receipt = dict(
        file=path.name,
        sha256=report["sha256"],
        bytes=path.stat().st_size,
        submission_name=name,
        note=note,
        note_chars=len(note),
        validator=report,
        zip_file=zip_path.name,
        zip_sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        approved_for_weekly_slot=False,
        promoted=False,
        submission_slots_used=0,
        status="research-only; local format validation is not organizer acceptance",
        metadata=metadata or {},
    )
    path.with_suffix(".json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    return receipt
