# Reusable findings — corrections lane, 2026-10-09

Written for the next run in this or any sibling lane. Every number is a receipt value, not a belief; the file
that contains it is named. Nothing here is a score, and no board position is claimed.

## 1. Data handling (saves hours; each of these bit us)

| fact | evidence | consequence |
|---|---|---|
| The feature stack's nodata is float32 `-3.4028e+38`, which is **finite**. 57.9% of band 1 is the sentinel. | `evidence/grid.json` (`sentinel`) | Any unmasked min/median/correlation is garbage. Read through `corrections.load_fields`, which converts to NaN **and asserts the band DESCRIPTION string** — sibling repos index the same physical bands under different numbers. |
| The LiDAR products are packed, differently per file: the 100 m stack is int16 decimetres with `SCALE` and nodata `-32768`; the 3 m pilot tiles decode as `z_m = 1000 + v/10`. | IR-56-005 | Assert decoding against bounds, and guard a reprojection with a valid-fraction check — a silently all-NaN destination grid was a real failure mode here. |
| `sample_submission.tif` **is** the catalogue, cell-for-cell (60,988 positives in both). | `evidence/grid.json` (`sample_submission_forensics`) | Never treat it as a zero template. It is the format reference (CRS/shape/transform) and the "do nothing" baseline, and that baseline scores DTI 0.00000 under the organizer's own masking. |
| Grid `(3730, 3292)`, EPSG:32611, transform `(100, 0, 243350, 0, -100, 4508550)`, 5,165,840 footprint cells, 60,894 catalogue cells inside it. | `evidence/grid.json` | One pixel = 100 m exactly along either axis, so offsets quote metres without a resampling correction. |
| The data tab is login-gated (HTTP 302). `fetch_page` reads drivendata.org pages that the sandbox's own HTTP client cannot. | IR-56-003, `knowledge/sources.json` | For official text use the page fetcher; for bytes use the hash-pinned sibling bridge and say so. 3 of 4 inputs reproduce their pin; the LiDAR cache has no pin, so its measured hash is published in `data_manifest.json`. |

## 2. Scoring geometry (where submission decisions should come from)

- `DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw + ε)`, triangular kernel `k(d) = max(1 − d/300 m, 0)` = **3 cells at
  100 m**. Pinned to a brute force to 1e-9 and to the organizer's published aggregates (`tests/test_contracts.py`).
- `k(3 px) = 0`: a dot 3 cells from a truth pixel earns **nothing**; 2 cells earns 1/3 of it.
- Known-fault pixels are excluded from the penalty terms (staff, thread 11516). A sibling measured that
  deleting exactly the 2,545 dots within 2 px of a catalogue trace **raised** the score 0.2708 → 0.2778.
  ⇒ *Mass on the catalogue is worth nothing.* Every emission rule here forbids it structurally.
- β = 0.8 vs α = 0.2: a missed truth pixel costs 4× a false dot at unit mass, so sparse confident dots on
  genuinely new lineations dominate dense fuzz.

## 3. The corrections question — closed, with the numbers

| measurement | value | receipt |
|---|---|---|
| transects usable | 60,756 with a strike, 59,805 valid, DEM crest on 44,390, magnetic ridge on 40,063, both on 29,557 (48.5% of the catalogue) | `offsets_v1.json` |
| ungated offsets | DEM median −0.113 px (n=44,390), joint −0.382 px (n=7,239), abs median 1.476 px | `offsets_v1.json` |
| **estimator noise floor** | median \|offset\| **1.323 px** at random points ≥5 px from any trace; **1.394 px** on catalogue pixels sampled in a random direction; MAD 0.735 px | `calibration_v1.json` |
| null-calibrated (crest height > null p90: 17.57 DEM / 94.10 mag) | DEM median **−0.103 px** (n=3,187), magnetic **+0.030 px** (n=5,297), joint **+0.774 px** (n=156, MAD 1.88) | `calibration_v1.json` |
| independence of the two families | Pearson r(DEM offset, magnetic offset) = **0.022**; both families agree in side within 1 px on **0.26%** of pixels | `offsets_v1.json`, `calibration_v1.json` |
| corridors, ungated | 2 of 1,273 components qualify (25 px, 2,500 m, joint median −2.34 px) | `offsets_v1.json` |
| **corridors, decision gate** (height gate + SE floored at the measured 1.296 px precision) | **0 of 21** qualify; worst z 4.85 | `calibration_v1.json` |
| 3 m LiDAR, 0.9% of catalogue px | pooled median **−0.021 px**, MAD 0.664, 7.9% ≥2 px, **0.27% ≥3 px**; **0 of 13** segments ≥200 m, max z 2.68 | `lidar_calibration_v1.json` |
| coarse vs fine | bias 17.9 m, **RMS 180.9 m** (> 1 cell) between a 100 m offset and the same offset at 3 m | `lidar_calibration_v1.json` |
| holdout (HOLDOUT-DTI, 4 folds, 48,080 withheld positives) | do-nothing 0.00000; evidence snap 0.00016 [0, 0.00045]; subtractive 0.00005; **random jitter 0.00021** — `best_comparable_control = D_jitter` | `holdout_corrections_v1.json` |

