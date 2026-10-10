#!/usr/bin/env python3
"""E1 -- validate the round-2 hypotheses (H6/H7/H8) on the shared spatially-blocked holdout.

Pre-registration lives in ``docs/research/hypotheses-20261009.md`` (fixed before this script was
run). Summary of the contract, restated so the receipt is self-contained:

* instrument  : gems56.evaluate_holdout ``gems52-pooled-hide-v1`` -- no private metric fork;
                whole-component withholding, visible catalogue masked pixel-exactly,
                paired spatial-block bootstrap (1,000 draws, seed 520810).
* folds       : make_folds(mode="hide", n_folds=4, buffer_px=4, prevalence=0.00294, seed=0)
                -- identical parameters to scripts/run_corrections_holdout.py.
* emission    : one rule for holdout AND shipped file: top-k of the arm's ranked field inside
                ``footprint & region & ~dilate(known catalogue, 2 px)``, value 1.0,
                budgets k in {8000, 15000, 25000, 37654}.  The 2 px exclusion of known traces
                is the verified 0.2778 mechanism (GEMSDOE54 RUN2-SUMMARY: parent 40,199 dots
                minus 2,545 dots within 200 m of catalogue = child 37,654 dots, 0.2708 ->
                0.2778) combined with this repo's own <=2 px correction result.
* arms        : iso_step (H6), bc_step (H7), tilt_r (H8), multi (mean of the three ranked),
                mag_ref (hessian_line(tmi_hg), reference only: occupied family),
                random (seeded uniform -- the chance floor).
* canary      : per-single-field ROC-AUC vs pooled withheld truth; > 0.90 = leakage.
* pick rule   : among {iso_step, bc_step, tilt_r, multi} @ 25,000 take highest pooled DTI.
                PASS iff paired 95% CI vs random@25000 strictly > 0, no new-field canary
                > 0.90, and every new arm stays above the previous repo best 0.00021.
* budget      : E1 only; E2 (build) and E3 (uniqueness) are separate scripts.

Receipt: evidence/holdout_discovery_v1.json
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
from gems56 import evaluate_holdout as EH          # noqa: E402
from gems56 import gates, holdout as H, lane_inputs as L, metric as M  # noqa: E402
from gems56 import corrections as C, transform as T                    # noqa: E402

BUDGETS = (8000, 15000, 25000, 37654)
PRIMARY_BUDGET = 25000
NEW_ARMS = ("iso_step", "bc_step", "tilt_r", "multi")
PREV_BEST_DTI = 0.00020550105762550465     # D_jitter, evidence/holdout_corrections_v1.json
CANARY_LIMIT = 0.90
BUFFER_PX, N_FOLDS = 4, 4
EXTRA_BANDS = {"iso_grav_anom": 13, "depth_to_base_surf": 15, "cond_surf": 17, "tc": 6}


def read_extra_bands(path: Path) -> dict[str, np.ndarray]:
    """Sentinel-safe, description-asserted reads of the bands corrections.load_fields does not load."""
    import rasterio
    out = {}
    with rasterio.open(str(path)) as src:
        desc = {i: (src.descriptions[i - 1] or "") for i in range(1, src.count + 1)}
        for name, band in EXTRA_BANDS.items():
            assert desc[band].split(" ")[0] == name, f"band {band} is {desc[band]!r}, not {name!r}"
            a = src.read(band).astype(np.float64)
            a[~np.isfinite(a) | (a < C.NODATA_LIMIT)] = np.nan
            out[name] = a.astype(np.float32)
    return out


def auc(scores: np.ndarray, labels: np.ndarray, valid: np.ndarray) -> float:
    """Mann-Whitney ROC-AUC of a fold-independent field against pooled withheld truth.

    Cells where the field is NaN (edge-masked by the IR-56-020 fix) are excluded -- they are
    neither a positive nor a negative prediction, they are "no opinion".
    """
    ok = np.asarray(valid, bool) & np.isfinite(scores)
    s = np.asarray(scores, np.float64)[ok]
    y = np.asarray(labels, bool)[ok]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def build_fields(fields: dict, extra: dict, fp: np.ndarray) -> tuple[dict, dict]:
    """Pre-registered field recipe.  Returns (ranked fields for topk, raw fields for the canary)."""
    t0 = time.time()
    iso_raw = T.scarp_step(extra["iso_grav_anom"], fp, half_width_m=150.0, persist_m=2000.0)[0]
    bas_raw = T.scarp_step(extra["depth_to_base_surf"], fp, half_width_m=150.0, persist_m=2000.0)[0]
    con_raw = T.scarp_step(extra["cond_surf"], fp, half_width_m=150.0, persist_m=2000.0)[0]
    tilt_raw = -T.box_mean(extra["tc"], fp, radius_m=100.0)
    mag_raw = T.hessian_line(fields["tmi_hg"], fp, sigma_m=300.0)

    iso_r = T.rank01(iso_raw, fp)
    bas_r = T.rank01(bas_raw, fp)
    con_r = T.rank01(con_raw, fp)
    bc_r = np.minimum(bas_r, con_r)                     # concordance = intersection of ranks
    tilt_r = T.rank01(tilt_raw, fp)
    mag_r = T.rank01(mag_raw, fp)
    multi_r = ((iso_r + bc_r + tilt_r) / 3.0).astype(np.float32)
    ranked = dict(iso_step=iso_r, bc_step=bc_r, tilt_r=tilt_r, multi=multi_r, mag_ref=mag_r)
    raw = dict(iso_step=iso_raw, basement=bas_raw, cond=con_raw, tilt=tilt_raw, mag_ref=mag_raw)
    print(f"fields built in {time.time() - t0:.1f}s", flush=True)
    return ranked, raw


def main() -> None:
    t0 = time.time()
    fields, cat, fp, meta = L.load(sample=True)
    extra = read_extra_bands(L.path("features"))
    ranked, raw = build_fields(fields, extra, fp)
    rng = np.random.default_rng(560202)
    ranked["random"] = rng.random(cat.shape, dtype=np.float32)

    folds = H.make_folds(cat, fp, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                         prevalence=0.00294, seed=0, mode="hide")
    disk2 = gates._disk(2.0)
    arms = list(ranked)
    terms: dict[str, list] = {f"{a}@{k}": [] for a in arms for k in BUDGETS}
    per_fold, n_truth_total = [], 0

    for fold in folds:
        vis = fold["visible"] & fp
        near_vis = ndimage.binary_dilation(vis, structure=disk2)
        allowed = fp & fold["region"] & ~near_vis
        for arm in arms:
            field = ranked[arm]
            for k in BUDGETS:
                p = H.emit_topk(field, allowed, k)
                res, tm = EH.evaluate(p, fold, fp)
                terms[f"{arm}@{k}"].append(tm)
                per_fold.append(dict(fold=fold["fold"], arm=arm, budget=int(k),
                                     dti=round(float(res["dti"]), 6),
                                     emitted=res["emitted"], n_truth=res["n_truth"]))
        n_truth_total += fold["n_truth"]
        print(f"fold {fold['fold']}: truth {fold['n_truth']} done "
              f"({time.time() - t0:.0f}s)", flush=True)

    # ---- leakage canary: every single raw field alone, pooled withheld truth ---------------
    pooled_truth = np.zeros(cat.shape, bool)
    for fold in folds:
        pooled_truth |= fold["truth"] & fold["region"] & fp
    canary = {name: round(auc(a, pooled_truth, fp), 4) for name, a in raw.items()}

    pooled = EH.pooled_summary({k: np.sum(np.stack(v), axis=0) for k, v in terms.items()},
                               candidate=f"{NEW_ARMS[0]}@{PRIMARY_BUDGET}")
    scores = pooled["scores"]

    # ---- pre-registered pick rule ---------------------------------------------------------
    new_at_primary = {f"{a}@{PRIMARY_BUDGET}": scores[f"{a}@{PRIMARY_BUDGET}"]["dti"]
                      for a in NEW_ARMS}
    candidate = max(new_at_primary, key=new_at_primary.get)
    pooled = EH.pooled_summary({k: np.sum(np.stack(v), axis=0) for k, v in terms.items()},
                               candidate=candidate)
    scores = pooled["scores"]
    vs_chance = pooled["paired_differences"].get(f"random@{PRIMARY_BUDGET}")
    canary_max_new = max((v for k, v in canary.items() if k != "mag_ref" and np.isfinite(v)),
                         default=float("nan"))
    ci_above_zero = bool(vs_chance and vs_chance["ci95"][0] > 0)
    # faithful to the pre-registered text: EVERY new arm (not just the pick) must stay above the
    # previous repo best at the primary budget -- tilt_r's near-zero scores fail this bar.
    above_prev_best = bool(all(dt > PREV_BEST_DTI for dt in new_at_primary.values()))
    canary_ok = bool(np.isfinite(canary_max_new) and canary_max_new <= CANARY_LIMIT)
    verdict_pass = bool(ci_above_zero and canary_ok and above_prev_best)

    out = {
        "evidence_class": "HOLDOUT-DTI (catalogue recovery, hide-and-recover; NOT new-fault discovery)",
        "evaluator": {"version": EH.VERSION, "sha256": EH.implementation_hashes(),
                      "alpha": M.ALPHA, "beta": M.BETA, "radius_m": M.R_M},
        "design": dict(folds=N_FOLDS, mode="hide", buffer_px=BUFFER_PX,
                       prevalence=0.00294, seed=0,
                       emission="top-k of ranked field in footprint & region & "
                                "~dilate(visible catalogue, 2 px), value 1.0",
                       budgets=list(BUDGETS), primary_budget=PRIMARY_BUDGET,
                       arms={a: d for a, d in [
                           ("iso_step", "H6: rank01(scarp_step iso_grav_anom, 150 m, 2 km)"),
                           ("bc_step", "H7: min(rank01 step(basement), rank01 step(conductivity))"),
                           ("tilt_r", "H8: rank01(-box_mean(tc, 100 m))"),
                           ("multi", "mean(iso_step, bc_step, tilt_r) ranks"),
                           ("mag_ref", "reference only: rank01(hessian_line(tmi_hg, 300 m))"),
                           ("random", "seeded uniform chance floor (rng 560202)")]}),
        "bars": dict(previous_repo_best_dti=PREV_BEST_DTI,
                     previous_arm="D_jitter (evidence/holdout_corrections_v1.json)",
                     sibling_prior_pooled="GEMSDOE54 RUN2-SUMMARY, their evaluator: chance 0.0104, "
                                          "mag-hgrad 0.0148, basement-step 0.0097 (priors, not scores)"),
        "canary": canary,
        "canary_rule": "AUC > 0.90 means leakage until proven otherwise",
        "canary_max_new_fields": canary_max_new,
        "withheld_positives_total": n_truth_total,
        "pick_rule": dict(candidate=candidate,
                          new_arms_at_primary=new_at_primary,
                          paired_vs_random=vs_chance,
                          ci_strictly_above_zero=ci_above_zero,
                          canary_ok=canary_ok,
                          every_new_arm_above_previous_best=above_prev_best),
        "verdict_pass": verdict_pass,
        "pooled": pooled,
        "per_fold": per_fold,
        "footprint_cells": int(fp.sum()),
        "elapsed_s": round(time.time() - t0, 1),
        "limitations": [
            "target = withheld catalogue components, not the organizer's new-fault set (IR-56-004)",
            "budgets and arms are conditional; the CI is not a leaderboard interval",
            "mag_ref is an occupied family and is never eligible for the shipped file",
        ],
    }
    path = ROOT / "evidence" / "holdout_discovery_v1.json"
    path.write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("canary", "verdict_pass", "pick_rule", "withheld_positives_total",
                       "elapsed_s")}, indent=1, default=float)[:3000])
    print(f"\npooled (candidate={candidate}):")
    for name in sorted(scores, key=lambda n: -scores[n]["dti"]):
        s = scores[name]
        print(f"  {name:24s} {s['dti']:.5f}  ci=[{s['ci95'][0]:.5f}, {s['ci95'][1]:.5f}]")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
