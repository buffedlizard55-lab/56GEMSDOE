# Standing brief — session of 2026-10-09 (H57 corrections run)

This file is the verbatim operating brief for this repository. Read it at the start of every
session before touching code: it defines the lane, the protocol, the evidence-labelling rules and
the deliverable.

## Lane (the only method this session may pursue)

Corrections lane: measure how far the catalogue sits from the evidence, then emit where the
evidence says the fault is. New-fault ground truth can lie within 300 m of a known trace as
"corrections or modifications to existing fault traces" (DrivenData forum thread 11516), and
known-fault pixels are masked pixel-exactly, so the catalogue line itself is not the target.
Hermant, Kiersnowski and Bellanger (Stanford Geothermal Workshop, 2025) measured USGS-to-refined
discrepancies up to 400 m in north-central Nevada. First deliverable: sample perpendicular
transects within ±400 m of every catalogue trace, locate the nearest crest of the DEM-curvature
scarp and of the magnetic-gradient ridge, publish the offset histogram, calibrated on 1 m LiDAR
where the crest is unambiguous. Where a consistent offset exceeds about two pixels, emit dots on
the evidence-defined trace. Train any learned component with a registration- and
omission-tolerant loss in the style of Mnih and Hinton (ICML 2012). **If offsets cluster under
two pixels, report that as the result and emit nothing from this lane.** Output the standard
validated GeoTIFF, uniqueness-checked against every earlier raster.

## Parallel-run protocol

1. **Lane.** Stay inside the method paragraph. Rank correlation > 0.90 with any registry raster,
   or > 70 % of dots within 3 px of one registry raster's dots, means drift: log it as a
   duplicate and stop. Check on the surface before placement and on the final dots.
2. **Reuse, don't rebuild.** Use the cached feature stack, the holdout evaluator and the
   submission writer. Holdout = hide-and-recover: withhold whole fault segments with a buffer,
   derive every catalogue-based feature only from the visible faults, mask visible faults
   pixel-exactly, score pooled DTI (α 0.2, β 0.8, 300 m triangular kernel). Fix a broken shared
   tool once, in the template; never keep a private fork.
3. **Label every number** as HOLDOUT-DTI (evaluator version, withheld positives, 95 % CI) or
   ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never a score.
4. **Leakage canary.** Test each feature alone on the holdout; AUC > 0.90 means leakage until
   proven otherwise.
5. **Run card.** End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator
   output; submission name + note ≤ 140 chars; verdict promote / negative. **Negative results are
   deliverables.**
6. **Budget.** Stop after 3 experiments or 2 hours. Promotion to a real competition slot is a
   separate selector step within the weekly cap.

## Standing product requirements

* The site must make the submission file obvious: a one-click download at the very top, with an
  unambiguous statement of whether it is OK to download and OK to submit.
* The raster must satisfy the form: single band, float32, every value in [0, 1], EPSG:32611,
  3292×3730, geotransform identical to `sample_submission.tif`. The live form rejected an earlier
  upload with "Predicted values must be in range [0, 1]" — caused by non-finite cells — so this
  project now exports all-finite rasters (zeros, not NaN, outside the emission).
* Every submission needs a unique name and a note ≤ 140 characters.
* An executive-summary subpage must explain exactly how to submit.
* Work line by line from official, verified sources; link them for manual review; flag
  irregularities; no hallucinations; no manual input required from the user.
* Core values: **Maximize P(Win)** and **Own the Outcome**.

## Official sources (for manual review)

* Competition: <https://www.drivendata.org/competitions/306/competition-doe-gems/>
* Problem description: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
* About / resources: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/>
* Data (login-gated): <https://www.drivendata.org/competitions/306/competition-doe-gems/data/>
* Reference solution: <https://github.com/drivendataorg/gems-prize-reference-solution>
* GeoDAWN survey: <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
* INGENIOUS: <https://gbcge.org/current-projects/ingenious/>
* EPSG:32611: <https://epsg.io/32611>
* Tversky index: <https://en.wikipedia.org/wiki/Tversky_index>
* Forum thread 11516 (masking of known faults):
  <https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516>
