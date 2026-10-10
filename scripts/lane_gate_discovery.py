#!/usr/bin/env python3
"""E3 (gate half) -- the shared lane-uniqueness tools on the round-2 discovery candidate.

Protocol text being executed (verbatim from the standing brief):

    "If your raster's rank-correlation with any registry raster exceeds [0.90], or more than
     [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into
     another lane: log it as a duplicate and stop. Check this on the surface before placement
     AND on the final dots."

Implementation, all through the vendored template gate (no fork):

* ``gates.lane_report`` is called twice -- phase="surface" (the ranked field the dots were
  placed from, normalised to [0,1]) and phase="dots" (the shipped raster).  It returns the
  literal verdict (the brief's rule applied to EVERY aligned prior, probes included) and the
  H61 coverage-adjusted policy verdict side by side; neither replaces the other.
* Priors = every single-band raster on the reference grid under the harvested sibling mirror
  (``/home/user/_reg``, produced by scripts/mirror_registry.sh).  Off-grid or multiband files
  cannot be duplicates of a grid-locked submission and are counted and listed, not silently
  dropped.  The candidate's own file is not in the mirror (the mirror predates E2 by design).
* The cheap full-corpus proximity pass (both directions, exact <=3 px) comes first from
  ``scripts/screen_registry.py --tag v2`` and is re-published here for the record.

Receipt: evidence/lane_gate_discovery_v2.json
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
sys.path.insert(0, str(ROOT / "scripts"))
from gems56 import gates, lane_inputs as L  # noqa: E402
from run_discovery_holdout import build_fields, read_extra_bands  # noqa: E402

REG = Path("/home/user/_reg")


def aligned_priors(sample_path: Path) -> tuple[list[Path], list[dict]]:
    """Every single-band raster on the reference grid; the rest is reported, not dropped silently."""
    with rasterio.open(sample_path) as ref:
        meta = (ref.shape, ref.crs, ref.transform)
    good, skipped = [], []
    files = sorted(p for p in REG.rglob("*.tif"))
    for i, p in enumerate(files):
        try:
            with rasterio.open(p) as ds:
                if ds.count != 1 or (ds.shape, ds.crs, ds.transform) != meta:
                    skipped.append(dict(path=str(p.relative_to(REG)),
                                        why=f"{ds.count} band(s) or off-grid {ds.shape}"))
                    continue
        except Exception as exc:  # noqa: BLE001
            skipped.append(dict(path=str(p.relative_to(REG)), why=f"{type(exc).__name__}"))
            continue
        good.append(p)
        if (i + 1) % 200 == 0:
            print(f"  header scan {i+1}/{len(files)}", flush=True)
    return good, skipped


def main() -> None:
    t0 = time.time()
    build = json.loads((ROOT / "evidence" / "build_discovery_v1.json").read_text())
    hold = json.loads((ROOT / "evidence" / "holdout_discovery_v1.json").read_text())
    arm = build["arm"]
    cand_path = ROOT / "docs" / "downloads" / Path(build["receipt"]["file"]).name
    sample = ROOT / "data" / "grid" / "sample_submission.tif"

    priors, skipped = aligned_priors(sample)
    print(f"{len(priors)} aligned priors, {len(skipped)} skipped (off-grid/multiband/unreadable)",
          flush=True)
    screen = None
    sp = ROOT / "evidence" / "registry_screen_v2.json"
    if sp.exists():
        screen = json.loads(sp.read_text())

    # ---- phase 1: the surface (the ranked field the dots came from) ------------------------
    fields, cat, fp, _ = L.load(sample=True)
    extra = read_extra_bands(L.path("features"))
    ranked, _ = build_fields(fields, extra, fp)
    surface = np.nan_to_num(ranked[arm], nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)
    surf_rep = gates.lane_report(surface, fp, priors, sample=sample, phase="surface", log=print)

    # ---- phase 2: the final dots ------------------------------------------------------------
    with rasterio.open(cand_path) as ds:
        cand = ds.read(1)
    dots_rep = gates.lane_report(cand, fp, priors, sample=sample, phase="dots", log=print)

    out = dict(
        evidence_class="uniqueness/lane diagnostic, not a score",
        protocol_rule="rho > 0.90 with any registry raster, or >70% of dots within 3 px of ONE "
                      "registry raster's dots => logged duplicate and stop; checked on the surface "
                      "and on the final dots",
        candidate=str(cand_path.relative_to(ROOT)),
        candidate_sha256=gates.sha256(cand_path),
        arm=arm,
        corpus=dict(root=str(REG), scanned_files=len(list(REG.rglob('*.tif'))),
                    aligned_priors=len(priors), skipped=len(skipped), skipped_detail=skipped[:50],
                    note="includes this repository's own earlier rasters (mirror predates the "
                         "candidate by construction); off-grid/multiband files cannot be "
                         "duplicates of a grid-locked submission and are listed above"),
        screen=screen,
        surface=surf_rep,
        dots=dots_rep,
        verdict_literal=dots_rep["literal"]["verdict"],
        verdict_policy=dots_rep["policy"]["verdict"],
        duplicate=bool(dots_rep["duplicate"] or surf_rep["duplicate"]),
        ok=bool(dots_rep["ok"] and surf_rep["ok"]),
        verdict_pass_holdout=bool(hold.get("verdict_pass")),
        elapsed_s=round(time.time() - t0, 1),
    )
    path = ROOT / "evidence" / "lane_gate_discovery_v2.json"
    path.write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: out[k] for k in ("verdict_literal", "verdict_policy", "duplicate",
                                          "ok", "elapsed_s")}, indent=1))
    print(f"surface: {surf_rep['literal']['verdict']} / policy {surf_rep['policy']['verdict']}")
    print(f"dots:    {dots_rep['literal']['verdict']} / policy {dots_rep['policy']['verdict']}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