**Answer: the catalogue is on the lineations to within the noise of any instrument buildable from these
inputs.** The residual is a coherent ~1 px wobble (see the control below), not a ≥2 px displacement, and the
two independent datasets do not even correlate in their apparent offsets.

## 4. One genuine positive, and why it still emits nothing

The cluster rule ("≥3 of 9 neighbouring candidates") was tested against two nulls built from the same 5,612
candidate target cells (`cluster_gate_control.json`):

| null | what it randomises | mean ± sd | observed |
|---|---|---|---|
| label permutation | which pixel gets which offset — magnitudes, signs and the detector's placement bias preserved | 152.6 ± 15.5 (max 193 of 250) | **680** |
| sign flip | each pixel keeps its offset, re-draws its side (not neutral: a bias b displaces a flipped dot by 2b) | 170.8 ± 14.2 | **680** |

p < 0.004 against both. So the small residual offset is *spatially coherent* — a real, local disagreement
between the mapped trace and the geomorphic/magnetic lineation. It is not emittable because (a) it lives at
~0.8 px, under both the brief's 2 px bar and the estimator's own 1.3 px floor, (b) at 3 m resolution no segment
reaches 200 m, and (c) the holdout cannot see a shift that small at all. A future lane with a 1 m-native
instrument should pick this up: it is the only positive signal this run found, and it is a *registration*
signal, not a discovery signal.

## 5. Instrument lessons (generalise to any "find the feature near the label" lane)

1. **Measure the estimator where the answer is known to be "nothing."** Two nulls, not one: random points
   (magnitude null) and same-points-wrong-direction (geometry null). A "nearest extremum in a window" rule is
   never silent — here its silence was 1.3 px wide.
2. **Never difference a bilinear-interpolated profile at sub-cell spacing.** The interpolation is piecewise
   linear, so its second derivative is a comb of spikes one cell apart, amplified by 1/h². Take the curvature
   stencil over a full source cell and give the window a cell of slack at each end so the crediting range is
   not eaten by the stencil.
3. **A prominence rule measured against flanking troughs is not symmetric under reflection** when the signal is
   a curvature *doublet*: it silently rejects one side and centres your histogram on zero. This one defect was
   capable of manufacturing the lane's entire negative verdict (IR-56-009).
4. **Canonicalise eigenvector signs.** Strike from a structure tensor is defined up to ±1; without a rule, two
   neighbouring pixels of one trace place corrected dots on opposite sides and every signed statistic dies.
5. **Floor the standard error with a measured instrument-precision number.** A robust MAD over four pixels goes
   to zero and z goes to 60. The floor here was the coarse-vs-fine RMS (1.296 px), not a knob.
6. **Characterise the detector on synthetic inputs with a closed-form answer and publish the bias.**
   `scripts/validate_estimator.py` gives a constant +0.2…+0.5 px placement bias with 0.0 px scatter and
   complete detection inside ±2 px. That bounds what the real numbers can mean.
7. **A "coherence" control must preserve the bias.** A sign-flip null looks rigorous but is not neutral when
   the estimator has a constant offset bias; label permutation is the fair version. They disagreed here
   (171 vs 153), which is worth knowing before you trust either.

## 6. Dead ends (do not re-try)

- **The hide-and-recover holdout cannot judge a lateral correction.** Masking visible catalogue pixels
  pixel-exactly makes it blind to ≤3 px shifts: snap 0.00016, subtractive 0.00005, *random jitter* 0.00021,
  do-nothing 0.00000, all overlapping, and the harness itself names the jitter arm as the best control. Use it
  to rule out a catastrophe, never to license a correction.
