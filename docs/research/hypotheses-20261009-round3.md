# Round-3 hypotheses — 2026-10-09 (corrections lane, session `arena/e86c5610-56gemsdoe`)

Status key: **VALIDATED / NEGATIVE / BLOCKED / UNTESTED**. Pre-registered **before** any join of
offset tables to fault attributes was inspected. No number below is a submission score.

## Why this round exists (the gap it attacks)

Rounds 1–2 of this lane measured the catalogue-to-evidence offset (transects ±400 m, DEM-scarp
crest + magnetic ridge, LiDAR-calibrated) and emitted dots on the crest lines of the 28 records
whose strongest-crest offset is consistently > 2 px. **Every validation of "the crest is where the
refined fault is" so far is construction-biased**: the round-1 holdout truth was the measured crest
lines themselves (simulated corrections). The one piece of independent evidence (1 m LiDAR: the
100 m crest sits on the 1 m scarp, MAD 0.29 px) proves the crest is a *real scarp*, not that the
scarp is *the mapped fault's corrected position* rather than a terrace, a fan edge, or a
neighbouring unmapped strand.

This round adds the missing independent test using **official metadata that has never been joined
to the measurements in any sibling repo** (registry name-grep: `FCODE`/`MAPSCALE`/`FTYPE_` = 0
paths): the QFaults/INGENIOUS compilation's own per-record **location-quality fields** —
`FTYPE_` (Well Constrained / Moderately Constrained / Inferred), `MAPSCALE` (24 … 500) and
`FCODE2023` — plus `SLIPSENSE`/`DIPDIRECT`.

Source (verified this session, files in hand, sha256 in `registry/input_pins.json` pattern):
`sibling GEMSDOE51 registry/official/` mirror of the official shapefile
`qfaults_ingenious_nad83conus117_2023-06-27.shp` (GDR submission 1391,
https://gdr.openei.org/submissions/1391, CC BY 4.0; field definitions
`qfaults_8_README_fielddefinitions_*.txt` fetched and read this session via api.github.com).

---

## H-C1 (rank 1) — Map-quality stratification of the catalogue-to-evidence offset

* **Layer(s):** round-1 per-record offsets (committed, unchanged:
  `evidence/corrections/record_offsets_dem_slope_strongest.csv`, 125 records; secondary:
  `…_nearest.csv`, `…_mag_hg_strongest.csv`) ⨝ `qfault_attributes.csv`
  (`FTYPE_`, `MAPSCALE`, `FCODE2023`) on record id = `NUM`.
* **Physical signature:** positional error of *source mapping*. A trace compiled at 1:250 k or
  rated "Inferred" carries a horizontal positional tolerance an order of magnitude larger than a
  1:24 k "Well Constrained" trace (cartographic convention: ~0.5 mm at publication scale → 12 m
  at 1:24 k, 50 m at 1:100 k, 125 m at 1:250 k, 250 m at 1:500 k; NMAS horizontal-accuracy
  convention, https://www.usgs.gov/usgs/national-map-accuracy-standards-nmas — page not reachable
  from this sandbox, convention cited from the USGS "Standards for Digital Line Graphs"
  lineage; flagged as IR-56-030 if the convention cannot be verified online this session).
* **Why it discriminates fault-correction from mimic:** if the measured offsets are *map-position
  errors* (the corrections-lane hypothesis: the refined trace sits at the scarp crest), the offset
  magnitude must stratify with the catalogue's own statement of how well each record is located.
  Erosional terraces and alluvial-fan edges have **no reason** to respect the map's metadata.
* **Named non-fault process that could mimic the stratification (pre-registered confound):**
  low-relief, sediment-covered terrain is both (a) where mappers infer rather than constrain
  traces and (b) where DEM slope-crests are dominated by terrace/fan edges rather than fault
  scarps. The stratification could then reflect terrain, not map error. **Control:** repeat the
  test within the top prominence quartile of transects (sharp crests) and within the
  LiDAR-covered subset; report both regardless.
