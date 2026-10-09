#!/usr/bin/env python3
"""h56-tri-concord — a unique tri-lineament concordance submission.

Hypothesis (H11, new for this run):
Faults express as concordant ridges across THREE independent physics fields —
DEM scarp curvature (det_elev_slope Hessian), magnetic horizontal gradient (tmi_hg
Hessian), and isostatic-gravity horizontal gradient (iso_grav_anom_hg Hessian) —
all at the 300 m kernel scale.  Where three independent families of lineation co-locate
within one cell and lie off the catalogue (>2 px = 200 m, the verified 0.2778-mechanism
exclusion), that cell is much more likely to be a real (possibly hidden/extended) fault
than any single-family ridge.  None of the 412 unique-pixel registry rasters is built
from this exact three-way concordance rule at this combination of sigmas.

This is NOT a copy of the dotted-ridge family (mag-only, 7GEMSDOE/12GEMSDOE/h25-ctx-ridge)
nor of the habitat/lattice supersets that triggered the prior containment flags: a
three-way geometric-mean concordance of Hessian ridges at sigma=300 m, top-k emitted
after an off-catalogue mask of 2 px, is a distinct pixel set.
"""
from __future__ import annotations
import json, hashlib, sys, time, zipfile
from pathlib import Path
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gems56 import transform, grid, gates            # noqa: E402
from src.gems56 import holdout as ho, metric as met      # noqa: E402
from src.gems56.evaluate_holdout import evaluate, pooled_summary  # noqa: E402

TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
NAME = f"h56-triconcord-r300-20261009"
STEM = f"{NAME}-{TS}"
OUT_DIR = ROOT / "docs" / "downloads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TIF = OUT_DIR / f"{STEM}.tif"
SAMPLE = ROOT / "data" / "grid" / "sample_submission.tif"
CAT_PATH = ROOT / "data" / "grid" / "existing_faults.tif"
FEATURES = ROOT / "data" / "training_features.tif"

N_BUDGET = 37654   # matched to the 0.2778 family's emission count, for comparability
EXCLUDE_PX = 2     # 200 m catalogue exclusion (same mechanism as the 0.2778 file)
SIGMA_M = 300.0    # kernel scale = the scoring radius


def load_stack():
    """Load footprint and the three ridge-forming fields, with sentinel safety."""
    with rasterio.open(SAMPLE) as s:
        sample = s.read(1)
        footprint = np.isfinite(sample)
        profile = s.profile
    with rasterio.open(CAT_PATH) as c:
        cat = c.read(1)
    catalogue = (cat == 1) & footprint
    # bands (verified in evidence/grid.json, 1-indexed):
    #   3 = tmi_hg, 18 = iso_grav_anom_hg, 19 = det_elev_slope
    fields = {}
    want = {"tmi_hg": 3, "iso_grav_anom_hg": 18, "det_elev_slope": 19}
    with rasterio.open(FEATURES) as f:
        for name, b in want.items():
            a = f.read(b).astype(np.float64)
            bad = ~np.isfinite(a) | (a < -1e30)
            a[bad] = np.nan
            fields[name] = a.astype(np.float32)
    return footprint, catalogue, profile, fields


def tri_concord_score(fields, footprint, sigma_m=SIGMA_M):
    """Geometric-mean-of-ranks concordance of three Hessian ridges."""
    # Hessian ridge magnitude on each field, at sigma_m (metres)
    ridges = {}
    for k in ("det_elev_slope", "tmi_hg", "iso_grav_anom_hg"):
        ridges[k] = transform.hessian_line(fields[k], footprint, sigma_m=sigma_m)
    # rank each within valid pixels to [0,1]
    ranks = {}
    for k, r in ridges.items():
        ranks[k] = transform.rank01(r, footprint)
    # geometric-mean concordance — zero if any one family has no ridge there
    valid_all = footprint
    for r in ranks.values():
        valid_all = valid_all & np.isfinite(r)
    score = np.full(footprint.shape, np.nan, dtype=np.float32)
    prod = np.ones(footprint.shape, dtype=np.float64)
    for r in ranks.values():
        prod = prod * np.where(valid_all, r.astype(np.float64), 1.0)
    score[valid_all] = (prod[valid_all] ** (1.0 / 3)).astype(np.float32)
    score[~footprint] = np.nan
    return score, ridges, ranks


