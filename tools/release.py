#!/usr/bin/env python3
"""Bump VERSION (patch|minor|major) and move CHANGELOG's Unreleased notes under the new version."""
import datetime, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
part = (sys.argv[1] if len(sys.argv) > 1 else "patch").lower()
vf = os.path.join(ROOT, "VERSION"); a, b, c = map(int, open(vf).read().strip().split("."))
a, b, c = {"major": (a + 1, 0, 0), "minor": (a, b + 1, 0), "patch": (a, b, c + 1)}[part]
new = f"{a}.{b}.{c}"
cl = os.path.join(ROOT, "CHANGELOG.md"); text = open(cl, encoding="utf-8").read()
m = re.search(r"## Unreleased\n(.*?)(?=\n## |\Z)", text, re.S)
notes = m.group(1).strip() if m else ""
if not notes: sys.exit("CHANGELOG.md has no notes under '## Unreleased'. Add them first.")
text = text.replace(m.group(0), f"## Unreleased\n\n## {new} ({datetime.date.today()})\n{notes}\n", 1)
open(cl, "w", encoding="utf-8").write(text); open(vf, "w").write(new + "\n")
print(f"Version {new}")
