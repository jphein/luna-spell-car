#!/usr/bin/env python3
"""Browser smoke tests: drives every screen in Chromium, in both the web build (fake claude.ai
runtime) and the Android build (fake AndroidBridge), and fails on any assertion or console error.
Run: make test      Screenshots of failures land in build/test-shots/."""
import asyncio, json, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack import Stack, TOKEN, FakeAzure
from playwright.async_api import async_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = "file://" + os.path.join(ROOT, "dist", "web", "index.html")
AND = "file://" + os.path.join(ROOT, "android", "assets", "index.html")
SHOTS = os.path.join(ROOT, "build", "test-shots"); os.makedirs(SHOTS, exist_ok=True)

FAKE_CLAUDE = """
window.__saved = [];
const story = "The Purple Parade\\n\\nLuna and her friend walked to the castle. It was sunny.\\n\\nLuna counted one blue and one red mana. Sparkle! The end.";
window.claude = { use: async n => n === 'sample' ? (async (prompt, o) => { window.__prompt = prompt; o && o.onText && o.onText({ text: story.slice(0, 30), delta: '' }); return { text: story, truncated: false }; })
  : n === 'downloads' ? { save: async ({ filename, data }) => { window.__saved.push({ filename, size: data.size || data.length }); return { status: 'saved' }; } } : null };
"""
FAKE_ANDROID = """
window.__calls = [];
window.AndroidBridge = {
  ready: () => true,
  voices: () => JSON.stringify([{ name: 'en-us-a', lang: 'en-US', network: false }, { name: 'en-gb-b', lang: 'en-GB', network: false }]),
  speak: (t, id, r, p, v) => { window.__calls.push({ t, id, v }); setTimeout(() => window.__ttsEvent(id, 'start'), 5); setTimeout(() => window.__ttsEvent(id, 'end'), 30); },
  stop: () => window.__calls.push('STOP'), openTtsSettings: () => window.__calls.push('SETTINGS'),
  saveFile: (n, b, m) => { window.__calls.push({ saved: n, mime: m }); return 'ok'; }
};
"""
SEED_PETS = """localStorage.setItem('luna_pets', JSON.stringify([
 {id:'p1',kind:'unicorn',color:'P',p:4,t:2,power:'sparkle',name:'Princess Starmane',acc:'crown'},
 {id:'p2',kind:'kitty',color:'U',p:2,t:3,power:'fly',name:'Captain Whiskers'}]));"""

results = []
def test(fn):
    results.append(fn); return fn

async def home(pg): await pg.evaluate("go('home', true)")

@test
async def home_renders(pg, mode):
    tiles = await pg.locator(".game-btn:not(.hidden)").count()
    assert tiles >= (11 if mode == "web" else 10), f"only {tiles} tiles"
    assert await pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "home scrolls sideways"

@test
async def window_magic(pg, mode):
    await pg.click("[data-go=window]")
    for b in ["#addBlue", "#addRed", "#addPurple"]: await pg.click(b)
    assert await pg.evaluate("pool.U === 2 && pool.R === 2"), "mana pool wrong"
    await pg.locator(".mini.ready").first.click(force=True)
    assert await pg.is_visible("#celebrate"), "no celebration after cast"
    await pg.click("#celOk"); await home(pg)

@test
async def make_creature_with_drawing(pg, mode):
    n0 = await pg.evaluate("pets.length")
    await pg.click("[data-go=maker]"); await pg.click("#kindRow .pick >> nth=1"); await pg.click("[data-st=p][data-d='1']")
    await pg.click("#artDraw"); box = await pg.locator("#pCanvas").bounding_box()
    await pg.mouse.move(box["x"] + 30, box["y"] + 30); await pg.mouse.down(); await pg.mouse.move(box["x"] + 200, box["y"] + 120, steps=8); await pg.mouse.up()
    await pg.click("#pDone"); assert await pg.evaluate("!!draft.art"), "drawing not attached"
    await pg.click("#savePet"); await pg.click("#celOk")
    assert await pg.evaluate("pets.length") == n0 + 1, "creature not saved"
    assert await pg.evaluate("pets[pets.length-1].art.startsWith('data:image/jpeg')"), "art not saved"
    await home(pg)

@test
async def count_the_mana(pg, mode):
    await pg.click("[data-go=count]")
    total = await pg.evaluate("total(cCur)")
    for b in await pg.query_selector_all("#cCost button"): await b.click()
    assert await pg.inner_text("#cRun") == str(total), "tap-to-count total wrong"
    await pg.locator("#cAns .ans", has_text=str(total)).first.click()
    assert await pg.is_visible("#cNext"), "right answer not accepted"
    await home(pg)

