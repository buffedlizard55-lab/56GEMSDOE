"""Corrections lane: how far does the catalogue sit from the evidence, and where is the fault?

The measurement
---------------
For every pixel of the competition catalogue (``existing_faults.tif``, the USGS/INGENIOUS
quaternary-fault raster shipped on the data tab) we walk a straight line perpendicular to the local
trace strike, +-400 m (``HALF_WINDOW_PX = 4`` cells at 100 m), and look for the nearest

* **crest** of the DEM scarp -- the convex break-in-slope, the maximum of ``-d2z/dn2`` of the
  detrended-elevation profile (``det_elev``, band 12 of the official feature stack);
* **ridge** of the magnetic gradient -- the maximum of the ``tmi_hg`` magnitude profile (band 3);
* and, as an independent corroboration channel only, the gravity gradient ``iso_grav_anom_hg``
  (band 18).

All three are crest/ridge detectors: they locate a step and are indifferent to which side of the
catalogue the step lies on, which is what makes them admissible for a registration test. None is
learned and none is catalogue-derived, so none can leak the holdout target.

Why this is the right instrument for the scoring rule
-----------------------------------------------------
DrivenData staff, thread 11516 post #2 (fetched quote in ``knowledge/sources.json``): "Pixels
corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not
count towards penalty terms." A dot sitting exactly on a catalogue pixel therefore earns nothing,
while a dot a few cells off the line can still reach a *corrected* trace through the 300 m
triangular kernel. If the catalogue is systematically displaced from the geomorphic and magnetic
lineation, the evidence-defined trace -- not the catalogue line -- is where credit lives. If it is
not, this lane must emit nothing and the deliverable is the offset histogram itself.

Everything here is label-free. The catalogue enters only as the object being measured (and, in the
holdout, only through its visible part).

Deterministic: this module contains no RNG. The control arms take an explicit seeded generator.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d, map_coordinates

PIXEL_M = 100.0
HALF_WINDOW_PX = 4.0            # +-400 m: the 300 m kernel envelope plus a cell of slack
STEP_PX = 0.25                  # 25 m sampling along the transect
CURV_BASELINE_PX = 1.0          # second difference taken over 100 m, i.e. one source cell
SMOOTH_PX = 0.75                # gaussian sigma in PIXELS (converted to samples inside find_crest)
MIN_PROM_FRAC = 0.25            # crest must clear its flanking troughs by this fraction of its height
OFFSET_GATE_PX = 2.0            # the brief's "about two pixels" = 200 m
SIGN_GATE = 0.75                # fraction of a corridor's pixels that must agree in sign
DEG = np.pi / 180.0
NODATA_LIMIT = -1e38            # measured float32 sentinel -3.4028234663852886e+38


# --------------------------------------------------------------------------------------------
# fields
# --------------------------------------------------------------------------------------------
def load_fields(feature_path, lidar_path=None):
    """``{name: float32 grid}`` with the official nodata sentinel already turned into NaN.

    The sentinel is measured, not assumed: the stack stores nodata as -3.4028234663852886e+38,
    which ``np.isfinite`` accepts as valid data (57.93 % of band 1, see evidence/grid.json), so a
    reader that forgets this treats the outside-footprint area as an elevation of -3.4e38 m. The
    band index is asserted against the file's own band description rather than trusted from a
    table.
    """
    import rasterio

    out: dict = {}
    want = {"det_elev": 12, "tmi_hg": 3, "tmi": 14, "iso_grav_anom_hg": 18, "det_elev_slope": 19}
    with rasterio.open(str(feature_path)) as src:
        desc = {i: (src.descriptions[i - 1] or "") for i in range(1, src.count + 1)}
        for name, band in want.items():
            assert desc[band].split(" ")[0] == name, f"band {band} is {desc[band]!r}, not {name!r}"
            a = src.read(band).astype(np.float64)
            bad = ~np.isfinite(a) | (a < NODATA_LIMIT)
            n_bad = int(bad.sum())
            a[bad] = np.nan
            out[name] = a.astype(np.float32)
            out.setdefault("_inventory", {})[name] = dict(
                band=band, description=desc[band], nodata_cells=n_bad,
                nan_fraction=n_bad / a.size,
                stats=dict(min=float(np.nanmin(a)), max=float(np.nanmax(a)),
                           p50=float(np.nanmedian(a)), p99=float(np.nanpercentile(a, 99))))
    if lidar_path is not None:
        # GEMSDOE48 h52_scarp3m_100m.tif: int16, value/SCALE (SCALE from scripts/dem_region_merge.py,
        # which encodes a 3 m line-persistent scarp detector run over 700 USGS 3DEP 1 m tiles).
        with rasterio.open(str(lidar_path)) as src:
            d = {src.descriptions[i - 1]: i for i in range(1, src.count + 1)}
            for band, scale, key in (("h_all", 100.0, "lidar_h_m"), ("strike_at", 100.0, "lidar_strike_deg"),
                                      ("facing_at", 1e4, "lidar_facing"), ("cover", 1e4, "lidar_cover")):
                a = src.read(d[band]).astype(np.float64)
                a[a <= -32767] = np.nan                 # int16 nodata -32768
                out[key] = (a / scale).astype(np.float32)
    return out


# --------------------------------------------------------------------------------------------
# trace strike, from catalogue geometry alone
# --------------------------------------------------------------------------------------------
def strike_at(cat: np.ndarray, row: np.ndarray, col: np.ndarray, window_px: int = 5):
    """Local strike unit vectors at the requested pixels, from PCA of the trace inside a window.

    Gathered per origin (N x side x side of float32) instead of filtering the 12.3 M-cell grid: the
    same second moments, two orders of magnitude less memory, which matters in a 3 GB sandbox.

    A +-500 m window is used because a normal-fault trace is straight to first order at that scale;
    a smaller window makes the strike jittery on 100 m rasterisation stair-steps, and that jitter
    smears the offset histogram. ``ok`` is False where fewer than 5 catalogue pixels sit in the
    window: an isolated pixel has no strike, and inventing one would fabricate an offset.
    """
    w = int(window_px)
    side = 2 * w + 1
    pad = np.pad(np.asarray(cat, np.float32), w)
    off = np.arange(-w, w + 1, dtype=np.int64)
    oy, ox = np.meshgrid(off, off, indexing="ij")
    base = pad.shape[1]
    idx = (row[:, None, None] + w + oy[None]) * base + (col[:, None, None] + w + ox[None])
    win = pad.reshape(-1)[idx]                                   # (N, side, side)
    cnt = win.sum(axis=(1, 2))
    yy = np.broadcast_to(oy[None].astype(np.float32), win.shape)
    xx = np.broadcast_to(ox[None].astype(np.float32), win.shape)
    n = np.maximum(cnt, 1e-6)
    cy = (win * yy).sum((1, 2)) / n
    cx = (win * xx).sum((1, 2)) / n
    cyy = (win * yy * yy).sum((1, 2)) / n - cy * cy
    cxx = (win * xx * xx).sum((1, 2)) / n - cx * cx
    cxy = (win * yy * xx).sum((1, 2)) / n - cy * cx
    tr, det = cyy + cxx, cyy * cxx - cxy * cxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    # Principal eigenvector of [[cyy,cxy],[cxy,cxx]]. Row-1 form (cxy, l1-cyy) degenerates when
    # cxy == 0 (axis-aligned trace), where row-2 (l1-cxx, cxy) is the usable one; both are needed.
    a1, b1 = cxy, l1 - cyy
    a2, b2 = l1 - cxx, cxy
    use1 = (np.abs(a1) + np.abs(b1)) >= (np.abs(a2) + np.abs(b2))
    ny = np.where(use1, a1, a2)
    nx = np.where(use1, b1, b2)
    nr = np.hypot(ny, nx)
    ok = (cnt >= 5.0) & (nr > 1e-6)
    ty = np.where(ok, ny / np.where(nr > 0, nr, 1.0), 0.0)
    tx = np.where(ok, nx / np.where(nr > 0, nr, 1.0), 0.0)
    # Canonicalise the eigenvector sign. An eigenvector is defined only up to +-1, and the normal
    # (-tx, ty) inherits that arbitrariness: without a rule, two neighbouring pixels of the same
    # trace could place their corrected dots on opposite sides, which would destroy any corridor-level
    # sign statistic and scatter the emission. Rule: strike points along +col; ties go to +row.
    flip = (tx < 0) | ((tx == 0) & (ty < 0))
    ty, tx = np.where(flip, -ty, ty), np.where(flip, -tx, tx)
    return ty.astype(np.float32), tx.astype(np.float32), ok, cnt.astype(np.int32)


# --------------------------------------------------------------------------------------------
# transect sampling and crest location
# --------------------------------------------------------------------------------------------
@dataclass
class Profiles:
    s: np.ndarray              # (S,) signed offsets along the normal, in pixels
    dem: np.ndarray            # (N, S) convexity score -d2z/dn2, metres per cell^2
    mag: np.ndarray            # (N, S) |tmi_hg| profile
    grav: np.ndarray           # (N, S) |iso_grav_anom_hg| profile
    inside: np.ndarray         # (N, S) bool: sample inside footprint and finite in every field
    origin_valid: np.ndarray   # (N,) bool
    row: np.ndarray
    col: np.ndarray


def _convexity(z: np.ndarray, h: float, baseline_px: float = CURV_BASELINE_PX) -> np.ndarray:
    """``-d2z/dn2`` on the sampled profile: positive on a convex break (a scarp crest).

    The stencil straddles one *source cell* (``lag = baseline_px / step`` samples, = 4 here), not one
    *sample*. That choice is measured, not stylistic: the profiles are bilinearly interpolated, so a
    smooth surface sampled at 0.25 px is piecewise linear between source gridlines, and its second
    difference at sample spacing is a comb of spikes at every gridline -- 16x amplified by ``1/h**2``.
    Differencing twice at 0.25 px therefore reported spurious "crests" one cell apart and, because the
    crest rule keeps the one *nearest* the trace, it pulled the whole offset histogram toward zero: on a
    synthetic scarp 3 cells off the trace the sample-spacing stencil reported 0.0 px. With a one-cell
    baseline the kinks cancel and the true crest is recovered.

    Sign: ``-d2`` is positive where the surface is convex, so the same "maximise" routine serves a
    scarp crest and a gradient ridge. No pre-smoothing of the elevation: that suppresses the very
    break-in-slope being located.
    """
    lag = max(1, int(round(baseline_px / h)))
    filled = np.where(np.isfinite(z), z, 0.0)
    live = np.isfinite(z)
    out = np.full(z.shape, np.nan)
    if z.shape[1] < 2 * lag + 1:
        return out
    d2 = (filled[:, :-2 * lag] - 2.0 * filled[:, lag:-lag] + filled[:, 2 * lag:]) / (lag * h) ** 2
    ok = live[:, :-2 * lag] & live[:, lag:-lag] & live[:, 2 * lag:]
    out[:, lag:-lag] = np.where(ok, d2, np.nan)
    return -out


def sample_profiles(fields: dict, row: np.ndarray, col: np.ndarray, ty: np.ndarray, tx: np.ndarray,
                    footprint: np.ndarray, half: float = HALF_WINDOW_PX, step: float = STEP_PX,
                    rescale_m: float = PIXEL_M) -> Profiles:
    """Sample the evidence profiles along a normal through each (row, col) origin.

    The competition grid is uniform and axis-aligned (measured transform ``(100, 0, 243350, 0,
    -100, 4508550)``), so one pixel of offset is exactly ``rescale_m`` metres along either axis and
    distances can be quoted in metres without a resampling correction. Sampling is bilinear; a
    sample that leaves the footprint or lands on a sentinel is invalid for *all three* fields, so a
    truncated transect cannot borrow a crest from outside the study area.

    The array is sampled one cell wider than ``half`` on each side, because the convexity stencil needs
    that room; the crediting window is restored by ``max_offset`` in :func:`find_crest`, so a crest
    400 m from the trace is still reportable instead of being clipped off the end of the transect.
    """
    pad = CURV_BASELINE_PX + 2.0 * SMOOTH_PX      # room for the stencil and for the gaussian's tails
    offs = np.arange(-half - pad, half + pad + 1e-9, step)
    ny, nx = -tx, ty                      # strike rotated 90 degrees
    yy = row[:, None] + offs[None, :] * (ny[:, None] * rescale_m / PIXEL_M)
    xx = col[:, None] + offs[None, :] * (nx[:, None] * rescale_m / PIXEL_M)
    coords = np.stack([yy.ravel(), xx.ravel()])
    H, W = footprint.shape
    rr = np.rint(yy).astype(np.int64)
    cc = np.rint(xx).astype(np.int64)
    inb = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
    rr = np.clip(rr, 0, H - 1)
    cc = np.clip(cc, 0, W - 1)
    inside_cell = np.where(inb, footprint[rr, cc], False)

    def grab(a):
        v = map_coordinates(np.nan_to_num(a, nan=0.0), coords, order=1, mode="nearest").reshape(yy.shape)
        return v, inside_cell & np.isfinite(a[rr, cc])

    z, ok_z = grab(fields["det_elev"])
    g, ok_g = grab(np.abs(np.nan_to_num(fields["tmi_hg"], nan=0.0)))
    q, ok_q = grab(np.abs(np.nan_to_num(fields["iso_grav_anom_hg"], nan=0.0)))
    inside = ok_z & ok_g & ok_q
    z = np.where(inside, z, np.nan)
    h_step = float(offs[1] - offs[0]) * rescale_m / PIXEL_M
    dem = _convexity(z, h_step)
    g = np.where(inside, g, np.nan)
    q = np.where(inside, q, np.nan)
    origin_valid = inside.sum(axis=1) >= (offs.size - 4)          # at most two dead samples per transect
    return Profiles(s=offs, dem=dem, mag=g, grav=q, inside=inside, origin_valid=origin_valid,
                    row=row, col=col)


def find_crest(score: np.ndarray, s: np.ndarray, *, smooth: float = SMOOTH_PX,
               min_prom: float = MIN_PROM_FRAC, min_offset: float = 0.0, max_offset: float = np.inf,
               min_hgt: float = 0.0, mode: str = "nearest"):
    """Nearest interior local maximum of a per-sample score, with sub-sample refinement.

    ``mode="nearest"`` (the brief's "locate the nearest crest") picks the qualifying crest closest to
    the trace; ``mode="strongest"`` picks the tallest and is reported as a control, because a
    prominence-selected crest can sit further away than a small nearby bump.

    Returns ``(offset_px, height, strength_ratio, n_candidates)``. ``offset_px`` is NaN when a
    transect has no qualifying interior extremum -- a miss is recorded as a miss and never silently
    credited to offset 0, which would bias the histogram toward "no correction needed". ``height`` is
    the smoothed convexity at the peak in data units per cell^2 (the absolute "is this a real scarp"
    measure, thresholded by the null calibration) and ``strength_ratio`` the peak's height divided by
    the strongest convex break anywhere in that transect: together they are the "unambiguous crest"
    test the brief asks for, and each is invariant to which side of the trace the scarp is on.
    """
    x = np.asarray(score, np.float64)
    n, S = x.shape
    live = np.isfinite(x)
    if S < 5:
        return (np.full(n, np.nan),) * 3 + (np.zeros(n, np.int64),)
    step = float(abs(s[1] - s[0]))
    sig = max(smooth / max(step, 1e-9), 0.5)          # sigma is quoted in PIXELS
    f = np.where(live, x, 0.0)
    mass = gaussian_filter1d(live.astype(float), sig, axis=1, mode="constant")
    sm = gaussian_filter1d(f, sig, axis=1, mode="nearest") / np.maximum(mass, 1e-9)
    # A crest is only trusted where the smoothing kernel sat entirely on live samples. Renormalising by
    # the live mass keeps the average right next to a gap, but it *inflates* the score there, and an
    # inflated edge was being chosen as the "nearest crest" instead of the real scarp; requiring full
    # support turns that into a recorded miss, which is the honest outcome.
    full = mass >= 0.999          # tolerance is a float-accumulation allowance, not physics
    left = np.concatenate([sm[:, :1], sm[:, :-1]], axis=1)      # left[j]  = sm[j-1], clamped at j=0
    right = np.concatenate([sm[:, 1:], sm[:, -1:]], axis=1)     # right[j] = sm[j+1], clamped at j=S-1
    is_max = (sm >= left) & (sm >= right) & live & full
    is_max[:, 0] = False
    is_max[:, -1] = False                                  # interior only: never report a clipped edge
    fin = np.where(live, sm, -np.inf)
    mx = fin.max(axis=1, keepdims=True)                       # strongest convex break in this transect
    # Strength is measured two ways, both of which are symmetric in the sign of the offset. The earlier
    # rule (peak above the profile's own minimum, clearance of the flanking troughs) was not: a real
    # scarp's -z'' is a *doublet* (concave lobe 1 cell either side of the convex one), so a crest to the
    # right of the trace was flanked by its own trough and failed the clearance test while an identical
    # crest to the left, whose trough had fallen off the clipped end of the window, passed. That produced
    # a one-sided detector and a histogram biased toward zero -- caught by the synthetic-scarp test.
    height = np.where(live, sm, np.nan)
    rel = height / np.where(np.abs(mx) > 1e-12, mx, np.inf)
    qual = (is_max & np.isfinite(height) & (height > 0)
            & (rel >= min_prom) & (np.nan_to_num(height, nan=-np.inf) >= min_hgt))
    if min_offset > 0:
        qual = qual & (np.abs(s)[None, :] >= min_offset)
    if np.isfinite(max_offset):
        qual = qual & (np.abs(s)[None, :] <= max_offset)   # the brief's +-400 m crediting window
    ar = np.arange(n)
    if mode == "strongest":
        # tallest qualifying crest, ties broken toward the trace: the control for the rule below.
        top = np.where(qual, sm, -np.inf).max(axis=1, keepdims=True)
        qual = qual & (sm >= top - 1e-9)
    elif mode != "nearest":
        raise ValueError(f"unknown crest rule {mode!r}")
    dist = np.abs(s)[None, :] + np.where(qual, 0.0, np.inf)
    idx = dist.argmin(axis=1)
    got = qual[np.arange(n), idx]
    j = np.clip(idx, 1, S - 2)
    y0, y1, y2 = sm[np.arange(n), j - 1], sm[np.arange(n), j], sm[np.arange(n), j + 1]
    den = y0 - 2 * y1 + y2
    dd = np.where(np.abs(den) > 1e-12, 0.5 * (y0 - y2) / np.where(np.abs(den) > 1e-12, den, 1.0), 0.0)
    ds = s[j] + np.clip(dd, -1.0, 1.0) * float(s[1] - s[0])
    off = np.where(got, ds, np.nan)
    hgt = np.where(got, height[np.arange(n), idx], np.nan)
    pr = np.where(got, rel[np.arange(n), idx], np.nan)
    return off, hgt, pr, qual.sum(axis=1).astype(np.int64)


# --------------------------------------------------------------------------------------------
# the lane measurement
# --------------------------------------------------------------------------------------------
def measure(fields: dict, cat: np.ndarray, footprint: np.ndarray, half: float = HALF_WINDOW_PX,
            window_px: int = 5, min_offset_px: float = 0.0, min_hgt: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    """Per-catalogue-pixel signed offsets to the nearest DEM crest and magnetic/gravity ridge.

    Sign convention: positive is to the left of the strike vector, i.e. along ``(-tx, ty)`` in
    (row, col) space, which for a north-referenced UTM grid is "west of a north-facing trace". The
    sign is only meaningful as a pair: DEM and magnetic offsets measured on the same transect are
    comparable, and a genuinely displaced map line shows as one signed mode in both families.
    """
    row, col = np.nonzero(cat & footprint)
    ty, tx, strike_ok, cnt = strike_at(cat & footprint, row, col, window_px=window_px)
    keep = strike_ok
    P = sample_profiles(fields, row[keep], col[keep], ty[keep], tx[keep], footprint, half=half)
    hd, hm, hg = min_hgt
    kw = dict(max_offset=half, min_offset=min_offset_px)
    dem_off, dem_h, dem_p, dem_n = find_crest(P.dem, P.s, min_hgt=hd, **kw)
    mag_off, mag_h, mag_p, mag_n = find_crest(P.mag, P.s, min_hgt=hm, **kw)
    grv_off, grv_h, grv_p, grv_n = find_crest(P.grav, P.s, min_hgt=hg, **kw)
    # control: would the "tallest crest" rule have picked a different place? reported, not used.
    dem_str, _ = find_crest(P.dem, P.s, min_hgt=hd, mode="strongest", **kw)[:1] + (None,)
    mag_str, _ = find_crest(P.mag, P.s, min_hgt=hm, mode="strongest", **kw)[:1] + (None,)
    return dict(
        row=row[keep].astype(np.int32), col=col[keep].astype(np.int32),
        strike_ok=keep, n_window_pixels=cnt[keep].astype(np.int16),
        valid=P.origin_valid,
        dem_off_px=dem_off, dem_hgt=dem_h, dem_prom=dem_p, dem_ncand=dem_n,
        mag_off_px=mag_off, mag_hgt=mag_h, mag_prom=mag_p, mag_ncand=mag_n,
        grv_off_px=grv_off, grv_hgt=grv_h, grv_prom=grv_p, grv_ncand=grv_n,
        dem_off_strongest=dem_str, mag_off_strongest=mag_str,
        strike_deg=np.degrees(np.arctan2(tx[keep], ty[keep])) % 180.0,
    )


def control_points(fields: dict, cat: np.ndarray, footprint: np.ndarray, n: int = 60988,
                   seed: int = 5601, min_dist_px: int = 5, half: float = HALF_WINDOW_PX,
                   mode: str = "random"):
    """Two nulls, because "nearest crest within 400 m" is not zero where no fault exists.

    ``random``  -- random footprint pixels at least ``min_dist_px`` from any catalogue pixel, with a
                  random strike. This is the *magnitude* null: it answers "what offset does the
                  detector return when there is nothing to be offset from?". Any claim that the
                  median catalogue-to-crest offset is 1.6 px is meaningless without it.
    ``rotated`` -- the same catalogue pixels and the same +-400 m window, but sampled along a random
                  direction instead of the local normal. This is the *geometry* null: if the
                  perpendicular transect is not special, the offset signal is lineation noise.
    """
    rng = np.random.default_rng(seed)
    if mode == "random":
        near = ndimage.binary_dilation(cat, iterations=int(min_dist_px)) & footprint
        yy, xx = np.nonzero(footprint & ~near)
        pick = rng.choice(yy.size, size=min(int(n), yy.size), replace=False)
        row, col = yy[pick], xx[pick]
        ang = rng.random(row.size) * np.pi              # no trace to align to
        ty, tx = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
    elif mode == "rotated":
        row, col = np.nonzero(cat & footprint)
        ty, tx, ok, _ = strike_at(cat & footprint, row, col)
        ang = np.deg2rad(rng.random(row.size) * 180.0)  # rotate away from the strike
        ty, tx = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
    else:
        raise ValueError(mode)
    P = sample_profiles(fields, row, col, ty.astype(np.float32), tx.astype(np.float32), footprint, half=half)
    dem_off, dem_h, dem_p, _ = find_crest(P.dem, P.s, max_offset=half)
    mag_off, mag_h, mag_p, _ = find_crest(P.mag, P.s, max_offset=half)
    return dict(mode=mode, row=row.astype(np.int32), col=col.astype(np.int32), valid=P.origin_valid,
                dem_off_px=dem_off, dem_hgt=dem_h, dem_prom=dem_p,
                mag_off_px=mag_off, mag_hgt=mag_h, mag_prom=mag_p)


def usable(rec: dict, min_prom: float = MIN_PROM_FRAC, both: bool = True) -> np.ndarray:
    """Pixels with a valid transect and a qualifying crest in every family used by the rule."""
    u = rec["valid"] & np.isfinite(rec["dem_off_px"]) & (rec["dem_prom"] >= min_prom)
    if both:
        u &= np.isfinite(rec["mag_off_px"]) & (rec["mag_prom"] >= min_prom)
    return u


def joint_offset(rec: dict, u: np.ndarray | None = None):
    """``(joint_offset_px, corroborated)``: mean of the two family offsets where they agree within 1 px.

    The conjunction is the lane's "evidence says the fault is here" test: a DEM crest and a
    magnetic ridge landing on the same place is one physical break in two independent data; two
    separate lineations would not.
    """
    d, m = rec["dem_off_px"], rec["mag_off_px"]
    agree = np.isfinite(d) & np.isfinite(m) & (np.abs(d - m) <= 1.0) & (np.sign(d) == np.sign(m))
    if u is not None:
        agree = agree & np.asarray(u, bool)
    out = np.full(rec["dem_off_px"].shape, np.nan)
    out[agree] = 0.5 * (d[agree] + m[agree])
    return out, agree


def corridor_table(rec: dict, cat: np.ndarray, min_prom: float = MIN_PROM_FRAC,
                   offset_gate_px: float = OFFSET_GATE_PX, sign_gate: float = SIGN_GATE,
                   min_hgt: float = 0.0, sigma_floor_px: float = 0.0):
    """Aggregate per-pixel offsets into whole catalogue components (8-connected traces).

    A corridor *qualifies* when (a) >= ``sign_gate`` of its usable pixels put the displacement on
    the same side, (b) the median joint offset exceeds ``offset_gate_px``, (c) the crest is
    corroborated by both families within 1 px on most pixels, and (d) the component is long enough
    that "consistent" is not one lucky pixel. Sign agreement, not mean magnitude, is load-bearing: a
    mean of +2 px made of half +6 and half -2 is detector scatter, not a displaced map line.
    """
    lab, n = ndimage.label(cat, structure=np.ones((3, 3), bool))
    idx = lab[rec["row"], rec["col"]]
    u = usable(rec, min_prom=min_prom)
    joint, corr = joint_offset(rec, u)
    joint_all, corr_all = joint, corr
    rows = []
    for k in range(1, n + 1):
        sel = (idx == k) & u
        m = int(sel.sum())
        if m < 8:
            continue
        d, j = rec["dem_off_px"][sel], joint[sel]
        agree = np.isfinite(j)
        sign_d = np.sign(d)
        rows.append(dict(
            comp=k, n_usable=m, n_component=int((idx == k).sum()),
            dem_med=float(np.median(d)), dem_mad=float(np.median(np.abs(d - np.median(d)))),
            dem_iqr=float(np.subtract(*np.percentile(d, [75, 25]))),
            dem_sign_pos=float((sign_d > 0).mean()), dem_sign_consistency=float(max((sign_d > 0).mean(), (sign_d < 0).mean())),
            mag_sign_consistency=float(max((np.sign(rec["mag_off_px"][sel]) > 0).mean(),
                                            (np.sign(rec["mag_off_px"][sel]) < 0).mean())),
            joint_med=float(np.median(j[agree])) if agree.sum() >= 4 else float("nan"),
            joint_n=int(agree.sum()),
            corroborated_frac=float(agree.mean()),
            length_m=float(m) * PIXEL_M,
            strike_deg=float(np.median(rec["strike_deg"][sel])),
        ))
    for r in rows:
        jm = r["joint_med"]
        # robust SE of a median: 1.2533 * sigma / sqrt(n), with sigma estimated by MAD/0.6745
        jmads = np.median(np.abs(joint_all[corr_all & (idx == r["comp"])] - jm)) if np.isfinite(jm) else np.nan
        r["joint_mad"] = float(jmads)
        se_raw = float(1.2533 * (jmads / 0.6745) / np.sqrt(max(r["joint_n"], 1))) if np.isfinite(jmads) else float("nan")
        # A MAD that collapses to zero on four pixels makes z explode (one corridor in this run reached
        # z = 60), so the floor is the measured disagreement between a 100 m offset and the same offset
        # measured on 3 m LiDAR (scripts/lidar_calibration.py), not a tuning knob.
        r["joint_se"] = float(max(se_raw, sigma_floor_px / np.sqrt(max(r["joint_n"], 1)))) if (
            np.isfinite(se_raw) or sigma_floor_px > 0) else float("nan")
        r["joint_se_raw"] = se_raw
        # 3 SE keeps a long trace with a tiny skew from masquerading as a displaced map line
        r["z"] = float(abs(jm) / r["joint_se"]) if r["joint_se"] and np.isfinite(r["joint_se"]) else float("nan")
        r["qualifies"] = bool(np.isfinite(jm) and abs(jm) >= offset_gate_px
                              and r["dem_sign_consistency"] >= sign_gate
                              and r["mag_sign_consistency"] >= sign_gate
                              and r["corroborated_frac"] >= 0.6
                              and r["n_usable"] >= 12 and np.isfinite(r["z"]) and r["z"] >= 3.0)
    return rows, joint, corr, u
