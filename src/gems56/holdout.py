"""Spatially-blocked, whole-segment, prevalence-matched validation, in two instruments.

Both instruments obey the three rules that matter here, and both are reported:

* **Whole segments.** Held-out truth is a set of complete 8-connected catalogue components.  If a
  trace were cut by a fold boundary the model would be shown half of it and asked to continue the
  other half, which is not discovery.  Components go to the fold owning most of their pixels.
* **The visible catalogue is masked exactly as the organiser masks it.** DrivenData staff, thread
  11516 post #2: "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from
  evaluation, so they do not count towards penalty terms", and post #4 that the mask is
  *pixel-exact* with no buffer.  So mass sitting on a visible catalogue pixel is deleted before
  scoring (``mask_visible``), while mass one pixel off the trace is fully penalised.
* **Prevalence matching.** The hidden set is bracketed at 0.112-0.294 % of the footprint by the
  organiser's own published scores (``knowledge/01``); folds are thinned to that bracket because
  the optimal emission density moves with prevalence, and an unmatched fold selects the wrong budget.

Instruments
-----------
``mode="hide"``  -- hide-and-recover: remove whole components from the *labels*, train everywhere
                    else, score everywhere.  Measures recovery of structure the model was never
                    told about, and is the comparison the brief asks for against a single view.
``mode="block"`` -- quadrant-blocked: train on other quadrants only (minus a boundary buffer),
                    score inside the held quadrant.  Removes the "the neighbouring block gives it
                    away" leak and is the conservative read.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import emit as E
from . import metric as M

PREVALENCE_TARGETS = (0.00112, 0.00200, 0.00294)     # |G| bracket / footprint
DISC = [(dy, dx) for dy in range(-3, 4) for dx in range(-3, 4) if dy * dy + dx * dx <= 9]


def block_ids(shape: tuple[int, int], valid: np.ndarray, n: int = 4) -> np.ndarray:
    """Contiguous rectangular block ids, -1 outside the footprint.  n x n blocks."""
    h, w = shape
    rs = np.linspace(0, h, n + 1).astype(int)
    cs = np.linspace(0, w, n + 1).astype(int)
    lab = np.full(shape, -1, dtype=np.int16)
    k = 0
    for i in range(n):
        for j in range(n):
            blk = np.zeros(shape, dtype=bool)
            blk[rs[i]:rs[i + 1], cs[j]:cs[j + 1]] = True
            lab[blk & valid] = k
            k += 1
    return lab


def fold_of_components(cat: np.ndarray, valid: np.ndarray, n_folds: int = 4) -> np.ndarray:
    """Per-pixel fold id for catalogue pixels: whole components, majority block wins."""
    lab = block_ids(cat.shape, valid, n=n_folds)
    fid = np.where(lab >= 0, lab % n_folds, -1).astype(np.int16)
    comp, ncomp = ndimage.label(cat & valid, structure=np.ones((3, 3), dtype=bool))
    fold = np.full(cat.shape, -1, dtype=np.int16)
    if ncomp == 0:
        return fold
    ids = comp.ravel()
    f = fid.ravel()
    votes = np.zeros((ncomp + 1, n_folds), dtype=np.int64)
    ok = ids > 0
    np.add.at(votes, (ids[ok], f[ok]), 1)
    best = votes.argmax(axis=1).astype(np.int16)
    fold[comp > 0] = best[ids[ids > 0]]
    return fold, fid


def boundary(valid: np.ndarray, n_folds: int, buffer_px: int) -> np.ndarray:
    """Pixels within ``buffer_px`` of a fold boundary or of the footprint edge."""
    lab = block_ids(valid.shape, valid, n=n_folds)
    fid = np.where(lab >= 0, lab % n_folds, -1).astype(np.int16)
    border = np.zeros(valid.shape, dtype=bool)
    for dy, dx in ((0, 1), (1, 0), (-1, 0), (0, -1)):
        sh = np.roll(fid, (-dy, -dx), axis=(0, 1))
        border |= (sh != fid) & (sh >= 0) & (fid >= 0)
    border = ndimage.binary_dilation(border, iterations=buffer_px) & valid
    edge = ndimage.binary_dilation(~valid, iterations=buffer_px)
    return border | edge


def _thin_to_prevalence(held: np.ndarray, target_px: float, rng) -> np.ndarray:
    """Keep whole components of ``held`` (shuffled) until the target pixel count is reached."""
    comp, ncomp = ndimage.label(held, structure=np.ones((3, 3), dtype=bool))
    keep = np.zeros(held.shape, dtype=bool)
    if ncomp == 0:
        return keep
    ids = np.arange(1, ncomp + 1)
    sizes = np.bincount(comp.ravel(), minlength=ncomp + 1)[1:]
    order = rng.permutation(ids.size)
    tot = 0.0
    for k in order:
        if tot >= target_px:
            break
        keep |= comp == ids[k]
        tot += float(sizes[k])
    return keep


def tips_of(comp_mask: np.ndarray, frac: float = 0.3) -> np.ndarray:
    """The two along-strike ends of every trace in ``comp_mask``: the outer ``frac`` of each
    component's pixels by projection on its own principal axis.

    This is the object of the *truncation* instrument.  The competition's new-fault truth includes
    corrections and extensions of mapped traces (staff, thread 11516 post #4), and a mapped trace
    that stops because mapping stopped is the single most reliable place to find one.  Removing whole
    components cannot measure that at all - only 0.5 % of a hidden component's pixels lie within 5 px
    of a still-visible trace, because the neighbours of a trace belong to the same component - so a
    fold set built that way is structurally blind to near-trace mass and must not be used to judge it.
    """
    from scipy import ndimage
    lab, n = ndimage.label(comp_mask, structure=np.ones((3, 3), bool))
    out = np.zeros(comp_mask.shape, dtype=bool)
    if n == 0:
        return out
    ys, xs = np.nonzero(lab)
    ids = lab[ys, xs]
    order = np.argsort(ids, kind="stable")
    ys, xs, ids = ys[order], xs[order], ids[order]
    starts = np.searchsorted(ids, np.arange(1, n + 1))
    ends = np.append(starts[1:], ids.size)
    for k in range(n):
        a, b = starts[k], ends[k]
        if b - a < 3:
            continue
        yy = ys[a:b].astype(np.float64)
        xx = xs[a:b].astype(np.float64)
        u, s_, vt = np.linalg.svd(np.stack([yy - yy.mean(), xx - xx.mean()]), full_matrices=False)
        proj = (vt[0] * (yy - yy.mean()) + vt[1] * (xx - xx.mean()))
        lim = np.quantile(np.abs(proj), 1.0 - frac)
        keep = np.abs(proj) >= lim
        out[yy[keep].astype(int), xx[keep].astype(int)] = True
    return out


def make_folds(cat: np.ndarray, valid: np.ndarray, n_folds: int = 4, buffer_px: int = 4,
               prevalence: float = 0.002, seed: int = 0, mode: str = "hide",
               tip_frac: float = 0.3) -> list[dict]:
    """List of fold dicts with keys truth / visible / fit / region / boundary / n_truth.

    ``mode``: ``hide`` removes whole catalogue components; ``block`` additionally restricts fitting
    and scoring to a quadrant; ``tip`` removes only the along-strike ends of components, which is the
    instrument that can see near-trace mass (see :func:`tips_of`).
    """
    if mode not in ("hide", "block", "tip"):
        raise ValueError(mode)
    fold_of, fid = fold_of_components(cat, valid, n_folds)
    bnd = boundary(valid, n_folds, buffer_px)
    rng = np.random.default_rng(seed)
    target = prevalence * float(valid.sum())
    out = []
    for f in range(n_folds):
        held_cat = (fold_of == f) & valid                       # complete components of this fold
        if mode == "tip":
            held_cat = tips_of(cat & (fold_of == f) & valid, frac=tip_frac)
        # Prevalence-matched truth, whole components, identical rule in both instruments.
        truth = _thin_to_prevalence(held_cat, target, rng)
        visible = (cat & ~held_cat) & valid                     # what the model may still use
        # Region the model is allowed to emit in, and the area the model is fitted on.
        #   hide : labels removed for these components only; predictions scored grid-wide, so the
        #          model must recover a hidden trace from physics alone, with no help from the
        #          catalogue on either side of it.
        #   block: the model never sees the quadrant's own labels at fit time and is scored inside
        #          the quadrant, with a boundary buffer on both sides of the cut.
        region = valid if mode in ("hide", "tip") else (fid == f) & valid
        if mode == "hide":
            # the model must not be trained on *any* pixel of a hidden segment, or it is being shown
            # the trace it is then graded on recovering
            fit = valid & ~bnd & ~_grow(held_cat, buffer_px)
        elif mode == "tip":
            fit = valid & ~bnd & ~_grow(truth, buffer_px)
        else:
            fit = valid & (fid != f) & ~bnd
        out.append(dict(fold=f, mode=mode, truth=truth, visible=visible, fit=fit, region=region,
                        boundary=bnd, n_truth=int((truth & region).sum()),
                        n_held=int(held_cat.sum())))
    return out


def _grow(mask: np.ndarray, px: int) -> np.ndarray:
    return ndimage.binary_dilation(mask, iterations=px) if px > 0 else mask


def mask_visible(p: np.ndarray, visible_cat: np.ndarray) -> np.ndarray:
    """Delete predicted mass sitting exactly on the visible catalogue, as the organiser's mask does."""
    q = np.array(p, copy=True)
    q[visible_cat] = 0.0
    return q


def score(p: np.ndarray, fold: dict, valid: np.ndarray, restrict_to_region: bool = True,
          extra: bool = True) -> dict:
    """Official DTI of one emission on one fold."""
    pp = np.where(valid, p, 0.0)
    if restrict_to_region:
        pp = np.where(fold["region"], pp, 0.0)
    pp = mask_visible(pp, fold["visible"] & valid)
    r = M.dti(pp, fold["truth"] & fold["region"] & valid)
    r["emitted"] = int((pp > 0).sum())
    if extra:      # the two extras cost an EDT and a full-grid mask each; the hot sweep skips them
        r["in_region_emitted"] = int(((pp > 0) & fold["region"]).sum())
        r["recall_within_3px"] = recall_within(pp > 0, fold["truth"] & fold["region"] & valid, valid)
    return r


def recall_within(emitted: np.ndarray, truth: np.ndarray, valid: np.ndarray,
                  radius_px: float = 3.0) -> float:
    """Fraction of truth pixels with an emitted pixel within ``radius_px`` (the recovery read)."""
    t = truth & valid
    if not t.any():
        return float("nan")
    ed = ndimage.distance_transform_edt(~emitted)
    return float((ed[t] <= radius_px + 1e-9).mean())


def emit_topk(field: np.ndarray, allowed: np.ndarray, k: int) -> np.ndarray:
    """Binary emission of the k highest-valued allowed pixels.  {0,1} is not a simplification: at a
    fixed support the metric is linear in the mass and a single uncovered truth pixel gives
    ``DTI = k_lambda * lambda / (0.2 k_lambda lambda + 0.8)``, increasing in ``lambda``, so the
    optimum is ``lambda = 1`` (pinned in tests/test_metric.py)."""
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=0.0, posinf=0.0), -np.inf)
    n = f.size
    k = int(min(max(k, 0), n))
    out = np.zeros(n, dtype=np.float32)
    if k == 0:
        return out.reshape(field.shape)
    flat = f.ravel()
    cand = np.argpartition(-flat, k - 1)[:k]
    cand = cand[flat[cand] > -np.inf]
    out[cand] = 1.0
    return out.reshape(field.shape)


