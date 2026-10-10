#!/usr/bin/env python3
"""E2 -- build the discovery-lane submission GeoTIFF, validate it, and file the receipt.

The emission rule is *identical* to the one the holdout validated (E1): top-k of the chosen
arm's ranked field inside ``footprint & ~dilate(catalogue, 2 px)``, value 1.0.  The chosen arm
and budget are read from ``evidence/holdout_discovery_v1.json`` (``pick_rule.candidate``) so the
shipped file cannot silently diverge from the validated configuration.

Hard guarantees (each enforced by shared template code, not by this script):

* values finite and in [0, 1] everywhere           -- gems56.grid.write_geotiff + gates.format_report
* single band, float32, EPSG:32611, shape/transform == sample_submission.tif  -- gates.format_report
* no mass on any catalogue pixel and none within 2 px of one (the 0.2778 mechanism + our <=2 px
  correction result)                               -- the allowed-mask construction below
* submission name and note each 1..140 chars       -- gems56.submission_writer
* receipt JSON + single-TIFF zip written next to the file, sha256 inside

If E1's verdict was NEGATIVE the file is still built (the brief demands a unique, obviously-labelled
downloadable TIF) but the note and the receipt say NEGATIVE, exactly like the corrections lane's
precedent.  This script never marks a file as cleared for a slot.

Receipt: docs/downloads/<name>.json + evidence/build_discovery_v1.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems56 import gates, holdout as H, lane_inputs as L, submission_writer as SW  # noqa: E402
from run_discovery_holdout import build_fields, read_extra_bands  # noqa: E402  (single recipe, no fork)


def main() -> None:
    t0 = time.time()
    hold = json.loads((ROOT / "evidence" / "holdout_discovery_v1.json").read_text())
    candidate = hold["pick_rule"]["candidate"]          # e.g. "multi@25000"
    arm, budget = candidate.rsplit("@", 1)
    budget = int(budget)
    passed = bool(hold["verdict_pass"])

    fields, cat, fp, meta = L.load(sample=True)
    extra = read_extra_bands(L.path("features"))
    ranked, _ = build_fields(fields, extra, fp)
    if arm not in ranked:
        raise SystemExit(f"pick {candidate!r} names an unknown arm {arm!r}")

    # ---- the one emission rule, on the full grid -------------------------------------------
    known = ndimage.binary_dilation(cat, structure=gates._disk(2.0))
    allowed = fp & ~known
    p = H.emit_topk(ranked[arm], allowed, budget)
    dots = int((p > 0).sum())
    on_cat = int((p > 0).sum() - (p > 0)[allowed].sum())
    if on_cat:
        raise SystemExit(f"emission placed {on_cat} dots on/adjacent to known catalogue pixels")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    slug = arm.replace("_", "")
    name = f"h56-disc-{slug}-b{budget}-20261009-{ts}"
    if passed:
        note = (f"h56 discovery {arm} k={budget}: step-lineament dots >200 m off catalogue; "
                f"HOLDOUT-VALIDATED vs chance; own model")
        verdict = "validated-local"
    else:
        note = (f"h56 discovery {arm} k={budget}: step-lineament dots >200 m off catalogue; "
                f"NEGATIVE holdout, research only, do not slot")
        verdict = "negative"
    if len(note) > 140:
        raise SystemExit(f"note too long: {len(note)}")

    out_dir = ROOT / "docs" / "downloads"
    tif = out_dir / f"{name}.tif"
    receipt = SW.write_submission(
        tif, p, ROOT / "data" / "grid" / "sample_submission.tif", fp,
        note=note, name=name,
        metadata=dict(
            lane="discovery (round 2, corrections-lane repo)",
            evidence_class="MODEL output; local validation only; no ORGANIZER-CONFIRMED score",
            holdout_evidence="evidence/holdout_discovery_v1.json",
            holdout_candidate=candidate,
            holdout_dti=hold["pooled"]["scores"][candidate]["dti"],
            holdout_ci95=hold["pooled"]["scores"][candidate]["ci95"],
            verdict_pass=passed,
            verdict=verdict,
            emission=f"top-{budget} of rank01 field {arm} in footprint & ~dilate(catalogue,2px)",
            dots=dots,
            budget_used="E1 holdout + E2 build (2 of 3)",
            cleared_for_weekly_slot=False,
        ),
    )

    summary = dict(
        name=name, note=note, note_chars=len(note), verdict=verdict,
        arm=arm, budget=budget, dots=dots,
        holdout_dti=hold["pooled"]["scores"][candidate]["dti"],
        holdout_ci95=hold["pooled"]["scores"][candidate]["ci95"],
        chance_dti=hold["pooled"]["scores"].get(f"random@{budget}", {}).get("dti"),
        receipt=receipt,
        elapsed_s=round(time.time() - t0, 1),
    )
    (ROOT / "evidence" / "build_discovery_v1.json").write_text(
        json.dumps(summary, indent=1, default=float) + "\n")
    print(json.dumps(summary, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
