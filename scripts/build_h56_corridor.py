#!/usr/bin/env python3
"""h56-corridor — emit in the 200–500 m correction belt around known catalogue traces,
weighted by scarp + mag gradient ridge strength concordance.

Hypothesis (H13, new for this run):
The dominant hidden-truth mass confirmed by the organizers (forum 11516) is
corrections/modifications within ~300 m of known traces. The corrections lane
documented 22% of records have a consistent offset 200–340 m from the catalogue,
with the DEM-scarp LiDAR-calibrated to ~0.29 px MAD. The physics arms H11/H12
scored BELOW random because they were forced to select off-catalogue everywhere,
which is dominated by non-fault edges (canyons, plutons). Restricting emission to
the annulus 200–500 m around the catalogue — exactly where corrections live —
focuses the detector on the region the organizers say contains truth, and
weights the emission by the same scarp×mag-ridge concordance used in the
corrections-lane holdout (which achieved HOLDOUT-DTI 0.31 on simulated
corrections).

This is a physically-grounded, prior-informed emission distinct from every
sibling that either: (a) emitted globally, (b) emitted ON catalogue, or
(c) emitted only on a handful of well-constrained offsets.
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
STEM = f"h56-corridor-b2to5-20261009-{TS}"
OUT_DIR = ROOT / "docs" / "downloads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TIF = OUT_DIR / f"{STEM}.tif"
SAMPLE = ROOT / "data" / "grid" / "sample_submission.tif"
CAT_PATH = ROOT / "data" / "grid" / "existing_faults.tif"
FEATURES = ROOT / "data" / "training_features.tif"

N_BUDGET = 37654
EXCLUDE_INNER_PX = 2     # 200 m inner mask (catalogue-adjacent dots are pure 0.2 penalty)
ANNULUS_OUTER_PX = 5     # 500 m outer (organizer's corrections window ≈ 300 m; +1 cell slack)
SIGMA_M = 300.0


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


def build_score(fields, footprint, sigma=SIGMA_M):
    """Hessian ridges on scarp/mag/gravity; geometric-mean rank concordance."""
    ridges = {k: transform.hessian_line(fields[k], footprint, sigma_m=sigma)
              for k in ("det_elev_slope", "tmi_hg", "iso_grav_anom_hg")}
    ranks = {k: transform.rank01(v, footprint) for k, v in ridges.items()}
    valid = footprint.copy()
    for r in ranks.values():
        valid &= np.isfinite(r)
    prod = np.ones(footprint.shape, dtype=np.float64)
    for r in ranks.values():
        prod *= np.where(valid, r.astype(np.float64), 1.0)
    score = np.full(footprint.shape, np.nan, dtype=np.float32)
    score[valid] = (prod[valid] ** (1.0/3)).astype(np.float32)
    score[~footprint] = np.nan
    return score, ridges, ranks


def annulus_mask(catalogue, footprint, inner_px, outer_px):
    inner = ndi.binary_dilation(catalogue, iterations=inner_px) & footprint
    outer = ndi.binary_dilation(catalogue, iterations=outer_px) & footprint
    return outer & ~inner


def emit_topk(score, allowed, k):
    s = np.where(allowed, score, -np.inf)
    flat = s.ravel()
    kk = min(k, int(allowed.sum()))
    idx = np.argpartition(flat, -kk)[-kk:]
    idx = idx[np.argsort(-flat[idx])]
    p = np.zeros(score.shape, dtype=np.float32)
    p[np.unravel_index(idx, score.shape)] = 1.0
    return p, kk


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    print(f"=== {STEM} ===")
    footprint, catalogue, profile, fields = load_stack()
    print(f"footprint {int(footprint.sum()):,}  catalogue {int(catalogue.sum()):,}")

    score, ridges, ranks = build_score(fields, footprint)
    print("score built")

    # ------- Holdout -------
    print("\n--- holdout ---")
    folds = ho.make_folds(catalogue, footprint, mode="hide", n_folds=4,
                          buffer_px=4, prevalence=0.00294, seed=0)
    terms = {}
    for arm in ("corridor", "random"):
        t = None
        for fi, fold in enumerate(folds):
            visible = fold["visible"] & footprint & fold["region"]
            if arm == "corridor":
                # Restrict emission to the annulus around VISIBLE faults (2-5 px)
                ann = annulus_mask(visible, footprint & fold["region"],
                                   EXCLUDE_INNER_PX, ANNULUS_OUTER_PX)
                allowed = ann & np.isfinite(score)
                p, _ = emit_topk(score, allowed, N_BUDGET)
                # NaN outside footprint
                p[~footprint] = np.nan
            else:
                ann = annulus_mask(visible, footprint & fold["region"],
                                   EXCLUDE_INNER_PX, ANNULUS_OUTER_PX)
                rng = np.random.default_rng(560204 + fi)
                yy, xx = np.nonzero(ann)
                n = yy.size
                pick = rng.choice(n, size=min(N_BUDGET, n), replace=False)
                p = np.zeros(footprint.shape, dtype=np.float32)
                p[yy[pick], xx[pick]] = 1.0
                p[~footprint] = np.nan
            res, blk = evaluate(np.nan_to_num(p, nan=0.0).astype(np.float32), fold, footprint)
            t = blk if t is None else np.concatenate([t, blk], axis=0)
        terms[f"{arm}@{N_BUDGET}"] = t
    summary = pooled_summary(terms, draws=1000, seed=520810, candidate=f"corridor@{N_BUDGET}")
    print(json.dumps(summary["scores"], indent=2))
    print("paired vs random (annulus):",
          json.dumps(summary["paired_differences"][f"random@{N_BUDGET}"], indent=2))

    # also compare against global random at same budget
    terms_g = {}
    for fi, fold in enumerate(folds):
        visible = fold["visible"] & footprint & fold["region"]
        near = ndi.binary_dilation(visible, iterations=EXCLUDE_INNER_PX) & footprint & fold["region"]
        allowed = (footprint & fold["region"] & ~near)
        rng = np.random.default_rng(560205 + fi)
        yy, xx = np.nonzero(allowed)
        n = yy.size
        pick = rng.choice(n, size=min(N_BUDGET, n), replace=False)
        p = np.zeros(footprint.shape, dtype=np.float32)
        p[yy[pick], xx[pick]] = 1.0
        p[~footprint] = np.nan
        res, blk = evaluate(np.nan_to_num(p, nan=0.0).astype(np.float32), fold, footprint)
        terms_g[f"gr"] = blk if fi == 0 else np.concatenate([terms_g[f"gr"], blk], axis=0)

    # ------- Final emission -------
    ann = annulus_mask(catalogue, footprint, EXCLUDE_INNER_PX, ANNULUS_OUTER_PX)
    allowed = ann & np.isfinite(score)
    pred, n_dots = emit_topk(score, allowed, N_BUDGET)
    pred[~footprint] = np.nan
    on_cat = int(((pred > 0) & catalogue).sum())
    inner = ndi.binary_dilation(catalogue, iterations=EXCLUDE_INNER_PX) & footprint
    inner_hits = int(((pred > 0) & inner).sum())
    print(f"\nfinal dots: {n_dots}, on-catalogue: {on_cat}, within {EXCLUDE_INNER_PX}px: {inner_hits}")
    print(f"annulus cells: {int(ann.sum()):,}")

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
    print("validate:", "PASS" if ok else "FAIL")

    note = (f"h56 corridor: 37654 dots in 200-500 m annulus around USGS/INGENIOUS catalogue, "
            f"weighted by Hessian-ridge concordance of det_elev_slope/tmi_hg/iso_grav_anom_hg")
    name = "GEMSDOE56-CORRIDOR-CONCORD"
    delta = summary["paired_differences"][f"random@{N_BUDGET}"]
    promote = bool(delta["ci95"][0] > 0 and ok)
    receipt = dict(
        generated_utc=TS,
        hypothesis="Corrections to existing fault traces (confirmed in-scope by forum 11516) lie within the 200-500 m annulus around the catalogue, where DEM-scarp and magnetic/gravity gradient ridges mark the refined trace position.",
        mechanism="Hessian bright-ridge (sigma=300 m) of det_elev_slope, tmi_hg, iso_grav_anom_hg; ECDF rank each to [0,1]; geometric-mean concordance; emission restricted to the annulus 2-5 px (200-500 m) from the USGS/INGENIOUS catalogue; top-k=37654 dots=1.0/0.0; NaN outside footprint.",
        named_non_fault_process="Erosional retreat of range fronts and wind/water gaps can create scarps 200-500 m from the mapped trace without representing a fault correction; the 1 m LiDAR calibration (MAD 0.29 px vs 100 m ridges) reduces but does not eliminate this confound.",
        holdout_dti=summary,
        raster=dict(file=OUT_TIF.name, sha256=sha, bytes=OUT_TIF.stat().st_size,
                    dots=n_dots, dots_on_catalogue=on_cat, dots_within_200m=inner_hits,
                    sigma_m=SIGMA_M, annulus_inner_px=EXCLUDE_INNER_PX,
                    annulus_outer_px=ANNULUS_OUTER_PX, k=N_BUDGET,
                    annulus_cells=int(ann.sum())),
        submission_name=name,
        note=note[:140],
        zip_file=zp.name, zip_sha256=zp_sha,
        validator_pass=ok,
        verdict=dict(value="promote" if promote else "negative/research",
                     promote=promote, format_valid=ok,
                     rationale="promote iff paired 95% CI vs same-annulus random at equal budget is strictly positive AND format-valid"),
    )
    (OUT_TIF.with_suffix(".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print("verdict:", receipt["verdict"])


if __name__ == "__main__":
    main()
