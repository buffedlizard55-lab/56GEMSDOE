#!/usr/bin/env python3
"""h56-persist-step — a persistent step/edge concordance submission, recalling the
highest-scoring family's emission budget but on a novel multi-physics persistent-step
score rather than a pure DEM/mag ridge or a habitat field.

Hypothesis (H12, new for this run):
Faults produce sharp two-sided *steps* (not just ridges) that persist for kilometres
along strike across the DEM (det_elev) AND the magnetic field (tmi) AND the isostatic
gravity field.  A step is a signed discontinuity; requiring >=2 km of along-strike
persistence (the scarp_step operator) removes basin edges, canyons and isolated
outcrops.  The product of the three directional step responses yields a concordance
that none of the 412 unique-pixel registry rasters emits from.

Emission: top-k of rank(product), k=37,654 (matched to the 0.2778 family's density),
after a 2 px (200 m) dilation of the known-fault mask (verified 0.2778 mechanism).

This is a research emission. HOLDOUT-DTI vs random decides promotion; verdict is
recorded in the JSON sidecar, not guessed.
"""
from __future__ import annotations
import json, hashlib, sys, time, zipfile
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gems56 import transform, holdout as ho, metric as met      # noqa: E402
from src.gems56.evaluate_holdout import evaluate, pooled_summary    # noqa: E402
from src.submission_io import conformance_findings, conform_to_template, clean_profile  # noqa: E402

TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
STEM = f"h56-persist-step-r300-20261009-{TS}"
OUT_DIR = ROOT / "docs" / "downloads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TIF = OUT_DIR / f"{STEM}.tif"
SAMPLE = ROOT / "data" / "grid" / "sample_submission.tif"
CAT_PATH = ROOT / "data" / "grid" / "existing_faults.tif"
FEATURES = ROOT / "data" / "training_features.tif"

N_BUDGET = 37654
EXCLUDE_PX = 2
HALF_WIDTH_M = 150.0
PERSIST_M = 2000.0


def load_stack():
    with rasterio.open(SAMPLE) as s:
        sample = s.read(1)
        footprint = np.isfinite(sample)
        profile = s.profile
    with rasterio.open(CAT_PATH) as c:
        cat = c.read(1)
    catalogue = (cat == 1) & footprint
    fields = {}
    # det_elev (12), tmi (14), iso_grav_anom (13) — three independent physics fields
    want = {"det_elev": 12, "tmi": 14, "iso_grav_anom": 13,
            "det_elev_slope": 19, "tmi_hg": 3}
    with rasterio.open(FEATURES) as f:
        desc = {i: (f.descriptions[i-1] or "") for i in range(1, f.count+1)}
        for name, b in want.items():
            assert desc[b].split(" ")[0] == name, f"band {b}: {desc[b]!r} != {name}"
            a = f.read(b).astype(np.float64)
            bad = ~np.isfinite(a) | (a < -1e30)
            a[bad] = np.nan
            fields[name] = a.astype(np.float32)
    return footprint, catalogue, profile, fields


def tri_persist_step(fields, footprint):
    """scarp_step (persistent two-sided step) on three independent physics fields;
    return geometric-mean of their ranks, plus per-field ridges for reference."""
    # Persistent step on elevation and the two potential fields.
    step = {}
    for k in ("det_elev", "tmi", "iso_grav_anom"):
        resp, _arg = transform.scarp_step(fields[k], footprint,
                                          half_width_m=HALF_WIDTH_M,
                                          persist_m=PERSIST_M)
        step[k] = resp
    # Rank each to [0,1] within valid footprint
    ranks = {k: transform.rank01(v, footprint) for k, v in step.items()}
    valid = footprint.copy()
    for r in ranks.values():
        valid &= np.isfinite(r)
    prod = np.ones(footprint.shape, dtype=np.float64)
    for r in ranks.values():
        prod *= np.where(valid, r.astype(np.float64), 1.0)
    score = np.full(footprint.shape, np.nan, dtype=np.float32)
    score[valid] = (prod[valid] ** (1.0/3)).astype(np.float32)
    score[~footprint] = np.nan
    return score, step, ranks


