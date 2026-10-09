#!/usr/bin/env python3
"""h56-final — promoted submission built from h56-dotted-ridge-d2p8,
with the catalogue-pruning step that the 0.2778 family applied (delete any dot
within 2 px of the dilated catalogue after emission, then re-top-up to 37,654
dots if needed from the next-best local maxima).

This is the file we put in front of the site as the submission candidate.
It is format-validated, holdout-validated, and its receipt records:
  - submission name + note (<= 140 chars each)
  - holdout DTI + 95% CI vs the random control at matched budget
  - sha256
  - validator: all-finite inside footprint, NaN outside, values in [0,1],
    CRS/shape/transform matching sample_submission.tif
"""
from __future__ import annotations
import json, hashlib, sys, time, zipfile
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gems56 import transform, holdout as ho                   # noqa: E402
from src.gems56.evaluate_holdout import evaluate, pooled_summary  # noqa: E402
from src.submission_io import conformance_findings, conform_to_template, clean_profile  # noqa: E402

TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
NAME_BASE = "h56-final-dotted-ridge-d2p8"
STEM = f"{NAME_BASE}-{TS}"
OUT_DIR = ROOT / "docs" / "downloads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TIF = OUT_DIR / f"{STEM}.tif"
SAMPLE = ROOT / "data" / "grid" / "sample_submission.tif"
CAT_PATH = ROOT / "data" / "grid" / "existing_faults.tif"
FEATURES = ROOT / "data" / "training_features.tif"

FINAL_BUDGET = 37654       # 0.2778 family's post-prune count
NMS_RADIUS_PX = 2.8
SIGMA_M = 300.0
EXCLUDE_PX = 2             # dilated-catalogue mask (200 m) — delete any dot within


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
    return out


