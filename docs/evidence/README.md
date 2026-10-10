# Published evidence copies

Byte copies of the receipts in `evidence/` at the repo root, with underscores swapped for hyphens so the Pages URL is the exact string the site links to. `evidence/` at the repo root stays canonical; this directory exists so every number on the site can be checked without cloning the repository. Regenerate with `python scripts/build_round2.py`.

The list is generated from the directory, so a receipt that exists is a receipt that is described - nothing published here is left unexplained. Rows without a description of their own are receipts belonging to the parallel run (PR #7) or to round 1; they are copied so the group can audit both runs from one place, and they are labelled as that run's claim rather than ours.

| file | what it is | 35 files |
|---|---|
| `build-corrections-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: built artefacts with local format and lane receipts; no organizer receipt exists |
| `build-discovery-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: h56 discovery multi k=25000: step-lineament dots &gt;200 m off catalogue; NEGATIVE holdout, research only, do not slot |
| `calibration-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: MEASURED; descriptive statistics and estimator calibration, not a score |
| `checks-h56-magpack-37k-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `checks-h56-quota-37k-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `cluster-gate-control.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: MEASURED permutation control on the same candidate set; not a score |
| `emission-holdout-h56-mpp-r1-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `estimator-validation.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: MEASURED instrument characterisation on synthetic scarps; not a score |
| `field-holdout-v1.json` | E1b: every official channel scored alone on the shared blocked holdout, both instruments, AUC canaries, budget ladder |
| `grid.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `hidden-size-inversion.json` | E0: what the two published scores imply about hidden |G|, credit per dot, the marginal-dot rule and the perfect-placement ceiling - arithmetic on user-reported scores, never a projection |
| `holdout-corrections-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: HOLDOUT-DTI (catalogue recovery, hide-and-recover; NOT new-fault discovery) |
| `holdout-discovery-v0-prefx.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: HOLDOUT-DTI (catalogue recovery, hide-and-recover; NOT new-fault discovery) |
| `holdout-discovery-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: HOLDOUT-DTI (catalogue recovery, hide-and-recover; NOT new-fault discovery) |
| `inventory-official-data.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: All values measured from the downloaded bytes. Not transcribed from docs. |
| `inventory.json` | published by another run of this lane: a list of 48 records (its own tool wrote it, not this page; read it as that run's claim) |
| `irregularities.json` | the shared irregularity registry for this repository: round 1, the parallel discovery run (PR #7) and this run, merged with ids reconciled rather than overwritten - rendered at docs/irregularities.html |
| `lane-gate-discovery-v2.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: uniqueness/lane diagnostic, not a score |
| `lane-uniqueness-h56-corr-snap100cm-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `lane-uniqueness-h56-corr-snap200cm-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `lane-uniqueness2-h56-magpack-37k-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `lane-uniqueness2-h56-quota-37k-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `lane-uniqueness2-summary.json` | the shared lane gate's own summary for both round-2 rasters, with the resolved prior count and the disclosed-subset rule |
| `lidar-calibration-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: MEASURED on 3 m USGS 1 m-LiDAR tiles; calibration and descriptive statistics, not a score |
| `offsets-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: MEASURED on this machine; descriptive statistic, not a score |
| `quota-union-v1.json` | E4: combination rules - equal-rank mean, quota union, credit-weighted union, packing - with paired bootstrap CIs |
| `raster-h56-magpack-37k-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `raster-h56-quota-37k-20261009.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `registry-corpus-mirror.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: no header recorded in the file |
| `registry-screen-h56b.json` | uniqueness screen over the mirrored sibling corpus: 868 rasters, <=3 px dot proximity in both directions |
| `registry-screen-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: uniqueness diagnostic, not a score |
| `registry-screen-v2.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: uniqueness diagnostic, not a score |
| `run-card-discovery-v1.json` | published by another run of this lane (its own page is under docs/); not re-derived here, so read it as that run's claim. Its file says: discovery (round 2 of the corrections-lane repository) |
| `run-card-round2.json` | the round-2 run card (identical to docs/research/run-card-round2.json) |
| `run-card.json` | the round-1 lane-assignment run card |
