# Ranked geological hypotheses (preregistered candidates)

2026-10-09. Five candidates ranked by **expected DTI improvement vs implementation cost**.
Each names its layers, target physical signature/operator, why it could expose fault geometry
missing from the USGS/INGENIOUS catalogue (rather than merely recover known-fault habitat),
how it differs from implemented repository/prior-art work, expected benefit, and cost.
Hypothesis 1 was implemented and validated on a spatially-blocked holdout this session
(HOLDOUT-DTI, simulated corrections truth). Budget note: the session's 3-experiment budget is
spent (E1 measurement, E2 leakage canary, E3 holdout); H2–H5 are preregistered future lanes.

## The metric constraint every hypothesis must respect

DTI = T/(0.2·(T+F) + 0.8·K); a dot pays iff its kernel credit exceeds 0.2·DTI (~0.052 at
DTI 0.26) — it must land within ~284 m of a hidden truth pixel. Known-fault pixels are
masked pixel-exactly (forum 11516), so the catalogue line is never the target. Every
hypothesis below therefore targets **off-catalogue** positions that the hidden truth
(corrections within 300 m of known traces, plus genuinely new faults) can occupy.

## 1. Corrections: catalogue-to-evidence registration offset — IMPLEMENTED + HOLDOUT-VALIDATED

* **Layers:** `det_elev` (12), `det_elev_slope` (19); 1 m USGS 3DEP LiDAR (calibration only);
  the vector catalogue records (USGS QFaults + INGENIOUS).
* **Signature / operator:** perpendicular transects ±400 m on every catalogue trace;
  strongest-crest offset of the DEM-scarp ridge per record (crest = ridge of the slope of
  detrended elevation); consistent offset = |median| > 2 px, sign agreement ≥ 0.70, ≥ 8
  transects; emit dots on the connected crest line, off-catalogue, inside the footprint.
* **Why it catches catalogue-missing geometry:** the organizers confirmed corrections within
  300 m of known traces are in the hidden GT (forum 11516); USGS-to-refined discrepancies up
  to 400 m are documented (Hermant et al., Stanford Geothermal Workshop 2025). The catalogue
  line is masked, so only the refined position scores.
* **Differs from prior art:** siblings emit on catalogue-distance halos or learned fields;
  none measures the catalogue-to-evidence offset per vector trace with a LiDAR-calibrated
  crest and a per-record consistency gate.
* **Expected benefit / cost:** validated this session — HOLDOUT-DTI(sim) 0.31049
  [0.282, 0.338] vs 0.00000 masked control and 0.01174 random (26,813 withheld positives).
  Cost already spent. Real-world effect: captures the corrections slice of the hidden truth.
* **Named non-fault mimic:** erosional terraces / alluvial-fan edges (same convex crest,
  no fault); a crest can belong to a neighbouring unmapped strand (would still score as a
  new fault). The 1 m LiDAR confirms the crest is a real sharp scarp; it cannot prove it is
  a fault.

## 2. Magnetic-gradient ridge lineaments off-catalogue — preregistered future lane

* **Layers:** `tmi_hg` (3), `tc` (6), `rtp` (2), `tmi` (14).
* **Signature / operator:** ridge tracing of the horizontal-gradient / tilt-angle fields;
  strike-family filtering (Basin-and-Range orientation families); exclude anything within
  2 px of the catalogue (masked); corroborate with a DEM scarp where available.
* **Why it catches catalogue-missing faults:** faults with magnetic contrast produce gradient
  ridges even where scarps are absent (buried or eroded faults) — the largest pool of
  genuinely new faults in the footprint.
* **Differs from prior art:** siblings feed the mag bands into CNNs as inputs; none traces
  mag ridges as primary lineament evidence with strike filtering and a holdout gate.
