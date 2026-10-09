"""Regression checks for the review's provenance and no-promotion safeguards."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

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


def test_current_status_fails_closed_for_every_historical_artifact():
    status = load_json("evidence/submission_status.json")
    assert status["safe_to_download_for_audit"] is True
    assert status["safe_to_submit"] is False
    assert "no new TIF" in status["deliverable_tension"]["resolution"]
    assert status["organizer_confirmed_score"] is None
    assert status["weekly_slots_used"] == 0
    assert "NOT CLEARED" in status["status"]
    assert all(artifact["status"].endswith("not safe to submit")
               for artifact in status["artifacts"].values())
    assert any(gate["gate"] == "feature-alone leakage canary" and gate["result"].startswith("NOT RUN")
               for gate in status["blocking_gates"])


def test_historical_downloads_match_receipts_but_remain_audit_only():
    status = load_json("evidence/submission_status.json")
    names = [artifact["submission_name"] for artifact in status["artifacts"].values()]
    assert len(names) == len(set(names))  # distinct historical names, not approval to submit
    for artifact in status["artifacts"].values():
        raster = ROOT / artifact["file"]
        receipt = json.loads(raster.with_suffix(".json").read_text())
        digest = hashlib.sha256(raster.read_bytes()).hexdigest()
        assert digest == artifact["sha256"] == receipt["sha256"]
        assert artifact["status"].endswith("not safe to submit")
        audit = artifact["on_disk_audit"]
        assert audit["sha256_matches_adjacent_receipt"] is True
        assert audit["candidate_nan_pixels"] == 0
        assert audit["sample_nan_exterior_pixels"] > 0
        assert audit["exterior_behavior"].startswith("finite zero outside")
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
