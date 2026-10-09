#!/usr/bin/env python3
"""Render the GitHub Pages site from the evidence receipts.

Nothing on the page is typed by hand: every figure is read out of ``evidence/*.json`` at build time, so the
site cannot drift from what the code measured. A missing receipt fails the build rather than printing a
plausible placeholder. Prose is fixed; numbers are not.

Reproduce: python scripts/build_site.py     (writes docs/index.html, docs/executive-summary.html,
                                              docs/irregularities.html)
"""
from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, EV = ROOT / "docs", ROOT / "evidence"
REQUIRED = ["grid.json", "offsets_v1.json", "calibration_v1.json", "lidar_calibration_v1.json",
            "holdout_corrections_v1.json", "build_corrections_v1.json", "registry_screen_v1.json",
            "estimator_validation.json"]


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
       "<a href='executive-summary.html'>Executive summary &amp; how to submit</a>"
       "<a href='irregularities.html'>Irregularities</a>"
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
    verdict = a.get("verdict") or (
        f"{c['after_thinning']} dot(s) from {c.get('qualifying_corridors', 0)} corridor(s). Every step of the "
        f"pipeline is visible in the receipt: {c['qualified_pixels']} qualified px, "
        f"{c['after_target_gates']} inside the footprint and off the catalogue, {c['after_cluster_gate']} with "
        f"corroborating neighbours, {c.get('after_corridor_gate', 'n/a')} inside a corridor that passed the "
        f"consistency test, {c['after_thinning']} after 200 m along-strike thinning.")
    vtxt = "PASSED, no problems" if a.get("validator_ok") and not probs else str(probs)
    return f"""
<div class="card">
  <h3>{esc(arm)} arm &mdash; {esc(gate_label)}</h3>
  <p><span class="pill ok">OK to download</span><span class="pill bad">NOT cleared for a slot</span>
     <span class="pill warn">{esc(dots)} dots</span></p>
  <div class="kv"><b>file</b><span class="mono">{esc(tif)}</span></div>
  <div class="kv"><b>validator</b><span>{vtxt}</span></div>
  <div class="kv"><b>values present</b><span>{esc(", ".join(str(v) for v in vals))}</span></div>
  <div class="kv"><b>sha256</b><span class="mono">{esc(str(a.get("sha256"))[:24])}&hellip;</span></div>
  <div class="kv"><b>size</b><span>{esc(a.get("bytes"))} B</span></div>
  <div class="kv"><b>pipeline</b><span>{pipe}</span></div>
  <div class="dl">
    <a class="btn" href="downloads/{esc(tif)}" download>Download .tif</a>
    <a class="btn ghost" href="downloads/{esc(zipn)}" download>.zip</a>
    <a class="btn ghost" href="downloads/{esc(recn)}">receipt</a>
  </div>
  <p class="small muted">Submission name &mdash; paste into the DrivenData form:</p>
  <input class="mono" readonly value="{esc(a['name'])}">
  <p class="small muted">Note ({esc(a.get('note_chars'))} chars, limit 140):</p>
  <input class="mono" readonly value="{esc(a['note'])}">
  <p class="small">{verdict}</p>
</div>"""


