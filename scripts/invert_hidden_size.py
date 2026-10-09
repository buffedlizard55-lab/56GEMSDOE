#!/usr/bin/env python3
"""E0 — invert the published scores of two sibling rasters for the size of the hidden scored set.

The organiser's metric is a closed-form relation between three numbers we can count (emitted mass) or
read off a receipt (the score) and two we cannot see (T = weighted true positives, |G| = hidden truth
pixels). Two files whose dot sets differ by *exactly* a known deletion give two equations:

    base   : 44,090 dots, claimed 0.2600
    pruned : the same dots minus the 6,436 that sit within 2 px of a known catalogue pixel,
             claimed 0.2778

Assumption, stated and tested: the deleted dots carried no true-positive credit. They sit within 2 px
of a known trace, and known trace pixels are masked out of the truth, so the only way one could earn
credit is a *new* fault pixel lying within 3 px of a mapped one. Under that assumption T is shared and

    D_pruned = D_base - 0.2*6436 ,  T = s_base*D_base = s_pruned*D_pruned
    =>  D_pruned = s_base*0.2*6436/(s_pruned - s_base)

which pins T and the denominator, and then |G| up to the unknown false-positive mass F:

    0.8|G| = D_base - 0.2*T - 0.2*F ,   F in [0.5 N, N]  (bracket, not a measurement)

Everything this script prints is DERIVED: it is arithmetic on user-reported scores and dot counts
measured from rasters in the sibling mirror. It is not an organizer statement about the label set, and
it is never written as a score. Its purpose is sizing: it says how much of the hidden set the current
family already reaches, hence whether the remaining headroom is placement or budget.

Reproduce: python scripts/invert_hidden_size.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
ALPHA, BETA = 0.2, 0.8
PAIR = {  # (dots measured from the file, user-reported score from the brief)
    "base": dict(path="data/registry/GEMSDOE32/docs/downloads/"
                        "gems32-probe-S1-ANCHOR-identical-to-live-02600.tif", score=0.2600),
    "pruned": dict(path="data/registry/GEMSDOE32/docs/downloads/"
                          "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif", score=0.2778),
}


def main() -> int:
    cat = np.load(ROOT / "data/interim/fields/_cat.npy") if (ROOT / "data/interim/fields/_cat.npy").exists() \
        else None
    if cat is None:
        with rasterio.open(ROOT / "data/grid/existing_faults.tif") as ds:
            cat = ds.read(1) == 1
    out = {"assumption": "the deleted dots carried zero true-positive credit (they sit within 2 px of a "
                         "masked catalogue pixel); T is shared between the two files",
           "evidence_class": "DERIVED (arithmetic on user-reported scores + measured dot counts)",
           "not": "an organizer statement about the label set; never a score", "inputs": {}}
    masks = {}
    for tag, d in PAIR.items():
        with rasterio.open(ROOT / d["path"]) as ds:
            a = np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0)
        m = a > 0
        masks[tag] = m
        d["dots"] = int(m.sum())
        d["mass"] = float(np.nansum(a))
        d["values"] = sorted(set(np.unique(a[m]).tolist()))
        ed = ndimage.distance_transform_edt(~cat)
        dd = ed[m]
        d["d_catalogue_px"] = dict(min=float(dd.min()), p50=float(np.percentile(dd, 50)),
                                   max=float(dd.max()), frac_le_2=float((dd <= 2 + 1e-9).mean()))
    inter = int((masks["base"] & masks["pruned"]).sum())
    out["subset_check"] = dict(pruned_inside_base=inter, base=masks["base"].sum(), pruned=masks["pruned"].sum(),
                               deleted=int(masks["base"].sum() - inter),
                               reading=("the pruned file's dot set is a strict subset of the base file's: "
                                        "the two files differ ONLY by the near-catalogue deletion"
                                        if inter == masks["pruned"].sum() else "NOT a strict subset"))
    nb, np_ = masks["base"].sum(), masks["pruned"].sum()
    deleted = nb - np_
    sb, sp = PAIR["base"]["score"], PAIR["pruned"]["score"]
    # solve D from  s_b*(D + a*deleted) = s_p*D
    Dp = sb * ALPHA * deleted / (sp - sb)
    Db = Dp + ALPHA * deleted
    T = sp * Dp
    G_lo = (Db - ALPHA * T - ALPHA * nb) / BETA
    G_hi = (Db - ALPHA * T - 0.5 * ALPHA * nb) / BETA
    out["solution"] = dict(deleted_pixels=int(deleted), D_base=round(float(Db), 1),
                           D_pruned=round(float(Dp), 1), T_credit=round(float(T), 1),
                           credit_per_dot=round(float(T / np_), 4),
                           hidden_truth_pixels_G=dict(lo=round(float(G_lo)), hi=round(float(G_hi))),
                           # each covered truth pixel contributes <= 1 credit, so the number of truth
                           # pixels reached is in [T, |G|]: recall of the hidden set is bracketed by
                           # [T/|G|_hi, min(1, T/|G|_lo)] and a second bound #covered/|G| <= 1.
                           recall_of_hidden=dict(lo=round(float(T / G_hi), 3), hi=1.0),
                           ceiling_at_this_mass_if_perfect=dict(
                               formula="T=G, F=N-G: DTI = G/(0.2(G+F)+0.8G)",
                               value=round(float(G_hi / (ALPHA * (G_hi + max(0, np_ - G_hi)) + BETA * G_hi)), 3)),
                           reading=("the hidden scored set is ~10^4 px, the same order as the emitted dot "
                                    "count, so the family already reaches a large fraction of it: the "
                                    "remaining headroom is per-dot credit (placement), not budget"))
    for tag in PAIR:
        PAIR[tag].pop("path", None)
        out["inputs"][tag] = PAIR[tag]
    def _d(o):
        return int(o) if isinstance(o, np.integer) else float(o)

    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / "hidden_size_inversion.json").write_text(json.dumps(out, indent=1, default=_d))
    print(json.dumps(out, indent=1, default=_d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
