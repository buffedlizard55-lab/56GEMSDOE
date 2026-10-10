#!/usr/bin/env python3
"""Write ``data_manifest.json`` with current input presence, hashes, and provenance limits.

The competition inputs are mirrored in public owner-maintained GitHub repositories because the
competition data tab is login-gated. Their SHA-256 pins establish byte identity with those mirrors,
not direct organizer authentication, licence terms, or permission to redistribute. The LiDAR products
are sibling-repo derivatives and are explicitly kept separate from competition inputs.

Reproduce after ``bash scripts/download_competition_data.sh`` with:
``python scripts/make_manifest.py``
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_DATA_PAGE = "https://www.drivendata.org/competitions/306/competition-doe-gems/data/"


def hash_file(path: Path, block_size: int = 1 << 22) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def main() -> None:
    pins = json.loads((ROOT / "registry" / "input_pins.json").read_text())
    bridge = json.loads((ROOT / "registry" / "bridge_sources.json").read_text())
    core = bridge["competition_bridge"]
    lidar = bridge["lidar_cache"]
    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "statement": ("SHA-256 equality confirms byte identity with the owner-maintained public mirror pins; "
                      "it does not authenticate these files as direct organizer downloads or resolve licensing/"
                      "redistribution terms. Confirm those on the login-gated competition data page."),
        "competition_data_page": OFFICIAL_DATA_PAGE,
        "competition_mirror": {
            "repository": core["repository"], "commit": core["commit"],
            "commit_url": core["commit_url"], "manifest_blob": core["manifest_blob"],
            "classification": "public owner-maintained mirror; not direct organizer authentication",
        },
        "official_inputs": {},
        "external_inputs": {},
        "derived_inputs": {},
    }

    file_key = {"catalogue": "catalogue", "sample": "sample", "features": "features"}
    for name in ("catalogue", "sample", "features"):
        meta = pins["files"][name]
        path = ROOT / meta["path"]
        exists = path.is_file()
        current_bytes, current_hash = hash_file(path) if exists else (None, None)
        expected_hash = meta.get("sha256")
        match = (current_hash == expected_hash) if exists and expected_hash else (None if not exists else None)
        mirror_spec = core["files"][file_key[name]]
        out["official_inputs"][name] = {
            "path": meta["path"], "bytes": current_bytes if exists else meta.get("bytes"),
            "bytes_now": current_bytes, "expected_bytes": meta.get("bytes"),
            "sha256": expected_hash, "sha256_now": current_hash,
            "matches_pin": match, "present_in_workspace": exists,
            "source_class": "competition input, obtained from public owner-maintained mirror",
            "source_repository": core["repository"], "source_commit": core["commit"],
            "source_blob": mirror_spec.get("blob"),
            "source_shards": mirror_spec.get("parts"),
            "role": meta.get("role"), "provenance": meta.get("provenance"),
            "data_page": OFFICIAL_DATA_PAGE,
            "access": "competition data page login-gated; mirrored bytes hash-pinned; organizer provenance not independently authenticated",
            "note": ("missing here; download with scripts/download_competition_data.sh" if not exists else
                     ("hash does not match the recorded mirror pin" if expected_hash and match is False else
                      "hash matches recorded mirror pin; this is not proof of organizer authenticity or licensing")),
        }

    out["external_inputs"]["lidar_cache"] = {}
    for name, meta in lidar["files"].items():
        path = ROOT / meta["destination"]
        exists = path.is_file()
        current_bytes, current_hash = hash_file(path) if exists else (None, None)
        match = (current_hash == meta["sha256"]) if exists else None
        out["external_inputs"]["lidar_cache"][name] = {
            "path": meta["destination"], "bytes": current_bytes if exists else meta["bytes"],
            "bytes_now": current_bytes, "expected_bytes": meta["bytes"],
            "sha256": meta["sha256"], "sha256_now": current_hash,
            "matches_pin": match, "present_in_workspace": exists,
            "source_class": meta["classification"],
            "source_repository": lidar["repository"], "source_commit": lidar["commit"],
            "source_blob": meta["blob"],
            "source_url": lidar["commit_url"],
            "note": ("missing here; optional 3 m sibling-derived calibration cache" if not exists else
                     ("hash mismatch with sibling-repo pin" if match is False else
                      "matches sibling-repo pin; not a direct USGS 1 m source file")),
        }

    grid_path = ROOT / "evidence" / "grid.json"
    if grid_path.is_file():
        grid = json.loads(grid_path.read_text())
        for name, meta in (grid.get("inputs") or {}).items():
            out["derived_inputs"][name] = {
                "path": meta.get("path"), "bytes": meta.get("bytes"),
                "sha256": meta.get("sha256"), "role": meta.get("role"),
                "provenance": meta.get("provenance"), "pin_match": meta.get("pin_match"),
            }

    official = list(out["official_inputs"].values())
    external = [v for group in out["external_inputs"].values() for v in group.values()]
    out["summary"] = {
        "official_files": len(official),
        "verified_here": sum(v["matches_pin"] is True for v in official),
        "pinned_official_files": sum(bool(v.get("sha256")) for v in official),
        "missing_here": sum(not v["present_in_workspace"] for v in official),
        "mismatched_here": sum(v["matches_pin"] is False for v in official),
        "all_pinned_files_verified": all(v["matches_pin"] is True for v in official if v.get("sha256")),
        "external_files": len(external),
        "external_hash_verified": sum(v["matches_pin"] is True for v in external),
        "external_missing_here": sum(not v["present_in_workspace"] for v in external),
        "source_authentication": "mirror byte identity only; not organizer authentication",
    }
    (ROOT / "data_manifest.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["summary"], indent=2))
    for group, rows in (("competition", out["official_inputs"]), ("sibling-derived", out["external_inputs"]["lidar_cache"])):
        for name, row in rows.items():
            print(f"  {group}/{name}: present={row['present_in_workspace']} pin_match={row['matches_pin']}")


if __name__ == "__main__":
    main()
