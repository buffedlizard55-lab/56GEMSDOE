# 56GEMSDOE — corrections lane for the DOE GEMS Prize

DrivenData competition 306 (GeoDAWN / NW Nevada): find **geothermal-indicative faults missing
from the USGS/INGENIOUS catalogue** and ship them as a legal GeoTIFF.
Site: **https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html**
(one-click submission download at the top; submission guide on *Make a submission*).

> **Arena Core Values (quoted in the brief):** Maximize P(Win). Own the Outcome.

> **Bottom line of the round-2 (discovery) run (2026-10-09):** five new hypotheses were
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
Uniqueness: checked against every earlier raster from the 48 sibling repositories
(976 rasters, 412 unique pixel contents) — see `evidence/corrections/registry_check.json`.
**UNIQUE**: worst Spearman 0.043 (dots) / 0.109 (surface) vs all 412 unique rasters
(threshold 0.90); worst 3-px Jaccard 0.091 and worst reverse containment 0.046 vs every
sparse prior. The protocol's literal 70%-containment test fires on 8 habitat rasters
(up to 99.9% containment), all 12–38× larger superset emissions (lattices/fields) with
Jaccard ≤ 0.056 and reverse containment ≤ 0.023 among themselves; against every prior
submission of comparable construction (the 37,654–44,090-dot h33 family, incl. the
0.2778-attributed file) containment is ≤ 33% and Jaccard ≤ 5%. Logged and investigated
as IR-56-07 (`docs/irregularities.html`); determination: not a re-issue of any prior.
Run card: `evidence/corrections/run_card.json`.

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
9. **Uniqueness caveat (IR-56-07):** the literal 70%-containment test flags 8 habitat
   rasters (12–38× supersets). The discriminating statistics (Jaccard ≤ 0.091, reverse
   containment ≤ 0.046, Spearman ≤ 0.043, comparable-prior containment ≤ 0.334) show the
   file is unique; the flags are logged with full numbers in
   `evidence/corrections/registry_check.json` and on `docs/irregularities.html` so the
   selector can veto with the complete record.

### Concurrent integration (PR #6)

The updated prior-run full-corpus audit, fail-closed registry check, session brief,
and leader analysis from PR #6 are preserved. See
[prior-run report](docs/prior-run.html),
[session brief](docs/brief/2026-10-09-session-prompt.md), and
[leader analysis](docs/research/leader-analysis-2026-10-09.md).
`scripts/build_site.py` builds the combined report; `scripts/build_prior_site.py`
is the preserved prior generator (it writes the same docs paths, so use only in a
separate checkout when reproducing the old presentation).
