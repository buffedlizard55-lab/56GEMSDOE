# Round-2 hypotheses — 2026-10-09 (corrections-lane repo, discovery sub-lane)

Status key: **VALIDATED / NEGATIVE / BLOCKED / UNTESTED**. No number below is a score for a
submission; expected-DTI ranges are *judgements* informed by receipts named inline. This file
supersedes nothing: `hypotheses.md` (round 1) stays as the earlier record.

Scope rule from the brief: each hypothesis names (a) the layer(s), (b) the physical signature,
(c) why it should catch a fault **missing** from the USGS/INGENIOUS catalogue rather than one
already in it, (d) how it differs from anything already implemented, (e) the free official source
and its obtainability, and is (f) ranked by expected DTI improvement ÷ implementation cost.

**What "already implemented" is measured against (this session, line by line):**

* *This repo*: only the corrections lane (crest-offset measurement + its negative-result rasters).
  No discovery emitter exists here yet. Measured: `src/gems56/corrections.py`, `scripts/`.
* *Sibling corpus*: `docs/research/registry-index.json` — 944 published raster **paths**, 651
  distinct sha256, name-grepped this session. Counts below are path-substring hits; they are a
  floor on occupied *families*, not an audit of private code (stated so a reviewer can repeat it).
* *Sibling holdout receipts*: GEMSDOE54 `RUN2-SUMMARY.md` (fetched this session from
  `api.github.com/repos/buffedlizard55-lab/GEMSDOE54/contents/RUN2-SUMMARY.md`) — their
  `gemsdoe54-segment-cv` v2 numbers: chance C0 = 0.0104 [0.0091, 0.0117]; magnetic horizontal-
  gradient ridge C3 = 0.0148 [0.0118, 0.0180]; mag×gravity cross-gradient C5 = 0.0128
  [+0.0024 vs chance, CI touches 0]; basement-step gradient C6 = 0.0097 (chance); geodetic shear
  ridge C2 = 0.0098 (chance); SGMC complement C1 = 0.0483 (sibling-occupied); learned C4 = 0.0465.
  **Those are HOLDOUT-DTI on their evaluator, not board scores.** Their instrument ≠ ours, so they
  are *priors*, not predictions for our numbers.

**Our own holdout bars (this repo's evaluator `gems52-pooled-hide-v1`, 4 folds, whole-component
withholding, visible catalogue masked pixel-exactly):** previous best arm = `D_jitter`
0.00021 [0.000003, 0.00051] (`evidence/holdout_corrections_v1.json`) — a corrections arm, i.e.
essentially empty; a chance control for *discovery-sized* emissions did not exist in our receipts
and is added in this round (E1).

---

## H6 (rank 1) — Isostatic-gravity persistent-step lineaments (the unoccupied potential-field family)

- **Layer(s):** competition bands 13 `iso_grav_anom`, 5 `iso_grav_anom_slope`,
  11 `iso_grav_anom_vg`, 18 `iso_grav_anom_hg` (band inventory: `evidence/grid.json`,
  measured this session from `data/training_features.tif`).
- **Physical signature:** a *two-sided, along-strike-persistent step* in the isostatic anomaly —
  the repo's own `transform.scarp_step` (half-width 150 m, persistence ≥ 2 km, 4 strikes),
  ranked to [0,1]; the density contrast of a basin-bounding normal fault or a detachment break
  produces a step in the anomaly that persists along strike, while an intrusion body does not.
- **Why it should catch a missing fault:** the Quaternary catalogue maps *surface rupture*.
  Basin-rooted faults whose young expression is buried under alluvium are structurally invisible
  to surface mapping but step the density field; GeoDAWN's gravity is exactly a cover-blind view.
  The named mimic (must be stated): (i) intrusive/sill bodies, (ii) **topographic leakage through
  the isostatic correction itself** — residual terrain-correlated error that follows range fronts,
  which is why the run requires the two nulls/controls of E1 before any emission is believed.
- **Difference from what exists:** registry name-grep `iso` = **0** of 944 paths (this session).
  Gravity touches only 3 paths: `h7-rtp-euler-gravity-context` (context channel in an Euler
  stack), `h55-grav-rtp-logedge` (one log-edge family), and sibling-54's C5 *cross-gradient*,
  where gravity was the *second* family and the arm sat on chance (0.0128, CI touching 0).
  No sibling receipt tests pure isostatic-step emission. This repo implements none of it.
- **Validation:** local, no new data — E1 in this run (holdout arms `iso_step`, plus canary).
- **Source:** competition stack only (login-gated tab; bytes hash-pinned via the owner bridge,
  `registry/input_pins.json`, re-verified this session: sha256 `4371c82e…`).
- **Cost:** low (one transform + rank + top-k). **Expected (judgement):** the best-placed of the
  unoccupied families: 1.0–1.8× a chance floor of the C0 class (≈0.010–0.018 in our units).