@test
async def who_wins(pg, mode):
    await pg.click("[data-go=battle]")
    truth = await pg.evaluate("bAtk.p >= bDef.t")
    await pg.click(f"#battle .yesno .ans[data-yes='{1 if truth else 0}']")
    assert await pg.is_visible("#bNext"), "correct battle answer not accepted"
    await home(pg)

@test
async def memory_match(pg, mode):
    await pg.click("[data-go=memory]")
    order = await pg.evaluate("mem.map(m => m.k)")
    seen = {}
    for i, k in enumerate(order): seen.setdefault(k, []).append(i)
    for a, b in seen.values():
        await pg.click(f"#memGrid .mcard >> nth={a}"); await pg.click(f"#memGrid .mcard >> nth={b}"); await pg.wait_for_timeout(520)
    assert await pg.evaluate("mem.every(m => m.done)"), "pairs not all matched"
    await pg.wait_for_timeout(600); await pg.click("#celOk"); await home(pg)

@test
async def mana_bubbles(pg, mode):
    await pg.click("[data-go=bubbles]")
    for _ in range(80):
        if await pg.evaluate("bb.slots.every(s => s.full)"): break
        await pg.evaluate("""(() => { const need = bb.slots.filter(s => !s.full);
          const b = [...document.querySelectorAll('.bub:not(.popped)')].find(x => need.some(s => s.k === 'N' || x.classList.contains(s.k)));
          if (b) b.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); })()""")
        await pg.wait_for_timeout(200)
    assert await pg.evaluate("bb.slots.every(s => s.full)"), "bubble cost never filled"
    await pg.click("#celOk"); await home(pg)
    assert await pg.evaluate("bb.timer === null"), "bubble timer still running after leaving"

@test
async def rootha_says(pg, mode):
    await pg.click("[data-go=says]"); await pg.click("#saysPlay"); await pg.wait_for_timeout(3500)
    txt = await pg.inner_text("#saysCmd")
    assert "Listen to Rootha" not in txt, "Rootha Says never advanced"
    await home(pg); assert await pg.evaluate("!saysOn"), "Rootha Says kept running"

@test
async def story_time(pg, mode):
    if mode != "web": return
    await pg.click("[data-go=story]")
    assert await pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "story picker scrolls sideways"
    await pg.click("#storyGo"); await pg.wait_for_timeout(500)
    assert await pg.inner_text("#storyTitle") == "The Purple Parade", "story not shown"
    assert "Characters:" in await pg.evaluate("window.__prompt"), "story prompt missing characters"
    await home(pg)

@test
async def art_studio(pg, mode):
    await pg.click("[data-go=studio]"); n0 = await pg.evaluate("drawings.length")
    await pg.click("#stNew"); box = await pg.locator("#pCanvas").bounding_box()
    await pg.mouse.move(box["x"] + 50, box["y"] + 50); await pg.mouse.down(); await pg.mouse.move(box["x"] + 150, box["y"] + 150, steps=6); await pg.mouse.up()
    await pg.click("#pDone"); await pg.click("#celOk")
    assert await pg.evaluate("drawings.length") == n0 + 1, "drawing not saved to gallery"
    assert await pg.locator("#stGallery .bk").count() == n0 + 1, "gallery not updated"
    await home(pg)

@test
async def game_night(pg, mode):
    await pg.click("[data-go=night]")
    if await pg.is_visible("#ntStart"): await pg.click("#ntStart")
    l0 = await pg.evaluate("night.players[0].life")
    await pg.click("#ntBoard .nt-p >> nth=0 >> .tap >> nth=0"); await pg.click("#ntBoard .nt-p >> nth=0 >> .five button >> nth=1")
    assert await pg.evaluate("night.players[0].life") == l0 + 4, "life math wrong"
    await pg.click("[data-roll='20']"); assert "🎲" in await pg.inner_text("#ntRoll")
    await home(pg)

