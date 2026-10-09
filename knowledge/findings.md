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