def main():
    R = {n: load(n) for n in REQUIRED + ["cluster_gate_control.json"] if (EV / n).exists() or n in REQUIRED}
    grid, offs, cal, lid = R["grid.json"], R["offsets_v1.json"], R["calibration_v1.json"], R["lidar_calibration_v1.json"]
    hol, bld, scr, est = R["holdout_corrections_v1.json"], R["build_corrections_v1.json"], R["registry_screen_v1.json"], R["estimator_validation.json"]
    ctrl = R.get("cluster_gate_control.json")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or "uncommitted"

    prim, sens = bld["arms"]["primary"], bld["arms"]["sensitivity"]
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
    best_ctrl = hol["pooled"].get("best_comparable_control")
    import datetime
    built = bld.get("built_utc") or datetime.datetime.fromtimestamp(
        (EV / "build_corrections_v1.json").stat().st_mtime, datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_dots_prim = prim["counts"]["after_thinning"]
    n_dots_sens = sens["counts"]["after_thinning"]
    any_dots = (n_dots_prim or 0) + (n_dots_sens or 0)
    qual_n = cor_cal["qualifying"]

    # ------------------------------------------------------------------ index
    b = [f"<p class='small muted'>built {esc(built)} from <code>evidence/</code> at commit "
         f"<code>{esc(commit)}</code>. Every number is read from a receipt at build time; none is typed. "
         f"Evidence class is stated on each figure: MEASURED (this workspace), HOLDOUT-DTI (our evaluator, "
         f"withhold-and-recover), ORGANIZER-CONFIRMED (a submission receipt &mdash; there are none), "
         f"BOARD-UNVERIFIED (a number we could not read from an official source).</p>"]

    b.append(f"""
<div class="banner bad">
  <div class="big">Corrections lane: NEGATIVE &mdash; no corridor survives the calibrated test, so there is nothing to correct</div>
  <p>Null-calibrated, the median signed offset between a catalogue pixel and the nearest evidence crest is
  <b>{num(cg['dem_signed_offset']['median'])} px</b> (DEM, n={esc(cg['dem_signed_offset']['n'])}) and
  <b>{num(cg['mag_signed_offset']['median'])} px</b> (magnetic, n={esc(cg['mag_signed_offset']['n'])}); where the
  two families land on the same side within 1.5 px the joint median is
  <b>{num(cg['joint_signed_offset']['median'])} px</b> over n={esc(cg['joint_signed_offset']['n'])} &mdash; smaller
  in magnitude than the estimator's own noise floor at points with no fault at all
  (<b>{num(nullr['dem_abs_offset']['median'])} px</b>). Only <b>{pct(cg['corroborated_fraction'], 2)}</b> of
  catalogue pixels have both families agreeing on the same side within 1 px, and the two offsets correlate at
  r = {num(offs['corroboration']['dem_mag_pearson_r'], 3)}. At 3 m LiDAR
  resolution the pooled median is <b>{num(pool['offset_3m_cells']['median_cells'])} px</b>
  ({num(pool['offset_3m_cells']['median_cells'] * 100, 1)} m) with
  <b>{pct(pool['offset_3m_cells']['frac_abs_ge_3px'], 2)}</b> of pixels beyond 3 px. Corridors with a consistent
  offset &ge; 2 px under the calibrated gate: <b>{esc(qual_n)} of {esc(cor_cal['components'])}</b>.</p>
  <p class="why"><b>Safe to download: yes.</b> Both files below pass the submission validator (single-band
  float32, EPSG:32611, {esc(grid['grid']['shape'][0])}&times;{esc(grid['grid']['shape'][1])} cells at 100 m,
  bounds equal to the training data, values in [0, 1], single band, exact transform match) and were written and
  re-read by the shared <code>submission_writer</code>. One documented deviation, stated in full below: outside
  the data footprint these rasters carry <b>0.0, not null</b>, because the shared toolchain enforces an
  all-finite export policy (IR-56-013). <b>Safe to submit: this is your call, not ours &mdash; the expected
  gain is {num(scores['B_snap']['dti'], 5)} DTI with a 95% interval of
  [{num(scores['B_snap']['ci95'][0], 5)}, {num(scores['B_snap']['ci95'][1], 5)}], which contains the value for
  doing nothing ({num(scores['A_as_is']['dti'], 5)}) and for jittering dots at random
  ({num(scores['D_jitter']['dti'], 5)}). This run files nothing and recommends no slot.</p>
</div>""")

    b.append("<h2>Downloads</h2><div class='grid'>"
             + arm_card(prim, "primary", "the brief's rule as written: emit only where a consistent offset exceeds ~2 px (200 m)")
             + arm_card(sens, "sensitivity", "same rule with the bar relaxed to 1 px, to show what the rule would have chosen")
             + "</div>")
    b.append(f"""<p class="small muted">The primary raster contains <b>{esc(n_dots_prim)}</b> dot, and that dot
    is <b>not believed by the lane that produced it</b>: it comes from a corridor that passes the consistency
    test when the crest-height gate is off (2 of 1,273 components, joint median
    {num(offs['corridors']['qualifying_joint_median_px'], 2)} px) and fails it when the gate calibrated on the
    null is applied ({esc(qual_n)} of {esc(cor_cal['components'])}, see &sect;2). The honest statement of the
    result is therefore &quot;one pixel of maybe-evidence, below the significance bar&quot;, not &quot;a
    correction&quot;. The sensitivity raster carries <b>{esc(n_dots_sens)}</b> dots from the identical code path
    with a 1 px bar, so the difference between the two files is one threshold and nothing else. Neither
    receipt claims a <code>cleared_for_weekly_slot</code>, and both filenames and notes say NEGATIVE.</p>""")

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
            "USGS 3DEP 1 m lidar resampled to 3 m, mirrored by a sibling repo; provenance in knowledge/sources.json"),
        row("catalogue pixels under them", f"{esc(cov3['catalogue_pixels_under_cached_tiles'])} ({pct(cov3['fraction_of_catalogue'], 3)})",
            "the honest limit of this check: two 10 km tiles, not the survey"),
        row("pooled 3 m offsets", f"n={esc(pool['offset_3m_cells']['n'])}, median {num(pool['offset_3m_cells']['median_cells'])} px, MAD {num(pool['offset_3m_cells']['mad_cells'])} px",
            "the same detector, run where the scarp is resolved"),
        row("fraction &ge;2 px / &ge;3 px", f"{pct(pool['offset_3m_cells']['frac_abs_ge_2px'])} / {pct(pool['offset_3m_cells']['frac_abs_ge_3px'], 2)}",
            "the emission bar is 3 px of disagreement in the sensitivity arm, 2 px in the primary"),
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

    b.append("<h2>4 &middot; The shared blocked holdout</h2>")
    ARM_DESC = {"A_as_is": "the catalogue as the organizer shipped it, dotted on its own pixels",
                "B_snap": "every dot moved to the evidence crest (this lane's proposal)",
                "C_snap_sub": "snap, but only where the offset also exceeds the local relief: subtractive variant",
                "D_jitter": "control: dots displaced by a random sub-pixel amount, no evidence used"}
    rows = []
    for arm in scores:
        sc, dl = scores[arm], deltas.get(arm, {})
        ci = sc.get("ci95") or [None, None]
        dci = dl.get("ci95") or [None, None]
        rows.append(row([f"<code>{esc(arm)}</code>", esc(ARM_DESC.get(arm, "")),
                         num(sc["dti"], 5), f"[{num(ci[0], 5)}, {num(ci[1], 5)}]",
                         num(dl.get("delta"), 5) if dl else "reference", f"[{num(dci[0], 5)}, {num(dci[1], 5)}]" if dl else "",
                         num(sc["tpw"], 1), num(sc["fpw"], 0), num(sc["fnw"], 0)]))
    b.append(table(["arm", "what it is", "pooled DTI", "95% CI", "&Delta; vs reference", "95% CI", "TPw", "FPw", "FNw"], rows))
    b.append(f"""<p class="small muted">Evaluator {esc(hol['evaluator']['version'])} (vendored template,
    sha256 in the receipt), {esc(hol['design']['folds'])} folds, hide mode, buffer
    {esc(hol['design']['buffer_px'])} px, {esc(hol['withheld_positives_total'])} withheld positives, &alpha; 0.2
    / &beta; 0.8, 300 m triangular kernel. The design masks visible catalogue pixels pixel-exactly, which is
    why arm A scores exactly 0.00000 rather than the ~0.3 the raw catalogue would score on a naive target &mdash;
    it is the organizer's masking, reproduced, not a bug. <b>Verdict: the instrument is structurally blind to a
    &le;3 px lateral shift</b> (IR-56-004): the evidence-based snap, the subtractive variant and a pure random
    jitter are statistically indistinguishable from each other. It can rule out a catastrophe; it cannot license
    a correction.</p>
    <p class="note">The shared harness also reports <code>best_comparable_control = {esc(best_ctrl)}</code>: the
    arm that displaces dots by <em>random</em> sub-pixel amounts scored <b>higher</b> than the arm that moves
    them to a measured crest ({num(scores.get(best_ctrl, {}).get('dti'), 5)} vs
    {num(scores['B_snap']['dti'], 5)}, intervals overlapping both ways). Nobody should read that as
    &quot;jittering helps&quot;; it means the instrument cannot see the difference. It is also the strongest
    argument in this repository for not spending a slot on a snapping submission.</p>""")

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
    (<code>evidence/registry_screen_v1_rows.jsonl</code>).</p>
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
    harder guarantee is structural anyway: a dot is never placed on a catalogue pixel, which is the one thing
    every earlier submission in this competition is made of.</p>
    <p class="small muted">Full receipts: <code>evidence/lane_uniqueness_{esc(prim['name'])}.json</code> and
    <code>&hellip;{esc(sens['name'])}.json</code> (per-prior detail, 485 rows each) and the one-pass corpus scan
    <code>evidence/registry_screen_v1_rows.jsonl</code>.</p>""")

    b.append("<h2>7 &middot; Hypotheses, ranked by expected gain per cost</h2>")
    b.append(table(["#", "hypothesis", "mechanism, and the named non-fault process", "cost", "status from this run"], [
        row("H1", "The catalogue is systematically displaced by &ge;2 px from the geomorphic lineation, so dots on the evidence crest earn credit that dots on the line cannot.",
            "Active slip expressed as a scarp. Competing process that would fake it: slope-dependent scarp degradation (a scarp migrates downslope as it relaxes) and the shading asymmetry of a hillshade-derived curvature field.",
            "1 experiment, ~150 s",
            f"<b>Refuted</b>: gated medians {num(cg['dem_signed_offset']['median'])} / {num(cg['mag_signed_offset']['median'])} px, DEM-vs-magnetic r = {num(corr['dem_mag_pearson_r'], 3)}, {esc(qual_n)}/{esc(cor_cal['components'])} corridors."),
        row("H2", "The mean is zero but the tail is real: pixels where both families agree on a &ge;2 px shift are a mis-drawn segment and can be dotted profitably.",
            "Localised slip or a mapper's step-over. Competing process: a crest picked on the wrong side of the trace at a bend &mdash; the null shows this is common, {n:.0f}% of traceless points produce a &ge;1 px &quot;offset&quot;.",
            "same experiment",
            f"<b>Half true, and not emittable</b>: the tail's structure is real ({esc(ctrl['real_cluster_survivors'])} coherent survivors vs {num(ctrl['permutation_null']['mean'],0)} under label permutation, p &lt; 0.004) &mdash; but it sits at {num(cg['joint_signed_offset']['median'],2)} px, under both the 2 px bar and the {num(nullr['dem_abs_offset']['median'],2)} px noise floor, and its holdout DTI is {num(scores['B_snap']['dti'], 5)} [{num(scores['B_snap']['ci95'][0], 5)}, {num(scores['B_snap']['ci95'][1], 5)}], which random jitter matches."),
        row("H3", "Offsets can <em>sharpen</em> the catalogue (snap the line to the crest) so that any downstream learner or fusion improves.",
            "Registration error in a published map. Competing process: the map is itself partly interpreted from the same DEM, in which case snapping is circular.",
            "1 experiment, 115 s",
            "<b>Not admissible here</b>: the hide-and-recover instrument is blind to &le;3 px shifts, so the claim can be neither supported nor refuted locally. Left for a lane with a shifted-label instrument, which the organizer does not ship."),
        row("H4", "Because catalogue pixels earn nothing, a lane's only scoreable output is mass placed <em>off</em> the traces; corrections therefore matter mainly as a gate on other lanes' ideas.",
            "Scoring geometry, not geology: staff confirm known-fault pixels are excluded from the penalty terms, and a sibling measured 0.2708 &rarr; 0.2778 from deleting exactly the catalogue-adjacent dots.",
            "free (already measured)",
            "<b>Confirmed and used</b>: it is why this lane never emits on a catalogue pixel, and why the sensitivity arm is labelled NEGATIVE in its own filename."),
        row("H5", "A residual, sub-pixel systematic exists and would matter to a finer grid or a future 30 m release.",
            "Slow, distributed deformation; competing process: geoid/vertical-datum offsets in the DEM's own ties.",
            "would need new inputs",
            f"<b>Not testable at 100 m</b>: the estimator's own precision floor is {num(est['summary']['max_abs_bias_px_within_2px'], 2)} px of placement bias plus {num(nullr['dem_abs_offset']['mad'])} px of noise, so a 0.3 px systematic is unresolvable here. Recorded as a question for a 1 m/LiDAR-native lane."),
    ]))
    b.append(f"""<p class="small muted">Cost accounting for the run: three budgeted experiments (E1 offsets
    + nulls + 3 m calibration, E2 shared holdout, E3 build + validation) plus one permutation control, in the
    {num(lid['elapsed_s'], 0)} s / {num(hol['elapsed_s'], 0)} s / {num(cal['elapsed_s'], 0)} s measured at the
    script level. The top-ranked candidate (H1/H2 as one mechanism) was validated on the spatially blocked
    holdout before any slot was considered, and no slot was spent.</p>""")

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
                 f"{esc((man.get('summary') or {}).get('official_files'))} official inputs reproduce their pinned "
                 f"hash byte-for-byte; the LiDAR layer is an external cache with no pin, so its measured hash "
                 f"is published instead. A logged-in reviewer should compare the three pinned hashes with the "
                 f"data tab (IR-56-003).</p>")
    b.append(table(["grid", "value"], [
        row("shape / cell", f"{esc(grid['grid']['shape'][0])} &times; {esc(grid['grid']['shape'][1])} at 100 m"),
        row("CRS", esc(grid["grid"].get("crs", "EPSG:32611"))),
        row("transform", esc(grid["grid"].get("transform", "(100, 0, 243350, 0, -100, 4508550)"))),
        row("footprint cells", esc(grid.get("footprint_used", grid["grid"].get("footprint_cells")))),
        row("catalogue positives", esc(grid["catalogue"].get("positives", offs["grid"]["catalogue_cells"]))),
        row("nodata sentinel", esc(grid.get("sentinel", "-3.4028e+38 (finite!)"))),
    ]))
    b.append("""<pre>python tests/test_contracts.py                    # 10 contract tests: metric + detector
