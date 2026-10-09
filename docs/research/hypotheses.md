# Candidate hypotheses — ranked, with the data each one needs

Status key: **VALIDATED** = a holdout DTI with CI exists. **BLOCKED** = cannot be tested here; the blocker is named. **NEGATIVE** = a measured null.
No expected-DTI number below is a score. The ranking is qualitative and is a judgement, not a projection.

Scope rule from the brief: each hypothesis must (a) name the layer(s), (b) name the physical signature, (c) say why it would find a fault **missing** from the USGS/INGENIOUS catalogue, (d) say how it differs from what is already implemented here, and (e) name the free official source and whether it is obtainable.

What is implemented in **this** repository today: the metric (pinned from the template), the validator and writer, and the corrections proxy. Nothing else. "Differs from implemented here" therefore means "differs from the registry of earlier runs", judged by grepping the sibling docs (counts below). Those counts are grep hits in sibling documents, not an audit of their code.

---

## H1 (rank 1) — Shallow-temperature lineaments from the INGENIOUS 2 m probe survey

- **Layer(s):** INGENIOUS "2m Temperature Probes" point survey (GDR 1391, CC BY 4.0, 1.03 MB zip), interpolated to the 100 m grid.
- **Physical signature:** linear or en-échelon alignments of anomalously warm 2 m probes (for example, more than 2 σ above a local background) that run along a trend, lie 300 m or more from every catalogue trace, and lie within a corridor that a trend analysis of the probe values picks out.
- **Why it should find a missing fault:** fault-controlled hydrothermal leakage and damage zones can give shallow thermal anomalies on fault traces that never reached the Quaternary catalogue, because the offset is too small or the trace was never mapped.
- **Named non-fault mimic:** shallow groundwater, irrigation or playa-margin moisture; vegetation and soil contrasts; drainage channels; roads and buildings. A 2 m survey alignment can follow a drainage or a road.
- **Difference from what exists:** `2m probes` appears in 2 GEMSDOE30 docs and 1 GEMSDOE32 doc (grep). No thermal-probe lineament feature exists in this repo.
- **Validation:** **BLOCKED.** It needs the labels and a holdout, neither available in the sandbox. A catalogue-only holdout is possible once the probe zip is downloaded, but the sibling notes say the catalogue holdout cannot reward genuinely new faults.
- **Free official source and obtainability:** GDR submission 1391 (CC BY 4.0). Listed in the page we fetched. **Not downloadable from this sandbox** (egress limited to GitHub and package indexes). A user with a normal browser can download it.
- **Cost:** medium (point-to-raster, then a lineament extraction).
- **Expected improvement (judgement):** the highest novelty of the candidates, moderate expected gain, unvalidated.

## H2 (rank 2) — Spring and sinter collinearity from the INGENIOUS well/spring and paleo layers

- **Layer(s):** INGENIOUS "Well and Spring Temperature and Chemistry" geodatabase (19.85 MB) and "Paleo Geothermal Features" shapefile (82 kB).
- **Signature:** three or more springs or paleo-deposits (sinter, tufa) that are collinear within a stated tolerance, on a trend consistent with the regional stress field, and more than 300 m from every catalogue trace.
- **Why it should find a missing fault:** spring and sinter alignments mark conduits, and the conduit can lie on a fault the catalogue never mapped.
- **Named non-fault mimic:** stratigraphic contacts, lithological linear units, drainage valleys, and sampling artefacts (wells are drilled along roads).
- **Difference:** `paleo` appears in 13 GEMSDOE30 docs and 7 GEMSDOE32 docs, and `springs` in 7 and 4. The novelty lies in a strict collinearity test. Not novel as a data source.
- **Validation:** **BLOCKED** (same as H1).
- **Source:** GDR 1391 (CC BY 4.0). Not downloadable from the sandbox.
- **Cost:** low to medium.
- **Expected improvement (judgement):** moderate to low. Springs cluster near known faults, so much of the signal lies within the 300 m corridor that the catalogue already covers.

## H3 (rank 3) — Seismicity-density lineaments from INGENIOUS earthquake density

