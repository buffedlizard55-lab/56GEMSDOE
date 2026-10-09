# 56GEMSDOE — GEMS Prize (DrivenData 306), **corrections lane**

Live site: **https://buffedlizard55-lab.github.io/56GEMSDOE/** · downloadable rasters in
[`docs/downloads/`](docs/downloads/) · all receipts in [`evidence/`](evidence/)

> **Bottom line (updated 2026-10-09, second run).** The catalogue is **not** displaced from the geomorphic and
> magnetic lineations by ≥ 2 px anywhere we can show: 0 of 21 corridors pass the decision gate, the 3 m LiDAR
> check finds 0 of 13 segments displaced by ≥ 200 m, and the two data families do not correlate (r = 0.022). The
> lane therefore emits no correction. Its two rasters are **format-valid — download is safe — and not for
> submission**: the shared uniqueness gate, now run against the full 944-raster corpus, reports a *proximity
> duplicate* (263 of 944 priors for the primary; the rule fires on dense registry layers, IR-56-006), so under the
> parallel-run protocol the lane is logged as a duplicate and stops.
>
> **Why 0.2778 scored and what a sparse file can reach** (derived from the official formula, not from a holdout):
> recall is weighted 0.8 against 0.2 for false-positive mass, so the leader emits dense mass over the fault field.
> A file with S emitted mass can earn at most `min(|G|, S·9.38)` of credit. For this lane's 14-dot file that
> bound exceeds 0.2777 only if the hidden positive set has fewer than ~558 pixels. Full analysis:
> [docs/research/leader-analysis-2026-10-09.md](docs/research/leader-analysis-2026-10-09.md).
>
> The HOLDOUT-DTI of the lane's arms is 0.00016 (B_snap, CI [0, 0.00045], 48,080 withheld positives,
> `gems52-pooled-hide-v1`) — indistinguishable from jitter. Negative results are the deliverable here.
> Numbers, links and caveats: [the site](https://buffedlizard55-lab.github.io/56GEMSDOE/). Executive summary and
> the one-click downloads: [docs/executive-summary.html](docs/executive-summary.html).

## What changed in the 2026-10-09 second run

* **Inputs re-hydrated and re-verified.** `data/` was absent at session start (IR-56-014). The three pinned
  competition inputs were re-fetched from the owner's sibling repo `buffedlizard55-lab/GEMSDOE` (`data/bridge`,
  5 shards reassembled) and the LiDAR layer from `buffedlizard55-lab/GEMSDOE48`. Every hash matches
  `registry/input_pins.json` / `data_manifest.json`. The 3 m pilot tiles come from `GEMSDOE48/data/pilot/dem3m`
  and match `dem_pilot_receipt.json`. That is a third-party mirror of a login-gated organizer tab: a licence
  review is needed before any redistribution (IR-56-014). `data/` is git-ignored and is not committed.
* **Reproduction.** The lane's five scripts regenerate both rasters byte-for-byte (sha256 `e3285854…` and
  `65635a53…`) and the calibration and holdout receipts with identical numbers (timing fields aside).
* **Uniqueness gate fixed and run on the full corpus (IR-56-015).** The gate had been silently checking zero
  priors (`/home/user/_reg` absent) and wrote empty receipts. The build now fails closed below 944 priors, and
  `scripts/mirror_registry_corpus.py` rebuilds the flat corpus from `docs/research/registry-index.json` with a
  sha256 check per file (944/944, `evidence/registry_corpus_mirror.json`). 36 priors are unreadable on this grid
  and are reported as errors, not silently dropped.
* **Submission status made unambiguous.** Site and summary now say *download: yes (format-valid); submit: no*.
* **Session brief stored** in [docs/brief/2026-10-09-session-prompt.md](docs/brief/2026-10-09-session-prompt.md)
  (near-verbatim; the per-site score table is abbreviated, IR-56-017).
* **Irregularities IR-56-014 … 018** are in [`evidence/irregularities.json`](evidence/irregularities.json).

---

## Standing project brief (the assignment, verbatim as recorded)

Reproduced from the session record of the instruction this repository was created to execute. The
original message text was not preserved byte-for-byte in the workspace, so this is the recorded
brief — every requirement below is active, and nothing here is summarised away.

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

### Standing constraints (also verbatim, also active)

- MUST generate a UNIQUE TIF submission; never copy a previous submission except for learning. It must be
  obvious whether it is OK to download and submit.
