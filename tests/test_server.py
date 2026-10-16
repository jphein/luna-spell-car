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
IMPL = os.environ.get("SPELLCAR_IMPL", "python")
def check(ok, msg): print(("  ok   " if ok else "  FAIL ") + f"{IMPL}: " + msg); ok or fails.append(msg)

s = Stack(IMAGES_PER_DAY=4, STORIES_PER_DAY=5, VIDEOS_PER_DAY=3)
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
    st, _, b = call(u, "/story", {"characters": ["FILTERME"], "place": "sea"}); check(st == 422, f"maps Azure content filter to 422 (got {st} {b[:120]!r})")
    st, _, b = call(u, "/image", {"kind": "unicorn", "color": "P", "acc": "crown", "power": "fly"})
    check(st == 200 and json.loads(b)["image"].startswith("data:image/png;base64,"), "image returns a data URL")
    st, _, _ = call(u, "/image", {"kind": "kraken", "color": "P", "power": "fly"}); check(st == 400, "rejects unknown creature kinds")
    st, _, b = call(u, "/image", {"kind": "fox", "color": "R", "acc": "wand", "power": "zoom"}); check(st == 200, "accepts Star Shop creatures and accessories")
    st, _, _ = call(u, "/image", {"kind": "mermaid", "color": "U", "power": "heart"}); check(st == 200, "accepts the mermaid")
    st, _, _ = call(u, "/image", {"kind": "pegasus", "color": "P", "power": "fly"}); check(st == 200, "accepts the pegasus")
    st, _, _ = call(u, "/image", {"kind": "kitty", "color": "U", "power": "heart"}); check(st == 429, "enforces the daily picture cap")
    st, h, b = call(u, "/tts", {"text": "Hi Luna! <b>sparkle</b>", "voice": "en-US-AnaNeural", "rate": 0.9})
    check(st == 200 and h["Content-Type"].startswith("audio/") and len(b) > 100, "tts returns audio")
    ssml = [x for x in FakeAzure.seen if "cognitive" in x[0]][-1][1].decode()
    check("<b>" not in ssml and "rate='-10%'" in ssml, "tts escapes text and maps rate")
    st, _, _ = call(u, "/tts", {"text": "hi", "voice": "en-US-SomeoneElse"}); check(st == 400, "rejects voices outside the allowlist")
    st, _, _ = call(u, "/story", {"characters": ["a" * 100]}, ); check(st == 400, "validates input")
    import base64, time
    from stack import png
    img = "data:image/png;base64," + base64.b64encode(png(32, 18)).decode()
    st, _, b = call(u, "/animate", {"image": img, "card": "Goldspan Dragon"}); job = json.loads(b)
    check(st == 200 and job["status"] == "running" and len(job["id"]) == 32, "animate starts a Veo job")
    sent = json.loads([x for x in FakeAzure.seen if "predictLongRunning" in x[0]][-1][1])
    check("gold coins" in sent["instances"][0]["prompt"] and sent["parameters"]["durationSeconds"] == 8, "Veo prompt comes from the card's motion template")
    st2, _, b2 = call(u, "/animate", {"image": img, "card": "Goldspan Dragon"})
    check(json.loads(b2)["id"] == job["id"] and len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]]) == 1, "the same picture never starts a second paid job")
    for _ in range(40):
        st, _, b = call(u, f"/animate/{job['id']}")
        if json.loads(b)["status"] != "running": break
        time.sleep(0.25)
    check(json.loads(b)["status"] == "done", "background poller finishes the clip")
    st, h, b = call(u, f"/video/{job['id']}.mp4"); check(st == 200 and h["Content-Type"].startswith("video/") and len(b) > 1000, "finished clip downloads")
    st, _, _ = call(u, f"/video/{job['id']}.mp4", token="nope"); check(st == 401, "clips need the app token")
    st, _, _ = call(u, "/animate", {"image": img, "card": "Some Other Card"}); check(st == 400, "rejects unknown cards")
    st, _, b = call(u, "/animate", {"painting": True, "ref": "painting:abc123:x9", "peek": True})
    check(st == 200 and json.loads(b)["status"] == "none", "accepts an Art Studio painting for a movie")
    st, _, _ = call(u, "/animate", {"painting": "yes", "ref": "painting:abc123:x9", "peek": True}); check(st == 400, "painting flag must be true")
    n0 = len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]])
    st, _, b = call(u, "/animate", {"card": "Faerie Mastermind", "ref": "card:Faerie Mastermind", "peek": True})
    check(st == 200 and json.loads(b)["status"] == "none", "peek reports a missing clip without starting a job")
    call(u, "/animate", {"image": img, "card": "Faerie Mastermind", "ref": "card:Faerie Mastermind"})
    other = "data:image/png;base64," + base64.b64encode(png(40, 22, (10, 200, 90))).decode()
    st, _, b = call(u, "/animate", {"image": other, "card": "Faerie Mastermind", "ref": "card:Faerie Mastermind"})
    check(json.loads(b)["status"] in ("running", "done") and len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]]) == n0 + 1,
          "a second device's slightly different image reuses the same clip by ref")
    st, _, _ = call(u, "/animate", {"image": "https://example.com/x.png", "kind": "unicorn"}); check(st == 400, "rejects image URLs (data URLs only)")
    if IMPL == "worker":
        st, _, b = call(u, "/animate", {"image": img, "kind": "panda", "ref": "pet:cron-test"}); jid = json.loads(b)["id"]
        for _ in range(3): urllib.request.urlopen(u + "/__scheduled?cron=*+*+*+*+*", timeout=10).read(); time.sleep(0.5)
        st, _, b = call(u, f"/video/{jid}.mp4")
        check(st == 200 and len(b) > 1000, "cron trigger finishes clips with no device polling")
finally:
    s.close()
print("\n" + (f"All {IMPL} server tests passed." if not fails else f"{len(fails)} server test(s) failed.")); sys.exit(1 if fails else 0)
