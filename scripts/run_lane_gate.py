#!/usr/bin/env python3
"""Run the shared lane-uniqueness gate on this round's rasters against a disclosed prior set.

The protocol names two drift checks: Spearman rank correlation above 0.90 with any registry raster,
or more than 70 % of dots within 3 px of one. ``scripts/screen_registry.py`` computes the second one
cheaply and exhaustively over the whole mirror; this script runs the *shared tool* - the one every
lane calls - on the disclosed subset the screen ranks as the most duplicate-like, so that the
authoritative verdict, including the rank-correlation term the cheap pass cannot compute, is on the
record for each candidate.

Reproduce: python scripts/run_lane_gate.py data/_reg_top_h56b docs/downloads/<name>.tif ...
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import gates, lane_inputs as L  # noqa: E402


def main(reg_dir: str, candidates: list[str]) -> int:
    reg = Path(reg_dir)
    if not reg.is_absolute():
        reg = ROOT / reg_dir
    priors = sorted(str(p) for p in reg.glob("*.tif"))
    if not priors:
        raise SystemExit(f"no priors in {reg} - run scripts/screen_registry.py first")
    sample = str(ROOT / "data" / "grid" / "sample_submission.tif")
    _fields, _cat, fp, _meta = L.load()          # the same pinned loader every lane uses
    out = dict(registry=str(reg.relative_to(ROOT)), priors=len(priors),
               rule="STOP at rho > 0.90 or directed <=3 px dot proximity > 0.70; no lane retuning",
               candidates={})
    for cand in candidates:
        p = Path(cand)
        if not p.is_absolute():
            p = ROOT / cand
        t0 = time.time()
        with rasterio.open(p) as src:
            a = src.read(1).astype(np.float32)
        rep = {}
        for phase in ("surface", "dots"):
            try:
                rep[phase] = gates.lane_uniqueness_report(a, fp, priors, sample=sample, phase=phase)
            except ValueError as exc:      # constant candidate has no rank evidence by design
                rep[phase] = dict(error=str(exc), phase=phase, ok=None)
        name = p.stem
        rec = dict(file=str(p.relative_to(ROOT)), sha256=gates.sha256(p), seconds=round(time.time() - t0, 1),
                   phases=rep)
        out["candidates"][name] = rec
        (ROOT / "evidence" / f"lane_uniqueness2_{name}.json").write_text(json.dumps(rec, indent=1, default=float))
        print(name, {k: (v.get("ok") if isinstance(v, dict) else None) for k, v in rep.items()},
              {k: (v.get("max_spearman"), v.get("max_near_3px_fraction")) for k, v in rep.items()
               if isinstance(v, dict)}, flush=True)
    (ROOT / "evidence" / "lane_uniqueness2_summary.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "candidates"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2:]))
