#!/usr/bin/env python3
"""Build the current, evidence-led DOE GEMS status site in docs/.

The active corrections run is negative. Generated pages must not advertise a file as ready to
submit. The only one-click raster is a historical, format-valid archive that still fails the
registry duplicate-and-stop rule. Run: python scripts/build_site.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
.btn.stop{background:var(--bad);color:#1c0808}
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
    tifs = sorted(DOWNLOADS.glob("gems56-corr-*-nan.tif"))
    tif = tifs[-1] if tifs else None
    rel = tif.name if tif else ""
    dlbtn = ""
    if dl and tif:
        dlbtn = (f'<div class="dlbtn"><a class="btn stop" href="downloads/{esc(rel)}">'
                 f'&#11015; Download archived TIFF — NOT safe to submit</a> '
                 f'<span class=mut>.tif ({tif.stat().st_size / 1024:.0f} KB) · '
                 f'technical inspection only</span></div>')
    nav = "".join(
        f'<a href="{h}"{" class=active" if h == active else ""}>{t}</a>'
        for h, t in (("index.html", "Home"), ("executive-summary.html", "Submission status"),
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
<div class=values><div class=wrap><b>Evidence classes.</b>
<span class=ok>ORGANIZER-CONFIRMED</span> requires an organizer receipt;
<span class=warn>HOLDOUT-DTI</span> requires evaluator/version, withheld-positive count, and 95% CI;
<span class=mut>MEASURED</span> describes local measurements; user and sibling reports are not organizer facts.</div></div>
<main class=wrap><div class=card><h2 class=bad>Current verdict: NEGATIVE / STOP — no safe-to-submit file</h2>
<p>The active corrections primary triggers the literal &gt;70%-within-3-px registry stop and fails
strict sample-footprint format validation. The 14-dot sensitivity also fails format validation.
The format-valid historical TIFF linked above still triggers the registry stop. No slot has been
used; the experiment budget is exhausted; no file is selected or promoted. The archive download is
for technical inspection only.</p>
<p><a href="research.html">Research and 0.2778 evidence review</a> ·
<a href="irregularities.html">Machine-logged findings</a></p></div>{body}</main>
<footer><div class=wrap>56GEMSDOE · <a href="https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/evidence/run_card.json">active run card</a> ·
generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} by
<code>scripts/build_site.py</code> ·
<a href="https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html">project site</a></div></footer>
</body></html>"""


def load_json(p):
    return json.loads(Path(p).read_text())


def fmt(x, n=4):
    return f"{x:.{n}f}" if isinstance(x, (int, float)) else str(x)



