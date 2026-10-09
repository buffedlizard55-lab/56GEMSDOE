"""Distance-weighted Tversky index -- literal transcription of the published metric.

Source of truth (read 2026-10-06, agent fetch):
    https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric

Published definitions, with R = 300 m, alpha = 0.2, beta = 0.8:

    k(d)  = max(1 - d/R, 0)                                   (triangular kernel)
    TPw   = sum_{g in G} max_{x : d(x,g) <= R} p(x) k(d(x,g))
    FPw   = sum_{x : p(x) > 0} p(x) [ 1 - max_{g in G} k(d(x,g)) ]
    FNw   = sum_{g in G} [ 1 - max_{x : d(x,g) <= R} p(x) k(d(x,g)) ]
    DTI   = TPw / (TPw + alpha*FPw + beta*FNw + eps)

Algebraic consequences (checked against brute force, not a model of hidden labels):

    (i)  FNw == |G| - TPw identically, hence with T = TPw, S = sum_x p(x),
         M = sum_x p(x) max_g k(d(x,g))  and  FPw = S - M:

             DTI = T / ( 0.2*(T + S - M) + 0.8*|G| )

    (ii) For general incremental credit c and false-positive increment f, an addition helps iff

             c * (1 - 0.2*DTI) > 0.2*DTI*f.

         Only in the special case of one previously uncovered truth pixel, with c=w and f=1-w,
         does this reduce to w > 0.2*DTI. Max-cover competition between nearby predictions means
         c is not generally the nearest-truth kernel weight. Calibration and placement still matter.
         Uniform scaling of a fixed support is monotone, but that one-parameter argument alone is
         not a proof of global binary optimality or of optimal expected DTI under uncertain truth.

The organiser's published worked example (TPw 3.00, FPw 1.89, FNw 2.00) evaluates to
0.6026516673...; the page rounds it to 0.60.  ``tests/test_metric.py`` pins that number so a
future edit cannot silently change the metric.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

ALPHA = 0.2
BETA = 0.8
R_M = 300.0
PIXEL_M = 100.0
R_PX = R_M / PIXEL_M          # exactly 3.0 px at 100 m
EPS = 0.0                      # published eps unquantified; empty denominator explicitly returns zero


def kernel(d_m) -> np.ndarray:
    """Triangular kernel k(d) = max(1 - d/R, 0), distances in metres."""
    return np.maximum(1.0 - np.asarray(d_m, dtype=np.float64) / R_M, 0.0)


def _offsets() -> list[tuple[int, int, float]]:
    """All lattice offsets with |offset| <= R, as (dy, dx, k). Enumerated, never approximated."""
    out = []
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            d = float(np.hypot(dy, dx))
            if d <= R_PX + 1e-12:
                out.append((dy, dx, 1.0 - d / R_PX))
    return out


OFFSETS = _offsets()


def max_cover(p: np.ndarray, g: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-truth-pixel best cover m(g), per-pixel best truth weight q(x), and diagnostics.

    m     = 1-D, in row-major order over the truth pixels: m[i] = max over emitted x within R of
            p(x)*k(d(x, g_i))                 (used by TPw and FNw)
    q[x] = max over truth g of k(d(x,g))                       (used by FPw)

    ``m`` is computed by enumerating the exact lattice offsets inside the kernel disc (no
    interpolation, no separable approximation), which is what makes it a literal transcription.
    ``q`` is the kernel applied to the exact Euclidean distance transform, i.e.
    max_g k(d) = k(min_g d) because k is non-increasing.
    """
    w = np.where(p > 0, p, 0.0).astype(np.float64)
    # zero-padded shifts, never np.roll: a wrapped edge would invent cover across the grid
    wp = np.pad(w, 3, mode="constant", constant_values=0.0)
    idx = g > 0
    gy, gx = np.nonzero(idx)
    m = np.zeros(gy.size, dtype=np.float64)
    for dy, dx, kk in OFFSETS:
        # Gather truth coordinates before multiplication: 60k values, not a
        # 12.28M-cell temporary for every offset. Sign is immaterial to the
        # symmetric kernel but the zero padding is essential.
        m = np.maximum(m, wp[gy + 3 - dy, gx + 3 - dx] * kk)
    ed = ndimage.distance_transform_edt(~idx, sampling=PIXEL_M)
    q = np.maximum(1.0 - ed / R_M, 0.0)
    return m, q, ed


