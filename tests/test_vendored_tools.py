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

SHIPPED = sorted((ROOT / "docs" / "downloads").glob("gems56-corr-*-nan.tif"))


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
@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
def test_shipped_submission_passes_validator():
    tif = SHIPPED[-1]
    command = [sys.executable, "scripts/validate_submission.py",
               "--pred", str(tif), "--sample", "data/sample_submission.tif"]
    train = ROOT / "data" / "training_features.tif"
    if train.is_file():
        command.extend(["--train", str(train)])
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
def test_shipped_submission_is_template_conformant():
    tif = SHIPPED[-1]
    r = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant",
                        str(tif), "--sample", "data/sample_submission.tif"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not SHIPPED, reason="shipped submission GeoTIFF not present")
def test_shipped_submission_readback():
    import corrections as C
    tif = SHIPPED[-1]
    with rasterio.open(tif) as src:
        a = src.read(1)
        assert src.dtypes[0] == "float32" and src.count == 1
        assert str(src.crs) == "EPSG:32611"
        assert (src.height, src.width) == (3730, 3292)
        assert src.nodata is not None and np.isnan(src.nodata)
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as src:
        tpl = src.read(1)
    fault, _ = C.load_labels(ROOT / "data" / "labels.tif")
    fin = np.isfinite(a)
    assert (fin == np.isfinite(tpl)).all()          # NaN mask matches the sample
    assert np.isfinite(a[fin]).all()                # no NaN inside the footprint
    assert a[fin].min() >= 0.0 and a[fin].max() <= 1.0
    assert (a[fault] == 0).all()                    # no dots on the catalogue
    assert (a > 0).sum() > 0
