"""Regression tests for the footprint-edge defect class (IR-56-020).

The transforms zero-fill outside the footprint before differencing/smoothing.  A shared tool
that does not mask the resulting edge response turns the data rim into a fake feature: on the
competition footprint, 56 % of scarp_step's top-25,000 cells landed on a 2 px rim band, and
rank01 then re-ranked NaN-within-valid cells into the top bin.  Every test here fails on the
pre-fix code.
"""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems56 import transform as T  # noqa: E402


def _disc_mask(h=96, w=96, r=34):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((yy - h // 2) ** 2 + (xx - w // 2) ** 2) <= r * r


def test_scarp_step_constant_field_has_no_rim_artifact():
    valid = _disc_mask()
    a = np.full(valid.shape, 10.0, np.float32)
    resp, _ = T.scarp_step(a, valid, half_width_m=200.0, persist_m=1000.0)
    finite = resp[np.isfinite(resp)]
    assert finite.size > 0, "interior must still respond (0 for a constant, but evaluated)"
    # A constant field is a step of height 0 *everywhere*, so any positive rim response is fake.
    assert float(np.nanmax(np.abs(resp))) < 1e-5, (
        f"footprint rim produced a fake step: max {np.nanmax(resp)}")


def test_scarp_step_still_finds_an_interior_step():
    valid = _disc_mask()
    a = np.zeros(valid.shape, np.float32)
    a[:, 48:60] = 10.0                          # a 12 px band = an interior "horst"
    resp, _ = T.scarp_step(a, valid, half_width_m=200.0, persist_m=1000.0)
    band = resp[20:76, 48]
    off = resp[20:76, 20]
    assert np.isfinite(band).any() and np.nanmax(band[np.isfinite(band)]) > 1.0, (
        "the interior step must still be detected after edge masking")
    if np.isfinite(off).any():
        assert np.nanmax(np.abs(off)) < 1e-5, "no step where the field is flat"


def test_rank01_nan_inside_valid_stays_nan():
    valid = np.ones((32, 32), bool)
    a = np.arange(32 * 32, dtype=np.float32).reshape(32, 32)
    a[10:12, 10:12] = np.nan                    # transform-rejected cells inside the footprint
    r = T.rank01(a, valid)
    assert np.isnan(r[10, 10]), "NaN-inside-valid must stay NaN, not become a top rank"
    finite = r[np.isfinite(r)]
    assert finite.size == 32 * 32 - 4
    assert np.nanmax(r) <= 1.0
    # the true maximum of the finite data must be (near) 1.0 and located at index max
    ys, xs = np.nonzero(a == np.nanmax(a))
    assert r[ys[0], xs[0]] >= 0.99


def test_rank01_without_nan_unchanged():
    valid = np.ones((16, 16), bool)
    a = np.random.default_rng(0).normal(size=(16, 16)).astype(np.float32)
    r = T.rank01(a, valid)
    assert np.isfinite(r).all()
    assert 0.0 < r.min() and r.max() <= 1.0


def test_gradient_magnitude_rim_masked():
    valid = _disc_mask()
    a = np.full(valid.shape, 7.0, np.float32)
    g = T.gradient_magnitude(a, valid)
    # interior gradient of a constant is 0
    yy, xx = np.mgrid[0:96, 0:96]
    core = ((yy - 48) ** 2 + (xx - 48) ** 2) <= 20 * 20
    assert np.nanmax(np.abs(g[core])) < 1e-5
    # rim band must be NaN (pre-fix it measured the data edge against the zero fill)
    edge = np.asarray(valid, bool) & (T._edge_band(valid, 2.0))
    assert np.isnan(g[edge]).all()


def test_hessian_line_rim_masked():
    valid = _disc_mask()
    a = np.full(valid.shape, 7.0, np.float32)
    h = T.hessian_line(a, valid, sigma_m=300.0)      # sigma = 3 px
    band = T._edge_band(valid, 3.0 * 3.0 + 1.0)
    assert np.isnan(h[band & valid]).all(), "3 sigma edge band must be NaN"
    core = np.asarray(valid, bool) & ~T._edge_band(valid, 12.0)
    assert np.nanmax(np.abs(h[core])) < 1e-4, "constant interior must have ~zero line response"
