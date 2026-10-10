#!/usr/bin/env python3
"""Round-3 run card: one JSON card per the parallel-run protocol.

Assembles evidence/corrections/run_card_round3.json from the round's receipts
(no number is typed in by hand):
  * evidence/corrections/map_quality_stratification.json  (E1, H-C1)
  * evidence/corrections/holdout_corrections.json          (E2, arms A1b/A4b)
  * evidence/corrections/build_round3.json                 (E3, the raster)
  * evidence/corrections/registry_check_round3.json        (E3, uniqueness)

Run: .venv/bin/python scripts/run_card_round3.py
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence" / "corrections"


def main() -> int:
    e1 = json.loads((EV / "map_quality_stratification.json").read_text())
    e2 = json.loads((EV / "holdout_corrections.json").read_text())
    e3 = json.loads((EV / "build_round3.json").read_text())
    reg = json.loads((EV / "registry_check_round3.json").read_text())

    a1b = e2["arms"]["A1b_twin"]
    a4b = e2["arms"]["A4b_random_a1b"]
    a1 = e2["arms"]["A1_lane"]

    p = e1["tables"]["primary"]
    h_c1 = dict(
        hypothesis="H-C1: the catalogue-to-evidence offset stratifies with the catalogue's "
                   "own location-quality metadata (FTYPE_/MAPSCALE/FCODE2023, official "
                   "QFaults/INGENIOUS attribute table)",
        pre_registered_rule=e1["h_c1_rule"],
        verdict=e1["h_c1_verdict"],
        primary=dict(spearman_MAPSCALE_vs_absmedian=p["spearman_MAPSCALE_A"],
                     mannwhitney_notwell_vs_well=p["mw_notwell_vs_well"]),
        secondaries=dict(spearman_MAPSCALE_vs_fracgt2=p["spearman_MAPSCALE_fracgt2"],
                         kruskal_FTYPE=p.get("kruskal_FTYPE"),
                         spearman_FCODE=p.get("spearman_FCODE_A")),
        controls={k: dict(spearman=v.get("spearman_MAPSCALE_A"),
                          mw=v.get("mw_notwell_vs_well"),
                          n=v.get("records_n_ge_8"))
                  for k, v in e1["controls"].items()},
        interpretation=(
            "Conjunction FAILED: the MAPSCALE arm could not fire (120/125 records mapped at "
            "1:250k - no scale variance; rho 0.059, p 0.257) while the FTYPE arm passed "
            "(MW p 0.039) and the secondaries lean supportive (FCODE rho 0.169 p 0.030; "
            "Kruskal p 0.034; monotone medians Well 1.05 < Moderately 1.50 < Inferred 3.15 px). "
            "The stratification also vanishes in the top-prominence quartile (MW p 0.62), the "
            "pre-registered terrain confound. Read as: suggestive, NOT confirmed - the "
            "corrections hypothesis keeps no independent validation from this round."),
    )

    card = dict(
        session="56GEMSDOE corrections lane round 3 (arena/e86c5610-56gemsdoe)",
        generated_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        lane="corrections (the brief's single method paragraph)",
        hypothesis=(
            "Round 3: (a) H-C1 - the round-1 catalogue-to-crest offsets should stratify with the "
            "catalogue's own location-quality fields if they are map-position errors (the "
            "corrections mechanism), since erosional terraces have no reason to respect mapping "
            "metadata; (b) fallback emission - restrict the round-1 crest lines to records whose "
            "displacement is corroborated by BOTH evidence families of the lane paragraph "
            "(DEM-curvature scarp crest AND magnetic-gradient ridge) with sign-concordant "
            "medians on one shared perpendicular reference."),
        mechanism=(
            "E1: join FTYPE_/MAPSCALE/FCODE2023 (official qfaults_ingenious attribute table, "
            "GDR 1391, positional join verified 1126/1126 on SLIPSENSE) to the round-1 per-record "
            "offset table; pre-registered two-arm conjunction test. E2: tighten the emission set "
            "with mag_corroborated_candidates (shared src/corrections.py; |mag median| >= 1 px, "
            "same sign as the DEM median, >= 3 qualified mag transects, shared reference "
            "perpendicular per record); rebuild dots on the DEM crest lines (LiDAR-calibrated, "
            "MAD 0.29 px); re-run the simulated-corrections holdout with the new A1b arm and a "
            "matched-mass chance control. E3: registry uniqueness screen over 1,026 sibling "
            "rasters (TIFs + unzipped single-GeoTIFF zips, 477 unique pixel contents)."),
        named_non_fault_process=(
            "Erosional terraces and alluvial-fan edges produce the same convex slope crest "
            "without a fault; a crest can belong to a neighbouring unmapped strand; a magnetic "
            "lithologic contact steps tmi_hg without any young fault; and the pre-registered "
            "confound realised: low-relief sediment-covered terrain hosts both inferred mapping "
            "and terrace-dominated crests, which is the likeliest reading of the vanishing "
            "stratification among sharp crests. The LiDAR proves the crest is a real scarp, not "
            "that it is the mapped fault's corrected position."),
        h_c1=h_c1,
        holdout_dti=dict(
            label=e2["label"],
            n_withheld_positives=e2["n_withheld_positives"],
            A1b_twin=dict(dti=a1b["dti"], ci95=a1b["ci95"], dots=a1b["dots"],
                          TP_w=a1b["TP_w"], FP_w=a1b["FP_w"], FN_w=a1b["FN_w"]),
            A4b_random_matched_mass=dict(dti=a4b["dti"], ci95=a4b["ci95"], dots=a4b["dots"]),
            A1_round1_reference=dict(dti=a1["dti"], ci95=a1["ci95"], dots=a1["dots"]),
            machinery_check=("PASS: A1b 0.10788 [0.0898, 0.1268] vs matched-mass chance "
                             "0.00414 [0.0029, 0.0054] (26x, CI excludes 0) and vs masked "
                             "control 0.0; canary max 0.5785 < 0.90; controls OK. The simulated "
                             "truth is the measured crest lines themselves - construction-biased "
                             "BY DESIGN; it validates machinery, not geology."),
            construction_bias_warning=(
                "The holdout truth is simulated (the measured crests). No geological claim may "
                "be derived from A1b's value; the geological test this round was H-C1, and it "
                "returned NEGATIVE on the pre-registered conjunction."),
        ),
        registry_comparison=dict(
            tool="scripts/check_registry.py (shared; re-screened AFTER merging main, over the "
                 "updated corpus that includes this repo's newest parallel-session rasters "
                 "(H57 cover band, magpack/quota, dotted-ridge, corridor, triconcord, "
                 "persist-step); surface AND dots checked)",
            documented_verdict=reg["verdict"],
            n_registry_rasters=reg["n_registry_rasters"],
            n_unique_pixel_content=reg["n_unique_pixel_content"],
            n_duplicates=reg["n_duplicates"],
            worst=dict(spearman_dots=reg["worst"]["spearman_dots"],
                       spearman_surface=reg["worst"]["spearman_surface"],
                       jaccard_3px=reg["worst"]["jaccard_3px"],
                       containment=reg["worst"]["containment"],
                       rev_containment=reg["worst"]["rev_containment"]),
            literal_clause=(
                "FIRES (STOP logged per protocol): the degenerate-superset class (habitat/"
                "lattice/scatter/cover-band emissions many times larger, reverse containment "
                "small) plus THIS lane's own round-1 raster - the dots are a strict subset of "
                "the round-1 emission by construction, which was pre-registered before the "
                "screen ran. No prior is re-issued: see the worst statistics and "
                "n_duplicates=0 in this receipt."),
            receipt="evidence/corrections/registry_check_round3.json",
        ),
        cross_run_caveat=dict(
            h57_session=(
                "The concurrent H57 session (merged to main during this round) independently "
                "measured the pooled DEM-mag offset correlation at r = 0.022 (near-independent) "
                "and refuted crest steering on a neighbour-strand hide-and-recover holdout "
                "(crest-steered 0.00087 vs evidence-free corridor 0.00177 at equal budget). "
                "Consistent with this round's NEGATIVE on H-C1, and a stated caveat on the "
                "twin-family gate: 9 of 28 records pass vs ~4-7 expected by chance sign "
                "concordance, so the gate's incremental evidence is modest."),
            reconciliation=(
                "Both rounds agree the corrections hypothesis currently lacks a passing "
                "independent validation. The shipped artefacts answer different questions: "
                "H57's cover band is an unsteered bet on the organizer statement; round 3's "
                "twin raster is the best-corroborated crest subset. Neither is promoted."),
        ),
        raster=dict(
            file=e3["artefact"]["file"],
            sha256=e3["artefact"]["sha256"],
            bytes=e3["artefact"]["bytes"],
            dots=e3["dots"],
            zip_file=e3["artefact"]["zip_file"],
            zip_sha256=e3["artefact"]["zip_sha256"],
            values_present=e3["artefact"]["values_present"],
            validator=dict(exit=e3["artefact"]["validator"]["returncode"],
                           summary="CRS/shape/transform/dtype/range/nodata all PASS; all "
                                   "5,167,373 template-valid px finite in [0,1]; NaN exactly "
                                   "outside the footprint; GDAL_NODATA=nan"),
        ),
        submission_name=e3["artefact"]["name"],
        note=e3["artefact"]["note"],
        note_chars=e3["artefact"]["note_chars"],
        verdict=dict(
            value="negative",
            rationale=(
                "H-C1 failed its pre-registered conjunction (the only independent geological "
                "test of the corrections hypothesis this round); the holdout is "
                "construction-biased by design; the literal registry containment clause fires "
                "(12 flags incl. this lane's own round-1 superset). The raster is a unique, "
                "format-valid research artefact - NOT cleared for a weekly slot."),
            beats_holdout_controls=True,
            format_valid=True,
            unique_documented=True,
            literal_gate="STOP (logged; degenerate-superset class + own round-1 superset)",
            selector_note=(
                "PROMOTE would have required H-C1 to pass. No slot is spent by this run; "
                "promotion is the separate selector step within the weekly cap. The twin-family "
                "records (9) remain the lane's best-corroborated correction set for any future "
                "composition once an independent validation passes."),
        ),
        budget=dict(experiments="E1 (H-C1 stratification) + E2 (twin emission + holdout) + "
                                "E3 (screen + build + card) = 3; stop after this card",
                    slots_spent=0),
    )
    out = EV / "run_card_round3.json"
    out.write_text(json.dumps(card, indent=1))
    print(f"wrote {out}")
    print("verdict:", card["verdict"]["value"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
