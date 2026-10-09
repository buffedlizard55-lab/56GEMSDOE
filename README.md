# 56GEMSDOE — GEMS Prize (DrivenData 306), **corrections lane**

Live site: **https://buffedlizard55-lab.github.io/56GEMSDOE/** · downloadable rasters in
[`docs/downloads/`](docs/downloads/) · all receipts in [`evidence/`](evidence/)

> **Current decision (2026-10-09): corrections lane negative; NO FILE IS SAFE TO SUBMIT.** The calibrated gate
> accepts **0 of 21** corridors; the cached, sibling-derived 3 m LiDAR check reports **0 of 13** segments at or
> beyond 200 m displacement. The historical DEM/magnetic snap has HOLDOUT-DTI `gems52-pooled-hide-v1` of
> 0.00015661 [0.00000000, 0.00045357] over 48,080 withheld catalogue positives; random jitter is
> 0.00020550 [0.00000261, 0.00050850]. These marginal 95% CIs overlap and the holdout is not the organizer's new-fault
> test. The one-dot primary artifact was built with the null-strength floor disabled; the 14-dot sensitivity is
> below the ~2 px rule. Both remain in `docs/downloads/` for audit only and are **not upload-ready**. The official
> format requires null/NaN outside the training bounds, but the shared writer rejects non-finite output; no portal
> upload has resolved the conflict (upstream issue [GEMSDOE52 #65](https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65)).
> No weekly slot has been used and no ORGANIZER-CONFIRMED score exists. The request for a new unique TIF conflicts
> with the lane's explicit stop condition (under-2 px offsets mean emit nothing): we honor the negative scientific
> result rather than manufacture or promote a correction. No new TIF or submission metadata was created; the
> existing rasters remain downloadable only for audit. See the [current status record](evidence/submission_status.json)
> and [submission page](docs/submit.html).
---

## Standing project brief (reconstructed from the session record)

Reproduced from the available session record of the instruction this repository was created to execute. The
original user message was not preserved byte-for-byte in the workspace, so this cannot honestly be called a
verbatim full prompt. This reconstruction retains the active scope, requirements, constraints, and guidance known
to this review; recover the original text from the authoritative conversation record if exact wording is required.

> Autonomously build `56GEMSDOE` into a DrivenData "GEMS Prize" (competition 306) project that beats the
> current best 0.3195, and produce ONE unique, validated, downloadable submission GeoTIFF.
>
> **Assigned lane (parallel-run protocol, must stay inside it): Corrections lane** — measure how far the
> GeoDAWN/USGS catalogue sits from the evidence: sample perpendicular transects within ±400 m of every
> catalogue trace, locate the nearest crest of the DEM-curvature scarp and of the magnetic gradient ridge,
> publish the offset histogram, calibrate on 1 m LiDAR tiles where the crest is unambiguous. Where a
> consistent offset exceeds ~2 pixels, emit dots on the evidence-defined trace instead of the catalogue
> line. Any learned component uses a registration- and omission-tolerant loss (Mnih & Hinton, ICML 2012).
> If offsets cluster under 2 pixels, report that as the result and emit nothing from this lane. Output the
> standard validated GeoTIFF, uniqueness-checked against every earlier raster.
>
> **Site/deliverable requirements:** easy one-click downloadable `.tif` on the page with an OBVIOUS statement
> whether it is safe to download and submit; executive-summary subpage explaining exactly how to submit;
> unique submission name + ≤140-char note; GitHub Pages site (clean UI, official verified links, audit
> tables); repo README contains the full user prompt as the standing project brief; 3–5 new geological
> hypotheses ranked by expected DTI gain/cost, top candidate validated on the spatially-blocked holdout
> before any slot is spent; all findings stored for reuse; PR created and merged to `main`; multi-pass
> self-review; flag irregularities; no hallucination (every claim backed by a tool call this turn).

### Standing constraints (reconstructed from the record; active)

- MUST generate a UNIQUE TIF submission; never copy a previous submission except for learning. It must be
  obvious whether it is OK to download and submit.
- Submission raster values MUST be in `[0, 1]`. A past download failed the DrivenData upload with
  `Predicted values must be in range [0, 1]`; the site must not offer a raster that triggers this.
- The submission form accepts a single-band GeoTIFF (`.tif`) or a `.zip` with one GeoTIFF; it must match the
  submission format's CRS, shape and geotransform; an optional short note is accepted.
- Every **score** is labelled **HOLDOUT-DTI** (evaluator version, withheld-positive count, 95% CI) or
  **ORGANIZER-CONFIRMED** (from a submission receipt). Other measurements are labelled MEASURED, user statements
  USER-REPORTED, and projections PROJECTION; no projection is written as a score.
- Run only this lane. Drift check before placement *and* on the final dots: rank-correlation with any
  registry raster > 0.90, or > 70% of dots within 3 px of one registry raster's dots ⇒ log as duplicate and
  stop.
- Reuse the template's cached feature stack, `evaluate_holdout.py` and `submission_writer.py`; holdout =
  hide-and-recover (withhold whole fault segments with a buffer, derive catalogue features only from visible
  faults, mask visible faults pixel-exactly, pooled DTI α 0.2 / β 0.8 / 300 m triangular kernel). Fix shared
  tools once in the template, never keep a private fork.
- Leakage canary: each feature alone on holdout; AUC > 0.90 is leakage until proven otherwise.
- End with one JSON run card (hypothesis; mechanism; named non-fault process; holdout DTI + CI;
  correlation/overlap vs registry; raster sha256; validator output; submission name + ≤140-char note; verdict
  promote/negative). Negative results are deliverables.
- Budget: stop after 3 experiments or 2 hours. Do **not** pick submissions for real slots — promotion is a
  separate selector step within the weekly cap.
- Only free, official, publicly verifiable data sources; provide links for manual review; no manual input
  from the user; flag irregularities; verify line by line; no hallucinations.
- Core values: *Maximize P(Win)* and *Own the Outcome*.

---

## What this repository is

A single lane of a multi-agent attack on the same competition, built to be auditable rather than impressive.

| path | what it is |
|---|---|
| `src/gems56/` | 10 modules vendored **byte-identically** from the shared template (grid, metric, holdout, evaluate_holdout, gates, submission_writer, features, …) plus this lane's `corrections.py` and `lane_inputs.py` |
| `scripts/` | the seven numbered experiments and the site builder, each self-documenting and re-runnable |
| `evidence/` | one JSON receipt per measurement, written by the code that produced it; `irregularities.json` |
| `registry/input_pins.json` | SHA-256 and byte counts for downloaded competition-input mirrors and sibling-derived LiDAR; proves identity to recorded pins, not direct organizer provenance |
| `knowledge/sources.json` | every external claim with its link, its access status, and what was actually read |
| `tests/test_contracts.py` | 10 contract tests on the vendored metric and on the lane's detector |
| `docs/` | the GitHub Pages site and the downloadable rasters |

### Data provenance

The competition data page is login-gated. `scripts/download_competition_data.sh` fetches hash-pinned bytes from a
public, owner-maintained GitHub mirror recorded in `registry/bridge_sources.json`; `data/` remains ignored by
Git. Matching SHA-256 pins proves byte identity to that mirror, not direct organizer authentication, licensing,
or permission to redistribute. Verify the participant terms on the [official data page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/).
The optional LiDAR inputs are sibling-derived products: two 3 m pilot tiles and a 100 m summary, not the original
regional USGS 1 m DEM rasters. See `data_manifest.json` for actual workspace presence, hash status, and
source-class labels. Do not describe the sibling cache as official 1 m input.
## Relationship to the earlier session on this repo (PRs #1–#3)

The earlier proxy-only stage correctly reported that real inputs were blocked. A later historical run restored
owner-mirrored competition bytes, measured catalogue offsets and generated the two diagnostic rasters now retained
under `docs/downloads/`. The current review found those artifacts were not safe to submit: the primary build
bypassed the calibrated strength floor, the relaxed sensitivity file is below threshold, the uniqueness gate
triggered, and the shared writer's all-finite exterior policy conflicts with the official sample/spec. The
historical HOLDOUT-DTI is not a validation of the newly ranked three-physics hypothesis. No new experiment or
upload was run in this review, and the existing three-experiment stop-loss is treated as consumed.

The shared writer issue is tracked once upstream at [GEMSDOE52 #65](https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65);
these vendored copies remain unchanged. The active hypotheses and status are recorded in
[`docs/research/hypotheses.md`](docs/research/hypotheses.md) and [`evidence/submission_status.json`](evidence/submission_status.json).
The older `src/gems/` copy and the current `src/gems56/` shared template also coexist; consolidation is a shared
template concern and is not attempted here.
## Claim labels used everywhere in this repository

- **HOLDOUT-DTI (evaluator version, withheld positives, 95% CI)** — the historical DEM/magnetic hide-and-recover
  receipt uses `gems52-pooled-hide-v1`, 48,080 withheld catalogue positives and 4 folds:
  `evidence/holdout_corrections_v1.json`. It is not the new three-physics candidate's result and not an organizer score.
- **ORGANIZER-CONFIRMED (submission-page receipt)** — *none exists*: no upload was filed. The `0.3195` target is
  USER-REPORTED from the standing brief; the leaderboard was not independently verified here.
- **MEASURED** — read off a file in this repository by a script in this repository.
- **PROXY** — a stand-in input. The earlier session's SGMC number is labelled so; nothing on the current site
  is a proxy for a score.
- **PROJECTION** — a model output. Never written as a score; none of the published figures is one.

## How to reproduce safely

Read the standing brief above before working on this project. The current review restored and hash-checked inputs,
updated manifests/site status and added tests/documentation, but did **not** run a new holdout or leakage experiment.
The historical E1/E2/E3 experimental budget is already treated as consumed; do not rerun the experiment scripts
unless a new run budget is explicitly reset. The current top-ranked three-physics hypothesis has not been validated.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/download_competition_data.sh       # public owner-maintained mirror, pinned hashes; ignored data/
.venv/bin/python scripts/prepare_data.py        # recompute grid facts from the restored bytes
.venv/bin/python scripts/make_manifest.py       # current presence, hashes, and provenance limits
.venv/bin/python tests/test_contracts.py        # non-experimental contract tests
.venv/bin/python scripts/build_site.py          # regenerate the public pages from receipts/status
```

The following are historical experiment commands and **must not be run under the consumed stop-loss** without a
newly reset budget and a reviewed preregistration: `measure_offsets.py`, `calibrate_gate.py`,
`lidar_calibration.py`, `run_corrections_holdout.py`, `cluster_gate_control.py`,
`build_corrections_submission.py`, and `screen_registry.py`. Reproduction of old receipts is not a new candidate
validation and does not establish organizer scoring.
## Reading order for a reviewer

1. [`docs/executive-summary.html`](docs/executive-summary.html) — current negative result and why no file is safe to submit.
2. [`docs/index.html`](docs/index.html) — the historical measurements and current submission status.
3. [`docs/submit.html`](docs/submit.html) — why no current file is safe and the conditional upload checklist.
4. [`docs/irregularities.html`](docs/irregularities.html) — 14 logged irregularities, including the shared-template blocker.
5. [`evidence/`](evidence/) — the receipts the pages are generated from.

## Honest limits of this run

* The historical holdout cannot adjudicate new-fault discovery or reliably distinguish a small lateral shift.
  HOLDOUT-DTI `gems52-pooled-hide-v1` (48,080 withheld catalogue positives): B_snap 0.00015661
  [0.00000000, 0.00045357], D_jitter 0.00020550 [0.00000261, 0.00050850]. These marginal 95% CIs overlap;
  the historical receipt contains no direct paired B_snap-versus-D_jitter interval. This is not a leaderboard score
  and does not validate the ranked three-physics hypothesis.
* The 3 m LiDAR check uses two sibling-derived pilot tiles and covers about 0.9% of catalogue pixels; it is not
  direct native 1 m validation of the region. The corridor-level negative is partly an extrapolation.
* The crest locator has a measured, shape-dependent placement bias of +0.2 to +0.5 px
  (`evidence/estimator_validation.json`). Nothing here rests on an absolute sub-pixel offset.
* Board scores could not be read from an organizer source in this review; `0.3195` remains USER-REPORTED from
  the standing brief, and there is no organizer-confirmed score or upload receipt.