* **Pre-registered test (primary, fixed now):** among records with `n_transects >= 8` in the
  `dem_slope_strongest` table, let `A(r) = |median_offset_px|`. H-C1 **passes** iff BOTH
  1. Spearman ρ(`MAPSCALE`, `A`) > 0 with one-sided p < 0.05, AND
  2. median `A` over records with `FTYPE_ != "Well Constrained"` exceeds median `A` over
     `FTYPE_ == "Well Constrained"` with one-sided Mann–Whitney p < 0.05.
  Secondary (reported, not gating): the same two tests on `frac_abs_gt_2px`, and on the
  `mag_hg_strongest` and `dem_slope_nearest` tables; Kruskal–Wallis across the three `FTYPE_`
  classes; ρ(`FCODE2023`, `A`).
* **Difference from anything implemented:** no sibling path joins fault-attribute metadata to a
  measured offset distribution (rounds 1–2 of this repo did not; registry grep = 0 hits).
* **Cost:** trivial (CSV join on committed measurements). **Expected:** if the corrections
  hypothesis is right, a monotone offset–quality relation with ρ ≈ 0.2–0.4 (125 records, enough
  for p < 0.05 only if the effect is real).

## H-C2 (rank 2, secondary — supportive only, never gating) — Dip-direction consistency

* **Layer(s):** `DIPDIRECT` + `SLIPSENSE` (attributes) vs the scarp facing at the measured crest
  (sign of the det-elev gradient across the crest, and the LiDAR product's `facing_at`).
* **Signature:** a normal-fault scarp free-faces the downthrown (hanging-wall) side, i.e. the
  dip direction; a consistent facing–dip match across normal-slip records supports
  crest = fault scarp.
* **Named mimic (pre-registered, severe):** in the Basin and Range, alluvial fans and terraces
  also face the basins — the same direction as the hanging walls. H-C2 therefore cannot separate
  fault scarp from basinward geomorphology; it is reported as context only and can never promote
  an emission on its own.
* **Test:** among `SLIPSENSE == N` records with a parseable `DIPDIRECT` and n >= 8 transects,
  fraction of records whose crest-facing azimuth is within 45° of `DIPDIRECT`, vs the 25 % chance
  level (uniform on the circle, ±45° window), binomial one-sided p.
* **Difference:** facing is used descriptively in round-1 crops; never tested against dip
  metadata anywhere in the corpus.

## Emission decision rule for this round (fixed before inspection)

The round-1 gate stays the base (the lane paragraph's rule): records with
`|median_offset_px| > 2`, `sign_agreement >= 0.70`, `n_transects >= 8` on
`dem_slope_strongest`. On top, each surviving record gets a **map-tolerance z-score**

    z_map(r) = |median_offset_m| / tol(r),
    tol(r)   = 0.0005 * MAPSCALE * 1000  (m)   if FTYPE_ == "Well Constrained",
             = 400 m (the transect half-width = uninformative bound) otherwise

(0.5 mm at publication scale; an Inferred trace has no accuracy claim, so its tolerance is the
measurement window itself — it can never fail the gate, which is stated, not hidden).

* **If H-C1 passes:** the shipped emission is the round-1 crest lines restricted to
  `z_map <= 3` (an offset within 3× the record's own stated accuracy is a plausible map
  correction; beyond that the crest is more likely a *different* feature — a neighbouring strand
  or a terrace — than the mapped trace's true position). Sensitivity table for
  `z_map* ∈ {1.5, 2, 3, ∞}` is published with the run card.
* **If H-C1 fails:** the corrections hypothesis loses its only independent test; the round
  verdict is NEGATIVE, the research raster is labelled do-not-submit, and per the lane paragraph
  the fallback position ("offsets cluster under two pixels" on the *nearest*-crest reading)
  is restated as the lane's answer.
* Values 1.0 on kept crest-line pixels, off-catalogue (>= 2 px), inside the footprint, NaN
  outside — identical writer/validator chain as round 1.

## Machinery re-check (pre-registered)

Re-run the round-1 simulated-corrections holdout (4 folds, pooled DTI, masking model,
block-bootstrap CI) with arms: A1′ (this round's gated emission), A1 (round-1 gate), A0 masked
control, A4 random control at A1′ mass. **Pass:** A1′ DTI > A0 and > A4 with CI excluding 0
(machinery sanity only — the simulated truth remains construction-biased and is labelled as
such). Leakage canary: per-feature AUC on the holdout; > 0.90 means leakage until proven
otherwise.

## Budget

E1 = the H-C1/H-C2 joins and tests; E2 = gated emission rebuild + holdout re-run; E3 = registry
uniqueness screen + validators + run card + site. Stop after these three. No submission slot is
spent; promotion is the selector's separate step.
