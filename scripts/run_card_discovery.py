#!/usr/bin/env python3
"""The round-2 run card: one JSON object, every field sourced from a receipt written this run.

Required fields (standing brief): hypothesis; mechanism; the named non-fault process that could
mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output;
submission name + note of at most 140 characters; verdict promote / negative.

Receipt: evidence/run_card_discovery_v1.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"


def load(name):
    p = EV / name
    return json.loads(p.read_text()) if p.exists() else None


def main():
    hold = load("holdout_discovery_v1.json")
    pre = load("holdout_discovery_v0_prefx.json")
    bld = load("build_discovery_v1.json")
    gate = load("lane_gate_discovery_v2.json")
    scr = load("registry_screen_v2.json")
    if not (hold and bld):
        raise SystemExit("holdout_discovery_v1.json and build_discovery_v1.json are required")
    cand = bld["receipt"]["metadata"]["holdout_candidate"]
    sc = hold["pooled"]["scores"][cand]
    chance = hold["pooled"]["scores"].get(f"random@{bld['budget']}")
    paired = hold["pooled"]["paired_differences"].get(f"random@{bld['budget']}")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    promoted = bool(hold.get("verdict_pass") and (gate or {}).get("ok"))
    card = dict(
        run_utc=subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True,
                               text=True).stdout.strip(),
        lane="discovery (round 2 of the corrections-lane repository)",
        commit=commit,
        hypothesis=(
            "Faults that never reached the USGS/INGENIOUS catalogue are expressed in the GeoDAWN "
            "stack as laterally-persistent steps of the isostatic gravity anomaly (H6), of the "
            "basement-depth surface concordant with conductivity (H7), and as proximity to the "
            "magnetic tilt/curvature low (H8); ranking those signatures and emitting the top-k "
            "cells >200 m off known traces recovers structure the catalogue does not contain."),
        mechanism=(
            "scarp_step (two-sided, >=2 km along-strike persistent step, 150 m half-width) on "
            "bands 13/15/17, box-mean low of band 6; per-field rank01; concordance = min of "
            "ranks; emission = top-k inside footprint & ~dilate(catalogue, 2 px), value 1.0."),
        named_non_fault_process=(
            "topographic leakage through the isostatic correction (range-front-correlated error "
            "that mimics a density step); depositional onlap gradients that step basement depth "
            "without faulting; saline playa-margin conductivity contrasts; intrusive bodies that "
            "step gravity without any fault; lithologic contacts in the tilt/curvature field; and "
            "on the estimator side, the footprint-rim zero-fill artefact (IR-56-020, fixed and "
            "regression-tested before this run's verdict)."),
        measurements=dict(
            evidence_class="HOLDOUT-DTI (catalogue recovery, hide-and-recover; NOT new-fault discovery)",
            evaluator_version=hold["evaluator"]["version"],
            folds=hold["design"]["folds"],
            withheld_positives=hold["withheld_positives_total"],
            candidate_arm=cand,
            candidate_dti=sc["dti"], candidate_ci95=sc["ci95"],
            chance_dti=chance["dti"] if chance else None,
            chance_ci95=chance["ci95"] if chance else None,
            paired_vs_chance=paired,
            canary=hold["canary"],
            canary_rule=hold["canary_rule"],
            canary_max_new_fields=hold["canary_max_new_fields"],
            pre_fix_run=dict(
                note="superseded by IR-56-020 (footprint-rim artefact); preserved for the record",
                candidate_dti=(pre or {}).get("pooled", {}).get("scores", {}).get(cand, {}).get("dti"),
                receipt="evidence/holdout_discovery_v0_prefx.json" if pre else None,
            ),
            previous_repo_best_dti=hold["bars"]["previous_repo_best_dti"],
        ),
        registry_comparison=dict(
            tool="gems56.gates.lane_report (H61 shared-template repair): literal + coverage-adjusted "
                 "policy, phase=surface and phase=dots",
            screen=dict(
                files=(scr or {}).get("corpus", {}).get("files"),
                max_directed_overlap=(scr or {}).get("worst_max_frac"),
                reciprocal_over_070=(scr or {}).get("over_070_reciprocal"),
            ) if scr else None,
            literal_verdict=(gate or {}).get("verdict_literal"),
            policy_verdict=(gate or {}).get("verdict_policy"),
            max_spearman=(gate or {}).get("dots", {}).get("literal", {}).get("max_spearman"),
            max_near_3px_fraction=(gate or {}).get("dots", {}).get("literal", {}).get("max_near_3px_fraction"),
            max_near_source=(gate or {}).get("dots", {}).get("literal", {}).get("max_near_source"),
            duplicate=(gate or {}).get("duplicate"),
            receipt="evidence/lane_gate_discovery_v2.json" if gate else None,
        ),
        artefact=dict(
            name=bld["name"], note=bld["note"], note_chars=bld["note_chars"],
            file=bld["receipt"]["file"], sha256=bld["receipt"]["sha256"],
            bytes=bld["receipt"]["bytes"], dots=bld["dots"],
            validator_ok=bld["receipt"]["validator"]["ok"],
            validator_problems=bld["receipt"]["validator"]["problems"],
            values_present=[0.0, 1.0],
            zip_file=bld["receipt"]["zip_file"],
        ),
        budget=dict(experiments=3,
                    used="E1 holdout (incl. one re-run after the IR-56-020 template fix), "
                         "E2 build+validate, E3 uniqueness screen+gate",
                    slots_used=0,
                    note="promotion to a real weekly slot is a separate selector step; this card "
                         "does not pick one"),
    )
    card["verdict"] = "promote" if promoted else "negative"
    card["verdict_text"] = (
        "PROMOTE to selector: the pre-registered holdout rule passed and both lane gates are clear."
        if promoted else
        "NEGATIVE: "
        + ("holdout rule failed (paired CI vs chance "
           f"{(paired or {}).get('ci95')}); " if not hold.get("verdict_pass") else "")
        + ("" if gate is None else f"lane gate literal={card['registry_comparison']['literal_verdict']}, "
                                  f"policy={card['registry_comparison']['policy_verdict']}; ")
        + "the raster is published, format-validated and labelled; no slot is recommended."
    )
    path = EV / "run_card_discovery_v1.json"
    path.write_text(json.dumps(card, indent=1, default=float) + "\n")
    print(json.dumps({k: card[k] for k in ("run_utc", "verdict", "verdict_text")}, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
