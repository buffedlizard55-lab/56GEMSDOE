"""Shared fail-closed GeoTIFF packaging, delegates to the existing grid writer/gate."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
from . import gates, grid


def write_submission(path, prediction, sample, footprint, *, note, name, metadata=None):
    if not name or len(name) > 140 or not note or len(note) > 140:
        raise ValueError('name and note must each have 1..140 characters')
    p = np.asarray(prediction)
    if p.ndim != 2 or not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError('prediction must already be normalized, finite and in [0,1]; no silent repair')
    fp = np.asarray(footprint, bool)
    if fp.shape != p.shape or np.any((p > 0) & ~fp):
        raise ValueError('invalid footprint or positive mass outside footprint')
    path = Path(path)
    grid.write_geotiff(path, p.astype(np.float32), nodata=None)
    report = gates.format_report(path, sample, footprint=fp)
    if not report['ok']:
        raise ValueError(f'on-disk validator rejected output: {report["problems"]}')
    # A submission ZIP contains ONLY the one TIFF; notes/evidence are adjacent downloads.
    zp = path.with_suffix('.zip')
    with zipfile.ZipFile(zp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(path.name, date_time=(2026, 10, 8, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, path.read_bytes())
    with zipfile.ZipFile(zp) as z:
        if z.namelist() != [path.name] or z.read(path.name) != path.read_bytes():
            raise IOError('single-TIFF ZIP roundtrip failed')
    receipt = dict(file=path.name, sha256=report['sha256'], bytes=path.stat().st_size,
        submission_name=name, note=note, note_chars=len(note), validator=report,
        zip_file=zp.name, zip_sha256=hashlib.sha256(zp.read_bytes()).hexdigest(),
        approved_for_weekly_slot=False, promoted=False, submission_slots_used=0,
        status='research-only; local format validation is not organizer acceptance', metadata=metadata or {})
    path.with_suffix('.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    return receipt
