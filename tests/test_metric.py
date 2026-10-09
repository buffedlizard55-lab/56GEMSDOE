"""Tests for the vendored template metric (src/gems/metric.py, pinned to GEMSDOE32 @ 0d6a624).

The brute-force reference below is an independent literal transcription of the published
equations, so these tests check the vendored vectorised code against the formula itself.
"""

import numpy as np
import pytest

from gems import metric as M

ALPHA, BETA, R = 0.2, 0.8, 3.0


def brute_force(p, g, known=None, valid=None):
    H, W = p.shape
    valid = np.ones_like(g, bool) if valid is None else valid
    known = np.zeros_like(g, bool) if known is None else known
    active = valid & ~known
    p = np.where(active, p, 0.0)
    G = [tuple(x) for x in zip(*np.nonzero(g & active))]
    P = [(i, j) for i in range(H) for j in range(W) if p[i, j] > 0]

    def k(d):
        return max(1.0 - d / R, 0.0)

    tp = fn = 0.0
    for gi, gj in G:
        best = 0.0
        for i, j in P:
            d = np.hypot(i - gi, j - gj)
            if d <= R:
                best = max(best, p[i, j] * k(d))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for i, j in P:
        m = max([k(np.hypot(i - gi, j - gj)) for gi, gj in G] + [0.0])
        fp += p[i, j] * (1.0 - m)
    return tp / (tp + ALPHA * fp + BETA * fn + 1e-12), dict(tp=tp, fp=fp, fn=fn)


def test_template_constants_match_published_values():
    assert M.ALPHA == 0.2 and M.BETA == 0.8
    assert M.RADIUS_PX == 3.0  # 300 m at 100 m pixels


def test_worked_example_arithmetic_matches_published_0_60():
    # Official page: TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 -> TI_w = 0.60
    assert round(M.dti(3.00, 1.89, 2.00), 2) == 0.60


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_vectorised_matches_brute_force(seed):
    rng = np.random.default_rng(seed)
    g = rng.random((9, 11)) < 0.08
    p = np.where(rng.random((9, 11)) < 0.3, rng.random((9, 11)), 0.0)
    fast = M.dti_exact(p, g)
    slow_score, slow_parts = brute_force(p, g)
    assert fast["dti"] == pytest.approx(slow_score, rel=1e-6, abs=1e-9)
    assert fast["tp"] == pytest.approx(slow_parts["tp"], rel=1e-6, abs=1e-9)
    assert fast["fp"] == pytest.approx(slow_parts["fp"], rel=1e-6, abs=1e-9)
    assert fast["fn"] == pytest.approx(slow_parts["fn"], rel=1e-6, abs=1e-9)


def test_binary_fast_path_agrees_with_exact():
    rng = np.random.default_rng(7)
    g = rng.random((15, 15)) < 0.1
    b = rng.random((15, 15)) < 0.15
    assert M.dti_binary(b, g)["dti"] == pytest.approx(M.dti_exact(b.astype(float), g)["dti"], rel=1e-9)


def test_identity_dti_equals_T_over_alpha_T_plus_F_plus_beta_K():
    # With alpha + beta = 1 and FN = |G| - TP, DTI = T / (alpha (T+F) + beta |G|)
    rng = np.random.default_rng(3)
    g = rng.random((12, 12)) < 0.12
    p = rng.random((12, 12)) * (rng.random((12, 12)) < 0.2)
    out = M.dti_exact(p, g)
    alt = out["tp"] / (ALPHA * (out["tp"] + out["fp"]) + BETA * out["n_truth"] + 1e-12)
    assert out["dti"] == pytest.approx(alt, rel=1e-9)


def test_known_pixels_are_masked_out_of_truth_and_prediction():
    g = np.zeros((20, 20), bool)
    g[10, 2:18] = True
    p = g.astype(float)
    known = np.zeros_like(g)
    known[10, 2:18] = True  # the whole line is a known fault -> nothing is scored
    out = M.dti_exact(p, g, known=known)
    assert out["n_truth"] == 0 and out["dti"] == 0.0


def test_perfect_and_empty_predictions():
    g = np.zeros((20, 20), bool)
    g[5, 2:18] = True
    assert M.dti_exact(g.astype(float), g)["dti"] == pytest.approx(1.0, abs=1e-9)
    assert M.dti_exact(np.zeros((20, 20)), g)["dti"] == 0.0


def test_out_of_range_predictions_are_rejected():
    g = np.zeros((4, 4), bool)
    with pytest.raises(ValueError):
        M.dti_exact(np.full((4, 4), 1.5), g)


def test_break_even_credit_per_unit_mass_is_alpha_times_dti():
    """Adding unit mass with realised kernel weight k raises DTI iff k > alpha * DTI.

    Numeric check on a concrete state: T=1, F=2, K=4 -> DTI = 1/(0.2*3 + 0.8*4).
    """
    T, F, K = 1.0, 2.0, 4.0
    s = T / (ALPHA * (T + F) + BETA * K)
    kstar = M.marginal_inclusion_threshold(s)
    assert kstar == pytest.approx(ALPHA * s)
    up = (T + kstar + 1e-6) / (ALPHA * (T + kstar + F + 1 - kstar) + BETA * K)
    down = (T + kstar - 1e-6) / (ALPHA * (T + kstar + F + 1 - kstar) + BETA * K)
    assert up > s > down
