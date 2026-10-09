"""Image transforms shared by both views.

Two properties are load-bearing and both are tested:

* **Metric scale, not pixel scale.** The scored kernel has 300 m support, so every smoothing
  radius here is expressed in metres and converted with the 100 m grid.  A transform that only
  works at "r = 9" is a different physical statement from one at "r = 900 m".
* **Sentinel safety.** The official rasters carry -3.4028234663852886e+38 outside the footprint.
  Every function here takes and returns NaN-aware arrays and fills only *inside* the footprint
  before differentiating, so a footprint edge never becomes a fake fault.  (This is a real
  regression in this project family: an early sibling repo overflowed to inf on the sentinel.)
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

PIXEL_M = 100.0

# (dy, dx, metres-per-step) for the four strike families on a square lattice.  Diagonal steps are
# sqrt(2) px, and are weighted accordingly so a "900 m half-width" means 900 m on any strike.
STRIKES = {
    "E-W":   ((0, 1), (1, 0)),      # strike (dy,dx); across-strike is the orthogonal pair below
    "N-S":   ((1, 0), (0, 1)),
    "NE-SW": ((-1, 1), (1, 1)),
    "NW-SE": ((1, 1), (1, -1)),
}


def fill_outside(a: np.ndarray, valid: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """Replace NaN/sentinel by a constant so filters do not smear NaN into valid pixels."""
    out = np.array(a, dtype=np.float32, copy=True)
    bad = ~np.isfinite(out) | ~valid
    out[bad] = fill
    return out


def rank01(a: np.ndarray, valid: np.ndarray, nbins: int = 4096) -> np.ndarray:
    """Empirical CDF rank inside the footprint -> [0, 1]; NaN outside. Tie-stable.

    Quantile-bin approximation of the rank, not exact argsort: exact ranks over 5.17M valid pixels
    are unnecessary (the metric resolves 100 m, not 1e-7 of a quantile) and cost 10x the memory.

    NaN *inside* the footprint (a transform that legitimately returns NaN, e.g. an unsupported
    edge window) is excluded from the ranking and stays NaN on output.  Before this rule a
    NaN-within-valid cell was pushed into the top histogram bin and came out rank ~1.0, which
    silently turned every edge-masked cell into a top-ranked emission candidate (IR-56-015).
    """
    good = np.asarray(valid, bool) & np.isfinite(a)
    v = a[good]
    if v.size == 0:
        return np.full_like(a, np.nan, dtype=np.float32)
    lo, hi = float(np.nanmin(v)), float(np.nanmax(v))
    if not hi > lo:
        r = np.zeros_like(a, dtype=np.float32)
        r[good] = 0.5
        return np.where(good, r, np.nan).astype(np.float32)
    edges = np.linspace(lo, hi, nbins + 1)
    hist, _ = np.histogram(v, bins=edges)
    cdf = np.cumsum(hist).astype(np.float64)
    cdf /= cdf[-1]
    idx = np.clip(np.searchsorted(edges, a, side="right") - 1, 0, nbins - 1)
    out = np.where(good, cdf[idx], np.nan).astype(np.float32)
    return out


def gradient_magnitude(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """|grad| in units per metre (central differences, sentinel-safe).

    Cells within 2 px of the footprint edge return NaN: the exterior is zero-filled, so a
    central difference there measures the data edge, not the field (IR-56-015 defect class).
    """
    f = fill_outside(a, valid)
    gy, gx = np.gradient(f.astype(np.float32), PIXEL_M, PIXEL_M, edge_order=2)
    gy[~valid] = np.nan
    gx[~valid] = np.nan
    out = np.sqrt(gy * gy + gx * gx).astype(np.float32)
    out[_edge_band(valid, 2.0)] = np.nan
    return out


def box_mean(a: np.ndarray, valid: np.ndarray, radius_m: float) -> np.ndarray:
    """Mean over a disc of the given radius (metres), computed inside the footprint only."""
    r = max(1, int(round(radius_m / PIXEL_M)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = (yy * yy + xx * xx) <= r * r
    k = disc.astype(np.float32)
    num = ndimage.convolve(fill_outside(a, valid), k, mode="constant", cval=0.0)
    den = ndimage.convolve(valid.astype(np.float32), k, mode="constant", cval=0.0)
    out = np.where(den > 0, num / np.maximum(den, 1e-6), np.nan)
    out[~valid] = np.nan
    return out.astype(np.float32)


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Zero-padded integer shift (never np.roll: a wrapped edge invents structure)."""
    h, w = a.shape
    out = np.zeros((h, w), dtype=a.dtype)
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def _edge_band(valid: np.ndarray, radius_px: float) -> np.ndarray:
    """Cells whose distance to the footprint's complement is < radius_px (invalid cells included)."""
    v = np.asarray(valid, bool)
    if v.all():
        return np.zeros(v.shape, bool)
    if not v.any():
        return np.ones(v.shape, bool)
    dist = ndimage.distance_transform_edt(v)
    return dist < radius_px