def emit_masked_topk(field, footprint, near_mask, k, nms_radius_px=NMS_RADIUS_PX):
    """Top-k of local maxima strictly OUTSIDE the near-catalogue mask."""
    from scipy.ndimage import maximum_filter
    r = int(np.ceil(nms_radius_px))
    yy, xx = np.mgrid[-r:r+1, -r:r+1]
    struct = (yy*yy + xx*xx) <= nms_radius_px*nms_radius_px + 1e-12
    allowed = footprint & ~near_mask & np.isfinite(field)
    f = np.where(allowed, np.nan_to_num(field, nan=-np.inf), -np.inf)
    mf = maximum_filter(f, footprint=struct, mode="constant", cval=-np.inf)
    is_lm = (f >= mf - 1e-12) & allowed
    if int(is_lm.sum()) < k:
        # fall back: top-k among allowed without the NMS constraint
        cand = allowed
    else:
        cand = is_lm
    flat = np.where(cand, f, -np.inf).ravel()
    kk = min(k, int(cand.sum()))
    idx = np.argpartition(flat, -kk)[-kk:]
    idx = idx[np.argsort(-flat[idx])]
    p = np.zeros(field.shape, dtype=np.float32)
    p[np.unravel_index(idx, field.shape)] = 1.0
    return p, kk, int(is_lm.sum())


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    print(f"=== {STEM} (promoted submission) ===")
    footprint, catalogue, profile, fields = load_stack()
    print(f"footprint {int(footprint.sum()):,}  catalogue {int(catalogue.sum()):,}")
    field = build_field(fields, footprint)

    # ------- Holdout with the final emission rule -------
    print("\n--- holdout ---")
    folds = ho.make_folds(catalogue, footprint, mode="hide", n_folds=4,
                          buffer_px=4, prevalence=0.00294, seed=0)
    arms = {
        "final": dict(k=FINAL_BUDGET, exclude=EXCLUDE_PX, rule="ridge NMS"),
        "random": dict(k=FINAL_BUDGET, exclude=EXCLUDE_PX, rule="random"),
    }
    terms = {a: None for a in arms}
    for fi, fold in enumerate(folds):
        visible = fold["visible"] & footprint & fold["region"]
        near = ndi.binary_dilation(visible, iterations=EXCLUDE_PX) & footprint & fold["region"]
        # final arm
        p, _, _ = emit_masked_topk(field, footprint & fold["region"], near, FINAL_BUDGET)
        p[~footprint] = np.nan
        _, blk = evaluate(np.nan_to_num(p, nan=0.0).astype(np.float32), fold, footprint)
        terms["final"] = blk if terms["final"] is None else np.concatenate([terms["final"], blk], axis=0)
        # random arm (same exclude mask, same budget)
        rng = np.random.default_rng(560207 + fi)
        allowed = footprint & fold["region"] & ~near
        yy, xx = np.nonzero(allowed)
        n = yy.size
        pick = rng.choice(n, size=min(FINAL_BUDGET, n), replace=False)
        q = np.zeros(footprint.shape, dtype=np.float32)
        q[yy[pick], xx[pick]] = 1.0
        q[~footprint] = np.nan
        _, blk = evaluate(np.nan_to_num(q, nan=0.0).astype(np.float32), fold, footprint)
        terms["random"] = blk if terms["random"] is None else np.concatenate([terms["random"], blk], axis=0)
    terms_k = {f"{k}@{FINAL_BUDGET}": v for k, v in terms.items()}
    summary = pooled_summary(terms_k, draws=1000, seed=520810, candidate=f"final@{FINAL_BUDGET}")
    print(json.dumps(summary["scores"], indent=2))
    delta = summary["paired_differences"][f"random@{FINAL_BUDGET}"]
    print("paired vs random:", json.dumps(delta, indent=2))
    promote = bool(delta["ci95"][0] > 0)

    # ------- Final emission -------
    near = ndi.binary_dilation(catalogue, iterations=EXCLUDE_PX) & footprint
    pred, n_dots, n_lm = emit_masked_topk(field, footprint, near, FINAL_BUDGET)
    pred[~footprint] = np.nan
    on_cat = int(((pred > 0) & catalogue).sum())
    near_n = int(((pred > 0) & ~catalogue & near).sum())
    print(f"\nfinal dots: {n_dots}  on-catalogue: {on_cat}  within 2 px: {near_n}  local-max: {n_lm:,}")

    # ------- Write TIF (conformant with sample) -------
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
    print(f"\nwrote {OUT_TIF.name} ({OUT_TIF.stat().st_size} B)")
    print(f"sha256: {sha}")

    zp = OUT_TIF.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(OUT_TIF.name, date_time=(2026, 10, 9, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, OUT_TIF.read_bytes())
    zp_sha = sha256_file(zp)

    from scripts.validate_submission import validate as do_val
    ok = do_val(str(OUT_TIF), str(SAMPLE), str(FEATURES))

    # canonical submission name/note (both <= 140 chars)
    sub_name = f"GEMSDOE56-dotted-ridge-d2p8"
    note = (f"h56 final: 37654 unit dots on 3-band mean-rank Hessian ridge "
            f"(det_elev_slope/tmi_hg/iso_grav_anom_hg, sigma=300 m, 280 m NMS, "
            f"200 m catalogue mask); HOLDOUT-DTI vs random +{delta['delta']:.4f}")
    note = note[:140]

    receipt = dict(
        generated_utc=TS,
        hypothesis="Faults produce ridges in three independent physics fields simultaneously (DEM slope curvature det_elev_slope, magnetic horizontal gradient tmi_hg, isostatic-gravity horizontal gradient iso_grav_anom_hg); local-maximum suppression at the 300 m scoring-kernel scale yields a sparse set of candidate pixels; the top 37,654 outside a 200 m dilated catalogue mask is the emission.",
        mechanism=("Hessian bright-ridge (sigma=300 m) per band; ECDF rank transform to [0,1]; "
                   "arithmetic mean of ranks across bands; 280 m disc local-maximum suppression; "
                   "top-k=37,654 restricted to footprint minus a 2 px (200 m) dilation of the USGS/INGENIOUS catalogue; "
                   "emitted value 1.0, background 0.0, NaN strictly outside the sample footprint. "
                   "No learned component; no external data beyond the competition feature stack."),
        named_non_fault_process=("Basin-and-Range range-front escarpments, volcanic flow edges, "
                                 "and lithologic contacts produce Hessian ridges in one or two of "
                                 "the three bands; requiring three bands and NMS thinning reduces "
                                 "but does not eliminate non-fault lineaments."),
        holdout_dti=summary,
        raster=dict(file=OUT_TIF.name, sha256=sha, bytes=OUT_TIF.stat().st_size,
                    dots=n_dots, dots_on_catalogue=on_cat, dots_within_200m=near_n,
                    sigma_m=SIGMA_M, nms_radius_px=NMS_RADIUS_PX,
                    exclude_px=EXCLUDE_PX, k=FINAL_BUDGET,
                    local_max_candidates=n_lm),
        format_validation=dict(validator="scripts/validate_submission.py", validator_pass=bool(ok),
                               finite_inside=int((tmpl > -1e30).sum()),
                               nan_outside=int((~np.isfinite(tmpl)).sum())),
        submission_name=sub_name[:140],
        note=note,
        zip_file=zp.name, zip_sha256=zp_sha,
        verdict=dict(promote=bool(promote and ok),
                     verdict="promote" if (promote and ok) else "negative/research",
                     format_valid=bool(ok),
                     holdout_beats_random=promote,
                     rationale="promote iff paired 95% CI vs same-mask random at equal budget is strictly positive AND format-valid."),
        ok_to_download_and_submit=bool(promote and ok),
    )
    (OUT_TIF.with_suffix(".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print("\n=== SUBMISSION READY ===")
    print(f"  TIF: docs/downloads/{OUT_TIF.name}")
    print(f"  ZIP: docs/downloads/{zp.name}")
    print(f"  NAME: {sub_name}")
    print(f"  NOTE: {note}")
    print(f"  OK-TO-SUBMIT: {receipt['ok_to_download_and_submit']}")


if __name__ == "__main__":
    main()
