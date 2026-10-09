# 56GEMSDOE — DOE GEMS Prize, corrections lane

> **Current verdict: NEGATIVE / STOP. No file in this repository is cleared or safe to submit.**
> The experiment budget for the active corrections lane is exhausted. No submission slot has
> been used, no candidate is selected or promoted, and no ORGANIZER-CONFIRMED score exists.

**GitHub Pages:** [project status and research](https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html) ·
[submission instructions](https://buffedlizard55-lab.github.io/56GEMSDOE/docs/executive-summary.html).

## Current authoritative run

The authoritative result for the active corrections lane is [`evidence/run_card.json`](evidence/run_card.json),
run `2026-10-09T16:49:44Z`. It is later than the earlier strongest-crest corrections run and is
more relevant than the still-later **discovery** run (`evidence/run_card_discovery_v1.json`), which
is outside the active lane. The card now explicitly records this authority decision and the strict
format revalidation. No experiments were run in this review.

The active-lane 2 px primary has the name `h56-corr-snap200cm-20261009` and this 122-character note:

> h56 corrections lane, PRIMARY arm: dots on the evidence crest >= 200 m off catalogue, DEM+mag concordant; 1 dots; NEGATIVE

Its GeoTIFF SHA-256 is `65635a536d5195532691dbe02c04f796ea6b9e7123cd4c9cf5a8f930b351d20b`.

**Do not submit it.** Two independent stop conditions apply:

1. **Registry:** pre-placement surface screening found no ρ>0.90 trigger among readable priors
   (max ρ = 0.00513), but that receipt has 36 unreadable entries and is not a complete clearance.
   The final-dot gate reports a directed 3-px fraction of 1.0 against 263/944 indexed priors,
   exceeding the literal 0.70 rule. Low correlation does not waive the independent proximity stop.
2. **Format:** strict replay against the pinned sample reports **7,111,787 non-NaN cells outside
   the sample footprint** and `nodata=None` where the template declares NaN. Correct CRS, shape,
   transform, and value range do not make the file conformant.

The 14-dot sensitivity raster has the same strict format failure. The 25,000-dot discovery raster
also fails it and is outside the active method lane. The original build receipts marked these files
`validator_ok: true`; those are now explicitly retained as *legacy* results and superseded by the
strict validator outputs in the receipts/run card. None was repaired, regenerated, or promoted.

### One-click download — archive only, NOT safe to submit

[Download the historical 6,504-dot corrections TIFF for technical inspection](docs/downloads/gems56-corr-crestgt2px-20261009T051209Z-78fc86ad-nan.tif)

This older file is **format-conformant to the pinned bridge sample** under the strict local check
(single-band float32, values in [0,1], matching finite/NaN mask and NaN nodata tag). It is still
**not safe to submit**: its historical registry receipt triggered the literal >70%-within-3-px
rule. Its descriptive low correlation/Jaccard statistics do not override duplicate-and-stop.
The sample itself is a third-party hash-pinned mirror, not organizer-authenticated; see
[IR-56-001/003/027](evidence/irregularities.json). This link is provided only to preserve the
research artifact and make the negative result inspectable.

## Evidence labels and 0.2778 research note

- **ORGANIZER-CONFIRMED:** none. No submission-page receipt is present.
- **HOLDOUT-DTI:** local hidden-component catalogue-recovery diagnostic, not a score and not the
  organizer's hidden-new-fault test. For the active run, the method-level `B_snap` value is
  **HOLDOUT-DTI** (evaluator `gems52-pooled-hide-v1`; 48,080 withheld positives; 95% CI
  `[0.0000000, 0.0004536]`): DTI `0.0001566`. The random-jitter control is also **HOLDOUT-DTI**
  (same archived evaluator receipt and withheld-positive count; 95% CI `[0.0000026, 0.0005085]`):
  DTI `0.0002055`. These method arms are inside overlapping uncertainty and do not establish
  benefit; the 1-dot TIFF was not separately scored. The detailed values are in the run card.
- **USER-REPORTED / SIBLING-REPORTED:** the 0.2778 attribution and leaderboard figures. Do not
  present them as facts from the organizer.

The [official problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
defines the 300 m triangular-kernel DTI with α=0.2 and β=0.8. A [DrivenData staff reply in forum
thread 11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)
says known USGS/INGENIOUS fault pixels are excluded from penalty terms. That does **not** mean a
200 m buffer around a known fault is automatically exempt.

The [GEMSDOE32 page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) labels the
specific H33-2-B2 artifact **UNSCORED**, calls 0.2747 a model projection, and says no organizer
score exists for artifacts in that repository. Separately, [GEMSDOE54 reports](https://github.com/buffedlizard55-lab/GEMSDOE54/blob/main/RUN2-SUMMARY.md)
that the 37,654-dot raster was made by pruning 2,545 dots within 200 m from a 40,199-dot parent.
That is a **sibling-reported raster-construction mechanism**, not proof of the 0.2778 score. The
pruning could reduce false-positive mass, but it could also remove credit if new truth lies nearby.
Without an organizer receipt or hidden labels, no causal explanation of an unverified score is
possible. See [`docs/research/leader-analysis-2026-10-09.md`](docs/research/leader-analysis-2026-10-09.md)
for the formula, evidence classes, and limitations.

## Data, validators, and reproducibility

The official data tab requires login in this environment. `scripts/download_competition_data.sh`
uses hash-pinned owner-bridge inputs, verifies their recorded pins, prepares `evidence/grid.json`,
and now publishes the root-level aliases required by downstream tools:

- `data/sample_submission.tif` ← `data/grid/sample_submission.tif`
- `data/labels.tif` ← `data/grid/existing_faults.tif`

The aliases are byte-identical to the verified grid files. **Pin match is not organizer
authentication.** The public problem page describes the sample as a total-fault-absence raster,
while the local bridge copy is cell-for-cell equal to `existing_faults.tif` (60,988 positive cells).
Only its locally measured finite mask has been used for format comparison; a logged-in comparison
to the official data-tab download remains outstanding.

The local gates now fail closed on the sample's exact finite footprint: output must be finite and
in [0,1] inside; NaN outside; carry a matching nodata tag; and match the sample/training CRS, shape,
transform, and bounds. A local pass is **not** organizer acceptance or proof that upload will
succeed. The shared writer and validators were hardened; regression tests cover NaNs inside,
finite values outside, infinities, missing nodata, and empty output.

Recreate the pinned inputs and run the suite:

```bash
bash scripts/download_competition_data.sh
.venv/bin/python -m pytest -q
```

Current verification: **77 tests passed**. To see the strict format result for any archived TIFF:

```bash
.venv/bin/python scripts/validate_submission.py \
  --pred docs/downloads/h56-corr-snap200cm-20261009.tif \
  --sample data/sample_submission.tif \
  --train data/training_features.tif
```

This command is expected to fail for the 1-dot, 14-dot, and discovery outputs. Do not run the
experiment/build scripts: the active 3-experiment/2-hour budget is already exhausted.

## Three review passes completed

1. **Implementation and verification:** fixed download aliases; hardened the shared GeoTIFF writer,
   exact-mask gate, CLI validator, and friendly validator; added regressions; reran the downloader
   and test suite.
2. **Adversarial review:** replayed strict validation against all four published TIFFs. The 1-dot,
   14-dot, and 25,000-dot files fail for the outside mask and missing nodata; the historical 6,504-dot
   file passes local format only but still hits the registry stop. Corrected stale receipts/run cards.
3. **Original-request cross-check:** confirmed the authoritative corrections card, marked the later
   discovery card out of scope, kept the lane verdict negative, and did not run more experiments,
   select a submission, or spend a slot. Source links and unresolved provenance are recorded above
   and in the evidence files.

Review notes: [`docs/review/2026-10-09.md`](docs/review/2026-10-09.md).

## Remaining work and limitations

1. A logged-in human must compare the owner-bridge TIFFs to the actual competition data-tab downloads
   and resolve the sample-content mismatch.
2. No submission receipt exists, so none of the user/sibling leaderboard figures is organizer-confirmed.
3. The holdout target is catalogue recovery, not the hidden new-fault truth. The latest run's per-feature
   leakage-canary receipt is missing. Its evaluator also has unresolved provenance defects: snap inputs
   use `fold["visible"]` while the buffer is applied to `fold["fit"]`, and the receipt records
   `design.prevalence: null` despite an invocation value of `0.00294`. Treat the DTI as exploratory,
   not promotion evidence; do not rerun under the exhausted budget.
4. The strict format gate currently rejects the active 1-dot and 14-dot files. Do not “fix” those by
   rewriting them into another candidate: the duplicate/stop rule already fired.
5. Registry receipts disagree slightly on unreadable files: the active gate records 35 errors and
   an earlier full-screen receipt records 36 among 944 rasters. The 1-dot proximity trigger is
   density-sensitive; review it only under a changed, explicitly authorized protocol—not waive it here.
6. No active-lane candidate is safe to submit. Future work requires a new authorized experiment budget,
   an authenticated input/template check, valid holdout/canary receipts, both surface and final-dot
   registry checks, and a fresh strict validator pass before any separate selector decision.

## Repository map

- `src/gems56/` — corrections, grid, shared holdout, gates, and submission writer.
- `src/submission_io.py`, `src/gems/submission.py` — legacy/local writer and validation helpers, now
  fail-closed where a reference mask is supplied.
- `scripts/download_competition_data.sh` — pinned data preparation and compatibility aliases.
- `scripts/validate_submission.py` — strict local template/metadata validator; not organizer acceptance.
- `evidence/run_card.json` — authoritative active corrections-lane run card.
- `evidence/corrections/run_card.json` — earlier corrections run, retained as history.
- `evidence/run_card_discovery_v1.json` — later discovery run, outside the active corrections lane.
- `docs/downloads/` — archived research GeoTIFFs and their receipts; none is cleared.
- `docs/research/leader-analysis-2026-10-09.md` — researched score attribution and formula caveats.

## Standing prompt and active constraints

The recoverable 2026-10-09 user brief is copied below from `docs/brief/2026-10-09-session-prompt.md`.
That source explicitly says it is **near-verbatim, not byte-identical**: its per-site score list was
abbreviated in the repository, so the absent figures cannot be reconstructed here. This README
preserves the full recoverable prompt and the active constraints; it does not upgrade any user- or
sibling-reported score into fact.

**Active continuation constraints:** corrections lane only; rank-correlation against registry
rasters before placement and on final dots; if ρ>0.90 or >70% of dots lie within 3 px of a registry
raster, log duplicate and stop. Reuse shared tools. Hide whole segments with a buffer, derive
catalogue features only from visible faults, mask visible fault pixels exactly, and report pooled
DTI with α=0.2, β=0.8, 300 m triangular kernel. Label scores only as HOLDOUT-DTI with evaluator,
withheld-positive count and 95% CI, or ORGANIZER-CONFIRMED from a receipt; never call a projection a
score. Canary each feature; AUC>0.90 is leakage until resolved. Stop at 3 experiments or 2 hours;
prior receipts say this budget is exhausted. End with one JSON run card containing hypothesis,
mechanism, named non-fault mimic, holdout DTI/CI, registry correlation/overlap, TIFF SHA-256,
validator output, ≤140-character submission name/note, and promote/negative verdict. Do not choose
or promote a submission in this lane.

---

# Session prompt, 2026-10-09 (standing brief — near-verbatim, NOT byte-identical)

The user asked for this prompt to be kept in the repository and re-read at the start of every session.

**Fidelity statement (IR-56-017):** the prose is reproduced in order with Markdown link wrappers flattened to
plain URLs. The long per-site score table (GEMSDOE2 … 57GEMSDOE) is **abbreviated** in the second block below;
its figures were not copied line by line, so they must be taken from the original message, not from this file.

---

Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt. Read the entire prompt.

Corrections lane: measure how far the catalogue sits from the evidence, then emit where the evidence says the fault is. The organizers said new-fault ground truth can lie within 300 m of a known trace as "corrections or modifications to existing fault traces", and that finding them is an outcome the competition is explicitly aiming for (forum thread 11516). Known-fault pixels are masked pixel-exactly, so the catalogue line itself is not the target. Hermant, Kiersnowski and Bellanger (Stanford Geothermal Workshop, 2025) measured USGS-to-refined trace discrepancies of up to 400 m in north-central Nevada, larger than the scoring kernel, but nobody here has measured the offset in GeoDAWN. First deliverable: sample perpendicular transects within ±400 m of every catalogue trace, locate the nearest crest of the DEM-curvature scarp and of the magnetic gradient ridge, and publish the offset histogram, calibrated on 1 m LiDAR tiles where the crest is unambiguous. Where a consistent offset exceeds about two pixels, emit dots on the evidence-defined trace rather than the catalogue line. Train any learned component with a registration- and omission-tolerant loss in the style of Mnih and Hinton (ICML 2012), which was designed for labels that are both incomplete and shifted. If offsets cluster under two pixels, report that as the result and emit nothing from this lane. Output the standard validated GeoTIFF, uniqueness-checked against every earlier raster.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_holdout.py and submission_writer.py. Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions. These websites are researched, and tested and have generated TIF submissions. But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition. Must be unique submission unlike any within the GEMSDOE sites above. Verify working line by line no hallucinations.

Current competition leaderboard GEMSDOE high score:

0.3774

https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html

gems-submission-20260925T001403Z-7f00890a: 0.1563

....

(The per-site score list continues in the original prompt for GEMSDOE2 through GEMSDOE54, 55GEMSDOE, 56GEMSDOE and 57GEMSDOE, with scores ranging from 0.0020 to 0.2778 as the user reported them. Those figures are USER-REPORTED and are not verified against any organizer receipt.)

The following is the leaderboard for the competition:

https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/

See below for more links and information related to the competition:

https://github.com/drivendataorg/gems-prize-reference-solution

https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and

https://gbcge.org/current-projects/ingenious/

https://epsg.io/32611

https://en.wikipedia.org/wiki/Tversky_index

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above. We need to come up with distinct and unique strategies to score higher in this competition leaderboard.

We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents. We should store all of our information and knowledge that we can gather from official verified sources. This will serve as a starting point for other projects as well. We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for. So it's important to be contrarian but be smart about it. We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents. We need to do deep research and critical thinking and come up with new hypothesis to test.

0.3195 is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website. It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use. It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

"Maximize the Probability of Winning": our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). "Maximize P(Win)" frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission. It should be as easy as download to click a File to submit into the competition. This needs to be in the executive summary or the very beginning of the site. it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submit No file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition. The following is the competition:

https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

We need to create a project that can compete and place top of the leaderboard. We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.
https://www.drivendata.org/competitions/306/competition-doe-gems/

Get familiar with the problem through the overview and problem description, https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/. You might also want to reference additional resources available on the about page, https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/.

Download the data from the data, https://www.drivendata.org/competitions/306/competition-doe-gems/data/, tab.

Create and train your own model. This reference solution, https://github.com/drivendataorg/gems-prize-reference-solution implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project. We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

https://docs.nlr.gov/docs/fy26osti/96647.pdf

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information. This must be done autonomously and must be constantly reviewed and improved upon. Provide suggestions and improvements and implement them.

No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from the data tab (verified redirect to login)

See below for links from the above site. See attached files for links from the above site.

https://gdr.openei.org/submissions/1391

Download competition data from the data tab (requires login) to data/

See links below for competition data:

https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf

https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif

https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif

https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif

https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf

Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.

Site creation

Create a github page for this repo that has clean ui, user friendly, simple and easy to use. It should be organized and clean.

It should include all relevant information in an easy to read format with official verified links as sources for review. Work line by line verify everything no hallucinations.

The single remaining blocker to training is data placement: run bash scripts/download_competition_data.sh on any unrestricted machine into data/, then python scripts/prepare_data.py — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself. Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request. Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project. It should be worked on in this next session or the next session. Work line by line verify everything no hallucinations.
