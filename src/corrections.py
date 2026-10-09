"""Corrections lane: measure how far the catalogue sits from the evidence.

Lane brief (parallel-run protocol, this session's single method paragraph):

  "Corrections lane: measure how far the catalogue sits from the evidence, then
   emit where the evidence says the fault is. The organizers said new-fault ground
   truth can lie within 300 m of a known trace as 'corrections or modifications to
   existing fault traces' ... Known-fault pixels are masked pixel-exactly, so the
   catalogue line itself is not the target. ... sample perpendicular transects
   within +/-400 m of every catalogue trace, locate the nearest crest of the
   DEM-curvature scarp and of the magnetic gradient ridge, and publish the offset
   histogram, calibrated on 1 m LiDAR tiles where the crest is unambiguous. Where
   a consistent offset exceeds about two pixels, emit dots on the evidence-defined
   trace rather than the catalogue line. ... If offsets cluster under two pixels,
   report that as the result and emit nothing from this lane."

Method (all geometry on the official grid: EPSG:32611, 100 m px, 3730 x 3292)
---------------------------------------------------------------------------
1. Catalogue = labels.tif (existing_faults.tif): 1 = known fault pixel,
   -1 = outside the scored footprint.  The catalogue line is an INPUT here, never
   a target: the live scorer masks known-fault pixels pixel-exactly
   (DrivenData forum thread 11516, linked on the site's sources page).
2. Traces = record_id groups of the official vector catalogue
   (USGS QFaults + INGENIOUS, exported as trace_segments_utm11.csv in the
   GEMSDOE51 registry; 99.8% of raster fault pixels lie within 1.5 px of a vector
   segment).  Per-record statistics need long traces; the raster's 8-connected
   components are too fragmented (median 12 px) for consistency tests.
3. Local trace orientation from the structure tensor of the catalogue mask
   (gaussian-weighted window sums of squared sobel gradients).  The perpendicular
   direction is the minor-eigenvector (gradient) direction.
4. Perpendicular transects: +/-4 px (+/-400 m) at 0.25 px steps (33 samples),
   bilinearly sampled from the official feature bands:
     - DEM scarp       : det_elev_slope (band 19) - ridge of the slope of
                         detrended elevation (the DEM-curvature scarp crest).
     - magnetic ridge  : tmi_hg (band 3) - horizontal-gradient ridge of TMI.
   Two crest definitions are measured per band:
     - strongest : the dominant crest in the +/-400 m window (where the evidence
                   says the fault is when the catalogue is displaced from it);
     - nearest   : the prominent crest nearest the catalogue line (pure
                   registration: how far the catalogue sits from the closest
                   crest).
5. Unambiguity gate: a crest is kept when its prominence >= K x robust noise
   (1.4826 x MAD of the transect profile) and it is an interior local maximum;
   sub-sample refinement by parabolic interpolation.  K is calibrated per band
   against the 1 m LiDAR scarp product (below).
6. Calibration: the cached 1 m LiDAR scarp product (7GEMSDOE
   external/dem/lidar_scarp_features_u8.tif - 706 official USGS 3DEP 1 m tiles
   mosaicked onto this grid, 12 uint8 channels with documented dequantisation;
   covers 75% of the footprint) is sampled on the same transects.  The LiDAR
   crest = max of lapneg_max (crest convexity of the 50 m band-passed 1 m
   surface).  Only transects with mean LiDAR coverage >= 0.5 are used.
   Measured agreement (this checkout, evidence/corrections/offset_stats.json):
     det_elev_slope strongest crest vs LiDAR crest  MAD 0.29 px (k=3),
     72.5% within 1 px  -> the 100 m slope ridge IS the 1 m scarp crest.
7. Decision rule (preregistered): a record is a CORRECTION CANDIDATE when its
   strongest-crest offset has |median| > 2 px (200 m), sign agreement >= 0.70,
   and >= 8 unambiguous transects.  Emission = dots on the evidence-defined
   trace (the strongest-crest positions of the candidate records' transects),
   restricted to crest points that are off-catalogue (>= 2 px from any known
   fault pixel - on-catalogue dots are masked in scoring and cost alpha each)
   and inside the footprint.

No learned component is used in this lane: the measurement is geometric and the
emission rule is a fixed threshold.  (The brief's Mnih & Hinton ICML 2012
registration/omission-tolerant loss is the prescribed training loss IF a learned
component were trained; it is not invoked here, and this is recorded on the run
card.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.signal import find_peaks

# ---------------------------------------------------------------- constants --
GRID_H, GRID_W = 3730, 3292
PX_M = 100.0                      # pixel size, metres (official)
TRANSECT_HALF_PX = 4.0            # +/-400 m at 100 m px
TRANSECT_STEP_PX = 0.25
N_TRANSECT_SAMPLES = int(round(2 * TRANSECT_HALF_PX / TRANSECT_STEP_PX)) + 1  # 33
TRANSECT_T = np.round(
    np.arange(-TRANSECT_HALF_PX, TRANSECT_HALF_PX + 1e-9, TRANSECT_STEP_PX), 4)

# official 19-band layout (verified against the band tags of training_features.tif)
BAND = {
    "mag_anom": 1, "rtp": 2, "tmi_hg": 3, "geod_2ndinv": 4,
    "iso_grav_anom_slope": 5, "tc": 6, "geod_shearrate": 7, "geod_dilaterate": 8,
    "tmi_vg": 9, "deq_n100a15": 10, "iso_grav_anom_vg": 11, "det_elev": 12,
    "iso_grav_anom": 13, "tmi": 14, "depth_to_base_surf": 15, "ieq_n100a15": 16,
    "cond_surf": 17, "iso_grav_anom_hg": 18, "det_elev_slope": 19,
}
FEATURE_NODATA = np.float32(-3.4028234663852886e38)

# evidence bands measured on every transect, with LiDAR-calibrated gates
# (gate K = prominence / (1.4826 x MAD); calibration numbers in the module docstring)
EVIDENCE_BANDS = {
    "dem_slope": dict(band="det_elev_slope", k_strongest=3.0, k_nearest=4.0),
    "mag_hg":    dict(band="tmi_hg",         k_strongest=2.0, k_nearest=2.0),
}
LIDAR_CREST_BAND = "lapneg_max"     # crest convexity of the 1 m surface
LIDAR_GATE_K = 4.0
LIDAR_MIN_COVERAGE = 0.5

# LiDAR product dequantisation (7GEMSDOE scripts/dem_merge.py QUANT table)
LIDAR_QUANT = {
    "ex_max": (1.5, "sqrt"), "ex_mean": (0.3, "sqrt"), "step_max": (1.0, "sqrt"),
    "lapneg_max": (0.05, "sqrt"), "lappos_max": (0.05, "sqrt"),
    "downface_max": (1.0, "sqrt"), "upface_max": (1.0, "sqrt"),
    "cross_max": (1.0, "sqrt"), "relief": (300.0, "sqrt"),
    "coh100": (1.0, "linear"), "strike": (180.0, "linear"), "valid": (1.0, "linear"),
}
LIDAR_BANDS = {name: i + 1 for i, name in enumerate(LIDAR_QUANT)}

# lane decision constants (preregistered)
MIN_TRANSECTS_PER_RECORD = 8
SIGN_AGREEMENT = 0.70
OFFSET_EMIT_PX = 2.0         # "about two pixels" - the lane's emission threshold
OFF_CATALOGUE_PX = 2.0       # crest points must be >= this far from any known fault
MIN_SHIFT_PX = 1.0           # records shifted by <= this in the holdout are "uncorrected"


# ------------------------------------------------------------------ loading --
def load_labels(path):
    """-> (fault_mask bool, footprint bool).  labels: -1 nodata, 0 no fault, 1 fault."""
    with rasterio.open(path) as src:
        lab = src.read(1)
    footprint = lab != -1
    fault = lab == 1
    return fault, footprint


def load_band(path, band_index):
    """One band of the feature stack as float32 with nodata -> NaN."""
    with rasterio.open(path) as src:
        d = src.read(band_index).astype(np.float32)
    d[d <= FEATURE_NODATA / 2] = np.nan   # sentinel is float32 min; be liberal
    return d


def load_lidar_band(path, name):
    """Dequantise one uint8 channel of the LiDAR scarp product (0 -> NaN)."""
    xmax, how = LIDAR_QUANT[name]
    with rasterio.open(path) as src:
        q = src.read(LIDAR_BANDS[name])
    u = (q.astype(np.float32) - 1.0) / 254.0
    x = (np.sqrt(np.clip(u, 0, 1)) if how == "sqrt" else np.clip(u, 0, 1)) * xmax
    return np.where(q == 0, np.nan, x).astype(np.float32)


# ------------------------------------------------------- orientation (tensor) --
def structure_tensor(mask: np.ndarray, sigma: float = 2.5):
    """Structure tensor of a binary mask on the array grid.

    Returns (perp_row, perp_col, coherence): the unit perpendicular (gradient)
    direction per pixel and the tensor coherence in [0,1].
    Array axes: row = south, col = east.
    """
    m = mask.astype(np.float32)
    gx = ndimage.sobel(m, axis=1, mode="nearest")
    gy = ndimage.sobel(m, axis=0, mode="nearest")
    sxx = ndimage.gaussian_filter(gx * gx, sigma, mode="nearest")
    sxy = ndimage.gaussian_filter(gx * gy, sigma, mode="nearest")
    syy = ndimage.gaussian_filter(gy * gy, sigma, mode="nearest")
    tr = sxx + syy
    det_term = np.sqrt(np.maximum((sxx - syy) ** 2 / 4.0 + sxy ** 2, 0.0))
    lam_plus = tr / 2.0 + det_term
    lam_minus = np.maximum(tr / 2.0 - det_term, 0.0)
    vr = sxy.copy()
    vc = lam_plus - sxx
    norm = np.hypot(vr, vc)
    ok = norm > 1e-12
    vr = np.where(ok, vr / np.where(ok, norm, 1.0), 0.0)
    vc = np.where(ok, vc / np.where(ok, norm, 1.0), 0.0)
    pr = -vc
    pc = vr
    nrm = np.hypot(pr, pc)
    okp = nrm > 1e-12
    pr = np.where(okp, pr / np.where(okp, nrm, 1.0), 0.0)
    pc = np.where(okp, pc / np.where(okp, nrm, 1.0), 0.0)
    coh = np.where(tr > 1e-12, (lam_plus - lam_minus) / np.maximum(tr, 1e-12), 0.0)
    return pr, pc, np.clip(coh, 0.0, 1.0)


def select_transect_centers(fault: np.ndarray, min_dist: int = 2, seed: int = 13):
    """Greedy min-distance subsample of fault pixels (seeded shuffle)."""
    rr, cc = np.nonzero(fault)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(rr))
    rr, cc = rr[order], cc[order]
    taken = np.zeros(fault.shape, bool)
    keep_r, keep_c = [], []
    for r, c in zip(rr, cc):
        if not (min_dist <= r < fault.shape[0] - min_dist
                and min_dist <= c < fault.shape[1] - min_dist):
            continue
        if taken[r - min_dist:r + min_dist + 1, c - min_dist:c + min_dist + 1].any():
            continue
        taken[r, c] = True
        keep_r.append(r)
        keep_c.append(c)
    return np.array(keep_r, int), np.array(keep_c, int)


# ------------------------------------------------------------- transect I/O --
def sample_transects(band: np.ndarray, centers_r, centers_c, perp_r, perp_c):
    """Bilinear sample of `band` on every transect. -> (n_transects, 33) float32."""
    rows = centers_r[:, None] + TRANSECT_T[None, :] * perp_r[:, None]
    cols = centers_c[:, None] + TRANSECT_T[None, :] * perp_c[:, None]
    return ndimage.map_coordinates(band, [rows, cols], order=1, mode="constant",
                                   cval=np.nan).astype(np.float32)


def _parabolic_peak(profile_row, idx):
    """Sub-sample peak refinement. -> fractional index delta in [-1, 1]."""
    if 0 < idx < len(profile_row) - 1:
        y0, y1, y2 = profile_row[idx - 1], profile_row[idx], profile_row[idx + 1]
        denom = y0 - 2.0 * y1 + y2
        if denom < -1e-12:
            delta = 0.5 * (y0 - y2) / denom
            if abs(delta) <= 1.0:
                return delta
    return 0.0


def _noise(profiles):
    med = np.median(profiles, axis=1)
    mad = np.median(np.abs(profiles - med[:, None]), axis=1)
    return med, 1.4826 * mad


def strongest_crest(profiles: np.ndarray, k: float):
    """Dominant crest in the window: global max, gated by prominence >= k x noise.

    Returns (t_star, prominence, ok); t_star in transect px units (-4..+4),
    sub-sample refined.
    """
    n = profiles.shape[0]
    med, noise = _noise(profiles)
    idx = np.argmax(profiles, axis=1)
    rows = np.arange(n)
    peak = profiles[rows, idx]
    prominence = peak - med
    left = profiles[rows, np.maximum(idx - 1, 0)]
    right = profiles[rows, np.minimum(idx + 1, profiles.shape[1] - 1)]
    local_max = (peak >= left) & (peak >= right) & (idx > 0) & (idx < profiles.shape[1] - 1)
    ok = (prominence >= k * np.maximum(noise, 1e-12)) & local_max \
        & np.isfinite(peak) & (noise > 0)
    deltas = np.array([_parabolic_peak(profiles[i], idx[i]) for i in range(n)])
    t_star = TRANSECT_T[idx] + deltas * TRANSECT_STEP_PX
    return t_star.astype(np.float64), prominence.astype(np.float64), ok


def nearest_crest(profiles: np.ndarray, k: float):
    """Prominent crest nearest the catalogue line (t=0); ties -> stronger peak.

    Returns (t_star, prominence, ok, n_peaks).
    """
    n = profiles.shape[0]
    med, noise = _noise(profiles)
    t_out = np.full(n, np.nan)
    prom_out = np.full(n, np.nan)
    ok_out = np.zeros(n, bool)
    npeaks = np.zeros(n, int)
    for i in range(n):
        p = profiles[i]
        pk, _ = find_peaks(p, prominence=k * max(noise[i], 1e-12))
        pk = pk[(pk > 0) & (pk < len(p) - 1)]
        npeaks[i] = len(pk)
        if len(pk) == 0:
            continue
        j = np.argmin(np.abs(TRANSECT_T[pk]))
        t_out[i] = TRANSECT_T[pk[j]] + _parabolic_peak(p, pk[j]) * TRANSECT_STEP_PX
        prom_out[i] = p[pk[j]] - med[i]
        ok_out[i] = True
    return t_out, prom_out, ok_out, npeaks


# ------------------------------------------------------------- record stats --
def record_consistency(offsets, perp_r, perp_c, record_ids,
                       min_transects=MIN_TRANSECTS_PER_RECORD):
    """Per-record robust offset with a consistent sign convention.

    offsets: signed offsets (px) for the record's transects.  Sign alignment:
    each transect's perpendicular is aligned to the record's reference
    perpendicular (orientation is defined modulo 180 deg), flipping the offset
    sign when anti-parallel.
    """
    out = {}
    for rec in np.unique(record_ids):
        sel = record_ids == rec
        if sel.sum() < min_transects:
            continue
        d = offsets[sel].astype(np.float64).copy()
        pr = perp_r[sel]
        pc = perp_c[sel]
        ref = np.argmax(np.abs(pr) + np.abs(pc))
        dot = pr * pr[ref] + pc * pc[ref]
        d[dot < 0] *= -1.0
        med = float(np.median(d))
        mad = float(np.median(np.abs(d - med)))
        frac_pos = float((d > 0).mean())
        agreement = max(frac_pos, 1.0 - frac_pos)
        out[str(rec)] = dict(
            n_transects=int(sel.sum()),
            median_offset_px=med,
            median_offset_m=med * PX_M,
            mad_px=mad,
            sign_agreement=agreement,
            frac_abs_gt_2px=float((np.abs(d) > OFFSET_EMIT_PX).mean()),
            mean_abs_px=float(np.mean(np.abs(d))),
        )
    return out


def _robust(vals):
    vals = np.asarray(vals, float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return dict(n=0)
    med = float(np.median(vals))
    return dict(
        n=int(vals.size),
        median_px=med,
        median_m=med * PX_M,
        mad_px=float(np.median(np.abs(vals - med))),
        mean_px=float(vals.mean()),
        std_px=float(vals.std()),
        pct_abs_le_1px=float((np.abs(vals) <= 1.0).mean()),
        pct_abs_le_2px=float((np.abs(vals) <= 2.0).mean()),
        pct_abs_gt_2px=float((np.abs(vals) > 2.0).mean()),
        pct_abs_gt_3px=float((np.abs(vals) > 3.0).mean()),
        pct_abs_le_4px=float((np.abs(vals) <= 4.0).mean()),
    )


# ------------------------------------------------------------------ driver --
@dataclass
class TransectResult:
    centers_r: np.ndarray
    centers_c: np.ndarray
    perp_r: np.ndarray
    perp_c: np.ndarray
    record_ids: np.ndarray          # str per transect (vector-catalogue record_id)
    # per band x definition: crest position (px), prominence, ok
    crest: dict = field(default_factory=dict)   # (band, 'strongest'|'nearest') -> (t, prom, ok)
    lidar_t_strongest: np.ndarray = None
    lidar_ok_strongest: np.ndarray = None
    lidar_t_nearest: np.ndarray = None
    lidar_ok_nearest: np.ndarray = None
    lidar_coverage: np.ndarray = None

    def t(self, band, definition):
        return self.crest[(band, definition)][0]

    def ok(self, band, definition):
        return self.crest[(band, definition)][2]

    def prom(self, band, definition):
        return self.crest[(band, definition)][1]


def run_measurement(labels_path, features_path, record_npz, lidar_path=None):
    """Full lane measurement. Returns TransectResult."""
    fault, footprint = load_labels(labels_path)
    pr, pc, coh = structure_tensor(fault)

    cr, cc = select_transect_centers(fault, min_dist=2)
    prc = pr[cr, cc]
    pcc = pc[cr, cc]
    keep = (coh[cr, cc] > 0.3) & (np.hypot(prc, pcc) > 0.5)
    cr, cc, prc, pcc = cr[keep], cc[keep], prc[keep], pcc[keep]

    # footprint gate: the whole transect must lie inside the footprint
    rows = cr[:, None] + TRANSECT_T[None, :] * prc[:, None]
    cols = cc[:, None] + TRANSECT_T[None, :] * pcc[:, None]
    r0 = np.clip(np.round(rows).astype(int), 0, GRID_H - 1)
    c0 = np.clip(np.round(cols).astype(int), 0, GRID_W - 1)
    inside = footprint[r0, c0].all(axis=1)
    cr, cc, prc, pcc = cr[inside], cc[inside], prc[inside], pcc[inside]

    # record ids: nearest vector segment's record_id per fault pixel
    d = np.load(record_npz, allow_pickle=True)
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([d["row"], d["col"]]))
    _, idx = tree.query(np.column_stack([cr, cc]), k=1)
    rec = d["record"][idx].astype(str)

    res = TransectResult(centers_r=cr, centers_c=cc, perp_r=prc, perp_c=pcc,
                         record_ids=rec)

    # ---- evidence bands ------------------------------------------------------
    for name, spec in EVIDENCE_BANDS.items():
        band = load_band(features_path, BAND[spec["band"]])
        prof = sample_transects(band, cr, cc, prc, pcc)
        t_s, prom_s, ok_s = strongest_crest(prof, spec["k_strongest"])
        t_n, prom_n, ok_n, _ = nearest_crest(prof, spec["k_nearest"])
        res.crest[(name, "strongest")] = (t_s, prom_s, ok_s)
        res.crest[(name, "nearest")] = (t_n, prom_n, ok_n)

    # ---- LiDAR calibration ---------------------------------------------------
    if lidar_path and Path(lidar_path).exists():
        lapneg = load_lidar_band(lidar_path, LIDAR_CREST_BAND)
        valid = load_lidar_band(lidar_path, "valid")
        prof_l = sample_transects(lapneg, cr, cc, prc, pcc)
        prof_v = sample_transects(valid, cr, cc, prc, pcc)
        with np.errstate(invalid="ignore"):
            cov = np.nanmean(prof_v, axis=1)
        res.lidar_coverage = cov
        t_s, _, ok_s = strongest_crest(prof_l, LIDAR_GATE_K)
        t_n, _, ok_n, _ = nearest_crest(prof_l, LIDAR_GATE_K)
        res.lidar_t_strongest = t_s
        res.lidar_ok_strongest = ok_s & (cov >= LIDAR_MIN_COVERAGE)
        res.lidar_t_nearest = t_n
        res.lidar_ok_nearest = ok_n & (cov >= LIDAR_MIN_COVERAGE)
    return res


def summarise(res: TransectResult, fault: np.ndarray):
    """Robust statistics for the offset histogram + decision inputs."""
    stats = dict(
        grid=dict(height=GRID_H, width=GRID_W, px_m=PX_M),
        catalogue_fault_px=int(fault.sum()),
        n_transects=int(len(res.centers_r)),
        n_records=int(len(np.unique(res.record_ids))),
        transect_half_width_m=TRANSECT_HALF_PX * PX_M,
        bands={},
        records={},
        lidar_calibration={},
    )
    for name in EVIDENCE_BANDS:
        for definition in ("strongest", "nearest"):
            ok = res.ok(name, definition)
            t = res.t(name, definition)
            stats["bands"][f"{name}_{definition}"] = dict(
                gate_k=(EVIDENCE_BANDS[name]["k_strongest"] if definition == "strongest"
                        else EVIDENCE_BANDS[name]["k_nearest"]),
                n_unambiguous=int(ok.sum()),
                offset=_robust(t[ok]),
            )
            rec = record_consistency(t[ok], res.perp_r[ok], res.perp_c[ok],
                                     res.record_ids[ok])
            stats["records"][f"{name}_{definition}"] = _record_rollup(rec)
    if res.lidar_t_strongest is not None:
        lok_s = res.lidar_ok_strongest
        lok_n = res.lidar_ok_nearest
        stats["lidar_calibration"] = dict(
            n_transects_strongest=int(lok_s.sum()),
            n_transects_nearest=int(lok_n.sum()),
            coverage_mean=float(np.nanmean(res.lidar_coverage[lok_s])),
            offset_strongest=_robust(res.lidar_t_strongest[lok_s]),
            offset_nearest=_robust(res.lidar_t_nearest[lok_n]),
        )
        for name in EVIDENCE_BANDS:
            for definition in ("strongest", "nearest"):
                both = lok_s & res.ok(name, definition)
                if both.sum() >= 30:
                    diff = res.t(name, definition)[both] - res.lidar_t_strongest[both]
                    stats["lidar_calibration"][
                        f"agreement_{name}_{definition}_vs_lidar_strongest"] = _robust(diff)
    return stats


def _record_rollup(rec: dict):
    if not rec:
        return dict(n_records=0)
    med = np.array([v["median_offset_px"] for v in rec.values()])
    agr = np.array([v["sign_agreement"] for v in rec.values()])
    ntr = np.array([v["n_transects"] for v in rec.values()])
    consistent = (np.abs(med) > OFFSET_EMIT_PX) & (agr >= SIGN_AGREEMENT) \
        & (ntr >= MIN_TRANSECTS_PER_RECORD)
    sel = ntr >= MIN_TRANSECTS_PER_RECORD
    return dict(
        n_records=int(len(rec)),
        n_records_sampled=int(sel.sum()),
        n_consistent_offset_gt_2px=int(consistent.sum()),
        frac_consistent_offset_gt_2px=float(consistent.sum() / max(sel.sum(), 1)),
        median_abs_offset_px=float(np.median(np.abs(med[sel]))) if sel.any() else None,
        records_offset_gt_2px=int((np.abs(med) > OFFSET_EMIT_PX).sum()),
        records_offset_gt_3px=int((np.abs(med) > 3.0).sum()),
    )


# ------------------------------------------------------------- emission ------
def correction_candidates(res: TransectResult, band="dem_slope",
                          definition="strongest"):
    """Records whose consistent offset exceeds ~2 px (the lane's emission set)."""
    ok = res.ok(band, definition)
    t = res.t(band, definition)
    rec = record_consistency(t[ok], res.perp_r[ok], res.perp_c[ok],
                             res.record_ids[ok])
    return {sid for sid, v in rec.items()
            if abs(v["median_offset_px"]) > OFFSET_EMIT_PX
            and v["sign_agreement"] >= SIGN_AGREEMENT
            and v["n_transects"] >= MIN_TRANSECTS_PER_RECORD}


def record_crest_line(res: TransectResult, record_id, band="dem_slope",
                      definition="strongest"):
    """Connected evidence-defined trace (crest line) of one record, in px coords.

    Orders the record's transects along the trace (projection onto the trace
    direction) and connects consecutive crest positions with straight segments,
    so the emission is the continuous evidence-defined trace, not just the
    transect sample points.  Returns (rows float, cols float) or None.
    """
    ok = res.ok(band, definition)
    sel = np.nonzero(ok & (res.record_ids == record_id))[0]
    if sel.size == 0:
        return None
    pr = res.perp_r[sel]
    pc = res.perp_c[sel]
    ref = np.argmax(np.abs(pr) + np.abs(pc))
    tr = -pr[ref]          # trace direction = perpendicular of the perpendicular
    tc = pc[ref]
    s = res.centers_r[sel] * tr + res.centers_c[sel] * tc
    order = np.argsort(s)
    sel = sel[order]
    t = res.t(band, definition)[sel]
    crest_r = res.centers_r[sel] + t * pr[order]
    crest_c = res.centers_c[sel] + t * pc[order]
    pts_r = [crest_r[0]]
    pts_c = [crest_c[0]]
    for i in range(1, len(sel)):
        r0, c0 = pts_r[-1], pts_c[-1]
        r1, c1 = crest_r[i], crest_c[i]
        n = int(max(abs(r1 - r0), abs(c1 - c0))) + 1
        for tt in np.linspace(0, 1, n + 1)[1:]:
            pts_r.append(r0 + (r1 - r0) * tt)
            pts_c.append(c0 + (c1 - c0) * tt)
    return np.array(pts_r), np.array(pts_c)


def build_emission(res: TransectResult, fault, footprint,
                   candidates=None, band="dem_slope", definition="strongest",
                   off_catalogue_px=OFF_CATALOGUE_PX, value=1.0):
    """Dots on the evidence-defined trace.

    For each candidate record, take its connected crest line (the evidence-
    defined trace), snap to pixels, and keep points that are inside the
    footprint and not ON any known fault pixel (known-fault pixels are masked
    pixel-exactly in scoring: dots there earn nothing and cost alpha each).

    candidates=None -> every record with an unambiguous crest (the no-gate arm).
    Returns (raster float32 with NaN outside footprint, n_dots, per-record counts).
    """
    ok = res.ok(band, definition)
    if candidates is None:
        candidates = set(np.unique(res.record_ids[ok]).tolist())
    dist_cat = ndimage.distance_transform_edt(~fault)
    out = np.full(fault.shape, np.nan, np.float32)
    per_record = {}
    for sid in sorted(candidates):
        line = record_crest_line(res, sid, band, definition)
        if line is None:
            per_record[sid] = 0
            continue
        ri = np.clip(np.round(line[0]).astype(int), 0, GRID_H - 1)
        ci = np.clip(np.round(line[1]).astype(int), 0, GRID_W - 1)
        good = footprint[ri, ci] & (dist_cat[ri, ci] >= off_catalogue_px)
        ri, ci = ri[good], ci[good]
        if ri.size == 0:
            per_record[sid] = 0
            continue
        out[ri, ci] = value
        per_record[sid] = int(ri.size)
    n_dots = int(np.count_nonzero(np.nan_to_num(out)))
    return out, n_dots, per_record


def transect_table(res: TransectResult):
    out = dict(
        row=res.centers_r.astype(int), col=res.centers_c.astype(int),
        record=res.record_ids, perp_r=res.perp_r, perp_c=res.perp_c,
    )
    for (name, definition), (t, prom, ok) in res.crest.items():
        out[f"{name}_{definition}_px"] = t
        out[f"{name}_{definition}_prom"] = prom
        out[f"{name}_{definition}_ok"] = ok
    if res.lidar_t_strongest is not None:
        out["lidar_strongest_px"] = res.lidar_t_strongest
        out["lidar_strongest_ok"] = res.lidar_ok_strongest
        out["lidar_nearest_px"] = res.lidar_t_nearest
        out["lidar_nearest_ok"] = res.lidar_ok_nearest
        out["lidar_coverage"] = res.lidar_coverage
    return out


def record_table(res: TransectResult, band="dem_slope", definition="strongest"):
    ok = res.ok(band, definition)
    t = res.t(band, definition)
    rec = record_consistency(t[ok], res.perp_r[ok], res.perp_c[ok],
                             res.record_ids[ok])
    rows = [dict(record=sid, **v) for sid, v in rec.items()]
    return rows
