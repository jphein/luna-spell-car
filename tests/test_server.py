#!/usr/bin/env python3
"""Spell Car server tests against a fake Azure."""
import json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack import Stack, TOKEN, FakeAzure

def call(url, path, body=None, token=TOKEN, method=None):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None, method=method or ("POST" if body is not None else "GET"),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e: return e.code, e.headers, e.read()

fails = []
def check(ok, msg): print(("  ok   " if ok else "  FAIL ") + "server: " + msg); ok or fails.append(msg)

s = Stack(IMAGES_PER_DAY=2, STORIES_PER_DAY=5)
try:
    u = s.url
    st, _, _ = call(u, "/health", token="wrong"); check(st == 401, "rejects a bad token")
    st, _, b = call(u, "/health"); caps = json.loads(b); check(st == 200 and caps["story"] and caps["image"] and caps["tts"], "health reports story/image/tts")
    st, h, _ = call(u, "/story", method="OPTIONS"); check(st == 204 and h["Access-Control-Allow-Origin"] == "*", "CORS preflight works")
    st, _, b = call(u, "/story", {"characters": ["Princess Starmane, a purple unicorn"], "place": "castle"})
    check(st == 200 and json.loads(b)["text"].startswith("The Sparkle Parade"), "story works (and survives a model that rejects temperature)")
    prompt = json.loads([x for x in FakeAzure.seen if b"chat" in x[0].encode()][-1][1])["messages"][1]["content"]
    check("Princess Starmane" in prompt and "sparkly castle" in prompt, "server builds the prompt from structured input")
    st, _, _ = call(u, "/story", {"characters": ["x"], "place": "volcano lair"}); check(st == 400, "rejects unknown places")
    st, _, _ = call(u, "/story", {"prompt": "write anything"}); check(st == 400, "rejects free-form prompts")
    st, _, b = call(u, "/story", {"characters": ["FILTERME"], "place": "sea"}); check(st == 422, "maps Azure content filter to 422")
    st, _, b = call(u, "/image", {"kind": "unicorn", "color": "P", "acc": "crown", "power": "fly"})
    check(st == 200 and json.loads(b)["image"].startswith("data:image/png;base64,"), "image returns a data URL")
    st, _, _ = call(u, "/image", {"kind": "kraken", "color": "P", "power": "fly"}); check(st == 400, "rejects unknown creature kinds")
    call(u, "/image", {"kind": "kitty", "color": "U", "power": "heart"})
    st, _, _ = call(u, "/image", {"kind": "kitty", "color": "U", "power": "heart"}); check(st == 429, "enforces the daily picture cap")
    st, h, b = call(u, "/tts", {"text": "Hi Luna! <b>sparkle</b>", "voice": "en-US-AnaNeural", "rate": 0.9})
    check(st == 200 and h["Content-Type"].startswith("audio/") and len(b) > 100, "tts returns audio")
    ssml = [x for x in FakeAzure.seen if "cognitive" in x[0]][-1][1].decode()
    check("<b>" not in ssml and "rate='-10%'" in ssml, "tts escapes text and maps rate")
    st, _, _ = call(u, "/tts", {"text": "hi", "voice": "en-US-SomeoneElse"}); check(st == 400, "rejects voices outside the allowlist")
    st, _, _ = call(u, "/story", {"characters": ["a" * 100]}, ); check(st == 400, "validates input")
finally:
    s.close()
print("\n" + ("All server tests passed." if not fails else f"{len(fails)} server test(s) failed.")); sys.exit(1 if fails else 0)
