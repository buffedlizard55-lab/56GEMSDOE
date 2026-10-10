"""Regressions for the template-footprint convention and strict local format gates."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems56.gates import format_report  # noqa: E402
from submission_io import clean_profile, conformance_findings, write_submission  # noqa: E402


def _fixture(path, values, *, nodata=np.nan):
    values = np.asarray(values, dtype=np.float32)
    transform = Affine(100, 0, 1000, 0, -100, 3000)
    with rasterio.open(
        path, "w", driver="GTiff", width=values.shape[1], height=values.shape[0],
        count=1, dtype="float32", crs="EPSG:32611", transform=transform,
        nodata=nodata, tiled=True, blockxsize=16, blockysize=16,
    ) as dst:
        dst.write(values, 1)
    return transform


def _arrays():
    template = np.full((32, 32), np.nan, dtype=np.float32)
    template[4:28, 3:29] = 0.0
    good = np.full(template.shape, np.nan, dtype=np.float32)
    good[np.isfinite(template)] = 0.0
    good[10, 10] = 1.0
    return template, good


def test_format_gate_accepts_only_finite_inside_and_nan_outside(tmp_path):
    template, good = _arrays()
    sample = tmp_path / "sample.tif"
    pred = tmp_path / "good.tif"
    _fixture(sample, template)
    _fixture(pred, good)

    report = format_report(pred, sample)
    assert report["ok"], report["problems"]
    assert report["mask_matches_template"]
    assert report["nodata_matches_template"]
    assert report["nan_inside_px"] == 0
    assert report["non_nan_outside_px"] == 0
    assert report["validation_class"].startswith("local on-disk")


def test_format_gate_rejects_finite_outside_even_when_all_values_are_in_range(tmp_path):
    template, candidate = _arrays()
    candidate[0, 0] = 0.0
    sample = tmp_path / "sample.tif"
    pred = tmp_path / "outside.tif"
    _fixture(sample, template)
    _fixture(pred, candidate)

    report = format_report(pred, sample)
    assert not report["ok"]
    assert report["non_nan_outside_px"] == 1
    assert any("outside" in problem for problem in report["problems"])


def test_format_gate_rejects_nan_inside_and_missing_nodata_tag(tmp_path):
    template, candidate = _arrays()
    candidate[5, 5] = np.nan
    sample = tmp_path / "sample.tif"
    bad_mask = tmp_path / "bad-mask.tif"
    missing_tag = tmp_path / "missing-tag.tif"
    _fixture(sample, template)
    _fixture(bad_mask, candidate)

    report = format_report(bad_mask, sample)
    assert not report["ok"]
    assert report["nan_inside_px"] == 1

    _fixture(missing_tag, _arrays()[1], nodata=None)
    report = format_report(missing_tag, sample)
    assert not report["ok"]
    assert not report["nodata_matches_template"]


def test_format_gate_rejects_infinite_values(tmp_path):
    template, candidate = _arrays()
    candidate[6, 6] = np.inf
    sample = tmp_path / "sample.tif"
    pred = tmp_path / "infinite.tif"
    _fixture(sample, template)
    _fixture(pred, candidate)

    report = format_report(pred, sample)
    assert not report["ok"]
    assert report["infinity_pixels"] == 1


def test_conformance_findings_does_not_mistake_infinity_for_nan(tmp_path):
    template, candidate = _arrays()
    candidate[0, 0] = np.inf
    findings = conformance_findings(candidate, template)
    assert not findings["conformant"]
    assert findings["infinite_px"] == 1
    assert findings["non_nan_outside_px"] == 1


def test_legacy_writer_checks_optional_exact_mask_and_refuses_blank(tmp_path):
    valid = np.zeros((32, 32), dtype=bool)
    valid[4:28, 3:29] = True
    values = np.zeros(valid.shape, dtype=np.float32)
    values[10, 10] = 1.0
    values[~valid] = np.nan
    transform = Affine(100, 0, 1000, 0, -100, 3000)
    profile = clean_profile(
        height=32, width=32, crs="EPSG:32611", transform=transform,
        dtype="float32", nodata=float("nan"), tile=16,
    )
    info = write_submission(tmp_path / "valid.tif", values, profile, valid_mask=valid)
    assert info["nonzero_px"] == 1
    assert info["template_mask_checked"] is True

    wrong_mask = valid.copy()
    wrong_mask[0, 0] = True
    with pytest.raises(ValueError, match="finite/NaN mask"):
        write_submission(tmp_path / "wrong-mask.tif", values, profile, valid_mask=wrong_mask)

    blank = np.zeros(valid.shape, dtype=np.float32)
    blank[~valid] = np.nan
    with pytest.raises(ValueError, match="no positive finite emission"):
        write_submission(tmp_path / "blank.tif", blank, profile, valid_mask=valid)
