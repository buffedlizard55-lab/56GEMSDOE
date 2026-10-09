"""Grid, footprint, spatial blocks and buffers.

Every constant here is *measured* from the restored rasters by ``scripts/prepare_data.py`` and
recorded in ``evidence/grid.json``; nothing in this module is copied from a sibling repository's
claim.  The grid facts themselves are also stated on the official problem page
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format):
UTM zone 11N / EPSG:32611, 100 m resolution, same bounds as the training data, single band,
float32, values in [0, 1], and data outside the bounds null or NaN.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

PIXEL_M = 100.0
CRS_EPSG = "EPSG:32611"
SHAPE = (3730, 3292)                       # (rows, cols), measured
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)   # a, b, c, d, e, f (Affine order, NOT GDAL geotransform order)
CELL_M = 100.0                                 # resolution the rules page states, in metres
SENTINEL_LIMIT = -1e38                      # official nodata is -3.4028234663852886e+38


def open_raster(path: str | Path):
    return rasterio.open(str(path))


def read_band(path: str | Path, band: int, dtype=np.float32) -> np.ndarray:
    """Read one band as float32 with the nodata sentinel already turned into NaN."""
    with rasterio.open(str(path)) as src:
        a = src.read(band).astype(dtype)
    a[~np.isfinite(a)] = np.nan
    a[a < SENTINEL_LIMIT] = np.nan
    return a


def footprint_from(path: str | Path, bands: str = "all") -> np.ndarray:
    """Finite-data footprint.  ``bands='all'`` = every band finite (the intersection).

    Measured, three defensible footprints exist and they differ (see registry/irregularities
    IR-52-002): band-1 finite, all-19-bands finite, and the sample-submission finite mask.  This
    repository emits on the intersection so that both views are defined at every emitted pixel.
    """
    with rasterio.open(str(path)) as src:
        if bands == "all":
            acc = None
            for i in range(1, src.count + 1):
                a = src.read(i)
                ok = np.isfinite(a) & (a > SENTINEL_LIMIT)
                acc = ok if acc is None else (acc & ok)
            return acc
        a = src.read(1)
        return np.isfinite(a) & (a > SENTINEL_LIMIT)


@dataclass(frozen=True)
class BlockSplit:
    """One whole-block train / eval split with a border buffer.

    ``train``  = pixels whose block is held-out, used as the scored region.
    ``fit``    = pixels whose block is *not* held out **and** that are not within ``buffer_px`` of
                 a block boundary, i.e. the only pixels a model may be trained on.
    ``excluded`` = buffered boundary pixels: never trained on, never scored.

    The buffer is what stops a leak that a 300 m kernel would otherwise forgive: a trace entering
    a held-out block is usually visible in the neighbouring block's features.
    """

    train: np.ndarray
    fit: np.ndarray
    excluded: np.ndarray
    held: tuple[int, ...]
    buffer_px: int


def make_split(lab: np.ndarray, buf: np.ndarray, held: list[int], buffer_px: int) -> BlockSplit:
    held = [int(h) for h in held]
    train = np.isin(lab, held)
    fit = (~train) & (~buf)
    return BlockSplit(train=train, fit=fit, excluded=buf, held=tuple(held), buffer_px=buffer_px)


def block_labels(shape: tuple[int, int], valid: np.ndarray, n: int = 8) -> np.ndarray:
    """Assign each valid pixel to one of n x n contiguous rectangular blocks.

    Contiguous *rectangles* are used deliberately: a random pixel split leaks along a trace that
    crosses the split, and a 300 m kernel forgives it.  Blocks are whole segments of the grid, so
    every block-boundary is a straight line, and any pixel near it is buffered out of training.
    """
    h, w = shape
    rows = np.linspace(0, h, n + 1).astype(int)
    cols = np.linspace(0, w, n + 1).astype(int)
    lab = np.full(shape, -1, dtype=np.int16)
    k = 0
    for i in range(n):
        for j in range(n):
            blk = np.zeros(shape, dtype=bool)
            blk[rows[i]:rows[i + 1], cols[j]:cols[j + 1]] = True
            lab[blk & valid] = k
            k += 1
    return lab


def buffer_from_block_ids(lab: np.ndarray, buffer_px: int) -> np.ndarray:
    """True on pixels whose ``buffer_px`` neighbourhood touches more than one block id.

    A dilation of block borders: ``max`` and ``min`` of the (id, id + 1) pair over a window of
    radius ``buffer_px`` disagree exactly where the neighbourhood crosses a boundary.  Block id
    0 is excluded from the min-side test by the +1 shift, so an unlabelled (-1) neighbour counts
    as a boundary too (outside the footprint we do not want to trust it).
    """
    from scipy import ndimage
    size = 2 * buffer_px + 1
    pos = np.where(lab >= 0, lab.astype(np.int32) + 1, 0)
    pmax = ndimage.maximum_filter(pos, size=size, mode="nearest")
    pmin = ndimage.minimum_filter(np.where(lab >= 0, lab.astype(np.int32) + 1, -1), size=size,
                                  mode="nearest")
    return (pmax != pmin) & (lab >= 0)


def save_json(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=_fallback))


def _fallback(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def write_geotiff(path: str | Path, arr: np.ndarray, *, nodata: float | None = None) -> dict:
    """Write a single-band float32 GeoTIFF on the pinned competition grid, then re-read it.

    The re-read is the contract: the writer returns what the *file* says, not what the array said.
    Tiled (256 px) with deflate + horizontal predictor is what this family has actually shipped:
    it is byte-small for a 0/1 emission, GDAL-legal, and reads back identical.  The block size is a
    power of two so it cannot trip the TileWidth rules that killed an earlier write in this family.

    The affine is built from the pinned six numbers and then *asserted* against them, because the
    first version of this writer passed ``from_origin`` the wrong two indices and produced a file
    whose bounds were ``[-1.68e10, 100]`` instead of the competition box.  The submission gate caught
    it by comparing to ``data/sample_submission.tif``; the assert is what stops it ever reaching a
    gate again.  Read the receipt, not the log.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr.dtype != np.float32:
        raise TypeError(f"submission must be float32, got {arr.dtype}")
    if arr.shape != SHAPE:
        raise ValueError(f"submission must be {SHAPE}, got {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError("submission contains NaN/inf; all-finite compatibility policy requires finite values")
    if arr.min() < 0.0 or arr.max() > 1.0:
        raise ValueError(f"submission out of range: min={arr.min()} max={arr.max()}")
    from affine import Affine
    tr = Affine(*[float(v) for v in TRANSFORM])                 # Affine order: a, b, c, d, e, f
    west, north = tr.c, tr.f
    xs, ys = tr.a, -tr.e
    from rasterio.transform import from_origin
    check = from_origin(west, north, xs, ys)
    if tuple(float(v) for v in check)[:6] != tuple(tr)[:6]:
        raise AssertionError(f"transform reconstruction drifted: {tuple(check)[:6]} != {tuple(tr)[:6]}")
    if abs(xs) != CELL_M or abs(ys) != CELL_M:
        raise AssertionError(f"cell size {xs} x {ys} != {CELL_M} m")
    profile = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                   dtype="float32", crs=CRS_EPSG, transform=tr,
                   tiled=True, blockxsize=256, blockysize=256, compress="deflate", predictor=2)
    if nodata is not None:
        profile["nodata"] = float(nodata)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
    return read_geotiff(path)


def read_geotiff(path: str | Path) -> dict:
    """Everything a validator can complain about, re-derived from the bytes on disk."""
    import hashlib
    from rasterio.enums import Resampling  # noqa: F401  (import guard only; not used)

    p = Path(path)
    with rasterio.open(p) as src:
        a = src.read(1)
        crs = str(src.crs) if src.crs is not None else None
        t = tuple(float(v) for v in src.transform)[:6]
        info = dict(
            path=str(p), bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            bands=src.count, dtype=src.dtypes[0], height=src.height, width=src.width,
            crs=crs, transform=list(t), res=[float(v) for v in src.res],
            nodata=src.nodata, nodata_repr=repr(src.nodata),
        )
    finite = np.isfinite(a)
    info.update(
        finite_pixels=int(finite.sum()),
        min=float(np.nanmin(a)) if finite.any() else None,
        max=float(np.nanmax(a)) if finite.any() else None,
        positive_pixels=int((a > 0).sum()),
        nonzero_in_footprint=int(((a > 0) & finite).sum()),
        unique_values=int(len(np.unique(a[finite]))) if finite.any() else 0,
    )
    return info
