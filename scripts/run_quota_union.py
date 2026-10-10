#!/usr/bin/env python3
"""E4 — combination rule: does a *quota union* of channels beat a rank-mean or the best single channel?

A rank-mean fusion of channels asks a cell to be high in *every* channel, which is the right rule when
the channels are noisy views of the same object and the wrong rule when they are partial views of
different objects. A fault set is the latter: a magnetic lineament with no scarp (buried under valley
fill) and a scarp with no magnetic contrast (a normal fault in unconsolidated section) are both real,
and a mean rank demotes both to mediocrity.

The metric says the same thing structurally: TPw is a **max over emitted pixels per truth pixel**, so
two channels that reach *different* truth pixels add credit, while two channels that reach the same
truth pixel add nothing. The right combinator for a max objective is therefore a **union with a quota
per channel**, not an average, and the quota is where budget goes.

Arms (all at the same total emitted count, all on the same folds):
  each channel |topk           the single-channel control, reproduced here so the comparison is same-run
  MEAN|topk                    equal-weight rank mean (the conventional fusion)
  QUOTA|topk                   per-channel quota = total / n_channels, unioned
  QUOTA|packed                the union, then exact greedy packing at --nms px on the consensus rank
  QUOTA|packed|weighted       quota per channel proportional to that channel's pooled DTI measured in
                              E1 (``evidence/field_holdout_v1.json``), read from the file, not re-fitted

Decision rule, fixed before running: the arm with the highest pooled HOLDOUT-DTI at the shipping budget
is emitted. Ties broken by the lower emitted count.

Reproduce: python scripts/run_quota_union.py            (~4 min)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems56 import evaluate_holdout as EH, grid as G, holdout as H, metric as M  # noqa: E402
from emit_and_score import greedy_pack  # noqa: E402  (same packer the shipped file uses)
from run_field_holdout import dti_from, fast_terms  # noqa: E402  (cross-checked accelerator)

FIELDS = ROOT / "data" / "interim" / "fields"
CH = ["mag_ridge", "scarp_slope", "rtp_ridge", "strain_2ndinv_ridge", "grav_ridge", "cond_edge"]
BUDGET, SHADOW, NMS = 37654, 2, 2.8
N_FOLDS, BUFFER_PX, PREVALENCE, SEED = 4, 4, 0.002, 5610


def ranks(names) -> dict:
    return {n: (np.load(FIELDS / f"{n}.npy").astype(np.float32) / 65535.0) for n in names}


def main() -> int:
    t0 = time.time()
    ev = json.loads((ROOT / "evidence" / "field_holdout_v1.json").read_text())
    e1 = {n: v["dti"] for n, v in ev["instruments"]["hide"]["pooled"]["scores"].items() if n in CH}
    w = np.array([max(0.0, e1[n]) for n in CH], dtype=np.float64)
    w = w / w.sum()
    fp = np.load(FIELDS / "_footprint.npy")
    cat = np.load(FIELDS / "_cat.npy") & fp
    folds = H.make_folds(cat, fp, n_folds=N_FOLDS, buffer_px=BUFFER_PX, prevalence=PREVALENCE,
                         seed=SEED, mode="hide")
    terms: dict[str, list] = {}
    diag: dict[str, dict] = {}
    for fi, fold in enumerate(folds):
        vis = fold["visible"] & fp
        allowed = fp & ~vis & fold["region"] & ~ndimage.binary_dilation(vis, iterations=SHADOW)
        truth = fold["truth"] & fold["region"] & fp
        dgt = ndimage.distance_transform_edt(~truth, sampling=M.PIXEL_M)
        r = ranks(CH)
        arms: dict[str, np.ndarray] = {f"{n}|topk": H.emit_topk(r[n], allowed, BUDGET) for n in CH}
        mean = np.mean([r[n] for n in CH], axis=0).astype(np.float32)
        arms["MEAN|topk"] = H.emit_topk(mean, allowed, BUDGET)
        cons = np.max([r[n] for n in CH], axis=0).astype(np.float32)     # best rank any channel gives
        q = BUDGET // len(CH)
        uni = np.zeros(fp.shape, bool)
        for n in CH:
            uni |= H.emit_topk(r[n], allowed, q) > 0
        arms["QUOTA|topk"] = uni.astype(np.float32)
        packed, _ = greedy_pack(cons, allowed & uni, NMS, BUDGET)
        arms["QUOTA|packed"] = packed
        qw = np.ceil(w * BUDGET).astype(int)
        uni2 = np.zeros(fp.shape, bool)
        for n, qq in zip(CH, qw):
            uni2 |= H.emit_topk(r[n], allowed, int(qq)) > 0
        packed2, st2 = greedy_pack(cons, allowed & uni2, NMS, BUDGET)
        arms["QUOTA|packed|weighted"] = packed2
        # the same packing applied to a single channel, to separate "union" from "packing"
        pk0, _ = greedy_pack(r[CH[0]], allowed, NMS, BUDGET)
        arms[f"{CH[0]}|packed"] = pk0
        for name, em in arms.items():
            if not isinstance(em, np.ndarray):
                continue
            tt, tp, fpm, ng, rec = fast_terms(np.asarray(em) > 0, truth, dgt, fp.shape)
            terms.setdefault(name, []).append(tt)
            if fi == 0:
                diag[name] = dict(emitted=int((np.asarray(em) > 0).sum()), tpw0=round(tp, 1),
                                  fpw0=round(fpm, 1), recall3=round(float(rec), 4))
        del r, dgt, truth
    pooled = {k: np.sum(np.stack(v), axis=0) for k, v in terms.items()}
    summ = EH.pooled_summary(pooled, candidate=f"{CH[0]}|topk")
    table = {k: {**v, **diag.get(k, {})} for k, v in summ["scores"].items()}
    ranked = sorted(table, key=lambda k: -table[k]["dti"])
    out = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ"), channels=CH,
               e1_pooled_dti=e1, weighted_quotas={n: int(q) for n, q in zip(CH, qw)},
               budget=BUDGET, nms_px=NMS, shadow_px=SHADOW, decision_rule="highest pooled hide DTI",
               ranking={k: table[k]["dti"] for k in ranked}, table=table, pooled=summ,
               best_arm=ranked[0],
               interpretation=dict(
                   union_vs_mean=dict(union=table["QUOTA|packed"]["dti"], mean=table["MEAN|topk"]["dti"],
                                      best_single=max(table[f"{n}|topk"]["dti"] for n in CH)),
                   note=("if the union beats the best single channel the channels are complementary "
                         "under the max objective; if the mean loses to the best single, averaging was "
                         "the wrong combinator")),
               seconds=round(time.time() - t0, 1))
    (ROOT / "evidence" / "quota_union_v1.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out["ranking"], indent=1, default=float))
    print(json.dumps(out["interpretation"], indent=1, default=float))
    print(json.dumps({k: {kk: table[k][kk] for kk in ("dti", "emitted", "tpw0", "recall3")} for k in ranked},
                     indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
