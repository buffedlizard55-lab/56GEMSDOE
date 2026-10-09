#!/usr/bin/env python3
"""Write data_manifest.json: every input this repository reads, with hash, source and access status.

A manifest is an integrity statement about the bytes on this machine plus a pointer a reviewer can open. It
does not authenticate organizer provenance by itself: for a login-gated file the strongest honest claim is
"these bytes hash to X, and here is the page where a logged-in human can confirm X".

Reproduce: python scripts/make_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXTERNAL = {
    "/home/user/_lidar/x42y427_3m.tif": dict(
        role="3 m lidar DEM pilot tile for the sub-cell crest calibration",
        source="USGS 3DEP 1 m lidar, resampled to 3 m by sibling repo GEMSDOE48",
        link="https://github.com/buffedlizard55-lab/GEMSDOE48/actions/runs/37565284104",
        access="public (GitHub release artefact of a sibling repo)"),
    "/home/user/_lidar/x40y425_3m.tif": dict(
        role="second 3 m tile, for a sign check across separate areas",
        source="USGS 3DEP 1 m lidar via GEMSDOE48", link="https://github.com/buffedlizard55-lab/GEMSDOE48",
        access="public"),
    "/home/user/_lidar/h52_scarp3m_100m.tif": dict(
        role="7-band 100 m scarp stack derived from the same lidar (used for coverage only)",
        source="GEMSDOE48 merged product, int16 decimetres, nodata -32768",
        link="https://github.com/buffedlizard55-lab/GEMSDOE48/blob/main/data/external/h52_scarp3m_100m.json",
        access="public"),
}


def sha(p: Path, n: int = 1 << 22):
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(n), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    pins = json.loads((ROOT / "registry" / "input_pins.json").read_text())
    grid = json.loads((ROOT / "evidence" / "grid.json").read_text())
    out = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        statement=("every number published by this repository derives from the files listed here; nothing was "
                   "downloaded or generated between the pin and the measurement that is not in this list"),
        official_inputs={}, external_inputs={}, derived_inputs={})

    for name, meta in (pins.get("files") or {}).items():
        p = (ROOT / meta["path"]) if meta.get("path") else None
        here = bool(p and p.exists())
        out["official_inputs"][name] = dict(
            path=str(p.relative_to(ROOT)) if here else meta.get("path"), bytes=meta["bytes"],
            sha256=meta.get("sha256"), sha256_now=sha(p) if here else None,
            matches_pin=((sha(p) == meta["sha256"]) if meta.get("sha256") else None) if here else None,
            present_in_repo=here,
            note=("no pin recorded for this input in registry/input_pins.json (it is not part of the data-tab "
                  "bridge); the hash measured here is published so a later run can pin it"
                  if here and not meta.get("sha256") else
                  (None if here else "not stored in the repository (too large for git); cached in the sandbox "
                                     "workspace at the path above -- a null matches_pin means absent here, "
                                     "not a mismatch")),
            role=meta.get("role"), source=meta.get("source", "DrivenData competition 306 data tab"),
            link="https://drivendata.org/competitions/306/competition-doe-gems/data/",
            access="login required (HTTP 302 observed); bytes obtained through the pinned sibling bridge")

    for path, meta in EXTERNAL.items():
        p = Path(path)
        out["external_inputs"][path] = dict(
            **meta, exists=p.exists(), bytes=p.stat().st_size if p.exists() else None,
            sha256=sha(p) if p.exists() else None)

    for name, meta in (grid.get("inputs") or {}).items():
        p = ROOT / meta["path"]
        out["derived_inputs"][name] = dict(path=meta["path"], bytes=meta["bytes"], sha256=meta["sha256"],
                                           sha256_now=sha(p) if p.exists() else None,
                                           role=meta.get("role"), provenance=meta.get("provenance"))

    n_ok = sum(1 for v in out["official_inputs"].values() if v["matches_pin"])
    out["summary"] = dict(official_files=len(out["official_inputs"]), official_hash_verified=n_ok,
                          external_files=len(out["external_inputs"]),
                          verified_here=sum(1 for v in out["official_inputs"].values() if v["matches_pin"] is True),
                          unpinned_here=sum(1 for v in out["official_inputs"].values() if v["matches_pin"] is None and v["present_in_repo"]),
                          missing_here=sum(1 for v in out["official_inputs"].values() if not v["present_in_repo"]),
                          all_pinned_files_verified=all(v["matches_pin"] is not False for v in out["official_inputs"].values()))
    (ROOT / "data_manifest.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["summary"], indent=1))
    for k, v in out["official_inputs"].items():
        print(f"  {k}: pin_match={v['matches_pin']}")


if __name__ == "__main__":
    main()
