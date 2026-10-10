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
    readme = (ROOT / "README.md").read_text()
    exec_page = (ROOT / "docs" / "executive-summary.html").read_text()
    downloads = (ROOT / "docs" / "downloads" / "README.md").read_text()
    submit = (ROOT / "docs" / "submit.html").read_text()
    h57_page = (ROOT / "docs" / "h57.html").read_text()
    pr7_index = (ROOT / "docs" / "discovery-index.html").read_text()
    pr7_exec = (ROOT / "docs" / "discovery-executive-summary.html").read_text()
    research = (ROOT / "docs" / "research.html").read_text()
    hypotheses = (ROOT / "docs" / "hypotheses.html").read_text()
    h56_hypotheses = (ROOT / "docs" / "research" / "hypotheses-round2.md").read_text()
    research_summary = (ROOT / "docs" / "research" / "hypotheses.md").read_text()
    round2_builder = (ROOT / "scripts" / "build_round2.py").read_text()
    prior_lane = (ROOT / "docs" / "lane1-corrections.html").read_text()
    assert "H57 ARCHIVE — NEGATIVE / STOP — NOT SAFE TO SUBMIT" in index
    assert "The H57 TIFF linked above is retained for audit only" in index
    assert "DUPLICATE/STOP" in index
    assert "h56 round-3 corrections" in index and "H-C1 map-quality NEGATIVE" in index
    assert "ROUND-2 DISCOVERY CANDIDATE (PR #7)" in index
    assert "this PR #7" in index
    assert "48,080 withheld positives" in index and "gems52-pooled-hide-v1" in index
    assert "neither is cleared for upload or a weekly slot" in index
    assert "finite exterior conflicts with the official null-outside-footprint convention" in index
    assert "No portal" in index and "upload or organizer score exists." in index
    assert "h57-hide-and-recover-v1" in index and "41,742 withheld positives" in index
    assert "0.00087 [95% CI 0.000486, 0.001327]" in index
    assert "[paired 95% CI -0.001378, -0.000476]" in index
    assert "Local <b>HOLDOUT-DTI</b> on simulated-corrections truth" in research
    assert "evaluator version hash not recorded" in research
    assert "26,813 withheld positives" in research
    assert "A1 lane (archived research output; not submitted)" in research
    assert "0.31049 [95% CI 0.28212, 0.33781]" in research
    assert "0.10788 [95% CI 0.08976, 0.12681]" in research
    assert "not an organizer score" in research
    assert "DUPLICATE / STOP" in research and "not submitted" in research
    assert "HOLDOUT-DTI, simulated truth" in hypotheses
    assert "26,813 withheld positives" in hypotheses and "version hash not recorded" in hypotheses
    assert "0.00716 [95% CI 0.00284, 0.01270]" in hypotheses
    assert "0.00523 [95% CI 0.00162, 0.00963]" in hypotheses
    assert "0.00020 [95% CI 0.00000, 0.00065]" in hypotheses
    assert "evaluator <code>gems52-pooled-hide-v1</code>" in hypotheses
    assert "48,080 withheld positives" in hypotheses and "paired contrast -0.02257 [95% CI" in hypotheses
    assert "Evidence classes: **HOLDOUT-DTI**" in h56_hypotheses
    assert "36,335 withheld positive pixels" in h56_hypotheses
    assert "0.03872 [95% CI 0.03494, 0.04239]" in h56_hypotheses
    assert "0.03117 [95% CI 0.02769, 0.03469]" in h56_hypotheses
    assert "0.09003 [95% CI 0.08041, 0.09856]" in h56_hypotheses
    assert "not an organizer score" in h56_hypotheses
    assert "HOLDOUT-DTI, evaluator" in prior_lane and "gems52-pooled-hide-v1" in prior_lane
    assert "48,080 withheld positives" in prior_lane
    assert "Historical PR #4 page" in prior_lane
    assert "NOT CLEARED for upload or a weekly slot" in prior_lane
    assert "0.00016 [95% CI 0.00000, 0.00045]" in prior_lane
    assert "not an organizer score" in prior_lane
    assert "OK to submit" not in prior_lane
    assert "paste into the DrivenData form" not in prior_lane
    assert "No corrections-lane artifact is selected, promoted, or cleared to submit" in exec_page
    assert "No corrections-lane TIFF in this review is cleared or safe to submit" in submit
    assert "Other lanes have separate receipts and are not adjudicated here" in submit
    assert "48,080 withheld positives; not an organizer score" in downloads
    assert "0.01242 [95% CI 0.00787, 0.01718]" in downloads
    assert "0.05466" not in downloads and "0.05340" not in downloads
    assert "0.00552" not in downloads and "0.00647" not in downloads
    assert "promoted=None" not in downloads
    assert "not an organizer score" in (ROOT / "docs" / "downloads" / "README.md").read_text()
    assert "evaluator version hash not\nrecorded" in readme
    assert "26,813 withheld positives" in readme
    assert "0.10788 [95% CI 0.089756, 0.126814]" in readme
    assert "gems52-pooled-hide-v1`, 4 folds, 36,335 withheld positive pixels" in readme
    assert "0.03872 [95% CI 0.03483, 0.04241]" in readme
    assert "h57-hide-and-recover-v1" in h57_page and "60,894 withheld positives" in h57_page
    assert "paired contrast vs B1 (95% CI)" in h57_page
    assert "36,335 withheld positives" in research_summary
    assert "0.03872 [95% CI 0.03483, 0.04241]" in research_summary
    assert "0.00380 [95% CI 0.00330, 0.00429]" in research_summary
    assert "Historical Run A &mdash; separate corrections session" in pr7_index
    assert "score is deliberately omitted here because the note was never submitted" in pr7_index
    assert "HOLDOUT-DTI(sim) 0.3105" not in pr7_index
    assert "95% CI" in round2_builder and "withheld_positive_pixels" in round2_builder


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
