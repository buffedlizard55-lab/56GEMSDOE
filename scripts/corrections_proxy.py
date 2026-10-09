"""Corrections lane, PROXY measurement (experiment 2 of 3).

What it measures: how far the catalogue trace sits from an independent trace set, at 100 m.
  catalogue proxy : USGS QFaults-v2 traces rasterised to the competition grid (owner mirror,
                    GEMSDOE30/data/external/derived_gdr_qfaults_v2_100m_u8.tif)
  evidence proxy  : USGS State Geologic Map Compilation (SGMC) faults rasterised to the grid
                    (GEMSDOE30/data/external/derived_sgmc_faults_100m_u8.tif)

What it does NOT measure: the protocol's intended test - the DEM-curvature scarp crest and the
magnetic-gradient ridge crest, calibrated on 1 m LiDAR. Neither the 1 m DEM nor the GeoDAWN
magnetics are reachable from this sandbox, so this script only reports a proxy.

Usage: python scripts/corrections_proxy.py <catalogue.tif> <sgmc.tif> <out.json>
"""

import json
import sys
from collections import Counter

import numpy as np
import rasterio
from scipy import ndimage as ndi

PIX = 100.0
SEARCH_PX = 4          # +/- 400 m, the organisers' stated maximum discrepancy scale
THRESH_PX = 2.0        # protocol threshold: a consistent offset above ~2 px triggers emission
BLOCK_PX = 50          # 5 km blocks for the local-offset test
MIN_BLOCK_N = 30


def main(cat_path, sg_path, out_path):
    with rasterio.open(cat_path) as ds:
        cat = ds.read(1) == 1
        grid = dict(crs=ds.crs.to_string(), width=ds.width, height=ds.height,
                    transform=[float(x) for x in tuple(ds.transform)[:6]])
    with rasterio.open(sg_path) as ds:
        sg = ds.read(1) == 1
    d_sg = ndi.distance_transform_edt(~sg)
    d_cat = ndi.distance_transform_edt(~cat)
    idx = ndi.distance_transform_edt(~sg, return_distances=False, return_indices=True)

    near = cat & (d_sg <= SEARCH_PX)
    ci = np.argwhere(near)
    dist_hist = {str(r): int(((d_sg <= r) & cat).sum()) for r in range(0, SEARCH_PX + 1)}
    dy = (idx[0][ci[:, 0], ci[:, 1]] - ci[:, 0]).astype(float)
    dx = (idx[1][ci[:, 0], ci[:, 1]] - ci[:, 1]).astype(float)
    mag = np.hypot(dy, dx)

    # Local test: block-mean displacement. A consistent offset would show as block means > 2 px.
    keys = (ci[:, 0] // BLOCK_PX) * 100000 + (ci[:, 1] // BLOCK_PX)
    block_means = []
    for k in np.unique(keys):
        m = keys == k
        if m.sum() >= MIN_BLOCK_N:
            block_means.append(float(np.hypot(dy[m].mean(), dx[m].mean())))
    bm = np.array(block_means)

    result = dict(
        script="scripts/corrections_proxy.py",
        grid=grid,
        catalogue_proxy_px=int(cat.sum()),
        evidence_proxy_px=int(sg.sum()),
        evidence_px_within_r_of_catalogue={str(r): int(((d_cat <= r) & sg).sum()) for r in range(0, SEARCH_PX + 1)},
        evidence_px_farther_than_4px=int(((d_cat > SEARCH_PX) & sg).sum()),
        catalogue_px_within_r_of_evidence=dist_hist,
        catalogue_px_with_evidence_within_4px=int(len(ci)),
        nearest_displacement_magnitude_px=dict(
            mean=float(mag.mean()), median=float(np.median(mag)),
            share_le_1px=float((mag <= 1.0).mean()), share_le_2px=float((mag <= 2.0).mean())),
        top_displacements_dy_dx=[[list(k), int(v)] for k, v in Counter(zip(dy.astype(int).tolist(), dx.astype(int).tolist())).most_common(12)],
        local_test=dict(
            block_px=BLOCK_PX, min_pairs_per_block=MIN_BLOCK_N, blocks_tested=int(len(bm)),
            block_mean_magnitude_px=dict(median=float(np.median(bm)), p90=float(np.percentile(bm, 90)), max=float(bm.max())),
            blocks_over_2px=int((bm > THRESH_PX).sum())),
        protocol_threshold_px=THRESH_PX,
        verdict=("offsets cluster under 2 px in this proxy -> corrections lane emits NOTHING "
                 "(proxy only; DEM-crest test still BLOCKED)" if np.median(mag) < THRESH_PX and bm.size and np.percentile(bm, 90) <= THRESH_PX
                 else "offsets exceed 2 px in places -> needs DEM-crest confirmation before emission"),
        limitations=[
            "SGMC is a 1:50,000-1:1,000,000 compilation; its positional error is far larger than 100 m, so this is not a sub-pixel test.",
            "SGMC source used by the owner mirror is the 2017 release; USGS says it is superseded by DOI 10.5066/P1A3DQZK (2026).",
            "Nearest-pixel displacement is biased toward 0 for rasterised lines; treat it as an order-of-magnitude check.",
            "Not a DEM-crest or magnetic-ridge measurement; no LiDAR calibration was possible.",
        ],
    )
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in ("catalogue_proxy_px", "evidence_proxy_px", "nearest_displacement_magnitude_px", "local_test", "verdict")}, indent=2))


if __name__ == "__main__":
    main(*sys.argv[1:4])
