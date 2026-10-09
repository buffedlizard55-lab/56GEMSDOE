#!/usr/bin/env python3
"""Permutation control on the cluster gate: does ">=3 qualified neighbours" mean anything?

The emission rule keeps a candidate only when at least 3 qualified candidates land in its 3x3
neighbourhood, which is the operational reading of the brief's word "consistent". That is only
evidence of a *displaced line* if a coherent offset produces more neighbour-agreement than an
incoherent one. So: hold the candidate set and their count fixed, and randomise which side of the
trace each crest sits on (an independent fair coin per candidate). If the real, sign-preserving
configuration is not unusual against that null, then the surviving cluster is scatter, not a
correction -- which is precisely what a negative verdict needs to be able to say.

Reproduce: python scripts/cluster_gate_control.py
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
from gems56 import corrections as C, lane_inputs as L   # noqa: E402

GATE_PX, CORR_PX, MIN_CLUSTER, DRAWS = 1.0, 1.5, 3, 250


def targets(orow, ocol, ty, tx, joint, cat, fp, shape):
    yr = np.rint(orow - joint * tx).astype(np.int64)
    xc = np.rint(ocol + joint * ty).astype(np.int64)
    ok = ((yr >= 0) & (yr < shape[0]) & (xc >= 0) & (xc < shape[1]) & fp[yr, xc] & ~cat[yr, xc])
    return yr[ok], xc[ok]


def cluster_survive(yr, xc, shape, min_cluster=MIN_CLUSTER):
    cand = np.zeros(shape, bool)
    cand[yr, xc] = True
    nb = ndimage.uniform_filter(cand.astype(np.float32), size=3, mode="constant") * 9.0
    # count of *distinct occupied target cells* with >= min_cluster neighbours; duplicates collapse
    uniq = np.unique(np.ravel_multi_index((yr, xc), shape))
    yy, xx = np.unravel_index(uniq, shape)
    return int((nb[yy, xx] >= min_cluster).sum())


def main():
    t0 = time.time()
    fields, cat, fp, meta = L.load()
    rec = C.measure(fields, cat, fp)
    d, m = rec["dem_off_px"], rec["mag_off_px"]
    q = (rec["valid"] & np.isfinite(d) & np.isfinite(m) & (np.abs(d) >= GATE_PX) & (np.abs(m) >= GATE_PX)
         & (np.sign(d) == np.sign(m)) & (np.abs(d - m) <= CORR_PX)
         & (rec["dem_prom"] >= C.MIN_PROM_FRAC) & (rec["mag_prom"] >= C.MIN_PROM_FRAC))
    qi = np.nonzero(q)[0]
    orow, ocol, jj = rec["row"][qi], rec["col"][qi], (0.5 * (d + m))[qi]
    ty, tx, ok_s, _ = C.strike_at(cat, orow, ocol)
    orow, ocol, jj, ty, tx = [a[ok_s] for a in (orow, ocol, jj, ty, tx)]
    real_yr, real_xc = targets(orow, ocol, ty, tx, jj, cat, fp, cat.shape)
    real = cluster_survive(real_yr, real_xc, cat.shape)
    rng = np.random.default_rng(560301)

    def null_of(kind):
        """Two nulls, because a sign flip alone is not neutral.

        ``permute``  keeps the whole multiset of *signed* offsets -- magnitudes, signs and the detector's
                     own placement bias -- and reshuffles which pixel each one belongs to. This destroys the
                     correspondence between a transect and its crest and nothing else, so it is the fair
                     background for "the survivors are spatially coherent".
        ``signflip`` keeps the offset attached to its pixel and re-draws its side. It answers a different
                     question and it is *not* neutral here: with a constant placement bias b, a flipped dot
                     lands 2b further from its true mirror image, which mechanically loosens the cluster.
                     Reported anyway, because the difference between the two nulls is itself informative.
        """
        out = np.zeros(DRAWS, np.int64)
        for i in range(DRAWS):
            j2 = rng.permutation(jj) if kind == "permute" else np.where(
                rng.random(jj.size) < 0.5, -1.0, 1.0) * np.abs(jj)
            yr, xc = targets(orow, ocol, ty, tx, j2, cat, fp, cat.shape)
            out[i] = cluster_survive(yr, xc, cat.shape)
        return out

    nperm, nflip = null_of("permute"), null_of("signflip")
    p = float(((nperm >= real).mean()))
    out = dict(
        evidence_class="MEASURED permutation control on the same candidate set; not a score",
        n_candidates=int(q.sum()), n_targets_after_footprint=int(real_yr.size),
        real_cluster_survivors=real,
        permutation_null=dict(draws=DRAWS, mean=float(nperm.mean()), sd=float(nperm.std(ddof=1)),
                              p95=float(np.percentile(nperm, 95)), max=int(nperm.max())),
        sign_flip_null=dict(draws=DRAWS, mean=float(nflip.mean()), sd=float(nflip.std(ddof=1)),
                            p95=float(np.percentile(nflip, 95)), max=int(nflip.max())),
        one_sided_p_permutation=p, one_sided_p_signflip=float((nflip >= real).mean()),
        interpretation=("the configuration of survivors is no more coherent than the same offsets reassigned "
                        "to other pixels, so the cluster gate is not evidence of a displaced line"
                        if p > 0.05 else
                        "the survivors are more spatially coherent than a reassignment of the same offsets "
                        "would produce -- a necessary, not sufficient, condition for a real correction; read "
                        "together with the corridor gate, which is the sufficient one"),
        elapsed_s=round(time.time() - t0, 1))
    (ROOT / "evidence" / "cluster_gate_control.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
