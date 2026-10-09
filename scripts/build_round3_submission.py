#!/usr/bin/env python3
"""Round 3 (corrections lane): build the twin-family research GeoTIFF.

Pre-registered in docs/research/hypotheses-20261009-round3.md.  H-C1 (map-quality
stratification) returned NEGATIVE on the pre-registered conjunction, so per the
pre-registered fallback the shipped raster is the TIGHTENING arm: the round-1
crest lines restricted to records whose displacement is corroborated by BOTH
evidence families named in the lane paragraph (DEM-curvature scarp crest AND
magnetic-gradient ridge): sign-concordant medians, |mag median| >= 1 px,
>= 3 qualified mag transects, on one shared perpendicular reference per record
(src/corrections.mag_corroborated_candidates - the same function the holdout's
A1b arm uses, so the file and the receipt cannot drift apart).

VERDICT: NEGATIVE (research raster, NOT cleared for a weekly slot):
  * H-C1 failed its pre-registered conjunction;
  * the holdout validates machinery only (simulated truth = the measured crests);
  * the literal registry containment gate is expected to fire against this
    lane's own round-1 raster (the dots are a strict subset of it).

Pipeline (template tooling, no private forks):
  measurement -> twin candidates -> emission (dots on DEM crest lines, off
  catalogue) -> conform_to_template -> write_submission (fail-loud) ->
  validate_submission.py -> sha256 + zip + receipt JSON.

Run: .venv/bin/python scripts/build_round3_submission.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import corrections as C  # noqa: E402
import submission_io as S  # noqa: E402

NAME_NOTE = ("h56 round-3 corrections: twin-family gate (DEM+mag concordant offsets, "
             "9 records); H-C1 map-quality NEGATIVE; research only, do not slot")


def zmap_table(cands: dict) -> list[dict]:
    """Map-tolerance z-scores for the round-1 candidate set (sensitivity table)."""
    att = pd.read_csv(ROOT / "data/cache/qfault_attributes.csv", dtype={"NUM": str})
    att["record"] = att.index.astype(str)
    att = att.set_index("record")
    off = pd.read_csv(ROOT / "evidence/corrections/record_offsets_dem_slope_strongest.csv",
                      dtype={"record": str}).set_index("record")
    twin = set(cands.keys())
    rows = []
    for rid, v in off.iterrows():
        if rid not in att.index:
            continue
        a = att.loc[rid]
        ftype = str(a.get("FTYPE_", "")).strip()
        try:
            ms = float(a.get("MAPSCALE", np.nan))
        except (TypeError, ValueError):
            ms = np.nan
        well = ftype == "Well Constrained"
        tol = 0.0005 * ms * 1000.0 if (well and np.isfinite(ms)) else 400.0
        rows.append(dict(record=rid, name=str(a.get("NAME", "")), ftype=ftype,
                         mapscale=(None if not np.isfinite(ms) else ms),
                         dem_median_m=float(v["median_offset_m"]),
                         tol_m=float(tol), z_map=float(abs(v["median_offset_m"]) / tol),
                         round1_gate=bool(abs(v["median_offset_px"]) > 2.0
                                          and v["sign_agreement"] >= 0.70
                                          and v["n_transects"] >= 8),
                         twin_family=bool(rid in twin)))
    return rows


def main() -> int:
    outdir = ROOT / "docs/downloads"
    outdir.mkdir(parents=True, exist_ok=True)
    ev = ROOT / "evidence/corrections"

    print("[1/6] lane measurement (shared src/corrections.py)")
    res = C.run_measurement(str(ROOT / "data/labels.tif"),
                            str(ROOT / "data/training_features.tif"),
                            str(ROOT / "data/cache/fault_px_record.npz"),
                            str(ROOT / "data/cache/lidar_scarp_features_u8.tif"))
    fault, footprint = C.load_labels(str(ROOT / "data/labels.tif"))
    with rasterio.open(ROOT / "data/sample_submission.tif") as src:
        template = src.read(1)
        sample_profile = src.profile.copy()

    print("[2/6] twin-family candidates (mag-corroborated tightening)")
    twin = C.mag_corroborated_candidates(res)
    base = C.correction_candidates(res)
    print(f"      round-1 candidates: {len(base)}   twin-family: {len(twin)}")
    assert twin and set(twin) <= base, "twin set must be a nonempty subset of round-1's"

    print("[3/6] emission (dots on the DEM crest lines of the twin records)")
    emit, n_dots, per_rec = C.build_emission(res, fault, footprint,
                                             candidates=set(twin.keys()))
    on_cat = int((np.nan_to_num(emit)[fault]).sum())
    print(f"      dots: {n_dots:,}   on-catalogue dots: {on_cat}")
    assert on_cat == 0, "emission must not place dots on known-fault pixels"
    assert np.nan_to_num(emit).max() <= 1.0

    print("[4/6] conform + write (fail-loud writer, template NaN outside)")
    a1c, stats = S.conform_to_template(emit, template)
    print(f"      conformance: {stats}")
    pix_hash = hashlib.sha256(
        np.ascontiguousarray(a1c, dtype="<f4").tobytes()).hexdigest()[:8]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"gems56-corr-twinfam9-{stamp}-{pix_hash}"
    tif = outdir / f"{base_name}-nan.tif"
    # remove stale rebuilds with identical pixels (same pixel hash, older stamp)
    for old in list(outdir.glob(f"gems56-corr-twinfam9-*-{pix_hash}-nan.tif")) + \
               list(outdir.glob(f"gems56-corr-twinfam9-*-{pix_hash}.zip")):
        if old != tif:
            old.unlink(missing_ok=True)
            print(f"      removed stale rebuild {old.name}")
    prof = S.clean_profile(sample_profile, height=a1c.shape[0], width=a1c.shape[1],
                           crs="EPSG:32611", transform=sample_profile["transform"],
                           dtype="float32", nodata=float("nan"))
    info = S.write_submission(tif, a1c, prof,
                              band_description="GEMSDOE56 corrections lane round 3: "
                                               "twin-family evidence-defined traces",
                              tags={"lane": "corrections", "emission": "twin_family_v1",
                                    "round": "3",
                                    "twin_records": ",".join(sorted(twin)),
                                    "holdout": "evidence/corrections/holdout_corrections.json"})
    for k in ("path", "bytes", "sha256", "finite_px", "nonzero_px"):
        print(f"      {k}: {info[k]}")

    print("[5/6] validating with scripts/validate_submission.py")
    r = subprocess.run([sys.executable, "scripts/validate_submission.py",
                        "--pred", str(tif), "--sample", "data/sample_submission.tif",
                        "--train", "data/training_features.tif"],
                       capture_output=True, text=True)
    print(r.stdout[-600:])
    if r.returncode != 0:
        print(r.stderr)
        raise SystemExit("validation FAILED")
    val = dict(returncode=r.returncode, output=r.stdout[-1200:])

    print("[6/6] zip twin + receipt")
    zpath = outdir / f"{base_name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=tif.name)
    zsha = hashlib.sha256(zpath.read_bytes()).hexdigest()

    assert len(NAME_NOTE) <= 140, f"note is {len(NAME_NOTE)} chars (limit 140)"
    zt = zmap_table(twin)
    receipt = dict(
        evidence_class="built artefact with local format receipt; no organizer receipt exists",
        round=3,
        rule=dict(
            base="round-1 gate: |median dem_slope strongest offset| > 2 px, sign agreement >= 0.70, n >= 8",
            tightening="twin-family: mag_hg strongest median |m| >= 1 px, same sign as dem "
                       "(shared perpendicular reference per record), mag n >= 3",
            constants=dict(mag_corroborate_min_px=C.MAG_CORROBORATE_MIN_PX,
                           mag_corroborate_min_n=C.MAG_CORROBORATE_MIN_N),
            crest_source="DEM det_elev_slope strongest crest (LiDAR-calibrated, MAD 0.29 px vs 1 m scarp)",
        ),
        n_round1_candidates=len(base),
        n_twin_records=len(twin),
        twin_records={k: v for k, v in twin.items()},
        dots=n_dots,
        per_record_dots=per_rec,
        artefact=dict(name=base_name, note=NAME_NOTE, note_chars=len(NAME_NOTE),
                      file=tif.name, sha256=info["sha256"], bytes=info["bytes"],
                      zip_file=zpath.name, zip_sha256=zsha,
                      validator=val, values_present=[0.0, 1.0]),
        z_map_sensitivity=zt,
        verdict=("NEGATIVE - research raster, NOT cleared for a weekly slot: H-C1 failed its "
                 "pre-registered conjunction; holdout truth is simulated (construction-biased); "
                 "the literal registry containment gate fires against this lane's own round-1 "
                 "raster (strict subset); see evidence/corrections/run_card_round3.json"),
    )
    (ev / "build_round3.json").write_text(json.dumps(receipt, indent=1))
    print(f"receipt: evidence/corrections/build_round3.json")
    print(f"NAME  : {base_name}")
    print(f"NOTE  : {NAME_NOTE}  ({len(NAME_NOTE)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
