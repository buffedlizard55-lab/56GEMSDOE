import numpy as np
import pytest
import rasterio

from gems.submission import (REF_CRS, REF_HEIGHT, REF_TRANSFORM, REF_WIDTH,
                             validate_submission, write_submission)


def _write_raw(path, arr, crs=REF_CRS, nodata=None, dtype="float32"):
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0],
                       count=1, dtype=dtype, crs=crs, transform=REF_TRANSFORM, nodata=nodata) as dst:
        dst.write(arr.astype(dtype), 1)


def test_valid_file_passes(tmp_path):
    p = tmp_path / "ok.tif"
    v = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    v[100, 100:110] = 0.5
    write_submission(str(p), v)
    rep = validate_submission(str(p))
    assert rep.ok, rep.problems
    assert rep.n_positive == 10
    assert rep.vmax == pytest.approx(0.5)


def test_writer_refuses_nan_and_out_of_range(tmp_path):
    v = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    v[0, 0] = np.nan
    with pytest.raises(ValueError):
        write_submission(str(tmp_path / "a.tif"), v)
    v[0, 0] = 1.2
    with pytest.raises(ValueError):
        write_submission(str(tmp_path / "b.tif"), v)


def test_nodata_sentinel_is_rejected(tmp_path):
    arr = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    arr[5, 5] = -3.4028234663852886e+38
    p = tmp_path / "sentinel.tif"
    _write_raw(p, arr, nodata=-3.4028234663852886e+38)
    rep = validate_submission(str(p))
    assert not rep.ok
    assert any("nodata sentinel" in x for x in rep.problems)


def test_wrong_crs_is_rejected(tmp_path):
    arr = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    p = tmp_path / "crs.tif"
    _write_raw(p, arr, crs="EPSG:26911")
    rep = validate_submission(str(p))
    assert not rep.ok and any("CRS" in x for x in rep.problems)


def test_out_of_range_values_are_rejected(tmp_path):
    arr = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    arr[3, 3] = 1.5
    p = tmp_path / "range.tif"
    _write_raw(p, arr)
    rep = validate_submission(str(p))
    assert not rep.ok and any("outside [0, 1]" in x for x in rep.problems)


def test_nan_allowed_only_on_reference_footprint(tmp_path):
    arr = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    mask = np.zeros(arr.shape, bool)
    mask[:10, :] = True
    arr[mask] = np.nan
    p = tmp_path / "nan.tif"
    _write_raw(p, arr, nodata=np.nan)
    assert validate_submission(str(p), reference_nan_mask=mask).ok
    assert not validate_submission(str(p), reference_nan_mask=~mask).ok
    assert not validate_submission(str(p)).ok


def test_nan_template_mask_requires_matching_nodata_tag(tmp_path):
    arr = np.zeros((REF_HEIGHT, REF_WIDTH), np.float32)
    mask = np.zeros(arr.shape, bool)
    mask[:10, :] = True
    arr[mask] = np.nan
    p = tmp_path / "nan-without-tag.tif"
    _write_raw(p, arr, nodata=None)
    report = validate_submission(str(p), reference_nan_mask=mask)
    assert not report.ok
    assert any("nodata tag" in problem for problem in report.problems)