def write_status_pages(out):
    """Render every current status page from the authoritative run card and evidence log."""
    run = load_json(ROOT / "evidence" / "run_card.json")
    irr = load_json(ROOT / "evidence" / "irregularities.json")
    results = run["format_validation_review"]["results"]
    gate = run["registry_comparison"]["shared_gate_verdict"]
    surface = run["registry_comparison"]["stage_checks"]["primary"]["preplacement_surface"]
    hold = run["holdout_dti"]
    arms = hold["arms"]
    sub = run["submission"]
    archive = results["historical_6504"]
    archive_name = Path(archive["path"]).name
    home_rows = []
    for key, label, purpose in (
        ("primary", "Active corrections primary (1 dot)", "corrections"),
        ("sensitivity", "Sensitivity (14 dots)", "corrections"),
        ("discovery_archive", "Discovery archive (25,000 dots)", "outside active lane"),
        ("historical_6504", "Historical corrections archive (6,504 dots)", "historical"),
    ):
        r = results[key]
        status = "PASS — local format only" if r["ok"] else "FAIL — not template-conformant"
        explanation = "; ".join(r.get("problems", [])) or "Exact sample finite/NaN mask and nodata match."
        if key == "primary":
            a = f'<a href="downloads/{esc(Path(r["path"]).name)}">{esc(label)}</a>'
        elif key == "sensitivity":
            a = f'<a href="downloads/{esc(Path(r["path"]).name)}">{esc(label)}</a>'
        elif key == "discovery_archive":
            a = f'<a href="downloads/{esc(Path(r["path"]).name)}">{esc(label)}</a>'
        else:
            a = f'<a href="downloads/{esc(archive_name)}">{esc(label)}</a>'
        home_rows.append(
            f'<tr><td>{a}</td><td>{esc(purpose)}</td><td>{esc(status)}</td>'
            f'<td>{esc(explanation)}</td><td>{esc(r["sha256"])}</td></tr>'
        )
    hold_rows = []
    for arm in ("B_snap", "D_jitter"):
        value = arms[arm]
        hold_rows.append(
            f'<tr><td>{esc(arm)}</td><td>{fmt(value["dti"], 9)}</td>'
            f'<td>[{fmt(value["ci95"][0], 9)}, {fmt(value["ci95"][1], 9)}]</td></tr>'
        )
    hold_table = "".join(hold_rows)
    near = gate["directed_near3px_fraction"]
    corr = gate["max_spearman"]
    measurements = run["measurements"]
    offsets = measurements["offsets_null_calibrated_px"]
    corridors = measurements["corridors"]["decision_gate"]
    lidar = measurements["lidar_3m"]
    measurement_html = f"""
<h3>Local corrections measurements — MEASURED, not score</h3>
<p>Measured from the hash-pinned owner-bridge inputs; their organizer provenance is not authenticated.
These quantities describe this corrections lane, not competition performance.</p>
<table><thead><tr><th>Measurement</th><th>Result</th><th>Interpretation/limit</th></tr></thead><tbody>
<tr><td>Null-calibrated DEM median offset</td><td>{fmt(offsets["dem_median"], 3)} px ({offsets["dem_n"]:,} samples)</td><td>Not a consistent ≥2 px displacement.</td></tr>
<tr><td>Null-calibrated magnetic median offset</td><td>{fmt(offsets["mag_median"], 3)} px ({offsets["mag_n"]:,} samples)</td><td>Near zero under this calibration.</td></tr>
<tr><td>Joint DEM+mag median</td><td>{fmt(offsets["joint_median"], 3)} px ({offsets["joint_n"]:,} concordant samples)</td><td>Below the stated ~2 px lane threshold.</td></tr>
<tr><td>Absolute offset null medians</td><td>random {fmt(offsets["null_random_abs_median"], 3)} px; rotated {fmt(offsets["null_rotated_abs_median"], 3)} px</td><td>Estimator noise floor is comparable to the observed sub-pixel displacement.</td></tr>
<tr><td>Corridor decision gate</td><td>{corridors["qualifying"]} of {corridors["components"]} corridors qualify</td><td>Qualifying length {corridors["qualifying_length_m"]:,} m; sigma floor {fmt(corridors["sigma_floor_px"], 3)} px.</td></tr>
<tr><td>3 m LiDAR check</td><td>{lidar["segments_ge_200m"]} of {lidar["segments"]} segments reach ≥200 m</td><td>Only {fmt(lidar["coverage_fraction_of_catalogue"] * 100, 2)}% catalogue coverage; limited external validation.</td></tr>
</tbody></table>
"""
    source_links = """
<ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official DOE GEMS Prize problem page</a> — objective, DTI metric, 300 m triangular kernel, α=0.2, β=0.8, GeoTIFF requirements, and the page's description of its sample submission.</li>
<li><a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">DrivenData staff reply, forum topic 11516</a> — known USGS/INGENIOUS fault pixels are masked/excluded from penalty terms; it does not specify a 200 m buffer.</li>
<li><a href="https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html">Sibling GEMSDOE32 page</a> — H33-2-B2 is labeled UNSCORED and 0.2747 is a projection, not an organizer score.</li>
<li><a href="https://github.com/buffedlizard55-lab/GEMSDOE54/blob/main/RUN2-SUMMARY.md">Sibling GEMSDOE54 Run 2 summary</a> — reports 200 m catalogue-distance pruning as a raster-construction mechanism; this is not a submission receipt.</li>
</ul>"""

    index = f"""
<h2>Project status — corrections lane</h2>
<p><b>NEGATIVE / STOP.</b> No TIFF in this repository is cleared or safe to submit. The
active corrections run is authoritative (`2026-10-09T16:49:44Z`); the later discovery run is
outside this corrections-only scope. The experiment budget is exhausted. No slot was used, no
artifact was selected, and no new experiment was run during this review.</p>
<div class=card><h2>Download for inspection only — NOT safe to submit</h2>
<p><a class="btn stop" href="downloads/{esc(archive_name)}">&#11015; Download historical format-valid TIFF — NOT SAFE TO SUBMIT</a></p>
<p>It passes the strict local format check against the hash-pinned bridge sample, but its
historical registry receipt triggers the literal proximity stop. This link preserves the file
for audit; it is not a recommendation or candidate upload.</p>
<p><b>SHA-256:</b> <code>{esc(archive["sha256"])}</code></p></div>
<h2>Audited files</h2>
<p>Local template validation is not organizer acceptance. The pinned sample's provenance/content
is not authenticated; see the limitation below and the irregularity register.</p>
<table><thead><tr><th>Artifact</th><th>Scope</th><th>Strict local format result</th><th>Finding</th><th>SHA-256</th></tr></thead>
<tbody>{''.join(home_rows)}</tbody></table>
<h2>Active corrections result</h2>
<p>The primary `h56-corr-snap200cm-20261009` has the archived note below ({sub["note_chars"]}/140
characters), but the name/note are preserved for audit only. <b>Do not paste them into a submission
form.</b></p>
<p><b>Audit-only name:</b> <code>{esc(sub["name"])}</code><br><b>Audit-only note:</b>
<code>{esc(sub["note"])}</code><br><b>TIFF SHA-256:</b> <code>{esc(sub["sha256"])}</code></p>
<ul><li>Pre-placement surface check: max ρ={fmt(surface["max_spearman"], 6)} (no 0.90 trigger among
readable entries), but {surface["error_count"]} registry rasters were unreadable, so this is not a
complete clearance.</li>
<li>Final-dot registry gate: max ρ={fmt(corr, 6)}; directed within-3-px fraction {fmt(near, 3)}
triggers on {gate["offender_count"]}/{gate["priors_checked"]} priors, exceeding 0.70. Duplicate-and-stop
applies; low correlation does not waive proximity.</li>
<li>Strict local format: 7,111,787 finite cells outside the sample mask and `nodata=None` while
the template tag is NaN. The sensitivity TIFF has the same format failure.</li>
<li>No admissible artifact-level/new-fault holdout result; the 1-dot output was not separately
scored. The latest run has no per-feature canary receipt.</li></ul>
<h2>Holdout evidence — not a competition score</h2>
<p>Both rows are <b>HOLDOUT-DTI</b> from evaluator <code>{esc(hold["evaluator_version"])}</code>,
with {hold["withheld_positive_pixels"]:,} withheld catalogue-positive pixels and 95% CIs shown.
This is method-level catalogue recovery, not the organizer's hidden-new-fault score and not an
artifact-level evaluation. Treat as exploratory: protocol/provenance defects remain unresolved,
and the current run has no admissible promotion evidence.</p>
<table><thead><tr><th>HOLDOUT-DTI arm</th><th>DTI</th><th>95% CI</th></tr></thead><tbody>{hold_table}</tbody></table>
<p>See <a href="research.html">research</a> for the `0.2778` evidence review and published metric;
<a href="irregularities.html">irregularities</a> for logged provenance/implementation issues;
<a href="https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/README.md">repository README</a> for the standing prompt, review passes, and reproduction steps.</p>
<h2>Input/template caveat</h2>
<p>The hash-pinned owner-bridge sample is locally identical to the catalogue (60,988 positive
cells), while the official public problem page describes a total-fault-absence sample. Its grid
matches the training raster, but neither its provenance nor content is independently
organizer-authenticated. Only its finite mask has been used for local validation. A logged-in human
must compare against the actual data-tab file before any future submission is considered.</p>
"""
    (out / "index.html").write_text(page("Project status", "index.html", index, dl=False))

    submit = f"""
<h2>Submission status: DO NOT UPLOAD</h2>
<div class=card><h3 class=bad>No safe-to-submit file exists</h3>
<p>The active corrections candidate fails strict template validation and triggers the explicit
registry duplicate-and-stop rule. The only file that passes strict local format is an older
research raster that also triggers the registry stop. A separate discovery TIFF is both outside
the corrections lane and format-invalid. The experiment budget is exhausted; no submission slot
is cleared.</p>
<p><a class="btn stop" href="downloads/{esc(archive_name)}">Download archived TIFF for inspection only — NOT safe to submit</a></p>
<p>Archive SHA-256: <code>{esc(archive["sha256"])}</code>. This download is not an instruction to
upload it.</p></div>
<h2>Candidate name and note — audit record only</h2>
<p>The authoritative run card preserves this unique file name and {sub["note_chars"]}-character note
to keep the run auditable. <b>Do not submit or paste this note.</b></p>
<p><code>{esc(sub["name"])}</code></p><p><code>{esc(sub["note"])}</code></p>
<p>Current file SHA-256: <code>{esc(sub["sha256"])}</code> · strict format: <b>FAIL</b> ·
registry: <b>DUPLICATE / STOP</b> · holdout: no admissible artifact-level result.</p>
<h2>Why submission is blocked</h2>
<ol><li><b>Pre-placement surface:</b> max rank correlation {fmt(surface["max_spearman"], 6)}, with no
0.90 trigger among readable entries; {surface["error_count"]} of {surface["priors_checked"]} rasters
were unreadable, so this was not a complete clearance.</li>
<li><b>Final-dot registry rule:</b> directed within-3-px fraction is {fmt(near, 3)} against
{gate["offender_count"]}/{gate["priors_checked"]} prior rasters, above the 0.70 stop threshold.
Maximum rank correlation is {fmt(corr, 6)}, below 0.90; that does not negate the proximity trigger.</li>
<li><b>Format:</b> 7,111,787 finite cells are outside the pinned sample's footprint; nodata is absent
instead of matching the template's NaN. The sensitivity output fails the same check.</li>
<li><b>Holdout:</b> the local withheld target is catalogue recovery, not new-fault truth; the
1-dot TIFF itself was not evaluated, the active run's leakage canary is missing, and provenance
issues remain.</li></ol>
<h2>If a future, separately authorized submission is considered</h2>
<p>This is a checklist for a new authorized review, not permission to continue the exhausted run:</p>
<ol><li>Have a logged-in user compare the bridge input files with the official competition data-tab
files and record their SHA-256 hashes and exact sample mask.</li>
<li>Use an explicitly authorized new experiment budget. Follow the complete corrections-lane holdout
protocol and provenance requirements; attach per-feature leakage canaries and final-dot registry
checks. Do not waive a duplicate trigger.</li>
<li>Only after a separate selector decision, produce a new raster using the shared tools and run
<code>scripts/validate_submission.py</code> against the authenticated sample/template. Record the
file hash and all validator output in a run card.</li>
<li>Use the official <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>
upload instructions. Save its returned receipt before using the label ORGANIZER-CONFIRMED.</li></ol>
<p>No receipt exists for this run. Do not upload the archived file or the current one-dot file.</p>
"""
    (out / "executive-summary.html").write_text(page("Submission status", "executive-summary.html", submit, dl=False))

    research = f"""
<h2>What can—and cannot—be said about the claimed 0.2778</h2>
<p><b>No 0.2778 score is organizer-confirmed in this repository.</b> There is no submission-page
receipt. A number reported by a user or sibling repository is not an organizer score; a model
projection is never a score.</p>
<h3>Source-verified facts and source classes</h3>
{source_links}
<p>The public official problem page specifies the distance-weighted Tversky index with a 300 m
triangular kernel, α=0.2 and β=0.8. It says known USGS/INGENIOUS fault pixels are excluded from
penalties per the staff reply. That exact-pixel masking does not make the whole 200 m neighborhood
free of false-positive cost.</p>
<h3>A mechanism hypothesis, not an explanation of an unverified score</h3>
<p>GEMSDOE54 reports that its child raster contains 37,654 dots, made by removing 2,545 dots within
2 px (200 m) of a catalogue trace from a 40,199-dot parent; it also reports a smaller fraction of
dots within 300 m of the catalogue. This is a sibling-reported construction description, not an
organizer receipt and not independently re-derived from the source rasters here. The pruning could
reduce false-positive mass, but it could also remove credit if hidden truth lies nearby.</p>
<p>For unit-valued predictions, if <code>N</code> is predicted mass, <code>G</code> truth mass,
<code>T=TP_w</code>, and <code>M</code> is the total proximity-weighted true-positive credit, the
published decomposition implies:</p>
<pre>DTI = T / (0.2*N + 0.8*G + 0.2*(T-M))</pre>
<p>This is algebra from the metric, not access to hidden labels. It explains a possible trade-off;
it cannot determine the outcome of pruning without the private new-fault labels. The defensible
answer is therefore that the raster embodies a catalogue-distance-pruning mechanism, while the
claimed 0.2778 score and its cause remain unverified.</p>
<h3>Active corrections lane: negative</h3>
<p>The authoritative corrections run card records the negative result. The 1-dot primary triggers
the literal registry stop despite low rank correlation and fails strict format validation. The
14-dot sensitivity fails strict format too. The 6,504-dot historical raster is format-conformant
to the local bridge sample but still triggers the registry rule. No file is safe to submit.</p>
{measurement_html}
<h3>Method-level holdout values — HOLDOUT-DTI, not score</h3>
<p>Evaluator <code>{esc(hold["evaluator_version"])}</code>; {hold["withheld_positive_pixels"]:,}
withheld catalogue positives; 95% CIs. These are method-level catalogue-recovery diagnostics, not
new-fault truth, not per-artifact scores, and not promotion evidence.</p>
<table><thead><tr><th>HOLDOUT-DTI arm</th><th>DTI</th><th>95% CI</th></tr></thead><tbody>{hold_table}</tbody></table>
<p>The one-dot output was not separately scored. The current holdout receipt has no per-feature AUC
canary; a previous run's canary cannot be transferred. The corrections evaluator's catalogue-derived
snap inputs use <code>fold["visible"]</code> while the buffer applies to <code>fold["fit"]</code>, and
its receipt records <code>design.prevalence: null</code> although the invocation passed 0.00294.
Do not rerun: the recorded experiment budget is exhausted.</p>
<h3>Authoritative sources</h3>{source_links}
<p>Full discussion and exact source classifications:
<a href="https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/docs/research/leader-analysis-2026-10-09.md">research note</a>.
The workspace's three-pass review is in <code>docs/review/2026-10-09.md</code>.</p>
"""
    (out / "research.html").write_text(page("Research and score claim", "research.html", research))

    hypotheses = f"""
<h2>Corrections-lane hypothesis and outcome</h2>
<p><b>Hypothesis:</b> a catalogue trace may be laterally displaced from a real fault, and coherent
DEM-scarp plus magnetic-gradient evidence could locate a corrected trace. The named non-fault mimic
is an erosional terrace or alluvial-fan edge; nearby unmapped strands are another ambiguity.</p>
<p>The active run's measured offset/corridor gates did not authorize a candidate. The primary was
emitted as a one-dot research artifact, then the explicit registry rule fired and strict format
replay failed. Verdict: <b>NEGATIVE / STOP</b>. No placement, promotion, or experiment should follow
under the exhausted budget.</p>
<h3>Guardrails for any future authorized lane</h3>
<ul><li>Check rank correlation against registry rasters before placement and on the final dots.</li>
<li>If ρ &gt; 0.90 or more than 70% of dots are within 3 px of a registry raster, log duplicate and
stop.</li><li>Hide whole segments with a buffer; derive catalogue features only from visible faults;
mask visible fault pixels exactly.</li><li>Report pooled HOLDOUT-DTI with evaluator version, withheld-positive count and 95% CI; never
call a projection a score. Canary every feature; AUC &gt; 0.90 is leakage until resolved.</li>
<li>Stop after three experiments or two hours. This run's budget is exhausted. Do not select or
promote a submission in this lane.</li></ul>
<p>These are constraints, not a proposal to resume the current run. See the run card, review record,
and <a href="research.html">evidence note</a>.</p>
"""
    (out / "hypotheses.html").write_text(page("Corrections hypothesis", "hypotheses.html", hypotheses))

    sources = f"""
<h2>Sources and what they establish</h2>
<p>Source tiers are explicit. Official rules establish metric and format; staff replies establish
only the scope they state. Sibling repositories are useful leads but are not organizer receipts.</p>
{source_links}
<h3>Not established</h3>
<ul><li>No official leaderboard page or submission receipt was fetched; there is no
ORGANIZER-CONFIRMED score in this review.</li><li>The owner-bridge sample's provenance and content
are not authenticated against the login-gated data tab.</li><li>The public page's exact-pixel masking
reply does not establish a 200 m buffer exemption.</li><li>Sibling raster counts or scores are not
independently verified by an organizer source.</li></ul>
"""
    (out / "sources.html").write_text(page("Sources", "sources.html", sources))

    irregularities = []
    for item in irr:
        if item.get("id") in {"IR-56-024", "IR-56-025", "IR-56-026", "IR-56-027", "IR-56-028"}:
            irregularities.append(
                f'<div class=card><h3>{esc(item.get("id"))}: {esc(item.get("title", ""))}</h3>'
                f'<p>{esc(item.get("finding", ""))}</p>'
                f'<p><b>Action:</b> {esc(item.get("action", ""))}</p>'
                f'<p class=mut><b>Verified by:</b> {esc(item.get("verified_by", ""))}</p></div>'
            )
    irr_html = "".join(irregularities) or "<p>No review entries were found.</p>"
    irr_page = f"""
<h2>Review findings (2026-10-09)</h2>
<p>These issues are preserved so a local pass is not confused with organizer acceptance or an
experiment result.</p>
{irr_html}
<p>The full machine-readable append-only log is <a href="https://github.com/buffedlizard55-lab/56GEMSDOE/blob/main/evidence/irregularities.json">evidence/irregularities.json</a>
in the repository. Earlier lane entries are preserved there as well.</p>
"""
    (out / "irregularities.html").write_text(page("Review irregularities", "irregularities.html", irr_page))

    prior = f"""
<h2>Historical corrections artifact — research archive only</h2>
<p>The 6,504-dot file <code>{esc(archive_name)}</code> passes strict local template-mask, nodata,
range, and grid checks against the pinned bridge sample. Its SHA-256 is
<code>{esc(archive["sha256"])}</code>. This is a format result, not a duplicate-gate pass and not
organizer acceptance.</p>
<p>The literal registry proximity rule triggered on eight prior rasters in its receipt. That rule
requires duplicate-and-stop. Diagnostic low correlation/Jaccard statistics do not waive the
trigger. The file is <b>not safe to submit</b>.</p>
<p><a class="btn stop" href="downloads/{esc(archive_name)}">Download for technical inspection only</a></p>
<h2>Relationship to the active run</h2>
<p>This historical 6,504-dot output is not the authoritative active corrections run. The latest
corrections card is `evidence/run_card.json`, dated 2026-10-09T16:49:44Z. Its one-dot primary is
strict-format-invalid and hits the registry stop. The newer discovery card is a different lane,
not an override. All run histories retain their own receipts; no experiment is authorized or
remaining.</p>
"""
    (out / "prior-run.html").write_text(page("Historical run", "prior-run.html", prior))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DOCS), help="output directory (defaults to docs/)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "downloads").mkdir(parents=True, exist_ok=True)
    write_status_pages(out)
    (out / "submit.html").write_text("""<!doctype html><html lang=en><head>
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0; url=executive-summary.html">
<title>Submission status — NEGATIVE / STOP</title></head><body>
<h1>NEGATIVE / STOP — do not upload</h1><p>No TIFF in this repository is cleared or safe to submit.
<a href="executive-summary.html">Current submission status and future-review checklist</a>.</p>
</body></html>""")
    (out / "prior-irregularities.html").write_text("""<!doctype html><html lang=en><head>
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0; url=irregularities.html">
<title>Historical irregularities — current status</title></head><body>
<h1>Historical irregularities are superseded</h1><p>See the
<a href="irregularities.html">current review findings</a> and
<a href="executive-summary.html">current submission status</a>.</p></body></html>""")
    print(f"site written to {out}/")
    for f in sorted(out.glob("*.html")):
        print(f"  {f.name} {f.stat().st_size} B")


if __name__ == "__main__":
    main()
