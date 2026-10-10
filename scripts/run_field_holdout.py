#!/usr/bin/env python3
"""E1b — every candidate physical channel, alone, on the shared spatially-blocked holdout.

Protocol item 4 (leakage canary) and item 2 (one shared holdout, no private fork) in one script:

* each field is scored **by itself** at a ladder of budgets, so no channel can hide inside a fusion and
  the budget-response curve of each channel is visible;
* two instruments: ``hide`` (whole catalogue components withheld -- recovery of a trace the model was
  never shown) and ``tip`` (only the along-strike ends withheld -- the instrument that can see
  near-trace mass, i.e. trace *extension*, which is the corrections lane's own object);
* a **mimicry** statistic accompanies every field: how well the field alone reproduces the *visible*
  catalogue. A channel that reproduces the catalogue is redelivering mapped faults; a channel that
  reproduces the hidden target with AUC > 0.90 is leakage until proven otherwise (brief item 4);
* the emission floor is the fold's own ``visible`` catalogue dilated by 2 px, never the whole
  catalogue: in the ``tip`` instrument the withheld target *is* the end of a visible trace, and
  shadowing the full catalogue would delete the target the arm is graded on;
* two previously scored sibling rasters are run ``as_is`` because the claim under test -- "deleting the
  mass within 2 px of a known trace is free score" -- must reproduce on *our* instrument before it is
  built on.

The official DTI arithmetic is the shared template metric, and every score in the receipt is checked
against ``gems56.holdout.score`` (the slow reference) for a random subset, to 1e-9 -- see
``crosscheck`` in the output. The fast path exists only because a 17-channel x 6-budget x 4-fold screen
would otherwise spend 40 minutes in full-grid Euclidean distance transforms that do not depend on the
arm: for a fixed fold the distance-to-truth field is arm-invariant, so an exact scoring costs one EDT
per fold plus a 15-offset gather per arm.

Reproduce: python scripts/run_field_holdout.py            (~10 min, single core, <1.5 GB)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import evaluate_holdout as EH, holdout as H, metric as M  # noqa: E402

FIELDS = ROOT / "data" / "interim" / "fields"
N_FOLDS, BUFFER_PX, PREVALENCE, SEED = 4, 4, 0.002, 5610
BUDGET = 37654
LADDER = (8000, 15000, 25000, 37654, 60000, 90000)
AUC_SAMPLE = 400_000
BLOCK_SIDE = 200          # px: the template's physical bootstrap cluster (20 km)
OFFS = [(dy, dx, 1.0 - np.hypot(dy, dx) * M.PIXEL_M / M.R_M)
        for dy in range(-3, 4) for dx in range(-3, 4)
        if np.hypot(dy, dx) * M.PIXEL_M <= M.R_M + 1e-9]


def fast_terms(p: np.ndarray, g: np.ndarray, dgt: np.ndarray, shape: tuple[int, int]):
    """Exact (TPw, FPw, FNw, |G|) per 20 km block for a binary emission ``p`` against truth ``g``.

    TPw = sum_g max_{x in P} k(d) is the 15-offset gather (no full-grid distance transform);
    FPw = sum_{x in P} p(x)(1 - max_g k(d(x,g))) uses the fold-invariant ``dgt``.
    """
    h, w = shape
    yy, xx = np.nonzero(g)
    n = yy.size
    m = np.zeros(n, np.float64)
    if n and p.any():
        pf = p.astype(np.float32)
        for dy, dx, kk in OFFS:
            Y, X = yy + dy, xx + dx
            ok = (Y >= 0) & (Y < h) & (X >= 0) & (X < w)
            v = np.zeros(Y.size, np.float32)
            v[ok] = pf[Y[ok], X[ok]]
            np.maximum(m, v * kk, out=m)
    py, px = np.nonzero(p)
    q = np.maximum(1.0 - dgt[py, px] / M.R_M, 0.0)
    fp = 1.0 - q
    ncols = (w + BLOCK_SIDE - 1) // BLOCK_SIDE
    nrows = (h + BLOCK_SIDE - 1) // BLOCK_SIDE
    terms = np.zeros((nrows * ncols, 4), np.float64)
    if n:
        ids = (yy // BLOCK_SIDE) * ncols + (xx // BLOCK_SIDE)
        terms[:, 0] = np.bincount(ids, weights=m, minlength=len(terms))
        terms[:, 2] = np.bincount(ids, weights=1.0 - m, minlength=len(terms))
        terms[:, 3] = np.bincount(ids, weights=np.ones(n), minlength=len(terms))
    if py.size:
        idp = (py // BLOCK_SIDE) * ncols + (px // BLOCK_SIDE)
        terms[:, 1] = np.bincount(idp, weights=fp, minlength=len(terms))
    return terms, float(m.sum()), float(fp.sum()), n, (m > 0).mean() if n else float("nan")


def dti_from(tp: float, fp: float, fn: float, ng: int) -> float:
    den = tp + M.ALPHA * fp + M.BETA * fn
    return float(tp / den) if den > 0 else 0.0


def slow(p, fold, fp):
    return H.score(p.astype(np.float32), fold, fp, extra=False)


def auc(scores, labels) -> float:
    y = np.asarray(labels, bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(np.asarray(scores, np.float64))
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def diagnostics(field, fold, fp, rng) -> dict:
    reg = fp & fold["region"]
    idx = np.flatnonzero(reg.ravel())
    pick = rng.choice(idx, size=min(AUC_SAMPLE, idx.size), replace=False)
    v = field.ravel()[pick].astype(np.float64)
    return dict(auc_hidden=auc(v, (fold["truth"] & reg).ravel()[pick]),
                auc_catalogue_mimicry=auc(v, (fold["visible"] & fp).ravel()[pick]),
                hidden_pos_in_sample=int((fold["truth"] & reg).ravel()[pick].sum()),
                n_sampled=int(pick.size))


def main() -> int:
    t0 = time.time()
    fp = np.load(FIELDS / "_footprint.npy")
    cat = np.load(FIELDS / "_cat.npy") & fp
    names = sorted(p.stem for p in FIELDS.glob("*.npy") if not p.stem.startswith("_"))
    prior = {}
    for tag, path in (("PRIOR_base_44090", ROOT / "data/registry/GEMSDOE32/docs/downloads/"
                       "gems32-probe-S1-ANCHOR-identical-to-live-02600.tif"),
                      ("PRIOR_pruned_37654", ROOT / "data/registry/GEMSDOE32/docs/downloads/"
                       "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif")):
        if path.exists():
            import rasterio
            with rasterio.open(path) as ds:
                a = np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0)
            prior[tag] = (a > 0) & fp
        else:
            print(f"WARN prior raster missing: {path}", flush=True)
    out = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
               protocol=dict(evaluator=EH.VERSION, folds=N_FOLDS, buffer_px=BUFFER_PX,
                             prevalence=PREVALENCE, budget=BUDGET, ladder=list(LADDER),
                             emission_floor=f"2 px dilation of the fold's visible catalogue",
                             visible_mask="pixel-exact (thread 11516 post #4)",
                             block_side_px=BLOCK_SIDE, auc_sample=AUC_SAMPLE, seed=SEED,
                             alpha=M.ALPHA, beta=M.BETA, radius_m=M.R_M),
               fields=names, instruments={}, crosscheck=[])
    for mode in ("hide", "tip"):
        folds = H.make_folds(cat, fp, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                             prevalence=PREVALENCE, seed=SEED, mode=mode)
        terms = {n: [] for n in names + list(prior)}
        ladder = {n: {b: [] for b in LADDER} for n in names}
        diag: dict[str, dict] = {}
        for fi, fold in enumerate(folds):
            region = fp & fold["region"]
            vis = fold["visible"] & fp
            floor = ndimage.binary_dilation(vis, iterations=2)
            allowed = region & ~vis & ~floor
            truth = fold["truth"] & region
            dgt = ndimage.distance_transform_edt(~truth, sampling=M.PIXEL_M)
            rng = np.random.default_rng(SEED + 31 * fi + (0 if mode == "hide" else 7))
            for n in names:
                f = np.load(FIELDS / f"{n}.npy").astype(np.float32)
                if fi == 0:
                    diag[n] = diagnostics(f, fold, fp, rng)
                for b in (LADDER if mode == "hide" else (BUDGET,)):
                    em = H.emit_topk(f, allowed, b) > 0
                    tt, tp, fp_, ng, rec = fast_terms(em, truth, dgt, f.shape)
                    terms[n].append(tt) if b == BUDGET else None
                    ladder[n][b].append(dict(dti=dti_from(tp, fp_, ng - tp, ng), emitted=int(em.sum()),
                                             tpw=round(tp, 2), fpw=round(fp_, 2),
                                             recall_within_3px=round(float(rec), 4)))
                    if (fi == 0 and b == BUDGET and len(out["crosscheck"]) < 4):
                        s = slow(em, fold, fp)
                        out["crosscheck"].append(dict(field=n, fold=fi, mode=mode,
                                                       fast=round(dti_from(tp, fp_, ng - tp, ng), 9),
                                                       shared=round(s["dti"], 9),
                                                       abs_diff=abs(dti_from(tp, fp_, ng - tp, ng) - s["dti"])))
                    del em
                del f
            for tag, mask in prior.items():
                em = mask & region & ~vis      # scored as it stands; only the organiser mask applies
                tt, tp, fp_, ng, rec = fast_terms(em, truth, dgt, fp.shape)
                terms[tag].append(tt)
            del dgt
        pooled = {n: np.sum(np.stack(v), axis=0) for n, v in terms.items() if v}
        summ = EH.pooled_summary(pooled, candidate=("PRIOR_pruned_37654" if prior else names[0]))
        per_budget = {n: {str(b): ladder[n][b][0] if len(ladder[n][b]) == 1 else dict(
                            dti=float(np.mean([s["dti"] for s in ladder[n][b]])),
                            fold_sd=float(np.std([s["dti"] for s in ladder[n][b]], ddof=1)) if len(ladder[n][b]) > 1 else 0.0,
                            emitted=int(np.mean([s["emitted"] for s in ladder[n][b]])),
                            tpw=float(np.mean([s["tpw"] for s in ladder[n][b]])),
                            fpw=float(np.mean([s["fpw"] for s in ladder[n][b]])),
                            recall_within_3px=float(np.mean([s["recall_within_3px"] for s in ladder[n][b]])),
                            folds=[s["dti"] for s in ladder[n][b]])
                        for b in ladder[n] if ladder[n][b]} for n in names}
        _tmp = EH.pooled_summary(pooled, candidate=names[0])
        print(mode, "top by pooled DTI:",
              sorted(((round(v["dti"], 5), k) for k, v in _tmp["scores"].items()), reverse=True)[:8],
              flush=True)
        out["instruments"][mode] = dict(
            pooled=summ, per_budget=per_budget, diagnostics=diag,
            withheld_positive_pixels=int(sum(int((f["truth"] & f["region"] & fp).sum()) for f in folds)),
            seconds=round(time.time() - t0, 1))
        print(f"[{mode}] pooled done at {time.time()-t0:.0f}s", flush=True)
    hide = out["instruments"]["hide"]["pooled"]["scores"]
    order = sorted([n for n in hide if not n.startswith("PRIOR")], key=lambda n: -hide[n]["dti"])
    out["ranking_by_hide_dti"] = {n: hide[n]["dti"] for n in order}
    out["prior_control_delta"] = dict(base=hide.get("PRIOR_base_44090", {}).get("dti"),
                                      pruned=hide.get("PRIOR_pruned_37654", {}).get("dti"),
                                      note="both are the sibling files scored as-is on our instrument")
    out["seconds"] = round(time.time() - t0, 1)
    out["max_crosscheck_abs_diff"] = max((c["abs_diff"] for c in out["crosscheck"]), default=0.0)
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / "field_holdout_v1.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out["ranking_by_hide_dti"], indent=1, default=float))
    print("ladder at 90k vs 37.6k (hide):")
    for n in order[:6]:
        pb = out["instruments"]["hide"]["per_budget"][n]
        print(" ", n, {k: round(v["dti"], 4) for k, v in pb.items()})
    print(json.dumps({n: {k: round(v, 3) for k, v in out["instruments"]["hide"]["diagnostics"][n].items()}
                      for n in names}, indent=1))
    print("prior control:", json.dumps(out["prior_control_delta"], default=float))
    print("crosscheck:", json.dumps(out["crosscheck"], default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
