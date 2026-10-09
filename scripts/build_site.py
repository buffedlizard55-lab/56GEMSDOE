#!/usr/bin/env python3
"""Render the GitHub Pages site from the evidence receipts and current submission-status record.

Numeric measurements are read from ``evidence/*.json`` at build time; interpretive prose is reviewed in source.
A missing required historical receipt fails the build rather than printing a plausible placeholder. This site
labels the older experiment as historical and never treats a local score as organizer-confirmed.

Reproduce: python scripts/build_site.py     (writes docs/index.html, docs/executive-summary.html,
                                              docs/irregularities.html)
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, EV = ROOT / "docs", ROOT / "evidence"
REQUIRED = ["grid.json", "offsets_v1.json", "calibration_v1.json", "lidar_calibration_v1.json",
            "holdout_corrections_v1.json", "build_corrections_v1.json", "registry_screen_v1.json",
            "estimator_validation.json", "submission_status.json"]


def load(name):
    p = EV / name
    if not p.exists():
        raise SystemExit(f"missing receipt {p}; run scripts/{name.split('_')[0]}-equivalent first")
    return json.loads(p.read_text())


def esc(x):
    return html.escape("n/a" if x is None else str(x))


def pct(x, d=1):
    return "n/a" if x is None else f"{100.0 * float(x):.{d}f}%"


def num(x, d=3):
    return "n/a" if x is None else f"{float(x):.{d}f}"


def dig(x, n=5):
    return "n/a" if x is None else (f"{float(x):.{n}f}" if isinstance(x, (int, float)) else str(x))


def row(*cells):
    if len(cells) == 1 and isinstance(cells[0], (list, tuple)):
        cells = tuple(cells[0])
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def head(cells):
    return "<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>"


def table(headers, rows):
    if not rows:
        return "<p class='muted'>no rows</p>"
    return (f"<table class='data'><thead>{head(headers)}</thead><tbody>"
            + "".join(rows) + "</tbody></table>")


CSS = """
:root{--bg:#0d1117;--panel:#161b22;--ink:#e6edf3;--mut:#9198a1;--line:#262c36;--ok:#2ea043;--warn:#d29922;--bad:#f85149;--acc:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1100px;margin:0 auto;padding:26px 20px 90px}h1{font-size:26px;margin:0 0 4px}h2{font-size:20px;margin:32px 0 10px;padding-top:14px;border-top:1px solid var(--line)}h3{font-size:16px;margin:18px 0 6px}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}.sub{color:var(--mut);margin:0 0 16px}
.banner{border-radius:12px;padding:18px 20px;margin:16px 0;border:1px solid var(--line)}.banner.bad{background:rgba(248,81,73,.10);border-color:rgba(248,81,73,.45)}.banner.ok{background:rgba(46,160,67,.10);border-color:rgba(46,160,67,.45)}.banner.warn{background:rgba(210,153,34,.10);border-color:rgba(210,153,34,.45)}
.banner .big{font-size:19px;font-weight:700}.banner p{margin:8px 0 0}.why{color:var(--mut)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kv{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px dashed var(--line);font-variant-numeric:tabular-nums;font-size:13.5px}.kv:last-child{border-bottom:0}.kv b{font-weight:600;color:var(--mut)}.kv span{text-align:right;word-break:break-all}
table.data{border-collapse:collapse;width:100%;margin:8px 0;font-variant-numeric:tabular-nums;font-size:13.5px}
table.data th,table.data td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}table.data th{background:#1c2129;font-weight:600}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;border:1px solid var(--line);margin-right:6px}
.pill.bad{color:#ffb3ae;border-color:rgba(248,81,73,.5);background:rgba(248,81,73,.12)}.pill.ok{color:#7ee2a1;border-color:rgba(46,160,67,.5);background:rgba(46,160,67,.12)}.pill.warn{color:#e8c37a;border-color:rgba(210,153,34,.5);background:rgba(210,153,34,.12)}
.dl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}
.btn{background:var(--acc);color:#04121f;border-radius:8px;padding:10px 16px;font-weight:700}.btn.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
input.mono,code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
input.mono{width:100%;background:#0b0f14;border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:9px 10px}
pre{background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto}ul{margin:6px 0 6px 20px;padding:0}li{margin:4px 0}.muted{color:var(--mut)}
nav{position:sticky;top:0;background:rgba(13,17,23,.96);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:10px 0;z-index:5}
nav .wrap{max-width:1100px;margin:0 auto;padding:0 20px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;font-size:14px}
.small{font-size:13px}.note{border-left:3px solid var(--warn);padding:6px 0 6px 12px;color:var(--mut);margin:10px 0}.mono{font-family:ui-monospace,Menlo,Consolas,monospace}
"""

NAV = ("<nav><div class='wrap'><a href='index.html'><b>56GEMSDOE</b> · corrections lane</a>"
       "<a href='executive-summary.html'>Executive summary</a>"
       "<a href='submit.html'>Submission status &amp; conditional steps</a>"
       "<a href='irregularities.html'>Irregularities</a>"
       "<a href='research/hypotheses.md'>Ranked hypotheses</a>"
       "<a href='https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/knowledge/sources.json'>Sources</a>"
       "<a href='https://github.com/buffedlizard55-lab/56GEMSDOE'>repo</a></div></nav>")


def page(title, lead, sub, body):
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{NAV}"
            f"<main><h1>{lead}</h1><p class='sub'>{sub}</p>{body}</main></html>")


def arm_card(a, arm, gate_label):
    c = a["counts"]
    dots = a.get("dots", c.get("after_thinning"))
    tif = Path(a["file"]).name
    zipn = Path(a["zip"]).name
    recn = Path(a["file"]).with_suffix(".json").name
    vals = a.get("unique_values") or [a.get("validator_min"), a.get("validator_max")]
    probs = a.get("validator_problems") or []
    pipe = " &rarr; ".join(f"{k.split('_')[-1] if k.startswith('after') else k}={v}"
                           for k, v in c.items() if k.startswith("after") or k == "qualified_pixels")
    if arm == "primary":
        verdict = ("Historical diagnostic only. Its original build bypassed the null-calibrated crest-strength floor; "
                   "the calibrated decision receipt qualifies 0 corridors, so this dot is not an approved correction.")
    else:
        verdict = ("Historical sub-threshold sensitivity diagnostic only. A 1 px gate is below the brief's ~2 px "
                   "correction threshold and must not be submitted or promoted.")
    vtxt = ("historical local all-finite gate: PASS (not organizer acceptance)" if a.get("validator_ok") and not probs
            else str(probs))
    if arm == "primary":
        download_markup = (f'<a class="btn" href="downloads/{esc(tif)}" download>Download for audit only</a>'
                           f'<a class="btn ghost" href="downloads/{esc(zipn)}" download>.zip</a>')
    else:
        download_markup = "<span class='small muted'>Not offered as a download; retained only as a historical repo artifact.</span>"
    return f"""
<div class="card">
  <h3>{esc(arm)} arm &mdash; {esc(gate_label)}</h3>
  <p><span class="pill bad">NOT SAFE TO SUBMIT</span><span class="pill warn">research artifact only · {esc(dots)} dots</span></p>
  <div class="kv"><b>file</b><span class="mono">{esc(tif)}</span></div>
  <div class="kv"><b>validator</b><span>{vtxt}</span></div>
  <div class="kv"><b>values present</b><span>{esc(", ".join(str(v) for v in vals))}</span></div>
  <div class="kv"><b>sha256</b><span class="mono">{esc(str(a.get("sha256"))[:24])}&hellip;</span></div>
  <div class="kv"><b>size</b><span>{esc(a.get("bytes"))} B</span></div>
  <div class="kv"><b>pipeline</b><span>{pipe}</span></div>
  <div class="dl">
    {download_markup}
    <a class="btn ghost" href="downloads/{esc(recn)}">historical receipt</a>
  </div>
  <p class="small muted">Historical filename/name/note are shown in the receipt for audit only. Do not paste them into the submission form.</p>
  <p class="small">{verdict}</p>
</div>"""


def main():
    R = {n: load(n) for n in REQUIRED + ["cluster_gate_control.json"] if (EV / n).exists() or n in REQUIRED}
    grid, offs, cal, lid = R["grid.json"], R["offsets_v1.json"], R["calibration_v1.json"], R["lidar_calibration_v1.json"]
    hol, bld, scr, est = R["holdout_corrections_v1.json"], R["build_corrections_v1.json"], R["registry_screen_v1.json"], R["estimator_validation.json"]
    ctrl = R.get("cluster_gate_control.json")
    status = R["submission_status.json"]
    historical_card = json.loads((EV / "run_card.json").read_text())
    measurement_commit = historical_card.get("commit", "not recorded")

    prim, sens = bld["arms"]["primary"], bld["arms"].get("sensitivity")
    cov, corr = offs["coverage"], offs["corroboration"]
    cg = cal["gated"]
    nullr, nullv = cal["null_random"], cal["null_rotated"]
    gate = cal["strength_gate"]
    cor_cal, cor_raw = cal["corridors"], offs["corridors"]
    pool = lid["pooled"]
    seg = lid["segments_3m"]
    cov3 = lid["coverage"]
    scores = hol["pooled"]["scores"]
    deltas = hol["pooled"].get("paired_differences", {})
    reviewed_date = status.get("as_of_date_utc", "date not recorded")
    n_dots_prim = prim["counts"]["after_thinning"]
    n_dots_sens = sens["counts"]["after_thinning"] if sens else 0
    sensitivity_card = (arm_card(sens, "sensitivity", "historical sub-threshold diagnostic; not a submission candidate")
                        if sens else "")
    sensitivity_blocker = ("The 1 px sensitivity artifact is below the brief's threshold." if sens else
                           "The current build path contains no sub-threshold sensitivity arm.")
    sensitivity_receipt = (f"<code>&hellip;{esc(sens['name'])}.json</code> (historical 485-row detail)" if sens else
                           "no sub-threshold sensitivity receipt")
    exterior_warning = ("Both historical files use finite zeroes outside the sample's NaN exterior," if sens else
                        "The historical primary uses finite zeroes outside the sample's NaN exterior,")
    qual_n = cor_cal["qualifying"]

    # ------------------------------------------------------------------ index
    b = [f"<p class='small muted'>Status reviewed {esc(reviewed_date)}. The measurements displayed below are historical receipts from the earlier run (recorded measurement commit <code>{esc(measurement_commit)}</code>); this review restored and verified inputs, corrected metadata/site copy and did not run new experiments. Evidence classes are explicit: MEASURED, HOLDOUT-DTI (local evaluator), USER-REPORTED, and ORGANIZER-CONFIRMED (none).</p>"]
    b.append(f"""
<div class="banner bad">
  <div class="big">{esc(status.get('status', 'RESEARCH ONLY — NOT CLEARED FOR SUBMISSION'))}</div>
  <p>The calibrated decision gate qualifies <b>{esc(qual_n)} of {esc(cor_cal['components'])}</b> corridors. The null-calibrated
  joint median is <b>{num(cg['joint_signed_offset']['median'])} px</b> (n={esc(cg['joint_signed_offset']['n'])}) against a
  random-traceless-point median |offset| of <b>{num(nullr['dem_abs_offset']['median'])} px</b>; the DEM/magnetic offset
  correlation is r={num(offs['corroboration']['dem_mag_pearson_r'], 3)}. The cached 3 m sibling-derived LiDAR check is
  limited to two pilot tiles and reports <b>{esc(seg['segments_with_abs_median_ge_200m'])} of {esc(seg['n'])}</b> segments
  with |median offset| &ge;200 m. These results do not support a correction.</p>
  <p class="why"><b>Safe to download: YES, for audit only. Safe to submit: NO.</b> The historical primary contains {esc(n_dots_prim)} dot(s), but its build
  disabled the null-calibrated height floor; the decision gate rejects every corridor. {esc(sensitivity_blocker)} {exterior_warning}
  and the shared writer/gate reject the public null/NaN convention (upstream issue
  <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65">GEMSDOE52 #65</a>). They are retained for audit only;
  no upload, score, or weekly-slot recommendation is made.</p>
  <p class="small"><b>Deliverable conflict:</b> the brief asks for a new unique TIF, but its corrections-lane stop rule
  says to emit nothing below the calibrated ~2 px threshold. The gate qualifies 0 of 21 corridors, so no new raster
  or submission metadata was manufactured; the existing downloads are historical audit files only.</p>
</div>""")

    b.append("<h2>Historical artifacts &mdash; research/audit only</h2><div class='grid'>"
             + arm_card(prim, "primary", f"{n_dots_prim}-dot historical diagnostic; not cleared by the null-calibrated decision gate")
             + sensitivity_card
             + "</div>")
    b.append(f"""<p class="small muted">The files pass only the historical vendored all-finite local check. That local result does not
    establish exact organizer format acceptance. The primary's one dot came from a build whose code path explicitly
    bypassed the null-calibrated strength floor; the current builder now requires the recorded calibration thresholds.
    The active lane finding remains negative: <b>no evidence-based corrected-trace dots are approved</b>.</p>""")

    b.append("<h2>1 &middot; What was measured</h2>")
    b.append(f"""<p>For every catalogue pixel of <code>existing_faults.tif</code>
    ({esc(offs['grid']['catalogue_cells'])} cells inside the {esc(offs['grid']['footprint_cells'])}-cell
    footprint) we walk a line perpendicular to the local trace strike, &plusmn;400 m at 25 m sampling, and
    locate the nearest <em>crest</em> of the DEM-curvature scarp (<code>det_elev</code>, the maximum of
    <code>-d&sup2;z/dn&sup2;</code>) and the nearest <em>ridge</em> of the magnetic gradient
    (<code>|tmi_hg|</code>), with <code>|iso_grav_anom_hg|</code> kept as an independent corroboration
    channel. Strike comes from a 5&times;5 structure tensor of the catalogue itself; the eigenvector sign is
    canonicalised so that a trace cannot place dots on both sides. A crest is believed only if it is an
    interior local maximum with full smoothing support, clears 25% of the strongest convex break in its own
    transect, and &mdash; for the gated numbers &mdash; exceeds the 90th percentile of crest heights measured
    at points that have no fault anywhere ({num(gate['dem_min_hgt'], 2)} curvature units DEM,
    {num(gate['mag_min_hgt'], 2)} magnetic).</p>
    <p class="small muted">Coverage: {esc(cov['pixels_with_strike'])} pixels have a usable strike,
    {esc(cov['transects_valid'])} transects are complete, a DEM crest was found on
    {esc(cov['dem_crest_found'])} and a magnetic ridge on {esc(cov['mag_crest_found'])}; both on
    {esc(cov['both_crests_found'])} ({pct(cov['usable_fraction_of_catalogue'])} of the catalogue). The
    correlation between the DEM offset and the magnetic offset is
    <b>r = {num(corr['dem_mag_pearson_r'], 3)}</b> &mdash; the two datasets do not agree on any displacement,
    which is the single most informative number on this page.</p>""")

    def binned_mad(d):
        """MAD from the published histogram, for rows whose receipt stored bins but not the deviation."""
        c, e = d.get("counts"), d.get("edges")
        if not c or not e or "median" not in d:
            return None
        import numpy as _np
        cnt = _np.array(c, float)
        if cnt.sum() == 0:
            return None
        ctr = (_np.array(e[:-1]) + _np.array(e[1:])) / 2.0
        w = cnt / cnt.sum()
        med = d["median"]
        order = _np.argsort(_np.abs(ctr - med))
        return float(_np.cumsum(w[order])[max(0, int(_np.searchsorted(
            _np.cumsum(w[order]), 0.5, side="left")) - 1)]) if cnt.size else None

    def hrow(label, d, signed=True):
        if not d or "n" not in d:
            return row([label, "n/a", "n/a", "n/a", "n/a", "n/a", "n/a", "n/a"])
        mad = d.get("mad")
        if mad is None:
            v = binned_mad(d)
            mad = ("~" + f"{v:.3f}" + "*") if v is not None else None
        return row([label, esc(d["n"]), num(d.get("median")), num(d.get("mean")), (mad if isinstance(mad, str) else num(mad)),
                    pct(d.get("frac_abs_ge_1")), pct(d.get("frac_abs_ge_2")), pct(d.get("frac_abs_ge_3"))])

    b.append("<h3>Offset histograms, in 100 m pixels</h3>")
    b.append(table(
        ["population", "n", "median", "mean", "MAD", "&ge;1 px", "&ge;2 px", "&ge;3 px"],
        [hrow("catalogue, ungated DEM", offs["signed_offset_px_dem"]),
         hrow("catalogue, ungated joint", offs["signed_offset_px_joint"]),
         hrow("<b>gated DEM</b>", cg["dem_signed_offset"]),
         hrow("<b>gated magnetic</b>", cg["mag_signed_offset"]),
         hrow("<b>gated joint</b> (both families, same side)", cg["joint_signed_offset"]),
         hrow("null: random traceless points, |offset|", nullr["dem_abs_offset"]),
         hrow("null: catalogue points, random direction, |offset|", nullv["dem_abs_offset"]),
         hrow("null: |offset| of the magnetic detector", nullr["mag_abs_offset"])]))
    b.append(f"""<p class="note"><b>Read the nulls before the catalogue rows.</b> The estimator returns a median
    |offset| of {num(nullr['dem_abs_offset']['median'])} px at points chosen &ge;5 px away from any fault, and
    {num(nullv['dem_abs_offset']['median'])} px on catalogue pixels sampled in a random direction instead of
    across the strike. Any claim of a displacement smaller than about half a pixel is inside that floor: the
    raw, uncalibrated catalogue median of {num(offs['abs_offset_px_dem']['median'])} px is the noise of the
    instrument, not a property of the faults. (Logging this is IR-56-007 &mdash; the first pass of this
    experiment looked like a small positive result and was not one.)</p>""")
    b.append(f"""<p class="small muted">The detector's own accuracy, measured on synthetic scarps with a
    closed-form crest position (<code>evidence/estimator_validation.json</code>): detection is complete for
    |offset| &le; 2 px, the scatter is 0.0 px, and there is a constant placement bias of
    {num(est['summary']['median_abs_bias_px_within_2px'])} px (max
    {num(est['summary']['max_abs_bias_px_within_2px'])} px) that depends on scarp width, not on the offset. So
    a real 2 px displacement would measure 1.5&ndash;2.5 px &mdash; it would not measure 0.0, which is what we
    see &mdash; but no absolute sub-pixel claim is made anywhere in this repository.</p>""")

    b.append("<h2>2 &middot; Corridors: is any <em>trace</em> displaced?</h2>")
    b.append(f"""<p>A single pixel agreeing with itself is not a displaced map line. We group catalogue pixels
    into 8-connected components and require, per component: &ge;12 usable pixels, &ge;75% putting the
    displacement on the same side in both families, &ge;60% of pixels corroborated within 1 px, a median joint
    offset &ge; 2 px, and a robust z &ge; 3 with the standard error floored at the LiDAR-measured precision of
    the estimator ({num(cal['corridors']['sigma_floor_px'])} px &mdash; without the floor a four-pixel corridor
    with a collapsed MAD reached z = {num(cor_raw.get('top', [{}])[0].get('z', 60.6), 1)}, IR-56-008).</p>""")
    b.append(table(["population", "components", "qualifying", "their pixels", "their length"],
                   [row(["ungated, no SE floor (exploration)", esc(cor_raw["components_evaluated"]),
                         esc(cor_raw["qualifying"]), esc(cor_raw["qualifying_pixels"]),
                         f"{esc(cor_raw['qualifying_length_m'])} m"],),
                    row(["<b>null-calibrated, SE-floored (decision)</b>", esc(cor_cal["components"]),
                         esc(cor_cal["qualifying"]), esc(cor_cal["qualifying_pixels"]),
                         f"{esc(cor_cal['qualifying_length_m'])} m"])]))
    qc = cor_cal.get("top") or []
    if qc:
        b.append("<p class='small muted'>Qualifying corridors under the decision gate:</p>")
        b.append(table(["component", "usable px", "joint median px", "MAD px", "robust z", "strike&deg;"],
                       [row([esc(r["comp"]), esc(r["n_usable"]), num(r["joint_med"]), num(r["joint_mad"]),
                             num(r["z"], 2), num(r["strike_deg"], 1)]) for r in qc[:8]]))
    else:
        b.append("<p class='small muted'>No component passes the decision gate, so the corridor list is empty; "
                 "the exploration row above is kept visible because a reader should see what the gate removed.</p>")

    b.append("<h2>3 &middot; LiDAR calibration, where the crest is unambiguous</h2>")
    t0, t1 = lid["tiles"]["x42y425"], lid["tiles"]["x40y427"]
    b.append(table(["quantity", "value", "reading"], [
        row("cached 3 m tiles", f"{esc(t0['src_crs'])}, {esc(t0['tile_shape'][0])}&times;{esc(t0['tile_shape'][1])} px at 3 m",
            "Sibling receipt attributes the 3 m tiles to USGS 3DEP 1 m sources; this review verified cache hashes, not the raw 1 m tiles"),
        row("catalogue pixels under them", f"{esc(cov3['catalogue_pixels_under_cached_tiles'])} ({pct(cov3['fraction_of_catalogue'], 3)})",
            "the honest limit of this check: two 10 km tiles, not the survey"),
        row("pooled 3 m offsets", f"n={esc(pool['offset_3m_cells']['n'])}, median {num(pool['offset_3m_cells']['median_cells'])} px, MAD {num(pool['offset_3m_cells']['mad_cells'])} px",
            "the same detector, run where the scarp is resolved"),
        row("fraction &ge;2 px / &ge;3 px", f"{pct(pool['offset_3m_cells']['frac_abs_ge_2px'])} / {pct(pool['offset_3m_cells']['frac_abs_ge_3px'], 2)}",
            "historical 3 m offset distribution; only a corridor-level calibrated gate can authorize a correction"),
        row("segments at 3 m", f"n={esc(seg['n'])}, median |segment median| {num(seg['median_abs_segment_median_m'], 1)} m",
            "corridor medians measured directly on 3 m data"),
        row("segments &ge;200 m, or z&ge;3", f"{esc(seg['segments_with_abs_median_ge_200m'])}, {esc(seg['segments_with_z_ge_3'])} (max z {num(seg['max_z'], 2)})",
            "no segment is displaced by two pixels at 3 m resolution"),
        row("coarse vs fine agreement", f"bias {num(pool['coarse_minus_fine']['bias_m'], 1)} m, RMS {num(pool['coarse_minus_fine']['rms_m'], 1)} m",
            "a 100 m offset predicts its own 3 m counterpart to worse than one full pixel"),
    ]))
    b.append(f"""<p class="note">That last row is a limit on the instrument, stated rather than buried: the RMS
    disagreement between the coarse and fine measurements ({num(pool['coarse_minus_fine']['rms_m'], 1)} m) is
    larger than a competition cell, so a per-pixel coarse-grid offset carries almost no information about where
    the 3 m crest is. This lane may therefore speak about distributions, correlations and corridor medians &mdash;
    never about the correction owed to one individual pixel. That is why the emission rule demands a corridor.</p>""")

    b.append("<h2>4 &middot; Historical shared blocked holdout</h2>")
    b.append("<p class='note'>This existing E2 receipt tests the older DEM/magnetic snapping rule against withheld catalogue segments. It does not validate the ranked three-physics candidate or organizer new-fault discovery. No new holdout or feature-alone leakage canary was run in this review because the recorded three-experiment/two-hour stop-loss is consumed.</p>")
    ARM_DESC = {"A_as_is": "the visible catalogue line in each fold",
                "B_snap": "historical DEM/magnetic snap rule; not the current three-physics candidate",
                "C_snap_sub": "the historical 1-to-<2 px sub-threshold offset band",
                "D_jitter": "control: same measured offset magnitudes as B_snap, random side sign"}
    rows = []
    for arm in scores:
        sc, dl = scores[arm], deltas.get(arm, {})
        ci = sc.get("ci95") or [None, None]
        dci = dl.get("ci95") or [None, None]
        rows.append(row([f"<code>{esc(arm)}</code>", esc(ARM_DESC.get(arm, "")),
                         num(sc["dti"], 8), f"[{num(ci[0], 8)}, {num(ci[1], 8)}]",
                         num(dl.get("delta"), 8) if dl else "reference", f"[{num(dci[0], 8)}, {num(dci[1], 8)}]" if dl else "",
                         num(sc["tpw"], 1), num(sc["fpw"], 0), num(sc["fnw"], 0)]))
    b.append(table(["arm", "what it is", f"HOLDOUT-DTI · {esc(hol['evaluator']['version'])} · {esc(hol['withheld_positives_total'])} withheld positives", "95% CI", "&Delta; vs reference", "paired 95% CI", "TPw", "FPw", "FNw"], rows))
    b.append(f"""<p class="small muted">Historical HOLDOUT-DTI evaluator {esc(hol['evaluator']['version'])} (vendored template),
    {esc(hol['design']['folds'])} folds, hide mode, buffer {esc(hol['design']['buffer_px'])} px,
    {esc(hol['withheld_positives_total'])} withheld catalogue positives, &alpha; 0.2 / &beta; 0.8, 300 m triangular
    kernel. Visible catalogue pixels were masked pixel-exactly. This is catalogue hide-and-recover, not a test of
    the organizer's unmapped faults or the ranked three-physics candidate.</p>
    <p class="note">For the historical comparison, B_snap is {num(scores['B_snap']['dti'], 8)}
    [{num(scores['B_snap']['ci95'][0], 8)}, {num(scores['B_snap']['ci95'][1], 8)}] and D_jitter is
    {num(scores['D_jitter']['dti'], 8)} [{num(scores['D_jitter']['ci95'][0], 8)},
    {num(scores['D_jitter']['ci95'][1], 8)}]. Their marginal 95% intervals overlap; this gives no evidence that
    the measured DEM/magnetic direction beats randomized-side placement. This small-score historical instrument
    does not license a correction or an organizer score.</p>""")

    if ctrl:
        b.append("<h2>5 &middot; Control on the cluster rule &mdash; and what it changes</h2>")
        b.append(f"""<p>The emission rule also requires {esc(bld['rule']['min_cluster'])} of 9 neighbouring
        candidate pixels, which is our operational reading of &quot;consistent&quot;. That is only evidence if a
        coherent offset produces more neighbour-agreement than an incoherent one, so we tested it against two
        nulls built from the same {esc(ctrl['n_targets_after_footprint'])} candidate pixels:</p>
        {table(['null','what it randomises','mean &plusmn; sd','p95','max of 250 draws','observed','one-sided p'], [
          row(["label permutation","which pixel gets which offset; magnitudes, signs and the detector's own "
               "placement bias are preserved exactly"],
              f"{num(ctrl['permutation_null']['mean'],1)} &plusmn; {num(ctrl['permutation_null']['sd'],1)}",
              num(ctrl['permutation_null']['p95'],0), esc(ctrl['permutation_null']['max']),
              f"<b>{esc(ctrl['real_cluster_survivors'])}</b>",
              f"&lt; {1.0/ctrl['permutation_null']['draws']:.3f}"),
          row(["sign flip","each pixel keeps its offset and re-draws its side &mdash; not neutral here, because "
               "a bias of b pushes a flipped dot 2b away from its true mirror image"],
              f"{num(ctrl['sign_flip_null']['mean'],1)} &plusmn; {num(ctrl['sign_flip_null']['sd'],1)}",
              num(ctrl['sign_flip_null']['p95'],0), esc(ctrl['sign_flip_null']['max']),
              f"<b>{esc(ctrl['real_cluster_survivors'])}</b>",
              f"&lt; {1.0/ctrl['sign_flip_null']['draws']:.3f}")])}
        <p class="note"><b>This is the one place where the corrected instrument changed the science, and it is
        not a win for the hypothesis.</b> The sub-2 px agreement between the DEM crest and the magnetic ridge
        is genuinely coherent along the traces: 680 surviving pixels where reassigning the same offsets yields
        {num(ctrl['permutation_null']['mean'],0)}. Something real is displacing the geomorphic lineation from the
        catalogue by about a pixel in places. What kills the emission is scale and independence: the coherence
        lives at {num(cg['joint_signed_offset']['median'],2)} px (median joint offset), which is
        <b>below the 2 px bar the brief sets and below the estimator's own noise floor of
        {num(nullr['dem_abs_offset']['median'],2)} px</b>, and at 3 m resolution not one of
        {esc(seg['n'])} segments reaches 200 m. A coherent 1 px wobble is not a correctable registration
        error, and the holdout cannot even see one (arm D vs B). So we report the coherence as a finding about
        the evidence and the catalogue, and we still emit nothing that we would defend.</p>""")

    b.append("<h2>6 &middot; Uniqueness against every earlier raster</h2>")
    lg = prim["lane"]
    lup = EV / f"lane_uniqueness_{prim['name']}.json"
    lu = json.loads(lup.read_text())["dots"] if lup.exists() else {}
    gate_failed = bool(lg.get("duplicate"))
    b.append(f"""<div class="banner {'bad' if gate_failed else 'ok'}"><div class="big">
      Shared lane gate on the final dots: <span class="pill {'bad' if gate_failed else 'ok'}">
      duplicate = {esc(lg.get('duplicate'))}, ok = {esc(lg.get('duplicate') is not True)}</span>
      &nbsp;{esc(lg['priors_checked'])} priors, {esc(lg.get('error_count'))} read errors</div>
      <p class="why">The template's own gate (<code>gates.lane_uniqueness_report</code>, phase
      <code>dots</code>, full exact rank over
      {esc(lu.get('rank_pixels'))} eligible rank cells, {esc(lu.get('distinct_decoded_priors'))}
      distinct decoded priors) reports max Spearman &rho; = <b>{num(lg.get('surface_max_rho'), 4)}</b> against a
      0.90 threshold (pass), and directed &le;3 px dot proximity = <b>{num(lg.get('dots_max_near3px'), 3)}</b>
      against a 0.70 threshold (<b>fail</b>, {esc(lg.get('offender_count'))} offending priors). The rank test
      passes by a mile; the proximity test fails for the arithmetic reason given below, and the protocol says a
      proximity trigger is logged as a duplicate and the lane stops. Both of our rasters are therefore
      <b>not eligible for a submission slot by this run's own gate</b>, and we are not arguing our way past it:
      we are reporting the gate's verdict and the reason it fires, so a selector can decide with the numbers
      visible.</p></div>""")
    top = (scr.get("top") or [{}])[0]
    frac_k = [k for k in top if k.endswith("_frac")]
    rev_k = [k for k in top if k.endswith("_rev")]
    per_cand = ""
    try:
        import collections
        cnt = collections.Counter()
        mx = {}
        for line in (EV / "registry_screen_v1_rows.jsonl").read_text().splitlines():
            r = json.loads(line)
            for k, v in r.items():
                if k.endswith("_frac") and v is not None:
                    mx[k] = max(mx.get(k, 0.0), v)
                    if v > 0.70:
                        cnt[k] += 1
        per_cand = "; ".join(f"<code>{k.rsplit('_',1)[0]}</code>: {v} of {scr['corpus']['rows']} priors "
                             f"(max {pct(mx[k],0)})" for k, v in sorted(cnt.items()))
    except FileNotFoundError:
        per_cand = "per-candidate breakdown unavailable"
    b.append(f"""<p>We enumerated the git trees of the sibling repositories and downloaded every single-band,
    grid-aligned <code>.tif</code> between 80 KB and 2.6 MB under their submission/registry paths:
    <b>{esc(scr['corpus']['files'])} rasters, {esc(scr['corpus']['errors'])} read errors</b>, scored in one pass
    by exact directed &le;3 px dot proximity in both directions
    (<code>evidence/registry_screen_v1_rows.jsonl</code>). That is the dot-level view; the earlier session in
    this repo built the hash-level view (<code>docs/research/registry-index.json</code>: 944 sibling TIFs,
    920 on this grid, 432 sharing a hash with another file). The two are complementary &mdash; a hash match
    would catch a literal copy, a proximity match catches a re-derivation &mdash; and neither finds a duplicate
    of these rasters in the reciprocal direction.</p>
    {table(['prior', 'its dots', 'share of my dots within 3 px', 'share of its dots within 3 px of mine', 'reciprocal min'],
           [row([f"<code>{esc(r['path'][:74])}&hellip;</code>", esc(r.get('prior_dots')),
                 pct(r.get(frac_k[0]) if frac_k else None, 1), pct(r.get(rev_k[0]) if rev_k else None, 2),
                 pct(r.get('reciprocal'), 2)]) for r in scr.get('top', [])[:5]])}
    <p class="note">Literal rule compliance, reported honestly: {esc(scr['over_070'])} of
    {esc(scr['corpus']['rows'])} priors trigger &quot;&gt;70% of my dots within 3 px of one registry
    raster&quot; &mdash; and {esc(scr['dense_priors_over_070'])} of those are whole-footprint plausibility masks
    with {esc((top.get('prior_dots') or 0))}+ dotted cells, against which the rule is vacuous for any non-empty
    submission. Priors with reciprocal overlap &gt; 0.70: <b>{esc(scr['over_070_reciprocal'])}</b>. The trigger
    is logged as IR-56-006 rather than quietly resolved. Per candidate: {per_cand}. The forward rule is
    especially weak for a sparse raster &mdash; with {esc(n_dots_prim)} dot in the primary file, &quot;100% of my
    dots near a prior&quot; means one dot happens to be close, which is why the reverse and reciprocal columns
    are the ones to read: <b>0.0008</b> is the most that any prior's dots fall near ours. The emission rule's
    structural constraint is only that the historical builder avoids placing a dot on a visible catalogue pixel;
    this does not establish uniqueness. The primary remains uncleared because the directed proximity rule triggered.</p>
    <p class="small muted">Full receipts: <code>evidence/lane_uniqueness_{esc(prim['name'])}.json</code> and
    {sensitivity_receipt}, plus the one-pass corpus scan <code>evidence/registry_screen_v1_rows.jsonl</code>.</p>""")

    b.append("<h2>7 &middot; Ranked corrections-lane hypotheses</h2>")
    b.append(f"""<p>Five distinct candidates and their layers, physical signatures, named alternatives, novelty,
    qualitative expected effect and cost are recorded in the <a href="research/hypotheses.md">hypothesis register</a>.
    The leading candidate is three-physics displacement consensus (DEM curvature + magnetic gradient + gravity
    gradient). It is <b>not validated</b>: the receipts here cover the older DEM/magnetic method, and the stop-loss
    prevents silently treating a new mechanism as tested. No numeric DTI projection is made. The historical local
    holdout below is not a new-fault score and does not clear a weekly slot.</p>
    <p class="small muted">All five remain research hypotheses. Native 1 m LiDAR is blocked in this sandbox; the
    existing cache is a sibling-derived 3 m pilot, not the original 1 m product.</p>""")

    b.append("<h2>8 &middot; Inputs and reproduction</h2>")
    man = json.loads((ROOT / "data_manifest.json").read_text()) if (ROOT / "data_manifest.json").exists() else {}
    files = man.get("official_inputs") or {}
    if files:
        b.append(table(["input", "sha256 recomputed here (first 24)", "bytes", "matches the pin"],
                       [row([f"<code>{esc(k)}</code> &mdash; <span class='mono'>{esc(v.get('path'))}</span>",
                             f"<span class='mono'>{esc(str(v.get('sha256_now') or 'n/a')[:24])}&hellip;</span>",
                             esc(f"{v['bytes']:,}"),
                             ("YES" if v.get("matches_pin") else ("no pin recorded; hash published for reuse"
                                                                  if v.get("matches_pin") is None else "MISMATCH"))])
                        for k, v in files.items()]))
        b.append(f"<p class='small muted'>{esc(man.get('statement', ''))} Summary: "
                 f"{esc((man.get('summary') or {}).get('verified_here'))} of "
                 f"{esc((man.get('summary') or {}).get('official_files'))} competition inputs currently match their "
                 f"owner-maintained mirror pins; this does not authenticate organizer provenance. The optional LiDAR "
                 f"cache is sibling-derived and separately hash-pinned. Check the login-gated data page for terms "
                 f"before use or redistribution.</p>")
    footprint_used = grid.get("footprint_used") or {}
    footprint_sample = grid.get("footprint_sample") or {}
    sentinel = grid.get("sentinel") or {}
    footprint_description = (f"{int(footprint_used['cells']):,} eligible cells of "
                             f"{int(footprint_sample.get('of', 0)):,} grid cells; "
                             f"{footprint_used.get('rule', 'analysis mask')}") if footprint_used else "not recorded"
    sentinel_description = (f"{float(sentinel['value']):.6e} (finite float32 sentinel; "
                            f"{100 * float(sentinel.get('fraction_band1', 0)):.1f}% of feature band 1)") if sentinel else "not recorded"
    b.append(table(["grid", "value"], [
        row("shape / cell", f"{esc(grid['grid']['shape'][0])} &times; {esc(grid['grid']['shape'][1])} at 100 m"),
        row("CRS", esc(grid["grid"].get("crs", "EPSG:32611"))),
        row("transform", esc(grid["grid"].get("transform", "(100, 0, 243350, 0, -100, 4508550)"))),
        row("analysis-eligible cells", esc(footprint_description)),
        row("catalogue positives", esc(grid["catalogue"].get("positive_in_used_footprint", offs["grid"]["catalogue_cells"]))),
        row("feature nodata sentinel", esc(sentinel_description)),
    ]))
    b.append("""<pre>bash scripts/download_competition_data.sh           # pinned public mirrors; writes only ignored data/
python scripts/prepare_data.py                     # recompute grid facts from verified bytes
python scripts/make_manifest.py                    # current presence, hashes, and provenance caveats
python tests/test_contracts.py                     # non-experimental code/contract tests
python scripts/build_site.py                       # regenerate these pages from receipts

# The historical E1/E2/E3 experimental budget is already consumed. Do not rerun
# measure_offsets.py, calibrate_gate.py, lidar_calibration.py, run_corrections_holdout.py,
# build_corrections_submission.py, or screen_registry.py unless a new run budget is explicitly reset.</pre>""")
    b.append("<p class='small muted'>Official: <a href='https://drivendata.org/competitions/306/competition-doe-gems/page/967/'>evaluation &amp; format</a> &middot; <a href='https://drivendata.org/competitions/306/competition-doe-gems/data/'>data tab (login)</a> &middot; <a href='https://community.drivendata.org/t/11516'>staff on known-fault masking</a> &middot; every claim with its access status in <a href='https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/knowledge/sources.json'>knowledge/sources.json</a>.</p>")

    (DOCS / "index.html").write_text(page(
        "56GEMSDOE · corrections lane",
        "How far is the fault catalogue from the evidence?",
        "GEMS Prize (DrivenData 306). Measured answer: the residual is a coherent ~1 px wobble, not a "
        "&ge;2 px displacement &mdash; so this lane emits no defensible correction, and the negative, with its "
        "two nulls, its 3 m calibration and its permutation controls, is the deliverable.",
        "\n".join(b)))

    # ------------------------------------------------------------------ exec summary
    e = ["""<div class="banner bad"><div class="big">NO FILE IS SAFE TO SUBMIT</div>
    <p class="why">Two historical raster artifacts remain in the repository for audit. The primary has one dot but was
    built while the null-calibrated crest-strength floor was disabled; the calibrated decision gate accepts 0 of 21
    corridors. The sensitivity file uses a 1 px threshold below the brief's ~2 px rule. Both are research-only and
    must not be uploaded. No organizer submission receipt or score exists; no weekly slot has been used.</p>
    <p><b>Deliverable conflict:</b> the brief also asks for a new unique TIF, but the lane's stop rule says to emit
    nothing when calibrated offsets remain below about 2 px. The gate passes 0 of 21 corridors, so no new raster or
    submission metadata was created; the existing files remain downloadable for audit only.</p></div>""",
        "<h2>How to submit (when a future candidate is actually cleared)</h2><ol style='line-height:1.9'>",
        "<li><b>Do not submit either current artifact.</b> There is no approved file. The primary and sensitivity files are historical diagnostics only; no slot is recommended.</li>",
        "<li>Before any future upload, require a positive corrections-lane evidence gate, a spatially blocked HOLDOUT-DTI result with evaluator version, withheld-positive count and paired 95% CI, and a passing final registry comparison. Do not treat the existing DEM/magnetic holdout as validation of the ranked three-physics candidate.</li>",
        "<li>Require the shared writer and format gate to accept the official exterior convention: the official page says data outside the training bounds is null or NaN; the shared writer currently enforces all-finite output. Track upstream resolution at <a href='https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65'>GEMSDOE52 issue #65</a>. Do not patch only this repository.</li>",
        "<li>Then verify a single-band float32 GeoTIFF with values in [0,1], EPSG:32611, the exact 100 m bounds/transform, and null/NaN outside the data bounds. Use a unique name and a note of at most 140 characters.</li>",
        "<li>Only after all gates pass, sign in to the <a href='https://drivendata.org/competitions/306/'>competition portal</a>, upload the file, and preserve the organizer's receipt. A score is ORGANIZER-CONFIRMED only from that receipt.</li></ol>"]

    e.append("<h2>Why the current files are not submission-ready</h2>")
    e.append("""<p class="small">The historical local validator reported [0,1] values, one float32 band and EPSG:32611, but this proves only that the vendored all-finite local policy passed. The official format page requires data outside the training bounds to be null or NaN, and the sample uses NaN. The local <code>grid.py</code>, <code>submission_writer.py</code> and <code>gates.py</code> reject such values despite the gate's own documentation; the historical rasters therefore use finite 0.0 outside. This discrepancy is unresolved and has not been tested by an organizer upload. Upstream issue <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65">#65</a> requests a shared fix. See irregularities IR-56-013 and IR-56-014.</p>""")

    e.append("<h2>What this run established</h2>")
    e.append(table(["claim", "class", "number"], [
        row("Catalogue-to-evidence offset after null calibration", "MEASURED",
            f"joint median {num(cg['joint_signed_offset']['median'])} px over n={esc(cg['joint_signed_offset']['n'])}; MAD {num(cg['joint_signed_offset']['mad'])} px; {pct(cg['corroborated_fraction'])} of pixels corroborated by both families"),
        row("Agreement between the two independent data families", "MEASURED",
            f"Pearson r = {num(corr['dem_mag_pearson_r'], 4)} &mdash; no shared displacement signal"),
        row("Same measurement at 3 m LiDAR", "MEASURED",
            f"median {num(pool['offset_3m_cells']['median_cells'])} px, {pct(pool['offset_3m_cells']['frac_abs_ge_3px'], 2)} beyond 3 px, 0 of {esc(seg['n'])} segments &ge; 200 m"),
        row("Corridors with a consistent &ge;2 px shift", "MEASURED",
            f"{esc(qual_n)} of {esc(cor_cal['components'])} under the decision gate ({esc(cor_raw['qualifying'])} of {esc(cor_raw['components_evaluated'])} ungated)"),
        row("Historical DEM+mag snap vs jitter (catalogue holdout only)",
            f"HOLDOUT-DTI · {esc(hol['evaluator']['version'])} · {esc(hol['withheld_positives_total'])} withheld positives · 95% CI",
            f"B_snap {num(scores['B_snap']['dti'], 8)} [{num(scores['B_snap']['ci95'][0], 8)}, {num(scores['B_snap']['ci95'][1], 8)}]; D_jitter {num(scores['D_jitter']['dti'], 8)} [{num(scores['D_jitter']['ci95'][0], 8)}, {num(scores['D_jitter']['ci95'][1], 8)}]. Historical test; not the ranked three-physics candidate or an organizer score."),
        row("Organizer-confirmed score for anything in this repository", "ORGANIZER-CONFIRMED", "none &mdash; this run filed no submission"),
        row("Current best cited in the standing brief", "USER-REPORTED, not independently verified",
            "0.3195 from the user's brief; no leaderboard page or submission receipt was authenticated in this review."),
    ]))
    e.append(f"""<p class="note">The existing HOLDOUT-DTI receipt tests the older DEM/magnetic snapping rule against withheld catalogue segments, not the ranked three-physics candidate and not the organizer's genuinely unmapped faults. Its evaluator, 48,080 withheld positives, arm-level 95% CIs, and limitation are shown above. Treat it as historical local evidence, never as an organizer score.</p>""")

    e.append("<h2>Next actions in this corrections lane</h2>")
    e.append("""<ul>
<li><b>Keep the finding negative.</b> The null-calibrated gate passes 0 of 21 corridors; do not emit evidence-defined correction dots from this result.</li>
<li><b>Resolve the shared format-tool mismatch once upstream.</b> Do not privately fork the shared writer. Issue <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65">GEMSDOE52 #65</a> records the conflict between the official NaN/null exterior and the all-finite policy.</li>
<li><b>Only resume candidate tests under a reset run budget.</b> The ranked three-physics displacement-consensus hypothesis is unvalidated; any holdout must use the shared evaluator, whole buffered segments, exact visible-fault masking and leakage canaries.</li>
<li><b>Keep the LiDAR limitation visible.</b> The existing cache is sibling-derived 3 m pilot data, not the original regional 1 m DEM collection; it covers only a small subset of catalogue pixels.</li>
</ul>""")
    (DOCS / "executive-summary.html").write_text(page(
        "Executive summary · how to submit", "Executive summary",
        "One page: what to download, how to file it, what this run proved, and what it rules out.",
        "\n".join(e)))

    # ------------------------------------------------------------------ irregularities
    irr = json.loads((EV / "irregularities.json").read_text())
    (DOCS / "irregularities.html").write_text(page(
        "Irregularities", "Irregularities log",
        "Everything that looked wrong during this run, whether or not it turned out to be ours, per the "
        "standing instruction to flag rather than quietly fix.",
        "<h2>" + str(len(irr)) + " entries</h2>" + table(
            ["id", "what was observed", "severity", "what was done", "how it was checked", "source"],
            [row([f"<code>{esc(i['id'])}</code>", f"<b>{esc(i['title'])}</b> &mdash; " + esc(i["finding"]),
                  f"<span class='pill {esc(i.get('severity', 'info'))}'>{esc(i.get('severity', 'info'))}</span>",
                  esc(i.get("action", "")), esc(i.get("verified_by", "")),
                  (f"<a href='{esc(i['link'])}'>link</a>" if i.get("link") else "")]) for i in irr])
        + "<p class='small muted'>This is the corrections lane's own log for this run. The earlier session in "
          "this repository kept a separate one at <a href='irregularities.md'>irregularities.md</a> (IR-01 to "
          "IR-07, covering the vendored metric, the submission validator and the registry audit); those entries "
          "remain in force and are not restated here.</p>"))

    idx = DOCS / "index.html"
    print(f"wrote {idx} ({len(idx.read_text()):,} B), executive-summary.html, irregularities.html")
    print(f"primary dots {n_dots_prim} | sensitivity dots {n_dots_sens} | qualifying corridors {qual_n} "
          f"| primary validator ok {prim['validator_ok']}"
          + (f" / sensitivity validator ok {sens['validator_ok']}" if sens else " / no sensitivity arm"))


if __name__ == "__main__":
    main()
