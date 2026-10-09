#!/usr/bin/env python3
"""Download hash-pinned inputs from the public owner mirror into ignored ``data/`` paths.

This does not authenticate the files as organizer-originated. SHA-256 checks prove they match the
recorded pins; reviewers must use the DrivenData data page to confirm provenance/terms. The mirror
source, immutable commits, Git blob IDs, and expected bytes/hashes are recorded in
``registry/bridge_sources.json``. Large feature shards are streamed directly to disk and assembled
without loading the 419 MB stack into memory.

Run via: ``bash scripts/download_competition_data.sh [--skip-lidar]``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "registry" / "bridge_sources.json").read_text())


def hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def checked(path: Path, expected_bytes: int, expected_sha256: str) -> bool:
    if not path.is_file():
        return False
    actual_bytes, actual_sha256 = hash_file(path)
    if actual_bytes == expected_bytes and actual_sha256 == expected_sha256:
        return True
    raise RuntimeError(
        f"existing file does not match its pin: {path} "
        f"({actual_bytes} B, sha256={actual_sha256}; expected "
        f"{expected_bytes} B, sha256={expected_sha256}). Move it aside and investigate; it was not overwritten."
    )


def fetch_blob(repository: str, blob: str, destination: Path,
               expected_bytes: int, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if checked(destination, expected_bytes, expected_sha256):
        print(f"verified existing {destination.relative_to(ROOT)}", flush=True)
        return
    temporary = destination.with_name(destination.name + f".partial-{os.getpid()}")
    try:
        print(f"fetching {destination.relative_to(ROOT)} ({expected_bytes:,} B) from {repository}", flush=True)
        with temporary.open("wb") as output:
            subprocess.run(
                ["gh", "api", "--header", "Accept: application/vnd.github.raw",
                 f"repos/{repository}/git/blobs/{blob}"],
                check=True, stdout=output,
            )
        actual_bytes, actual_sha256 = hash_file(temporary)
        if (actual_bytes, actual_sha256) != (expected_bytes, expected_sha256):
            raise RuntimeError(
                f"download pin mismatch for {destination}: got {actual_bytes} B, sha256={actual_sha256}; "
                f"expected {expected_bytes} B, sha256={expected_sha256}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def assemble(parts: list[dict], destination: Path, expected_bytes: int, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if checked(destination, expected_bytes, expected_sha256):
        print(f"verified existing {destination.relative_to(ROOT)}", flush=True)
        return
    temporary = destination.with_name(destination.name + f".partial-{os.getpid()}")
    try:
        with temporary.open("wb") as output:
            for part in parts:
                path = ROOT / part["path"]
                if not checked(path, int(part["bytes"]), part["sha256"]):
                    raise RuntimeError(f"missing verified feature shard: {path}")
                with path.open("rb") as source:
                    shutil.copyfileobj(source, output, length=4 * 1024 * 1024)
        actual_bytes, actual_sha256 = hash_file(temporary)
        if (actual_bytes, actual_sha256) != (expected_bytes, expected_sha256):
            raise RuntimeError(
                f"assembled stack pin mismatch: got {actual_bytes} B, sha256={actual_sha256}; "
                f"expected {expected_bytes} B, sha256={expected_sha256}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def copy_verified(source: Path, destination: Path, expected_bytes: int, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if checked(destination, expected_bytes, expected_sha256):
        print(f"verified existing {destination.relative_to(ROOT)}", flush=True)
        return
    temporary = destination.with_name(destination.name + f".partial-{os.getpid()}")
    try:
        with source.open("rb") as in_stream, temporary.open("wb") as out_stream:
            shutil.copyfileobj(in_stream, out_stream, length=4 * 1024 * 1024)
        if not checked(temporary, expected_bytes, expected_sha256):
            raise AssertionError("temporary copy vanished")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-lidar", action="store_true",
                        help="fetch only the competition feature stack/catalogue/sample; skip sibling-derived LiDAR cache")
    args = parser.parse_args()
    if shutil.which("gh") is None:
        parser.error("GitHub CLI `gh` is required for the public API blob download")

    core = SOURCES["competition_bridge"]
    repo = core["repository"]
    files = core["files"]
    bridge = ROOT / "data" / "bridge"
    for part in files["features"]["parts"]:
        fetch_blob(repo, part["blob"], ROOT / part["path"], int(part["bytes"]), part["sha256"])
    assemble(files["features"]["parts"], ROOT / files["features"]["destination"],
             int(files["features"]["bytes"]), files["features"]["sha256"])

    for key in ("catalogue", "sample"):
        spec = files[key]
        mirror_path = bridge / Path(spec["destination"]).name
        fetch_blob(repo, spec["blob"], mirror_path, int(spec["bytes"]), spec["sha256"])
        copy_verified(mirror_path, ROOT / spec["destination"], int(spec["bytes"]), spec["sha256"])

    if not args.skip_lidar:
        lidar = SOURCES["lidar_cache"]
        for spec in lidar["files"].values():
            fetch_blob(lidar["repository"], spec["blob"], ROOT / spec["destination"],
                       int(spec["bytes"]), spec["sha256"])

    print("\nData staged and SHA-256 verified. These files are ignored by Git.")
    print(f"Competition mirror commit: {core['commit_url']}")
    print("Hash identity is not direct organizer authentication or a licensing determination.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"GitHub API download failed (exit {exc.returncode}); check GitHub connectivity/authentication.",
              file=sys.stderr)
        raise