- **Layer(s):** INGENIOUS "Earthquake Density Models" GeoTIFFs (22.98 MB, CC BY 4.0), or ComCat (USGS).
- **Signature:** linear ridges of earthquake density that trend along a fault direction and are off catalogue.
- **Why it could find a missing fault:** microseismicity aligns on active faults, including unmapped ones.
- **Named non-fault mimic:** mining, reservoir or quarry seismicity; aftershock sequences; network-coverage bias.
- **Difference:** seismicity is already in heavy use (13 GEMSDOE32 docs, 4 GEMSDOE30 docs). **Lowest novelty of the three data-driven candidates.**
- **Validation:** **BLOCKED.**
- **Source:** GDR 1391 (CC BY 4.0); ComCat (USGS) listed, not reached from the sandbox.
- **Cost:** medium.
- **Expected improvement (judgement):** moderate, uncertain.

## H4 (rank 4) — Corrections lane: offset of the catalogue from a DEM-crest scarp

- **Layer(s):** 1 m DEM tiles (USGS 3DEP, listed by the competition), DEM curvature, magnetic gradient ridge (GeoDAWN).
- **Signature:** the crest of a DEM-curvature scarp, or of a magnetic gradient ridge, lying 2 px or more from a catalogue trace along a consistent direction.
- **Why it could find a missing fault:** the brief's own premise is that known traces are misplaced, and the Stanford 2025 paper reports up to 400 m of discrepancy in North Central Nevada (D5).
- **Result so far (PROXY, NEGATIVE):** the USGS SGMC-to-QFaults proxy gives a median nearest-pixel displacement of 1.41 px. Eight of 306 five-km blocks have mean displacement above 2 px, with no consistent direction. The protocol says that when offsets cluster below two pixels the lane emits nothing. **The DEM-crest measurement itself is BLOCKED** (no DEM, no GeoDAWN magnetics in the sandbox). See [corrections-proxy.json](corrections-proxy.json).
- **Named non-fault mimic:** scarps from erosion or landslides; magnetic ridges from lithology contacts or intrusions.
- **Difference:** the sibling repos contain DEM-scarp features (`lidar_scarp_features_u8.tif` in GEMSDOE24 and GEMSDOE7; provenance not checked here) and many scarp-based submissions. Not novel.
- **Validation:** BLOCKED (DEM). The proxy is NEGATIVE; the proxy's own limits are listed in IR-11.
- **Source:** USGS 3DEP (free, official). Listed; not reachable from the sandbox.
- **Cost:** high (1 m DEM at scale).
- **Expected improvement (judgement):** low, given the proxy result.

## H5 (rank 5) — Volcanic-vent alignments as dike or fault proxies

- **Layer(s):** INGENIOUS "Quaternary Volcanics" vents and flows (9.44 MB, CC BY 4.0).
- **Signature:** alignments of vents along a trend, more than 300 m from catalogue traces.
- **Named non-fault mimic:** volcanic vent alignments reflect magma pathways and can be non-tectonic.
- **Difference:** `volcanic` appears in 16 GEMSDOE30 docs and 8 GEMSDOE32 docs. **Low novelty.**
- **Validation:** BLOCKED.
- **Cost:** low.
- **Expected improvement (judgement):** low.

---

## What we should not do

- Copy any sibling submission. The brief forbids it, and the registry shows many byte-identical duplicates (IR-03).
- Use the public copies of competition files (`existing_faults.tif`, `labels.tif`, `sample_submission.tif`) without a rights check (IR-03).
- Rank hypotheses by sibling scores. Those scores are unverified (IR-04, IR-05).

## Free official sources still needed, in order

1. **Competition training files** (`training_features.tif`, `labels.tif`, `sample_submission.tif`, DEM links). Source: DrivenData data page, login required. **Not obtainable from the sandbox**; a registered user can download them into `data/raw/`.
2. **INGENIOUS regional compilation** (GDR 1391), for H1–H3, H5. Free, CC BY 4.0, public. The zips are listed on the page we fetched; the sandbox cannot download them.
3. **USGS 3DEP 1 m DEM tiles** (for H4). Free, official. Listed by the competition; not reachable from the sandbox.
4. **SGMC 2026 update** (DOI 10.5066/P1A3DQZK), to replace the superseded 2017 raster (IR-08).