## H7 (rank 2) — Basement-depth × conductivity concordant steps (buried basin-bounding faults)

- **Layer(s):** band 15 `depth_to_base_surf` (m, p50 316 m, p99 3,420 m — measured this
  session), band 17 `cond_surf` (0.19–4.97, p50 2.89 — measured this session).
- **Physical signature:** `min(rank step(basement depth), rank step(conductivity))` — a throw
  in the basement surface *and* a conductivity contrast at the same cells (`transform.scarp_step`
  on both, intersection of ranks). Concordance, not either field alone: a depositional onlap
  steps basement depth without a fluid-conductivity break; a saline playa edge breaks
  conductivity without basement throw.
- **Why it should catch a missing fault:** the named mimic pair above is precisely why one
  family alone fires on basin *outline*; requiring both steps to coincide at 100 m removes
  basin-margin onlaps and brine edges, leaving fault throw with a hydrothermal/fluid signature —
  the damage zone a surface mapper never saw under the alluvial fan.
- **Difference from what exists:** sibling-54 tested basement-step **alone** = chance (C6
  0.0097); registry `basement` = 2 paths, both *gated* uses (`triple-conv-basement-cover-gated`
  — basement as a gate on a topographic emitter, not as the emitter). Conductivity touches ≤4
  paths (`dilcond` = dilatation-conditioned, not conductivity; `conduit-conflict`, `condmag`
  — name-visible but different mechanisms: none is the step-concordance rule). This repo: none.
- **Validation:** local — E1 arms `bc_step` (+ per-field canary: basement alone, cond alone).
- **Source:** competition stack (same pins). **Cost:** low. **Expected:** H6's caution (C6 =
  chance for basement alone) means concordance must *earn* its keep: 0.9–1.6× chance.

## H8 (rank 3) — Tilt-angle (band 6 `tc`) near-zero contour lineaments

- **Layer(s):** band 6 `tc` (“Tilt angle or total curvature – magnetic field derivative for edge
  detection”; observed range this session **2.95–88.57, no sign change** — the description is
  ambiguous and the data are magnitude-like; flagged as an irregularity, IR-56-014), optionally
  gated by band 3 `tmi_hg`.
- **Physical signature:** proximity to *low* `tc` — the tilt/curvature zero-contour family
  (Miller & Singh 1994 tilt-angle edge rule), i.e. contact edges at any source depth, smoothed
  100 m and ranked.
- **Why it should catch a missing fault:** buried contacts offset by blind faults carry an edge
  that amplitude-gradient ridges (siblings' favourite) miss when the source is deep or the
  contrast is broad; the catalogue cannot contain what no surface trace exposes.
- **Difference from what exists:** registry `tc`/`tiltc`/`depth_to` = 0 paths; the 4 `tilt` hits
  are `h20-1-sarnnpu-…-tilt-wingcrack` (a mechanical wingcrack model name, not band 6).
  Sibling C3 used raw `tmi_hg` ridges (0.0148, occupied family: `dotted-ridge`, `pindrop-ridge`,
  `tiprelay-ridgeconcord`, `magedge-hgrad-ridge`…). Tilt-zero contours are a different locus
  than amplitude maxima. This repo: none.
- **Validation:** local — E1 arm `tilt_r` + canary. **Source:** competition stack.
- **Cost:** very low (cheapest of the five). **Expected:** 1.0–1.6× chance; high lithology-
  contact mimic risk (the named non-fault process), so it is ranked below H6/H7 despite cost.

## H9 (rank 4) — INGENOUS 2 m probe thermal lineaments as *gating* evidence (not as an emitter)

- **Layer(s):** `data/external/2m_temperature_probe_INGENIOUS_regional_data.zip` (1,080,530 B,
  sha256 `1301f70d…` measured this session): 3,800 NAD83 points, **3,439 inside the competition
  grid bbox** (measured this session), fields `T2m` (°C, 5.8–70.6) and `F2mDAB` (area-normalised
  deviation, −7.1…+54.7).
- **Physical signature:** collinear alignments (≥3 points, corridor ≤200 m) of probes with
  `F2mDAB` above +2σ, i.e. linear hydrothermal leakage — then used only as a *gate* on H6/H7/H8
  dots, never as the emission family itself.
- **Why it should catch a missing fault:** warm linear anomalies mark permeable structures that
  need not have Quaternary surface expression; the named mimics are irrigation, roads and
  drainages — which is exactly why a *gate* (must also coincide with a geophysical step) is the
  admissible role, and a lone probe lineament is not.
- **Difference from what exists:** the probe family is **occupied**: registry `probe` = 10 paths
  (`gems32-probe-S1-ANCHOR-identical-to-live-02600`, `h53-probe-tmi-pointlineation`,
  `derived_gdr_2m_probes_100m_u8`, …). Using probes as a *corroboration gate on a
  basement/gravity step* rather than as the emitter is the part no name in the corpus shows.
- **Validation:** local possible (points are in hand). **Source, checked this session:**
  official landing page **GDR submission 1391**, DOI **10.15121/1881483**, CC BY 4.0 —
  https://gdr.openei.org/submissions/1391 (fetched this session; resource list and 1.03 MB probe
  zip match the file we hold). **Cost:** medium (shapefile → corridor test). **Expected:** low
  as a standalone (sparse coverage: 3,439 pts over 5.17 M cells), moderate as a precision gate.