def scarp_step(a: np.ndarray, valid: np.ndarray, half_width_m: float,
               persist_m: float, strikes=tuple(STRIKES)) -> tuple[np.ndarray, np.ndarray]:
    """Laterally-persistent two-sided across-strike step -- the "is there a straight offset with
    topography/field *discontinuity* that continues for kilometres" transform.

        step_theta(x) = mean_{0<k<=r} [ f(x + k v) - f(x - k v) ]        (v = across-strike unit)
        resp_theta    = |step_theta| smoothed along the strike over ``persist_m``
        response      = max over strikes ;  also returns the argmax strike index

    Why this and not curvature: a curvature or ridge magnitude responds equally to canyon rims,
    stream banks and alluvial-fan edges.  Requiring a *two-sided* offset (both flanks move) and
    kilometres of along-strike persistence removes exactly those, which is the documented
    false-positive mode of fault mappers in this province (Hermant et al. 2025, 50th Stanford
    Geothermal Workshop: their models "falsely fire on coastline, canyon and stream morphology").
    """
    fa = fill_outside(a, valid)
    best = np.full(a.shape, -np.inf, dtype=np.float32)
    arg = np.zeros(a.shape, dtype=np.int16)
    for si, name in enumerate(strikes):
        u, v = STRIKES[name]
        # Lattice length of one step along each direction: sqrt(2) px on the diagonals, 1 px on
        # the axes.  Scaling the sample counts by it makes half_width_m and persist_m mean the same
        # physical distance on every strike, so the maximum over strikes is not an artefact of one
        # strike sampling further than another.
        lv = PIXEL_M * (2 ** 0.5 if (v[0] and v[1]) else 1.0)
        lu = PIXEL_M * (2 ** 0.5 if (u[0] and u[1]) else 1.0)
        rv = max(1, int(half_width_m / lv))
        # Support mask: the two-sided window must lie *inside* the footprint for every k, and the
        # persistence window only reads supported acc.  Without this the zero-fill outside the data
        # extent is differenced against real data and the footprint rim becomes a fake step ~10x
        # the interior response (measured IR-56-015: 56 % of an emission's top cells landed on a
        # 2 px rim band of the competition footprint).
        sup = np.asarray(valid, bool).copy()
        for k in range(1, rv + 1):
            dy, dx = int(round(k * v[0])), int(round(k * v[1]))
            sup &= _shift(np.asarray(valid, bool), dy, dx)
            sup &= _shift(np.asarray(valid, bool), -dy, -dx)
        acc = np.zeros(a.shape, dtype=np.float32)
        for k in range(1, rv + 1):
            dy, dx = int(round(k * v[0])), int(round(k * v[1]))
            acc += _shift(fa, dy, dx) - _shift(fa, -dy, -dx)
        acc /= rv                                  # two-sided mean difference, uniform weights
        mj = max(1, int(persist_m / (2.0 * lu)))    # half-length of the along-strike window
        sup_p = sup.copy()
        for j in range(-mj, mj + 1):
            uy, ux = int(round(j * u[0])), int(round(j * u[1]))
            sup_p &= _shift(sup, uy, ux)
        per = np.zeros(a.shape, dtype=np.float32)
        for j in range(-mj, mj + 1):
            per += np.abs(_shift(acc, int(round(j * u[0])), int(round(j * u[1]))))
        per /= (2 * mj + 1)
        per[~sup_p] = np.nan                        # edge-unsupported cells never respond
        per[~valid] = np.nan
        better = np.isfinite(per) & (per > best)
        best = np.where(better, per, best)
        arg = np.where(better, si, arg)
    best[~np.isfinite(best)] = np.nan
    best[~valid] = np.nan
    return best.astype(np.float32), arg


def hessian_line(a: np.ndarray, valid: np.ndarray, sigma_m: float = 300.0) -> np.ndarray:
    """Bright/dark ridge response: -|lambda_2| of the (scaled) Hessian of a Gaussian-smoothed field.

    Cells within ~3 sigma of the footprint edge return NaN: the exterior is zero-filled, so the
    smoothed field (and its second derivatives) are contaminated out to 3 sigma there
    (IR-56-015 defect class).
    """
    sig = max(0.5, sigma_m / PIXEL_M)
    f = ndimage.gaussian_filter(fill_outside(a, valid).astype(np.float64), sig)
    f /= max(PIXEL_M, 1.0)
    gy, gx = np.gradient(f, 1.0, 1.0)
    yyy, yyx = np.gradient(gy, 1.0, 1.0)
    yxx, yxy = np.gradient(gx, 1.0, 1.0)
    lam2 = 0.5 * ((yyy + yxx) - np.sqrt(np.maximum((yyy - yxx) ** 2 + 4 * yxy ** 2, 0.0)))
    out = np.abs(lam2).astype(np.float32)
    out[~valid] = np.nan
    out[_edge_band(valid, 3.0 * sig + 1.0)] = np.nan
    return out
