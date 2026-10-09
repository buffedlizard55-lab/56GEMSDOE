#!/usr/bin/env python3
"""E3 -- build the corrections-lane GeoTIFF(s), validate, and screen for lane uniqueness.

The default build has exactly one arm: **primary (>= 2 px = 200 m)**, the brief's correction threshold.
There is no sub-threshold sensitivity output in the default path. If no corridor passes the calibrated
strength and consistency gates, no corrected-trace dots are emitted; do not relax the threshold merely
to create a non-empty raster or satisfy a file-deliverable request.

The rule, fixed before counting pixels
--------------------------------------
1. For every catalogue pixel, measure the perpendicular offset to the nearest *qualified* DEM crest
   (max -d2z/dn2 of det_elev) and magnetic ridge (max |tmi_hg|). Qualified = prominence >= 0.25 of the
   peak's own height above the profile minimum AND height >= the 90th percentile of the same statistic
   measured at random traceless points (scripts/lidar_calibration.py). No tuned thresholds: the floor is
   calibrated on data.
2. A pixel is a correction candidate when |dem| and |mag| both clear the gate, agree in sign and lie
   within 1.5 px of each other. The joint offset is their mean.
3. Drop candidates with < 3 qualified candidates among their 8 neighbours: an isolated flip is scatter.
4. Emit 1.0 on the cell the joint offset points at, thinned to >= 200 m along strike, never on a
   catalogue pixel -- E2 measured the whole visible catalogue at DTI 0.00000 exactly because the
   organizer mask (thread 11516 post #2) deletes mass that sits on it.

Reproduce: python scripts/build_corrections_submission.py [registry_dir]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems56 import corrections as C, gates, lane_inputs as L, submission_writer as SW  # noqa: E402

CORR_PX, MIN_CLUSTER, MIN_SPACING_PX = 1.5, 3, 2.0
ARMS = {"primary": 2.0}
# 1.296 px: RMS difference between a 100 m-grid offset and the same offset measured on 3 m LiDAR
# (evidence/lidar_calibration_v1.json, "estimator"). Used as the floor on the corridor robust-SE so a
# four-pixel corridor with a collapsed MAD cannot manufacture a significant z.
SIGMA_FLOOR_PX = 1.296


def build_arm(fields, cat, fp, gate_px, *, hd, hm, corridor_gate=True):
    # The same null-calibrated crest-strength floors used by the decision histogram are mandatory
    # at build time. Never disable them to preserve a non-empty raster: doing so would turn null-level
    # crests into apparent corrections merely to satisfy a deliverable requirement.
    rec = C.measure(fields, cat, fp, min_hgt=(hd, hm, 0.0))
    # "consistent offset exceeds ~2 pixels" is read at the scale the brief states it at: a *corridor*, i.e.
    # a whole catalogue component whose pixels agree in sign, are corroborated by both families, and survive
    # the robust-SE test. A single pixel agreeing with itself is not a displaced map line.
    crows, joint_all, corr_all, u_all = C.corridor_table(rec, cat, offset_gate_px=gate_px,
                                                         sigma_floor_px=SIGMA_FLOOR_PX)
    qual = {r["comp"] for r in crows if r["qualifies"]}
    d, m = rec["dem_off_px"], rec["mag_off_px"]
    q = (rec["valid"] & np.isfinite(d) & np.isfinite(m) & (np.abs(d) >= gate_px)
         & (np.abs(m) >= gate_px) & (np.sign(d) == np.sign(m)) & (np.abs(d - m) <= CORR_PX))
    joint = np.where(q, 0.5 * (d + m), np.nan)
    # one aligned block for every per-candidate array: no filter can desynchronise an origin from
    # its target cell, which is the bug class that would silently place dots on the wrong trace
    qi = np.nonzero(q)[0]
    orow, ocol, jj, st = rec["row"][qi], rec["col"][qi], joint[qi], rec["strike_deg"][qi]
    ty0, tx0, ok_strike, _ = C.strike_at(cat, orow, ocol)
    keep = ok_strike
    orow, ocol, jj, st, ty0, tx0 = [a[keep] for a in (orow, ocol, jj, st, ty0, tx0)]
    yr = np.rint(orow - jj * tx0).astype(np.int64)
    xc = np.rint(ocol + jj * ty0).astype(np.int64)
    k1 = ((yr >= 0) & (yr < cat.shape[0]) & (xc >= 0) & (xc < cat.shape[1])
          & fp[yr, xc] & ~cat[yr, xc])
    orow, ocol, yr, xc, jj, st = [a[k1] for a in (orow, ocol, yr, xc, jj, st)]
    n_after_gates = int(orow.size)
    cand = np.zeros(cat.shape, bool)
    cand[yr, xc] = True
    nb = ndimage.uniform_filter(cand.astype(np.float32), size=3, mode="constant") * 9.0
    k2 = nb[yr, xc] >= MIN_CLUSTER
    orow, ocol, yr, xc, jj, st = [a[k2] for a in (orow, ocol, yr, xc, jj, st)]
    lab, _ = ndimage.label(cat, structure=np.ones((3, 3), bool))
    comp = lab[orow, ocol]
    k3 = np.ones(comp.size, bool)
    if corridor_gate:
        k3 = np.isin(comp, sorted(qual)) if qual else np.zeros(comp.size, bool)
        orow, ocol, yr, xc, jj, st, comp = [a[k3] for a in (orow, ocol, yr, xc, jj, st, comp)]
    sel = np.zeros(yr.size, bool)
    for k in np.unique(comp):
        if k == 0:
            continue
        idx = np.nonzero(comp == k)[0]
        ang = np.deg2rad(float(np.median(st[idx])))
        proj = yr[idx].astype(np.float64) * np.cos(ang) + xc[idx].astype(np.float64) * np.sin(ang)
        last = -1e18
        for t in np.argsort(proj):
            if proj[t] - last >= MIN_SPACING_PX:
                sel[idx[t]] = True
                last = proj[t]
    pred = np.zeros(cat.shape, np.float32)
    if sel.any():
        pred[yr[sel], xc[sel]] = 1.0
    counts = dict(qualified_pixels=int(q.sum()), after_target_gates=n_after_gates,
                  after_cluster_gate=int(k3.sum()), qualifying_corridors=len(qual),
                  after_corridor_gate=int(orow.size), after_thinning=int(pred.astype(bool).sum()))
    counts["corridors"] = [r for r in crows if r["qualifies"]]
    counts["corridors_evaluated"] = len(crows)
    return pred, counts, rec


def main(argv):
    t0 = time.time()
    reg = Path(argv[0]) if argv else Path("/home/user/_reg")
    fields, cat, fp, meta = L.load()
    calibration_path = ROOT / "evidence" / "calibration_v1.json"
    if not calibration_path.is_file():
        raise SystemExit("missing null-calibration receipt; run the prescribed calibration before building")
    calibration = json.loads(calibration_path.read_text())
    hd = float(calibration["strength_gate"]["dem_min_hgt"])
    hm = float(calibration["strength_gate"]["mag_min_hgt"])
    if not (np.isfinite(hd) and np.isfinite(hm)):
        raise SystemExit("null-calibrated strength floors are not finite; refusing to build")
    priors = sorted(str(p) for p in reg.glob("*.tif")) if reg.exists() else []
    # Fail closed: an empty corpus made the gate check zero priors and write an empty receipt
    # (found in the 2026-10-09 re-run). Rebuild the corpus with scripts/mirror_registry_corpus.py first.
    if len(priors) < 944:
        raise SystemExit(f"uniqueness corpus incomplete: {len(priors)} of 944 indexed priors in {reg}; "
                         "refusing to write a uniqueness receipt. Run scripts/mirror_registry_corpus.py.")
    sample = ROOT / "data" / "grid" / "sample_submission.tif"
    out = dict(evidence_class="built artefacts with local format and lane receipts; no organizer receipt exists",
               rule=dict(corroboration_px=CORR_PX, min_cluster=MIN_CLUSTER, spacing_m=MIN_SPACING_PX * 100,
                         null_dem_hgt_p90=hd, null_mag_hgt_p90=hm,
                         floor_source="evidence/calibration_v1.json (the same recorded decision thresholds)",
                         applied_at_build=True,
                         note="strength floor is mandatory; it is never disabled to preserve non-empty output"),
               catalogue_pixels=int(cat.sum()), arms={}, priors_in_registry=len(priors),
               built_utc=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    for arm, gate in ARMS.items():
        pred, counts, rec = build_arm(fields, cat, fp, gate, hd=hd, hm=hm)
        name = f"h56-corr-snap{int(gate * 100):03d}cm-20261009"
        dots = counts["after_thinning"]
        note = (f"h56 corrections lane, {'PRIMARY' if arm=='primary' else 'sensitivity'} arm: dots on the "
                f"evidence crest >= {int(gate*100)} m off catalogue, DEM+mag concordant; {dots} dots; NEGATIVE")
        assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
        tif = ROOT / "docs" / "downloads" / f"{name}.tif"
        receipt = SW.write_submission(tif, pred, sample, fp, note=note, name=name,
                                      metadata=dict(arm=arm, offset_gate_px=gate, counts=counts,
                                                    null_strength_floor_applied=True,
                                                    null_calibration_receipt="evidence/calibration_v1.json",
                                                    null_dem_min_hgt=hd, null_mag_min_hgt=hm,
                                                    holdout_dti_arm="B_snap/C_snap_sub",
                                                    cleared_for_weekly_slot=False))
        rep = {}
        if priors and dots > 0:
            for phase in ("surface", "dots"):
                rep[phase] = gates.lane_uniqueness_report(
                    pred, fp, priors, sample=sample, phase=phase)
        out["arms"][arm] = dict(
            name=name, note=note, note_chars=len(note), dots=int(dots),
            cleared_for_weekly_slot=False,
            verdict=("nothing passed the corridor-consistency rule, so nothing was emitted" if dots == 0
                     else f"{dots} dots on {counts['qualifying_corridors']} corridor(s) that passed the "
                          f"corridor-consistency rule; not cleared for a slot by this run"),
            file=str(tif.relative_to(ROOT)),
            sha256=receipt["sha256"], bytes=receipt["bytes"], zip=receipt["zip_file"],
            zip_sha256=receipt["zip_sha256"], validator_ok=receipt["validator"]["ok"],
            validator_problems=receipt["validator"]["problems"],
            validator_min=receipt["validator"].get("min"), validator_max=receipt["validator"].get("max"),
            unique_values=sorted(set(np.unique(pred[fp]).tolist())), counts=counts,
            lane=dict(priors_checked=len(priors),
                      surface_max_rho=rep.get("surface", {}).get("max_spearman"),
                      dots_max_rho=rep.get("dots", {}).get("max_spearman"),
                      dots_max_near3px=rep.get("dots", {}).get("max_near_3px_fraction"),
                      duplicate=rep.get("dots", {}).get("duplicate"),
                      offender_count=rep.get("dots", {}).get("offender_count"),
                      error_count=rep.get("dots", {}).get("error_count")),
            offenders=sorted({o["path"].split("/")[-1] for o in (rep.get("dots", {}).get("per_prior") or [])
                              if o.get("near_duplicate") or o.get("rank_duplicate") or o.get("identical")})[:12])
        (ROOT / "evidence" / f"lane_uniqueness_{name}.json").write_text(json.dumps(rep, indent=1, default=float))
    (ROOT / "evidence" / "build_corrections_v1.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float)[:3800])


if __name__ == "__main__":
    main(sys.argv[1:])
