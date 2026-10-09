"""Lane unit tests: src/corrections.py (corrections lane machinery).

Run: python -m pytest tests/test_corrections_lane.py -q
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import corrections as C  # noqa: E402


# --------------------------------------------------------------- crest finding
def test_strongest_crest_finds_the_peak():
    rng = np.random.default_rng(0)
    t = C.TRANSECT_T
    prof = rng.normal(0.0, 0.05, (3, len(t))).astype(np.float32)
    prof[:, 16] += 5.0         # a sharp peak at t=0 (index 16 of 33)
    prof[:, 10] += 1.0
    prof[:, 22] += 1.0
    t_star, prom, ok = C.strongest_crest(prof, k=3.0)
    assert ok.all()
    assert np.allclose(t_star, 0.0, atol=0.26)
    assert prom.max() > 3.0


def test_strongest_crest_rejects_flat_profiles():
    prof = np.ones((4, len(C.TRANSECT_T)), np.float32)
    _, _, ok = C.strongest_crest(prof, k=3.0)
    assert not ok.any()          # zero noise -> gate fails closed


def test_nearest_crest_picks_closest_peak_not_strongest():
    t = C.TRANSECT_T
    prof = np.full((1, len(t)), 0.01, np.float32)   # tiny floor, no noise peaks
    prof[0, 16] += 2.0           # near peak at t=0
    prof[0, 28] += 9.0           # stronger peak far away (t=+3)
    t_star, _, ok, npeaks = C.nearest_crest(prof, k=2.0)
    assert ok[0]
    assert abs(t_star[0]) < 0.3          # nearest, not strongest
    assert npeaks[0] == 2


def test_parabolic_peak_refinement():
    p = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    assert C._parabolic_peak(p, 2) == pytest.approx(0.0)
    p2 = np.array([0.0, 1.0, 2.0, 1.5, 0.0])
    # delta = 0.5*(y0 - y2) / (y0 - 2*y1 + y2); peak shifts toward the higher side
    assert C._parabolic_peak(p2, 2) == pytest.approx(0.5 * (1.0 - 1.5) / (1.0 - 4.0 + 1.5))


# ------------------------------------------------------------ record consistency
def _fake_transects(n, offset, jitter=0.0, seed=0):
    rng = np.random.default_rng(seed)
    rec = np.array(["R1"] * n)
    perp_r = np.zeros(n)
    perp_c = np.ones(n)
    t = np.full(n, offset) + rng.normal(0, jitter, n)
    return t, perp_r, perp_c, rec


def test_record_consistency_median_and_agreement():
    t, pr, pc, rec = _fake_transects(20, 3.0, jitter=0.1)
    seg = C.record_consistency(t, pr, pc, rec)
    assert set(seg) == {"R1"}
    v = seg["R1"]
    assert v["n_transects"] == 20
    assert v["median_offset_px"] == pytest.approx(3.0, abs=0.2)
    assert v["sign_agreement"] == pytest.approx(1.0)


def test_record_consistency_sign_alignment_flips_antiparallel():
    # Half the transects carry the opposite perpendicular.  The same PHYSICAL
    # crest (3 px east of the trace) then has t=+3 along +col and t=-3 along
    # -col; after sign alignment all offsets must agree in magnitude and sign.
    n = 20
    t = np.full(n, 3.0)
    pr = np.zeros(n)
    pc = np.ones(n)
    pc[::2] = -1.0               # antiparallel perpendiculars
    t[::2] = -3.0                # same physical crest, opposite frame
    rec = np.array(["R1"] * n)
    seg = C.record_consistency(t, pr, pc, rec)
    assert abs(seg["R1"]["median_offset_px"]) == pytest.approx(3.0)
    assert seg["R1"]["sign_agreement"] == pytest.approx(1.0)
    # inconsistent physical crests (half east, half west) must NOT align
    t_bad = np.full(n, 3.0)
    seg_bad = C.record_consistency(t_bad, pr, pc, rec)
    assert seg_bad["R1"]["sign_agreement"] == pytest.approx(0.5)


def test_record_consistency_requires_min_transects():
    t, pr, pc, rec = _fake_transects(5, 3.0)
    assert C.record_consistency(t, pr, pc, rec) == {}


# ------------------------------------------------------------------- emission
class _FakeRes:
    """Minimal TransectResult stand-in for build_emission / crest_line."""

    def __init__(self, record_ids, t, perp_r, perp_c, centers_r, centers_c, ok=None,
                 mag_t=None, mag_ok=None):
        n = len(record_ids)
        self.record_ids = np.array(record_ids)
        self.perp_r = np.asarray(perp_r, float)
        self.perp_c = np.asarray(perp_c, float)
        self.centers_r = np.asarray(centers_r, float)
        self.centers_c = np.asarray(centers_c, float)
        self.crest = {("dem_slope", "strongest"): (np.asarray(t, float),
                                                   np.ones(n), np.asarray(ok, bool))}
        if mag_t is not None:
            self.crest[("mag_hg", "strongest")] = (np.asarray(mag_t, float),
                                                   np.ones(n),
                                                   np.asarray(mag_ok, bool))

    def ok(self, band, definition):
        return self.crest[(band, definition)][2]

    def t(self, band, definition):
        return self.crest[(band, definition)][0]


def test_build_emission_off_catalogue_and_inside_footprint():
    H, W = C.GRID_H, C.GRID_W
    fault = np.zeros((H, W), bool)
    footprint = np.zeros((H, W), bool)
    # a vertical catalogue trace at col 100, rows 500..560
    fault[500:561, 100] = True
    footprint[400:700, 50:150] = True
    # transects on the trace, perpendicular pointing +col, crest offset +3 px
    n = 30
    res = _FakeRes(
        record_ids=["R1"] * n,
        t=np.full(n, 3.0),
        perp_r=np.zeros(n), perp_c=np.ones(n),
        centers_r=np.linspace(505, 555, n), centers_c=np.full(n, 100.0),
        ok=np.ones(n, bool))
    out, n_dots, per_rec = C.build_emission(res, fault, footprint,
                                            candidates={"R1"})
    assert n_dots > 0
    assert per_rec["R1"] >= n_dots          # per-record count is pre-dedupe
    # every dot is off the catalogue and inside the footprint
    dots = np.nan_to_num(out) > 0
    assert not (dots & fault).any()
    assert (dots & ~footprint).sum() == 0
    # dots sit ~3 px east of the trace (col ~103)
    cols = np.nonzero(dots.any(axis=0))[0]
    assert cols.min() >= 102 and cols.max() <= 104


def test_build_emission_respects_candidate_gate():
    H, W = C.GRID_H, C.GRID_W
    fault = np.zeros((H, W), bool)
    footprint = np.ones((H, W), bool)
    fault[500:561, 100] = True
    n = 10
    res = _FakeRes(["R1"] * n, np.full(n, 3.0), np.zeros(n), np.ones(n),
                   np.linspace(505, 555, n), np.full(n, 100.0), np.ones(n, bool))
    out_gated, n_gated, _ = C.build_emission(res, fault, footprint,
                                             candidates={"OTHER"})
    assert n_gated == 0                       # gate excludes the record
    out_all, n_all, _ = C.build_emission(res, fault, footprint, candidates=None)
    assert n_all > 0                          # no gate -> emits


def test_correction_candidates_threshold():
    # |median| > 2 px, agreement >= 0.7, n >= 8
    n = 12
    res = _FakeRes(["BIG"] * n, np.full(n, 3.0), np.zeros(n), np.ones(n),
                   np.arange(n) * 2.0 + 500, np.full(n, 100.0), np.ones(n, bool))
    assert C.correction_candidates(res) == {"BIG"}
    res2 = _FakeRes(["SMALL"] * n, np.full(n, 1.0), np.zeros(n), np.ones(n),
                    np.arange(n) * 2.0 + 500, np.full(n, 100.0), np.ones(n, bool))
    assert C.correction_candidates(res2) == set()


# ------------------------------------------------------------------ geometry
def test_structure_tensor_perpendicular_of_horizontal_trace():
    mask = np.zeros((40, 40), bool)
    mask[20, 5:35] = True                     # horizontal trace (constant row)
    pr, pc, coh = C.structure_tensor(mask)
    # perpendicular of a horizontal trace is vertical (row direction)
    assert abs(pr[20, 20]) > 0.9
    assert abs(pc[20, 20]) < 0.1
    assert coh[20, 20] > 0.5


def test_select_transect_centers_min_distance():
    fault = np.zeros((30, 30), bool)
    fault[10:20, 10:20] = True
    r, c = C.select_transect_centers(fault, min_dist=2, seed=1)
    assert len(r) > 0
    d = np.sqrt((r[:, None] - r[None, :]) ** 2 + (c[:, None] - c[None, :]) ** 2)
    d[d == 0] = np.inf
    assert d.min() >= 2


# ---------------------------------------------------- round 3: twin-family gate
def _twin_res(dem_t, mag_t, mag_ok=None, perp_c=None):
    """One record 'R1' with n transects; dem all ok; mag offsets/ok as given."""
    n = len(dem_t)
    perp_c = np.ones(n) if perp_c is None else np.asarray(perp_c, float)
    if mag_ok is None:
        mag_ok = np.ones(n, bool)
    return _FakeRes(["R1"] * n, np.asarray(dem_t, float), np.zeros(n), perp_c,
                    np.arange(n) * 2.0 + 500, np.full(n, 100.0), np.ones(n, bool),
                    mag_t=np.asarray(mag_t, float), mag_ok=np.asarray(mag_ok, bool))


def test_twin_family_sign_concordance():
    # dem +3 px, mag +1.5 px -> corroborated
    r = _twin_res([3.0] * 12, [1.5] * 12)
    assert set(C.mag_corroborated_candidates(r)) == {"R1"}
    # mag opposite sign -> dropped
    r = _twin_res([3.0] * 12, [-1.5] * 12)
    assert C.mag_corroborated_candidates(r) == {}
    # |mag| below the 1 px floor -> dropped
    r = _twin_res([3.0] * 12, [0.5] * 12)
    assert C.mag_corroborated_candidates(r) == {}
    # too few qualified mag transects -> dropped
    ok = np.zeros(12, bool)
    ok[:2] = True
    r = _twin_res([3.0] * 12, [1.5] * 12, mag_ok=ok)
    assert C.mag_corroborated_candidates(r) == {}


def test_twin_family_is_subset_of_round1_gate():
    # a record failing the round-1 gate cannot enter the twin set even if mag agrees
    r = _twin_res([1.0] * 12, [1.5] * 12)
    assert C.correction_candidates(r) == set()
    assert C.mag_corroborated_candidates(r) == {}


def test_twin_family_shared_perpendicular_reference():
    """The sign-convention trap (round 3, record 1514 class).

    One record, 12 transects sharing ONE perpendicular table (the real
    TransectResult layout): transects 0..8 point +col, transects 9..11 point
    -col (a local flip of the orientation, defined modulo 180 deg).  Both
    families see the SAME physical displacement (east): along a +col perp the
    signed offset reads +3, along a -col perp it reads -3.

    The mag family is only qualified (ok) on transects 8..11 - a subset
    dominated by flipped perpendiculars.  The RAW mag median over [-3, -3, -3,
    +3] is -3 (would wrongly DISAGREE with the dem median +3); after realignment
    to the shared reference the mag median is +3 and the record is
    corroborated.
    """
    n = 12
    perp_c = np.array([1.0] * 9 + [-1.0] * 3)
    dem_t = [3.0] * 9 + [-3.0] * 3          # east everywhere in world coords
    mag_t = [-3.0] * 12                     # east everywhere in world coords
    mag_t[8] = 3.0
    mag_ok = np.zeros(n, bool)
    mag_ok[8:] = True
    r = _FakeRes(["R1"] * n, np.asarray(dem_t, float), np.zeros(n), perp_c,
                 np.arange(n) * 2.0 + 500, np.full(n, 100.0), np.ones(n, bool),
                 mag_t=np.asarray(mag_t, float), mag_ok=mag_ok)
    # sanity: the raw (unaligned) mag median over the ok subset is negative
    assert np.median(np.asarray(mag_t)[mag_ok]) < 0
    out = C.mag_corroborated_candidates(r)
    assert set(out) == {"R1"}
    assert out["R1"]["dem_median_px"] > 0 and out["R1"]["mag_median_px"] > 0