@test
async def spellbook_print_and_backup(pg, mode):
    await pg.click("[data-go=book]"); await pg.wait_for_timeout(200)
    await pg.click("#printBtn"); await pg.wait_for_timeout(2500)
    await pg.click("#bkSave"); await pg.wait_for_timeout(400)
    if mode == "web":
        names = [s["filename"] for s in await pg.evaluate("window.__saved")]
    else:
        names = [c["saved"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "saved" in c]
    assert any(n.endswith(".pdf") for n in names), f"no PDF saved ({names})"
    assert any(n.endswith(".json") for n in names), f"no backup saved ({names})"
    await home(pg)

@test
async def back_button(pg, mode):
    await pg.click("[data-go=memory]")
    assert await pg.evaluate("window.__back()") == "stay" and await pg.evaluate("current") == "home"
    assert await pg.evaluate("window.__back()") == "exit"

@test
async def android_tts_bridge(pg, mode):
    if mode != "android": return
    await pg.evaluate("window.__ttsReady && window.__ttsReady()")
    await pg.click(".grownup summary"); await pg.select_option("#voiceSel", "en-gb-b"); await pg.click("#voiceTest")
    spoken = [c for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "t" in c]
    assert spoken and spoken[-1]["v"] == "en-gb-b", "voice choice not passed to native TTS"
    assert await pg.evaluate("document.fonts.check('700 20px Fredoka')"), "bundled font not loaded"

@test
async def bubbles_speed(pg, mode):
    await pg.click("[data-go=bubbles]")
    await pg.click("[data-bspeed=slow]")
    assert await pg.evaluate("load('luna_bubspeed', 'normal')") == "slow", "speed not saved"
    await pg.wait_for_timeout(1300)
    ds = await pg.evaluate("[...document.querySelectorAll('.bub')].map(b => parseFloat(b.style.getPropertyValue('--d')))")
    assert ds and min(ds) >= 9, f"slow bubbles too fast: {ds}"
    await pg.click("[data-bspeed=normal]"); await home(pg)

@test
async def quiet_car_mode(pg, mode):
    await pg.evaluate("document.querySelector('.grownup').open = true")
    await pg.click("[data-quiet='1']")
    n0 = await pg.evaluate("tonesPlayed"); await pg.evaluate("chime(); boop(); plink('U')")
    assert await pg.evaluate("tonesPlayed") == n0, "chimes played in quiet car mode"
    await pg.click("[data-quiet='0']"); await pg.evaluate("chime()")
    assert await pg.evaluate("tonesPlayed") > n0, "chimes not restored"

@test
async def game_night_turns(pg, mode):
    await pg.click("[data-go=night]")
    if await pg.is_visible("#ntStart"): await pg.click("#ntStart")
    await pg.click("#ntNextTurn"); t1 = await pg.evaluate("night.turn")
    name = await pg.evaluate("night.players[night.turn].name")
    assert name in await pg.inner_text("#ntBanner"), "banner doesn't name the player"
    w = await pg.evaluate("[document.getElementById('ntWho').offsetWidth, document.getElementById('ntBanner').offsetWidth]")
    assert w[0] > w[1] * 0.8, f"turn banner text is squashed ({w})"
    assert await pg.locator(".nt-p.turn").count() == 1, "current player not highlighted"
    s0 = await pg.evaluate("night.step"); await pg.click("#ntNextStep")
    assert await pg.evaluate("night.step") == s0 + 1, "step didn't advance"
    await pg.click("#ntNextTurn")
    assert await pg.evaluate("night.turn") != t1 and await pg.evaluate("night.step") == 0, "turn didn't pass"
    await home(pg)

STACK = None

@test
async def cloud_connect(pg, mode):
    if mode != "android": return
    await pg.evaluate("document.querySelector('.grownup').open = true")
    assert await pg.is_visible("#cloudSet"), "server settings hidden on Android"
    await pg.fill("#cloudUrl", STACK.url); await pg.fill("#cloudToken", "wrong-token"); await pg.click("#cloudConnect")
    await pg.wait_for_function("document.getElementById('cloudStatus').textContent.includes('token')", timeout=5000)
    await pg.fill("#cloudToken", TOKEN); await pg.click("#cloudConnect")
    await pg.wait_for_function("document.getElementById('cloudStatus').textContent.includes('Connected')", timeout=5000)
    assert await pg.is_visible("#storyTile"), "Story Time tile not shown after connecting"

@test
async def cloud_story(pg, mode):
    if mode != "android": return
    await pg.click("[data-go=story]"); await pg.click("#storyGo")
    await pg.wait_for_function("document.getElementById('storyTitle').textContent === 'The Sparkle Parade'", timeout=8000)
    await home(pg)

@test
async def cloud_ai_picture(pg, mode):
    if mode != "android": return
    await pg.click("[data-go=maker]"); assert await pg.is_visible("#artAI"), "AI picture button missing"
    await pg.click("#artAI"); await pg.wait_for_function("draft.artBy === 'ai' && draft.art.startsWith('data:image/jpeg')", timeout=8000)
    await home(pg)

@test
async def cloud_voice(pg, mode):
    if mode != "android": return
    n0 = len([x for x in FakeAzure.seen if "cognitive" in x[0]])
    await pg.evaluate("document.querySelector('.grownup').open = true")
    await pg.click("[data-cv=all]"); await pg.evaluate("say('Hello from the cloud')"); await pg.wait_for_timeout(1500)
    assert len([x for x in FakeAzure.seen if "cognitive" in x[0]]) > n0, "cloud voice never requested"
    await pg.click("[data-cv=off]"); calls0 = await pg.evaluate("window.__calls.length")
    await pg.evaluate("say('Back to the tablet voice')"); await pg.wait_for_timeout(200)
    assert await pg.evaluate(f"window.__calls.slice({calls0}).some(c => c && c.t === 'Back to the tablet voice')"), "tablet voice not used when cloud voice is off"

@test
async def magic_movies(pg, mode):
    if mode != "android": return
    await pg.evaluate("clipPollMs = 300")
    starts0 = len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]])
    await pg.evaluate("openViewer(CARDS.find(c => c.name === 'Goldspan Dragon'))")
    assert await pg.is_visible("#vMake"), "Make it move button missing"
    await pg.click("#vMake")
    await pg.wait_for_function("clipKeys.has('card:Goldspan Dragon')", timeout=15000)
    sent = json.loads([x for x in FakeAzure.seen if "predictLongRunning" in x[0]][-1][1])
    assert sent["instances"][0]["image"]["inlineData"]["mimeType"] == "image/jpeg", "frame not sent as JPEG"
    await pg.wait_for_selector("#vMedia video", timeout=5000)
    await pg.wait_for_function("document.querySelector('#vMedia video').currentTime > 0", timeout=5000)
    assert await pg.evaluate("document.querySelector('#vMedia video').playbackRate") == 0.8, "clip not stretched to 10s"
    await pg.click("#vClose")
    # casting a card that has a movie plays it in the celebration
    await pg.evaluate("showCelebrate({ img: CARDS[0].img, clip: 'card:Goldspan Dragon', title: 'You cast Goldspan Dragon!' })")
    await pg.wait_for_selector("#celMedia video", timeout=5000); await pg.click("#celOk")
    # a fresh device (cleared clip store) gets the clip back without a new paid job
    await pg.evaluate("clipDB.del('card:Goldspan Dragon').then(() => clipKeys.delete('card:Goldspan Dragon'))")
    got = await pg.evaluate("syncClips()")
    assert got >= 1 and await pg.evaluate("clipKeys.has('card:Goldspan Dragon')"), "sync didn't restore the clip"
    assert len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]]) == starts0 + 1, "sync started a new paid job"
    await home(pg)

