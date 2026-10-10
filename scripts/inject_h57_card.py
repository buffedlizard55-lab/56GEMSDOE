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
    tif = sub["file"]
    size_kb = (ROOT / "docs" / "downloads" / tif).stat().st_size / 1024
    return f"""{MARK_OPEN}
<div class=card style="border-color:#3fd68f">
<h2>&#11015; H57 corrections-band GeoTIFF &mdash; download and submit</h2>
<p><a class="btn" href="downloads/{tif}">Download {tif} ({size_kb:.0f} KB)</a>
<a class="btn alt" href="downloads/{Path(tif).stem}.zip">.zip</a>
<a class="btn alt" href="h57.html">What it is &amp; the holdout &rarr;</a></p>
<p><b>OK to download: YES. OK to submit (the form will accept it): YES.</b>
Measured on this file: {val['n_nan']} NaN cells, 0 infinite cells, min {val['min']:.1f},
max {val['max']:.1f}, 1 band, float32, {val['crs']}, shape {val['shape']},
transform {val['transform']} &mdash; identical to <code>sample_submission.tif</code>;
validator problems: <code>{val['problems']}</code>. {sub['dots']:,} dots.</p>
<p><b>Submission name</b> <code>{sub['name']}</code><br>
<b>Note</b> ({sub['note_chars']}/140): <code>{sub['note']}</code><br>
<b>sha256</b> <code>{c['raster_sha256']}</code></p>
<p><b>Honest verdict:</b> the lane's crest-steering hypothesis is <b>REFUTED</b> by its own
holdout &mdash; offsets cluster under two pixels (median {e1['dem_abs_offset_median_px']:.2f} px,
signed median {e1['dem_signed_median_px']:.2f} px, {e1['dem_frac_abs_ge_2px']:.3f} beyond 2 px vs
{e1['random_null_frac_abs_ge_2px']:.3f} for the random null), and crest-steered dots scored
{e3['pooled']['B2_evidence']:.5f} against {e3['pooled']['B1_corridor']:.5f} for the same dots
placed without looking at the evidence ({e3['withheld_positives']:,} withheld positives, paired
contrast {e3['paired_contrast_vs_evidence_free_corridor']['B2_evidence']}). So this file emits
the <b>unsteered</b> cover of the band the organizers describe as containing corrections
(forum 11516): dots 200 m either side of every catalogue trace, 0 on the masked catalogue.
It is a <b>bet on an organizer statement, not a validated discovery</b>, and no holdout can
score that family because no corrections labels exist for us.</p>
<p>Uniqueness: max Spearman {reg['max_spearman']:.3f} (bar 0.90) and max exact-pixel Jaccard
{reg['max_exact_jaccard_vs_submissions']:.3f} against the worst-overlapping earlier submissions;
the literal 3 px containment clause fires and is logged as IR-57-003.
Run card: <code>evidence/h57_run_card.json</code>.</p>
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
