"""One place that resolves the pinned inputs, so no script re-derives the footprint differently."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
PINS = json.loads((ROOT / "registry" / "input_pins.json").read_text())


def path(key: str) -> Path:
    return ROOT / PINS["files"][key]["path"]


def load(*, with_lidar: bool = False, sample: bool = False):
    """Return ``(fields, catalogue, footprint, meta)`` on the measured grid.

    Footprint = the organizer sample submission's finite mask intersected with "all 19 feature
    bands valid", which is the template convention (see grid.footprint_from). Every value that
    could be a nodata sentinel is already NaN.
    """
    from . import corrections as C

    feats = C.load_fields(path("features"), lidar_path=path("lidar_scarp") if with_lidar else None)
    with rasterio.open(path("catalogue")) as ds:
        cat = ds.read(1) == 1
    with rasterio.open(path("features")) as ds:
        ok = None
        for i in range(1, ds.count + 1):
            a = ds.read(i)
            k = np.isfinite(a) & (a > C.NODATA_LIMIT)
            ok = k if ok is None else (ok & k)
    if sample:
        with rasterio.open(path("sample")) as ds:
            fp = np.isfinite(ds.read(1))
    else:
        fp = ok
    fp = fp & ok
    meta = dict(shape=cat.shape, cells=int(fp.sum()), catalogue_cells=int((cat & fp).sum()))
    return feats, (cat & fp), fp, meta
