#!/bin/bash
# Place every competition input this repository needs into data/, with hash verification.
#
# Two routes, in order of preference:
#
#   ROUTE A (official, any machine with a DrivenData login):
#     Download the four files from https://www.drivendata.org/competitions/306/competition-doe-gems/data/
#     into data/raw/ (training_features.tif, labels.tif if offered, sample_submission.tif,
#     existing_faults.tif), then run this script. Files are verified against the sha256 pins in
#     registry/input_pins.json and copied into their canonical locations. A pin mismatch is a
#     hard error, never a warning.
#
#   ROUTE B (sandbox default, no DrivenData login needed):
#     Assemble from the owner's hash-pinned GitHub bridge (the route this repository's pins
#     document: registry/input_pins.json "retrieval_route"). The bridge manifest itself is
#     fetched live from api.github.com and every shard is checked against it BEFORE assembly,
#     then the assembled file is checked against the pin in registry/input_pins.json.
#     Bytes still are NOT organizer-authenticated: see IR-56-003 (a logged-in human should
#     confirm the three data-tab hashes).
#
# After placement, scripts/prepare_data.py re-derives grid facts from the bytes on disk and
# fails on any pin mismatch.
#
# Usage:  bash scripts/download_competition_data.sh
#         bash scripts/fetch_inputs.sh                (identical; alias referenced by the pins)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

BRIDGE_REPO="buffedlizard55-lab/GEMSDOE"
LIDAR_REPO="buffedlizard55-lab/GEMSDOE48"
WORK="$(mktemp -d /tmp/gems-bridge.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

pin() { # pin <key> -> sha256 from registry/input_pins.json
  "$PY" - "$1" <<'EOF'
import json, sys
pins = json.load(open("registry/input_pins.json"))
print(pins["files"][sys.argv[1]].get("sha256") or "")
EOF
}

sha() { sha256sum "$1" | cut -d' ' -f1; }

verify() { # verify <key> <path>
  local key="$1" path="$2" want got
  want="$(pin "$key")"
  [ -z "$want" ] && { echo "  $key: no sha256 pin recorded; size check only"; return 0; }
  got="$(sha "$path")"
  if [ "$got" != "$want" ]; then
    echo "PIN MISMATCH for $key:" >&2
    echo "  want $want" >&2; echo "  got  $got  ($path)" >&2
    exit 1
  fi
  echo "  $key: pin OK ($(stat -c%s "$path") bytes, $got)"
}

mkdir -p data/grid data/external data/raw

have_route_a() { [ -f data/raw/training_features.tif ] && [ -f data/raw/sample_submission.tif ]; }
have_placed() { [ -f data/training_features.tif ] && [ -f data/grid/existing_faults.tif ] && [ -f data/grid/sample_submission.tif ]; }

if have_route_a && [ ! -f data/training_features.tif ]; then
  echo "ROUTE A: installing official files from data/raw/"
  cp data/raw/training_features.tif data/training_features.tif
  cp data/raw/sample_submission.tif data/grid/sample_submission.tif
  # existing_faults.tif may be named differently in a manual download
  if [ -f data/raw/existing_faults.tif ]; then cp data/raw/existing_faults.tif data/grid/existing_faults.tif
  elif [ -f data/grid/existing_faults.tif ]; then :; else
    echo "  NOTE: data/raw/existing_faults.tif missing; keeping bridge copy if present" >&2; fi
elif ! have_placed; then
  echo "ROUTE B: assembling from the pinned GitHub bridge ($BRIDGE_REPO) into $WORK"
  git clone --depth 1 --filter=blob:none --sparse "https://github.com/$BRIDGE_REPO.git" "$WORK/GEMSDOE" >/dev/null 2>&1
  git -C "$WORK/GEMSDOE" sparse-checkout set data/bridge >/dev/null 2>&1
  B="$WORK/GEMSDOE/data/bridge"

  # 1) every shard against the OWNER manifest (fetched live, not trusted from disk)
  "$PY" - "$B" <<'EOF'
import hashlib, json, sys, urllib.request, base64
b = sys.argv[1]
url = ("https://api.github.com/repos/buffedlizard55-lab/GEMSDOE"
       "/contents/data/bridge/manifest.json")
req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
man = json.loads(base64.b64decode(json.load(urllib.request.urlopen(req, timeout=30))["content"]))
ok = True
for f in man["files"]:
    if "parts" in f:
        for p in f["parts"]:
            h = hashlib.sha256(open(f"{b}/{p['name']}", "rb").read()).hexdigest()
            good = h == p["sha256"]
            ok &= good
            print(f"  shard {p['name']}: {'OK' if good else 'MISMATCH ' + h}")
    else:
        h = hashlib.sha256(open(f"{b}/{f['name']}", "rb").read()).hexdigest()
        good = h == f["sha256"]
        ok &= good
        print(f"  file {f['name']}: {'OK' if good else 'MISMATCH ' + h}")
if not ok:
    raise SystemExit("owner-manifest verification FAILED")
print("  owner manifest: all hashes OK")
EOF

  # 2) assemble the feature stack, verify against OUR pin, place
  if [ ! -f data/training_features.tif ]; then
    cat "$B"/gems-geodawn-numerical-features.tif.part-* > data/training_features.tif.tmp
    verify features data/training_features.tif.tmp
    mv data/training_features.tif.tmp data/training_features.tif
  fi
  cp "$B/existing_faults.tif" data/grid/existing_faults.tif
  cp "$B/example_submission.tif" data/grid/sample_submission.tif

  # 3) lidar scarp calibration layer (sibling-derived, documented in input_pins.json)
  if [ ! -f data/external/h52_scarp3m_100m.tif ]; then
    git clone --depth 1 --filter=blob:none --sparse "https://github.com/$LIDAR_REPO.git" "$WORK/GEMSDOE48" >/dev/null 2>&1
    git -C "$WORK/GEMSDOE48" sparse-checkout set data/external >/dev/null 2>&1
    cp "$WORK/GEMSDOE48/data/external/h52_scarp3m_100m.tif" data/external/
    cp "$WORK/GEMSDOE48/data/external/h52_scarp3m_100m.json" data/external/ 2>/dev/null || true
    cp "$WORK/GEMSDOE48/data/external/2m_temperature_probe_INGENIOUS_regional_data.zip" data/external/ 2>/dev/null || true
    cp "$WORK/GEMSDOE48/data/external/README.md" data/external/README_GEMSDOE48.md 2>/dev/null || true
  fi
else
  echo "All primary inputs already present; verifying only."
fi

echo "Verifying pins:"
verify features   data/training_features.tif
verify catalogue  data/grid/existing_faults.tif
verify sample     data/grid/sample_submission.tif
[ -f data/external/h52_scarp3m_100m.tif ] && verify lidar_scarp data/external/h52_scarp3m_100m.tif || true

# Compatibility copy: the vendored template tools and tests read data/sample_submission.tif,
# while the bridge places the canonical copy at data/grid/sample_submission.tif (IR-57-005).
cp -f data/grid/sample_submission.tif data/sample_submission.tif

echo "Re-deriving grid facts (scripts/prepare_data.py):"
"$PY" scripts/prepare_data.py >/dev/null
echo "DONE. evidence/grid.json written; pin_match must be true for all three official inputs."
