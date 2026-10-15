#!/usr/bin/env python3
"""Build Luna's Spell Car.
  dist/web/index.html          single-file page (Google Fonts + CDN jsPDF) for claude.ai or any web host
  android/assets/index.html    offline Android build (bundled font, local jsPDF, native TTS shim)
"""
import json, os, re, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "web")
src = open(os.path.join(W, "app.html"), encoding="utf-8").read()
cards = json.load(open(os.path.join(W, "cards.json"), encoding="utf-8"))
version = open(os.path.join(ROOT, "VERSION")).read().strip()
src = src.replace("__CARDS__", json.dumps(cards)).replace("__VERSION__", version)

web = src.replace("<!--SHIM-->", "")
os.makedirs(os.path.join(ROOT, "dist", "web"), exist_ok=True)
open(os.path.join(ROOT, "dist", "web", "index.html"), "w", encoding="utf-8").write(web)

fonts = """<style>@font-face{font-family:"Fredoka";src:url("fonts/Fredoka-Variable.ttf") format("truetype");font-weight:300 700;font-display:block}</style>"""
android = re.sub(r"<!--FONTS-->.*?<!--/FONTS-->", fonts, src, flags=re.S)
shim = open(os.path.join(W, "tts-shim.js"), encoding="utf-8").read()
android = android.replace("<!--SHIM-->", "<script>\n" + shim + "\n</script>")
# Optional: preconnect the tablet build to a Spell Car server (address + narrow app token only; never Azure/Google keys).
pre_url, pre_tok = os.environ.get("SPELLCAR_URL", "").strip(), os.environ.get("SPELLCAR_APP_TOKEN", "").strip()
if pre_url and pre_tok:
    android = android.replace("<script>\nconst CARDS", "<script>window.__SPELLCAR_DEFAULT = " + json.dumps({"url": pre_url, "token": pre_tok}) + ";</script>\n<script>\nconst CARDS", 1)
    print("android build preconnected to", pre_url)
A = os.path.join(ROOT, "android", "assets")
shutil.rmtree(A, ignore_errors=True)
os.makedirs(os.path.join(A, "fonts")); os.makedirs(os.path.join(A, "vendor"))
open(os.path.join(A, "index.html"), "w", encoding="utf-8").write(android)
shutil.copy(os.path.join(W, "fonts", "Fredoka-Variable.ttf"), os.path.join(A, "fonts"))
shutil.copy(os.path.join(W, "fonts", "OFL.txt"), os.path.join(A, "fonts"))  # the font license travels with the font
shutil.copy(os.path.join(W, "vendor", "jspdf.umd.min.js"), os.path.join(A, "vendor"))
print(f"built v{version}: dist/web/index.html and android/assets/")
