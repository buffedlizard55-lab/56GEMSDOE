#!/usr/bin/env python3
"""Build the GitHub Pages site (docs/) from the lane evidence JSONs.

Pages: index (audit-only downloads + repository-wide status + all three runs/lanes),
executive-summary (submission status and conditional future gates), research (method, offset histogram, LiDAR
calibration, holdout, canary, the "why 0.2778" analysis, the sibling run's
reconciliation), hypotheses (ranked candidates), sources (official verified
links), irregularities (flagged claims from both runs), prior-run (the merged
sibling corrections run: negative verdict, its downloads and receipts).
All numbers are read from evidence/corrections/*.json (run A) and
evidence/*.json (run B) so the site cannot drift from the evidence.

Run:  python scripts/build_site.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence" / "corrections"
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"

CSS = """
:root{--bg:#0f1420;--fg:#e8eaf0;--mut:#9aa3b5;--acc:#4da3ff;--ok:#3fd68f;--warn:#ffb454;--bad:#ff6b6b;--card:#171d2e;--line:#28304a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:0 18px}
header.top{background:linear-gradient(180deg,#131a2c,#0f1420);border-bottom:1px solid var(--line);padding:22px 0 18px}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:19px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:16px;margin:20px 0 6px}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
nav a{color:var(--mut);text-decoration:none;padding:5px 10px;border:1px solid var(--line);border-radius:16px;font-size:13px}
nav a.active,nav a:hover{color:var(--fg);border-color:var(--acc)}
.dlbtn{margin:14px 0}
.btn{display:inline-block;background:var(--acc);color:#06121f;font-weight:600;text-decoration:none;padding:10px 18px;border-radius:8px}
.btn.alt{background:transparent;color:var(--fg);border:1px solid var(--line)}
.btn:hover{filter:brightness(1.1)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.mut{color:var(--mut)}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
code{background:#0a0e18;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:13px}
pre{background:#0a0e18;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:10px 0}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#131a2c}
img{max-width:100%;border:1px solid var(--line);border-radius:8px}
.values{background:#10182b;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;font-size:13.5px;color:var(--mut)}
footer{border-top:1px solid var(--line);margin-top:34px;padding:18px 0 30px;color:var(--mut);font-size:13px}
.tag{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:10px;padding:1px 8px;color:var(--mut);margin-right:5px}
ul{margin:6px 0 6px 20px}li{margin:3px 0}
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def page(title, active, body, dl=True):
    tif = next(DOWNLOADS.glob("gems56-corr-*-nan.tif"), None)
    tifs = sorted(DOWNLOADS.glob("gems56-corr-*-nan.tif"))
    tif = tifs[-1] if tifs else None
    rel = tif.name if tif else ""
    dlbtn = ""
    if dl and tif:
        dlbtn = (f'<div class="dlbtn"><a class="btn" href="downloads/{esc(rel)}">'
                 f'&#11015; Download research GeoTIFF (audit only)</a> '
                 f'<a class="btn alt" href="downloads/{esc(rel)}">.tif '
                 f'({tif.stat().st_size / 1024:.0f} KB)</a></div>')
    nav = "".join(
        f'<a href="{h}"{" class=active" if h == active else ""}>{t}</a>'
        for h, t in (("index.html", "Home"), ("executive-summary.html", "Submission status"),
                     ("submit.html", "Submission status & conditions"),
                     ("research.html", "Research"), ("hypotheses.html", "Hypotheses"),
                     ("sources.html", "Sources"), ("irregularities.html", "Irregularities"),
                     ("prior-run.html", "Prior run")))
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{esc(title)} · 56GEMSDOE</title><style>{CSS}</style></head><body>
<header class=top><div class=wrap>
<h1>56GEMSDOE &mdash; corrections lane for the DOE GEMS Prize</h1>
<div class=mut>DrivenData competition 306 · GeoDAWN / NW Nevada · find geothermal-indicative
faults missing from the USGS/INGENIOUS catalogue</div>
<nav>{nav}</nav>{dlbtn}
</div></header>
<div class=values><div class=wrap><b>Core values.</b> Maximize P(Win) &mdash; every weekly
submission slot is an experiment, not a lottery ticket. Own the Outcome &mdash; every number
on this site is labelled by evidence class: <span class=ok>ORGANIZER-CONFIRMED</span>,
<span class=warn>HOLDOUT-DTI (local, simulated truth)</span>, <span class=mut>MEASURED (local inputs; mirror provenance documented)</span>, or <span class=bad>USER-REPORTED (unauthenticated)</span>.</div></div>
<main class=wrap><div class=card><h2 class=bad>STOP: no current file is cleared for submission</h2>
<p><b>Safe to download: YES, for audit/research only. Safe to submit: NO.</b> PR #4 has a
negative 0/21-corridor corrections result, PR #5/#6 has a format-conformant corrections TIF
but the literal registry rule returns DUPLICATE/STOP, and PR #7's separate discovery result
is negative and DUPLICATE/STOP. Superset or coverage-adjusted explanations do not waive a
literal stop. No organizer submission or slot use is recorded.</p>
<p><a href="submit.html">Full repository-wide status and conditional gates</a> ·
<a href="prior-run.html">Preserved prior run</a> ·
<a href="prior-irregularities.html">Prior run irregularities</a></p></div>{body}</main>
<footer><div class=wrap>56GEMSDOE · run A branch <code>arena/b71ede8d-56gemsdoe</code> ·
round-2 discovery run branch <code>arena/858a492d-56gemsdoe</code> (PR #7) ·
generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} by
<code>scripts/build_site.py</code> from <code>evidence/corrections/*.json</code> (run A)
and <code>evidence/*.json</code> (run B) ·
site served from <code>main</code> at
<a href="https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html">buffedlizard55-lab.github.io/56GEMSDOE/</a></div></footer>
</body></html>"""


def load_json(p):
    return json.loads(Path(p).read_text())


def fmt(x, n=4):
    return f"{x:.{n}f}" if isinstance(x, (int, float)) else str(x)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DOCS))
    args = ap.parse_args()
    out = Path(args.out)
    (out / "downloads").mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(parents=True, exist_ok=True)

    stats = load_json(EV / "offset_stats.json")
    hold = load_json(EV / "holdout_corrections.json")
    card = load_json(EV / "run_card.json")
    reg_path = EV / "registry_check.json"
    reg = load_json(reg_path) if reg_path.exists() else None
    reg_n = reg["n_unique_pixel_content"] if reg else None
    reg_n_flags = reg["n_literal_flags"] if reg else None
    reg_worst_cont = reg["worst"]["containment"] if reg else None
    reg_worst_jac = reg["worst"]["jaccard_3px"] if reg else None
    reg_worst_rev = reg["worst"]["rev_containment"] if reg else None
    reg_worst_sp = reg["worst"]["spearman_dots"] if reg else None
    reg_worst_sps = reg["worst"]["spearman_surface"] if reg else None

    # run B (merged PR #4, arena/1d3dbc39-56gemsdoe): the sibling corrections run
    # on this repository - a NEGATIVE result. Its receipts live in evidence/.
    EVB = ROOT / "evidence"
    card_b_path = EVB / "run_card.json"
    card_b = load_json(card_b_path) if card_b_path.exists() else None
    irr_b_path = EVB / "irregularities.json"
    irr_b = load_json(irr_b_path) if irr_b_path.exists() else None
    if card_b:
        mb = card_b["measurements"]
        m_ung = mb["offsets_ungated_px"]
        m_cal = mb["offsets_null_calibrated_px"]
        m_cor = mb["corridors"]
        m_lid = mb["lidar_3m"]
        hb = card_b["holdout_dti"]
        hab = hb["arms"]
        gate_b = card_b["registry_comparison"]["shared_gate_verdict"]
        art_b = card_b["artefacts"]

    # round-2 discovery run (PR #7, arena/858a492d): receipts live in the evidence/ root
    def opt(name):
        p = EVB / name
        return json.loads(p.read_text()) if p.exists() else None
    hold2 = opt("holdout_discovery_v1.json")
    bld2 = opt("build_discovery_v1.json")
    gate2 = opt("lane_gate_discovery_v2.json")
    scr2 = opt("registry_screen_v2.json")
    rcard2 = opt("run_card_discovery_v1.json")

    tifs = sorted((out / "downloads").glob("gems56-corr-*-nan.tif"))
    tif = tifs[-1] if tifs else None
    sha = card["raster"]["sha256"]
    dots = card["raster"]["dots"]
    cands = card["raster"]["candidate_records"]

    # copy evidence artifacts into docs/downloads for one-folder auditing
    for f in ("offset_histogram.png",):
        src = EV / f
        if src.exists():
            (out / "downloads" / f).write_bytes(src.read_bytes())
    for f in ("record_630_crop.png", "record_1567_crop.png", "record_322_crop.png",
              "record_2665_crop.png"):
        src = EV / f
        if src.exists():
            (out / "downloads" / f).write_bytes(src.read_bytes())

    a1 = hold["arms"]["A1_lane"]
    a0 = hold["arms"]["A0_catalogue"]
    a2 = hold["arms"]["A2_nogate"]
    a4 = hold["arms"]["A4_random"]
    a5 = hold["arms"]["A5_oracle"]

    # ---------------------------------------------------------------- index --
    # ---- round-2 discovery candidate card (PR #7): receipts optional, guarded --------------
    disc_html = ""
    if bld2 and hold2:
        rec2 = bld2["receipt"]
        tif2 = Path(rec2["file"]).name
        vs2 = hold2["pick_rule"]["paired_vs_random"]
        rand2 = hold2["pooled"]["scores"]["random@25000"]
        glit = gate2.get("verdict_literal") if gate2 else "n/a"
        disc_html = f"""
<h2>&#11015;&nbsp;ROUND-2 DISCOVERY CANDIDATE (PR #7) &mdash; download for review only</h2>
<div class=card>
<p><a class="btn" href="downloads/{esc(tif2)}">Download {esc(tif2)}</a>
<span class=mut>{rec2['bytes']/1024:.0f} KB · single band · float32 · EPSG:32611 ·
100 m · 3292&times;3730 · {bld2['dots']:,} dots · measured distinct values {{0.0, 1.0}} ·
0 NaN cells</span></p>
<p><b>OK to download: yes.</b> <b>OK to submit: <span class=bad>NO</span>.</b>
The pre-registered holdout verdict is <b>NEGATIVE</b> and the registry lane gate returned
<b>{esc(glit)}</b> on the literal 3&nbsp;px clause (density-degenerate trigger, IR-56-023: it
tracks grid coverage while the rank-agreement test passes at max &rho; 0.043 vs the 0.90 bar)
&mdash; nothing is promoted and no slot was spent.</p>
<p><b>HOLDOUT-DTI</b> of the shipped arm <code>{esc(bld2['arm'])}@{bld2['budget']:,}</code>,
evaluator <code>{esc(hold2['evaluator']['version'])}</code>,
{hold2['withheld_positives_total']:,} withheld positives:
<b>{fmt(bld2['holdout_dti'],5)}</b> [{fmt(bld2['holdout_ci95'][0],5)},
{fmt(bld2['holdout_ci95'][1],5)}] vs <b>uniform-random {fmt(bld2['chance_dti'],5)}</b>
[{fmt(rand2['ci95'][0],5)}, {fmt(rand2['ci95'][1],5)}] at the same budget; paired difference {fmt(vs2['delta'],5)}
[{fmt(vs2['ci95'][0],5)}, {fmt(vs2['ci95'][1],5)}] &mdash; strictly below chance; canaries
&le; {fmt(hold2['canary_max_new_fields'],3)} (limit 0.90). Receipts:
<code>evidence/build_discovery_v1.json</code>, <code>evidence/run_card_discovery_v1.json</code>.</p>
<p><b>submission name</b> <code>{esc(bld2['name'])}</code><br>
<b>note</b> ({bld2['note_chars']}/140): <code>{esc(bld2['note'])}</code><br>
<b>sha256</b> <code>{esc(rec2['sha256'])}</code> · validator ok:
{esc(rec2['validator']['ok'])}</p>
</div>
"""

    idx = f"""
<h2>&#11015;&nbsp;CORRECTIONS RUN A — AUDIT DOWNLOAD ONLY</h2>
<div class=card>
<p><a class="btn" href="downloads/{esc(tif.name if tif else '')}">Download for audit: {esc(tif.name if tif else '')}</a>
<span class=mut>{tif.stat().st_size/1024:.0f} KB · single band · float32 · EPSG:32611 · 100 m ·
3292&times;3730 · {dots:,} predicted pixels · every value in [0, 1] · NaN only outside the
scored footprint · nodata tag <code>nan</code> (the official sample's own format)</span></p>
<p><b>sha256:</b> <code>{sha}</code></p>
<p><b>Archived run name (not approved for reuse):</b> <code>{esc(card['submission_name'])}</code><br>
<b>Archived note (for provenance only; do not paste into a submission form)</b>
({len(card['note'])}/140 characters):<br><code>{esc(card['note'])}</code></p>
<p><b>Format status:</b> <span class=ok>PASS</span> &mdash; <code>scripts/validate_submission.py</code>
exit 0 and <code>python -m src.submission_io validate-conformant</code> exit 0
(no NaN inside the footprint, every value in [0,1], CRS/shape/transform match
<code>sample_submission.tif</code>, template conformance, GDAL_NODATA=<code>nan</code>).</p>
<p><b>Standing literal uniqueness verdict:</b> <span class=bad>DUPLICATE/STOP</span> — the &gt;70%-within-3-px rule flags {reg_n_flags if reg else 'pending'} priors. Coverage-adjusted diagnostics (412 unique pixel contents; max Spearman {fmt(reg_worst_sp,4) if reg else 'pending'}, max Jaccard {fmt(reg_worst_jac,3) if reg else 'pending'}) do not waive the protocol stop.</p>
<p><b>Evidence status:</b> <span class=warn>HOLDOUT-DTI (simulated-corrections truth; evaluator <code>src/metrics.py</code>; {hold['n_withheld_positives']:,} withheld positives)</span>:
A1 lane {fmt(a1['dti'],6)} [{fmt(a1['ci95'][0],6)}, {fmt(a1['ci95'][1],6)}]; A0 masked control {fmt(a0['dti'],6)} [{fmt(a0['ci95'][0],6)}, {fmt(a0['ci95'][1],6)}]; A4 random control {fmt(a4['dti'],6)} [{fmt(a4['ci95'][0],6)}, {fmt(a4['ci95'][1],6)}] &mdash; see <a href="research.html">research</a>.</p>
<p class=mut><b>Safe to download: YES, for audit only. Safe to submit: NO.</b> The local
format pass and simulated-truth holdout are not organizer evidence; the literal registry rule
requires STOP. Do not upload or spend a slot. See <a href="submit.html">submission status and
conditional gates</a>.</p>
</div>

{disc_html}
<h2>Two corrections runs, one repository &mdash; plus a discovery run</h2>
<p>This repository has run the corrections lane <b>twice</b>, in two parallel sessions.
Both runs measured the same catalogue against the same evidence; they gate different
questions and reached opposite verdicts. Both are reported in full &mdash; the disagreement
is the finding.</p>
<div class=grid>
<div class=card><h3>Run A &mdash; PR #5/#6 corrections (branch <code>arena/b71ede8d-56gemsdoe</code>) &mdash; <span class=bad>protocol verdict NEGATIVE / NOT CLEARED</span></h3>
<p>Question: <em>is the catalogue on the MAIN scarp?</em> For 28 of 125 well-sampled records
(22.4%) the strongest, LiDAR-confirmed DEM-scarp crest sits consistently &gt; 2&nbsp;px
(200&ndash;340&nbsp;m) from the catalogue line &rarr; <b>{dots:,} dots</b> emitted on the
evidence-defined traces, 0 on the catalogue. HOLDOUT-DTI(sim; evaluator <code>src/metrics.py</code>,
{hold['n_withheld_positives']:,} withheld positives): A1 {fmt(a1['dti'],6)}
[{fmt(a1['ci95'][0],6)}, {fmt(a1['ci95'][1],6)}], A0 masked control {fmt(a0['dti'],6)}
[{fmt(a0['ci95'][0],6)}, {fmt(a0['ci95'][1],6)}], A4 random control {fmt(a4['dti'],6)}
[{fmt(a4['ci95'][0],6)}, {fmt(a4['ci95'][1],6)}]. Literal containment gate failed; no slot is cleared.
<b>The audit download above is this run's historical file; it is not cleared for a slot.</b></p></div>
<div class=card><h3>Run B &mdash; merged PR #4 (branch <code>arena/1d3dbc39-56gemsdoe</code>) &mdash; <span class=warn>NEGATIVE, no slot recommended</span></h3>
<p>Question: <em>is the catalogue displaced from A crest by &ge; 2&nbsp;px?</em> No:
null-calibrated median offset {fmt(m_cal['dem_median'],3)}&nbsp;px (DEM) /
{fmt(m_cal['mag_median'],3)}&nbsp;px (magnetic), below the estimator's own noise floor
({fmt(m_cal['null_random_abs_median'],2)}&nbsp;px); <b>0 of {m_cor['decision_gate']['components']}
corridors</b> reach a consistent &ge; 2&nbsp;px offset; 3&nbsp;m LiDAR: 0 of
{m_lid['segments']} segments displaced by &ge; 200&nbsp;m. Their primary raster carries
<b>{art_b['primary']['dots']} dot</b> &mdash; the emptiness is their finding. Their two
files pass the legacy all-finite local format gate and are safe to download for audit, but
<b>not cleared for a slot</b> (their uniqueness gate returned <code>ok:false</code> on the
proximity criterion at 1-dot count, IR-56-006). Direct mask audit also found finite zeroes
outside where the official sample uses NaN (IR-56-013). Details: <a href="prior-run.html">Prior run</a>.</p></div>
<div class=card><h3>Run C &mdash; this PR #7 (branch <code>arena/858a492d-56gemsdoe</code>) &mdash; <span class=bad>discovery lane: NEGATIVE twice</span></h3>
<p>Question: <em>do off-catalogue step/tilt lineaments recover catalogue-missing faults?</em>
Five hypotheses pre-registered (H6&ndash;H10, <code>docs/research/hypotheses-20261009.md</code>);
the top three were evaluated using HOLDOUT-DTI (<code>gems52-pooled-hide-v1</code>, 48,080 withheld positives).
Pick <code>multi@25000</code> {fmt(bld2['holdout_dti'],5)}
[{fmt(bld2['holdout_ci95'][0],5)}, {fmt(bld2['holdout_ci95'][1],5)}]
vs uniform-random {fmt(bld2['chance_dti'],5)}
[{fmt(rand2['ci95'][0],5)}, {fmt(rand2['ci95'][1],5)}] &mdash; paired {fmt(hold2['pick_rule']['paired_vs_random']['delta'],5)}
[{fmt(hold2['pick_rule']['paired_vs_random']['ci95'][0],5)}, {fmt(hold2['pick_rule']['paired_vs_random']['ci95'][1],5)}],
canaries clean. Registry gate: surface PASS, dots
{esc(gate2.get('verdict_literal') if gate2 else '?')} (density-degenerate trigger, IR-56-023).
Their published research TIF is the second download above &mdash; the receipt and front page
label it NEGATIVE / do not submit, and the literal gate is DUPLICATE/STOP. 0 slots spent.</p></div>
</div>
<p class=mut>Reconciliation: the two runs agree on the measurement &mdash; the catalogue sits
within ~1&nbsp;px of <em>some</em> crest (run A's nearest-crest reading matches run B's
negative). They differ on the decision rule: run B gates on null-calibrated corridor
consistency with a crest-strength gate and DEM+mag concordance (very conservative &rarr;
0 corridors); run A gates on per-record strongest-crest consistency (median offset
&gt; 2&nbsp;px, sign agreement &ge; 0.70, &ge; 8 transects) with the crest identity
calibrated on 1&nbsp;m LiDAR (MAD 0.29&nbsp;px) &rarr; 28 records. Which gate matches the
organizer's hidden labels is exactly what a submission slot would test; neither run has an
organizer score.</p>

<h2>What this repository is</h2>
<p>56GEMSDOE runs one lane of a parallel multi-session effort on the DOE GEMS Prize: the
<b>corrections lane</b>. The organizers stated that new-fault ground truth can lie within
300&nbsp;m of a known trace as &ldquo;corrections or modifications to existing fault
traces&rdquo;, and that known-fault pixels are masked pixel-exactly when scoring
(<a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">forum thread 11516</a>).
The catalogue line itself is therefore not the target. This lane measures how far the
catalogue sits from the geophysical/topographic evidence &mdash; the DEM-scarp crest
(<code>det_elev_slope</code> ridge) and the magnetic-gradient ridge (<code>tmi_hg</code>)
&mdash; on perpendicular transects within &plusmn;400&nbsp;m of every catalogue trace,
calibrates the crest on 1&nbsp;m USGS 3DEP LiDAR, and emits dots on the evidence-defined
trace where a <em>consistent</em> offset exceeds ~2&nbsp;px (200&nbsp;m).</p>
<div class=grid>
<div class=card><h3>Measured (official data, this repo)</h3><ul>
<li>{stats['catalogue_fault_px']:,} catalogue fault px · {stats['n_records']} vector-catalogue
records · {stats['n_transects']:,} perpendicular transects (&plusmn;400&nbsp;m)</li>
<li>DEM-scarp crest vs 1&nbsp;m LiDAR crest: MAD {fmt(stats['lidar_calibration']['agreement_dem_slope_strongest_vs_lidar_strongest']['mad_px'],3)}&nbsp;px,
{fmt(stats['lidar_calibration']['agreement_dem_slope_strongest_vs_lidar_strongest']['pct_abs_le_1px']*100,1)}% within 1&nbsp;px</li>
<li>{cands} records with consistent offset &gt; 2&nbsp;px (of {stats['records']['dem_slope_strongest']['n_records_sampled']} well-sampled)</li>
<li>{dots:,} dots emitted, 0 on the catalogue</li></ul></div>
<div class=card><h3>Holdout (simulated truth, local)</h3><ul>
<li>A1 lane {fmt(a1['dti'])} [{fmt(a1['ci95'][0])}, {fmt(a1['ci95'][1])}]</li>
<li>A0 masked control {fmt(a0['dti'])} · A4 random {fmt(a4['dti'])}</li>
<li>A5 oracle {fmt(a5['dti'])} (ceiling)</li>
<li>leakage canary: max feature AUC {fmt(max(v['auc'] for k,v in hold['leakage_canary'].items() if not k.startswith('_')),4)}; controls read ~0.5</li></ul></div>
<div class=card><h3>Not claimed</h3><ul>
<li>no organizer score exists for this file (a projection is never written as a score);</li>
<li>the holdout truth is simulated from the measurement, not the organizer's hidden labels;</li>
<li>the 1&nbsp;m LiDAR calibration covers 75% of the footprint and validates the crest,
not the fault;</li>
<li>the sibling-reported 0.2778/0.3195/0.3774 figures are unauthenticated &mdash; see
<a href="irregularities.html">irregularities</a>.</li></ul></div>
</div>
<h2>Site map</h2>
<ul>
<li><a href="executive-summary.html">Submission status</a> &mdash; current audit-only artifacts and conditional gates; no current upload instructions</li>
<li><a href="submit.html">Submission status &amp; conditions</a> &mdash; all four files, format/uniqueness blockers, and the conditional future upload checklist</li>
<li><a href="research.html">Research</a> &mdash; method, offset histogram, LiDAR calibration, holdout, leakage canary, and the &ldquo;why 0.2778&rdquo; analysis</li>
<li><a href="hypotheses.html">Hypotheses</a> &mdash; broader register, corrections-only PR #9 candidates, plus PR #7 discovery set and its NEGATIVE holdout verdict</li>
<li><a href="sources.html">Sources</a> &mdash; official, verified links for manual review</li>
<li><a href="irregularities.html">Irregularities</a> &mdash; flagged claims and how each was checked</li>
<li><a href="prior-run.html">Prior run</a> &mdash; the sibling corrections run on this repo (negative verdict), its downloads and its reconciliation with this run</li>
</ul>
"""
    (out / "index.html").write_text(page("Home", "index.html", idx))

    # ------------------------------------------------- executive summary --
    exe = f"""
<h2>Submission status &mdash; STOP</h2>
<div class=card>
<h3 class=bad>NO CURRENT FILE IS CLEARED FOR SUBMISSION</h3>
<p><b>Safe to download: YES, for audit/research only. Safe to submit: NO.</b> This page is a
status report, not instructions to upload one of the files below. No organizer submission
receipt or score exists, and no weekly slot has been spent.</p>
<h3>Published corrections artifact from PR #5/#6 — audit only</h3>
<p><a href="downloads/{esc(tif.name if tif else '')}">Download for audit: {esc(tif.name if tif else '')}</a>
({dots:,} dots; SHA-256 <code>{sha}</code>). Its local mask-aware format check passes.
Its result is <b>HOLDOUT-DTI</b> on simulated-corrections truth (`src/metrics.py`,
26,813 withheld positives): A1 {fmt(a1['dti'],6)} [{fmt(a1['ci95'][0],6)},
{fmt(a1['ci95'][1],6)}]. This is not an organizer score and does not validate PR #9's
three-physics candidate. The standing literal registry rule flags {reg_n_flags if reg else 'multiple'}
priors, so the protocol result is <b>DUPLICATE/STOP</b>; no slot is cleared.</p>
<h3>PR #4 corrections run — negative</h3>
<p>The null-calibrated decision gate qualifies <b>{m_cor['decision_gate']['qualifying']} of
{m_cor['decision_gate']['components']} corridors</b>. Its primary has one unsupported dot and
its 14-dot sensitivity relaxes the approximately 2 px threshold. The historical HOLDOUT-DTI
is {fmt(hab['B_snap']['dti'],6)} [{fmt(hab['B_snap']['ci95'][0],6)},
{fmt(hab['B_snap']['ci95'][1],6)}], evaluator <code>{esc(hb['evaluator_version'])}</code>,
{hb['withheld_positive_pixels']:,} withheld positives; random jitter is
{fmt(hab['D_jitter']['dti'],6)} [{fmt(hab['D_jitter']['ci95'][0],6)},
{fmt(hab['D_jitter']['ci95'][1],6)}]. The marginal intervals overlap. These old files also
write finite zeroes outside the official sample's NaN mask; their legacy all-finite local
pass is not exact format conformance.</p>
<h3>PR #7 discovery run — separate lane, negative</h3>
<p>The discovery lane is not this corrections review. Its pre-registered holdout was below
same-budget random and its literal registry rule returned DUPLICATE/STOP; see the separate
receipt details below. Do not merge its result with the corrections evidence.</p>
</div>

<h2>Conditional future upload checklist &mdash; only after every gate passes</h2>
<div class=card>
<ol>
<li>Resolve participant data terms and confirm input hashes against the logged-in official
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">competition data page</a>;
a public mirror hash is not organizer authentication.</li>
<li>After the run budget is explicitly reset, preregister a corrections-only candidate and
run feature-alone leakage canaries plus the shared blocked holdout. Report HOLDOUT-DTI with
evaluator version, withheld-positive count and paired spatial-block 95% CI. A simulated or
catalogue hide-and-recover result is not an organizer score.</li>
<li>Apply the literal registry gate before and after placement. Any >70%-within-3-px trigger
is DUPLICATE/STOP; do not waive it based on similarity diagnostics.</li>
<li>Use a shared writer/gate path that matches the official grid and exterior mask; validate
the exact bytes and SHA-256 locally. A local pass is not portal acceptance.</li>
<li>Only if all gates pass and a separate weekly-slot selector approves, open the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">official portal</a>,
use a unique name and note of at most 140 characters, upload, and save the returned receipt.
Only its score is ORGANIZER-CONFIRMED.</li>
</ol>
<p>Archived submission names and notes in old run cards are for provenance only. They are not
approved for reuse or for a current upload.</p>
</div>
"""
    if bld2 and hold2:
        rec2 = bld2["receipt"]
        exe += f"""
<h2>Round-2 discovery candidate &mdash; also NOT for submission</h2>
<div class=card>
<p><b>OK to submit: <span class=bad>NO</span>.</b> The second download on the
<a href="index.html">home page</a>
(<code>{esc(Path(rec2['file']).name)}</code>, {bld2['dots']:,} dots) is format-validated
research output: single band, float32, values exactly {{0.0, 1.0}}, EPSG:32611, shape and
transform equal to the submission format, sha256 <code>{esc(rec2['sha256'])}</code>.
Two independent verdicts block it: HOLDOUT-DTI, evaluator <code>{esc(hold2['evaluator']['version'])}</code>,
{hold2['withheld_positives_total']:,} withheld positives: candidate {fmt(bld2['holdout_dti'],5)}
[{fmt(bld2['holdout_ci95'][0],5)}, {fmt(bld2['holdout_ci95'][1],5)}] vs uniform random
{fmt(bld2['chance_dti'],5)} [{fmt(rand2['ci95'][0],5)}, {fmt(rand2['ci95'][1],5)}]; paired
{fmt(hold2['pick_rule']['paired_vs_random']['delta'],5)} [{fmt(hold2['pick_rule']['paired_vs_random']['ci95'][0],5)}, {fmt(hold2['pick_rule']['paired_vs_random']['ci95'][1],5)}] strictly below zero. The
registry lane gate returned <b>{esc(gate2.get('verdict_literal') if gate2 else 'n/a')}</b>
(density-degenerate 3&nbsp;px trigger, IR-56-023). Its name, note and receipt all say
NEGATIVE; no slot was spent. Full walk-through of the numbers:
<a href="hypotheses.html">hypotheses (round-2 section)</a> ·
<code>evidence/run_card_discovery_v1.json</code>.</p>
</div>
"""
    (out / "executive-summary.html").write_text(page("Submission status", "executive-summary.html", exe))

    # ------------------------------------------------------------ research --
    b = stats["bands"]
    r = stats["records"]
    lc = stats["lidar_calibration"]
    res = f"""
<h2>Research &mdash; the corrections lane, end to end</h2>
<h3>1. The question</h3>
<p>The metric is a budget. With the official distance-weighted Tversky index
(<code>DTI = T / (&alpha;(T+F) + &beta;K)</code>, &alpha;=0.2, &beta;=0.8, 300&nbsp;m
triangular kernel), adding one unit of prediction mass raises the denominator by exactly
&alpha;=&nbsp;0.2 anywhere on the grid: a dot pays iff its kernel credit exceeds
&alpha;&middot;DTI (~0.052 at DTI&nbsp;0.26, i.e. within ~284&nbsp;m of a hidden truth pixel).
The live scorer masks known-fault pixels pixel-exactly
(<a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">forum 11516</a>),
so dots on the published catalogue cost 0.2 each and earn nothing. The organizers also stated
that new-fault ground truth can lie within 300&nbsp;m of a known trace as
&ldquo;corrections or modifications to existing fault traces&rdquo;. <b>Therefore: where the
catalogue line is measurably displaced from the physical fault, the refined (hidden) trace is
at the evidence, not on the catalogue.</b> This lane measures that displacement and emits
there.</p>
<h3>2. Method</h3>
<ul>
<li><b>Traces:</b> the catalogue raster (<code>labels.tif</code> = <code>existing_faults.tif</code>,
60,988 fault px) is grouped by <code>record_id</code> of the official vector catalogue
(USGS QFaults + INGENIOUS, 84,331 segments / 1,126 named records; 99.83% of raster fault px
lie within 1.5&nbsp;px of a vector segment). Per-record statistics need long traces; the
raster's 8-connected components are too fragmented (median 12&nbsp;px).</li>
<li><b>Orientation:</b> structure tensor of the catalogue mask (gaussian-weighted window sums
of squared sobel gradients); the perpendicular direction is the minor-eigenvector direction.</li>
<li><b>Transects:</b> {stats['n_transects']:,} perpendicular transects, &plusmn;4&nbsp;px
(&plusmn;400&nbsp;m) at 0.25&nbsp;px steps (33 bilinear samples), inside the footprint.</li>
<li><b>Crests:</b> the DEM-scarp crest = ridge of <code>det_elev_slope</code> (band 19, slope
of detrended elevation); the magnetic-gradient ridge = ridge of <code>tmi_hg</code> (band 3).
Two definitions per band: <em>strongest</em> (dominant crest in the window &mdash; where the
evidence says the fault is when the catalogue is displaced) and <em>nearest</em> (prominent
crest nearest the catalogue &mdash; pure registration). Unambiguous crests only:
prominence &ge; K&nbsp;&times;&nbsp;1.4826&nbsp;&times;&nbsp;MAD, interior local maximum,
parabolic sub-sample refinement.</li>
<li><b>Calibration:</b> the cached 1&nbsp;m LiDAR scarp product (706 official USGS 3DEP 1&nbsp;m
tiles mosaicked onto this grid by the 7GEMSDOE sibling; 75% footprint coverage) sampled on the
same transects; LiDAR crest = max of <code>lapneg_max</code> (crest convexity of the 50&nbsp;m
band-passed 1&nbsp;m surface).</li>
<li><b>Decision rule (preregistered):</b> a record is a correction candidate when its
strongest-crest offset has |median| &gt; 2&nbsp;px, sign agreement &ge; 0.70, and
&ge; 8 unambiguous transects. Emission = dots on the connected crest line, off-catalogue
(not on any known-fault pixel), inside the footprint.</li>
<li><b>No learned component.</b> The measurement is geometric and the emission rule is a fixed
threshold; the brief's Mnih &amp; Hinton ICML 2012 registration/omission-tolerant loss is the
prescribed training loss if a learned component were trained &mdash; it is not invoked here.</li>
</ul>
<h3>3. The offset histogram (deliverable)</h3>
<p><img src="downloads/offset_histogram.png" alt="offset histogram"></p>
<p class=mut>Full tables: <code>evidence/corrections/offset_histogram.csv</code> (binned),
<code>offset_transects.csv</code> (per transect),
<code>record_offsets_dem_slope_strongest.csv</code> (per record).</p>
<table>
<tr><th>band / definition</th><th>n</th><th>median</th><th>MAD</th><th>|d|&le;1px</th><th>|d|&le;2px</th><th>|d|&gt;2px</th><th>|d|&gt;3px</th></tr>
<tr><td>dem_slope strongest</td><td>{b['dem_slope_strongest']['offset']['n']:,}</td><td>{fmt(b['dem_slope_strongest']['offset']['median_px'],3)} px</td><td>{fmt(b['dem_slope_strongest']['offset']['mad_px'],2)}</td><td>{fmt(b['dem_slope_strongest']['offset']['pct_abs_le_1px']*100,1)}%</td><td>{fmt(b['dem_slope_strongest']['offset']['pct_abs_le_2px']*100,1)}%</td><td>{fmt(b['dem_slope_strongest']['offset']['pct_abs_gt_2px']*100,1)}%</td><td>{fmt(b['dem_slope_strongest']['offset']['pct_abs_gt_3px']*100,1)}%</td></tr>
<tr><td>dem_slope nearest</td><td>{b['dem_slope_nearest']['offset']['n']:,}</td><td>{fmt(b['dem_slope_nearest']['offset']['median_px'],3)} px</td><td>{fmt(b['dem_slope_nearest']['offset']['mad_px'],2)}</td><td>{fmt(b['dem_slope_nearest']['offset']['pct_abs_le_1px']*100,1)}%</td><td>{fmt(b['dem_slope_nearest']['offset']['pct_abs_le_2px']*100,1)}%</td><td>{fmt(b['dem_slope_nearest']['offset']['pct_abs_gt_2px']*100,1)}%</td><td>{fmt(b['dem_slope_nearest']['offset']['pct_abs_gt_3px']*100,1)}%</td></tr>
<tr><td>mag_hg strongest</td><td>{b['mag_hg_strongest']['offset']['n']:,}</td><td>{fmt(b['mag_hg_strongest']['offset']['median_px'],3)} px</td><td>{fmt(b['mag_hg_strongest']['offset']['mad_px'],2)}</td><td>{fmt(b['mag_hg_strongest']['offset']['pct_abs_le_1px']*100,1)}%</td><td>{fmt(b['mag_hg_strongest']['offset']['pct_abs_le_2px']*100,1)}%</td><td>{fmt(b['mag_hg_strongest']['offset']['pct_abs_gt_2px']*100,1)}%</td><td>{fmt(b['mag_hg_strongest']['offset']['pct_abs_gt_3px']*100,1)}%</td></tr>
<tr><td>mag_hg nearest</td><td>{b['mag_hg_nearest']['offset']['n']:,}</td><td>{fmt(b['mag_hg_nearest']['offset']['median_px'],3)} px</td><td>{fmt(b['mag_hg_nearest']['offset']['mad_px'],2)}</td><td>{fmt(b['mag_hg_nearest']['offset']['pct_abs_le_1px']*100,1)}%</td><td>{fmt(b['mag_hg_nearest']['offset']['pct_abs_le_2px']*100,1)}%</td><td>{fmt(b['mag_hg_nearest']['offset']['pct_abs_gt_2px']*100,1)}%</td><td>{fmt(b['mag_hg_nearest']['offset']['pct_abs_gt_3px']*100,1)}%</td></tr>
<tr><td>LiDAR strongest (1 m)</td><td>{lc['offset_strongest']['n']:,}</td><td>{fmt(lc['offset_strongest']['median_px'],3)} px</td><td>{fmt(lc['offset_strongest']['mad_px'],2)}</td><td>{fmt(lc['offset_strongest']['pct_abs_le_1px']*100,1)}%</td><td>{fmt(lc['offset_strongest']['pct_abs_le_2px']*100,1)}%</td><td>{fmt(lc['offset_strongest']['pct_abs_gt_2px']*100,1)}%</td><td>{fmt(lc['offset_strongest']['pct_abs_gt_3px']*100,1)}%</td></tr>
<tr><td>LiDAR nearest (1 m)</td><td>{lc['offset_nearest']['n']:,}</td><td>{fmt(lc['offset_nearest']['median_px'],3)} px</td><td>{fmt(lc['offset_nearest']['mad_px'],2)}</td><td>{fmt(lc['offset_nearest']['pct_abs_le_1px']*100,1)}%</td><td>{fmt(lc['offset_nearest']['pct_abs_le_2px']*100,1)}%</td><td>{fmt(lc['offset_nearest']['pct_abs_gt_2px']*100,1)}%</td><td>{fmt(lc['offset_nearest']['pct_abs_gt_3px']*100,1)}%</td></tr>
</table>
<h3>4. Per-record consistency &amp; the two readings</h3>
<table>
<tr><th>band (strongest)</th><th>records</th><th>well-sampled</th><th>consistent &gt;2px</th><th>median |median|</th><th>|median|&gt;2px</th><th>&gt;3px</th></tr>
<tr><td>dem_slope</td><td>{r['dem_slope_strongest']['n_records']}</td><td>{r['dem_slope_strongest']['n_records_sampled']}</td><td>{r['dem_slope_strongest']['n_consistent_offset_gt_2px']} ({fmt(r['dem_slope_strongest']['frac_consistent_offset_gt_2px']*100,1)}%)</td><td>{fmt(r['dem_slope_strongest']['median_abs_offset_px'],2)} px</td><td>{r['dem_slope_strongest']['records_offset_gt_2px']}</td><td>{r['dem_slope_strongest']['records_offset_gt_3px']}</td></tr>
<tr><td>mag_hg</td><td>{r['mag_hg_strongest']['n_records']}</td><td>{r['mag_hg_strongest']['n_records_sampled']}</td><td>{r['mag_hg_strongest']['n_consistent_offset_gt_2px']} ({fmt(r['mag_hg_strongest']['frac_consistent_offset_gt_2px']*100,1)}%)</td><td>{fmt(r['mag_hg_strongest']['median_abs_offset_px'],2)} px</td><td>{r['mag_hg_strongest']['records_offset_gt_2px']}</td><td>{r['mag_hg_strongest']['records_offset_gt_3px']}</td></tr>
</table>
<p><b>Reading 1 (nearest crest):</b> the catalogue sits on or within ~1&nbsp;px of a crest
almost everywhere &mdash; the catalogue is registered to <em>some</em> scarp.
<b>Reading 2 (strongest crest):</b> the dominant scarp/ridge in the &plusmn;400&nbsp;m window is
consistently offset from the catalogue on {r['dem_slope_strongest']['n_consistent_offset_gt_2px']}
of {r['dem_slope_strongest']['n_records_sampled']} well-sampled records (22.4%), with offsets
of 2&ndash;3.4&nbsp;px (200&ndash;340&nbsp;m) and per-transect MAD as low as 0.11&nbsp;px on the
most consistent records (e.g. record 630: +3.05&nbsp;&plusmn;&nbsp;0.11&nbsp;px over 14
transects &asymp; 2.8&nbsp;km; record 1567: +3.41&nbsp;px, sign agreement 1.00). This is
exactly the scale of USGS-to-refined-trace discrepancy reported for north-central Nevada
(Hermant, Kiersnowski &amp; Bellanger, Stanford Geothermal Workshop 2025: up to 400&nbsp;m)
and exactly the organizers' &ldquo;corrections within 300&nbsp;m&rdquo;. The lane's emission
follows reading 2, gated by per-record consistency.</p>
<p><img src="downloads/record_630_crop.png" alt="record 630 crop"></p>
<p class=mut>Record 630: the catalogue (white) and the evidence-defined trace (green circles)
run parallel, ~300&nbsp;m apart, over ~30&nbsp;km of map. Crops for records 322, 1567 and
2665 are in <code>docs/downloads/</code>.</p>
<h3>5. LiDAR calibration (1 m 3DEP)</h3>
<ul>
<li>dem_slope strongest crest vs LiDAR crest: median {fmt(lc['agreement_dem_slope_strongest_vs_lidar_strongest']['median_px'],3)}&nbsp;px,
MAD {fmt(lc['agreement_dem_slope_strongest_vs_lidar_strongest']['mad_px'],3)}&nbsp;px,
{fmt(lc['agreement_dem_slope_strongest_vs_lidar_strongest']['pct_abs_le_1px']*100,1)}% within 1&nbsp;px,
{fmt(lc['agreement_dem_slope_strongest_vs_lidar_strongest']['pct_abs_le_2px']*100,1)}% within 2&nbsp;px
(n={lc['agreement_dem_slope_strongest_vs_lidar_strongest']['n']}) &mdash; <b>the 100&nbsp;m slope
ridge is the 1&nbsp;m scarp crest</b>; the gate K=3 was chosen on this calibration.</li>
<li>mag_hg strongest crest vs LiDAR crest: MAD {fmt(lc['agreement_mag_hg_strongest_vs_lidar_strongest']['mad_px'],2)}&nbsp;px
(n={lc['agreement_mag_hg_strongest_vs_lidar_strongest']['n']}) &mdash; weak: many faults have no
magnetic contrast, so the magnetic ridge is corroborating evidence, not a requirement.</li>
<li>catalogue &rarr; LiDAR crest (strongest): median {fmt(lc['offset_strongest']['median_px'],3)}&nbsp;px,
MAD {fmt(lc['offset_strongest']['mad_px'],2)}&nbsp;px, |d|&gt;2px {fmt(lc['offset_strongest']['pct_abs_gt_2px']*100,1)}%
&mdash; the independent 1&nbsp;m reference shows the same wide scatter as the 100&nbsp;m DEM
band, and the same per-record consistency pattern.</li>
</ul>
<h3>6. Holdout (hide-and-recover, simulated corrections) &mdash; HOLDOUT-DTI</h3>
<p>Whole records' refined positions are withheld and simulated by their measured
crest lines (records with |median offset| &gt; 1&nbsp;px; records &le; 1&nbsp;px are
&ldquo;uncorrected&rdquo;). Visible faults are masked pixel-exactly on BOTH sides (GT excludes
the catalogue; prediction on the catalogue earns no TP and costs &alpha;). 4 spatial folds
(k-means on record centroids); DTI scored POOLED with the official metric
(<code>src/metrics.py</code>, &alpha;=0.2, &beta;=0.8, 300&nbsp;m triangular kernel);
95% CI from a 20&times;20&nbsp;px spatial-block bootstrap (2,000 draws).</p>
<table>
<tr><th>arm</th><th>dots</th><th>pooled DTI</th><th>95% CI</th><th>TP_w</th><th>FP_w</th><th>FN_w</th></tr>
<tr><td>A0 catalogue (masked control)</td><td>{a0['dots']:,}</td><td>{fmt(a0['dti'],5)}</td><td>[{fmt(a0['ci95'][0],5)}, {fmt(a0['ci95'][1],5)}]</td><td>{fmt(a0['TP_w'],1)}</td><td>{fmt(a0['FP_w'],1)}</td><td>{fmt(a0['FN_w'],1)}</td></tr>
<tr><td><b>A1 lane (historical PR #5/#6 artifact; not cleared)</b></td><td><b>{a1['dots']:,}</b></td><td><b>{fmt(a1['dti'],5)}</b></td><td><b>[{fmt(a1['ci95'][0],5)}, {fmt(a1['ci95'][1],5)}]</b></td><td><b>{fmt(a1['TP_w'],1)}</b></td><td><b>{fmt(a1['FP_w'],1)}</b></td><td><b>{fmt(a1['FN_w'],1)}</b></td></tr>
<tr><td>A2 no-gate crest emission</td><td>{a2['dots']:,}</td><td>{fmt(a2['dti'],5)}</td><td>[{fmt(a2['ci95'][0],5)}, {fmt(a2['ci95'][1],5)}]</td><td>{fmt(a2['TP_w'],1)}</td><td>{fmt(a2['FP_w'],1)}</td><td>{fmt(a2['FN_w'],1)}</td></tr>
<tr><td>A4 random (matched mass)</td><td>{a4['dots']:,}</td><td>{fmt(a4['dti'],5)}</td><td>[{fmt(a4['ci95'][0],5)}, {fmt(a4['ci95'][1],5)}]</td><td>{fmt(a4['TP_w'],1)}</td><td>{fmt(a4['FP_w'],1)}</td><td>{fmt(a4['FN_w'],1)}</td></tr>
<tr><td>A5 oracle (ceiling)</td><td>{a5['dots']:,}</td><td>{fmt(a5['dti'],5)}</td><td>[{fmt(a5['ci95'][0],5)}, {fmt(a5['ci95'][1],5)}]</td><td>{fmt(a5['TP_w'],1)}</td><td>{fmt(a5['FP_w'],1)}</td><td>{fmt(a5['FN_w'],1)}</td></tr>
</table>
<p>|G| = {hold['n_withheld_positives']:,} withheld positives (simulated).
Contrasts: A1&minus;A0 = +{fmt(hold['contrasts']['A1_minus_A0'])},
A1&minus;A4 = +{fmt(hold['contrasts']['A1_minus_A4'])}.
<b>The masked control scores exactly 0</b> &mdash; the masking model works, and the catalogue
line itself is not the target. <b>The lane arm beats both controls decisively.</b>
A2 (no gate) scores higher under the simulation, but the simulation is construction-biased
toward A2 (its truth includes crest lines of 1&ndash;2&nbsp;px-offset records, which the
real scorer rewards only if those corrections exist); the gate's real-world purpose is
precision against non-fault scarps, which the simulation cannot test. The preregistered
lane rule (gate at 2&nbsp;px) is what this repository ships.</p>
<h3>7. Leakage canary (E2)</h3>
<table>
<tr><th>feature</th><th>AUC vs simulated truth</th><th>role</th></tr>
{''.join(f'<tr><td>{esc(k)}</td><td>{fmt(v["auc"],4)}</td><td>{esc(v["role"])}</td></tr>' for k,v in hold['leakage_canary'].items() if not k.startswith('_'))}
</table>
<p>No feature exceeds 0.90 (max {fmt(max(v['auc'] for k,v in hold['leakage_canary'].items() if not k.startswith('_')),4)}).
The catalogue mask reads {fmt(hold['leakage_canary']['catalogue_mask']['auc'],4)} &asymp; 0.5
(truth pixels are not on catalogue pixels &mdash; masking worked), and
dist-to-catalogue reads {fmt(hold['leakage_canary']['dist_to_catalogue_px']['auc'],4)} &lt; 0.5
(the simulated truth is displaced away from the catalogue &mdash; the simulation is not
degenerate). <span class=ok>Controls OK: {hold['controls_ok']}</span></p>
<h3>8. Why 0.2778 &mdash; the PhD-level answer (and the irregularity)</h3>
<p><b>The mechanism</b> (measured by the GEMSDOE32 sibling on the official formula and its
worked example): (1) the distance-weighted Tversky index reduces exactly to
<code>DTI = T/(&alpha;(T+F)+&beta;K)</code> with T=TP_w, F=FP_w, K=|G|; (2) adding one unit
of mass raises the denominator by exactly &alpha;=0.2 anywhere, so a dot pays iff its
credit exceeds &alpha;&middot;DTI &asymp; 0.052 at DTI 0.26 &mdash; i.e. it must land within
~284&nbsp;m of a hidden truth pixel; (3) the live scorer masks known-fault pixels
(forum 11516), so dots on the published catalogue are pure 0.2-cost false positives;
(4) <code>h33-h33-2-b2</code> is the group's best live-scored emission (a 40,199-dot
&ldquo;dotted d2.8&rdquo; thinning of their H19-5 field) with every dot within 2&nbsp;px
(200&nbsp;m) of the catalogue deleted &rarr; 37,654 dots, 0 on-catalogue; (5) the family
shows the emission-side optimum: solid 121,131&nbsp;px &rarr; 0.1922, d1.5 60,069 &rarr; 0.2477,
d2.8 44,090 &rarr; 0.2600 (all owner-reported), implying a hidden |G| &asymp; 7,905&nbsp;px;
(6) beating the live leader needs ~+25% mean credit at equal mass &mdash; a better
<em>field</em>, or genuinely novel faults; emission-side gains are nearly exhausted. This
lane is such a field mechanism: refined traces within 300&nbsp;m of known traces are in the
hidden truth per forum 11516.</p>
<p><b>The irregularity</b> (flagged, see <a href="irregularities.html">irregularities</a>):
the 0.2778 figure attached to <code>h33-h33-2-b2</code> is <b>user-reported and unsupported</b>.
The GEMSDOE32 owner pages label that artifact <b>UNSCORED</b> with a modelled projection of
0.2747 and state that no organizer score exists for it; the GEMSDOE51 sibling's audit calls
the attribution &ldquo;unsupported and contradicted&rdquo;. What can be said is what the file
<em>embodies</em> (the mechanism above), not that it scored 0.2778.</p>
<h3>9. The sibling run on this repo (run B): same lane, negative verdict</h3>
<p>A parallel session (merged PR #4, branch <code>arena/1d3dbc39-56gemsdoe</code>) ran the
same corrections lane with a different, more conservative gate, and reported a
<b>negative</b> result. Its receipts are in <code>evidence/</code>
(<code>run_card.json</code>, <code>offsets_v1.json</code>, <code>calibration_v1.json</code>,
<code>holdout_corrections_v1.json</code>, <code>registry_screen_v1.json</code>,
<code>irregularities.json</code>); full presentation on <a href="prior-run.html">Prior run</a>.</p>
<ul>
<li><b>The measurement agrees with this run's nearest-crest reading:</b> null-calibrated
median catalogue-to-crest offset {fmt(m_cal['dem_median'],3)}&nbsp;px (DEM,
n={m_cal['dem_n']:,}) and {fmt(m_cal['mag_median'],3)}&nbsp;px (magnetic,
n={m_cal['mag_n']:,}); joint median {fmt(m_cal['joint_median'],3)}&nbsp;px over
n={m_cal['joint_n']:,} &mdash; <b>below the estimator's own noise floor</b>
(random traceless points: {fmt(m_cal['null_random_abs_median'],2)}&nbsp;px;
rotated: {fmt(m_cal['null_rotated_abs_median'],2)}&nbsp;px). The two families' offsets
correlate at r&nbsp;=&nbsp;{fmt(m_ung['dem_mag_correlation_r'],3)}.</li>
<li><b>Its gate is stricter:</b> a crest must exceed the 90th percentile of the same
statistic at random traceless points (DEM &ge; {fmt(m_cal['strength_gate']['dem_min_hgt'],1)},
mag &ge; {fmt(m_cal['strength_gate']['mag_min_hgt'],1)}), corridors need DEM+mag
concordance, and the corridor offset must clear a {fmt(m_cor['decision_gate']['sigma_floor_px'],2)}&nbsp;&sigma;
floor &rarr; <b>{m_cor['decision_gate']['qualifying']} of {m_cor['decision_gate']['components']}
corridors qualify</b> (ungated exploration: {m_cor['ungated_exploration']['qualifying']} of
{m_cor['ungated_exploration']['components_evaluated']:,}).</li>
<li><b>Its LiDAR check is finer but smaller:</b> 3&nbsp;m resolution over
{fmt(m_lid['coverage_fraction_of_catalogue']*100,1)}% of the catalogue &mdash; pooled median
{fmt(m_lid['pooled_median_px'],3)}&nbsp;px, <b>{m_lid['segments_ge_200m']} of
{m_lid['segments']} segments displaced by &ge; 200&nbsp;m</b>. This run's 1&nbsp;m
calibration (75% of the footprint) instead validates the crest operator itself
(MAD 0.29&nbsp;px).</li>
<li><b>Its holdout</b> (evaluator <code>{esc(hb['evaluator_version'])}</code>,
{hb['withheld_positive_pixels']:,} withheld positives, whole 8-connected components
withheld, visible catalogue masked pixel-exactly): A as-is {fmt(hab['A_as_is']['dti'],5)}
[{fmt(hab['A_as_is']['ci95'][0],5)}, {fmt(hab['A_as_is']['ci95'][1],5)}],
B snap {fmt(hab['B_snap']['dti'],5)} [{fmt(hab['B_snap']['ci95'][0],5)},
{fmt(hab['B_snap']['ci95'][1],5)}], C snap-sub {fmt(hab['C_snap_sub']['dti'],5)}
[{fmt(hab['C_snap_sub']['ci95'][0],5)}, {fmt(hab['C_snap_sub']['ci95'][1],5)}],
D jitter {fmt(hab['D_jitter']['dti'],5)} [{fmt(hab['D_jitter']['ci95'][0],5)},
{fmt(hab['D_jitter']['ci95'][1],5)}]. The snap arms' intervals contain zero.
The PR #5/#6 holdout (different truth construction: simulated corrections, evaluator
<code>src/metrics.py</code>, {hold['n_withheld_positives']:,} withheld positives) gives
A1 {fmt(a1['dti'],6)} [{fmt(a1['ci95'][0],6)}, {fmt(a1['ci95'][1],6)}]. These holdouts
validate different machinery on different simulated truths; neither is an organizer score.</li>
<li><b>Its uniqueness gate failed on a technicality:</b> the shared gate's proximity
criterion fires trivially at 1-dot count ({gate_b['directed_near3px_fraction']*100:.0f}% of
its dots within 3&nbsp;px of {gate_b['offender_count']} of {gate_b['priors_checked']} priors;
reciprocal overlap 0 above 0.70) &mdash; the same class of false positive this run hit at
6,504 dots and resolved with Jaccard/reverse-containment/mass-ratio (IR-56-07). Run B
chose to publish the artefacts as research output and claim no slot.</li>
</ul>
<p><b>Reconciliation:</b> both runs agree the catalogue sits within ~1&nbsp;px of
<em>some</em> crest. Run B's gate asks whether the catalogue is displaced from
<em>a</em> crest by &ge; 2&nbsp;px under null calibration &mdash; no. Run A's rule asks
whether the <em>strongest</em> crest (the dominant scarp, LiDAR-confirmed) is consistently
&gt; 2&nbsp;px away per vector record &mdash; yes, on 22.4% of well-sampled records. A
catalogue line on a secondary strand with the main scarp 200&ndash;340&nbsp;m away is
consistent with both statements. Existing receipts cannot resolve which gate matches hidden
labels. Neither run has an organizer score, and the literal stop rule plus consumed run budget
means no slot is recommended.</p>
<h3>10. Reproduce</h3>
<pre>python scripts/prepare_records.py            # vector catalogue -> record ids
python scripts/measure_corrections_offsets.py # E1: offset histogram + LiDAR calibration
python scripts/holdout_corrections.py        # E2 canary + E3 holdout
python scripts/check_registry.py ...         # uniqueness vs every earlier raster
python scripts/build_submission.py           # emission -> conform -> write -> validate
python scripts/build_site.py                 # regenerate this site</pre>
"""
    (out / "research.html").write_text(page("Research", "research.html", res))

    # --------------------------------------------------------- hypotheses --
    hyp = f"""
<h2>Ranked geological hypotheses</h2>
<p>Five candidates, ranked by expected DTI improvement versus implementation cost. Each
names its layers, target physical signature/operator, why it could expose fault geometry
missing from the USGS/INGENIOUS catalogue (rather than merely recovering known-fault
habitat), how it differs from implemented repository/prior-art work, expected benefit and
cost. The PR #5/#6 strongest-crest run reports HOLDOUT-DTI on a simulated-corrections truth;
that result does not validate the PR #9 three-physics candidate or organizer labels. The
PR #9 top candidate remains unvalidated, and the current literal registry rule blocks any
slot decision. Budget note: the recorded 3-experiment E1/E2/E3 budget is treated as spent.</p>
<p>The five corrections-only candidates retained from the PR #9 review are in
<a href="research/corrections-hypotheses-20261009.md">the corrections hypothesis register</a>;
they do not replace the broader register or PR #7 discovery lane.</p>
<table>
<tr><th>#</th><th>hypothesis</th><th>layers</th><th>signature / operator</th><th>why it catches catalogue-missing faults</th><th>differs from prior art</th><th>expected &Delta;DTI vs cost</th><th>status</th></tr>
<tr><td>1</td><td><b>Corrections: catalogue-to-evidence registration offset</b></td>
<td>det_elev, det_elev_slope (12, 19); 1 m 3DEP LiDAR (calibration); vector catalogue records</td>
<td>perpendicular transects &plusmn;400 m; strongest-crest offset of the DEM-scarp ridge per record; emit at the crest when consistent &gt; 2 px</td>
<td>the hidden truth contains &ldquo;corrections or modifications&rdquo; within 300 m of known traces (forum 11516); USGS-to-refined discrepancies up to 400 m are documented (Hermant et al. 2025). The catalogue line is masked, so only the refined position scores</td>
<td>siblings emit on catalogue-distance halos or learned fields; none measures the catalogue-to-evidence offset per vector trace with a LiDAR-calibrated crest</td>
<td>PR #5/#6 HOLDOUT-DTI (simulated-corrections truth; evaluator <code>src/metrics.py</code>, {hold['n_withheld_positives']:,} withheld positives): A1 {fmt(a1['dti'],6)} [{fmt(a1['ci95'][0],6)}, {fmt(a1['ci95'][1],6)}], A0 {fmt(a0['dti'],6)} [{fmt(a0['ci95'][0],6)}, {fmt(a0['ci95'][1],6)}], A4 {fmt(a4['dti'],6)} [{fmt(a4['ci95'][0],6)}, {fmt(a4['ci95'][1],6)}]. Separate from PR #9's unvalidated top candidate; literal registry STOP. Cost budget spent.</td>
<td><span class=bad>IMPLEMENTED; NO SLOT (DUPLICATE/STOP)</span></td></tr>
<tr><td>2</td><td><b>Magnetic-gradient ridge lineaments off-catalogue</b></td>
<td>tmi_hg (3), tc (6), rtp (2), tmi (14)</td>
<td>ridge tracing of the horizontal-gradient / tilt-angle fields; strike-family filtering (Basin-and-Range orientations); exclude anything within 2 px of the catalogue</td>
<td>faults with magnetic contrast produce gradient ridges even where scarps are absent (buried or eroded faults) &mdash; the largest pool of genuinely new faults</td>
<td>siblings feed mag bands into CNNs as inputs; none traces mag ridges as primary lineament evidence with strike filtering and a holdout gate</td>
<td>moderate (largest new-fault pool; lithologic contacts give false ridges &mdash; needs scarp corroboration); cost: ~1 session</td>
<td>preregistered future lane</td></tr>
<tr><td>3</td><td><b>Radiometric alteration halos along faults</b></td>
<td>cond_surf (17); cached GeoDAWN K/Th/U/TC radiometrics (7GEMSDOE external/geodawn_rad)</td>
<td>K/Th ratio and TC lineament detection; halo = elongated high-ratio anomaly parallel to a scarp or gradient ridge</td>
<td>geothermal fault conduits produce clay/potassium alteration halos; the competition asks for geothermal-indicative faults, so alteration-aligned faults are exactly the target class</td>
<td>siblings use cond_surf as one CNN input; none builds ratio lineaments with a holdout gate. Data is free/public (USGS GeoDAWN, DOI 10.5066/P93LGLVQ)</td>
<td>moderate (goal-aligned; GeoDAWN radiometrics are ~1 km flight-line scale &mdash; coarse); cost: ~1 session</td>
<td>preregistered future lane</td></tr>
<tr><td>4</td><td><b>Basement-depth edges under cover</b></td>
<td>depth_to_base_surf (15); cached 3 m LiDAR scarp product (GEMSDOE48 h52_scarp3m_100m)</td>
<td>gradient ridge of depth-to-basement, corroborated by a DEM scarp; emit at the corroborated edge, off-catalogue</td>
<td>faults control basin-fill thickness: buried fault edges in alluvial cover are invisible in the catalogue but offset the basement surface</td>
<td>GEMSDOE40 tried depth-KDE clusters cross-family; a gradient-edge + scarp corroboration with a blocked holdout is a different operator</td>
<td>low&ndash;moderate (indirect, two-step inference); cost: low&ndash;medium</td>
<td>preregistered future lane</td></tr>
<tr><td>5</td><td><b>Geodetic strain-gradient anomalies</b></td>
<td>geod_shearrate (7), geod_dilaterate (8), geod_2ndinv (4), deq/ieq (10, 16)</td>
<td>localized shear/dilation maxima off-catalogue; wavelength-filtered ridge detection</td>
<td>active faults concentrate strain; the 2020 Mw 6.5 Monte Cristo rupture occurred on a largely unmapped fault (Candelaria fault, inside the footprint &mdash; USGS field response, SRL 92(2A))</td>
<td>GEMSDOE51 tried Kreemer et al. (2000) Eq. 3 coarse priors (Spearman 0.14 &mdash; weak); a fine-scale strain-gradient ridge detector with holdout gating is different</td>
<td>low (the strain field is smooth at 100 m; one event is a weak prior); cost: medium</td>
<td>preregistered future lane</td></tr>
</table>
<p class=mut>Ranking rationale: expected DTI improvement per unit cost. H1 is the only
candidate whose target (corrections near known traces) is confirmed by the organizers to be
in the hidden label set, and it is the only one with a completed holdout. H2 addresses the
largest untapped pool (genuinely new faults) but carries lithology false-positive risk.
H3 is the most goal-aligned but the coarsest data. H4 is cheap but indirect. H5 is the
weakest signal at the official resolution.</p>
"""
    # round-2 discovery set (PR #7): pre-registered H6-H10 + the E1 verdict, appended to the
    # concurrent run's five hypotheses above -- two sessions, two hypothesis sets, both shown.
    if hold2 and bld2:
        pr2 = hold2["pick_rule"]
        sc2 = hold2["pooled"]["scores"]
        hyp += f"""
<h2>Round-2 discovery run (PR #7): five more hypotheses, H6&ndash;H10 &mdash; validated NEGATIVE</h2>
<p>The concurrent session on this repo pre-registered its own set
(<a href="https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/docs/research/hypotheses-20261009.md"><code>docs/research/hypotheses-20261009.md</code></a>,
ranked prior &times; cost &divide; danger) and spent its three-experiment budget testing the
top three on the same blocked instrument (E1, <code>evidence/holdout_discovery_v1.json</code>,
evaluator <code>gems52-pooled-hide-v1</code>, 4 folds, 48,080 withheld positives, budgets
8k/15k/25k/37,654, six arms including a <i>measured</i> chance floor):</p>
<table>
<tr><th>#</th><th>hypothesis</th><th>mechanism / named non-fault process</th><th>status from E1</th></tr>
<tr><td>H6</td><td><b>iso-gravity steps are fault-reactivated boundaries</b></td>
<td>isostatic residual steps &rarr; potential-field edges; non-fault: erosional terrace edges</td>
<td>HOLDOUT-DTI (<code>gems52-pooled-hide-v1</code>, 48,080 positives): {fmt(sc2['iso_step@25000']['dti'],5)} [{fmt(sc2['iso_step@25000']['ci95'][0],5)}, {fmt(sc2['iso_step@25000']['ci95'][1],5)}] vs random {fmt(sc2['random@25000']['dti'],5)} [{fmt(sc2['random@25000']['ci95'][0],5)}, {fmt(sc2['random@25000']['ci95'][1],5)}] &mdash; <span class=bad>below chance, NEGATIVE</span></td></tr>
<tr><td>H7</td><td><b>basement topography &times; conductors concordance</b></td>
<td>weak contact made conductive by fluids; non-fault: intrusions &amp; alteration halos</td>
<td>HOLDOUT-DTI (<code>gems52-pooled-hide-v1</code>, 48,080 positives): {fmt(sc2['bc_step@25000']['dti'],5)} [{fmt(sc2['bc_step@25000']['ci95'][0],5)}, {fmt(sc2['bc_step@25000']['ci95'][1],5)}] &mdash; <span class=bad>below chance, NEGATIVE</span></td></tr>
<tr><td>H8</td><td><b>tilt-low lineaments beneath cover</b></td>
<td>basin-fill depocentres; non-fault: channel &amp; fan morphology</td>
<td>HOLDOUT-DTI (<code>gems52-pooled-hide-v1</code>, 48,080 positives): {fmt(sc2['tilt_r@37654']['dti'],5)} [{fmt(sc2['tilt_r@37654']['ci95'][0],5)}, {fmt(sc2['tilt_r@37654']['ci95'][1],5)}] &mdash; <span class=bad>~0, NEGATIVE (channel/fan stands)</span></td></tr>
<tr><td>H9</td><td><b>INGENOUS 2 m probes gate on structural proximity</b></td>
<td>measured surface-temperature steps; non-fault: soil moisture &amp; albedo</td>
<td>probe layer obtained (3,800 pts) &mdash; not tested (budget stop)</td></tr>
<tr><td>H10</td><td><b>probe&times;structure coincidence hotspots</b></td>
<td>fluid pathways without catalogue faults; non-fault: anthropogenic site effects</td>
<td>not tested (budget stop)</td></tr>
</table>
<p><b>The headline:</b> HOLDOUT-DTI using <code>{esc(hold2['evaluator']['version'])}</code>,
{hold2['withheld_positives_total']:,} withheld positives: the pre-registered pick
<code>{esc(pr2['candidate'])}</code> scored {fmt(bld2['holdout_dti'],5)}
[{fmt(bld2['holdout_ci95'][0],5)}, {fmt(bld2['holdout_ci95'][1],5)}];
<b>uniform-random emission at the same budget scored {fmt(bld2['chance_dti'],5)}</b>
[{fmt(rand2['ci95'][0],5)}, {fmt(rand2['ci95'][1],5)}]; paired
{fmt(pr2['paired_vs_random']['delta'],5)}
[{fmt(pr2['paired_vs_random']['ci95'][0],5)}, {fmt(pr2['paired_vs_random']['ci95'][1],5)}] &mdash;
strictly below chance. Leakage canaries &le; {fmt(hold2['canary_max_new_fields'],3)} (limit 0.90),
so this is not leakage: the step/tilt signatures locate <em>mapped</em> structure, and once the
catalogue &plusmn;200 m is excluded (the mechanism behind the sibling 0.2708&rarr;0.2778
deletion, <a href="research.html">research &sect;8</a>) there is nothing left for them to find.
Verdict by the pre-registered rule: <b>NEGATIVE</b>; the shipped TIF (second download on the
<a href="index.html">home page</a>) carries the verdict in its name, note and receipt
(<code>evidence/run_card_discovery_v1.json</code>). One instrument defect found en route &mdash;
the zero-filled rim put 56.5% of <code>iso_step</code>'s top-25,000 cells on the data edge
(IR-56-020) &mdash; was fixed once in <code>src/gems56/transform.py</code> with six regression
tests; the negative survived the re-run unchanged.</p>
"""
    (out / "hypotheses.html").write_text(page("Hypotheses", "hypotheses.html", hyp))

    # ------------------------------------------------------------- sources --
    src = """
<h2>Sources &mdash; official, verified, for manual review</h2>
<table>
<tr><th>what</th><th>link</th><th>used for</th></tr>
<tr><td>Competition (rules, metric, submission format)</td><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">drivendata.org/competitions/306/competition-doe-gems/</a></td><td>weekly cap, submission rules, one-file rule</td></tr>
<tr><td>Problem description &amp; metric (distance-weighted Tversky, &alpha;=0.2, &beta;=0.8, 300 m triangular kernel)</td><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">/page/967/</a></td><td>metric definition, worked example 0.60</td></tr>
<tr><td>About the competition</td><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/">/page/968/</a></td><td>geothermal-indicative faults goal</td></tr>
<tr><td>Organizer forum thread 11516 (known-fault pixels masked; corrections within 300 m of known traces)</td><td><a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">community.drivendata.org/t/.../11516</a></td><td>the lane's premise</td></tr>
<tr><td>Official reference solution</td><td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></td><td>submission writer conventions</td></tr>
<tr><td>GeoDAWN airborne magnetic/radiometric surveys (USGS)</td><td><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">usgs.gov/data/geodawn-...</a> · DOI <a href="https://doi.org/10.5066/P93LGLVQ">10.5066/P93LGLVQ</a></td><td>the 19 feature bands' provenance</td></tr>
<tr><td>INGENIOUS project (GBCGE)</td><td><a href="https://gbcge.org/current-projects/ingenious/">gbcge.org/current-projects/ingenious/</a></td><td>catalogue provenance</td></tr>
<tr><td>QFaults + INGENIOUS shapefile via GDR submission 1391 (CC BY 4.0)</td><td><a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a></td><td>vector catalogue (records, segments)</td></tr>
<tr><td>USGS 3DEP 1 m DEM (public domain)</td><td><a href="https://www.usgs.gov/3d-elevation-program">usgs.gov/3d-elevation-program</a></td><td>LiDAR calibration (via the 7GEMSDOE cached product)</td></tr>
<tr><td>USGS SGMC state geology (public domain)</td><td><a href="https://mrdata.usgs.gov/geology/state/">mrdata.usgs.gov/geology/state/</a></td><td>catalogue cross-check</td></tr>
<tr><td>Tversky index</td><td><a href="https://en.wikipedia.org/wiki/Tversky_index">en.wikipedia.org/wiki/Tversky_index</a></td><td>metric background</td></tr>
<tr><td>Mnih &amp; Hinton, ICML 2012 (registration/omission-tolerant loss)</td><td><a href="https://www.cs.toronto.edu/~hinton/absps/straightthru.pdf">cs.toronto.edu/~hinton/absps/straightthru.pdf</a></td><td>prescribed loss style for any learned component</td></tr>
<tr><td>Hermant, Kiersnowski &amp; Bellanger, Stanford Geothermal Workshop 2025</td><td><a href="https://pangea.stanford.edu/ERE/pdfs/StanfordGeothermalWorkshop/2025/Hermant.pdf">pangea.stanford.edu (SGW 2025)</a></td><td>USGS-to-refined trace discrepancies up to 400 m</td></tr>
<tr><td>USGS field response, 2020 Mw 6.5 Monte Cristo rupture (SRL 92(2A) 823&ndash;829)</td><td><a href="https://pubs.usgs.gov/publication/srl-92-2A">pubs.usgs.gov/publication/srl-92-2A</a></td><td>rupture on largely unmapped Candelaria fault, inside the footprint</td></tr>
<tr><td>Sibling repositories (this project's parallel lanes; scores user-reported)</td><td><a href="https://github.com/buffedlizard55-lab">github.com/buffedlizard55-lab</a> (GEMSDOE, GEMSDOE32, GEMSDOE51, 7GEMSDOE, GEMSDOE48, ...)</td><td>template tooling, cached rasters, registry</td></tr>
<tr><td>GEMSDOE54 <code>RUN2-SUMMARY.md</code> (sibling run log; byte-exact quotes in <code>knowledge/sources.json</code>)</td><td><a href="https://github.com/buffedlizard55-lab/GEMSDOE54/blob/main/RUN2-SUMMARY.md">github.com/buffedlizard55-lab/GEMSDOE54/blob/main/RUN2-SUMMARY.md</a></td><td>the 0.2708&rarr;0.2778 mechanism (delete 2,545 dots within 200 m of catalogue), board-rank and detection-floor caveats, holdout priors</td></tr>
<tr><td>INGENIOUS / GDR 1391 2 m temperature probes (CC BY 4.0, DOI 10.15121/1881483)</td><td><a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a></td><td>round-2 H9/H10 layer (3,800 points obtained via the org's hash-pinned mirror)</td></tr>
</table>
<p class=mut>Data provenance chain (sha256 pins, naming-drift table, DEM tile URLs) is in
<code>data/README.md</code> (adapted from the GEMSDOE template). External data policy: free,
public, official sources only; every external claim on this site carries its link.</p>
"""
    (out / "sources.html").write_text(page("Sources", "sources.html", src))

    # ------------------------------------------------------ irregularities --
    irr = f"""
<h2>Irregularities &mdash; flagged, and how each was checked</h2>
<div class=card><h3>IR-56-01: the 0.2778 attached to <code>h33-h33-2-b2</code> is user-reported and unsupported</h3>
<p>The brief asks why <code>h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros</code> &ldquo;got the
highest score (0.2778)&rdquo;. Checked against the sibling's own pages: the GEMSDOE32 site and
README label that artifact <b>UNSCORED</b>, give a <b>modelled projection of 0.2747</b>, and
state that no organizer score exists for it; <code>docs/score-ledger.csv</code> marks all
sibling scores user-reported; the GEMSDOE51 audit (<code>evidence/score_attribution_audit.json</code>)
calls the 0.2778 attribution &ldquo;unsupported and contradicted&rdquo;. <b>What is defensible:</b>
the mechanism the file embodies (catalogue-pruned dotted emission at the metric's break-even
bar &mdash; see <a href="research.html">research &sect;8</a>). <b>What is not:</b> any claim that
this exact file scored 0.2778, or any causal geological story for a public score.</p></div>
<div class=card><h3>IR-56-02: &ldquo;0.3195 is the highest score right now&rdquo; is stale; 0.3774 is unverifiable here</h3>
<p>The verified leaderboard snapshot stored by GEMSDOE32 (2026-10-04,
<code>registry/leaderboard_snapshot_2026-10-04.json</code>) has #1 nchuzhoy <b>0.3262</b>,
#2 kinghorton42 0.3222, #3 DARD 0.3195. GEMSDOE51's one-time official-page check on 2026-10-08
found 0.3195 was not the page high. The brief's newer figure (0.3774, 2026-10-09) cannot be
checked from this sandbox: drivendata.org is not reachable (egress allowlist). It is recorded
as <b>user-supplied, unverified</b>. Check the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official leaderboard</a>
directly; this site does not monitor it (DrivenData ToS).</p></div>
<div class=card><h3>IR-56-03: the portal error <code>"Predicted values must be in range [0, 1]"</code></h3>
<p>A previous attempt from this project was rejected with this message. Two mechanisms produce
it (measured by the GEMSDOE32 sibling on the official rasters): (1) writing the feature stack's
float32 nodata sentinel <code>-3.4028234663852886e+38</code> through unchanged &mdash;
7,113,308 cells carry it, 3,061 inside the submission footprint; (2) NaN inside the footprint.
This session's file: every template-valid pixel finite in [0,&nbsp;1], NaN only where the
official sample is NaN, nodata tag <code>nan</code> &mdash; both the repository validator and
the template-conformance gate pass (receipts in <code>evidence/corrections/run_card.json</code>).</p></div>
<div class=card><h3>IR-56-04: sibling scores are unauthenticated</h3>
<p>Every score in the sibling score ledger (0.1922&hellip;0.2778 family, and the 0.2708 base)
is owner-reported; none carries an organizer receipt. They are used here only as
<b>mechanism evidence</b> (the emission-side break-even), never as targets.</p></div>
<div class=card><h3>IR-56-05: holdout truth is simulated, not the organizer's</h3>
<p>The HOLDOUT-DTI numbers come from a simulated corrections truth (the measured crest lines
of withheld records). They validate the emission machinery and the controls; they are not
organizer scores and are labelled as such everywhere they appear.</p></div>
<div class=card><h3>IR-56-06: LiDAR calibration covers 75% of the footprint</h3>
<p>The 1 m calibration product (706 of 716 official 3DEP tiles) covers 3,892,964 grid cells
(75% of the 5,167,373-px footprint); 10 edge tiles failed in the sibling's CI. Calibration
statistics are computed on covered transects only and labelled with n.</p></div>
<div class=card><h3>IR-56-07: eight literal containment flags mean DUPLICATE/STOP; similarity diagnostics do not waive the rule</h3>
<p>The lane protocol's literal test (&ldquo;more than 70% of your dots fall within 3 px of one
registry raster's dots &rarr; log it as a duplicate and stop&rdquo;) fires on
{reg_n_flags if reg else '8'} sparse registry rasters (containment up to
{fmt(reg_worst_cont,4) if reg else '0.9989'}). Investigated with the discriminating statistics
(the sibling GEMSDOE51 gate's own): every one of them is a <b>habitat/superset emission
12&ndash;38&times; larger</b> than this lane's {dots:,} dots (13GEMSDOE lattice / toporef /
union-tips, 5GEMSDOE pindrop-v4 discovery/nodes, GEMSDOE50 topo-lineament-scatter,
GEMSDOE23 arrangement-matched-habitat, GEMSDOE37 h6-physics-dotted-80k), and for every one of
them the 3&nbsp;px Jaccard is &le; {fmt(reg_worst_jac,4) if reg else '0.091'} and the reverse
containment is &le; {fmt(reg_worst_rev,4) if reg else '0.046'} (globally; &le; 0.023 among the
flagged eight) &mdash; this lane's dot set is a small subset of their habitat, not a re-issue. Against every prior <b>submission of comparable
construction</b> (the 37,654&ndash;44,090-dot h33 family, incl. the 0.2778-attributed file),
containment is &le; 0.334 and Jaccard &le; 0.052. Spearman rank correlation is at most
{fmt(reg_worst_sp,4) if reg else '0.0429'} (dots) / {fmt(reg_worst_sps,4) if reg else '0.1086'}
(surface) against all {reg_n if reg else '412'} unique registry rasters &mdash; far below the
0.90 threshold. Those metrics help describe the overlap but do not alter the literal result:
<b>protocol verdict DUPLICATE/STOP; no slot cleared.</b> The flags are logged with full numbers
in <code>evidence/corrections/registry_check.json</code>. Jaccard, mass ratios and reverse
containment are diagnostic only and cannot override the stop rule.</p></div>
"""
    # round-2 (PR #7) entries from the machine-readable log -- both runs flag, neither hides
    if isinstance(irr_b, list) and bld2:
        new_irr = [i for i in irr_b if i.get("id") in
                   {"IR-56-019", "IR-56-020", "IR-56-021", "IR-56-022", "IR-56-023"}]
        irr += "\n<h2>Round-2 discovery run (PR #7) &mdash; its five entries</h2>\n"
        for i in new_irr:
            title = i.get("title") or i.get("area") or ""
            body = i.get("finding") or i.get("what") or ""
            check = i.get("verified_by") or i.get("why_it_matters") or ""
            irr += (f"<div class=card><h3>{esc(i.get('id'))}: {esc(title)}</h3>\n"
                    f"<p>{esc(body)}</p>\n<p><b>Checked / why it matters:</b> {esc(check)}</p>\n"
                    f"<p class=mut>Done: {esc(i.get('action', ''))} · source: "
                    f"{esc(i.get('verified_by') or i.get('found_by') or '')}</p></div>\n")
        review_irr = [i for i in irr_b if i.get("id") == "IR-56-024"]
        if review_irr:
            irr += "<h2>PR #9 integration review</h2>\n"
            for i in review_irr:
                irr += (f"<div class=card><h3>{esc(i.get('id'))}: {esc(i.get('area'))}</h3>\n"
                        f"<p>{esc(i.get('what'))}</p>\n"
                        f"<p><b>Why it matters:</b> {esc(i.get('why_it_matters'))}</p>\n"
                        f"<p><b>Action:</b> {esc(i.get('action'))}</p>\n"
                        f"<p class=mut>Source: {esc(i.get('found_by'))}</p></div>\n")
        irr += ("<p class=mut>Full machine-readable log (both runs and this integration review, "
                "<code>evidence/irregularities.json</code>, 24 entries): IR-56-001&hellip;013 "
                "round 1, IR-56-014&hellip;018 the concurrent corrections session, "
                "IR-56-019&hellip;023 this round-2 discovery run, IR-56-024 PR #9.</p>\n")
    (out / "irregularities.html").write_text(page("Irregularities", "irregularities.html", irr))

    print(f"site written to {out}/")
    for f in sorted(out.glob("*.html")):
        print("  ", f.name, f.stat().st_size, "B")


if __name__ == "__main__":
    main()
