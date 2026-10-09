# Published evidence copies

Byte copies of the receipts in `evidence/` at the repo root, with underscores swapped for hyphens so the Pages URL is the exact string the site links to. `evidence/` at the repo root stays canonical; this directory exists so every number on the site can be checked without cloning the repository. Regenerate with `python scripts/build_round2.py`.

| file | what it is |
|---|---|
| `hidden-size-inversion.json` | E0: what the two published scores imply about hidden |G|, credit per dot, the marginal-dot rule and the perfect-placement ceiling - arithmetic on user-reported scores, never a projection |
| `field-holdout-v1.json` | E1b: every official channel scored alone on the shared blocked holdout, both instruments, AUC canaries, budget ladder |
| `emission-holdout-h56-mpp-r1-20261009.json` | E3: emitter arms (top-K, exact packing, calibrated greedy) at matched budget, with the two filed sibling rasters scored as-is on the same folds |
| `quota-union-v1.json` | E4: combination rules - equal-rank mean, quota union, credit-weighted union, packing - with paired bootstrap CIs |
| `registry-screen-h56b.json` | uniqueness screen over the mirrored sibling corpus: 868 rasters, <=3 px dot proximity in both directions |
| `raster-h56-magpack-37k-20261009.json` | primary raster: dot count, distance-to-catalogue statistics, format-gate output, sha256 |
| `raster-h56-quota-37k-20261009.json` | secondary raster: the same fields |
| `run-card-round2.json` | the round-2 run card (identical to docs/research/run-card-round2.json) |
| `run-card.json` | the round-1 lane-assignment run card |
