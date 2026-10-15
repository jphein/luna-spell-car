#!/usr/bin/env python3
"""Fast static checks that catch the bugs this project has actually hit."""
import json, os, re, sys
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "web", "app.html"), encoding="utf-8").read()
fails = []
def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg); ok or fails.append(msg)

ver = open(os.path.join(ROOT, "VERSION")).read().strip()
check(re.fullmatch(r"\d+\.\d+\.\d+", ver) is not None, f"VERSION is semver ({ver})")
cards = json.load(open(os.path.join(ROOT, "web", "cards.json"), encoding="utf-8"))
need = {"name", "full", "say", "g", "u", "r", "p", "t", "artist", "img"}
check(all(need <= set(c) for c in cards), f"cards.json: {len(cards)} cards have all fields")
check(all(c["img"].startswith("data:image/jpeg;base64,") for c in cards), "cards.json: art is embedded")

script = src[src.index("<script>\nconst CARDS"):]
names = re.findall(r"^(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)", script, re.M)
dupes = [n for n, k in Counter(names).items() if k > 1]
check(not dupes, "no duplicate top-level names" + (f": {dupes}" if dupes else ""))
refs = set(re.findall(r'\$\("([\w-]+)"\)', src)) | set(re.findall(r'getElementById\("([\w-]+)"\)', src))
ids = re.findall(r'\bid="([\w-]+)"', src) + re.findall(r'\.id = "([\w-]+)"', src)
markup_ids = re.findall(r'\bid="([\w-]+)"', src[:src.index("<script>")])
check(not (refs - set(ids)), "every $(\"id\") exists in the HTML" + (f": missing {sorted(refs - set(ids))}" if refs - set(ids) else ""))
dup_ids = [i for i, k in Counter(markup_ids).items() if k > 1]
check(not dup_ids, "element ids are unique" + (f": {dup_ids}" if dup_ids else ""))
gos = set(re.findall(r'data-go="(\w+)"', src)); screens = set(re.findall(r"(\w+):\s*\"[^\"]*\"", src[src.index("const screens"):src.index("};", src.index("const screens"))]))
check(gos <= screens, "every home tile has a screen" + (f": {sorted(gos - screens)}" if gos - screens else ""))
check(all(f'<section id="{g}"' in src for g in gos), "every screen has a <section>")
stored = set(re.findall(r'store\("(luna_\w+)"', script)); loaded = set(re.findall(r'load\("(luna_\w+)"', script))
check(stored <= loaded, "every saved key is loaded back" + (f": {sorted(stored - loaded)}" if stored - loaded else ""))
css = src[src.index("<style>"):src.index("</style>")]
standalone = set(re.findall(r"(?:^|[},])\s*\.([\w-]+)\s*(?=[{:,])", css, re.M))
nested = re.findall(r"\.([\w-]+)[^{},]*?\s\.([\w-]+)\b[^{]*\{", css)
ALLOWED = {("grownup", "summary"), ("pbar", "i")}
clash = sorted({f".{par} .{child}" for par, child in nested if child in standalone and child != par
                and not re.search(r"\.%s\.%s|\.%s\b" % (par, child, child + "-"), css) and (par, child) not in ALLOWED})
NESTED_OK = {".celebrate .box", ".pmodal .box", ".mana-btn .count", ".mini .cost", ".petcard .bar", ".petcard .cost", ".shopitem .emo",
             ".shop-head .big", ".bk .nm", ".stage h2", ".mcard .f", ".mcard .b", ".game-btn .ico", ".hole .popwho", ".celebrate .bigemo",
             # deliberate size/spacing tweaks of the same component inside a container:
             ".pmodal .petcard", ".pmodal .rowbtns", ".slot .sym", ".voiceset .rowbtns", ".yesno .ans"}
clash = [x for x in clash if x not in NESTED_OK]
# compound selectors like .tile.next pick up every rule of a standalone .next (e.g. white text on a white tile)
compound = re.findall(r"\.([\w-]+)\.([\w-]+)", css)
COMPOUND_OK = {("mana-btn", "blue"), ("mana-btn", "red"), ("mana-btn", "purple")}
cclash = sorted({f".{a_}.{b_}" for a_, b_ in compound if b_ in standalone and (a_, b_) not in COMPOUND_OK})
check(not cclash, "no state class reuses a standalone component name (e.g. .tile.next)" + (f": {cclash}" if cclash else ""))
check(not clash, "no CSS class is styled both on its own and as a nested class (style clashes)" + (f": {clash}" if clash else ""))
native = [l.strip()[:60] for l in script.splitlines() if re.search(r"\b(confirm|alert|prompt)\(", l) and "grown-ups only" not in l]
check(not native, "no browser dialogs in Luna's games (use ask())" + (f": {native}" if native else ""))
check(src.count("__CARDS__") == 1 and "__VERSION__" in src, "build placeholders present")
# Released CHANGELOG sections never change: `merge=union` once slid a lane's Unreleased line into 1.8.0 during a rebase.
import subprocess
def _git(*a): return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout
def _released(t): i = t.find("\n## ", t.find("## Unreleased") + 1); return t[i:] if i >= 0 else ""
try: _tag = _git("describe", "--tags", "--abbrev=0").strip(); _old = _released(_git("show", f"{_tag}:CHANGELOG.md"))
except Exception: _tag = None  # shallow CI checkout has no tags
if _tag:
    _cur = _released(open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read())
    check(_cur.endswith(_old), f"released CHANGELOG sections unchanged since {_tag} (new notes go under ## Unreleased)")
check(len(src) < 400_000, f"app.html source size {len(src)//1024} KB")
print("\n" + ("All checks passed." if not fails else f"{len(fails)} check(s) failed.")); sys.exit(1 if fails else 0)
