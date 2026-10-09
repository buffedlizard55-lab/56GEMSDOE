# tests/ — what runs here and why

This repository vendors a **subset** of the GEMSDOE template tools:

```
src/metrics.py            official distance-weighted Tversky metric (+ blocked scoring,
                          block decomposition, spatial-block bootstrap)
src/submission_io.py      fail-loud submission writer, template conformance, clean profile
src/dataset.py            dataset name discovery / placement helpers
src/postprocess.py        post-processing version shims used by the metric tests
scripts/validate_submission.py    the submission validator
scripts/sanitize_submission.py    the validator's suggested fix tool
scripts/preflight_data.py        pre-flight data check (the template's
                                 `prepare_data.py`, renamed to coexist with run B's
                                 pin verifier at `scripts/prepare_data.py`)
scripts/assemble_data_bridge.py  reassemble the official rasters from bridge parts
```

The template repository (`buffedlizard55-lab/GEMSDOE`) carries 48 test files covering
its **full** stack (training, models, losses, holdout evaluator, emission decision,
ensembles, site generators, workflows). Those tests import modules this lane repo does
not vendor (`src.train`, `src.models`, `src.losses`, `src.submission_optim`, workflow
scripts, Node site tooling), so they are **not** kept here — keeping them would leave a
red suite that tests code that is not in this repository. The two template test files
that exercise only the vendored tools and pass unmodified are kept:

* `test_metric_parity.py` — the official metric against the organizer's worked example
  (0.60) and published formula identities.
* `test_block_decomposition.py` — the blocked-scoring identity
  (sum over blocks == global) that the holdout's pooled DTI and bootstrap rely on.

Lane-specific coverage lives in:

* `test_corrections_lane.py` — crest finding, record consistency, emission rules,
  off-catalogue restriction, end-to-end emission shape.
* `test_vendored_tools.py` — metric worked example, submission writer round-trip,
  template conformance of the shipped GeoTIFF, and the validator on the shipped file.

Run: `python -m pytest tests -q`