## H10 (rank 5) — Hydrothermal-leakage coincidence: probe warm-lineament × basement/gravity step

- **Layer(s):** H9 gate ∩ H6/H7 step fields at sites ≥300 m from every catalogue trace.
- **Physical signature:** a warm linear probe alignment *on* a buried structure step — the
  geothermal-vent science target of this project (fault-controlled upflow), expressed as
  coincident surface thermal + subsurface structural evidence.
- **Why it should catch a missing fault:** every individual family has a named mimic (brines,
  lithology, irrigation); the coincidence of two independent physics families on the same
  100 m cells has no single named non-fault process that produces both — that is the whole
  argument, and it is the contrarian bet: everyone else emits from topo/magnetics; nobody in the
  corpus name-grep emits from *heat ∩ buried structure*.
- **Difference from what exists:** no corpus path combines probe + basement + gravity
  (`probe` hits are probe-only or probe×TMI; `basement` hits are gated topography).
- **Validation:** blocked on H6/H7 first passing E1 (composing a gate onto a chance-level field
  cannot beat chance). **Source:** GDR 1391 (checked, above) + competition stack.
- **Cost:** medium-high (composition + tuning). **Expected:** uncertain; ranked last because it
  inherits H7's risk.

### External sources checked this session (for the record)

| source | link | status |
|---|---|---|
| INGENIOUS GDR 1391 (CC BY 4.0, DOI 10.15121/1881483) | https://gdr.openei.org/submissions/1391 | **fetched OK** (page + resource list); probe zip in `data/external/`, hash measured |
| GEMSDOE54 RUN2-SUMMARY (sibling holdout priors, 0.2778 mechanism) | https://github.com/buffedlizard55-lab/GEMSDOE54/blob/main/RUN2-SUMMARY.md | **fetched OK** via api.github.com this session |
| DrivenData evaluation page (DTI formula, format) | https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ | verified in `knowledge/sources.json` (fetch_page) |
| Staff thread 11516 (known-fault masking) | https://community.drivendata.org/t/11516 | verified in `knowledge/sources.json` (fetch_page) |
| Competition data tab | https://www.drivendata.org/competitions/306/competition-doe-gems/data/ | login-gated (HTTP 302 observed); bytes via pinned owner bridge, re-hashed this session |

### Pre-registered validation design (E1, fixed before looking at any result)

- **Instrument:** our shared evaluator only — `gems56.evaluate_holdout` (`gems52-pooled-hide-v1`),
  `gems56.holdout.make_folds(mode="hide", n_folds=4, buffer_px=4, prevalence=0.00294, seed=0)`,
  visible catalogue masked pixel-exactly, paired spatial-block bootstrap (1,000 draws, seed
  520810). No private metric fork.
- **Emission rule (one rule, holdout and shipped file identical):** top-k of the arm's ranked
  field inside `footprint ∧ region ∧ ¬dilate(known catalogue, 2 px)`; value 1.0; budgets
  k ∈ {8,000, 15,000, 25,000, 37,654}. The 2 px (200 m) exclusion of *known* traces is adopted
  from the verified 0.2778 mechanism (GEMSDOE54: parent 40,199 dots − 2,545 dots within 200 m
  of catalogue = child 37,654 dots, 0.2708 → 0.2778 — their raster-level receipt) and from this
  repo's own finding that the catalogue sits within ~2 px of the evidence everywhere.
- **Arms:** `iso_step` (H6), `bc_step` (H7), `tilt_r` (H8), `multi` = mean of the three ranked
  fields, `mag_ref` = `hessian_line(tmi_hg)` (reference only — occupied family, for scale),
  `random` (seeded uniform — the chance floor).
- **Canary:** per-single-field ROC-AUC against pooled withheld truth; **> 0.90 = leakage until
  proven otherwise** (threshold from the brief).
- **Primary pick rule (deterministic, fixed now):** among {`iso_step`,`bc_step`,`tilt_r`,`multi`}
  at k = 25,000, take the highest pooled HOLDOUT-DTI. It **passes** iff its paired 95 % CI vs
  `random`@25,000 is strictly > 0, no new-field canary exceeds 0.90, and every arm stays above
  the previous repo best 0.00021. Fail ⇒ verdict NEGATIVE, no slot, and the emitted research
  raster is labelled NEGATIVE — exactly the corrections-lane precedent.
- **Budget:** experiments E1 (holdout) → E2 (build+validate) → E3 (uniqueness screen); stop after
  these three.
