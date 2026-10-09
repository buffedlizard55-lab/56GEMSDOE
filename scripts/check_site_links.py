import re
import pathlib

docs = pathlib.Path("docs")
bad = []
for f in ["index.html", "executive-summary.html", "submit.html", "irregularities.html",
          "lane1-corrections.html"]:
    p = docs / f
    if not p.exists():
        bad.append((f, "-", "page missing"))
        continue
    t = p.read_text()
    ids = set(re.findall(r'id="([^"]+)"', t))
    for h in sorted(set(re.findall(r"href=['\"]([^'\"]+)['\"]", t))):
        if h.startswith(("http", "mailto", "data:")):
            continue
        frag, _, anc = h.partition("#")
        if frag == "":
            if anc and anc not in ids:
                bad.append((f, h, "anchor missing on this page"))
            continue
        tgt = (docs / frag).resolve()
        if not tgt.exists():
            bad.append((f, h, "file missing"))
        elif anc and tgt.suffix == ".html" and anc not in (docs / frag).read_text():
            bad.append((f, h, "anchor missing on target page"))
print("BROKEN LINKS:", "none - every internal link resolves inside docs/" if not bad else "")
for b in bad:
    print("  ", b)
