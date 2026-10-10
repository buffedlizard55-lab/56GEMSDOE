"""Regression checks for the review's provenance and no-promotion safeguards."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str):
    return json.loads((ROOT / path).read_text())


def test_mirror_pins_are_complete_and_consistent_with_input_registry():
    bridge = load_json("registry/bridge_sources.json")
    inputs = load_json("registry/input_pins.json")
    comp = bridge["competition_bridge"]["files"]
    features = comp["features"]
    assert sum(int(part["bytes"]) for part in features["parts"]) == features["bytes"]
    assert features["bytes"] == inputs["files"]["features"]["bytes"]
    assert features["sha256"] == inputs["files"]["features"]["sha256"]
    assert len(features["parts"]) == 5
    for name in ("catalogue", "sample"):
        assert comp[name]["bytes"] == inputs["files"][name]["bytes"]
        assert comp[name]["sha256"] == inputs["files"][name]["sha256"]
        assert len(comp[name]["sha256"]) == 64
    lidar = bridge["lidar_cache"]["files"]["scarp_summary"]
    assert lidar["sha256"] == inputs["files"]["lidar_scarp"]["sha256"]
    assert lidar["classification"].startswith("sibling-derived")
    assert all(len(part["sha256"]) == 64 and len(part["blob"]) == 40 for part in features["parts"])


def test_current_status_fails_closed_for_every_published_artifact():
    status = load_json("evidence/submission_status.json")
    assert status["safe_to_download_for_audit"] is True
    assert status["safe_to_submit"] is False
    assert "H57" in status["deliverable_tension"]["resolution"]
    assert "NOT CLEARED" in status["deliverable_tension"]["status"]
    assert status["organizer_confirmed_score"] is None
    assert status["weekly_slots_used"] == 0
    assert "NO CORRECTIONS-LANE FILE CLEARED FOR SUBMISSION" in status["status"]
    assert len(status["artifacts"]) == 5
    assert "corrections_h57_cover" in status["artifacts"]
    assert status["artifacts"]["discovery_pr7_round2"]["lane"] == "discovery; not corrections"
    h57 = status["artifacts"]["corrections_h57_cover"]
    assert h57["literal_uniqueness_gate"].startswith("DUPLICATE/STOP")
    assert h57["holdout_dti"]["withheld_positive_count"] == 41_742
    assert h57["holdout_dti"]["evaluator_version"].startswith("h57-hide-and-recover-v1")
    assert len(h57["holdout_dti"]["paired_contrast_B2_minus_B1_ci95"]) == 2
    assert all(artifact["safe_to_submit"] is False for artifact in status["artifacts"].values())
    assert all(artifact["status"].endswith("not safe to submit")
               for artifact in status["artifacts"].values())
    assert any("PR #9 corrections candidate" in gate["gate"] and gate["result"].startswith("NOT RUN")
               for gate in status["blocking_gates"])


def test_generated_site_fails_closed_and_keeps_independent_runs_separate():
    index = (ROOT / "docs" / "index.html").read_text()
    exec_page = (ROOT / "docs" / "executive-summary.html").read_text()
    downloads = (ROOT / "docs" / "downloads" / "README.md").read_text()
    submit = (ROOT / "docs" / "submit.html").read_text()
    h57_page = (ROOT / "docs" / "h57.html").read_text()
    pr7_index = (ROOT / "docs" / "discovery-index.html").read_text()
    pr7_exec = (ROOT / "docs" / "discovery-executive-summary.html").read_text()
    research = (ROOT / "docs" / "research.html").read_text()
    hypotheses = (ROOT / "docs" / "hypotheses.html").read_text()
    h56_hypotheses = (ROOT / "docs" / "research" / "hypotheses-round2.md").read_text()
    prior_lane = (ROOT / "docs" / "lane1-corrections.html").read_text()
    assert "H57 corrections-band GeoTIFF" in index
    assert "Available for audit download: YES. Cleared to submit: NO." in index
    assert "DUPLICATE/STOP" in index
    assert "H56 field/physics run" in index
    assert "Separate PR #7 discovery-lane result" in index
    assert "48,080 withheld positives" in index and "gems52-pooled-hide-v1" in index
    assert "h57-hide-and-recover-v1" in index and "41,742 withheld positives" in index
    assert "0.000872 [0.000486, 0.001327]" in index
    assert "paired 95% contrast [-0.001378, -0.000476]" in index
    assert "ok_to_submit" in h57_page and "no organizer receipt or tested upload behind it" in h57_page
    assert "H57 is audit-only" in h57_page and "DUPLICATE/STOP" in h57_page
    assert "gems52-pooled-hide-v1" in pr7_index and "48,080 withheld positives" in pr7_index
    assert "DUPLICATE/STOP" in pr7_index and "not an organizer score" in pr7_exec
    assert "no upload was made" in pr7_exec
    assert "HOLDOUT-DTI (local, never an organizer score)" in research
    assert "src/metrics.py" in research and "26,813 withheld positives" in research
    assert "0.31049" in research and "[0.28212, 0.33781]" in research
    assert "no separate contrast CI is recorded" in research
    assert "DUPLICATE/STOP" in research and "historical raster remains audit-only" in research
    assert "PR #5/#6 A1 historical correction run" in research
    assert "HOLDOUT-DTI (simulated truth)" in hypotheses
    assert "26,813 withheld positives" in hypotheses and "version hash not recorded" in hypotheses
    assert "historical PR #5/#6; DUPLICATE/STOP; audit-only" in hypotheses
    assert "0.00716 [0.00284, 0.01270] vs random 0.03499 [0.03273, 0.03714]" in hypotheses
    assert "0.00523 [0.00162, 0.00963] vs same-budget random 0.03499" in hypotheses
    assert "0.00020 [0.00000, 0.00065] vs same-budget random 0.04451 [0.04128, 0.04755]" in hypotheses
    assert "E1 field-only mag_ridge; HOLDOUT-DTI evaluator gems52-pooled-hide-v1, 36,335 withheld positives" in index
    assert "0.03826 [CI 0.03440 to 0.04196]" in index
    assert "0.03872 [95% CI 0.03483, 0.04241]" in index
    assert "36,335 withheld positives" in index and "95% CI" in index
    assert "every DTI value below is local **HOLDOUT-DTI**, not an organizer score" in h56_hypotheses
    assert "HOLDOUT-DTI, evaluator" in prior_lane and "gems52-pooled-hide-v1" in prior_lane
    assert "48,080 withheld positives" in prior_lane
    assert "Historical PR #4 page" in prior_lane and "NOT CLEARED for upload" in prior_lane
    assert "0.0001566 [0.0000000, 0.0004536]" in prior_lane
    assert "not a corrections-lane result" in exec_page
    assert "H57 corrections file is audit-only and DUPLICATE/STOP" in submit
    assert "no weekly slot selected and no submission made" in submit
    assert "0.05466" in downloads and "0.05340" in downloads
    assert "0.00552" in downloads and "0.00647" in downloads
    assert "not an organizer score or a weekly-slot selection" in downloads
    assert "promoted=None" not in downloads


def test_published_downloads_match_receipts_and_sample_mask_but_remain_audit_only():
    status = load_json("evidence/submission_status.json")
    names = [artifact["submission_name"] for artifact in status["artifacts"].values()]
    assert len(names) == len(set(names))  # distinct archived names, not approval to submit
    sample_path = ROOT / "data/sample_submission.tif"
    if not sample_path.exists():  # fresh checkout may have only the hash-pinned bridge raster
        sample_path = ROOT / "data/bridge/example_submission.tif"
    with rasterio.open(sample_path) as sample:
        template = sample.read(1)
        valid = np.isfinite(template)
        transform, crs, shape = sample.transform, sample.crs, sample.shape
    for artifact in status["artifacts"].values():
        raster = ROOT / artifact["file"]
        receipt_path = ROOT / artifact["receipt_file"]
        receipt = json.loads(receipt_path.read_text())
        digest = hashlib.sha256(raster.read_bytes()).hexdigest()
        if "raster" in receipt:
            receipt_sha = receipt["raster"]["sha256"]
        else:
            receipt_sha = receipt["sha256"]
        assert digest == artifact["sha256"] == receipt_sha
        assert artifact["status"].endswith("not safe to submit")
        audit = artifact["on_disk_audit"]
        assert audit["sample_nan_exterior_pixels"] == int((~valid).sum())
        assert audit.get("sha256_matches_adjacent_receipt") or audit.get("sha256_matches_recorded_run_card")
        assert audit["candidate_nan_pixels_inside_sample"] == 0
        with rasterio.open(raster) as ds:
            field = ds.read(1)
            assert ds.shape == shape and ds.transform == transform and ds.crs == crs
            assert ds.count == 1 and ds.dtypes[0] == "float32"
            assert np.isfinite(field[valid]).all()
            assert np.all((field[valid] >= 0) & (field[valid] <= 1))
            assert int((valid & ~np.isfinite(field)).sum()) == 0
            if audit["exterior_behavior"].startswith("NaN outside"):
                assert np.isnan(field[~valid]).all()
                assert ds.nodata is not None and np.isnan(ds.nodata)
            else:
                assert np.isfinite(field[~valid]).all()
                assert np.all(field[~valid] == 0)
                assert ds.nodata is None
    assert status["safe_to_submit"] is False


def test_default_correction_builder_cannot_disable_null_strength_gate_or_relax_threshold():
    source = (ROOT / "scripts" / "build_corrections_submission.py").read_text()
    tree = ast.parse(source)
    arms = next(node for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "ARMS" for target in node.targets))
    assert ast.literal_eval(arms.value) == {"primary": 2.0}
    build_arm = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_arm")
    kwonly = {arg.arg: default for arg, default in zip(build_arm.args.kwonlyargs, build_arm.args.kw_defaults)}
    assert kwonly["hd"] is None and kwonly["hm"] is None  # required; cannot silently default to zero
    measure_calls = [node for node in ast.walk(build_arm) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == "measure"]
    assert measure_calls
    min_hgt = next(k.value for k in measure_calls[0].keywords if k.arg == "min_hgt")
    assert isinstance(min_hgt, ast.Tuple) and len(min_hgt.elts) == 3
    assert not any(keyword.arg == "use_null_floor" for call in measure_calls for keyword in call.keywords)


def test_shared_template_defect_is_reported_without_local_fork():
    status = load_json("evidence/submission_status.json")
    template = status["shared_template"]
    assert template["upstream_issue"].endswith("/issues/65")
    assert template["local_private_fork_created"] is False
    assert "all-finite" in template["defect"]