def arm_scores(prefs: dict, fold: dict, valid: np.ndarray, budgets=(8000, 15000, 25000, 37654),
               dti_projected: float = 0.28, emit: str = "topk", as_is: tuple[str, ...] = ()) -> dict:
    """Score every arm of every round on one fold, at every budget.

    ``prefs`` maps arm-key -> float32 grid of that arm's *field* (already combined, unmasked).  The
    visible catalogue is deleted from the allowed set *and* from the score, exactly as the organiser
    does, so an arm cannot win by rediscovering a known trace.
    """
    allowed0 = valid & ~fold["visible"] & fold["region"]
    res = {}
    for mode, field in prefs.items():
        if mode in as_is:
            # a previously submitted raster is scored as it stands: cutting it to a budget would
            # compare an arbitrary tie-broken subset of it against our whole emission
            em = (np.nan_to_num(np.asarray(field, dtype=np.float32), nan=0.0) > 0).astype(np.float32)
            sc = score(em, fold, valid, extra=False)
            res[f"{mode}|full"] = {k: (round(v, 5) if isinstance(v, float) else v)
                                   for k, v in sc.items()}
            continue
        for b in budgets:
            if emit == "topk":
                em = emit_topk(field, allowed0, b)
                st = {"emitted": int((em > 0).sum())}
            else:
                em, st = emission_from_field(field, allowed0, dti_projected, b,
                                             calibrate_to=None, log=lambda *a: None)
            sc = score(em, fold, valid, extra=False)
            sc["emit"] = emit
            sc["arm"] = mode
            sc["budget"] = int(b)
            sc.update({k2: v for k2, v in st.items() if k2 == "rejects_at_stop"})
            res[f"{mode}|{b}"] = {k2: (round(v, 5) if isinstance(v, float) else v)
                                  for k2, v in sc.items()}
    return res