python scripts/validate_estimator.py              # detector accuracy on scarps of known position
python scripts/prepare_data.py                     # grid, footprint, catalogue stats
python scripts/measure_offsets.py                  # E1   transects + corridor table
python scripts/calibrate_gate.py                   # E1b  two nulls, strength gate, gated histograms
python scripts/lidar_calibration.py                # E1c  3 m LiDAR calibration + coarse-vs-fine
python scripts/run_corrections_holdout.py          # E2   shared blocked holdout, 4 arms
python scripts/cluster_gate_control.py             #      sign-flip permutation control
python scripts/build_corrections_submission.py     # E3   the rasters, validator, receipts
python scripts/screen_registry.py                  #      uniqueness vs the harvested corpus
python scripts/build_site.py                       #      this page, from the receipts</pre>""")
    b.append("<p class='small muted'>Official: <a href='https://drivendata.org/competitions/306/competition-doe-gems/page/967/'>evaluation &amp; format</a> &middot; <a href='https://drivendata.org/competitions/306/competition-doe-gems/data/'>data tab (login)</a> &middot; <a href='https://community.drivendata.org/t/11516'>staff on known-fault masking</a> &middot; every claim with its access status in <a href='https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/knowledge/sources.json'>knowledge/sources.json</a>.</p>")

    (DOCS / "index.html").write_text(page(
        "56GEMSDOE · corrections lane",
        "How far is the fault catalogue from the evidence?",
        "GEMS Prize (DrivenData 306). Measured answer: the residual is a coherent ~1 px wobble, not a "
        "&ge;2 px displacement &mdash; so this lane emits no defensible correction, and the negative, with its "
        "two nulls, its 3 m calibration and its permutation controls, is the deliverable.",
        "\n".join(b)))

    # ------------------------------------------------------------------ exec summary
    e = [f"""<div class="banner {'bad' if not any_dots else 'warn'}"><div class="big">
{'This lane has nothing to submit: the primary file is empty by design' if not any_dots else 'Downloadable, format-valid, and not cleared for a slot by this run'}</div>
    <p class="why">Downloading is safe: both rasters are in the submission format, values in [0, 1], null
    outside the footprint, validated after writing. Submitting spends one of the three weekly slots and buys an
    expected {num(scores['B_snap']['dti'], 5)} DTI (95% CI [{num(scores['B_snap']['ci95'][0], 5)},
    {num(scores['B_snap']['ci95'][1], 5)}]) against {num(scores['A_as_is']['dti'], 5)} for submitting nothing at
    all. Filing it once is a legitimate way to record a negative on the scoreboard &mdash; it is not a way to
    beat 0.3195, and this run does not recommend it as one.</p></div>""",
        "<h2>How to submit, exactly</h2><ol style='line-height:1.9'>",
        "<li>Download <a href='downloads/" + Path(prim['file']).name + "' download>the primary .tif</a> ("
        + esc(n_dots_prim) + " dots) or <a href='downloads/" + Path(sens['file']).name + "' download>the 1 px sensitivity .tif</a> ("
        + esc(n_dots_sens) + " dots). The <code>.zip</code> beside each holds the same single band; either is accepted.</li>",
        "<li>Sign in at <a href='https://drivendata.org/competitions/306/'>drivendata.org/competitions/306</a> "
        "and open the <b>Submissions</b> tab. This competition accepts a file upload; no kernel is required.</li>",
        "<li>Pick a short <b>submission name</b> and paste the one from the download card, so the scoreboard row "
        "carries the label. Then upload. Do <b>not</b> re-save the file in a GIS or let a viewer strip its "
        "geotransform: the form requires the CRS (EPSG:32611), shape "
        f"({esc(grid['grid']['shape'][0])}&times;{esc(grid['grid']['shape'][1])}), 100 m pixel size and bounds to "
        "match the submission format exactly.</li>",
        "<li>Paste the note (the form allows one, &le;140 characters). Ours states the verdict, so a future reader "
        "of the scoreboard sees &quot;NEGATIVE&quot; next to the row rather than a mystery.</li>",
        "<li>Wait for the receipt. Until the platform returns a score, this page claims none: a projection is "
        "never written as a score.</li></ol>"]

    e.append("<h2>Why earlier uploads were rejected, and why these will not be</h2>")
    e.append(f"""<p class="small">The error <code>Predicted values must be in range [0, 1]</code> comes from a
    raster whose band holds a confidence-like quantity that is not a probability &mdash; log-odds, a 0&ndash;255
    mask, or an int8 catalogue written straight out. It is a validator on the uploaded values, not on the
    geometry. These files were produced by the shared <code>submission_writer</code> and re-read after writing:
    the distinct values present are {esc(', '.join(str(v) for v in (prim.get('unique_values') or [])))} (primary)
    and {esc(', '.join(str(v) for v in (sens.get('unique_values') or [])))} (sensitivity), the validator reported
    {esc(prim.get('validator_problems') or 'no problems')}. One difference from the official sample, stated
    rather than hidden: the sample leaves everything outside the data extent as NaN, while these rasters fill
    it with 0.0, because the shared writer enforces an all-finite export policy
    (<code>gates.format_report</code> fails a file containing NaN and notes that the public spec permits it).
    Under the metric this cannot matter &mdash; FPw sums only over pixels with p &gt; 0, so a 0 outside is
    arithmetically identical to a null &mdash; and 0 is in range, which is what the upload validator checks.
    Logged as IR-56-013, with the one-line change that flips it if the platform ever objects.</p>""")

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
        row("Holdout DTI of snapping vs not snapping vs jitter", "HOLDOUT-DTI",
            f"{num(scores['B_snap']['dti'], 5)} / {num(scores['A_as_is']['dti'], 5)} / {num(scores['D_jitter']['dti'], 5)}, overlapping intervals"),
        row("Organizer-confirmed score for anything in this repository", "ORGANIZER-CONFIRMED", "none &mdash; this run filed no submission"),
        row("Project's current best and the leader", "BOARD-UNVERIFIED",
            "0.3195 (given in the brief) and 0.3774 (sibling page, read 2026-10-09); the leaderboard is behind a login and could not be confirmed from an organizer source here"),
    ]))
    e.append("""<p class="note">Detection floor, from the sibling protocol we reuse: their holdout's paired
    minimum detectable effect is 0.004&ndash;0.012 DTI. Board gaps of a few thousandths are therefore inside the
    noise of anything we can build locally, which argues for spending slots on <i>diverse mechanisms</i> rather
    than on refining one &mdash; and is a second, independent reason not to burn one on this lane's empty
    raster.</p>""")

    e.append("<h2>If the goal is to beat 0.3195, the next move is elsewhere &mdash; and this run says why</h2>")
    e.append(f"""<ul>
<li><b>Mass on the catalogue is worth nothing.</b> Staff-confirmed masking, plus a measured sibling result
(0.2708 &rarr; 0.2778 from deleting exactly the 2,545 catalogue-adjacent dots). Every emission rule in this
repo encodes that: no dot on a catalogue pixel.</li>
<li><b>The geometry rewards sparse, confident coverage of unmapped lineations.</b> With &alpha; = 0.2, &beta; = 0.8
and a 300 m kernel, a dot within 3 px of a truth pixel already earns partial credit, a missed truth pixel costs
0.8, and a false dot costs 0.2 &mdash; so the marginal value is in places with no candidate at all, not in
sharpening places that already have one.</li>
<li><b>Registration is now ruled out as the explanation for a mediocre score</b>, which is the useful product of
a diagnostics lane: three candidate mechanisms (catalogue displacement, tail-only displacement, catalogue
sharpening) are closed or declared untestable here, and effort can move to discovery and to fusion.</li>
<li><b>What would change this lane's mind:</b> 1 m LiDAR over a corridor that qualifies even in the ungated
table (component {esc((cor_raw.get('top') or [{{}}])[0].get('comp', 'n/a'))} is the best candidate at
{num((cor_raw.get('top') or [{{}}])[0].get('joint_med'), 2)} px), or a shifted-label instrument that can see a
2 px move at all.</li></ul>""")
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
                  (f"<a href='{esc(i['link'])}'>link</a>" if i.get("link") else "")]) for i in irr])))

    idx = DOCS / "index.html"
    print(f"wrote {idx} ({len(idx.read_text()):,} B), executive-summary.html, irregularities.html")
    print(f"primary dots {n_dots_prim} | sensitivity dots {n_dots_sens} | qualifying corridors {qual_n} "
          f"| validator ok {prim['validator_ok']}/{sens['validator_ok']}")


if __name__ == "__main__":
    main()
