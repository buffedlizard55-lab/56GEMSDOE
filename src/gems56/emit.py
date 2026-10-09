"""Triangular-kernel, metric-aware prediction placement.

For a known truth set, adding a binary pixel changes TP by c (incremental
max-cover) and FP by f = 1 - max_g k(d). With alpha=.2, beta=.8, improvement
is exactly c*(1-.2*DTI) > .2*DTI*f. Distance alone does NOT decide this:
a dot can cover several truth pixels or only duplicate existing coverage.

At inference the truth is unknown. We greedily maximize SUM rho_g*max_x k(d)
under a fixed dot budget, where rho is a model-derived proxy truth density.
This is a coverage surrogate, not E[DTI] and not a guaranteed improvement in
DTI. A full-pool cardinality greedy has the usual submodular-coverage bound;
that bound does not extend to the DTI ratio or to an arbitrary restricted pool.
For a nonzero stopping target, FP discounts below use an explicitly approximate
independent-Bernoulli model. Nearby fault pixels are not in fact independent.

R2 repairs two inherited bugs: reversed zero-padding at grid edges; and wx=1
for EVERY candidate (because the code included its own lattice offset without
asking whether a truth pixel existed there), which disabled the cost gate.
"""
from __future__ import annotations

import heapq
import numpy as np

R_PX = 3
OFFSETS = [(dy, dx, 1.0 - np.hypot(dy, dx) / R_PX)
           for dy in range(-R_PX, R_PX + 1) for dx in range(-R_PX, R_PX + 1)
           if np.hypot(dy, dx) < R_PX]


def accept_bar(dti: float, alpha: float = 0.2) -> float:
    if not 0 <= dti <= 1 or not 0 <= alpha < 1:
        raise ValueError("DTI and alpha must be in their valid ranges")
    return float(alpha * dti / (1 - alpha * dti))


def _neighbour_tables(cands, shape):
    h, w = shape
    r, c = cands // w, cands % w
    nb = np.full((len(cands), len(OFFSETS)), -1, np.int64)
    kk = np.zeros(nb.shape, np.float32)
    for j, (dy, dx, k) in enumerate(OFFSETS):
        yy, xx = r + dy, c + dx
        ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        nb[ok, j] = yy[ok] * w + xx[ok]
        kk[ok, j] = k
    return nb, kk


def gain_field(density, shape):
    """Exact zero-padded convolution of rho with the triangular lattice kernel."""
    h, w = shape
    d = np.asarray(density, np.float32).reshape(h, w)
    out = np.zeros((h, w), np.float32)
    for dy, dx, k in OFFSETS:
        y0, y1 = max(0, -dy), min(h, h - dy)
        x0, x1 = max(0, -dx), min(w, w - dx)
        if y1 > y0 and x1 > x0:
            out[y0:y1, x0:x1] += d[y0 + dy:y1 + dy, x0 + dx:x1 + dx] * k
    return out


def expected_nearest_discount(rho_nb, weights):
    """E[max k among occupied neighbours], under independent Bernoulli rho.

    NOT max of lattice weights (the inherited, always-one bug). This is only a
    surrogate for a spatially correlated geological truth, stated in receipts.
    """
    survival = np.ones(rho_nb.shape[0], np.float64)
    discount = np.zeros_like(survival)
    order = np.argsort([-k for _, _, k in OFFSETS], kind="stable")
    for j in order:
        p = np.clip(rho_nb[:, j], 0, 1)
        discount += survival * p * weights[:, j]
        survival *= 1 - p
    return discount


def greedy_emit(density, allowed, dti_projected, budget, pool=400_000, hard_max=None, log=print):
    """Deterministic lazy greedy of expected incremental kernel coverage.

    R2 validation uses dti_projected=0 to enforce exactly the same density/budget
    for all arms; the nonzero cost gate is available and tested, not claimed to
    optimize an unknown official score. No truth labels enter this function.
    """
    allowed = np.asarray(allowed, bool)
    if allowed.ndim != 2:
        raise ValueError("allowed must be a 2D grid")
    dens = np.asarray(density, np.float32).reshape(allowed.shape).ravel()
    if not np.isfinite(dens).all() or (dens < 0).any():
        raise ValueError("density must be finite and nonnegative")
    budget = int(min(max(0, budget), hard_max if hard_max is not None else max(0, budget)))
    g0 = gain_field(dens, allowed.shape).ravel()
    candidates = np.flatnonzero(allowed.ravel() & (g0 > 0))
    total_candidates = len(candidates)
    count = min(int(pool), total_candidates)
    if count <= 0 or budget == 0:
        return np.zeros(allowed.shape, np.float32), dict(emitted=0, reason="zero budget or no positive-gain candidates")
    # Stable cutoff: do not let argpartition randomly pick a different plateau.
    vals = g0[candidates]
    if len(candidates) > count:
        cutoff = np.partition(vals, len(vals) - count)[len(vals) - count]
        high = candidates[vals > cutoff]
        tie = candidates[vals == cutoff]
        candidates = np.concatenate([high, tie[:count - len(high)]])
    order = np.lexsort((candidates, -g0[candidates]))
    cand = candidates[order]
    nb, kk = _neighbour_tables(cand, allowed.shape)
    rho_nb = dens[np.maximum(nb, 0)] * (nb >= 0)
    discount = expected_nearest_discount(rho_nb, kk) if dti_projected else np.zeros(len(cand))
    bar = accept_bar(dti_projected)
    cover = np.zeros(dens.shape, np.float32)
    heap = [(-float(g0[c]), int(c), i) for i, c in enumerate(cand)]
    heapq.heapify(heap)
    chosen, gains, rejected, updates = [], [], 0, 0
    while heap and len(chosen) < budget:
        _, pixel, i = heapq.heappop(heap)
        good = nb[i] >= 0
        neighbors = nb[i][good]
        gain = float(np.sum(rho_nb[i][good] * np.maximum(kk[i][good] - cover[neighbors], 0)))
        # Recompute stale upper bounds until this candidate really is the best.
        if heap and gain < -heap[0][0] - 1e-10:
            heapq.heappush(heap, (-gain, pixel, i))
            updates += 1
            continue
        if gain <= 0 or gain <= bar * (1 - discount[i]) + 1e-12:
            rejected += 1
            continue
        chosen.append(pixel)
        gains.append(gain)
        cover[neighbors] = np.maximum(cover[neighbors], kk[i][good])
        if len(chosen) % 5000 == 0:
            log(f"    placed {len(chosen)}; marginal expected cover {gain:.5g}")
    out = np.zeros(dens.shape, np.float32)
    out[chosen] = 1.0
    stats = dict(emitted=len(chosen), requested_budget=budget, pool=len(cand), pool_restricted=len(cand) < total_candidates,
                 bar=bar, dti_projected=dti_projected, marginal_first=gains[0] if gains else None,
                 marginal_last=gains[-1] if gains else None, total_expected_credit=float(sum(gains)),
                 rejects_at_stop=rejected, lazy_updates=updates, density_sum=float(dens.sum()),
                 false_positive_discount="independent-Bernoulli approximation" if dti_projected else "unused: fixed matched budget",
                 objective="expected triangular max-coverage surrogate; not expected DTI")
    return out.reshape(allowed.shape), stats