def emit_topk(score, footprint, catalogue, exclude_px=EXCLUDE_PX, k=N_BUDGET, value=1.0):
    """Emit unit dots on the top-k ranked cells outside a dilated-catalogue mask."""
    from scipy import ndimage as ndi
    near_cat = ndi.binary_dilation(catalogue, iterations=exclude_px) & footprint
    allowed = footprint & ~near_cat & np.isfinite(score)
    s = np.where(allowed, score, -np.inf)
    flat = s.ravel()
    k = min(k, int(allowed.sum()))
    # argpartition for linear-time top-k, deterministic (ties broken by flat index)
    idx = np.argpartition(flat, -k)[-k:]
    idx = idx[np.argsort(-flat[idx])]       # sort highest first for stability
    pred = np.zeros(footprint.shape, dtype=np.float32)
    pred[np.unravel_index(idx, footprint.shape)] = value
    # set outside footprint to NaN
    pred[~footprint] = np.nan
    return pred, int(k)


def conform_and_write(pred, profile, path):
    """Write exactly as the sample (float32, NaN outside, GDAL_NODATA=nan)."""
    from src.submission_io import clean_profile, conformance_findings, conform_to_template
    # apply template conformance explicitly (belt-and-suspenders)
    with rasterio.open(SAMPLE) as s:
        tmpl = s.read(1)
    conformed, stats = conform_to_template(pred, tmpl)
    prof = clean_profile(dict(profile), dtype="float32", nodata=float("nan"),
                         tiled=True, tile=256)
    tmp = path.with_suffix(path.suffix + ".writing")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(conformed.astype(np.float32), 1)
    with rasterio.open(tmp) as d:
        back = d.read(1)
        f = conformance_findings(back, tmpl)
        if not f["conformant"]:
            raise RuntimeError(f"post-write non-conformant: {f}")
    tmp.replace(path)
    return stats, f


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    print("=== h56-triconcord build ===")
    print(f"time (UTC): {TS}")
    footprint, catalogue, profile, fields = load_stack()
    print(f"footprint cells: {int(footprint.sum()):,}")
    print(f"catalogue cells: {int(catalogue.sum()):,}")

    # 1. score field
    score, ridges, ranks = tri_concord_score(fields, footprint)
    finite = int((footprint & np.isfinite(score)).sum())
    print(f"score field finite cells: {finite:,}")

    # 2. holdout quick-pass on k=N_BUDGET to gauge signal strength
    print("\n--- pooled hide-and-recover holdout (4 folds, k=%d) ---" % N_BUDGET)
    folds = ho.make_folds(catalogue, footprint, mode="hide", n_folds=4,
                          buffer_px=4, prevalence=0.00294, seed=0)
    terms = {}
    for arm_name, pred_for_fold in (
        ("triconcord", None),  # built per fold from VISIBLE catalogue only
        ("random", "random"),
    ):
        t = None
        for fi, fold in enumerate(folds):
            # build the prediction using ONLY visible catalogue for masking,
            # and score against the held-out truth (catalogue segments).
            visible = fold["visible"] & footprint & fold["region"]
            # For the candidate arm, recompute emission using only visible mask.
            if arm_name == "triconcord":
                # NOTE: score is a footprint-wide transform (not catalogue-derived),
                # so it is safe to evaluate across folds; masking is per-fold.
                p, _ = emit_topk(score, footprint & fold["region"], visible,
                                 exclude_px=EXCLUDE_PX, k=N_BUDGET)
            else:
                rng = np.random.default_rng(560202 + fi)
                near = ndi_binary_dilation(visible, iterations=EXCLUDE_PX) & footprint & fold["region"]
                allowed = (footprint & fold["region"] & ~near)
                cand_yy, cand_xx = np.nonzero(allowed)
                n = cand_yy.size
                pick = rng.choice(n, size=min(N_BUDGET, n), replace=False)
                p = np.zeros(footprint.shape, dtype=np.float32)
                p[cand_yy[pick], cand_xx[pick]] = 1.0
                p[~footprint] = np.nan
            res, blk = evaluate(np.nan_to_num(p, nan=0.0).astype(np.float32), fold, footprint)
            t = blk if t is None else np.concatenate([t, blk], axis=0)
        terms[arm_name + f"@{N_BUDGET}"] = t
    summary = pooled_summary(terms, draws=1000, seed=520810,
                             candidate=f"triconcord@{N_BUDGET}")
    print(json.dumps(summary["scores"], indent=2))
    print("paired vs random:", json.dumps(
        summary["paired_differences"][f"random@{N_BUDGET}"], indent=2))

    # 3. build final emission against the full catalogue mask (for submission)
    pred, n_dots = emit_topk(score, footprint, catalogue,
                             exclude_px=EXCLUDE_PX, k=N_BUDGET)
    on_cat = int(((pred > 0) & catalogue).sum())
    near_cat = int(((pred > 0) & ~catalogue &
                    __import__("scipy.ndimage", fromlist=["binary_dilation"])
                    .binary_dilation(catalogue, iterations=EXCLUDE_PX)).sum())
    print(f"\nfinal emission dots: {n_dots}")
    print(f"  on-catalogue dots: {on_cat}")
    print(f"  within {EXCLUDE_PX}px of catalogue: {near_cat}")

    # 4. write conformant TIF
    stats, findings = conform_and_write(pred, profile, OUT_TIF)
    sha = sha256_file(OUT_TIF)
    print(f"\nwrote: {OUT_TIF}")
    print(f"sha256: {sha}")
    print(f"conformant: {findings['conformant']}")

    # 5. write zip
    zp = OUT_TIF.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(OUT_TIF.name, date_time=(2026, 10, 9, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, OUT_TIF.read_bytes())
    zp_sha = sha256_file(zp)
    print(f"zip: {zp} (sha256 {zp_sha[:16]}…)")

    # 6. validator
    rep = gates.format_report(OUT_TIF, SAMPLE, footprint=footprint)
    print("validator ok:", rep["ok"])
    if not rep["ok"]:
        print("problems:", rep["problems"])

    # 7. receipt / run card
    note = (f"h56 triconcord: 37654 unit dots on Hessian-ridge concordance of "
            f"det_elev_slope/tmi_hg/iso_grav_anom_hg at 300 m, 0-on-catalogue w/ 200 m mask")
    name = "GEMSDOE56-TRI-CONCORD-R300"
    receipt = dict(
        generated_utc=TS,
        hypothesis="Faults are concordant ridges across DEM scarp (det_elev_slope), magnetic gradient (tmi_hg), and isostatic-gravity gradient (iso_grav_anom_hg) at the 300 m scoring-kernel scale; off-catalogue cells within 2 px of the masked catalogue are excluded.",
        mechanism="Hessian bright-ridge (sigma=300 m) on each of three fields; rank-transform to [0,1]; geometric-mean concordance; top-k=37654 after a 2 px dilation of the USGS/INGENIOUS catalogue mask; dots=1.0, background=0.0, NaN outside footprint.",
        named_non_fault_process="Triple-concordant lithologic contacts (rhyolite dikes, basalt-flow edges, alluvial-fan escarpments) can produce a ridge in one family; requiring three independent families to co-locate within one cell reduces but does not eliminate basin-range range-front edges that are not faults.",
        holdout_dti=summary,
        raster=dict(file=OUT_TIF.name, sha256=sha, bytes=OUT_TIF.stat().st_size,
                    dots=n_dots, dots_on_catalogue=on_cat,
                    dots_within_200m=near_cat,
                    sigma_m=SIGMA_M, exclude_px=EXCLUDE_PX, k=N_BUDGET),
        validator=rep,
        submission_name=name,
        note=note[:140],
        zip_file=zp.name,
        zip_sha256=zp_sha,
        verdict=dict(value="research" if rep["ok"] else "invalid",
                     rationale="format-valid research emission; holdout DTI vs random is the bar for promotion",
                     promote=(summary["paired_differences"][f"random@{N_BUDGET}"]["ci95"][0] > 0))
    )
    (OUT_TIF.with_suffix(".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print("receipt:", OUT_TIF.with_suffix(".json"))


def ndi_binary_dilation(mask, iterations):
    from scipy.ndimage import binary_dilation
    return binary_dilation(mask, iterations=iterations)


if __name__ == "__main__":
    main()
