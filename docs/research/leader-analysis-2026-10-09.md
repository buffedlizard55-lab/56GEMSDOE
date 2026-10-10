# Why the 0.2778 file scored well, and can this lane beat it?

Session 2026-10-09 · lane: corrections · every number below is either (a) a formula checked against the official
page, (b) a value computed by the code cited in the row, or (c) a figure copied from a named public page and labelled
with its evidence class. Nothing here is a score for this lane's file.

## 0. Evidence classes used

| label | meaning here |
|---|---|
| **ORGANIZER-CONFIRMED** | none exists for anything discussed below |
| **HOLDOUT-DTI** | our evaluator (`gems52-pooled-hide-v1`), withheld positives and CI stated |
| **USER-REPORTED** | a number the user typed from a site or board; not checked |
| **CLAIM (site)** | a number a sibling site publishes about itself; not checked |
| **MEASURED** | computed by a script in this repo, receipt named |
| **DERIVED** | arithmetic from the official formula, with the code that checks it |

## 1. Verification status of the numbers in the brief

| number | where it appears | status | evidence |
|---|---|---|---|
| 0.2778 for `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` | user list; the GEMSDOE32 site | **USER-REPORTED** | The GEMSDOE32 page [docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) names the file `gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`, the same hash stem, and says it is **UNSCORED**: "NO ORGANISER SCORE EXISTS for this or any artifact in this repository". Its own projection is 0.2747 and is labelled a model. So 0.2778 has no receipt we can read. |
| 0.3262 (#1, nchuzhoy) | GEMSDOE32 page | **CLAIM (site)** | Same page, "read 2026-10-04 from the official page". Not re-read here. |
| 0.3774, 0.3195 | user brief | **USER-REPORTED** | Conflict with the 0.3262 above. Flagged, not resolved. |
| official leaderboard values | — | **UNVERIFIED in this sandbox** | The [leaderboard page](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) returned only "Loading..." to our fetch tool; the values are rendered client-side. Manual check needed. |
| metric definition | [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | **verified** this session | Fetched and read: triangular kernel `k(d)=max(1-d/R,0)`, R = 300 m, α = 0.2, β = 0.8, TP_w / FP_w / FN_w definitions, worked example TP_w 3.00, FP_w 1.89, FN_w 2.00 → 0.60. Our `src/gems56/metric.py` gives 0.602652 for that example (checked below). |
| submission format | same page | **verified** this session | float32, single layer, 100 m, EPSG 32611, "values between 0 and 1", "data outside the bounds is null or nan". |

## 2. Why the high-scoring files score high (mechanism, DERIVED)

The official metric is `DTI = T / (T + α·FP_w + β·FN_w)` with the distance-weighted terms of the page. Two
consequences follow directly from the formula and are the whole story:

1. **Recall is weighted four times precision.** β = 0.8 on misses against α = 0.2 on false-positive mass. A unit of
   emitted mass costs 0.2 unless it covers a truth pixel. So the optimum is to emit a *lot* of mass near where
   hidden faults are, and accept that much of it is wrong.
2. **The 3-px kernel turns a dot into a 29-cell disc of credit.** Each truth pixel is credited with the best cover
   within 300 m. A dotted field of ~37k pixels (0.3% of the 12.28 M-cell grid) therefore covers a large share of the
   plausible fault corridor while staying cheap in FP mass.

The break-even credit per emitted pixel is `0.2·DTI` (metric.py docstring, identity (ii)). At DTI 0.2778 that is
**0.0556 per pixel**; at the 0.3262 claimed leader it is 0.0652. A file of 14 pixels cannot earn that much total
credit (section 3).

The GEMSDOE32 site's own explanation (CLAIM, same page) agrees with this arithmetic: thinning a thick surface
raises credit per pixel, and the group measured the break-even at 0.0548. We did not re-derive that measurement.

## 3. The ceiling for a sparse file (DERIVED, code-checked)

Let `p` be the prediction, `S = Σp`, `M = Σ p·max_g k`, `G` the truth set, and `K = Σ_offsets k(d)` over the 29
lattice offsets inside the 3-px disc. Because each truth pixel's credit is at most the sum of kernel-weighted
predictions within 300 m of it,

    T = TP_w ≤ min(|G|, S·K),   and   S − M ≥ 0,

so for any prediction

    DTI ≤ T_max / (0.2·T_max + 0.8·|G|),   T_max = min(|G|, S·K).

`K = 9.3803` (computed with `gems56.metric.OFFSETS`, `.venv/bin/python`, this session).

| prediction | |G| = 558 | |G| = 1,000 | |G| = 12,691 | |G| = 60,988 |
|---|---|---|---|---|
| 14 dots (this lane's file) | **0.2777** | 0.1589 | 0.0129 | 0.0027 |

**Reading:** a 14-dot file can exceed 0.2778 only if the hidden truth set has fewer than about **558 positive
pixels** (~56 km of 100 m-wide trace). `|G|` for the organizer's private test set is not published. The only
figure in circulation is 12,691 px, which is the GEMSDOE32 *inference* (CLAIM), not an organizer count. This is
the single most important negative result in the session: the lane's file is capped far below the leader under
any |G| that is plausible for a regional fault test, independent of how well its dots are placed.

Scope of the check: the bound is algebra, not a measurement, so it does not depend on the holdout. The holdout
(section 4) uses different arms (about 3,700 dots per fold, catalogue truth) and is not a test of the 14-dot file.

## 4. What this lane's own holdout says (HOLDOUT-DTI)

Source: [evidence/holdout_corrections_v1.json](../../evidence/holdout_corrections_v1.json), evaluator
`gems52-pooled-hide-v1`, α 0.2, β 0.8, R 300 m, 4 folds, 48,080 withheld positives per arm.

| arm | DTI | 95% CI |
|---|---|---|
| A_as_is (catalogue, no snapping) | 0.00000 | [0, 0] |
| B_snap (dots snapped to evidence crest) | 0.00016 | [0.00000, 0.00045] |
| C_snap_sub | 0.00005 | [0.00000, 0.00011] |
| D_jitter (control) | 0.00021 | [0.00000, 0.00051] |

B_snap − D_jitter = −0.00016, CI [−0.00042, +0.00002]: no detectable benefit of evidence-placement over a random
jitter. The holdout also cannot reward genuinely new faults (catalogue truth only; IR-56-004).

## 5. Implication for the strategy

* A **sparse, evidence-placed** emission (this lane) is capped by the ceiling in section 3 and measured near zero
  on the holdout. It cannot be the route to 0.2778 or above.
* The leader's route is **dense, recall-weighted emission** over the plausible fault field. Its validity rests on
  a detector that finds unmapped faults, which is outside this lane's method paragraph.
* Therefore the honest outputs of this lane are: a format-valid, hash-unique file labelled **negative**, and the
  ceiling above. Spending a weekly slot on the 14-dot file is not recommended.

## 6. Checks run (line by line)

1. `metric.dti` worked example → 0.602652 (official page rounds to 0.60). Test: `tests/test_metric.py`.
2. `OFFSETS` count 29, `K` 9.3803 → the bound table above.
3. Repeat of the lane pipeline: `measure_offsets`, `lidar_calibration`, `run_corrections_holdout`,
   `cluster_gate_control`, `build_corrections_submission` regenerated both rasters byte-for-byte
   (sha256 `e3285854…` and `65635a53…`, see the run card).
4. Input pins: `existing_faults.tif` `7ba308cc…`, `sample_submission.tif` `2176d08e…`, `training_features.tif`
   `4371c82e…` all match `registry/input_pins.json`. LiDAR layer `h52_scarp3m_100m.tif` `b5e53d67…` matches
   `data_manifest.json`.
5. Uniqueness: see the run card and `evidence/lane_uniqueness_*.json` (regenerated with the full corpus; see IR-56-015).

## 7. Sources (all fetched or read this session)

* DrivenData problem page (metric, format): https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* DrivenData leaderboard (not readable here): https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* GEMSDOE32 site (claimed 0.2778 file, UNSCORED): https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html
* Input mirror used for the pinned inputs (sibling repo, third-party copy of the data tab, not an organizer source):
  https://github.com/buffedlizard55-lab/GEMSDOE/tree/main/data/bridge
* LiDAR layer source (sibling repo): https://github.com/buffedlizard55-lab/GEMSDOE48/tree/main/data/external