async def run_mode(browser, mode):
    ctx = await browser.new_context(viewport={"width": 400, "height": 860}, has_touch=True)
    await ctx.add_init_script((FAKE_CLAUDE if mode == "web" else FAKE_ANDROID) + "if(!localStorage.getItem('luna_pets')){" + SEED_PETS + "}")
    pg = await ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "fonts.g" not in m.text and "ERR_" not in m.text and not m.text.startswith("Failed to load resource") else None)
    await pg.goto(WEB if mode == "web" else AND); await pg.wait_for_timeout(700)
    fails = 0
    for fn in results:
        name = f"{mode}:{fn.__name__}"
        try:
            await fn(pg, mode)
            if errors: raise AssertionError("console errors: " + " | ".join(errors[:3]))
            print(f"  ok   {name}")
        except Exception as e:
            fails += 1; print(f"  FAIL {name}: {e}")
            await pg.screenshot(path=os.path.join(SHOTS, name.replace(":", "_") + ".png"), full_page=True)
            if not isinstance(e, AssertionError): traceback.print_exc()
            errors.clear()
            try: await pg.evaluate("document.querySelectorAll('.celebrate,.pmodal,.paint').forEach(x => x.classList.add('hidden')); go('home', true)")
            except Exception: pass
    await ctx.close(); return fails

async def main():
    global STACK
    STACK = Stack()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        fails = await run_mode(b, "web") + await run_mode(b, "android")
        await b.close()
    STACK.close()
    print("\n" + ("All smoke tests passed." if not fails else f"{fails} smoke test(s) failed. Screenshots in build/test-shots/"))
    sys.exit(1 if fails else 0)

asyncio.run(main())