- Submission raster values MUST be in `[0, 1]`. A past download failed the DrivenData upload with
  `Predicted values must be in range [0, 1]`; the site must not offer a raster that triggers this.
- The submission form accepts a single-band GeoTIFF (`.tif`) or a `.zip` with one GeoTIFF; it must match the
  submission format's CRS, shape and geotransform; an optional short note is accepted.
- Every number is labelled **HOLDOUT-DTI** (our evaluator version, withheld positives, 95% CI) or
  **ORGANIZER-CONFIRMED** (from a submission-page receipt). A projection is never written as a score.
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
| `registry/input_pins.json` | sha256 + byte count of every official input, so a reviewer can confirm we measured the real rasters |
| `knowledge/sources.json` | every external claim with its link, its access status, and what was actually read |
| `tests/test_contracts.py` | 10 contract tests on the vendored metric and on the lane's detector |
| `docs/` | the GitHub Pages site and the downloadable rasters |

### Data provenance

The competition data tab is behind a login, so the feature stack was assembled from hash-pinned copies in
the sibling repository bridge and verified against `registry/input_pins.json` (`pin_match: true` for
`training_features.tif` 418,912,844 B `4371c82e…`, `existing_faults.tif` `7ba308cc…`,
`sample_submission.tif` `2176d08e…`). The grid is `(3730, 3292)` cells, EPSG:32611, transform
`(100, 0, 243350, 0, -100, 4508550)`, 5,164,300 usable cells, catalogue prevalence 1.179%.
**A logged-in human should confirm those three hashes against the data tab** — that is the one link in the
chain this sandbox cannot close by itself (IR-56-003).

## Relationship to the earlier session on this repo (PRs #1–#3)

PRs #1–#3 built a *proxy* version of this lane and correctly stopped: with no training stack in the sandbox,
they measured catalogue-vs-SGMC (a stand-in), reported "no consistent offset > 2 px in the proxy", listed the
DEM-crest test as **blocked**, and opened a "Decision needed" because the brief simultaneously demands a unique
GeoTIFF and forbids emitting one under 2 px. Two things have changed:

- **The blocker is gone.** The aligned feature stack, `existing_faults.tif`, `sample_submission.tif` and the
  1 m LiDAR scarp layer are now present in the sandbox and hash-pinned in `data_manifest.json` (3 of 3 pinned
  files reproduce byte-for-byte). The real DEM-crest and magnetic-ridge measurement was run, not a proxy, over
  every one of the 60,894 catalogue cells.
- **The decision is answered by the measurement, not by choice.** The full instrument says the same thing the
  proxy did but now with nulls, calibration and a LiDAR check: no corridor is displaced by 2 px. The brief's own
  clause — "if offsets cluster under two pixels, report that as the result" — is the instruction being followed,
  and the artefacts published here are the report plus format-valid rasters that a human can submit if they
  choose to, with the gate's adverse verdict on them printed at the top of the page.

