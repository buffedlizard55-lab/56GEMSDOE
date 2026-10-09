"""Shared pooled hide-and-recover evaluator, not a new/private metric implementation.

Delegates official-formula arithmetic and visible-pixel masking to the template's
holdout.score / metric.max_cover. Spatial block terms are bookkeeping for a
conditional bootstrap, not a new scoring rule. No translated synthetic truth.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
from . import holdout, metric

VERSION = 'gems52-pooled-hide-v1'


def implementation_hashes():
    return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ('evaluate_holdout.py', 'holdout.py', 'metric.py', 'spatial.py')}


def evaluate(prediction, fold, valid, block_side=200):
    """Exact fold score plus additive (TPw, FPw, FNw, truth count) per spatial cluster."""
    if block_side <= 0:
        raise ValueError('block_side must be positive')
    p = np.asarray(prediction)
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError('predictions must be finite in [0,1] before masking')
    result = holdout.score(p, fold, valid, restrict_to_region=True, extra=False)
    p = np.where(valid & fold['region'] & ~fold['visible'], p, 0).astype(np.float32)
    truth = valid & fold['region'] & fold['truth']
    if not truth.any():
        raise ValueError('a holdout fold must contain positives')
    covers, q, _ = metric.max_cover(p, truth)
    h, w = truth.shape
    ncols = (w + block_side - 1) // block_side
    nrows = (h + block_side - 1) // block_side
    terms = np.zeros((ncols * nrows, 4), np.float64)
    y, x = np.nonzero(truth)
    ids = (y // block_side) * ncols + (x // block_side)
    for j, v in ((0, covers), (2, 1.0 - covers), (3, np.ones(len(y)))):
        terms[:, j] = np.bincount(ids, weights=v, minlength=len(terms))
    y, x = np.nonzero(p > 0)
    ids = (y // block_side) * ncols + (x // block_side)
    terms[:, 1] = np.bincount(ids, weights=p[y, x].astype(float) * (1.0 - q[y, x]), minlength=len(terms))
    totals = terms.sum(axis=0)
    np.testing.assert_allclose(totals, [result['tpw'], result['fpw'], result['fnw'], result['n_truth']], rtol=1e-11, atol=1e-7)
    result.update(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
                  spatial_bootstrap_cluster_m=block_side * metric.PIXEL_M)
    return result, terms


def from_terms(terms):
    a = np.asarray(terms, dtype=float)
    tp, fp, fn = a[..., 0], a[..., 1], a[..., 2]
    den = tp + metric.ALPHA * fp + metric.BETA * fn
    return np.divide(tp, den, out=np.zeros_like(tp), where=den > 0)


def pooled_summary(terms_by_arm, draws=1000, seed=520810, candidate='disagreement'):
    """Pool terms first; paired percentile CI resamples physical 20 km blocks.

    Each arm has identical block coordinates/order and evaluation masks. Contributions
    from the same physical block across folds are merged BEFORE resampling, so overlap
    in a component tail is not mistaken for an independent new spatial cluster.
    """
    names = list(terms_by_arm)
    if not names or candidate not in terms_by_arm:
        raise ValueError('candidate and at least one arm required')
    if draws < 20:
        raise ValueError('too few bootstrap draws')
    arrays = {n: np.asarray(v, float) for n, v in terms_by_arm.items()}
    shape = next(iter(arrays.values())).shape
    if len(shape) != 2 or shape[1] != 4 or any(a.shape != shape for a in arrays.values()):
        raise ValueError('aligned per-spatial-block arrays of four terms required')
    if any(not np.isfinite(a).all() or (a < -1e-8).any() for a in arrays.values()):
        raise ValueError('invalid metric terms')
    # Include negative-only clusters carrying FP weight for any comparator.
    active = np.any(np.stack([a.sum(axis=1) > 0 for a in arrays.values()]), axis=0)
    arrays = {n: a[active] for n, a in arrays.items()}
    nb = int(active.sum())
    if nb < 2:
        raise ValueError('need at least two nonempty spatial clusters')
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(draws, nb))
    boot = {n: from_terms(a[picks].sum(axis=1)) for n, a in arrays.items()}
    summaries = {}
    for n, a in arrays.items():
        t = a.sum(axis=0)
        summaries[n] = dict(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
            dti=float(from_terms(t)), ci95=[float(x) for x in np.quantile(boot[n], [.025, .975])],
            withheld_positive_pixels=int(round(t[3])), tpw=float(t[0]), fpw=float(t[1]), fnw=float(t[2]))
    controls = [n for n in names if n != candidate]
    best = max(controls, key=lambda n: summaries[n]['dti']) if controls else None
    differences = {}
    for n in controls:
        delta = boot[candidate] - boot[n]
        differences[n] = dict(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
            delta=summaries[candidate]['dti'] - summaries[n]['dti'],
            ci95=[float(x) for x in np.quantile(delta, [.025, .975])],
            withheld_positive_pixels=summaries[candidate]['withheld_positive_pixels'])
    return dict(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
        alpha=metric.ALPHA, beta=metric.BETA, triangular_radius_m=metric.R_M,
        pooled=True, scores=summaries, best_comparable_control=best,
        paired_differences=differences, bootstrap=dict(method='paired physical spatial-cluster percentile',
            clusters=nb, draws=draws, seed=seed, confidence=.95,
            caveat='Conditional on fitted folds, catalogue labels and fixed budgets; not a leaderboard interval.'),
        implementation_sha256=implementation_hashes())
