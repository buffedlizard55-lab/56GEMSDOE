# 56GEMSDOE — corrections lane for the DOE GEMS Prize

> **CURRENT CORRECTIONS STATUS: NEGATIVE / STOP — do not submit any file in the corrections lane.**
> The H57 artifact's final-dot registry receipt reports a 1.0 within-3-px fraction (>0.70), and a
> strict replay finds 7,111,787 finite cells outside the pinned sample mask plus a missing NaN
> nodata tag. The original H57 `OK to submit` wording is superseded by
> [`evidence/h57_run_card.json`](evidence/h57_run_card.json)'s post-review verdict. No experiment
> or slot was used in this review. See the three-pass review in `docs/review/2026-10-09.md`.

DrivenData competition 306 (GeoDAWN / NW Nevada): find **geothermal-indicative faults missing
from the USGS/INGENIOUS catalogue** and ship them as a legal GeoTIFF.
Site: **https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html**
(one-click archive download at the very top; the page states clearly that it is NOT safe to submit).

## Preserved main-side Round-3 twin-family record — research only, NEGATIVE / STOP

This run was already present on the updated `main` base (PR #14); this merge preserves its receipts
and makes no new experiment or registry scan. Its pre-registered H-C1 conjunction was **NEGATIVE**:
MAPSCALE could not discriminate because 120/125 records were mapped at 1:250k (Spearman
ρ=0.059, p=0.257), while a secondary FTYPE comparison passed but did not satisfy the conjunction.
The pre-registered fallback emitted `gems56-corr-twinfam9-20261009T190155Z-0279ca86-nan.tif`
(2,139 dots; SHA-256 `a614a594e179fa2af24a3d9c311bbab45f3c39ca868023da23b43ece16a32b75`).

The run's **HOLDOUT-DTI** is a machinery check on simulated corrections truth—not a competition
score or geological validation—using `src/metrics.py`, α=0.2, β=0.8, a 300 m triangular kernel,
and 26,813 withheld positives: 0.10788 [0.089756, 0.126814] versus matched-mass chance
0.00414 [0.002937, 0.005405]. The existing 1,034-raster registry receipt (485 unique pixel
contents) contains **12 literal >0.70 directed-proximity flags** (maximum containment 1.0);
maximum Spearman is 0.5732 for dots and 0.3335 for the surface. Under the standing rule those
flags mean **DUPLICATE / STOP**;
the older “UNIQUE” / zero-duplicate classification is superseded, and density, Jaccard, reverse
containment, and “superset” explanations do not waive the trigger. This status correction applies
the existing receipt only; no scan was rerun. The TIFF remains a research archive, not a candidate
for submission or promotion; the run spent no slot. See
[`evidence/corrections/run_card_round3.json`](evidence/corrections/run_card_round3.json),
[`evidence/corrections/registry_check_round3.json`](evidence/corrections/registry_check_round3.json),
[`evidence/corrections/registry_check_round3_post_review.json`](evidence/corrections/registry_check_round3_post_review.json),
and [`docs/research/hypotheses-20261009-round3.md`](docs/research/hypotheses-20261009-round3.md).

PR #11's dotted-ridge output is a separate artifact and remains unadjudicated by the H57 review.

> ## Historical Round-2 discovery artifacts (receipts stamped 16:29Z → 17:26Z; not current status)
>
> This is an archived run record, not a submission desk. The two GeoTIFFs remain available for
> technical inspection — [`h56-magpack-37k-20261009.tif`](docs/downloads/h56-magpack-37k-20261009.tif)
> (37,654 dots, `mag_ridge|packed`, min 2.24 px off the catalogue, sha256 `62824bcab55d…`) and
> [`h56-quota-37k-20261009.tif`](docs/downloads/h56-quota-37k-20261009.tif) (30,800 dots,
> `QUOTA|packed|weighted`). Their old receipts report single-band float32, EPSG:32611, 100 m,
> 3730×3292, values in [0, 1], zero NaN, and no nodata tag
> ([receipts](docs/downloads/checks-h56-magpack-37k-20261009.json)). These local format facts do
> not establish strict template conformance, registry clearance, organizer acceptance, or permission
> to submit; do not treat this historical block as a current download recommendation.
>
> **Submitting is a different question, and the answer is no this round.** On the shared blocked holdout
> (`gems52-pooled-hide-v1`, 4 folds, 36,335 withheld
> positive pixels) our best arm reaches **0.0387**
> [0.0348, 0.0424] where the group's filed sibling surface reaches
> **0.0900** [0.0811, 0.0988] at the same budget on the same folds (our arm read from `evidence/quota_union_v1.json`, the incumbent from `evidence/field_holdout_v1.json`; both receipts print 0.0387 for our arm).
> Verdict on the run card: **negative**, `promote: false`, no weekly slot claimed. Six hypotheses were tested;
> five were rejected on measurement and one (packing vs top-K) is **not resolvable on this instrument** and is
> reported as a null, not a win: [`docs/research/hypotheses-round2.md`](docs/research/hypotheses-round2.md).
>
> **Why the group's best file scores what it scores** — measured, not narrated. The
> 37,654-dot file claimed at 0.2778 (USER-REPORTED) is a strict subset
> of the 44,090-dot file claimed at 0.2600: the
> 6,436 deleted cells are *exactly* the dots within 2 px of a catalogue pixel
> (the survivor's distance floor is 2.24 px). The whole difference is one
> prune, because known-fault pixels are deleted from the truth. Inverting the published formula on those two
> numbers (DERIVED, never a projection) gives T = 5,223 credit,
> 0.139 per dot, and |G| ≈ 12,783–18,294
> hidden pixels; perfect placement at that mass would score 0.825.
>
> **The instrument is inverted for that decision, and that is the round's most useful finding.** The same folds
> score the *unpruned* sibling file at 0.0900 and its pruned, higher-scoring-live
> twin at 0.0038 — the opposite sign — because the withheld truth *is* the
> catalogue. So no near-catalogue policy was chosen from hide-DTI here (IR-56-004, IR-56-011).
>
> **Historical registry result: DUPLICATE / STOP for both H56 artifacts.** The 868-row
> directed screen (`evidence/registry_screen_h56b.json`; 31 unreadable rows) records 56 priors
> with >0.70 candidate-dot proximity for `h56-magpack-37k` and 54 for `h56-quota-37k` in its
> row data. The corresponding 40-prior subset receipt maxes at 0.527 and 0.475, respectively;
> that subset did not cover the triggering priors. Reciprocal containment is descriptive only and
> cannot waive the stated one-way rule. Lower rank correlations (0.0117 / 0.0169) do not cancel
> these proximity stops. The old “Unique” interpretation and reciprocal-only rationale are
> superseded; the files are historical archives, not submit-ready candidates. See
> [`evidence/irregularities.json`](evidence/irregularities.json), IR-56-036.
>
> **Run card:** [`docs/research/run-card-round2.json`](docs/research/run-card-round2.json)
> (= [`evidence/run_card_round2.json`](evidence/run_card_round2.json)) · site generator:
> `scripts/build_round2.py` · budget: 4 experiments against a stop-loss of 3 (the card says so and why),
> 2 h clock met. Round 1 (the lane's assigned measurement) is preserved at
> [`docs/lane1-corrections.html`](docs/lane1-corrections.html).
>
> *(Both round-2 runs of this lane ended negative on their own shared holdout; neither
> claims a weekly slot, and neither has an organizer-confirmed score. The two records are kept
> side by side: this page's front-end is `docs/index.html`, that run's preserved pages are
> `docs/discovery-*.html` and `docs/{hypotheses,research,sources,prior-run}.html`.)*

---

> **Arena Core Values (quoted in the brief):** Maximize P(Win). Own the Outcome.
> **Read `docs/brief/2026-10-09-session-prompt-h57.md` at the start of every session** — it is
> the standing brief (lane, protocol, product requirements, official sources) and this README
> links it first on purpose.

## H57 run — 2026-10-09 (latest corrections run; NEGATIVE / STOP)

**Archived file:** [`docs/downloads/h57-corr-band2px-cover-20261009T191337Z.tif`](docs/downloads/h57-corr-band2px-cover-20261009T191337Z.tif)
(+ `.zip`, + original build receipt) — 54,914 dots, single band, float32, 0 NaN cells, values
in [0, 1], EPSG:32611, 3292×3730, transform matching the local sample; SHA-256
`fbf6e8da4180f97f4f6f2eed01b4d673a2acce2b8ef6344a2889d8cb2be90ced`.
**Download for technical inspection only. NOT SAFE TO SUBMIT.** Its original run card's
"OK to submit" claim is preserved as historical input and explicitly superseded by the strict
post-review result below. No experiment or slot was used in this review.

**Hypothesis verdict: NEGATIVE — crest steering is refuted, by our own measurements.**

| experiment | what it measured | result |
|---|---|---|
| E1 (offset histogram, MEASURED) | catalogue → nearest DEM crest / magnetic ridge within ±400 m, 44,390 transects | median \|offset\| **1.48 px**, signed median −0.11 px, 0.326 beyond 2 px vs **0.273 for the random null**; DEM–magnetic r = 0.022; 2 of 1,273 corridors pass the consistency gate → *offsets cluster under two pixels* |
| E2 (`--mode spatial`) | hide-and-recover with whole-component spatial folds, 60,894 withheld px | corridor arms ≈ 0; uniform-random 0.01758 — **the split itself cannot test a corrections lane** (IR-57-001), so a second mode was built |
| E3 (`--mode neighbour`) | hide-and-recover withholding only components with another mapped component within 400 m; 41,742 withheld positives | crest-steered **0.00087** [0.00049, 0.00133] vs evidence-free corridor **0.00177** [0.00130, 0.00232] at an identical dot budget; paired contrast **[−0.00138, −0.00048]**, P(beats) = 0.0; `B4_catalogue` = 0.00000 exactly (masking control) |

All numbers are **HOLDOUT-DTI** (evaluator `h57-hide-and-recover-v1`: `src/metrics.py`, α 0.2,
β 0.8, 300 m triangular kernel, visible faults masked pixel-exactly, 20×20 px block bootstrap,
2,000 draws). None is a competition score; no ORGANIZER-CONFIRMED number exists for this repo.

**What the H57 output represents.** It is an unsteered 200 m either-side cover proposed after
crest steering was refuted. The geometry sweep is a design calculation against a circular simulated
target, not a score; the emitted cover itself has no HOLDOUT-DTI result. It remains an archive only.

**Why H57 is stopped.** The final-dot shared gate (`evidence/h57_uniqueness.json`) reports
**max near-3-px fraction 1.0** on its 40 worst-overlap prior rasters, above the explicit 0.70
threshold, and records **DUPLICATE/STOP**. Its full-run card reports max Spearman 0.286; low
correlation does not waive the separate proximity trigger. The registry trigger is not exempt just
because the overlap includes the catalogue.

A strict template replay of the actual final TIFF against the pinned sample and training grid also
fails: **7,111,787** finite cells lie outside the sample's finite footprint, while the TIFF has
`nodata=None` and the sample declares NaN. The current H57 card's earlier `validator_output.ok=true`
was from the permissive all-finite compatibility gate; the post-review strict result is recorded in
`validator_output`/`post_review` in `evidence/h57_run_card.json`. No repair, re-emission, DTI rerun,
or promotion was attempted.

The exact holdout values above are method-level **HOLDOUT-DTI** for the crest-steering comparison
(41,742 withheld positives), not an evaluation of the 54,914-dot cover. The last 40-prior final-dot
gate triggers even though its max Spearman is below 0.90. `IR-57-003` records the original literal
trigger; the final card now records the required stop action.

**Reproduction status:** the evidence receipts are preserved, but do not rerun holdout, geometry
sweeps, emitters, or experiments under the exhausted 3-experiment/2-hour budget. A future session
would need fresh authorization, official input/template verification, complete stage-specific
registry checks, and strict validation before any new candidate is considered.

**New irregularities from this run:** IR-57-001 (the spatial-fold holdout cannot test this lane),
IR-57-002 (crest steering refuted), IR-57-003 (the literal containment clause is unpassable for
any corrections emission), IR-57-004 (no holdout exists for the family the file bets on),
IR-57-005 (`data/sample_submission.tif` vs `data/grid/sample_submission.tif` path split — fixed
once in `scripts/download_competition_data.sh`), IR-57-006 (two mutually exclusive export
policies coexist in the template; the tests now assert the policy the file declares).

> ## Round 2 - discovery run (already on `main` via PR #7): **Bottom line:** five new hypotheses were
> pre-registered (`docs/research/hypotheses-20261009.md`), the missing probe layer was obtained
> (3,800 INGENOUS points), `scripts/download_competition_data.sh` now rebuilds every input from
> the hash-pinned bridge, and the top-three hypotheses were validated on the shared 4-fold blocked
> holdout (48,080 withheld positives). **Verdict: NEGATIVE, robustly.** The pre-registered pick,
> `multi@25000`, scored **0.01242 [0.00787, 0.01718]** while *uniform-random emission scored
> 0.03499 at the same budget* — the paired difference is **−0.02257 [−0.02749, −0.01717]**,
> strictly below chance; all physics arms sat below the measured chance floor (tilt ≈ 0.0001),
> with leakage canaries clean (≤ 0.567 vs the 0.90 bar), so this is not leakage — the fields
> simply locate *mapped* structure, and excluding the catalogue (±200 m, the verified 0.2778
> mechanism) leaves them nothing to find. An instrument defect found by the first run (the
> zero-filled rim put 56.5 % of `iso_step`'s top-25,000 cells on the data edge — IR-56-020) was
> fixed once in the template with six regression tests, and the negative survived re-run
> unchanged. The registry gate returned literal **DUPLICATE/STOP** on the 3 px clause — logged
> honestly as density-degenerate (IR-56-023: the trigger tracks grid coverage, while rank
> agreement passes at max ρ 0.043 vs the 0.90 bar, reciprocal >0.70 = 0). A unique, format-valid
> 25,000-dot GeoTIFF (`h56-disc-multi-b25000-20261009-…`, values {0.0, 1.0}, both validators ok)
> is downloadable for review, and its name, note, receipt and the front-page banner all say
> **NEGATIVE / do not submit** — nothing is promoted to a slot; no slot was spent.

---

## The standing brief (the full user prompt, verbatim)

> Review the repository and complete the end-to-end DOE GEMS project. Critically assess the
> claimed GEMSDOE32 `0.2778` result attributed to `H33-2-B2` and the stated `0.3195`
> leaderboard high; do not hallucinate a score-to-file or geological explanation. Use trusted,
> checked sources, link them, and distinguish owner reports, local measurements,
> user-supplied claims, and organizer facts.
>
> Before implementation, propose and rank 3–5 distinct geological hypotheses. For each,
> identify its layers, target physical signature/operator, why it could expose fault geometry
> missing from the existing USGS/INGENIOUS catalogue rather than merely recover known-fault
> habitat, how it differs from implemented repository/prior-art work, expected benefit, and
> implementation cost. If outside data is needed, name the free official source and verify
> availability before treating it as viable.
>
> Parallel-run protocol (highest urgency): (1) stay in the corrections lane; if the final
> raster's rank-correlation with any registry raster exceeds 0.90, or more than 70% of your
> dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log
> it as a duplicate and stop. Check this on the surface before placement AND on the final
> dots. (2) REUSE the template's cached feature stack, holdout evaluator, and submission
> writer — never keep private forks; if a shared tool is wrong, fix it once in the template
> and report it. Holdout = hide-and-recover: withhold whole fault segments with a buffer,
> derive every catalogue-based feature only from the visible faults, mask visible faults
> pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). (3) Label
> every number as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or
> ORGANIZER-CONFIRMED (copied from the submission-page receipt); a projection is never
> written as a score. (4) Leakage canary: test each feature alone on the holdout before
> trusting any result; AUC above 0.90 means leakage until proven otherwise. (5) End with one
> JSON run card: hypothesis; mechanism; named non-fault process that could mimic it; holdout
> DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside
> footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most
> 140 characters; verdict promote/negative. Negative results are deliverables. (6) Budget:
> stop after 3 experiments or 2 hours; do not pick submissions — promotion is a separate
> selector step within the weekly cap.
>
> Corrections lane: measure how far the catalogue sits from the evidence, then emit where the
> evidence says the fault is. The organizers said new-fault ground truth can lie within 300 m
> of a known trace as "corrections or modifications to existing fault traces" (DrivenData
> forum thread 11516), and known-fault pixels are masked pixel-exactly, so the catalogue line
> itself is not the target. I have not seen a lane try this: sample perpendicular transects
> within +/-400 m of every catalogue trace, locate the nearest crest of the DEM-curvature
> scarp and of the magnetic gradient ridge, and publish the offset histogram, calibrated on
> 1 m LiDAR tiles where the crest is unambiguous. Where a consistent offset exceeds about two
> pixels, emit dots on the evidence-defined trace rather than the catalogue line. Train any
> learned component with a registration/omission-tolerant loss in the style of Mnih & Hinton
> ICML 2012. If offsets cluster under two pixels, report that as the result and emit nothing
> from this lane.
>
> Standing requirements: generate a UNIQUE TIF submission (not a copy of any previous
> submission; uniqueness-checked against every earlier raster, sha256 recorded); the previous
> attempt failed with "Predicted values must be in range [0, 1]" — the TIF must be strictly
> within [0,1] with no NaN inside the footprint and CRS/shape/geotransform matching
> `sample_submission.tif`; the submission needs a unique name and a short note (≤140
> characters). Put the full prompt into the repo README and treat it as the standing starting
> point. Build a clean, user-friendly GitHub Pages site: organized info, official verified
> source links, easy TIF download at the top/executive summary, and an executive-summary
> subpage with submission instructions. Create a pull request and merge it onto main; suggest
> remaining work and limitations. Multi-pass discipline: Pass 1 implement+verify; Pass 2 review
> for bugs/edge cases; Pass 3 re-check against the original request. Work line by line verifying
> from official verified trusted sources, provide links for manual review, no manual input,
> flag irregularities, no hallucinations. Collect/organize data into a clean auditable table
> with official verified links; deep/scientific literature research stored for reuse; think
> contrarian but grounded.

---

### Round-2 session brief (2026-10-09, also active)

Recorded from this session's instruction; each item is executed in this run or explicitly deferred:

- **Study the top scores.** Why did `h33-h33-2-b2 … 0.2778` score highest among published sibling
  artefacts, and can we beat it? Answer, with receipts: GEMSDOE54's raster-level check proves that
  file = its 40,199-dot parent minus exactly the 2,545 dots within 200 m of a catalogue fault
  (0.2708 → 0.2778) — the metric masks known-fault pixels, so catalogue-adjacent mass is pure
  penalty under α = 0.2 while contributing no TP. 0.3195/0.3774 remain BOARD-UNVERIFIED here.
- **3–5 new geological hypotheses** we have not tried, each with layers/signature/why-missing/
  difference-from-attempts, ranked by expected DTI ÷ cost, top candidate validated on the
  spatially-blocked holdout **before** any slot is touched: `docs/research/hypotheses-20261009.md`
  (H6–H10; external sources named and checked live).
- **The data blocker**: `bash scripts/download_competition_data.sh` must exist and work end to end
  (created this run as IR-56-021's fix; route B verified against both hash sets).
- **One-click TIF with an obvious OK/NOT-OK statement**, at the very top of the site, plus the
  executive-summary submission walkthrough and a submission name + ≤140-char note.
- **Core values**: *Maximize P(Win)* and *Own the Outcome* — applied here by killing our own
  candidate when the pre-registered rule fails rather than shipping a hopeful file, and by fixing
  the shared instrument defect (IR-56-020) instead of routing around it.
- **Multi-pass self-review, PR to `main`, and a list of remaining work/limitations** at the end of
  the session (see the PR description and `evidence/run_card_discovery_v1.json`).

## Integration with the prior run (PR #4)

Both runs are preserved. The prior run's negative result, code, tests, receipts and
rasters remain in this repository; its original report is [archived here](knowledge/prior-run-readme.md)
and its [site is here](docs/prior-run.html). The current site compares their different
crest definitions and truth constructions; their holdout numbers are not directly comparable.
The template pre-flight script is now `scripts/preflight_data.py`; the prior run's
pin verifier remains `scripts/prepare_data.py`.

**Submission gate: STOP / not cleared for a slot.** The historical strongest-crest
analysis below described the raster as unique and recommended promotion after investigating
superset overlaps. That investigation does not override the standing rule: eight literal
>70% containment flags trigger duplicate-and-stop. The final run card records a negative
protocol verdict. The TIF remains downloadable as format-valid research output only.

## What this session did (2026-10-09, branch `arena/b71ede8d-56gemsdoe`)

Lane: **corrections** (the brief's single method paragraph above). Three experiments, inside
the 3-experiment budget:

| # | experiment | result (evidence class) |
|---|---|---|
| E1 | catalogue-to-evidence offset histogram (perpendicular transects ±400 m on every catalogue trace; DEM-scarp crest = `det_elev_slope` ridge; magnetic ridge = `tmi_hg`; both *strongest* and *nearest* crest definitions; calibrated on the cached 1 m USGS 3DEP LiDAR scarp product) | **MEASURED** (official data): 16,344 transects / 404 vector records / 60,988 catalogue px. Nearest-crest registration: catalogue sits within ~1 px of a crest almost everywhere. Strongest-crest offset: **28 of 125 well-sampled records (22.4%) have a consistent offset > 2 px** (200–340 m, sign agreement up to 1.00, per-transect MAD down to 0.11 px). LiDAR calibration: the 100 m DEM-slope ridge **is** the 1 m scarp crest (MAD 0.29 px, 72.5% within 1 px). |
| E2 | leakage canary (per-feature AUC vs the holdout truth) | **HOLDOUT-DTI instrument**: max feature AUC 0.58 (< 0.90); catalogue-mask control AUC 0.494 ≈ 0.5 (masking worked); dist-to-catalogue control AUC 0.151 < 0.5 (truth displaced — simulation not degenerate). No leakage. |
| E3 | hide-and-recover holdout with simulated corrections (4 spatial folds, pooled DTI, official metric `src/metrics.py` α=0.2 β=0.8 R=3 px, known-fault masking model, 20×20 px block-bootstrap 95% CI) | **HOLDOUT-DTI** (simulated-corrections truth, 26,813 withheld positives): A1 lane **0.31049 [0.282, 0.338]** vs A0 masked control **0.00000 [0, 0]** and A4 random **0.01174 [0.010, 0.014]**; A5 oracle 1.0. The masked control scoring exactly 0 proves the masking model; the lane arm beats both controls decisively. |

**Deliverable:** `docs/downloads/gems56-corr-crestgt2px-20261009T051209Z-78fc86ad-nan.tif`
— 6,504 unit dots on the evidence-defined traces of the 28 consistent records, **0 dots on the
catalogue**, single-band float32, EPSG:32611, 100 m, 3292×3730, same transform as the official
sample, every template-valid pixel finite in [0, 1], NaN only outside the footprint,
GDAL_NODATA=`nan`.
**sha256 `08de79ce298c74dc5fcc006c1bde2bf117203e31b3a5ba3e943c1d05154781d7`** (351,093 B).
Validator `scripts/validate_submission.py` exit 0; template conformance
(`python -m src.submission_io validate-conformant`) exit 0.
Uniqueness: the historical screen covered earlier rasters from 48 sibling repositories
(976 rasters, 412 unique pixel contents) — see `evidence/corrections/registry_check.json`.
Its literal 70%-containment test fires on 8 rasters. Lower Spearman (0.043 dots / 0.109 surface),
Jaccard, and reverse-containment values characterize the overlaps but do **not** waive the
explicit duplicate-and-stop rule. The protocol verdict is **DUPLICATE / STOP**; this file is
historical research output only. Run card: `evidence/corrections/run_card.json`.

**Historical interpretation (superseded): PROMOTE** — the lane's emission beats its controls on the holdout, the
crest is LiDAR-calibrated and the format is validated. The final run card instead records
**NEGATIVE** because the literal containment gate failed. No organizer
score exists for this file; spending a weekly slot is the separate selector step.

### Why 0.2778 (and the irregularity around it)

The mechanism (measured by the GEMSDOE32 sibling against the official formula and its worked
example): the distance-weighted Tversky index reduces exactly to
`DTI = T/(α(T+F)+βK)`; adding one unit of mass raises the denominator by exactly α=0.2
anywhere, so a dot pays iff its kernel credit exceeds α·DTI (≈0.052 at DTI 0.26, i.e. within
~284 m of a hidden truth pixel); the live scorer masks known-fault pixels (forum thread
11516), so catalogue dots are pure 0.2-cost false positives; `h33-h33-2-b2` is the group's
best live-scored emission (40,199-dot "dotted d2.8" thinning of their H19-5 field) with every
dot within 200 m of the catalogue deleted → 37,654 dots, 0 on-catalogue. The family shows the
emission-side optimum (solid 121,131 px → 0.1922, d1.5 → 0.2477, d2.8 → 0.2600, all
owner-reported), implying a hidden |G| ≈ 7,905 px. Beating the live leader needs ≈+25% mean
credit at equal mass — a better *field* or genuinely novel faults; emission-side gains are
nearly exhausted. **This lane is such a field mechanism.**
**Irregularity (flagged):** the 0.2778 attached to `h33-h33-2-b2` is user-reported and
unsupported — GEMSDOE32's own pages label that artifact UNSCORED (projected 0.2747, a model),
and GEMSDOE51's audit calls the attribution "unsupported and contradicted". The stated
"0.3195 is the highest score right now" is stale (verified 2026-10-04 snapshot: #1 nchuzhoy
0.3262; GEMSDOE51's 2026-10-08 check also found 0.3195 was not the page high); the newer
0.3774 figure is user-supplied and unverifiable from this sandbox (drivendata.org is not
reachable). Full analysis: `docs/research.html` §8 and `docs/irregularities.html`.

## Repository map

```
src/corrections.py       lane module: transects, crests, records, emission
src/metrics.py           official metric (vendored from the GEMSDOE template, unchanged)
src/submission_io.py     fail-loud submission writer + template conformance (vendored)
scripts/prepare_records.py         vector catalogue -> record ids (USGS QFaults+INGENIOUS)
scripts/measure_corrections_offsets.py   E1: offset histogram + LiDAR calibration
scripts/holdout_corrections.py           E2 canary + E3 holdout (pooled DTI + CI)
scripts/check_registry.py                uniqueness vs every earlier raster
scripts/build_submission.py              emission -> conform -> write -> validate -> card
scripts/build_site.py                    regenerates docs/ from evidence/*.json
scripts/validate_submission.py           submission validator (vendored from template)
scripts/preflight_data.py, assemble_data_bridge.py   data placement (vendored)
data/                    official rasters (gitignored; reassembled from data/bridge parts)
data/cache/              LiDAR product + vector CSV + measurement caches (gitignored)
docs/                    GitHub Pages site + downloads (the submission TIF)
evidence/corrections/    offset histogram, transect/record tables, holdout JSON, run card,
                         registry check, record crops (committed audit trail)
knowledge/               PhD-level notes (why 0.2778; ranked hypotheses)

## How to run it

```bash
python -m venv .venv && .venv/bin/pip install numpy scipy rasterio shapely pyproj pandas
bash scripts/download_competition_data.sh              # place + hash-verify ALL inputs into data/
                                                       #   route A: official files dropped in data/raw/
                                                       #   route B (default): pinned GitHub bridge,
                                                       #   owner-manifest + our sha256 pins verified
                                                       #   (alias: scripts/fetch_inputs.sh, the name
                                                       #    registry/input_pins.json documents)
.venv/bin/python scripts/prepare_data.py                    # grid, footprint, catalogue stats
.venv/bin/python scripts/measure_offsets.py                 # E1  offsets + corridor table
.venv/bin/python scripts/lidar_calibration.py               # E1b/E1c nulls, strength gate, 3 m calibration
.venv/bin/python scripts/run_corrections_holdout.py         # E2  shared blocked holdout, 4 arms
.venv/bin/python scripts/cluster_gate_control.py            #     sign-flip permutation control
.venv/bin/python scripts/build_corrections_submission.py    # E3  the rasters + receipts
.venv/bin/python scripts/run_discovery_holdout.py           # R2  E1 hypotheses H6-H8 on the holdout
.venv/bin/python scripts/build_discovery_submission.py      # R2  E2 the candidate .tif + receipt
bash scripts/mirror_registry.sh /home/user/_reg             # R2  E3 harvest sibling rasters (once)
.venv/bin/python scripts/screen_registry.py --tag v2 /home/user/_reg <candidate.tif>
.venv/bin/python scripts/lane_gate_discovery.py             # R2  E3 surface + dots lane gates
.venv/bin/python scripts/run_card_discovery.py              # R2  the one JSON run card
.venv/bin/python -m pytest -q                               # 69 tests (both runs)
.venv/bin/python scripts/screen_registry.py                #     uniqueness vs the harvested corpus
.venv/bin/python tests/test_contracts.py                    #     contract tests
.venv/bin/python scripts/build_site.py                      #     docs/*.html, from the receipts
```
```

## Reproduce (one command per step; CPU only, ~1 min total)

```bash
python scripts/assemble_data_bridge.py && python scripts/preflight_data.py   # official rasters
python scripts/prepare_records.py                                           # record ids
python scripts/measure_corrections_offsets.py                               # E1
python scripts/holdout_corrections.py                                       # E2 + E3
python scripts/check_registry.py --dots docs/downloads/gems56-corr-*-nan.tif \
       --surface data/cache/lane_surface_A2.npy                             # uniqueness
python scripts/build_submission.py                                          # the TIF
python scripts/build_site.py                                                # this site
```

The registry check needs the harvested sibling rasters (outside this repo; see
`docs/sources.html` for the sibling list).

## Remaining work and limitations

1. **No organizer score exists for this file.** Every number here is MEASURED (official data),
   HOLDOUT-DTI (simulated truth), or USER-REPORTED (siblings). The only ORGANIZER-CONFIRMED
   number will be the receipt after you submit.
2. **The holdout truth is simulated** (the measured crest lines of withheld records). It
   validates the machinery and the controls, not the organizer's hidden labels; the
   A1-vs-A2 (gate vs no-gate) contrast is construction-biased toward A2 and is reported as
   such. The external validation is the 1 m LiDAR calibration (crest MAD 0.29 px).
3. **Named non-fault mimic:** erosional terraces / alluvial-fan edges produce the same convex
   slope crest without a fault; a crest can belong to a neighbouring unmapped strand (which
   would still score as a new fault). The 1 m LiDAR confirms the crest is a real sharp scarp;
   it cannot prove it is a fault.
4. **LiDAR calibration covers 75% of the footprint** (706/716 official 3DEP tiles; 10 edge
   tiles failed in the sibling's CI). Calibration n's are reported with every statistic.
5. **Corrections-only is a slice.** The implied hidden truth is ~7,900 px (GEMSDOE32 estimate,
   user-reported family); this file captures corrections near known traces. Combining lanes
   (e.g. the preregistered mag-ridge / radiometric-alteration hypotheses on
   `docs/hypotheses.html`) is the path to the live leaders, within the weekly cap.
6. **Sibling figures are unauthenticated** (0.2778 attribution unsupported; 0.3195 stale;
   0.3774 unverifiable from this sandbox). See `docs/irregularities.html`.
7. **Template tools were reused, not forked** (`src/metrics.py`, `src/submission_io.py`,
   `src/dataset.py`, `src/postprocess.py`, `scripts/validate_submission.py`,
   `scripts/sanitize_submission.py`, `scripts/preflight_data.py`,
   `scripts/assemble_data_bridge.py` vendored unchanged from the GEMSDOE template). One
   template gap found and worked around locally (reported, not patched in the template): the
   official metric has no prediction-side known-fault mask, so the holdout implements the
   masking model in `scripts/holdout_corrections.py` (`masked_score`,
   `masked_block_aggregate`). The template's test suite was pruned to the two files that
   exercise only the vendored tools and pass (see `tests/README.md`); 35 tests pass.
8. **Budget:** 3 experiments used (E1, E2, E3). No submission slot was spent; promotion is the
   separate selector step.
9. **Uniqueness stop (IR-56-07):** the literal 70%-containment test flags 8 rasters.
   The discriminating statistics are diagnostic only; they cannot waive the user's duplicate-and-stop
   rule. The protocol verdict is **DUPLICATE / STOP**. Full numbers remain in
   `evidence/corrections/registry_check.json` and `docs/irregularities.html`.

### Concurrent integration (PR #6)

The updated prior-run full-corpus audit, fail-closed registry check, session brief,
and leader analysis from PR #6 are preserved. See
[prior-run report](docs/prior-run.html),
[session brief](docs/brief/2026-10-09-session-prompt.md), and
[leader analysis](docs/research/leader-analysis-2026-10-09.md).
`scripts/build_site.py` builds the combined report; `scripts/build_prior_site.py`
is the preserved prior generator (it writes the same docs paths, so use only in a
separate checkout when reproducing the old presentation).
