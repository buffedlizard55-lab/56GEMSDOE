#!/usr/bin/env python3
"""Put the H57 file on the front page that another lane's generator owns.

Two generators now write `docs/index.html` and `docs/executive-summary.html`:
`scripts/build_front.py` (the dotted-ridge lane, merged to main) and
`scripts/build_site.py` (this corrections lane). Rather than fork a page or delete another
lane's work, this script injects one self-contained H57 card immediately after `<main ...>`,
idempotently (an HTML marker comment guards re-runs), and leaves everything else untouched.

Run it after whichever generator ran last:
    .venv/bin/python scripts/build_front.py   # or scripts/build_site.py
    .venv/bin/python scripts/inject_h57_card.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK_OPEN = "<!-- H57-CARD:BEGIN -->"
MARK_CLOSE = "<!-- H57-CARD:END -->"


def card_html() -> str:
    c = json.loads((ROOT / "evidence" / "h57_run_card.json").read_text())
    sub, val = c["submission"], c["validator_output"]
    e1 = c["result_E1_MEASURED"]
    e3 = c["holdout_dti"]["E3_neighbour_strand_folds"]
    reg = c["correlation_overlap_vs_registry"]
    uniq = json.loads((ROOT / "evidence" / "h57_uniqueness.json").read_text())
    literal = uniq.get("literal", {})
    tif = sub["file"]
    size_kb = (ROOT / "docs" / "downloads" / tif).stat().st_size / 1024
    return f"""{MARK_OPEN}
<div class=card style="border-color:#ff6b6b">
<h2>&#11015; H57 corrections-band GeoTIFF &mdash; audit download only, NOT CLEARED</h2>
<p><a class="btn" href="downloads/{tif}">Download {tif} ({size_kb:.0f} KB)</a>
<a class="btn alt" href="downloads/{Path(tif).stem}.zip">.zip</a>
<a class="btn alt" href="h57.html">What it is &amp; the holdout &rarr;</a></p>
<p><b>Available for audit download: YES. Cleared to submit: NO.</b>
The local validator reports {val['n_nan']} NaN cells, 0 infinite cells, min {val['min']:.1f},
max {val['max']:.1f}, 1 band, float32, {val['crs']}, shape {val['shape']},
transform {val['transform']}; this is not an organizer upload receipt, and zero NaNs does not
match the official sample's NaN exterior. No portal upload was tested. {sub['dots']:,} dots.</p>
<p><b>Run-record name (not a submission instruction)</b> <code>{sub['name']}</code><br>
<b>Run-record note</b> ({sub['note_chars']}/140): <code>{sub['note']}</code><br>
<b>sha256</b> <code>{c['raster_sha256']}</code></p>
<p><b>Honest verdict:</b> the lane's crest-steering hypothesis is <b>REFUTED</b> by its own
holdout &mdash; offsets cluster under two pixels (median {e1['dem_abs_offset_median_px']:.2f} px,
signed median {e1['dem_signed_median_px']:.2f} px, {e1['dem_frac_abs_ge_2px']:.3f} beyond 2 px vs
{e1['random_null_frac_abs_ge_2px']:.3f} for the random null). HOLDOUT-DTI evaluator
<code>{c['holdout_dti']['evaluator_version']}</code>, {e3['withheld_positives']:,} withheld positives:
B2 crest-steered {e3['pooled']['B2_evidence']:.6f} [{e3['ci95']['B2_evidence'][0]:.6f}, {e3['ci95']['B2_evidence'][1]:.6f}]
vs B1 evidence-free {e3['pooled']['B1_corridor']:.6f} [{e3['ci95']['B1_corridor'][0]:.6f}, {e3['ci95']['B1_corridor'][1]:.6f}];
paired 95% contrast {e3['paired_contrast_vs_evidence_free_corridor']['B2_evidence']}.
These are local results on withheld mapped faults, not organizer scores or tests of real corrections truth.
The historical run emitted an unsteered 200 m band-cover: a coverage bet, not an evidence-supported
corrected trace. No holdout can score the real corrections family because no corrections labels exist.</p>
<p>Uniqueness diagnostics: max Spearman {reg['max_spearman']:.3f} and max exact-pixel Jaccard
{reg['max_exact_jaccard_vs_submissions']:.3f}; these do not waive the literal gate. The final-dot
receipt says <b>{literal.get('verdict', 'DUPLICATE/STOP')}</b> (max directed near fraction
{literal.get('max_near_3px_fraction', 1.0):.3f}; {len(literal.get('near_offenders', []))} near-offenders).
Under the stated protocol this blocks upload and slot selection. The H57 holdout is negative for
crest steering, and no holdout tests real corrections truth. Run card:
<code>evidence/h57_run_card.json</code>; current decision:
<code>evidence/submission_status.json</code>.</p>
</div>
{MARK_CLOSE}
"""


def inject(path: Path, html: str) -> bool:
    s = path.read_text()
    s = re.sub(re.escape(MARK_OPEN) + ".*?" + re.escape(MARK_CLOSE), "", s, flags=re.S)
    m = re.search(r"<main[^>]*>", s)
    if not m:
        return False
    s = s[:m.end()] + "\n" + html + s[m.end():]
    path.write_text(s)
    return True


def main() -> int:
    html = card_html()
    for name in ("index.html", "executive-summary.html"):
        p = ROOT / "docs" / name
        if p.exists():
            print(f"{name}: {'injected' if inject(p, html) else 'NO <main> TAG - skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
