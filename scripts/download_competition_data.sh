#!/usr/bin/env bash
# Fetch the hash-pinned, owner-maintained GitHub mirror without storing inputs in Git.
# Usage: bash scripts/download_competition_data.sh [--skip-lidar]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/download_competition_data.py" "$@"
