#!/usr/bin/env python3
"""E1 (round 3): map-quality stratification of the catalogue-to-evidence offset.

Pre-registered in docs/research/hypotheses-20261009-round3.md BEFORE this script ran.

H-C1 primary test (records with n_transects >= 8 in dem_slope_strongest):
  (1) Spearman rho(MAPSCALE, |median_offset_px|) > 0, one-sided p < 0.05, AND
  (2) median |median_offset_px| over FTYPE_ != "Well Constrained"  >  that over
      FTYPE_ == "Well Constrained", one-sided Mann-Whitney p < 0.05.
Both must hold => H-C1 VALIDATED.

Controls (pre-registered against the terrain confound):
  * top prominence quartile of records (median transect prominence, ok transects only)
  * LiDAR-covered records (every transect has lidar_coverage == 1)
  * second evidence family (mag_hg_strongest) and the nearest-crest definition

Inputs (all official / committed):
  evidence/corrections/record_offsets_dem_slope_strongest.csv   (round 1, unchanged)
  evidence/corrections/record_offsets_dem_slope_nearest.csv
  evidence/corrections/record_offsets_mag_hg_strongest.csv
  evidence/corrections/offset_transects.csv                     (prominence + lidar cols)
  data/cache/qfault_attributes.csv                              (GEMSDOE51 mirror of the
   official qfaults_ingenious_nad83conus117_2023-06-27.shp attribute table; GDR 1391)

Output: evidence/corrections/map_quality_stratification.json

Run: .venv/bin/python scripts/test_map_quality_stratification.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence" / "corrections"
MIN_N = 8            # pre-registered transect floor (same as the round-1 gate)


def load_attributes() -> pd.DataFrame:
    """Attribute table of the official shapefile, ONE ROW PER shapefile feature.

    Join semantics (verified this session before any statistic was read):
    ``record_id`` in trace_segments_utm11.csv is the 0-based index of the shapefile
    feature (GEMSDOE51 scripts/extract_official_segments.py: ``enumerate(r.iterShapeRecords())``),
    NOT the ``NUM`` field. qfault_attributes.csv is the dbf dumped in feature order
    (22,956 rows = the receipt's dbf record count), so the correct join is POSITIONAL:
    record_id i <-> attributes row i. Verified: SLIPSENSE agrees on 1,126/1,126 in-bbox
    records once NaN spellings are normalised (the 95 raw mismatches are all nan-vs-nan).
    The first draft of this script joined on NUM and was WRONG (46/125 spurious matches);
    logged as IR-56-031 and never used for a decision.
    """
    a = pd.read_csv(ROOT / "data/cache/qfault_attributes.csv", dtype={"NUM": str})
    a["NUM"] = a["NUM"].str.strip()
    a["record"] = a.index.astype(str)          # positional key == segments record_id
    a["MAPSCALE"] = pd.to_numeric(a["MAPSCALE"], errors="coerce")
    return a


def per_record_prominence() -> pd.DataFrame:
    t = pd.read_csv(EV / "offset_transects.csv")
    t = t[t["dem_slope_strongest_ok"] == True]  # noqa: E712
    t["record"] = t["record"].astype(str)
    g = t.groupby("record")["dem_slope_strongest_prom"].median()
    return g.rename("prom_med").reset_index()


def lidar_covered() -> set:
    t = pd.read_csv(EV / "offset_transects.csv", usecols=["record", "lidar_coverage"])
    t["record"] = t["record"].astype(str)
    g = t.groupby("record")["lidar_coverage"].min()
    return set(g[g >= 1.0].index)


def test_table(rec: pd.DataFrame, a: pd.DataFrame, label: str) -> dict:
    """The two pre-registered primary tests + secondaries, on one record table."""
    d = rec.merge(a, on="record", how="inner")
    n_join = len(d)
    d = d[d["n_transects"] >= MIN_N].copy()
    d["A"] = d["median_offset_px"].abs()
    out = {"table": label, "records_total": int(len(rec)), "records_joined": int(n_join),
           "records_n_ge_8": int(len(d))}
    if len(d) < 10:
        out["note"] = "too few records for the pre-registered tests"
        return out

    # --- (1) Spearman MAPSCALE vs A ---
    dm = d.dropna(subset=["MAPSCALE", "A"])
    rho, p2 = stats.spearmanr(dm["MAPSCALE"], dm["A"])
    out["spearman_MAPSCALE_A"] = {"n": int(len(dm)), "rho": float(rho),
                                  "p_one_sided": float(p2 / 2 if rho > 0 else 1 - p2 / 2)}

    # --- (2) Mann-Whitney: not-Well vs Well ---
    well = d[d["FTYPE_"] == "Well Constrained"]["A"]
    notw = d[d["FTYPE_"] != "Well Constrained"]["A"]
    if len(well) >= 3 and len(notw) >= 3:
        u, pw = stats.mannwhitneyu(notw, well, alternative="greater")
        out["mw_notwell_vs_well"] = {"n_well": int(len(well)), "n_notwell": int(len(notw)),
                                     "median_well": float(well.median()),
                                     "median_notwell": float(notw.median()),
                                     "p_one_sided": float(pw)}
    else:
        out["mw_notwell_vs_well"] = {"n_well": int(len(well)), "n_notwell": int(len(notw)),
                                     "note": "class too small"}

    # --- secondaries (reported, never gating) ---
    fr = d.dropna(subset=["frac_abs_gt_2px", "MAPSCALE"])
    rho2, p2b = stats.spearmanr(fr["MAPSCALE"], fr["frac_abs_gt_2px"])
    out["spearman_MAPSCALE_fracgt2"] = {"n": int(len(fr)), "rho": float(rho2),
                                        "p_one_sided": float(p2b / 2 if rho2 > 0 else 1 - p2b / 2)}
    ftypes = [str(x) for x in d["FTYPE_"].fillna("nan").unique()]
    if len(ftypes) > 2:
        groups = [d[d["FTYPE_"].fillna("nan") == f]["A"].values for f in ftypes]
        h, ph = stats.kruskal(*groups)
        out["kruskal_FTYPE"] = {"groups": ftypes,
                                "medians": {f: float(np.median(g)) for f, g in zip(ftypes, groups)},
                                "p": float(ph)}
    dfc = d.dropna(subset=["FCODE2023", "A"])
    dfc = dfc[dfc["FCODE2023"].astype(str).str.isnumeric()]
    if len(dfc) >= 10:
        rho3, p3 = stats.spearmanr(dfc["FCODE2023"].astype(float), dfc["A"])
        out["spearman_FCODE_A"] = {"n": int(len(dfc)), "rho": float(rho3),
                                   "p_one_sided": float(p3 / 2 if rho3 > 0 else 1 - p3 / 2)}
    out["mapscale_counts"] = {str(int(k)): int(v) for k, v in
                              d["MAPSCALE"].value_counts().sort_index().items()}
    out["ftype_counts"] = {str(k): int(v) for k, v in d["FTYPE_"].fillna("nan").value_counts().items()}
    # raw medians by class, for the site table
    out["A_by_ftype"] = {str(k): {"n": int(v), "median_A_px": float(m)}
                         for (k, v), m in zip(d.groupby(d["FTYPE_"].fillna("nan"))["A"].size().items(),
                                               d.groupby(d["FTYPE_"].fillna("nan"))["A"].median())}
    out["A_by_mapscale"] = {str(int(k)): {"n": int(v), "median_A_px": float(m)}
                            for (k, v), m in zip(d.groupby("MAPSCALE")["A"].size().items(),
                                                 d.groupby("MAPSCALE")["A"].median()) if pd.notna(k)}
    return out


def main() -> int:
    a = load_attributes()
    prom = per_record_prominence()
    lid = lidar_covered()

    tables = {
        "primary": pd.read_csv(EV / "record_offsets_dem_slope_strongest.csv", dtype={"record": str}),
        "secondary_mag_hg_strongest": pd.read_csv(EV / "record_offsets_mag_hg_strongest.csv", dtype={"record": str}),
        "secondary_dem_slope_nearest": pd.read_csv(EV / "record_offsets_dem_slope_nearest.csv", dtype={"record": str}),
    }
    receipt = {"pre_registered_in": "docs/research/hypotheses-20261009-round3.md",
               "min_transects": MIN_N, "tables": {}}

    for label, t in tables.items():
        receipt["tables"][label] = test_table(t, a, label)

    # ---- controls on the primary table (terrain confound) ----
    prim = tables["primary"].merge(prom, on="record", how="left")
    prim["lidar_all"] = prim["record"].isin(lid)
    q = prim["prom_med"].quantile(0.75)
    controls = {}
    for cname, sel in {
        "top_prominence_quartile": prim[prim["prom_med"] >= q],
        "lidar_covered_records": prim[prim["lidar_all"]],
        "lidar_and_top_prom": prim[prim["lidar_all"] & (prim["prom_med"] >= q)],
    }.items():
        controls[cname] = test_table(sel, a, f"primary/{cname}")
    receipt["controls"] = controls

    # ---- pre-registered verdict ----
    p = receipt["tables"]["primary"]
    ok1 = p.get("spearman_MAPSCALE_A", {}).get("p_one_sided", 1.0) < 0.05 and \
        p.get("spearman_MAPSCALE_A", {}).get("rho", 0) > 0
    mw = p.get("mw_notwell_vs_well", {})
    ok2 = mw.get("p_one_sided", 1.0) < 0.05 and mw.get("median_notwell", 0) > mw.get("median_well", 1)
    receipt["h_c1_verdict"] = "VALIDATED" if (ok1 and ok2) else "NEGATIVE"
    receipt["h_c1_rule"] = ("Spearman(MAPSCALE, |median_offset_px|) > 0 with one-sided p<0.05 AND "
                            "MW(not-Well > Well) one-sided p<0.05, records n>=8, dem_slope_strongest")

    out = EV / "map_quality_stratification.json"
    out.write_text(json.dumps(receipt, indent=1))
    print(json.dumps({k: receipt[k] for k in ("h_c1_verdict",)}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