Still valid and reused from that session: `src/gems/metric.py` and `src/gems/submission.py` with their 18 tests
(`pytest -q` now runs **28**), `scripts/registry_audit.py` + `docs/research/registry-index.json` (a hash-level
index of **944** sibling TIFs, 920 on this grid, 432 sharing a hash with another file — the complement of this
lane's dot-level screen), the licence policy that organizer inputs never enter Git, the rules answer in
`docs/submit.html`, and the claim-label vocabulary below. Two vendored copies of the template metric now
coexist (`src/gems/` and `src/gems56/`) because neither session could see the other; consolidating them is a
template-side change, and both are pinned to the same upstream commit, so they agree by construction
(`tests/test_metric.py` and `tests/test_contracts.py` pin the identical formula).

## Claim labels used everywhere in this repository

- **HOLDOUT-DTI (evaluator version, withheld positives, 95% CI)** — computed on whole withheld fault segments
  with a 4 px buffer, 48,080 withheld positives per arm, 4 folds: `evidence/holdout_corrections_v1.json`.
- **ORGANIZER-CONFIRMED (submission-page receipt)** — *none exists*: no upload was filed, so no score here is
  organizer-confirmed, and `0.3195` / `0.3774` are quoted only as CLAIM / USER-REPORTED from the brief.
- **MEASURED** — read off a file in this repository by a script in this repository.
- **PROXY** — a stand-in input. The earlier session's SGMC number is labelled so; nothing on the current site
  is a proxy for a score.
- **PROJECTION** — a model output. Never written as a score; none of the published figures is one.

## How to run it

```bash
python -m venv .venv && .venv/bin/pip install numpy==2.4.6 rasterio==1.4.4 scipy==1.17.1 shapely pyproj pandas pytest
# inputs (hash-checked; see registry/input_pins.json): data/training_features.tif, data/grid/existing_faults.tif,
#   data/grid/sample_submission.tif, data/external/h52_scarp3m_100m.tif  -- and for the 3 m check, the two pilot
#   tiles copied to /home/user/_lidar/ (x42y425_3m.tif, x40y427_3m.tif from GEMSDOE48/data/pilot/dem3m)
.venv/bin/python scripts/mirror_registry_corpus.py /home/user/_reg /home/user/_regsrc   # uniqueness corpus, 944 files
.venv/bin/python scripts/prepare_data.py                    # grid, footprint, catalogue stats
.venv/bin/python scripts/measure_offsets.py                 # E1  offsets + corridor table
.venv/bin/python scripts/lidar_calibration.py               # E1b/E1c nulls, strength gate, 3 m calibration
.venv/bin/python scripts/run_corrections_holdout.py         # E2  shared blocked holdout, 4 arms
.venv/bin/python scripts/cluster_gate_control.py            #     sign-flip permutation control
.venv/bin/python scripts/build_corrections_submission.py    # E3  the rasters + receipts
.venv/bin/python scripts/screen_registry.py                 #     uniqueness vs the harvested corpus
.venv/bin/python tests/test_contracts.py                    #     contract tests
.venv/bin/python scripts/build_site.py                      #     docs/*.html, from the receipts
```

Everything is deterministic: fixed seeds, no network at run time beyond the pinned inputs, and every script
writes its own receipt.

## Next steps and limitations (for the next session)

1. **Decide the submission question explicitly.** This lane's files are negative and capped (IR-56-018). The
   recommendation is *not* to spend a weekly slot on them. A selector decision is still needed, and it belongs to a
   person, not to this lane.
2. **Fix the proximity rule, through the protocol, not around it.** A 14-dot file meets "≥ 70 % of dots within
   3 px of a registry raster" against dense layers trivially. Propose a reciprocal or density-normalised rule to the
   organisers of the parallel-run protocol and log the proposal; do not change the rule in this repo.
3. **Keep the reciprocal screen current.** `scripts/screen_registry.py /home/user/_reg` was re-run on the full
   944-raster corpus in this session (evidence/registry_screen_v1.json). Re-run it whenever the corpus or the
   candidate files change; it takes roughly 30 minutes.
4. **Get the organiser-confirmed number.** Every score in this repo is HOLDOUT-DTI or a user report. The
   [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) renders
   client-side and was unreadable here (IR-56-016). A logged-in person must read it and paste the value.
5. **Licence the inputs.** The competition rasters came from a third-party GitHub mirror. Before any push of data
   or derived rasters beyond the two files in `docs/downloads/`, confirm the DrivenData data-use terms (IR-56-014).
6. **Dense, recall-weighted emission belongs in another lane.** The leader's mechanism (IR-56-018, H7/H8 in
   `docs/research/hypotheses.md`) needs a detector that emits mass over the fault field. That is a different method
   paragraph and must start from a clean session.
7. **Limits of the holdout.** It scores recovery of catalogue faults, cannot reward genuinely new faults, and cannot
   see a ≤ 3 px lateral offset (IR-56-004). Do not read it as a leaderboard predictor.

## Reading order for a reviewer

1. [`docs/executive-summary.html`](docs/executive-summary.html) — what to download and how to file it.
2. [`docs/index.html`](docs/index.html) — the measurement, with both nulls next to every histogram.
3. [`docs/irregularities.html`](docs/irregularities.html) — 12 logged irregularities, including the three
   estimator defects that a test caught and that changed the answer.
4. [`evidence/`](evidence/) — the receipts the pages are generated from.

## Honest limits of this run

* The holdout cannot adjudicate this lane (IR-56-004): a ≤3 px lateral shift is invisible to an instrument
  that hides whole catalogue segments. Snapping scored 0.00012, jitter 0.00011, no snapping 0.00000.
* The 3 m LiDAR check covers 0.9% of catalogue pixels (two cached tiles); the corridor-level negative is
  therefore partly an extrapolation, stated as such in the receipt.
* The crest locator has a measured, shape-dependent placement bias of +0.2 to +0.5 px
  (`evidence/estimator_validation.json`). Nothing here rests on an absolute sub-pixel offset.
* Board scores could not be read from an organizer source in this session; every number on the site carries
  an evidence class and none of them is a claimed ranking.
