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

s = Stack(IMAGES_PER_DAY=5, STORIES_PER_DAY=5, VIDEOS_PER_DAY=3, REMIXES_PER_DAY=3)
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
    st, _, _ = call(u, "/image", {"kind": "bunny", "color": "P", "power": "sparkle", "words": ["fluffy", "rainbow", "sleepy"], "scene": "castle"})
    gen = json.loads([x for x in FakeAzure.seen if "/images/generations" in x[0]][-1][1])["prompt"]
    check(st == 200 and "fluffy" in gen and "rainbow" in gen and "castle" in gen, "magic words and scene shape the picture prompt")
    st, _, _ = call(u, "/image", {"kind": "bunny", "color": "P", "power": "sparkle", "words": ["scary"]}); check(st == 400, "rejects words outside the list")
    st, _, _ = call(u, "/image", {"kind": "bunny", "color": "P", "power": "sparkle", "words": ["fluffy", "tiny", "silly", "happy"]}); check(st == 400, "allows at most three words")
    st, _, _ = call(u, "/image", {"kind": "bunny", "color": "P", "power": "sparkle", "scene": "volcano"}); check(st == 400, "rejects unknown scenes")
    st, _, _ = call(u, "/image", {"kind": "kitty", "color": "U", "power": "heart"}); check(st == 429, "enforces the daily picture cap")
    st, h, b = call(u, "/tts", {"text": "Hi Luna! <b>sparkle</b>", "voice": "en-US-AnaNeural", "rate": 0.9})
    check(st == 200 and h["Content-Type"].startswith("audio/") and len(b) > 100, "tts returns audio")
    ssml = [x for x in FakeAzure.seen if "cognitive" in x[0]][-1][1].decode()
    check("<b>" not in ssml and "rate='-10%'" in ssml, "tts escapes text and maps rate")
    st, _, _ = call(u, "/tts", {"text": "hi", "voice": "en-US-SomeoneElse"}); check(st == 400, "rejects voices outside the allowlist")
    import base64 as _b64
    from stack import png as _png
    drawing = "data:image/png;base64," + _b64.b64encode(_png(48, 36, (120, 90, 220))).decode()
    sp = json.loads([x for x in FakeAzure.seen if "/chat/completions" in x[0]][-1][1])["messages"][1]["content"]
    check("that makes two mana" in sp and "numbers right" in sp, "story prompt asks for simple, correct mana counting")
    st, _, b = call(u, "/health"); check(json.loads(b).get("remix") is True, "health reports drawing repaint (remix) when images are on")
    st, _, b = call(u, "/remix", {"image": drawing, "subject": "creature", "kind": "unicorn", "color": "P", "power": "sparkle", "words": ["glittery"]})
    edit = [x for x in FakeAzure.seen if "/images/edits" in x[0]][-1][1]
    check(st == 200 and json.loads(b)["image"].startswith("data:image/png;base64,"), "remix repaints a creature drawing")
    check(b"child's drawing" in edit and b"glittery" in edit and b"unicorn" in edit, "remix prompt keeps her drawing and uses her choices")
    st, _, b = call(u, "/remix", {"image": drawing, "subject": "painting"})
    check(st == 200 and b"child's painting" in [x for x in FakeAzure.seen if "/images/edits" in x[0]][-1][1], "remix repaints an Art Studio painting")
    st, _, _ = call(u, "/remix", {"image": "https://example.com/x.png", "subject": "painting"}); check(st == 400, "remix needs an image data URL")
    st, _, _ = call(u, "/remix", {"image": drawing, "subject": "creature", "kind": "kraken", "color": "P", "power": "fly"}); check(st == 400, "remix validates the creature")
    st, _, _ = call(u, "/remix", {"image": drawing, "subject": "creature", "prompt": "anything I like"}); check(st == 400, "remix rejects free-form prompts")
    call(u, "/remix", {"image": drawing, "subject": "painting"})
    st, _, _ = call(u, "/remix", {"image": drawing, "subject": "painting"}); check(st == 429, "enforces the daily repaint cap")
    st, _, _ = call(u, "/story", {"characters": ["a" * 100]}, ); check(st == 400, "validates input")
    import base64, time
    from stack import png
    img = "data:image/png;base64," + base64.b64encode(png(32, 18)).decode()
    st, _, b = call(u, "/animate", {"image": img, "card": "Goldspan Dragon"}); job = json.loads(b)
    check(st == 200 and job["status"] == "running" and len(job["id"]) == 32, "animate starts a Veo job")
    sent = json.loads([x for x in FakeAzure.seen if "predictLongRunning" in x[0]][-1][1])
    check("gold coins" in sent["instances"][0]["prompt"] and sent["parameters"]["durationSeconds"] == 8, "Veo prompt comes from the card's motion template")
    st2, _, b2 = call(u, "/animate", {"image": img, "card": "Goldspan Dragon"})
    vp = [x[0] for x in FakeAzure.seen if ":predictLongRunning" in x[0]]
    check(bool(vp) and all("veo-3.1-lite-generate-preview" in x for x in vp), "magic movies default to Veo 3.1 Lite")
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
    # Rootha's shorts: private movies kept on the server (never in the app), listed and streamed behind the token
    st, _, b = call(u, "/health"); check(json.loads(b).get("shorts") is True, "health reports Rootha's shorts when there's a list")
    st, _, _ = call(u, "/shorts", token="wrong"); check(st == 401, "the shorts list needs the app token")
    st, _, _ = call(u, "/shorts/film.mp4", token="wrong"); check(st == 401, "a short needs the app token")
    st, h, b = call(u, "/shorts"); lst = json.loads(b).get("shorts") if st == 200 else None
    check(lst == [{"id": "film", "title": "Rootha's big movie", "poster": True}, {"id": "hello", "title": "Hello  b from /b  Rootha", "poster": False}],
          f"shorts list drops bad ids and missing movies, and cleans titles (got {st} {b[:200]!r})")
    st, h, b = call(u, "/shorts/film.mp4"); check(st == 200 and h["Content-Type"].startswith("video/") and len(b) > 1000, "a short streams")
    st, h, b = call(u, "/shorts/film.jpg"); check(st == 200 and h["Content-Type"].startswith("image/") and len(b) > 20, "a short's poster streams")
    for bad in ("/shorts/gone.mp4", "/shorts/..%2Fbad.mp4", "/shorts/index.json", "/shorts/film.exe", "/shorts/hello.jpg"):
        st, _, _ = call(u, bad); check(st == 404, f"no file outside the list: {bad} (got {st})")
    FakeAzure.edits_ok = False
    s2_drawing = "data:image/png;base64," + _b64.b64encode(_png(20, 20, (1, 2, 3))).decode()
