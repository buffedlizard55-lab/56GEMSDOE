"""Fail-closed local GeoTIFF format check; never claims organizer acceptance."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rasterio  # noqa: E402
from gems56.gates import format_report  # noqa: E402


def validate(pred_path, sample_path=None, training_features_path=None):
    pred = Path(pred_path)
    sample = Path(sample_path) if sample_path else ROOT / "data" / "sample_submission.tif"
    train = Path(training_features_path) if training_features_path else None
    if not pred.is_file():
        print(f"LOCAL FORMAT CHECK FAIL: missing prediction {pred}")
        return False
    if not sample.is_file():
        print(f"LOCAL FORMAT CHECK FAIL: missing sample template {sample}")
        return False

    report = format_report(pred, sample)
    report["warnings"] = []
    if train is None:
        report["warnings"].append(
            "training feature reference not supplied; only the pinned sample grid was checked"
        )
    if train is not None:
        if not train.is_file():
            report["problems"].append(f"training feature reference is missing: {train}")
        else:
            with rasterio.open(pred) as candidate, rasterio.open(train) as features:
                train_match = bool(
                    candidate.shape == features.shape
                    and candidate.crs is not None and candidate.crs == features.crs
                    and candidate.transform == features.transform
                    and candidate.bounds == features.bounds
                )
                report["training_grid_matches"] = train_match
                report["training_grid"] = dict(
                    shape=[features.height, features.width],
                    crs=str(features.crs),
                    transform=list(features.transform),
                    bounds=list(features.bounds),
                )
                if not train_match:
                    report["problems"].append("prediction grid differs from training_features.tif")

    report["ok"] = not report["problems"]
    report["validation_class"] = "local format validation only; not organizer acceptance"
    print(json.dumps(report, indent=2, allow_nan=False))
    if report["ok"]:
        print("LOCAL FORMAT VALIDATION PASS — this does not establish uniqueness, score, or organizer acceptance.")
    else:
        print("LOCAL FORMAT VALIDATION FAIL:")
        for problem in report["problems"]:
            print(f"  - {problem}")
    return report["ok"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred", required=True, help="prediction GeoTIFF")
    parser.add_argument("--sample", default=str(ROOT / "data" / "sample_submission.tif"),
                        help="sample template, including its outside-footprint mask")
    default_train = ROOT / "data" / "training_features.tif"
    parser.add_argument(
        "--train",
        default=str(default_train) if default_train.is_file() else None,
        help="optional training feature grid used as a second metadata reference; omitted when unavailable",
    )
    args = parser.parse_args()
    sys.exit(0 if validate(args.pred, args.sample, args.train) else 1)
