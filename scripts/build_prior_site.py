#!/usr/bin/env python3
"""Deprecated site-builder alias; delegate to the current status-aware builder.

The previous builder could reintroduce stale submission/promotion wording from an archived run.
Use scripts/build_site.py as the single source of generated Pages content.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("build_site.py")
os.execv(sys.executable, [sys.executable, str(SCRIPT), *sys.argv[1:]])
