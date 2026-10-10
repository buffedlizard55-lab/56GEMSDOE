#!/usr/bin/env python3
"""H57 uniqueness gate: shared template gate on the curated worst-overlap priors.

Two stages, both published:

* ``scripts/screen_registry.py`` already ran the cheap, exact directed <=3 px dot-proximity
  statistic over the FULL harvested corpus (944 rasters, ``evidence/registry_screen_v1.json``)
  and symlinked the 40 largest reciprocal overlaps into ``/home/user/_reg_top_v1``.
* This script runs the shared template gate ``gems56.gates.lane_report`` on that curated set,
  which adds the exact tie-aware rank correlation and the measured universal-coverage-probe
  policy verdict.

Both verdicts are reported verbatim: ``literal`` (the brief's rule applied to every prior,
including rasters that dot most of the grid) and ``policy`` (the same rule restricted to priors
that actually localise something, i.e. whose 3 px halo covers < 95 % of the footprint).

Run: .venv/bin/python scripts/h57_uniqueness.py --candidate docs/downloads/<file>.tif
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import gates  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--registry", default="/home/user/_reg_top_v1")
    ap.add_argument("--out", default="evidence/h57_uniqueness.json")
    args = ap.parse_args()

    sample = ROOT / "data" / "grid" / "sample_submission.tif"
    with rasterio.open(sample) as ds:
        eligible = np.isfinite(ds.read(1))
    with rasterio.open(args.candidate) as ds:
        cand = np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0)

    priors = sorted(Path(args.registry).rglob("*.tif"))
    print(f"candidate dots {int((cand > 0).sum()):,}   priors {len(priors)}")
    rep = gates.lane_report(cand, eligible, priors, sample=str(sample), phase="dots",
                            log=print)
    Path(args.out).write_text(json.dumps(rep, indent=1, default=float) + "\n")
    keys = [k for k in ("literal", "policy", "max_spearman", "max_near_3px_fraction",
                        "universal_coverage_probes", "priors_checked") if k in rep]
    print(json.dumps({k: (rep[k] if not isinstance(rep[k], list) else len(rep[k]))
                      for k in keys}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
