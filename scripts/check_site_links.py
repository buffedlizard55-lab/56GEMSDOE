#!/usr/bin/env python3
"""Audit every internal link and anchor in the published site, and list the external hosts to click.

Generated pages can drift from the tree they describe; this is the cheap check that catches it. It walks
every ``*.html`` under ``docs/`` (so a page added by another run is audited too), resolves each relative
``href`` against the file system, checks that in-page anchors exist, and prints the external URLs so a human
can verify them by hand - we cannot fetch them from the sandbox, and no claim here depends on doing so.

Reproduce: python scripts/check_site_links.py        (exit 1 on any broken link)
"""
import pathlib
import re
import sys
from urllib.parse import urlparse

docs = pathlib.Path(__file__).resolve().parent.parent / "docs"
pages = sorted(docs.rglob("*.html"))
bad, external = [], set()
for p in pages:
    t = p.read_text()
    ids = set(re.findall(r'id="([^"]+)"', t))
    for h in sorted(set(re.findall(r"href=['\"]([^'\"]+)['\"]", t))):
        if h.startswith(("http://", "https://", "mailto:", "data:")):
            external.add(h)
            continue
        frag, _, anc = h.partition("#")
        rel = (p.parent / frag) if frag else p
        if frag == "":
            if anc and anc not in ids:
                bad.append((p.relative_to(docs), h, "anchor missing on this page"))
            continue
        tgt = rel.resolve()
        if not tgt.exists() or not tgt.is_relative_to(docs):
            bad.append((p.relative_to(docs), h, "file missing or outside docs/"))
        elif anc and tgt.suffix == ".html" and not re.search(
                r"""id=['"]""" + re.escape(anc) + r"""['"]""", tgt.read_text()):
            bad.append((p.relative_to(docs), h, "anchor missing on target page"))

# Repo-relative paths that the pages cite as <code>...</code> are resolved against the working tree too: a
# receipt named on a page has to exist, or the page is not verifiable. Sentences that name a sibling
# repository are skipped - those paths are not ours.
root = docs.parent
cited = 0
for q in pages:
    t = q.read_text()
    for m in re.finditer(r"<code>((?:evidence|docs|registry|scripts)/[A-Za-z0-9_.\-/]+\.(?:json|csv|md|tif|py|sh))</code>", t):
        ctx = t[max(0, m.start() - 170):m.end() + 60]
        if re.search(r"GEMSDOE\d+|buffedlizard55-lab/|sibling", ctx):
            continue
        cited += 1
        if not (root / m.group(1)).exists():
            bad.append((q.relative_to(docs), m.group(1), "cited path does not exist in this repository"))
print(f"repo-relative receipt paths cited and resolved: {cited}")

print(f"pages audited: {len(pages)}  ({', '.join(str(p.relative_to(docs)) for p in pages[:6])}, ...)")
print("BROKEN LINKS:", "none - every internal link resolves inside docs/" if not bad else "")
for b in bad:
    print("  ", b)
hosts = {}
for u in sorted(external):
    hosts.setdefault(urlparse(u).netloc, []).append(u)
print(f"\nexternal URLs referenced ({len(external)} on {len(hosts)} hosts) - click these manually; "
      "the sandbox has no route to them:")
for host, urls in sorted(hosts.items()):
    print(f"  {host}  ({len(urls)})")
    for u in urls[:4]:
        print("     ", u)
    if len(urls) > 4:
        print(f"      ... {len(urls) - 4} more")
sys.exit(1 if bad else 0)
