# What can—and cannot—be said about the claimed 0.2778

**Scope.** This note separates the official metric, a sibling-reported raster-construction observation, and the unsupported score attribution. It does not claim that the file scored 0.2778. No projection is a score.

## Evidence classes

| Class | What is supported |
|---|---|
| **ORGANIZER-CONFIRMED** | No submission-page receipt for the 0.2778 file is present in this repository. No score is organizer-confirmed here. |
| **USER-REPORTED / SIBLING-REPORTED** | The 0.2778 attribution and nearby leaderboard values. GEMSDOE54 reports a raster-level construction mechanism and a board observation; those reports are not an organizer receipt. |
| **ORGANIZER-SPEC** | The public problem page defines distance-weighted Tversky scoring with a 300 m triangular kernel, α=0.2, β=0.8, and the required GeoTIFF format. The staff forum reply says known USGS/INGENIOUS fault pixels are excluded from evaluation penalties. |
| **MEASURED HERE** | Current input hashes, grid facts, local format-validator results, and the local corrections-lane evidence in this repository. These are not competition scores. |
| **HOLDOUT-DTI** | A local catalogue-recovery diagnostic only; evaluator, withheld count, and CI must accompany every such value. It is not the hidden-new-fault score. |

## What the primary sources say

- **Official scoring and format:** [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). It defines a triangular kernel `k(d)=max(1-d/R, 0)` with `R=300 m`, and `DTI=TP_w/(TP_w+0.2 FP_w+0.8 FN_w)`. It says submissions are single-band float32, EPSG:32611, 100 m, values in [0,1], with null/NaN outside bounds. The page describes the supplied sample as predicting total fault absence.
- **Known-fault masking:** [DrivenData staff reply, forum thread 11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516). Staff say pixels corresponding to known USGS/INGENIOUS faults are masked/excluded and do not count toward penalty terms. This is a pixel-level statement; it does **not** say that a 200 m buffer around a known fault is automatically exempt.
- **The artifact's status:** [GEMSDOE32 page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html). The page identifies the H33-2-B2 artifact as **UNSCORED**, calls 0.2747 a model projection, and says no organizer score exists for artifacts in that repository. This directly blocks treating 0.2778 as a confirmed score.
- **Reported construction mechanism:** [GEMSDOE54 Run 2 summary](https://github.com/buffedlizard55-lab/GEMSDOE54/blob/main/RUN2-SUMMARY.md), section “The 0.2778 entry”. GEMSDOE54 reports that its child raster has 37,654 dots and equals a 40,199-dot parent minus the 2,545 parent dots within 2 px (200 m) of a USGS catalogue fault. It reports 5.8% of the child and 11.7% of the parent within 300 m of the catalogue. **That is a sibling's raster-level report, not an organizer score and not independently reproduced from the source rasters in this checkout.**

## A defensible mechanism hypothesis—not a score explanation

For unit-valued dots, let `N` be the number of predicted dots, `G` the number of positive truth pixels, `T=TP_w`, and `M` the sum of the best triangular-kernel proximity weight over predicted dots. The official definitions imply `FN_w=G-T` and `FP_w=N-M`, so:

```text
DTI = T / (0.2*N + 0.8*G + 0.2*(T-M))
```

This identity is algebra from the published metric, not an inference of any private labels or leaderboard score. Removing dots can improve DTI if it reduces false-positive mass more than it reduces true-positive cover; it can also hurt if removed dots were near newly labeled faults. The exact known-fault mask only removes the masked pixels themselves. A dot 200 m away is not automatically unpenalized: it can receive triangular credit only if it is within 300 m of a hidden truth pixel, and otherwise contributes false-positive cost.

Therefore the sibling-reported 200 m pruning rule is a plausible **mass/placement trade-off** to test. Its effect on a realized competition score cannot be deduced from the raster construction alone. The score attribution remains unverified, and there is no scientifically defensible causal explanation for why an unreceipted value “scored 0.2778.” The strongest supported answer is: the artifact embodies catalogue-distance pruning, but its claimed score is not established.

## Why the active corrections lane does not validate that claim

The active corrections run is recorded in [`evidence/run_card.json`](../../evidence/run_card.json). It is the latest corrections-lane card; the later `run_card_discovery_v1.json` is a different lane and is not the authority for this task. The current run's gate is negative: the one-dot primary triggers the literal >70%-within-3-px registry stop, and strict local template validation fails because 7,111,787 outside-mask cells are finite and the raster lacks the sample's NaN nodata tag. The sensitivity raster has the same format failure. No slot was used and no artifact is cleared.

The method-level values recorded in that run are `HOLDOUT-DTI (evaluator gems52-pooled-hide-v1; 48,080 withheld positives; 95% CI in evidence/run_card.json)`. They are copied from `evidence/holdout_corrections_v1.json`; no DTI was recomputed in this review. That holdout targets withheld **catalogue** components, not the organizer's hidden new faults, and the one-dot output was not separately scored. The receipt leaves `design.prevalence` null although `scripts/run_corrections_holdout.py` invokes `make_folds(... prevalence=0.00294 ...)`. The same script builds catalogue-derived snap inputs from `fold["visible"]` and does not restrict them to `fold["fit"]`, where the shared fold builder records the 4 px buffer. The specified spatial buffer is therefore not established for those inputs. The latest run card also has no per-feature canary receipt. Treat the values as exploratory, not admissible for promotion. The previous experiment budget is exhausted, so this note does not propose or perform another experiment.

## Remaining verification needed

1. A logged-in user should compare the hash-pinned bridge inputs against the actual competition data-tab downloads. The sample-mirror content differs from the official page's description of a total-fault-absence sample; see IR-56-001, IR-56-003, and IR-56-034.
2. A competition-page submission receipt would be needed before any value could be labeled **ORGANIZER-CONFIRMED**.
3. Do not select, repair, or submit any current TIFF based on this mechanism note. The active lane verdict is **NEGATIVE / STOP**.
