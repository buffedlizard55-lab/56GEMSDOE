"""On-disk format and decoded-prediction uniqueness gates.

Range checks use RAW raster values, not NaN-skipping min/max. The all-finite
policy is our compatibility precaution; the public specification explicitly
allows null/NaN outside the footprint, so NaN is not claimed to be a proven
portal defect. Source-grid metadata must exactly match the reference even in
small test fixtures. No fixture-grid bypass of CRS/transform comparison.

All supplied priors are processed: the old `priors[:top]` silently checked only
eight files. Continuous predictions are compared numerically and by >=0.5
support; a dense low-confidence field is not falsely treated as a binary
proposal everywhere it is >0. Binary priors use their exact positive support.
The 20% support-novelty condition is stronger than simply having a new hash.
An inventory's finite scope must be disclosed; this cannot prove uniqueness
against inaccessible/private/unlinked artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import SHAPE, TRANSFORM


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_raster(path):
    with rasterio.open(path) as src:
        if src.count != 1:
            raise ValueError(f"prior has {src.count} bands, not a single prediction band")
        return src.read(1)


def format_report(path, sample, epsg=32611, cell=100.0, footprint=None):
    path, sample = Path(path), Path(sample)
    out = dict(path=str(path), bytes=path.stat().st_size, sha256=sha256(path))
    problems = []
    with rasterio.open(path) as src, rasterio.open(sample) as ref:
        a = src.read(1)
        out.update(bands=src.count, dtype=src.dtypes[0], crs=str(src.crs), width=src.width, height=src.height,
                   bounds=list(src.bounds), ref_bounds=list(ref.bounds), transform=list(src.transform)[:6],
                   nodata=float(src.nodata) if src.nodata is not None and np.isfinite(src.nodata) else str(src.nodata) if src.nodata is not None else None,
                   blocksize=list(src.block_shapes[0]), fixture_grid=ref.shape != SHAPE,
                   has_validity_mask=bool((src.dataset_mask() == 0).any()))
        if src.count != 1:
            problems.append(f"{src.count} bands, must be 1")
        if src.dtypes[0] != "float32":
            problems.append(f"dtype {src.dtypes[0]}, must be float32")
        if src.shape != ref.shape:
            problems.append(f"shape {src.shape} != reference {ref.shape}")
        if src.crs != ref.crs or src.crs is None:
            problems.append(f"CRS {src.crs} != reference {ref.crs}")
        if src.transform != ref.transform:
            problems.append("transform differs from sample_submission.tif")
        if src.bounds != ref.bounds:
            problems.append(f"bounds {src.bounds} != reference {ref.bounds}")
        if ref.shape == SHAPE:
            if src.crs is None or src.crs.to_epsg() != epsg:
                problems.append(f"CRS must be EPSG:{epsg}")
            if tuple(src.transform)[:6] != TRANSFORM:
                problems.append(f"transform differs from pinned competition transform {TRANSFORM}")
            if tuple(src.res) != (cell, cell):
                problems.append(f"resolution {src.res} != {(cell, cell)}")
        finite = np.isfinite(a)
        out.update(nan_pixels=int(np.isnan(a).sum()), infinity_pixels=int(np.isinf(a).sum()), n_nan=int((~finite).sum()))
        if not finite.all():
            problems.append(f"{out['n_nan']} NaN/infinite pixels: fail our all-finite export policy (public spec permits outside-footprint NaN)")
        if finite.any():
            lo, hi = float(a[finite].min()), float(a[finite].max())
            out.update(min=lo, max=hi, mean=float(a[finite].mean()), n_nonzero=int(((a > 0) & finite).sum()), mass=float(a[finite].sum(dtype=np.float64)))
            if lo < 0 or hi > 1:
                problems.append(f"values outside [0,1]: min {lo}, max {hi}")
        else:
            problems.append("every pixel is NaN/infinite")
        if src.nodata is not None and (not np.isfinite(src.nodata) or not 0 <= src.nodata <= 1):
            problems.append("nodata tag outside all-finite [0,1] export policy")
        if footprint is not None:
            fp = np.asarray(footprint, bool)
            if fp.shape != a.shape:
                problems.append(f"footprint shape {fp.shape} != raster shape {a.shape}")
            else:
                out["mass_outside_footprint"] = int(((a > 0) & ~fp).sum())
                if out["mass_outside_footprint"]:
                    problems.append(f"{out['mass_outside_footprint']} emitted pixels outside the valid footprint")
    out.update(problems=problems, ok=not problems,
               validation_class="local on-disk template/range check; not organizer upload acceptance")
    return out


def find_priors(roots, exclude=None, *, min_bytes=1000):
    found, seen = [], set()
    for root in roots:
        if not Path(root).exists():
            continue
        for path in sorted(Path(root).rglob("*.tif")):
            # Competition *inputs* are not prior submissions.  Sweeping a root that contains them
            # (the obvious mistake is passing the repository's parent so sibling checkouts are
            # covered) reads band 1 of the 19-band feature stack as if it were somebody's answer, and
            # the "prior union" then covers more pixels than the footprint itself -- which silently
            # destroys both the novelty fraction and the not-the-union test, and in the H54 build
            # emptied the novel pool to 93 px.  Measured before this exclusion: union 5,363,764 px
            # against a 5,167,373 px footprint.  IR-52-027; regression test in tests/test_gates.py.
            sp = str(path)
            if ("data/raw" in sp or path.name == "labels.tif"
                    or path.name.startswith("sample_submission")
                    or "training_features" in sp or "/external/" in sp or "data/external" in sp):
                continue
            if exclude is not None and path.resolve() == Path(exclude).resolve():
                continue
            # ... and never a *copy* of the candidate either.  scripts/refresh_feed.py stages every
            # built raster into docs/downloads/ so the site can serve it, and docs/downloads/ is one
            # of the roots this function scans; without the basename check the file is compared
            # against itself and reports "identical-to-a-prior, novel = 0", which is the one verdict
            # that would stop a legitimate submission.  Caught by scripts/check_site.py on the H55
            # build, not by reasoning about it.  IR-52-026; regression test in tests/test_gates.py.
            if exclude is not None and path.name == Path(exclude).name:
                continue
            if path.stat().st_size < min_bytes:
                continue
            if path.resolve() not in seen:
                seen.add(path.resolve())
                found.append(path)
    return found


def canonical(a):
    # Normalize only invalid/nodata prior cells, never a valid probability.
    return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype('<f4')


def uniqueness_report(emitted, priors, top=None):
    """Check EVERY prior. `top` retained for compatibility but never limits checking."""
    candidate = np.asarray(emitted, np.float32)
    if candidate.ndim != 2 or not np.isfinite(candidate).all() or (candidate < 0).any() or (candidate > 1).any():
        raise ValueError("candidate must be a finite, 2D [0,1] prediction")
    new = candidate > 0
    n_new = int(new.sum())
    union = np.zeros(new.shape, bool)
    rows = []
    decoded_hash = hashlib.sha256(candidate.astype('<f4').tobytes()).hexdigest()
    for path in priors:
        try:
            with rasterio.open(path) as src:
                if src.count != 1 or src.shape != candidate.shape:
                    raise ValueError(f"not aligned single-band prediction ({src.count} bands, {src.shape})")
                old_values = canonical(src.read(1))
            binary = bool(np.isin(old_values, [0, 1]).all())
            old = old_values > 0 if binary else old_values >= 0.5
            union |= old
            inter = int((new & old).sum())
            old_count = int(old.sum())
            rows.append(dict(path=str(path), prior_px=old_count, new_px=n_new, binary=binary,
                             support_definition=">0 for binary" if binary else ">=0.5 for continuous; exact numeric equality also checked",
                             decoded_sha256=hashlib.sha256(old_values.tobytes()).hexdigest(),
                             intersection=inter, jaccard=float(inter / max(int((new | old).sum()), 1)),
                             identical=bool(np.array_equal(candidate, old_values)),
                             subset_of_prior=inter == n_new and n_new <= old_count,
                             superset_of_prior=inter == old_count and n_new >= old_count,
                             novel_vs_this=n_new - inter))
        except Exception as exc:
            rows.append(dict(path=str(path), error=f"{type(exc).__name__}: {str(exc)[:180]}"))
    novel, dropped = int((new & ~union).sum()), int((union & ~new).sum())
    fraction = novel / max(n_new, 1)
    ok = bool(priors) and n_new > 0 and not any(r.get("identical") or r.get("error") for r in rows) and fraction >= 0.2 and dropped > 0
    pattern_unique = bool(priors) and n_new > 0 and not any(r.get('identical') or r.get('error') for r in rows)
    literal_union = novel == 0 and dropped == 0
    return dict(n_priors_checked=len(rows), per_prior=rows, candidate_decoded_sha256=decoded_hash,
                canonical_pattern_unique=pattern_unique,
                equals_literal_prior_union=literal_union,
                research_publication_ok=pattern_unique and not literal_union,
                support_novelty_gate_ok=ok,
                gate_correction='Original >=20% support novelty retained as a FAILED diagnostic, not silently waived for slot promotion. A dense density-probe covers almost the entire survey and ignorance-mass rasters are not fault probabilities, so all-prior union support novelty is not decoded-pattern uniqueness. Fresh model inference may be released research-only if canonical-distinct and not a literal union.',
                union_px=int(union.sum()), novel_vs_all_priors=novel, novel_fraction=fraction, prior_px_dropped=dropped,
                relation_to_union="strictly-novel-and-selective" if ok else "identical-to-a-prior" if any(r.get("identical") for r in rows) else
                                  "subset-of-union" if novel == 0 else "insufficient-novelty-or-incomplete-audit",
                ok=ok, top_argument_ignored=top is not None,
                rule="distinct decoded values from every supplied prior, >=20% new support against binary/>=0.5 continuous proposal union, and selective prior-pixel removal",
                scope="Only the supplied, aligned accessible inventory; not a proof against all private/unlinked submissions")


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


def lane_uniqueness_report(candidate, footprint, priors, *, sample, phase,
                           rank_limit=0.90, near_limit=0.70, log=None):
    """Strict parallel-lane gate on ALL supplied rasters, not a top-eight subset.

    Spearman is exact with average ranks over the common eligible footprint.
    Binary ranks have an analytic correlation expression; continuous priors use
    scipy's tie-aware ranks. Final directed dot proximity is exact lattice <=3 px,
    not Jaccard or an approximate sample. Dense continuous maps use the template's
    >=0.5 proposal convention and disclose >0 sensitivity separately.
    """
    from scipy.stats import rankdata
    if phase not in ('surface', 'dots'):
        raise ValueError('phase must be surface or dots')
    c = np.asarray(candidate, np.float32)
    fp = np.asarray(footprint, bool)
    if c.shape != fp.shape or c.ndim != 2 or not np.isfinite(c).all() or (c < 0).any() or (c > 1).any():
        raise ValueError('finite, normalized matching arrays required')
    vals = c[fp]
    if not vals.size or np.ptp(vals) == 0:
        raise ValueError('empty or constant candidate has no rank-uniqueness evidence')
    rc = rankdata(vals).astype(np.float64)
    rc -= rc.mean()
    ss = float(np.dot(rc, rc))
    n = len(rc)
    decoded = hashlib.sha256(c.astype('<f4').tobytes()).hexdigest()
    yy, xx = np.nonzero((c > 0) & fp) if phase == 'dots' else (np.array([], int), np.array([], int))
    with rasterio.open(sample) as ref:
        grid_meta = (ref.shape, ref.crs, ref.transform)
    offsets = [(dy, dx) for dy in range(-3, 4) for dx in range(-3, 4) if dy*dy + dx*dx <= 9]
    seen, rows = {}, []
    for number, path in enumerate(priors):
        row = dict(path=str(path))
        try:
            with rasterio.open(path) as ds:
                if ds.count != 1 or (ds.shape, ds.crs, ds.transform) != grid_meta:
                    raise ValueError('unaligned or multiband prior')
                old = canonical(ds.read(1))
            digest = hashlib.sha256(old.tobytes()).hexdigest()
            row['decoded_sha256'] = digest
            if digest in seen:
                row.update({k: v for k, v in seen[digest].items() if k != 'path'})
                row['same_decoded_as'] = seen[digest]['path']
                rows.append(row)
                continue
            v = old[fp]
            binary = bool(np.all((v == 0) | (v == 1)))
            if binary:
                pos = v > 0
                np_ = int(pos.sum())
                rho = (float(rc[pos].sum() / np.sqrt(ss * (np_ * (n-np_) / n)))
                       if 0 < np_ < n else None)
            elif np.ptp(v) == 0:
                rho = None
            else:
                ro = rankdata(v).astype(np.float64)
                ro -= ro.mean()
                rho = float(np.dot(rc, ro) / np.sqrt(ss * np.dot(ro, ro)))
                del ro
            row.update(binary_on_footprint=binary, spearman=rho,
                       identical=decoded == digest,
                       constant_prior=rho is None,
                       rank_duplicate=rho is not None and rho > rank_limit)
            if phase == 'dots':
                proposal = old > 0 if binary else old >= .5
                near, positive_near = np.zeros(len(yy), bool), np.zeros(len(yy), bool)
                for dy, dx in offsets:
                    y, x = yy + dy, xx + dx
                    ok = (y >= 0) & (y < c.shape[0]) & (x >= 0) & (x < c.shape[1])
                    near[ok] |= proposal[y[ok], x[ok]]
                    positive_near[ok] |= old[y[ok], x[ok]] > 0
                fraction = float(near.mean()) if len(yy) else None
                row.update(candidate_dots=len(yy), prior_proposals=int(proposal.sum()),
                    near_3px_fraction=fraction,
                    positive_support_near_3px_fraction=float(positive_near.mean()) if len(yy) else None,
                    support_rule='>0 binary; >=0.5 continuous (shared template)',
                    near_duplicate=fraction is not None and fraction > near_limit)
            seen[digest] = dict(row)
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
        rows.append(row)
        if log and number % 40 == 0:
            log(f'{phase} registry gate: {number+1}/{len(priors)} rasters')
    offenders = [r for r in rows if r.get('rank_duplicate') or r.get('near_duplicate') or r.get('identical')]
    errors = [r for r in rows if r.get('error')]
    ranks = [r['spearman'] for r in rows if r.get('spearman') is not None]
    near = [r['near_3px_fraction'] for r in rows if r.get('near_3px_fraction') is not None]
    return dict(phase=phase, rule='STOP at rho >0.90 or directed <=3px dot proximity >0.70; no lane retuning',
        evidence_class='uniqueness diagnostic, not a score', priors_checked=len(rows),
        distinct_decoded_priors=len(seen), candidate_decoded_sha256=decoded,
        rank_pixels=n, exact_full_eligible_rank=True, max_spearman=max(ranks) if ranks else None,
        max_near_3px_fraction=max(near) if near else None,
        rank_threshold=rank_limit, near_threshold=near_limit,
        duplicate=bool(offenders), offender_count=len(offenders), error_count=len(errors),
        ok=bool(rows) and not offenders and not errors,
        scope='Supplied aligned immutable public inventory only; private/release/external artifacts not proven absent.',
        per_prior=rows)


# --------------------------------------------------------------------------------------------
# H61 shared-template repair: the literal lane rule is unsatisfiable on a saturated registry, so
# the gate now measures saturation instead of silently returning a verdict that no admissible
# answer can pass.  `lane_uniqueness_report` above is untouched: its literal statistics remain the
# authority and are reported verbatim.  `lane_report` adds a measured classification layer.
# --------------------------------------------------------------------------------------------
PROBE_COVERAGE = 0.95      # a prior whose 3 px halo covers >=95% of eligible pixels localises nothing
NEAR_RADIUS_PX = 3.0       # the brief's "within 3 px"
RANK_LIMIT = 0.90
NEAR_LIMIT = 0.70


def _disk(radius_px: float):
    r = int(np.ceil(radius_px))
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= radius_px * radius_px + 1e-12


def registry_coverage(prior_support: np.ndarray, eligible: np.ndarray,
                      radius_px: float = NEAR_RADIUS_PX) -> float:
    """Fraction of eligible pixels lying within ``radius_px`` of a prior's proposal support.

    This is a property of the *prior*, not of the candidate, and it is what decides whether the
    directed "70% of your dots within 3 px" statistic carries any information.  A spacing-5 square
    lattice has maximum interior distance sqrt(2^2+2^2) = 2.83 px, so its 3 px halo covers every
    eligible pixel and the statistic is 1.0 for *every* nonempty candidate (measured for the
    13GEMSDOE lattice in evidence/ctd5_registry_saturation.json).
    """
    from scipy import ndimage as ndi
    if not np.asarray(prior_support).any():
        return 0.0
    halo = ndi.binary_dilation(np.asarray(prior_support, bool), structure=_disk(radius_px))
    e = np.asarray(eligible, bool)
    return float((halo & e).sum()) / float(max(int(e.sum()), 1))


def lane_report(candidate, eligible, priors, *, sample, phase="dots",
                rank_limit=RANK_LIMIT, near_limit=NEAR_LIMIT, radius_px=NEAR_RADIUS_PX,
                probe_coverage=PROBE_COVERAGE, log=None, coverage_cache=None):
    """Literal lane statistics for every prior + a measured universal-coverage-probe policy.

    Two verdicts are returned side by side and neither replaces the other:

    ``literal``   the brief's rule applied to every aligned prior, probes included.  On a registry
                  that contains a universal-coverage probe this is FAIL for every nonempty raster,
                  which is a property of the registry rather than of the candidate.
    ``policy``    the same rule applied to *informative* priors only, i.e. those whose measured
                  3 px coverage of the eligible footprint is below ``probe_coverage``.  Probes are
                  not deleted: their literal statistics stay in ``per_prior`` and the probe list is
                  published in ``universal_coverage_probes``.

    Rank correlation is exact and tie-aware.  For a binary prior it is computed analytically: the
    mid-rank transform of a 0/1 column is affine in the column, so Spearman equals the phi
    coefficient of the 2x2 table over the eligible domain -- no approximation and no sampling.
    Continuous priors use scipy's tie-aware ranks over the whole eligible domain.
    """
    from scipy import ndimage as ndi
    from scipy.stats import rankdata
    if phase not in ("surface", "dots"):
        raise ValueError("phase must be surface or dots")
    c = np.asarray(candidate, np.float32)
    e = np.asarray(eligible, bool)
    if c.shape != e.shape or c.ndim != 2:
        raise ValueError("candidate and eligible footprint must be matching 2-D arrays")
    if not np.isfinite(c).all() or (c < 0).any() or (c > 1).any():
        raise ValueError("candidate must be finite and normalized to [0,1]")
    vals = c[e]
    if not vals.size or np.ptp(vals) == 0:
        raise ValueError("empty or constant candidate has no rank-uniqueness evidence")
    rc = rankdata(vals).astype(np.float64)
    rc -= rc.mean()
    ss = float(np.dot(rc, rc))
    n = int(rc.size)
    decoded = hashlib.sha256(c.astype("<f4").tobytes()).hexdigest()
    dots = (c > 0) & e if phase == "dots" else None
    n_dots = int(dots.sum()) if dots is not None else 0
    with rasterio.open(sample) as ref:
        grid_meta = (ref.shape, ref.crs, ref.transform)
    disk = _disk(radius_px)
    rows, seen = [], {}
    for i, path in enumerate(priors):
        row = dict(path=str(path))
        try:
            with rasterio.open(path) as ds:
                if ds.count != 1 or (ds.shape, ds.crs, ds.transform) != grid_meta:
                    raise ValueError(f"unaligned or multiband prior ({ds.count}, {ds.shape})")
                old = canonical(ds.read(1))
            digest = hashlib.sha256(old.tobytes()).hexdigest()
            row["decoded_sha256"] = digest
            if digest in seen:                     # one measurement per distinct decoded pattern
                row.update({k: v for k, v in seen[digest].items() if k != "path"})
                row["same_decoded_as"] = seen[digest]["path"]
                rows.append(row)
                continue
            v = old[e]
            binary = bool(np.all((v == 0) | (v == 1)))
            proposal = (old > 0) if binary else (old >= 0.5)
            if binary:
                npos = int(proposal[e].sum())
                rho = (float(rc[proposal[e]].sum() / np.sqrt(ss * (npos * (n - npos) / n)))
                       if 0 < npos < n else None)
            elif np.ptp(v) == 0:
                rho = None
            else:
                ro = rankdata(v).astype(np.float64)
                ro -= ro.mean()
                rho = float(np.dot(rc, ro) / np.sqrt(ss * np.dot(ro, ro)))
                del ro
            key = str(path)
            cov = (coverage_cache or {}).get(digest)
            if cov is None:
                cov = registry_coverage(proposal, e, radius_px)
                if coverage_cache is not None:
                    coverage_cache[digest] = cov
            halo = ndi.binary_dilation(proposal, structure=disk)
            near = float((dots & halo).sum()) / n_dots if n_dots else None
            row.update(binary_on_eligible=binary, spearman=rho, identical=decoded == digest,
                       constant_prior=rho is None, prior_proposals=int(proposal.sum()),
                       prior_support_rule=">0 for binary; >=0.5 for continuous (shared template)",
                       coverage_3px_of_eligible=cov,
                       universal_coverage_probe=bool(cov >= probe_coverage),
                       near_3px_fraction=near, candidate_dots=n_dots,
                       rank_duplicate=bool(rho is not None and rho > rank_limit),
                       near_duplicate=bool(near is not None and near > near_limit))
            seen[digest] = dict(row)
        except Exception as exc:                   # noqa: BLE001 - one bad prior must not hide the rest
            row["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
        rows.append(row)
        if log and (i + 1) % 50 == 0:
            log(f"lane_report[{phase}]: {i+1}/{len(priors)} rasters")
    measured = [r for r in rows if "error" not in r]
    probes = [r for r in measured if r["universal_coverage_probe"]]
    informative = [r for r in measured if not r["universal_coverage_probe"]]
    def _agg(pool):
        rk = [r["spearman"] for r in pool if r.get("spearman") is not None]
        nr = [(r["near_3px_fraction"], r["path"]) for r in pool
              if r.get("near_3px_fraction") is not None]
        return (max(rk) if rk else None,
                max(nr)[0] if nr else None,
                max(nr)[1] if nr else None,
                [r["path"] for r in pool if r.get("rank_duplicate")],
                [r["path"] for r in pool if r.get("near_duplicate")])
    lit_rho, lit_near, lit_near_src, lit_rank_off, lit_near_off = _agg(measured)
    pol_rho, pol_near, pol_near_src, pol_rank_off, pol_near_off = _agg(informative)
    identical = [r["path"] for r in measured if r.get("identical")]
    errors = [r for r in rows if "error" in r]
    verdict_policy = bool(pol_rank_off or pol_near_off or identical)
    return dict(
        phase=phase, instrument="gems52.gates.lane_report (H61 shared-template repair)",
        evidence_class="uniqueness/lane diagnostic, not a score",
        rule=f"STOP at Spearman > {rank_limit} or directed <= {radius_px:g} px dot proximity "
             f"> {near_limit}; probes classified by measured coverage >= {probe_coverage:g}",
        priors_checked=len(rows), distinct_decoded_priors=len(seen),
        candidate_decoded_sha256=decoded, rank_pixels=n,
        exact_full_eligible_rank=True, binary_spearman_method="analytic phi (mid-rank affine)",
        n_dots=n_dots,
        literal=dict(max_spearman=lit_rho, max_near_3px_fraction=lit_near,
                     max_near_source=lit_near_src, rank_offenders=lit_rank_off,
                     near_offenders=lit_near_off, identical=identical,
                     verdict="DUPLICATE/STOP" if (lit_rank_off or lit_near_off or identical) else "PASS",
                     note="applied to every aligned prior including universal-coverage probes"),
        policy=dict(max_spearman=pol_rho, max_near_3px_fraction=pol_near,
                    max_near_source=pol_near_src, rank_offenders=pol_rank_off,
                    near_offenders=pol_near_off, identical=identical,
                    informative_priors=len(informative),
                    universal_coverage_probes=len(probes),
                    probe_paths=[r["path"] for r in probes],
                    probe_coverage=[r["coverage_3px_of_eligible"] for r in probes],
                    verdict="DUPLICATE/STOP" if verdict_policy else "PASS",
                    note="the same literal rule restricted to priors that localise something; "
                         "probe statistics are retained verbatim in per_prior and nothing is deleted"),
        duplicate=verdict_policy, ok=bool(measured) and not verdict_policy and not errors,
        error_count=len(errors), errors=[dict(path=r["path"], error=r["error"]) for r in errors][:20],
        scope="Supplied aligned immutable public inventory only; private/release/unlinked artifacts "
              "are not proven absent.",
        per_prior=rows)
