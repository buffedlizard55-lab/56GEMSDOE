# Submission downloads — audit inventory; no corrections TIFF is cleared

> **CURRENT CORRECTIONS STATUS: NEGATIVE / STOP. Do not submit any corrections-lane TIFF in this folder.**
> The H57 final-dot registry receipt reports 1.0 within 3 px of a registry raster (>0.70), and
> strict template replay finds 7,111,787 non-NaN cells outside the sample mask plus a missing NaN
> nodata tag. The old run card's `OK to submit` wording is superseded by the post-review card.

This is an audit inventory, not a recommendation list. *Safe to download* means only that a file
can be retrieved for inspection; it is not format clearance, uniqueness clearance, organizer
acceptance, or permission to spend a slot. The H57 all-finite compatibility-gate result does not
waive strict mask/nodata checks or the duplicate-and-stop rule.

| file | what it is | verdict |
|---|---|---|
| `h57-corr-band2px-cover-20261009T191337Z.tif` (+ `.zip`, `.json`) | H57 corrections-band archive — 54,914 dots; original receipt reports all-finite [0,1] values | **NO — NEGATIVE / STOP.** Final-dot near-3-px fraction 1.0 (>0.70); strict sample-mask replay finds 7,111,787 finite cells outside and `nodata=None` vs template NaN. Crest steering was refuted; cover itself was not scored. Download for audit only. |
| `gems56-corr-twinfam9-20261009T190155Z-0279ca86-nan.tif` (+ `.zip`) | PR #14 Round-3 twin-family research artifact; 2,139 dots; separate from H57 | **DUPLICATE / STOP — do not submit.** The existing registry receipt has 12 literal >0.70 directed-proximity flags (max 1.0); H-C1 is negative and its HOLDOUT-DTI is machinery-only. The old “UNIQUE” label is superseded; no scan was rerun. See `evidence/corrections/registry_check_round3_post_review.json`. |
| `h56-final-dotted-ridge-d2p8-20261009T190421Z.tif` (+ `.zip`, `.json`) | Separate artifact from PR #11; outside this H57 strict-gate review | **Not adjudicated here.** This row is not a clearance or rejection; see PR #11's separate receipt and status wording. |
| `h56-disc-multi-b25000-20261009-20261009T165646Z.tif` (+ `.zip`, `.json`) | round-2 discovery-lane candidate (PR #7): 25,000 dots, `multi` arm, emission >200 m off catalogue | **NEGATIVE** — holdout 0.01242 [0.00787, 0.01718] vs chance 0.03499 (paired −0.02257, CI strictly below 0); gate literal DUPLICATE/STOP (density-degenerate trigger, IR-56-023; rank agreement passes at max ρ 0.043); research only — **do not submit** |
| `gems56-corr-crestgt2px-20261009T051209Z-78fc86ad-nan.tif` | corrections-lane run A (PR #5/#6, strongest crest >2 px) | **NEGATIVE** — format-valid, but the literal containment gate failed; no slot |
| `h56-corr-snap200cm-20261009.tif` | corrections-lane PRIMARY (2 px gate, PR #4) | **NEGATIVE** — 1 dot; research artefact; not cleared for a slot |
| `h56-corr-snap100cm-20261009.tif` | corrections-lane sensitivity (1 px gate, PR #4) | **NEGATIVE** — 14 dots; research artefact; not cleared for a slot |

| file | bytes | content | status | receipt |
|---|---|---|---|---|
| `checks-h56-magpack-37k-20261009.json` | 2,018 | validator receipt, this run | machine-readable proof of the row above, not a submission | - |
| `checks-h56-quota-37k-20261009.json` | 2,338 | validator receipt, this run | machine-readable proof of the row above, not a submission | - |
| `gems56-corr-twinfam9-20261009T190155Z-0279ca86-nan.tif` | 341,067 | PR #14 twin-family research raster; 2,139 dots; SHA-256 `a614a594e179fa2af24a3d9c311bbab45f3c39ca868023da23b43ece16a32b75` | **DUPLICATE / STOP — archive only.** Existing receipt has 12 literal >0.70 directed-proximity flags; no new screen was run. | `evidence/corrections/run_card_round3.json`; `evidence/corrections/registry_check_round3_post_review.json` |
| `gems56-corr-twinfam9-20261009T190155Z-0279ca86.zip` | 111,040 | exactly one GeoTIFF inside | archive copy of the stopped PR #14 research raster; do not submit | `evidence/corrections/run_card_round3.json` |
| `gems56-corr-crestgt2px-20261009T051209Z-78fc86ad-nan.tif` | 351,093 | diagnostic twin that carries NaN in the grid | **NOT safe to submit** - a NaN inside the footprint is exactly what makes the portal answer 'Predicted values must be in range [0, 1]'; kept here as evidence of the failure mode (IR-56-002), never as a candidate | - |
| `h56-corr-snap100cm-20261009.json` | 6,551 | validator receipt, this run | machine-readable proof of the row above, not a submission | - |
| `h56-corr-snap100cm-20261009.tif` | 55,844 | 14 dots at value 1.0 - round 1 of this lane (corrections experiment), not this page's method | **safe to download for inspection, do not submit** - round 1's own run card recorded it as a negative result (no corridor passed the offset-consistency gate), and a file this sparse cannot reach the filed score under the metric at all (PR #7's IR-56-018 derives that ceiling) | `docs/downloads/h56-corr-snap100cm-20261009.json`, `evidence/run_card.json` |
| `h56-corr-snap100cm-20261009.zip` | 1,776 | exactly one GeoTIFF inside | the same bytes as the .tif, zipped because the portal accepts either form | - |
| `h56-corr-snap200cm-20261009.json` | 3,608 | validator receipt, this run | machine-readable proof of the row above, not a submission | - |
| `h56-corr-snap200cm-20261009.tif` | 55,772 | 1 dot at value 1.0 - round 1 of this lane (corrections experiment), not this page's method | **safe to download for inspection, do not submit** - round 1's own run card recorded it as a negative result (no corridor passed the offset-consistency gate), and a file this sparse cannot reach the filed score under the metric at all (PR #7's IR-56-018 derives that ceiling) | `docs/downloads/h56-corr-snap200cm-20261009.json`, `evidence/run_card.json` |
| `h56-corr-snap200cm-20261009.zip` | 1,499 | exactly one GeoTIFF inside | the same bytes as the .tif, zipped because the portal accepts either form | - |
| `h56-disc-multi-b25000-20261009-20261009T165646Z.json` | 2,441 | validator receipt, published by the parallel discovery run (PR #7) | machine-readable proof of the row above, not a submission | - |
| `h56-disc-multi-b25000-20261009-20261009T165646Z.tif` | 68,005 | 25,000 dots - archived discovery output from PR #7, outside the active corrections run | **Archive only — NOT SAFE TO SUBMIT.** The old permissive receipt says `ok=True`, but strict replay finds 7,111,787 finite cells outside the sample mask and `nodata=None` vs template NaN; its holdout and literal registry gate are also negative. | `docs/review/2026-10-09.md`; `docs/downloads/h56-disc-multi-b25000-20261009-20261009T165646Z.json` |
| `h56-disc-multi-b25000-20261009-20261009T165646Z.zip` | 17,070 | exactly one GeoTIFF inside | the same bytes as the .tif, zipped because the portal accepts either form | - |
| `h56-magpack-37k-20261009.tif` | 154,019 | 37,654 dots at value 1.0 | **Archive only — DUPLICATE / STOP; do not submit.** The 868-row directed screen flags 56 priors above 0.70; its 31 unreadable rows remain a coverage limitation. The holdout is also behind the group's filed surface. | `evidence/registry_screen_h56b.json`; `evidence/raster_h56-magpack-37k-20261009.json` |
| `h56-magpack-37k-20261009.zip` | 154,173 | exactly one GeoTIFF inside | archive copy of the DUPLICATE / STOP TIFF above; technical inspection only, do not submit | `evidence/registry_screen_h56b.json`; `evidence/raster_h56-magpack-37k-20261009.json` |
| `h56-quota-37k-20261009.tif` | 138,144 | 30,800 dots at value 1.0 | **Archive only — DUPLICATE / STOP; do not submit.** The 868-row directed screen flags 54 priors above 0.70; its 31 unreadable rows remain a coverage limitation. The holdout is also behind the group's filed surface. | `evidence/registry_screen_h56b.json`; `evidence/raster_h56-quota-37k-20261009.json` |
| `h56-quota-37k-20261009.zip` | 138,294 | exactly one GeoTIFF inside | archive copy of the DUPLICATE / STOP TIFF above; technical inspection only, do not submit | `evidence/registry_screen_h56b.json`; `evidence/raster_h56-quota-37k-20261009.json` |

`*.tif` and `*.zip` are git-ignored repository-wide; the round-2 rasters, their zips and their receipts are force-added deliberately, because they are the deliverables this site exists to publish (see `.gitignore`).
