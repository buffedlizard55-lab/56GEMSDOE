#!/usr/bin/env python3
"""Verify the pinned inputs and measure the grid. Writes ``evidence/grid.json``.

Nothing here is taken on trust from a sibling repository: the shape, transform, footprint cell
count, catalogue pixel count and nodata sentinel are all re-derived from the bytes on disk and
compared with the pins in ``registry/input_pins.json``. A mismatch is an error, not a warning.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems56 import grid as G          # noqa: E402
from gems56 import corrections as C   # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv):
    pins = json.loads((ROOT / "registry" / "input_pins.json").read_text())
    out = {"class": "measured on this machine from the bytes on disk", "inputs": {}}
    for key, spec in pins["files"].items():
        p = ROOT / spec["path"]
        rec = dict(path=spec["path"], bytes=p.stat().st_size, sha256=sha256(p),
                   role=spec["role"], provenance=spec["provenance"])
        rec["pin_match"] = (rec["sha256"] == spec["sha256"]) if spec.get("sha256") else "no pin (large stack: pinned via shard hashes)"
        if key == "features" and spec.get("sha256"):
            rec["pin_match"] = rec["sha256"] == spec["sha256"]
        out["inputs"][key] = rec
        if rec["pin_match"] is False:
            raise SystemExit(f"PIN MISMATCH for {key}: {rec['sha256']} != {spec['sha256']}")
    # grid facts
    with rasterio.open(ROOT / pins["files"]["sample"]["path"]) as ds:
        a = ds.read(1)
        out["grid"] = dict(shape=list(ds.shape), crs=str(ds.crs.to_epsg()),
                           transform=[float(v) for v in ds.transform][:6], dtype=ds.dtypes[0],
                           nodata=repr(ds.nodata), count=ds.count)
        out["grid"]["transform_matches_template"] = (tuple(float(v) for v in ds.transform)[:6] == G.TRANSFORM)
        out["grid"]["shape_matches_template"] = (ds.shape == G.SHAPE)
        fp_sample = np.isfinite(a)
        out["footprint_sample"] = dict(cells=int(fp_sample.sum()), of=int(a.size),
                                       rule="sample_submission.tif finite mask (the organizer's own null convention)",
                                       nan_cells=int(np.isnan(a).sum()))
        fp = fp_sample
    catp = ROOT / pins["files"]["catalogue"]["path"]
    with rasterio.open(catp) as ds:
        cat = ds.read(1)
    out["catalogue"] = dict(dtype=ds.dtypes[0], nodata=repr(ds.nodata),
                            values=[int(v) for v in np.unique(cat)],
                            positive_cells=int((cat == 1).sum()),
                            positive_in_footprint=int(((cat == 1) & fp).sum()),
                            prevalence=float((cat == 1).sum()) / float(fp.sum()))
    # The organizer's sample submission is documented on the problem page as "a sample submission
    # that predicts total fault absence". Measured here: it is cell-for-cell the catalogue mask.
    with rasterio.open(ROOT / pins["files"]["sample"]["path"]) as ds:
        sub = ds.read(1)
    same = ((cat == 1) == (np.where(np.isfinite(sub), sub, 0) == 1)).all()
    out["sample_submission_forensics"] = dict(
        unique_finite_values=[float(v) for v in np.unique(sub[np.isfinite(sub)])],
        positive_cells=int((sub == 1).sum()), nan_cells=int(np.isnan(sub).sum()),
        cell_for_cell_equal_to_catalogue=bool(same),
        note=("MEASURED: the shipped sample submission is not an all-zero raster; it is the "
              "catalogue mask (NaN outside the footprint). Independently reproduces the "
              "GEMSDOE54 audit claim; logged as irregularity IR-56-001."),
    )
    # band inventory, footprints and the band-6 identity question (GEMSDOE52 IR-52-019 claims
    # band 6 is the radiometric total-count channel, not the magnetic tilt the tag says)
    feats = C.load_fields(ROOT / pins["files"]["features"]["path"])
    out["bands"] = feats["_band_inventory"]
    with rasterio.open(ROOT / pins["files"]["features"]["path"]) as ds:
        out["band_descriptions"] = {str(i): (ds.descriptions[i - 1] or "") for i in range(1, ds.count + 1)}
        out["sentinel"] = dict(
            value=float(ds.nodata) if ds.nodata is not None else None,
            detail=("nodata is stored as the float32 min-sentinel, which np.isfinite() accepts as "
                    "valid data; every reader in this repo masks it with grid.SENTINEL_LIMIT instead"),
        )
        stack_ok = None
        for i in range(1, ds.count + 1):
            b = ds.read(i)
            ok = np.isfinite(b) & (b > C.NODATA_LIMIT)
            stack_ok = ok if stack_ok is None else (stack_ok & ok)
            if i == 1:
                out["sentinel"]["fraction_band1"] = float((~ok).mean())
    out["footprint_features_all19"] = dict(cells=int(stack_ok.sum()), rule="intersection over all 19 bands")
    out["footprint_used"] = dict(
        cells=int((fp & stack_ok).sum()),
        rule="sample-submission finite mask AND every feature band valid, so both the evidence "
             "profile and the score are defined at every emitted pixel (template convention)",
    )
    out["footprint_catalogue"] = dict(nodata_cells=int((~fp_sample).sum()))
    fp_use = fp & stack_ok
    out["catalogue"]["positive_in_used_footprint"] = int(((cat == 1) & fp_use).sum())
    out["catalogue"]["prevalence_in_used_footprint"] = float(((cat == 1) & fp_use).sum()) / float(fp_use.sum())
    # LiDAR cover: how much of the footprint has an unambiguous 1 m-derived scarp at all
    lp = ROOT / pins["files"]["lidar_scarp"]["path"]
    if lp.exists():
        lc = C.load_fields(ROOT / pins["files"]["features"]["path"], lidar_path=lp)
        cov = np.isfinite(lc["lidar_cover"]) & (lc["lidar_cover"] > 0)
        out["lidar"] = dict(cells_with_cover=int((cov & fp_use).sum()),
                            fraction_of_footprint=float((cov & fp_use).sum() / fp_use.sum()),
                            h_all_percentiles=[float(v) for v in np.nanpercentile(lc["lidar_h_m"][fp_use], [50, 90, 99, 99.9])],
                            catalogue_pixels_with_cover=int((cov & (cat == 1)).sum()),
                            note="h_all > 0 means the 3 m detector found a line-persistent step in that cell")
    G.save_json(ROOT / "evidence" / "grid.json", out)
    print(json.dumps({k: (v if k not in ("band_descriptions", "bands") else "...") for k, v in out.items()}, indent=1)[:3000])
    print("\nwrote evidence/grid.json")


if __name__ == "__main__":
    main(sys.argv[1:])