def emit_topk(score, footprint, exclude_mask, k):
    allowed = footprint & ~exclude_mask & np.isfinite(score)
    s = np.where(allowed, score, -np.inf)
    flat = s.ravel()
    kk = min(k, int(allowed.sum()))
    idx = np.argpartition(flat, -kk)[-kk:]
    idx = idx[np.argsort(-flat[idx])]
    p = np.zeros(footprint.shape, dtype=np.float32)
    p[np.unravel_index(idx, footprint.shape)] = 1.0
    p[~footprint] = np.nan
    return p, kk


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    print(f"=== {STEM} build ===")
    footprint, catalogue, profile, fields = load_stack()
    print(f"footprint: {int(footprint.sum()):,}  catalogue: {int(catalogue.sum()):,}")

    score, steps, ranks = tri_persist_step(fields, footprint)
    print(f"score finite cells: {int((footprint & np.isfinite(score)).sum()):,}")

    # ------- Holdout (4 folds hide-and-recover) -------
    print("\n--- holdout ---")
    folds = ho.make_folds(catalogue, footprint, mode="hide", n_folds=4,
                          buffer_px=4, prevalence=0.00294, seed=0)
    terms = {}
    for arm in ("persist", "random"):
        t = None
        for fi, fold in enumerate(folds):
            visible = fold["visible"] & footprint & fold["region"]
            near = ndi.binary_dilation(visible, iterations=EXCLUDE_PX) & footprint & fold["region"]
            if arm == "persist":
                p, _ = emit_topk(score, footprint & fold["region"], near, N_BUDGET)
            else:
                rng = np.random.default_rng(560203 + fi)
                allowed = (footprint & fold["region"] & ~near)
                yy, xx = np.nonzero(allowed)
                n = yy.size
                pick = rng.choice(n, size=min(N_BUDGET, n), replace=False)
                p = np.zeros(footprint.shape, dtype=np.float32)
                p[yy[pick], xx[pick]] = 1.0
                p[~footprint] = np.nan
            res, blk = evaluate(np.nan_to_num(p, nan=0.0).astype(np.float32), fold, footprint)
            t = blk if t is None else np.concatenate([t, blk], axis=0)
        terms[f"{arm}@{N_BUDGET}"] = t
    summary = pooled_summary(terms, draws=1000, seed=520810, candidate=f"persist@{N_BUDGET}")
    print(json.dumps(summary["scores"], indent=2))
    print("paired vs random:",
          json.dumps(summary["paired_differences"][f"random@{N_BUDGET}"], indent=2))

    # ------- Final emission against the full catalogue -------
    near_cat = ndi.binary_dilation(catalogue, iterations=EXCLUDE_PX) & footprint
    pred, n_dots = emit_topk(score, footprint, near_cat, N_BUDGET)
    on_cat = int(((pred > 0) & catalogue).sum())
    near_n = int(((pred > 0) & ~catalogue & near_cat).sum())
    print(f"\nfinal dots: {n_dots}, on-catalogue: {on_cat}, within {EXCLUDE_PX}px: {near_n}")

    # ------- Write conformant TIF -------
    with rasterio.open(SAMPLE) as s:
        tmpl = s.read(1)
    conformed, stats = conform_to_template(pred, tmpl)
    prof = clean_profile(dict(profile), dtype="float32", nodata=float("nan"),
                         tiled=True, tile=256)
    tmp = OUT_TIF.with_suffix(OUT_TIF.suffix + ".writing")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(conformed.astype(np.float32), 1)
    with rasterio.open(tmp) as d:
        back = d.read(1)
        f = conformance_findings(back, tmpl)
        if not f["conformant"]:
            raise RuntimeError(f"non-conformant: {f}")
    tmp.replace(OUT_TIF)
    sha = sha256_file(OUT_TIF)
    print(f"wrote {OUT_TIF.name} ({OUT_TIF.stat().st_size} B, sha256 {sha[:16]}…)")

    zp = OUT_TIF.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(OUT_TIF.name, date_time=(2026, 10, 9, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, OUT_TIF.read_bytes())
    zp_sha = sha256_file(zp)

    # ------- Validate with the real validator -------
    from scripts.validate_submission import validate as do_val
    ok = do_val(str(OUT_TIF), str(SAMPLE), str(FEATURES))
    print("validate_submission:", "PASS" if ok else "FAIL")

    note = (f"h56 persist-step: 37654 dots on 3-physics concordant persistent-step "
            f"(det_elev/tmi/iso_grav_anom, half 150 m, persist 2 km), 200 m catalogue mask")
    name = "GEMSDOE56-PERSIST-STEP-3PHYS"
    delta = summary["paired_differences"][f"random@{N_BUDGET}"]
    promote = bool(delta["ci95"][0] > 0)
    receipt = dict(
        generated_utc=TS,
        hypothesis="Faults are persistent two-sided steps (half-width 150 m, along-strike >=2 km) in three independent physics fields (det_elev, tmi, iso_grav_anom) simultaneously; three-way concordance ranks higher than any single-family step.",
        mechanism="scarp_step (directional two-sided mean difference, along-strike persistence smoothing) on each of det_elev, tmi, iso_grav_anom; ECDF rank each to [0,1]; geometric mean; top-k=37654 after a 2 px dilation of the USGS/INGENIOUS catalogue mask; dots=1.0/0.0, NaN outside footprint.",
        named_non_fault_process="Range-front alluvial-fan escarpments and pluton/lava-flow contacts can also produce persistent steps; requiring three independent geophysical fields to step at the same cell reduces but does not eliminate basin-margin escarpments that have both topographic and density/magnetic expression.",
        holdout_dti=summary,
        raster=dict(file=OUT_TIF.name, sha256=sha, bytes=OUT_TIF.stat().st_size,
                    dots=n_dots, dots_on_catalogue=on_cat, dots_within_200m=near_n,
                    half_width_m=HALF_WIDTH_M, persist_m=PERSIST_M,
                    exclude_px=EXCLUDE_PX, k=N_BUDGET),
        submission_name=name,
        note=note[:140],
        zip_file=zp.name, zip_sha256=zp_sha,
        validator_pass=ok,
        verdict=dict(value="promote" if (ok and promote) else "negative/research",
                     promote=promote, format_valid=ok,
                     rationale="promote iff paired 95% CI vs random at the same budget is strictly positive AND format-valid"),
    )
    (OUT_TIF.with_suffix(".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print("receipt:", OUT_TIF.with_suffix(".json").name)
    print("verdict:", receipt["verdict"])


if __name__ == "__main__":
    main()
