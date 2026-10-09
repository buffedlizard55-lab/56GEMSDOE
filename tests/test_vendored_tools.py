"""Tests for the vendored template tools as used by this lane.

Covers: the official metric's worked example, the fail-loud submission writer
round-trip, template conformance of a conformed raster, and the repository
validator on the SHIPPED submission GeoTIFF (skipped if the file is absent).

Run: python -m pytest tests/test_vendored_tools.py -q
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import metrics as M  # noqa: E402
import submission_io as S  # noqa: E402

def _has_nan(path):
    with rasterio.open(path) as src:
        return bool(np.isnan(src.read(1)).any())


SHIPPED = (sorted((ROOT / "docs" / "downloads").glob("h57-corr-*.tif"))
           or sorted((ROOT / "docs" / "downloads").glob("gems56-corr-*-nan.tif")))


# ------------------------------------------------------------------- metric
def test_official_worked_example():
    # Problem page "Scoring example": TP_w=3.00, FP_w=1.89, FN_w=2.00 -> TI_w = 0.60
    # (|G| = TP_w + FN_w = 5 px).  3.00/(3.00 + 0.2*1.89 + 0.8*2.00) = 0.6027, which
    # the page rounds to 0.60.
    v = 3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00)
    assert round(v, 2) == 0.60
    assert abs(M.dti_bounds(3.00, 1.89, 5) - 0.6027) < 2e-4


def test_metric_identity_on_a_small_case():
    rng = np.random.default_rng(0)
    gt = np.zeros((60, 60))
    gt[30, 10:20] = 1.0
    pred = np.zeros((60, 60))
    pred[30, 12:18] = 1.0
    ctx = M.GtContext(gt)
    dti, (tp, fp, fn) = ctx.score(pred, return_components=True)
    manual = tp / (tp + 0.2 * fp + 0.8 * fn)
    assert dti == pytest.approx(manual, abs=1e-6)  # float32 credit internally
    assert tp + fn == pytest.approx(ctx.n_gt)


# ----------------------------------------------------------- writer round-trip
def test_writer_round_trip_and_conformance(tmp_path):
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as src:
        template = src.read(1)
        prof = src.profile.copy()
    arr = np.zeros(template.shape, np.float32)
    # place dots inside the template's valid (scored) region: the fail-loud
    # writer correctly refuses an emission that conforms away to all zeros
    vr, vc = np.nonzero(np.isfinite(template))
    r0, c0 = int(vr[len(vr) // 2]), int(vc[len(vc) // 2])
    arr[r0:r0 + 10, c0:c0 + 10] = 1.0
    arr, stats = S.conform_to_template(arr, template)
    # the all-zero input is finite everywhere, so conformance masks the outside
    # region to NaN; the dots inside the valid region must survive untouched
    assert stats["filled_inside"] == 0
    assert int((arr > 0).sum()) == 100
    out = tmp_path / "sub.tif"
    clean = S.clean_profile(prof, height=arr.shape[0], width=arr.shape[1],
                            crs="EPSG:32611", transform=prof["transform"],
                            dtype="float32", nodata=float("nan"))
    info = S.write_submission(out, arr, clean)
    assert info["nonzero_px"] == 100
    with rasterio.open(out) as src:
        back = src.read(1)
        assert src.nodata is not None and np.isnan(src.nodata)
        assert str(src.crs) == "EPSG:32611"
    assert np.array_equal(np.nan_to_num(back), np.nan_to_num(arr))
    # conformance findings accept its own output
    with rasterio.open(out) as src:
        back_arr = src.read(1)
    findings = S.conformance_findings(back_arr, template)
    assert findings["conformant"], findings


def test_writer_refuses_empty_emission(tmp_path):
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as src:
        template = src.read(1)
        prof = src.profile.copy()
    arr = np.zeros(template.shape, np.float32)
    arr, _ = S.conform_to_template(arr, template)
    clean = S.clean_profile(prof, height=arr.shape[0], width=arr.shape[1],
                            crs="EPSG:32611", transform=prof["transform"],
                            dtype="float32", nodata=float("nan"))
    with pytest.raises(Exception):
        S.write_submission(tmp_path / "empty.tif", arr, clean)


# ------------------------------------------------------- the shipped submission
# POLICY NOTE (IR-57-006). Two export policies coexist in this template and they are mutually
# exclusive on one file: the legacy "NaN outside the footprint + GDAL_NODATA=nan" policy of the
# gems56-corr-* run, and the all-finite policy that gems56.gates.write_geotiff/format_report
# enforce (zeros outside, no nodata tag). The public spec permits either ("data outside bounds is
# null or NaN"), and the all-finite form is what the current H57 file ships, because the live form
# rejected a NaN-bearing upload with "Predicted values must be in range [0, 1]". These tests
# therefore assert the policy the file declares, and assert the parts that are common to both.
ALL_FINITE = bool(SHIPPED) and not _has_nan(SHIPPED[-1])


@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
@pytest.mark.skipif(ALL_FINITE, reason="legacy NaN-outside validator does not apply to an all-finite export")
def test_shipped_submission_passes_validator():
    tif = SHIPPED[-1]
    r = subprocess.run([sys.executable, "scripts/validate_submission.py",
                        "--pred", str(tif),
                        "--sample", "data/sample_submission.tif",
                        "--train", "data/training_features.tif"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
@pytest.mark.skipif(ALL_FINITE, reason="template conformance encodes the NaN-outside policy")
def test_shipped_submission_is_template_conformant():
    tif = SHIPPED[-1]
    r = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant",
                        str(tif), "--sample", "data/sample_submission.tif"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
def test_shipped_submission_passes_all_finite_gate():
    """The gate that actually governs the shipped file: gems56.gates.format_report."""
    sys.path.insert(0, str(ROOT / "src"))
    from gems56 import gates
    rep = gates.format_report(SHIPPED[-1], ROOT / "data" / "grid" / "sample_submission.tif")
    assert rep["ok"], rep["problems"]
    assert rep["n_nan"] == 0 and rep["min"] >= 0.0 and rep["max"] <= 1.0
    assert rep["bands"] == 1 and rep["dtype"] == "float32"


@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
def test_shipped_submission_readback():
    tif = SHIPPED[-1]
    with rasterio.open(tif) as src:
        a = src.read(1)
        assert src.dtypes[0] == "float32" and src.count == 1
        assert str(src.crs) == "EPSG:32611"
        assert (src.height, src.width) == (3730, 3292)
        if ALL_FINITE:
            assert src.nodata is None or np.isnan(src.nodata)
        else:
            assert src.nodata is not None and np.isnan(src.nodata)
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as src:
        tpl = src.read(1)
    # the catalogue as the bridge places it (data/labels.tif is the login-gated name and is not
    # present in this sandbox; data/grid/existing_faults.tif is the hash-pinned same raster)
    cat_path = ROOT / "data" / "grid" / "existing_faults.tif"
    with rasterio.open(cat_path) as src:
        fault = src.read(1) == 1
    fin = np.isfinite(a)
    if ALL_FINITE:
        assert fin.all()                            # every cell finite: no reader can see NaN
        assert not np.any(a[~np.isfinite(tpl)] > 0)  # no positive mass outside the sample footprint
    else:
        assert (fin == np.isfinite(tpl)).all()      # NaN mask matches the sample
    assert np.isfinite(a[fin]).all()                # no NaN inside the footprint
    assert a[fin].min() >= 0.0 and a[fin].max() <= 1.0
    assert (a[fault] == 0).all()                    # no dots on the catalogue

    assert (a > 0).sum() > 0
