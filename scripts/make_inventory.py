#!/usr/bin/env python3
"""sha256-pin every committed evidence artifact (the auditable table).

Writes evidence/inventory.json: path, bytes, sha256 for every file under
evidence/ and docs/downloads/ (the submission TIF and its audit figures).
Re-run after any evidence change; the site and README quote these hashes.

Run:  python scripts/make_inventory.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [ROOT / "evidence", ROOT / "docs" / "downloads"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def main():
    rows = []
    for d in DIRS:
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix.lower() not in (".npy",):
                rows.append(dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size,
                                 sha256=sha256(p)))
    out = ROOT / "evidence" / "inventory.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"pinned {len(rows)} artifacts -> {out.relative_to(ROOT)}")
    for r in rows:
        if r["path"].endswith(".tif"):
            print(f"  {r['path']}  {r['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
