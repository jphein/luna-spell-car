#!/usr/bin/env python3
"""Check a deployed Spell Car server end to end with real Azure / Google calls. Never prints secrets.

  python3 tools/live_check.py --url https://spellcar.<you>.workers.dev            # token read from worker/.secrets
  python3 tools/live_check.py --url ... --video                                    # also makes ONE real Veo clip (~$0.80)

Outputs go to build/live/ (story.txt, picture.*, voice.mp3, clip.mp4) so a human can look and listen.
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "live"); os.makedirs(OUT, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--url", default=os.environ.get("SPELLCAR_URL", ""))
ap.add_argument("--token", default=os.environ.get("SPELLCAR_APP_TOKEN", ""))
ap.add_argument("--video", action="store_true", help="also generate one real Veo clip (costs money)")
a = ap.parse_args()
if not a.token:
    sec = os.path.join(ROOT, "worker", ".secrets")
    if os.path.exists(sec):
        a.token = next((l.split("=", 1)[1].strip() for l in open(sec) if l.startswith("SPELLCAR_TOKEN=")), "")
if not a.url or not a.token: sys.exit("Need --url and a token (--token, SPELLCAR_APP_TOKEN, or worker/.secrets).")
U = a.url.rstrip("/")

def call(path, body=None, timeout=120):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {a.token}", "Content-Type": "application/json", "User-Agent": "spellcar-live-check"},
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e: return e.code, e.headers.get("Content-Type", ""), e.read()

results = []
def report(name, ok, detail=""):
    results.append(ok); print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}", flush=True)

st, _, b = call("/health")
if st != 200: report("health", False, f"HTTP {st} {b[:200]!r}"); sys.exit(1)
caps = json.loads(b); report("health", True, "enabled: " + ", ".join(k for k in ("story", "image", "tts", "video") if caps.get(k)) or "nothing")

if caps.get("story"):
    st, _, b = call("/story", {"characters": ["Princess Starmane, a purple unicorn with sparkles"], "place": "castle"})
    ok = st == 200 and len(json.loads(b).get("text", "")) > 80
    if ok: open(os.path.join(OUT, "story.txt"), "w").write(json.loads(b)["text"])
    report("story (Azure OpenAI chat)", ok, json.loads(b)["text"].splitlines()[0] if ok else f"HTTP {st} {b[:300]!r}")
if caps.get("image"):
    st, _, b = call("/image", {"kind": "unicorn", "color": "P", "acc": "crown", "power": "sparkle"}, timeout=180)
    ok = st == 200 and json.loads(b).get("image", "").startswith("data:image/")
    if ok:
        head, data = json.loads(b)["image"].split(",", 1); ext = head.split("/")[1].split(";")[0]
        open(os.path.join(OUT, f"picture.{ext}"), "wb").write(base64.b64decode(data))
    report("AI picture (Azure OpenAI image)", ok, f"saved build/live/picture.*" if ok else f"HTTP {st} {b[:300]!r}")
if caps.get("tts"):
    st, ct, b = call("/tts", {"text": "Hi Luna! Sparkle sparkle! Let's cast a spell.", "voice": "en-US-AnaNeural", "rate": 0.95})
    ok = st == 200 and ct.startswith("audio/") and len(b) > 2000
    if ok: open(os.path.join(OUT, "voice.mp3"), "wb").write(b)
    report("voice (Azure Speech, Ana)", ok, "saved build/live/voice.mp3" if ok else f"HTTP {st} {b[:300]!r}")
if caps.get("video") and a.video:
    card = next(c for c in json.load(open(os.path.join(ROOT, "web", "cards.json"))) if c["full"] == "Faerie Mastermind")
    st, _, b = call("/animate", {"image": card["img"], "card": "Faerie Mastermind", "ref": "card:Faerie Mastermind"})
    if st != 200: report("magic movie (Google Veo)", False, f"HTTP {st} {b[:300]!r}")
    else:
        job = json.loads(b); print(f"        Veo job {job['id']} {job['status']}; checking every 15 s (can take a few minutes)...", flush=True)
        for _ in range(48):
            if job["status"] != "running": break
            time.sleep(15); st, _, b = call(f"/animate/{job['id']}"); job = json.loads(b)
        if job["status"] == "done":
            st, ct, b = call(f"/video/{job['id']}.mp4", timeout=180)
            ok = st == 200 and len(b) > 1000
            if ok: open(os.path.join(OUT, "clip.mp4"), "wb").write(b)
            report("magic movie (Google Veo)", ok, f"saved build/live/clip.mp4 ({len(b)//1024} KB); the app will reuse it" if ok else f"HTTP {st}")
        else: report("magic movie (Google Veo)", False, f"status {job['status']} {job.get('error', '')}")
elif caps.get("video"): print("  skip  magic movie (pass --video to make one real clip, about $0.80)")

print("\nAll live checks passed." if all(results) else "\nSome live checks FAILED (details above)."); sys.exit(0 if all(results) else 1)
