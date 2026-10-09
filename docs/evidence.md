# Evidence table — sources, verification status and claim labels

Checked 2026-10-09 from the sandbox. "Fetched" means the page or file text was retrieved and read in this session.
"Search snippet" means only the search-result text was read. "Listed" means the source was not opened.

## A. Official competition sources

| ID | Source (official link) | What it establishes | Status |
|---|---|---|---|
| C1 | [Problem description, metric and submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Metric: distance-weighted Tversky; α = 0.2, β = 0.8; triangular kernel, R = 300 m (3 px); predictions are probabilities in [0, 1]; GeoTIFF; EPSG:32611; 100 m; float32; same bounds as training data; data outside bounds null/NaN; one sample submission provided. | **Fetched** |
| C2 | [Official rules PDF, NLR doc 96647 (Sept. 2026)](https://docs.nlr.gov/docs/fy26osti/96647.pdf) | §3.2: single GeoTIFF, single raster layer, 100 m; generative-AI use must be disclosed in the narrative. §3.3: labels come from the INGENIOUS Great Basin Regional Dataset Compilation (DOI [10.15121/1881483](https://doi.org/10.15121/1881483)). §3.4: up to 3 submissions per week; one final submission. §3.6.2: one submission chosen without knowledge of private scores. Appendix A.4/A.5: originality and third-party-content warranties. | **Fetched** (all 7 chunks read; A.4–A.5 quoted from chunk 4; A.6–A.17 and the end from chunks 5–6) |
| C3 | [Leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) | Public scores. | **Fetched, but client-rendered: the page returns "Loading..."**, so no score can be read from it. See IR-04. |
| C4 | [Data download page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) | Training features, labels, sample submission, DEM links. | **Fetched: redirects to the login page** (`/accounts/login/?next=/competitions/306/competition-doe-gems/data/`). Not accessible from the sandbox. |
| C5 | [Reference solution (John Lipor, Portland State)](https://github.com/drivendataorg/gems-prize-reference-solution) | U-Net baseline; `data/` holds only `.gitkeep`; `*.tif` is git-ignored. | **Fetched (clone)** |
| C6 | [Competition home](https://www.drivendata.org/competitions/306/competition-doe-gems/) | Overview. | Listed |

## B. Public data sources (free, official)

| ID | Source (official link) | What it establishes | Status |
|---|---|---|---|
| D1 | [GeoDAWN airborne magnetic and radiometric surveys (USGS)](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) | Survey description; **rights: CC0 1.0**; 149,030 line-km over 51,857 km²; flight lines 200 m (Area 1) and 400 m (Area 2). | **Fetched** |
| D2 | [USGS Faults / Quaternary Fault and Fold Database](https://www.usgs.gov/programs/earthquake-hazards/faults) | Catalogue of Quaternary faults; **"Public Domain"**; GIS download link. | **Fetched** |
| D3 | [SGMC geodatabase (ScienceBase 5888bf4f…)](https://www.sciencebase.gov/catalog/item/5888bf4fe4b05ccb964bab9d) | 1:50,000–1:1,000,000 state geologic maps. **The page says this 2017 release is superseded by [DOI 10.5066/P1A3DQZK](https://doi.org/10.5066/P1A3DQZK)**. | **Fetched** |
| D4 | [INGENIOUS regional dataset compilation, GDR submission 1391](https://gdr.openei.org/submissions/1391) | **Licence CC BY 4.0.** Lists 2 m temperature probes (1.03 MB), Quaternary Faults v2 (5.85 MB, 2023-06-27), Quaternary volcanics (9.44 MB), paleo-geothermal features (82 kB), well and spring temperature/chemistry (19.85 MB), earthquake density (22.98 MB). | **Fetched** (download links listed; the zips were not downloaded because the sandbox cannot reach gdr.openei.org) |
| D5 | [Stanford Geothermal Workshop 2025, Hermant, Kiersnowski, Bellanger](https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Hermant.pdf) | Reports that the distance between USGS Quaternary faults and the TLS fault label **can be up to 400 m** in North Central Nevada, and discrepancies **>150 m** with a clear offset. The "TLS label" is a deep-learning detection, not a refined USGS trace. | **Search snippet only** (full PDF not opened). See IR-09. |
| D6 | [Mnih & Hinton, "Learning to Label Aerial Images from Noisy Data", ICML 2012](https://mlanthology.org/icml/2012/mnih2012icml-learning/) | Two robust losses for labels that are "incomplete and sometimes poorly registered". | **Search snippet only** (abstract text read). |
| D7 | [USGS 3DEP / National Map downloader](https://apps.nationalmap.gov/downloader/) | Source of the 1 m DEM tiles. | Listed. Not reachable from the sandbox. |

## C. Sibling-repository artefacts (owner's own work; never treated as verification)

| ID | Artefact | Used for | Label |
|---|---|---|---|
| S1 | [GEMSDOE32 template `src/gems32/metric.py`](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/0d6a6243147cd63a2000412d575d4c80a36d3a62/src/gems32/metric.py), commit 0d6a624 | Vendored into `src/gems/metric.py`. 18 tests pass against it. | Owner code, verified by our tests against a brute-force reference. |
| S2 | GEMSDOE32 `src/gems32/submission.py` (commit 0d6a624) | Footprint-aware portal audit; the parallel validator here is a re-implementation of the portal rules, see IR-07. | Owner code |
| S3 | GEMSDOE30 `data/external/derived_*_100m_u8.tif` (QFaults v2, SGMC, volcanics, paleo, 2 m probes) | Catalogue proxy and evidence proxy for the corrections measurement. EPSG:32611, 3292×3730, 100 m, origin (243350, 4508550); verified by reading the files. | Owner-derived from D2/D3 (rasterisation not independently re-derived). |
| S4 | GEMSDOE32 `docs/downloads/submissions_manifest.json` | Says the H33-2-B2 file is **UNSCORED**. | Owner record |
| S5 | GEMSDOE32 `docs/data/feed.json` and `README.md` | Quotes leaderboard ranks 0.3262 / 0.3222 / 0.3195 / 0.3042. The file and the README disagree on ranks (IR-04). | Owner claim; **not verified** |

## D. Claim labels (required by the brief)

- **HOLDOUT-DTI** (evaluator version, withheld positives, 95% CI): **none computed**. The training features and labels are not in the sandbox.
- **ORGANIZER-CONFIRMED** (copied from a submission-page receipt): **none**. No submission has been made from this repository.
- **CLAIM / USER-REPORTED**: every leaderboard figure in the brief, and every score in the sibling repositories, sits here. None is verified.
- **PROJECTION**: none written as a score.

## E. Verification log (line by line, this session)

| Step | Result |
|---|---|
| Fetched C1 and read the metric formula and the format bullets | Matches the implementation in `src/gems/metric.py` |
| Fetched C2 (all 7 chunks) and read §3.2–3.6, A.4–A.5, A.10 | Quoted text matches the fetched chunks |
| Fetched C3 | Page is client-rendered (`Loading...`); leaderboard NOT verified |
| Fetched C4 | Redirect to login confirmed |
| Read the GeoTIFF headers of the S3 rasters | EPSG:32611, 3292×3730, 100 m, origin (243350, 4508550), uint8, nodata 255 |
| Re-computed the metric worked example | 3.00 / (3.00 + 0.2·1.89 + 0.8·2.00) = 0.6027 → 0.60 |
| Ran the vendored metric against a brute-force reference (4 random grids) | Agree to 1e-6 |
| Numeric check of the break-even credit | Adding unit mass raises DTI iff k > α·DTI (exact under α+β = 1) |
| Indexed all 944 TIFs in the GEMSDOE* account | 920 on grid; 432 share a hash with another file (see IR-03) |