def dti(p: np.ndarray, g: np.ndarray, alpha: float = ALPHA, beta: float = BETA,
        eps: float = EPS) -> dict:
    """Exact DTI of prediction ``p`` against truth mask ``g`` (both 2-D, same grid)."""
    p = np.asarray(p, dtype=np.float64)
    g = np.asarray(g)
    if p.shape != g.shape or p.ndim != 2:
        raise ValueError(f"2D shape mismatch {p.shape} vs {g.shape}")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("predictions must be finite and within [0,1]")
    if not np.isfinite([alpha, beta, eps]).all() or alpha < 0 or beta < 0 or eps < 0:
        raise ValueError("metric coefficients and epsilon must be finite and nonnegative")
    ng = int((g > 0).sum())
    if ng == 0:
        return dict(dti=0.0, tpw=0.0, fpw=float(np.nansum(p)), fnw=0.0, n_truth=0,
                    mass=float(np.nansum(p)), m_covers=0.0, reduced=None)
    m, q, _ = max_cover(p, g)
    tpw = float(m.sum())
    mass = float(p[p > 0].sum())
    m_cover = float((p * q)[p > 0].sum())
    fpw = mass - m_cover
    fnw = ng - tpw
    num = tpw
    den = tpw + alpha * fpw + beta * fnw + eps
    reduced_den = (1 - beta) * tpw + alpha * (mass - m_cover) + beta * ng + eps
    reduced = tpw / reduced_den if reduced_den > 0 else 0.0
    return dict(dti=num / den if den > 0 else 0.0, tpw=tpw, fpw=fpw, fnw=fnw, n_truth=ng,
                mass=mass, m_covers=m_cover, reduced=float(reduced))


def dti_bruteforce(p: np.ndarray, g: np.ndarray, alpha: float = ALPHA,
                   beta: float = BETA) -> float:
    """Loop-for-loop transcription over the positive sets only. Reference implementation for tests."""
    pi = np.argwhere(np.asarray(p) > 0)
    gi = np.argwhere(np.asarray(g) > 0)
    if len(gi) == 0:
        return 0.0
    pv = p[pi[:, 0], pi[:, 1]].astype(np.float64)
    tpw = 0.0
    for gxy in gi:
        if len(pi):
            d = np.hypot(pi[:, 0] - gxy[0], pi[:, 1] - gxy[1]) * PIXEL_M
            kk = np.maximum(1.0 - d / R_M, 0.0)
            best = float(np.max(pv * kk)) if kk.size else 0.0
            sel = d <= R_M + 1e-9
            best = float(np.max((pv * kk)[sel])) if sel.any() else 0.0
        else:
            best = 0.0
        tpw += best
    fpw = 0.0
    for x in pi:
        d = np.hypot(gi[:, 0] - x[0], gi[:, 1] - x[1]) * PIXEL_M
        fpw += float(p[x[0], x[1]]) * (1.0 - (np.max(np.maximum(1.0 - d / R_M, 0.0)) if len(gi) else 0.0))
    fnw = len(gi) - tpw
    return tpw / (tpw + alpha * fpw + beta * fnw)


def credit_bar(dti_value: float, alpha: float = ALPHA) -> float:
    """Realised kernel weight a marginal emitted pixel must beat to raise DTI (see module docstring)."""
    return alpha * dti_value


def bar_to_max_distance_px(bar: float) -> float:
    """Kernel weight bar -> the largest lattice distance (px) that still clears it, for p = 1."""
    return float(R_PX * max(0.0, 1.0 - bar))
