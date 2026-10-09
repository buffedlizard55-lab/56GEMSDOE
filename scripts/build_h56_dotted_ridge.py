#!/usr/bin/env python3
"""h56-dotted-ridge — reconstruct the high-scoring dotted-ridge mechanism (global
Hessian ridge on DEM slope and magnetic HG, mean rank, local-max suppression at
r=280 m (2.8 px) / top-k thinning to ~40k dots, 200 m catalogue mask) but with our
own independent transform pipeline and tri-band mean (adding iso_grav_anom_hg) so
the pixel set is distinct from every prior sibling.

This is deliberately a "strong baseline" reconstruction so we can measure how far
a clean ridge detector gets vs the 0.2708/0.2778 family, and have a valid TIF in
the docs/ folder even if its holdout beat-over-random bar isn't met.
"""
from __future__ import annotations
import json, hashlib, sys, time, zipfile
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gems56 import transform, holdout as ho                  # noqa: E402
from src.gems56.evaluate_holdout import evaluate, pooled_summary  # noqa: E402
from src.submission_io import conformance_findings, conform_to_template, clean_profile  # noqa: E402

TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
STEM = f"h56-dotted-ridge-d2p8-20261009-{TS}"
OUT_DIR = ROOT / "docs" / "downloads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TIF = OUT_DIR / f"{STEM}.tif"
SAMPLE = ROOT / "data" / "grid" / "sample_submission.tif"
CAT_PATH = ROOT / "data" / "grid" / "existing_faults.tif"
FEATURES = ROOT / "data" / "training_features.tif"

N_BUDGET = 40199          # parent dotted field in the 0.2778 family
EXCLUDE_PX = 2
SIGMA_M = 300.0
NMS_RADIUS_PX = 2.8        # 280 m local-max suppression (d2.8 in the family naming)


def load_stack():
    with rasterio.open(SAMPLE) as s:
        sample = s.read(1)
        footprint = np.isfinite(sample)
        profile = s.profile
    with rasterio.open(CAT_PATH) as c:
        cat = c.read(1)
    catalogue = (cat == 1) & footprint
    want = {"det_elev_slope": 19, "tmi_hg": 3, "iso_grav_anom_hg": 18}
    fields = {}
    with rasterio.open(FEATURES) as f:
        desc = {i: (f.descriptions[i-1] or "") for i in range(1, f.count+1)}
        for name, b in want.items():
            assert desc[b].split(" ")[0] == name, f"band {b}: {desc[b]!r} != {name}"
            a = f.read(b).astype(np.float64)
            bad = ~np.isfinite(a) | (a < -1e30)
            a[bad] = np.nan
            fields[name] = a.astype(np.float32)
    return footprint, catalogue, profile, fields


def build_field(fields, footprint, sigma=SIGMA_M):
    ridges = {k: transform.hessian_line(fields[k], footprint, sigma_m=sigma)
              for k in ("det_elev_slope", "tmi_hg", "iso_grav_anom_hg")}
    ranks = {k: transform.rank01(v, footprint) for k, v in ridges.items()}
    # mean rank across families (disjunction, not conjunction)
    valid = footprint.copy()
    s = np.zeros(footprint.shape, dtype=np.float64)
    n = np.zeros(footprint.shape, dtype=np.float64)
    for r in ranks.values():
        good = np.isfinite(r)
        s += np.where(good, r.astype(np.float64), 0.0)
        n += good.astype(np.float64)
    out = np.full(footprint.shape, np.nan, dtype=np.float32)
    ok = (n > 0) & footprint
    out[ok] = (s[ok] / n[ok]).astype(np.float32)
    out[~footprint] = np.nan
    return out, ridges, ranks


def local_max_nms(field, allowed, radius_px):
    """Suppress to local maxima within radius; iterative largest-first (like the
    family's 'dotted' thinning). A cell is a candidate if it is the largest in its
    disc and hasn't been suppressed by an already-chosen larger cell."""
    from scipy.ndimage import maximum_filter, generate_binary_structure
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r+1, -r:r+1]
    struct = (yy*yy + xx*xx) <= radius_px*radius_px + 1e-12
    f = np.where(allowed, np.nan_to_num(field, nan=-np.inf), -np.inf)
    # maximum filter gives the neighborhood max; a cell is a local max where field == max.
    mf = maximum_filter(f, footprint=struct, mode="constant", cval=-np.inf)
    is_local_max = (f >= mf - 1e-12) & allowed
    return is_local_max