def emission_from_field(field: np.ndarray, allowed: np.ndarray, dti_projected: float,
                        budget: int, calibrate_to: float | None = None,
                        pool: int = 400_000, log=lambda *a: None) -> tuple[np.ndarray, dict]:
    """Rank field -> emission: calibrate the density, then greedy-cover it under the metric's rule.

    ``calibrate_to`` renormalises the field so that its total mass equals the |G| estimate.  That
    single choice is what makes the greedy gains commensurable with the credit bar: without it
    "gain > bar" is a comparison between a number in units of expected truth pixels and a number in
    units of DTI credit, i.e. meaningless.
    """
    # A density must be non-negative: the locally-centred field is signed by construction (it is a
    # contrast against a regional mean), so negatives are "below background", i.e. no expected mass.
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=0.0, posinf=0.0), 0.0).astype(np.float32)
    f = np.maximum(f, 0.0)
    tot = float(f.sum())
    if tot <= 0:
        return np.zeros_like(f, dtype=np.float32), {"emitted": 0, "reason": "empty field"}
    dens = f * (calibrate_to / tot) if calibrate_to else f
    em, st = E.greedy_emit(dens.ravel(), allowed, dti_projected, budget, pool=pool, log=log)
    st["field_sum"] = tot
    st["calibrated_to"] = float(calibrate_to) if calibrate_to else None
    return em, st
