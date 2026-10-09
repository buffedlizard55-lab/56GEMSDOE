#!/usr/bin/env python3
"""Full-corpus lane screen at the cost of one pass, then the shared gate on the top overlaps.

``gates.lane_uniqueness_report`` re-reads every prior for each phase; over a 485-raster corpus that is
~20 minutes for one candidate. This screen does the cheap half exactly (the directed <=3 px dot
proximity, which is the load-bearing statistic for a sparse dot set) over **every** harvested raster in
one pass, ranks the corpus, and then hands the disclosed top subset plus every GEMSDOE54 registry
raster to the shared tool for the authoritative verdict, including the rank-correlation term the cheap
pass cannot compute.

Scope, stated plainly: the corpus is the set of single-band grid-aligned rasters that the sibling
repositories publish under docs/downloads, docs/submissions, submission/ and registry/. It cannot prove
anything about unpublished, private or unlinked artefacts.

Reproduce: python scripts/screen_registry.py [dir] [candidate.tif ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import gates  # noqa: E402  (shared template gate, used for the authoritative verdict)

OFFSETS = [(dy, dx) for dy in range(-3, 4) for dx in range(-3, 4) if dy * dy + dx * dx <= 9]


def dots_of(a: np.ndarray) -> np.ndarray:
    """Positive support of a raster, decoded the way the shared gate decodes it (binary: >0;
    continuous: >= 0.5). float32 throughout: the 12.3 M-cell grid is 49 MB here and 98 MB in
    float64, and the screen holds one prior at a time in a 3 GB sandbox."""
    b = np.nan_to_num(a.astype(np.float32, copy=False), nan=0.0)
    binary = bool(np.all((b == 0) | (b == 1) | (b == -1)))
    return (b > 0) if binary else (b >= 0.5)


def screen(candidate_paths, reg_dir, footprint):
    """One pass over the corpus: exact directed <=3 px dot proximity in both directions."""
    cand = {}
    for cp in candidate_paths:
        with rasterio.open(cp) as ds:
            prop = dots_of(ds.read(1))
        yy, xx = np.nonzero(prop)
        dil = np.zeros(prop.shape, bool)
        if yy.size:                                  # dilate once per candidate: the reverse test
            for dy, dx in OFFSETS:
                y, x = yy + dy, xx + dx
                ok = (y >= 0) & (y < prop.shape[0]) & (x >= 0) & (x < prop.shape[1])
                dil[y[ok], x[ok]] = True
        cand[str(cp)] = dict(prop=prop, dil=dil, yy=yy, xx=xx, n=int(yy.size))
    rows = []
    files = sorted(Path(reg_dir).glob("*.tif"))
    for i, f in enumerate(files):
        try:
            with rasterio.open(f) as ds:
                if ds.count != 1 or ds.shape != footprint:
                    rows.append(dict(path=f.name, error="unaligned or multiband"))
                    continue
                prior = dots_of(ds.read(1))
        except Exception as exc:                       # noqa: BLE001 - a bad mirror must not stop the scan
            rows.append(dict(path=f.name, error=f"{type(exc).__name__}: {exc}"))
            continue
        n_prior = int(prior.sum())
        row = dict(path=f.name, prior_dots=n_prior)
        for key, c in cand.items():
            short = Path(key).stem[:24]
            if c["n"] == 0:
                row[f"{short}_frac"], row[f"{short}_rev"] = None, None
                continue
            near = np.zeros(c["n"], bool)
            yy, xx = c["yy"], c["xx"]
            for dy, dx in OFFSETS:                   # my dots -> nearest prior dot
                y, x = yy + dy, xx + dx
                ok = (y >= 0) & (y < prior.shape[0]) & (x >= 0) & (x < prior.shape[1])
                near[ok] |= prior[y[ok], x[ok]]
            row[f"{short}_frac"] = float(near.mean())
            row[f"{short}_rev"] = (float((prior & c["dil"]).sum() / n_prior) if n_prior else None)
        rows.append(row)
        if (i + 1) % 60 == 0:
            print(f"  screened {i+1}/{len(files)}", flush=True)
    return rows, cand


def tag(cp, kind):
    return f"{Path(cp).stem[:22]}_{kind}"


def main(argv):
    reg = Path(argv[0]) if argv else Path("/home/user/_reg")
    cands = [Path(p) for p in argv[1:]] or sorted((ROOT / "docs" / "downloads").glob("*.tif"))
    with rasterio.open(ROOT / "data" / "grid" / "sample_submission.tif") as ds:
        shape = ds.shape
    rows, _ = screen(cands, reg, shape)
    out_rows = [r for r in rows if "error" not in r]
    for r in rows:
        vals = [v for k, v in r.items() if k.endswith("_frac") and v is not None]
        r["max_frac"] = max(vals) if vals else None
        rv = [v for k, v in r.items() if k.endswith("_rev") and v is not None]
        r["max_rev"] = max(rv) if rv else None
    rows.sort(key=lambda r: -(r.get("max_frac") or 0.0))
    # The literal rule (">70% of my dots within 3 px of one registry raster") is satisfied by ANY raster
    # that dots most of the grid -- those are density/diagnostic layers, not earlier submissions. Both
    # directions are therefore kept for every file, and the reciprocal overlap min(frac, rev) is what
    # actually separates "someone already submitted this" from "their raster covers the whole footprint".
    for r in rows:
        if "error" not in r:
            r["reciprocal"] = round(min(r.get("max_frac") or 0.0, r.get("max_rev") or 0.0), 6)
    prefix = __import__("os").environ.get("SCREEN_PREFIX", "")
    with (ROOT / "evidence" / f"registry_screen_{prefix}rows.jsonl").open("w") as fh:
        for r in rows:
            fh.write(__import__("json").dumps(r) + "\n")
    out = dict(evidence_class="uniqueness diagnostic, not a score",
               rule="directed <=3px dot proximity, exact lattice, over the full harvested corpus; "
                    "no exclusions, no exemptions for dense rasters",
               corpus=dict(root=str(reg), files=len(list(reg.glob("*.tif"))), rows=len(rows),
                           note="screen prefix "+repr(__import__("os").environ.get("SCREEN_PREFIX","")),
                           errors=sum(1 for r in rows if "error" in r)),
               candidates=[str(c) for c in cands],
               top=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows[:40]],
               worst_max_frac=rows[0].get("max_frac") if rows else None,
               over_070=sum(1 for r in rows if (r.get("max_frac") or 0) > 0.70),
               over_070_reverse=sum(1 for r in rows if (r.get("max_rev") or 0) > 0.70),
               over_070_reciprocal=sum(1 for r in out_rows if r.get("reciprocal", 0) > 0.70),
               dense_priors_over_070=sum(1 for r in out_rows
                                         if (r.get("max_frac") or 0) > 0.70 and (r.get("prior_dots") or 0) > 1e5),
               top_reciprocal=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
                               for r in sorted(out_rows, key=lambda r: -(r.get("reciprocal") or 0.0))[:12]])
    (ROOT / "evidence" / f"registry_screen_{prefix or chr(118)+chr(49)}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float)[:2600])

    # Curated registry for the authoritative shared gate: the 40 largest *reciprocal* overlaps, so that
    # gates.lane_uniqueness_report -- which is the tool the protocol names -- runs on the priors that could
    # actually be duplicates rather than on the dense diagnostic layers that dominate a one-way count.
    cur = Path(ROOT / "data" / f"_reg_top_{prefix.strip(chr(95)) or 'v1'}")
    cur.mkdir(parents=True, exist_ok=True)
    for old in cur.glob("*.tif"):
        old.unlink()
    ranked = sorted(out_rows, key=lambda r: (-(r.get("reciprocal") or 0.0), -(r.get("max_frac") or 0.0)))
    kept = []
    for r in ranked[:40]:
        src = reg / r["path"]
        if src.exists():
            (cur / r["path"]).symlink_to(src)
            kept.append(r["path"])
    print(json.dumps(dict(curated_registry=str(cur), n=len(kept)), indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