- **Bulk-harvesting sibling rasters for a duplicate screen is cheap** (485 files, one pass, ~7 min, 0 errors)
  **but the rule it feeds is degenerate in both directions**: the forward fraction fires for 105 of 485 priors
  because our primary raster has *one* dot (100% of one dot is near any prior that touches it), and it fires
  against whole-footprint plausibility masks (5.17 M dots) for any candidate at all. Reverse overlap maxes at
  0.0008 and reciprocal overlap >0.70 is 0 — that is the pair of numbers to report (IR-56-006).
- **Don't clone 400 MB+ siblings or bulk-download ~1,200 rasters**; enumerate
  `git/trees?recursive=1` and fetch selected blobs. `gh api .../contents/` fails on large files, and GitHub's
  `search/code` returns nothing for real paths.
- **Don't chase leaderboard numbers from the sandbox** — JS-rendered behind login; label any board figure
  BOARD-UNVERIFIED.
- **Never treat `_ref54/data/grid/labels.tif` as organizer test labels** (it is a sibling's derived product).

## 7. Code map for reuse

- `src/gems56/corrections.py` — the whole measurement: `load_fields` (sentinel-safe, description-asserted),
  `strike_at` (canonicalised sign), `sample_profiles` (padded window, 1-cell curvature baseline), `find_crest`
  (`nearest` | `strongest`, relative strength, misses stay misses), `control_points` (two nulls), `measure`,
  `joint_offset`, `corridor_table` (`sigma_floor_px`).
- `src/gems56/lane_inputs.py` — resolves the pinned inputs once, returns `(fields, catalogue, footprint, meta)`.
- `scripts/` — `prepare_data` → `measure_offsets` → `calibrate_gate` → `lidar_calibration` →
  `run_corrections_holdout` → `cluster_gate_control` → `build_corrections_submission` → `screen_registry` →
  `validate_estimator` → `make_manifest` → `build_site` → `run_card`. Each writes its own receipt; the site
  and the card read those receipts rather than restating them, so prose cannot drift from measurement.
- `tests/test_contracts.py` — the 10 tests that found IR-56-009. Steal them for any lane with a crest/ridge
  detector.

---

# Round 2 — discovery sub-lane, 2026-10-09

Same evidence discipline: every number below is a receipt value; the receipt file is named.
Nothing here is a board score; no ORGANIZER-CONFIRMED number exists for anything in this repo.

## R1. Why the published top sibling scored 0.2778 (ANSWERED, raster-verified)

- Source: GEMSDOE54 `RUN2-SUMMARY.md`, fetched this session via api.github.com; their check:
  child `dotted_b2_prune_02778` (37,654 dots) == parent `dotted_d2_8_02708` (40,199 dots)
  **minus exactly the 2,545 parent dots within 2 px (200 m) of a USGS catalogue fault**.
- Mechanism: round-1 truth = new faults only; known-fault pixels are masked (staff, thread 11516),
  so a dot ≤200 m off a known trace earns TP only if a new fault lies within its 300 m kernel,
  while its FP cost (α = 0.2) is unconditional. Deleting those dots: 0.2708 → 0.2778.
- Also from that receipt: 0.2778 is *rank 13* on the displayed board (top 0.3774, 0.3195 rank 7);
  the 0.2778−0.2750 gap (0.0028) is inside their local detection floor (paired MDE 0.0043–0.0121);
  and "can we beat 0.2778? Not demonstrated" — no file there has an organizer score.
- Consequence for us: our emission rule structurally excludes catalogue pixels AND their 200 m
  halo — adopted pre-registration in `docs/research/hypotheses-20261009.md`.

## R2. The five new hypotheses and what the holdout said (NEGATIVE)

- Ranked H6 iso-gravity steps > H7 basement×conductivity concordance > H8 tilt-low lineaments >
  H9 INGENOUS 2 m probe gate > H10 probe×structure coincidence: `docs/research/hypotheses-20261009.md`.
- E1 (`evidence/holdout_discovery_v1.json`, evaluator `gems52-pooled-hide-v1`, 4 folds,
  48,080 withheld positives, budgets 8k/15k/25k/37,654):
  - chance floor MEASURED: uniform-random emission scores **0.0152 / 0.0248 / 0.0350 / 0.0445**
    across the four budgets — on this instrument uniform coverage of diffuse thinned truth is a
    *strong* strategy, stronger than any sibling receipt's chance arm (theirs 0.0104).
  - pick multi@25000 = **0.01242 [0.00787, 0.01718]**; paired vs chance@25000 delta
    **−0.02257 [−0.02749, −0.01717]** — strictly below chance. iso 0.0072, bc 0.0052, tilt ~0.0001.
  - canary (per-single-field AUC vs withheld truth): iso 0.535, basement 0.538, cond 0.499,
    tilt 0.567, mag 0.527 — all ≤ 0.90, no leakage; the fields are simply uninformative here.
  - pre-registered verdict: **NEGATIVE** (CI-vs-chance criterion failed; the brief's older bar
    0.00021 is beaten, but a candidate that loses to uniform dots is not promotable).
- Reading: GeoDAWN step/tilt signatures locate *mapped* structure. Once known traces are masked
  (±200 m), what remains in these fields does not concentrate on hidden catalogue segments —
  consistent with this repo's own corrections result that the catalogue sits on the evidence to
  within ~1–2 px. Discovery signal from these layers must therefore come from evidence families
  whose peaks are NOT on known traces (independent maps, heat, seismicity), or from emission
  *along* catalogue extensions, which this instrument is not built to reward.

## R3. Instrument defect found by E1 and fixed once in the template (IR-56-015)

- `transform.scarp_step` zero-fills the exterior before differencing: on the real footprint the
  23,600-cell rim band returned median 5.28 vs 0.47 interior, and **56.5 % of iso_step's
  top-25,000 cells were rim cells** — the first E1 run was measuring the data edge, not geology.
- `rank01` had the mirror-image bug: NaN-inside-valid cells landed in the top histogram bin
  (rank ≈ 1.0), so edge-masking a transform without fixing rank01 re-created the artefact.
- Fixed once in `src/gems56/transform.py` (support masks in `scarp_step`; 3σ band in
  `hessian_line`; 2 px band in `gradient_magnitude`; finite-only ranking in `rank01`), six
  regression tests in `tests/test_transform_edges.py` (each fails pre-fix), first run preserved as
  `evidence/holdout_discovery_v0_prefx.json`, E1 re-run — verdict unchanged (below chance either
  way), which is what a robust negative looks like.
- Lesson (generalises): **any transform that touches the zero-filled exterior must publish its
  support mask, and the ranker must not resurrect masked cells.**

## R4. Data placement solved (IR-56-016)

- `bash scripts/download_competition_data.sh` (alias `scripts/fetch_inputs.sh`, the name the pins
  document): route A verifies official files dropped in `data/raw/`; route B assembles from the
  owner's GitHub bridge verifying BOTH the live owner-manifest shard hashes and our pins.
- Exercised end to end this session: features 418,912,844 B `4371c82e…`, catalogue `7ba308cc…`,
  sample `2176d08e…`, lidar scarp `b5e53d67…` — all match `registry/input_pins.json`;
  `evidence/grid.json` regenerated byte-identically (determinism check).

## R5. The probe layer is obtainable (was "blocked" in round 1)

- GDR 1391 (DOI 10.15121/1881483, CC BY 4.0) fetched live this session; the 1,080,530 B zip in
  `data/external/` unpacks to 3,800 NAD83 points (3,439 inside the competition grid bbox),
  T2m 5.8–70.6 °C, F2mDAB −7.1…+54.7. Round 1's "not downloadable from this sandbox" is obsolete:
  the bytes ride in through the org's hash-pinned mirror (`GEMSDOE48` → `GEMSDOE24` commit).

## R6. The registry lane gate, round 2 (receipt: `evidence/lane_gate_discovery_v2.json`)

- Corpus: 996 mirrored rasters → 960 on-grid single-band priors (36 off-grid/multiband, listed not
  dropped), both phases run through the vendored `gates.lane_report` — surface AND final dots.
- Surface phase: **PASS / PASS** — max Spearman 0.193 (bar 0.90), zero near-offenders; the ranked
  field the dots came from correlates with nothing in the registry.
- Dots phase: literal **DUPLICATE/STOP** and policy **DUPLICATE/STOP** — 22 informative priors
  (13GEMSDOE composites, 15GEMSDOE curv_scarp, pindrop-v4, GEMSDOE54 registry rasters) each
  contain ≥70 % of our 25,000 dots within 3 px. The trigger is density-degenerate: for every
  offender `near_frac ≈ its own 3 px halo coverage of the grid` (0.887 vs 0.861, 0.740 vs 0.759,
  0.700 vs 0.735), i.e. any dot set whatsoever would trip it; max Spearman on dots 0.043, identical
  hashes 0, reciprocal >0.70 = 0. Logged as **IR-56-018** (mirror of IR-56-006). Protocol executed
  as written: verdict logged, nothing promoted.
- Net round-2 verdict: **NEGATIVE twice over** (holdout below chance; gate stop) — the unique TIF
  is published for review with both reasons in its receipt, note and the front-page banner.
