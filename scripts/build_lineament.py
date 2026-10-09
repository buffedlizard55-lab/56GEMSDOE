#!/usr/bin/env python3
"""E2 — a *lineament-persistence* channel: how linear is the high ground at this cell?

Every channel in ``build_fields.py`` is a pointwise response: a filter that fires at a crest, a step or
a strain maximum. A fault is not a point, it is a line, and the difference matters for this competition
because the two things a mapper uses to decide "this scarp is a fault and that one is an erosion line"
are (i) straightness/continuity along strike and (ii) persistence across the terrain. So this channel
asks a second question of every cell:

    for each of four strike directions, what is the *mean* channel value along a 1-pixel-wide
    segment of length 2L+1 through this cell -- and what is the best such mean over the strikes?

That is a discrete Radon line integral over the fused multi-physics rank field, evaluated at
L in {4, 8, 16} cells (400, 800, 1600 m). A blob scores high on L=4 but cannot beat a neighbour on
L=16; a through-going lineation scores high at all three lengths, and taking the *maximum over
lengths* keeps a 400 m stepover on a relay ramp as good as a continuous trace. The strike set is
0/45/90/135 deg, i.e. the Basin-and-Range dominant trends (N-S, E-W and the two obliques) sampled at
the lattice; the direction is chosen per cell, so no regional structural trend is baked in.

Why this should catch a fault that the USGS/INGENIOUS catalogue missed, and not one it already has:
the catalogue compiler worked from geomorphic expression and field access, so a trace that is *linear and
persistent under valley fill* -- where the scarp dies but the line keeps going -- is exactly the case a
line-integral of a magnetic/gravity/strain consensus fires on and a hillshade does not. It cannot help
with a trace already in the catalogue, which is masked out of the scored domain anyway.

Reproduce: python scripts/build_lineament.py            (~2 min)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIELDS = ROOT / "data" / "interim" / "fields"
LENGTHS = (4, 8, 16)
# (dy, dx) unit-ish steps along each strike, on the 100 m lattice
STRIKES = [(0, 1), (1, 0), (1, 1), (1, -1)]


def as_rank(v: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.zeros(v.size, np.uint16)
    idx = np.flatnonzero(valid.ravel())
    x = v.ravel()[idx]
    order = np.argsort(x, kind="stable")
    rank = np.empty(x.size, np.float64)
    rank[order] = np.arange(x.size, dtype=np.float64)
    out[idx] = np.clip(rank / max(1, x.size - 1) * 65535.0, 0, 65535).astype(np.uint16)
    return out.reshape(v.shape)


def line_integral(f: np.ndarray, dy: int, dx: int, L: int) -> np.ndarray:
    """Mean of f over the 2L+1 cells on the ray through each pixel along (dy, dx), zero-padded so a
    segment that runs off the grid is not credited with values it does not have."""
    h, w = f.shape
    acc = np.zeros_like(f)
    cnt = np.zeros_like(f)
    for t in range(-L, L + 1):
        Y, X = t * dy, t * dx
        y0, y1 = max(0, Y), min(h, h + Y)
        x0, x1 = max(0, X), min(w, w + X)
        acc[y0:y1, x0:x1] += f[y0 - Y:y1 - Y, x0 - X:x1 - X]
        cnt[y0:y1, x0:x1] += 1.0
    return acc / np.maximum(cnt, 1.0)


def main() -> int:
    t0 = time.time()
    fp = np.load(FIELDS / "_footprint.npy")
    names = json.loads((ROOT / "evidence" / "field_holdout_v1.json").read_text())["fields"] if \
        (ROOT / "evidence" / "field_holdout_v1.json").exists() else None
    use = ["mag_ridge", "scarp_slope", "rtp_ridge", "grav_ridge", "strain_2ndinv_ridge", "cover_depth_edge"]
    for n in use:
        assert (FIELDS / f"{n}.npy").exists(), f"missing channel {n}"
    ranks = np.stack([np.load(FIELDS / f"{n}.npy").astype(np.float32) / 65535.0 for n in use])
    fuse = ranks.mean(0).astype(np.float32)
    np.save(FIELDS / "fuse6.npy", as_rank(np.where(fp, fuse, -np.inf), fp))
    best = np.full(fuse.shape, -np.inf, np.float32)
    detail = {}
    for L in LENGTHS:
        per_strike = np.stack([line_integral(fuse, dy, dx, L) for dy, dx in STRIKES])
        m = per_strike.max(0)
        np.maximum(best, m, out=best)
        detail[str(L)] = dict(max_mean=float(best.max()), p99=float(np.percentile(best[fp], 99)))
    np.save(FIELDS / "line_persist.npy", as_rank(np.where(fp, best, -np.inf), fp))
    # persistence *contrast*: a line is only a lineament if it beats the cross-strike neighbourhood.
    cross = np.stack([line_integral(fuse, dx, -dy, 1) for dy, dx in STRIKES]).mean(0)
    cont = np.maximum(best - cross, 0.0).astype(np.float32)
    np.save(FIELDS / "line_contrast.npy", as_rank(np.where(fp, cont, -np.inf), fp))
    inv = json.loads((FIELDS / "inventory.json").read_text())
    inv["fields"].update({
        "fuse6": dict(description=f"equal-weight mean of the percentile ranks of {use}",
                      sources=use),
        "line_persist": dict(description=f"max over 4 strikes x L in {LENGTHS} cells of the mean of "
                                          f"fuse6 along a 1 px wide line integral (discrete Radon)",
                             lengths_m=[L * 100 for L in LENGTHS], strikes_deg=[0, 45, 90, 135],
                             stats=detail),
        "line_contrast": dict(description="line_persist minus the mean of the same field across strike: "
                                          "linear continuity in excess of local background",
                              note="excess of along-strike mean over cross-strike mean"),
    })
    (FIELDS / "inventory.json").write_text(json.dumps(inv, indent=1))
    print(json.dumps(dict(seconds=round(time.time() - t0, 1), channels=use, lengths=LENGTHS,
                          stats=detail), indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
