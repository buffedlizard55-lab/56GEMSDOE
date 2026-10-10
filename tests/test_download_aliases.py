"""The data prep script publishes verified grid inputs at the paths tools consume."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_verified_grid_inputs_have_root_level_compatibility_aliases():
    sample = ROOT / "data" / "sample_submission.tif"
    grid_sample = ROOT / "data" / "grid" / "sample_submission.tif"
    labels = ROOT / "data" / "labels.tif"
    catalogue = ROOT / "data" / "grid" / "existing_faults.tif"

    assert sample.is_file() and grid_sample.is_file()
    assert labels.is_file() and catalogue.is_file()
    assert _sha(sample) == _sha(grid_sample)
    assert _sha(labels) == _sha(catalogue)
