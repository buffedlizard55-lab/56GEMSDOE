#!/usr/bin/env python3
"""Rebuild the flat prior corpus that the uniqueness gate reads, verified against the index.

``build_corrections_submission.py`` and ``screen_registry.py`` glob ``*.tif`` in one flat directory
(default ``/home/user/_reg``). That directory did not exist in this sandbox, so the gate silently
checked **zero** priors and wrote an empty receipt (found and reverted in this session).

This script rebuilds it from ``docs/research/registry-index.json`` (944 rasters, sha256 per file):

* sparse, blobless, depth-1 clone of each sibling repo that the index names (github.com only);
* every index entry is copied to ``<dest>/<repo>__<path with / -> __>`` and its sha256 is
  re-computed and compared with the index. A mismatch aborts; a missing file is listed, not hidden.

Reproduce: ``python scripts/mirror_registry_corpus.py [dest] [workdir]``
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "research" / "registry-index.json"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv):
    dest = Path(argv[0]) if argv else Path("/home/user/_reg")
    work = Path(argv[1]) if len(argv) > 1 else Path("/home/user/_regsrc")
    dest.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text())
    repos = sorted({r["path"].split("/")[0] for r in index})
    report = dict(index_entries=len(index), repos=len(repos), copied=0, missing=[], mismatched=[], clone_failed=[])
    for repo in repos:
        rdir = work / repo
        if not rdir.exists():
            r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse",
                                f"https://github.com/buffedlizard55-lab/{repo}.git", str(rdir)],
                               capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                report["clone_failed"].append(repo)
                continue
            subprocess.run(["git", "-C", str(rdir), "sparse-checkout", "set", "--no-cone", "*.tif"],
                           capture_output=True, text=True, timeout=900)
        for rec in [x for x in index if x["path"].split("/")[0] == repo]:
            rel = rec["path"]
            src = rdir / rel.split("/", 1)[1]
            if not src.exists():
                # sparse checkout may not have materialised it yet; one checkout pass per repo
                subprocess.run(["git", "-C", str(rdir), "checkout", "-q"], capture_output=True, text=True, timeout=900)
            if not src.exists():
                report["missing"].append(rel)
                continue
            flat = dest / (repo + "__" + rel.split("/", 1)[1].replace("/", "__"))
            if not flat.exists():
                shutil.copyfile(src, flat)
            if sha256(flat) != rec["sha256"]:
                report["mismatched"].append(rel)
                flat.unlink()
                continue
            report["copied"] += 1
        print(repo, report["copied"], flush=True)
    report["ok"] = not report["missing"] and not report["mismatched"] and not report["clone_failed"]
    (ROOT / "evidence" / "registry_corpus_mirror.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
