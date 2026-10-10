#!/usr/bin/env python3
"""Corrections lane, final deliverable: build the submission GeoTIFF.

Pipeline (reuses the template's cached tooling, no private forks):
  1. run the lane measurement (src/corrections.py)
  2. emission = dots on the evidence-defined trace (connected strongest-crest
     line) for records with consistent offset > 2 px, off-catalogue, inside
     the footprint  ->  A1 "lane" raster
  3. surface  = the same emission WITHOUT the candidate gate (all records with
     an unambiguous crest)  ->  A2 "surface" raster (pre-placement uniqueness
     check only; NOT the submission)
  4. conform both to the official sample template (finite inside the footprint,
     NaN outside, GDAL_NODATA=nan) - src/submission_io.conform_to_template
  5. write with the fail-loud writer (src/submission_io.write_submission:
     clean tiled profile, read-back verification, refuses empty/all-zero)
  6. validate with scripts/validate_submission.py (CRS/shape/transform/dtype/
     range/template-conformance/nodata-tag checks)
  7. sha256 both file and pixels; write the run card skeleton

The registry uniqueness check (scripts/check_registry.py) is run separately and
its numbers are merged into the run card.

Run:  python scripts/build_submission.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import corrections as C  # noqa: E402
import submission_io as S  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--features", default="data/training_features.tif")
    ap.add_argument("--records", default="data/cache/fault_px_record.npz")
    ap.add_argument("--lidar", default="data/cache/lidar_scarp_features_u8.tif")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--outdir", default="docs/downloads")
    ap.add_argument("--evidence", default="evidence/corrections")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ev = Path(args.evidence)
    ev.mkdir(parents=True, exist_ok=True)

    print("[1/7] lane measurement")
    res = C.run_measurement(args.labels, args.features, args.records, args.lidar)
    fault, footprint = C.load_labels(args.labels)
    with rasterio.open(args.sample) as src:
        template = src.read(1)
        sample_profile = src.profile.copy()

    print("[2/7] lane emission (A1) + surface (A2)")
    cands = C.correction_candidates(res)
    a1, a1_n, a1_per_rec = C.build_emission(res, fault, footprint, candidates=cands)
    a2, a2_n, _ = C.build_emission(res, fault, footprint, candidates=None)
    on_cat = int((np.nan_to_num(a1)[fault]).sum())
    print(f"      candidate records: {len(cands)}   A1 dots: {a1_n:,}   "
          f"A2 surface dots: {a2_n:,}   A1 dots ON catalogue: {on_cat}")
    assert on_cat == 0, "emission must not place dots on known-fault pixels"
    np.save("data/cache/lane_emission_A1.npy", np.nan_to_num(a1, nan=0.0))
    np.save("data/cache/lane_surface_A2.npy", np.nan_to_num(a2, nan=0.0))

    print("[3/7] conforming to the official sample template")
    a1c, stats1 = S.conform_to_template(a1, template)
    a2c, stats2 = S.conform_to_template(a2, template)
    print(f"      A1 conformance: {stats1}")
    print(f"      A2 conformance: {stats2}")

    # pixel hash for the name + uniqueness bookkeeping
    pix_hash = hashlib.sha256(
        np.ascontiguousarray(a1c, dtype="<f4").tobytes()).hexdigest()[:8]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"gems56-corr-crestgt2px-{stamp}-{pix_hash}"
    primary = outdir / f"{base}-nan.tif"     # template-conformant (NaN outside, nodata=nan)
    # remove stale rebuilds with identical pixels (same pixel hash, older stamp)
    for old in outdir.glob(f"gems56-corr-crestgt2px-*-{pix_hash}-nan.tif"):
        if old != primary:
            old.unlink()
            print(f"      removed stale rebuild {old.name}")

    print("[4/7] writing the submission GeoTIFF (fail-loud writer)")
    prof = S.clean_profile(sample_profile, height=a1c.shape[0], width=a1c.shape[1],
                           crs="EPSG:32611", transform=sample_profile["transform"],
                           dtype="float32", nodata=float("nan"))
    info1 = S.write_submission(primary, a1c, prof,
                               band_description="GEMSDOE56 corrections lane: "
                                                "evidence-defined fault traces",
                               tags={"lane": "corrections", "emission": "crest_gt_2px",
                                     "candidates": str(len(cands)),
                                     "holdout": "evidence/corrections/holdout_corrections.json"})
    for k in ("path", "bytes", "sha256", "finite_px", "nonzero_px", "prob_mass"):
        print(f"      primary {k}: {info1[k]}")

    print("[5/7] validating with scripts/validate_submission.py")
    r = subprocess.run([sys.executable, "scripts/validate_submission.py",
                        "--pred", str(primary), "--sample", args.sample,
                        "--train", args.features],
                       capture_output=True, text=True)
    val = {"primary": dict(returncode=r.returncode, output=r.stdout[-1500:])}
    print(f"      primary: exit {r.returncode}")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("validation FAILED for primary")

    print("[6/7] conformance gate (src.submission_io validate-conformant)")
    r = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant",
                        str(primary), "--sample", args.sample],
                       capture_output=True, text=True, cwd=Path.cwd())
    conf = {"primary": dict(returncode=r.returncode, output=r.stdout[-800:])}
    print(f"      primary: exit {r.returncode}")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("conformance gate FAILED for primary")

    print("[7/7] run card skeleton")
    hold = json.loads((ev / "holdout_corrections.json").read_text())
    a1_dti = hold["arms"]["A1_lane"]["dti"]
    note = (f"GEMSDOE56 corrections: {a1_n} dots on LiDAR-calibrated DEM-scarp "
            f"crest where catalogue offset >2px; 0 on-catalogue; "
            f"HOLDOUT-DTI(sim) {a1_dti:.4f}")
    assert len(note) <= 140, f"note too long: {len(note)}"
    print(f"      note ({len(note)} chars): {note}")
    card = dict(
        session="56GEMSDOE corrections lane (arena/b71ede8d-56gemsdoe)",
        generated_utc=stamp,
        hypothesis=("New-fault ground truth lies within 300 m of known traces as "
                    "'corrections or modifications to existing fault traces' "
                    "(organizers, forum thread 11516). Where the DEM-scarp crest "
                    "(det_elev_slope ridge, calibrated on 1 m USGS 3DEP LiDAR) sits "
                    "consistently > 2 px (200 m) from the catalogue trace, the "
                    "refined fault is at the crest, not on the catalogue line."),
        mechanism=("Perpendicular transects (+/-400 m) on every catalogue trace; "
                   "strongest-crest offset of the det_elev_slope ridge per "
                   "vector-catalogue record; consistent offset = |median| > 2 px, "
                   "sign agreement >= 0.70, >= 8 transects; emit dots on the "
                   "connected crest line, off-catalogue, inside the footprint. "
                   "No learned component (Mnih & Hinton 2012 loss not invoked)."),
        named_non_fault_process=("Erosional/terrace scarps and alluvial-fan edges "
                                 "produce the same convex slope crest without a "
                                 "fault; a crest can also belong to a NEIGHBOURING "
                                 "fault (the off-catalogue restriction removes "
                                 "known-fault pixels, but an unmapped neighbour "
                                 "strand would score as a new fault, not a "
                                 "correction). LiDAR calibration shows the crest "
                                 "is a real sharp scarp; it cannot prove it is a "
                                 "fault."),
        holdout_dti=dict(
            label="HOLDOUT-DTI (simulated-corrections truth, evaluator src/metrics.py, "
                  "alpha 0.2, beta 0.8, 300 m triangular kernel, known-fault masking model)",
            n_withheld_positives=hold["n_withheld_positives"],
            n_correction_candidates=hold["n_correction_candidates"],
            A1_lane=dict(dti=hold["arms"]["A1_lane"]["dti"],
                         ci95=hold["arms"]["A1_lane"]["ci95"],
                         dots=hold["arms"]["A1_lane"]["dots"]),
            A0_masked_control=dict(dti=hold["arms"]["A0_catalogue"]["dti"],
                                   ci95=hold["arms"]["A0_catalogue"]["ci95"]),
            A4_random_control=dict(dti=hold["arms"]["A4_random"]["dti"],
                                   ci95=hold["arms"]["A4_random"]["ci95"]),
            contrasts=hold["contrasts"],
            leakage_canary=dict(
                max_evidence_auc=max(v["auc"] for k, v in hold["leakage_canary"].items()
                                     if not k.startswith("_")),
                catalogue_mask_auc=hold["leakage_canary"]["catalogue_mask"]["auc"],
                controls_ok=hold["controls_ok"]),
            source="evidence/corrections/holdout_corrections.json"),
        registry_check=dict(status="pending - run scripts/check_registry.py",
                            source="evidence/corrections/registry_check.json"),
        raster=dict(
            primary=str(primary),
            sha256=info1["sha256"],
            pixel_sha256=pix_hash,
            dots=a1_n, candidate_records=len(cands),
            on_catalogue_dots=on_cat,
            conformance=conf, validation=val),
        submission_name="GEMSDOE56-CORR-CRESTGT2PX",
        note=note,
        verdict=None,
    )
    (ev / "run_card.json").write_text(json.dumps(card, indent=1))
    print(f"      note ({len(note)} chars): {note}")
    print("\nPrimary download:", primary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