* **Expected benefit / cost:** moderate — largest new-fault pool, but lithologic contacts
  give false ridges (needs scarp corroboration). Cost ~1 session. Measured this session as a
  *measurement*: the tmi_hg ridge agrees with the 1 m LiDAR scarp crest within 2 px ~70% of
  the time (MAD 1.16 px) — a usable but noisy locator.
* **Named non-fault mimic:** lithologic contacts and pluton edges produce the same gradient
  ridges without a fault.

## 3. Radiometric alteration halos along faults — preregistered future lane

* **Layers:** `cond_surf` (17); cached GeoDAWN K/Th/U/TC radiometrics (7GEMSDOE
  `external/geodawn_rad`, free/public USGS GeoDAWN, DOI 10.5066/P93LGLVQ — availability
  verified: cached in the sibling repo).
* **Signature / operator:** K/Th ratio and total-count lineament detection; halo = elongated
  high-ratio anomaly parallel to a scarp or gradient ridge; off-catalogue.
* **Why it catches catalogue-missing faults:** geothermal fault conduits produce
  clay/potassium alteration halos; the competition asks for geothermal-indicative faults, so
  alteration-aligned faults are exactly the target class the catalogue misses.
* **Differs from prior art:** siblings use `cond_surf` as one CNN input; none builds ratio
  lineaments with a holdout gate.
* **Expected benefit / cost:** moderate (goal-aligned) but the GeoDAWN radiometrics are
  ~1 km flight-line scale — coarse at 100 m. Cost ~1 session.
* **Named non-fault mimic:** evaporite/playa potassium anomalies and man-made disturbance.

## 4. Basement-depth edges under cover — preregistered future lane

* **Layers:** `depth_to_base_surf` (15); cached 3 m LiDAR scarp product (GEMSDOE48
  `h52_scarp3m_100m`, free/public USGS 3DEP-derived — availability verified: cached).
* **Signature / operator:** gradient ridge of depth-to-basement, corroborated by a DEM scarp;
  emit at the corroborated edge, off-catalogue.
* **Why it catches catalogue-missing faults:** faults control basin-fill thickness; buried
  fault edges in alluvial cover are invisible in the catalogue but offset the basement
  surface.
* **Differs from prior art:** GEMSDOE40 tried depth-KDE clusters cross-family; a
  gradient-edge + scarp corroboration with a blocked holdout is a different operator.
* **Expected benefit / cost:** low–moderate (indirect, two-step inference); cost low–medium.
* **Named non-fault mimic:** depositional onlap edges and paleo-valley walls offset the
  basement surface without a fault.

## 5. Geodetic strain-gradient anomalies — preregistered future lane

* **Layers:** `geod_shearrate` (7), `geod_dilaterate` (8), `geod_2ndinv` (4), `deq_n100a15`
  (10), `ieq_n100a15` (16).
* **Signature / operator:** localized shear/dilation maxima off-catalogue; wavelength-filtered
  ridge detection.
* **Why it catches catalogue-missing faults:** active faults concentrate strain; the 2020
  Mw 6.5 Monte Cristo rupture occurred on the largely unmapped Candelaria fault, inside the
  footprint (USGS field response, SRL 92(2A) 823–829).
* **Differs from prior art:** GEMSDOE51 tried Kreemer et al. (2000) Eq. 3 coarse priors
  (Spearman 0.14 — weak); a fine-scale strain-gradient ridge detector with holdout gating is
  a different operator.
* **Expected benefit / cost:** low (the strain field is smooth at 100 m; one event is a weak
  prior); cost medium.
* **Named non-fault mimic:** sedimentary basin compaction and groundwater withdrawal
  produce dilation anomalies without faults.

## Ranking rationale

Expected DTI improvement per unit cost. H1 is the only candidate whose target (corrections
near known traces) is **confirmed by the organizers** to be in the hidden label set, and the
only one with a completed holdout. H2 addresses the largest untapped pool (genuinely new
faults) but carries lithology false-positive risk. H3 is the most goal-aligned but the
coarsest data. H4 is cheap but indirect. H5 is the weakest signal at the official resolution.