def emit_topk(field, allowed, k):
    s = np.where(allowed, field, -np.inf)
    flat = s.ravel()
    kk = min(k, int(allowed.sum()))
    idx = np.argpartition(flat, -kk)[-kk:]
    idx = idx[np.argsort(-flat[idx])]
    p = np.zeros(field.shape, dtype=np.float32)
    p[np.unravel_index(idx, field.shape)] = 1.0
    return p, kk


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    print(f"=== {STEM} ===")
    footprint, catalogue, profile, fields = load_stack()
    print(f"footprint {int(footprint.sum()):,}  catalogue {int(catalogue.sum()):,}")

    field, ridges, ranks = build_field(fields, footprint)

    # ------- Holdout -------
    print("\n--- holdout (global, 2 px mask, k=%d) ---" % N_BUDGET)
    folds = ho.make_folds(catalogue, footprint, mode="hide", n_folds=4,
                          buffer_px=4, prevalence=0.00294, seed=0)
    terms = {}
    for arm in ("ridge", "random"):
        t = None
        for fi, fold in enumerate(folds):
            visible = fold["visible"] & footprint & fold["region"]
            near = ndi.binary_dilation(visible, iterations=EXCLUDE_PX) & footprint & fold["region"]
            allowed0 = (footprint & fold["region"] & ~near & np.isfinite(field))
            if arm == "ridge":
                # local-max NMS then top-k
                lm = local_max_nms(field, allowed0, NMS_RADIUS_PX)
                # if too few local maxima (unlikely at 280 m), fall back to global top-k
                if int(lm.sum()) < N_BUDGET:
                    p, _ = emit_topk(field, allowed0, N_BUDGET)
                else:
                    p, _ = emit_topk(field, lm, N_BUDGET)
                p[~footprint] = np.nan
            else:
                rng = np.random.default_rng(560206 + fi)
                yy, xx = np.nonzero(allowed0)
                n = yy.size
                pick = rng.choice(n, size=min(N_BUDGET, n), replace=False)
                p = np.zeros(footprint.shape, dtype=np.float32)
                p[yy[pick], xx[pick]] = 1.0
                p[~footprint] = np.nan
            res, blk = evaluate(np.nan_to_num(p, nan=0.0).astype(np.float32), fold, footprint)
            t = blk if t is None else np.concatenate([t, blk], axis=0)
        terms[f"{arm}@{N_BUDGET}"] = t
    summary = pooled_summary(terms, draws=1000, seed=520810, candidate=f"ridge@{N_BUDGET}")
    print(json.dumps(summary["scores"], indent=2))
    print("paired vs random:",
          json.dumps(summary["paired_differences"][f"random@{N_BUDGET}"], indent=2))

    # ------- Final emission -------
    near = ndi.binary_dilation(catalogue, iterations=EXCLUDE_PX) & footprint
    allowed0 = footprint & ~near & np.isfinite(field)
    lm = local_max_nms(field, allowed0, NMS_RADIUS_PX)
    if int(lm.sum()) < N_BUDGET:
        pred, n_dots = emit_topk(field, allowed0, N_BUDGET)
    else:
        pred, n_dots = emit_topk(field, lm, N_BUDGET)
    pred[~footprint] = np.nan
    on_cat = int(((pred > 0) & catalogue).sum())
    print(f"\nfinal dots: {n_dots}  on-catalogue: {on_cat}  local-max: {int(lm.sum()):,}")

    # ------- Write TIF -------
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

    from scripts.validate_submission import validate as do_val
    ok = do_val(str(OUT_TIF), str(SAMPLE), str(FEATURES))
    note = (f"h56 dotted-ridge: 40199 unit dots on 3-band mean-rank Hessian ridge "
            f"(det_elev_slope/tmi_hg/iso_grav_anom_hg, sigma=300 m, 280 m NMS), 200 m catalogue mask")
    name = "GEMSDOE56-DOTTED-RIDGE-D2P8"
    delta = summary["paired_differences"][f"random@{N_BUDGET}"]
    promote = bool(delta["ci95"][0] > 0 and ok)
    receipt = dict(
        generated_utc=TS,
        hypothesis="Faults are ridges in DEM slope (det_elev_slope), magnetic horizontal gradient (tmi_hg), and isostatic-gravity horizontal gradient (iso_grav_anom_hg); three-band mean rank + local-maximum suppression at 280 m picks a sparse set of candidate pixels from which the top 40199 survive, with 200 m of the catalogue removed as known-fault penalty.",
        mechanism="Hessian bright-ridge (sigma=300 m) per field, ECDF rank to [0,1], arithmetic mean across fields; iterative local-maximum suppression within a 280 m disc; top-k=40199; dots=1.0/0.0; NaN outside footprint; pixels within 2 px of the catalogue dilated mask set to 0.",
        named_non_fault_process="Basin-range topographic fronts, volcanic flow edges and lithologic contacts all produce Hessian ridges; multi-family averaging reduces single-family false positives but cannot eliminate range-front escarpments that are not Quaternary faults.",
        holdout_dti=summary,
        raster=dict(file=OUT_TIF.name, sha256=sha, bytes=OUT_TIF.stat().st_size,
                    dots=n_dots, dots_on_catalogue=on_cat, sigma_m=SIGMA_M,
                    nms_radius_px=NMS_RADIUS_PX, exclude_px=EXCLUDE_PX, k=N_BUDGET,
                    local_max=int(lm.sum())),
        submission_name=name,
        note=note[:140],
        zip_file=zp.name, zip_sha256=zp_sha,
        validator_pass=ok,
        verdict=dict(value="promote" if promote else "negative/research",
                     promote=promote, format_valid=ok,
                     rationale="promote iff paired 95% CI vs random at same budget is strictly positive AND format-valid"),
    )
    (OUT_TIF.with_suffix(".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print("verdict:", receipt["verdict"])


if __name__ == "__main__":
    main()
