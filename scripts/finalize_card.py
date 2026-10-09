#!/usr/bin/env python3
"""Finalize the run card after the registry check completes.

Merges evidence/corrections/registry_check.json into the run card, records the
verdict per the lane protocol (promote/negative), and re-verifies the written
submission GeoTIFF from disk (independent read-back receipt).

Run:  python scripts/finalize_card.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import corrections as C  # noqa: E402


def verify_tif(path, sample_path, labels_path):
    """Independent read-back receipt for the written submission."""
    with rasterio.open(path) as src:
        a = src.read(1)
        prof = dict(dtype=src.dtypes[0], count=src.count, crs=str(src.crs),
                    width=src.width, height=src.height,
                    transform=tuple(src.transform)[:6], nodata=src.nodata,
                    descriptions=src.descriptions, tags=src.tags())
    with rasterio.open(sample_path) as src:
        tpl = src.read(1)
        tpl_nodata = src.nodata
        tpl_transform = tuple(src.transform)[:6]
        tpl_crs = str(src.crs)
    fault, footprint = C.load_labels(labels_path)
    fin = np.isfinite(a)
    tpl_fin = np.isfinite(tpl)
    checks = dict(
        dtype_float32=prof["dtype"] == "float32",
        single_band=prof["count"] == 1,
        crs_matches_sample=prof["crs"] == tpl_crs == "EPSG:32611",
        shape_matches_sample=(prof["height"], prof["width"]) == tpl.shape,
        transform_matches_sample=prof["transform"] == tpl_transform,
        nodata_tag_is_nan=bool(prof["nodata"] is not None and np.isnan(prof["nodata"])),
        nan_mask_matches_sample=bool((fin == tpl_fin).all()),
        all_finite_inside_footprint=bool(np.isfinite(a[tpl_fin]).all()),
        values_in_0_1=bool((a[tpl_fin] >= 0).all() and (a[tpl_fin] <= 1).all()),
        no_nan_inside_footprint=bool((~np.isnan(a[tpl_fin])).all()),
        dots=int((a > 0).sum()),
        dots_on_catalogue=int((a[fault] > 0).sum()),
        prob_mass=float(a[tpl_fin].sum()),
        min=float(a[tpl_fin].min()), max=float(a[tpl_fin].max()),
    )
    checks["all_pass"] = all(v for k, v in checks.items()
                             if isinstance(v, bool) and k not in ("all_pass",))
    return checks, prof


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--card", default="evidence/corrections/run_card.json")
    ap.add_argument("--registry-check", default="evidence/corrections/registry_check.json")
    ap.add_argument("--holdout", default="evidence/corrections/holdout_corrections.json")
    ap.add_argument("--tif", default=None, help="default: the card's primary raster")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--labels", default="data/labels.tif")
    args = ap.parse_args()

    card = json.loads(Path(args.card).read_text())
    tif = Path(args.tif or card["raster"]["primary"])

    print("[1/4] merging holdout DTI evidence")
    hold = json.loads(Path(args.holdout).read_text())
    hd = card.setdefault("holdout_dti", {})
    hd["label"] = hold["label"]
    hd["n_withheld_positives"] = hold["n_withheld_positives"]
    hd["n_correction_candidates"] = hold["n_correction_candidates"]
    for card_key, arm_key in (("A1_lane", "A1_lane"),
                              ("A0_masked_control", "A0_catalogue"),
                              ("A4_random_control", "A4_random"),
                              ("A2_nogate", "A2_nogate"),
                              ("A5_oracle", "A5_oracle")):
        arm = hold["arms"][arm_key]
        hd[card_key] = {k: arm[k] for k in
                        ("dti", "ci95", "dots", "TP_w", "FP_w", "FN_w")}
    hd["contrasts"] = hold["contrasts"]
    hd["contrast_ci95"] = hold["contrast_ci95"]
    hd["leakage_canary"] = dict(
        max_evidence_auc=max(v["auc"] for k, v in hold["leakage_canary"].items()
                             if not k.startswith("_")),
        catalogue_mask_auc=hold["leakage_canary"]["catalogue_mask"]["auc"],
        dist_to_catalogue_auc=hold["leakage_canary"]["dist_to_catalogue_px"]["auc"],
        controls_ok=hold["controls_ok"])
    hd["source"] = "evidence/corrections/holdout_corrections.json"
    a1 = hd["A1_lane"]
    a0 = hd["A0_masked_control"]
    a4 = hd["A4_random_control"]
    print(f"      A1 lane {a1['dti']:.5f} [{a1['ci95'][0]:.5f}, {a1['ci95'][1]:.5f}] "
          f"vs A0 {a0['dti']:.5f} / A4 {a4['dti']:.5f} "
          f"(n withheld positives {hd['n_withheld_positives']:,})")

    print("[2/4] independent read-back verification of", tif.name)
    checks, prof = verify_tif(tif, args.sample, args.labels)
    for k, v in checks.items():
        print(f"      {k}: {v}")
    assert checks["all_pass"], "read-back verification FAILED"
    sha = hashlib.sha256(tif.read_bytes()).hexdigest()
    assert sha == card["raster"]["sha256"], "sha256 mismatch vs run card"
    print(f"      sha256 matches run card: {sha}")

    print("[3/4] merging registry check")
    reg = json.loads(Path(args.registry_check).read_text())
    card["registry_check"] = dict(
        status=reg["verdict"],
        n_registry_rasters=reg["n_registry_rasters"],
        n_unique_pixel_content=reg["n_unique_pixel_content"],
        thresholds=reg["thresholds"],
        worst=dict(
            spearman_dots=reg["worst"]["spearman_dots"],
            spearman_surface=reg["worst"]["spearman_surface"],
            jaccard_3px=reg["worst"]["jaccard_3px"],
            containment=reg["worst"]["containment"],
            rev_containment=reg["worst"]["rev_containment"]),
        n_duplicates=reg["n_duplicates"],
        n_literal_containment_flags=reg["n_literal_flags"],
        literal_flag_note=("the protocol's literal >70%-dot-containment test fires on "
                           "sparse habitat supersets; investigated with 3-px Jaccard, "
                           "reverse containment and mass ratio (IR-56-07) and "
                           "determined NOT duplicates"),
        top10_by_correlation=reg["top10_by_correlation"],
        source="evidence/corrections/registry_check.json")
    print(f"      {reg['verdict']}  (max Spearman {reg['worst']['spearman_dots']}, "
          f"max 3px Jaccard {reg['worst']['jaccard_3px']}, "
          f"{reg['n_duplicates']} duplicates, "
          f"{reg['n_literal_flags']} literal containment flags investigated)")

    print("[4/4] verdict")
    unique = reg["n_duplicates"] == 0
    beats_controls = a1["dti"] > a0["dti"] and a1["dti"] > a4["dti"]
    valid = checks["all_pass"]
    verdict = "promote" if (unique and beats_controls and valid) else "negative"
    card["verdict"] = dict(
        value=verdict,
        rationale=("lane emission beats masked and random controls on the holdout "
                   f"({a1['dti']:.5f} vs {a0['dti']:.5f} / {a4['dti']:.5f}); raster unique vs "
                   f"{reg['n_unique_pixel_content']} earlier rasters; format validated "
                   "(no NaN inside footprint, values in [0,1], CRS/shape/transform match)."
                   if verdict == "promote" else
                   "one or more gates failed - see registry_check / validation"),
        unique_vs_registry=bool(unique),
        beats_holdout_controls=bool(beats_controls),
        format_valid=bool(valid),
        note=("PROMOTE is a lane verdict, not a slot decision: no organizer score exists "
              "for this file; spending a weekly submission slot is the separate selector "
              "step within the weekly cap."))
    card["readback_receipt"] = checks
    Path(args.card).write_text(json.dumps(card, indent=1))
    print(f"      verdict: {verdict.upper()}")
    print(f"      card: {args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