finally:
    s.close()
def tree(pid):  # pid and every descendant, across all threads (node forks from worker threads)
    out, todo = {pid}, [pid]
    while todo:
        p = todo.pop()
        try: tids = os.listdir(f"/proc/{p}/task")
        except OSError: continue
        for t in tids:
            try: kids = map(int, open(f"/proc/{p}/task/{t}/children").read().split())
            except OSError: continue
            for k in kids:
                if k not in out: out.add(k); todo.append(k)
    return out
def alive(p):
    try: return open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError: return False
s = Stack(REMIXES_PER_DAY=5)
procs = tree(s.proc.pid)
try:
    u = s.url
    st, _, b = call(u, "/remix", {"image": s2_drawing, "subject": "painting"})
    check(st == 501, f"an image model that can't edit gives a clear 501 (got {st})")
    st, _, b = call(u, "/health"); check(json.loads(b).get("remix") is False, "after that, health turns repaint off so the app hides it")
    st, _, b = call(u, "/image", {"kind": "unicorn", "color": "P", "power": "fly"}); check(st == 200, "normal AI pictures still work")
finally:
    FakeAzure.edits_ok = True
    s.close()
left = sorted(p for p in procs | tree(s.proc.pid) if alive(p))
check(not left, f"closing the stack stops the whole server tree, not just its launcher ({len(procs)} procs, left: {left[:5]})")
tmps = getattr(s, "tmpdirs", [])
check(tmps and not any(os.path.exists(d) for d in tmps), f"closing the stack removes its temp dirs (got {tmps})")
print("\n" + (f"All {IMPL} server tests passed." if not fails else f"{len(fails)} server test(s) failed.")); sys.exit(1 if fails else 0)
