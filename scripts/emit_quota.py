#!/usr/bin/env python3
"""E5 — the secondary candidate: the credit-weighted multi-physics *quota union*, packed on the axes.

Same packing, same emission floor and the same dot count as the primary, but the pixels come from six
independent physical channels, each given a quota of the budget proportional to the pooled HOLDOUT-DTI
we measured for it (``evidence/field_holdout_v1.json``), so the weak channels get little and no channel
has to agree with the others for a cell to be emitted. The equal-rank mean is the wrong combinator for
a max-over-neighbours objective (it demotes a cell that is first in one channel and tenth in another),
and E4 measured that: the mean lost to the best single channel by a factor of two
(0.0179 vs 0.0387 pooled HOLDOUT-DTI, evidence/quota_union_v1.json). This file is the version of the
idea that survived: the union, weighted by measured credit, still behind the primary but covering a
materially different part of the surface, which is what makes it worth keeping as the alternative arm.

Reproduce: python scripts/emit_quota.py --budget 37654 --name h56-quota-37k-20261009
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from emit_and_score import greedy_pack  # noqa: E402
from gems56 import gates, grid as G, holdout as H  # noqa: E402

FIELDS = ROOT / "data" / "interim" / "fields"
CH = ["mag_ridge", "scarp_slope", "rtp_ridge", "strain_2ndinv_ridge", "grav_ridge", "cond_edge"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--nms", type=float, default=2.8)
    ap.add_argument("--shadow", type=int, default=2)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    ev = json.loads((ROOT / "evidence" / "field_holdout_v1.json").read_text())
    e1 = {n: v["dti"] for n, v in ev["instruments"]["hide"]["pooled"]["scores"].items() if n in CH}
    w = np.array([max(0.0, e1[n]) for n in CH]); w /= w.sum()
    fp = np.load(FIELDS / "_footprint.npy")
    cat = np.load(FIELDS / "_cat.npy") & fp
    allowed = fp & ~(ndimage.binary_dilation(cat, iterations=a.shadow) & fp)
    ranks = {n: (np.load(FIELDS / f"{n}.npy").astype(np.float32) / 65535.0) for n in CH}
    cons = np.max([ranks[n] for n in CH], axis=0).astype(np.float32)
    uni = np.zeros(fp.shape, bool)
    quota = {}
    for n, wi in zip(CH, w):
        q = int(np.ceil(wi * a.budget))
        quota[n] = q
        uni |= H.emit_topk(ranks[n], allowed, q) > 0
    em, st = greedy_pack(cons, allowed & uni, a.nms, a.budget)
    arr = np.where(fp, em, 0.0).astype(np.float32)
    out = ROOT / "docs" / "downloads" / f"{a.name}.tif"
    meta = G.write_geotiff(out, arr, nodata=None)
    import zipfile
    with zipfile.ZipFile(out.with_suffix(".zip"), "w", zipfile.ZIP_STORED) as z:
        z.write(out, arcname=out.name)
    fmt = gates.format_report(out, ROOT / "data" / "grid" / "sample_submission.tif", footprint=fp)
    dd = ndimage.distance_transform_edt(~cat)[arr > 0]
    rep = dict(name=a.name, file=f"docs/downloads/{a.name}.tif", bytes=out.stat().st_size,
               sha256=gates.sha256(out), dots=int((arr > 0).sum()),
               values_present=sorted(set(np.unique(arr).tolist())), mass=float(arr.sum()),
               min_d_catalogue_px=float(dd.min()), frac_d_gt_2px=float((dd > 2 + 1e-9).mean()),
               arm="QUOTA|packed|weighted", quota=quota, pack_stats=st, channels=CH,
               weights_from="evidence/field_holdout_v1.json pooled hide DTI",
               format_report=fmt, geotiff=meta)
    for p in (ROOT / "evidence" / f"raster_{a.name}.json", ROOT / "docs" / "downloads" / f"checks-{a.name}.json"):
        p.write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: rep[k] for k in ("name", "dots", "values_present", "min_d_catalogue_px",
                                          "bytes", "sha256")}, indent=1, default=float))
    print("FORMAT ok:", fmt.get("ok"), "problems:", fmt.get("problems"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
