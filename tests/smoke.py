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
  : n === 'downloads' ? { save: async ({ filename, data }) => { window.__saved.push({ filename, size: data.size || data.length, text: filename.endsWith('.json') ? await data.text() : null }); return { status: 'saved' }; } } : null };
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
ONLY = set(filter(None, os.environ.get("SMOKE_ONLY", "").split(",")))  # e.g. SMOKE_ONLY=home_renders,art_studio
def test(fn):
    results.append(fn); return fn

async def dismiss(pg): await pg.evaluate("celebQueue.length = 0; ['celebrate','viewer','petModal','paint'].forEach(i => document.getElementById(i).classList.add('hidden'))")
async def home(pg):
    # Random events (a natural 20 in Game Night, a surprise sticker) can open a celebration; clear it between tests.
    await dismiss(pg); await pg.evaluate("go('home', true)")

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
async def coloring_pages(pg, mode):
    # Art Studio coloring pages: pick a line drawing, 🪣 fill stops at the lines, and the saved painting keeps the lines.
    await pg.click("[data-go=studio]"); n0 = await pg.evaluate("drawings.length")
    await pg.click("#stColor"); pages = pg.locator("#stPages button")
    assert await pages.count() >= 6, "not enough coloring pages"
    bb = await pages.first.bounding_box(); assert bb["height"] >= 52 and bb["width"] >= 52, f"page button too small ({bb})"
    await pages.nth(0).click()
    assert await pg.is_visible("#paint") and await pg.is_visible("#pLines"), "coloring page didn't open with its lines"
    await pg.click("[data-tool=fill]"); await pg.click("#pColors .sw >> nth=4")
    box = await pg.locator("#pCanvas").bounding_box()
    await pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] * 400 / 720)
    px_ = "(x, y) => Array.from(pc.getContext('2d').getImageData(x, y, 1, 1).data)"
    assert await pg.evaluate(f"({px_})(480, 400)") == [239, 90, 49, 255], "fill didn't color the shape"
    assert (await pg.evaluate(f"({px_})(20, 20)"))[3] == 0, "fill leaked past the lines"
    await pg.click("#pDone"); await pg.click("#celOk")
    assert await pg.evaluate("drawings.length") == n0 + 1, "colored page not saved"
    dark = await pg.evaluate("""new Promise(r => { const im = new Image(); im.onload = () => { const c = document.createElement('canvas'); c.width = 640; c.height = 480;
        const x = c.getContext('2d'); x.drawImage(im, 0, 0); const d = x.getImageData(320, 267, 1, 200).data; let n = 0;
        for (let i = 0; i < d.length; i += 4) if (d[i] < 90 && d[i + 1] < 90 && d[i + 2] < 90) n++; r(n); }; im.src = drawings[drawings.length - 1].img; })""")
    assert dark > 0, "saved painting lost the coloring page lines"
    await pg.click("#stNew")
    assert not await pg.is_visible("#pLines"), "lines stayed on a blank painting"
    await pg.click("#pCancel"); await home(pg)

@test
async def creature_coloring(pg, mode):
    # A creature she drew becomes a coloring page: its edges turn into lines the 🪣 fill stops at.
    await pg.evaluate("""(() => { const c = document.createElement('canvas'); c.width = 480; c.height = 360; const x = c.getContext('2d');
        x.fillStyle = '#fff'; x.fillRect(0, 0, 480, 360); x.fillStyle = '#7C4DFF'; x.beginPath(); x.arc(240, 180, 120, 0, 7); x.fill();
        const n = document.createElement('canvas'); n.width = 480; n.height = 360; const nx = n.getContext('2d');
        for (let i = 0; i < 4000; i++){ nx.fillStyle = `hsl(${i * 37 % 360},80%,${30 + i % 40}%)`; nx.fillRect(i * 13 % 480, i * 7 % 360, 9, 9); }
        const pet = (id, name, art) => ({ id, kind: pets[0] ? pets[0].kind : KINDS[0].id, color: 'U', p: 1, t: 1, power: '', acc: 'none', name, art });
        pets = pets.concat([pet('colorme', 'Puffball', c.toDataURL('image/jpeg', 0.72)), pet('busy', 'Confetti', n.toDataURL('image/jpeg', 0.72))]);
        store('luna_pets', pets); })(); true""")
    await pg.click("[data-go=studio]"); await pg.click("#stColor")
    mine = pg.locator("#stPages button[aria-label=Puffball]")
    assert await mine.count() == 1, "her drawn creature isn't a coloring page"
    await pg.wait_for_function("document.querySelector('#stPages button[aria-label=Puffball] img').complete && document.querySelector('#stPages button[aria-label=Puffball] img').naturalWidth > 0")
    await pg.wait_for_function("!document.querySelector('#stPages button[aria-label=Confetti]')")  # too busy to color: left out
    await mine.click()
    assert "Puffball" in await pg.inner_text("#pTitle"), "title doesn't name her creature"
    await pg.wait_for_function("pWall && pWall.some(v => v)")
    box = await pg.locator("#pCanvas").bounding_box()
    await pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    px_ = "(x, y) => Array.from(pc.getContext('2d').getImageData(x, y, 1, 1).data)"
    assert (await pg.evaluate(f"({px_})(480, 360)"))[3] == 255, "fill didn't color inside her creature"
    assert (await pg.evaluate(f"({px_})(20, 20)"))[3] == 0, "fill leaked past her creature's outline"
    await pg.click("#pCancel"); await pg.click("#askNo")
    assert not await pg.is_visible("#paint"), "cancel didn't close the coloring page"
    await pg.evaluate("pets = pets.filter(p => !['colorme', 'busy'].includes(p.id)); store('luna_pets', pets); true"); await home(pg)

@test
async def game_night(pg, mode):
    await pg.click("[data-go=night]")
    if await pg.is_visible("#ntStart"): await pg.click("#ntStart")
    l0 = await pg.evaluate("night.players[0].life")
    await pg.click("#ntBoard .nt-p >> nth=0 >> .tap >> nth=0"); await pg.click("#ntBoard .nt-p >> nth=0 >> .five button >> nth=1")
    assert await pg.evaluate("night.players[0].life") == l0 + 4, "life math wrong"
    await pg.click("[data-roll='20']"); assert "🎲" in await pg.inner_text("#ntRoll")
    await dismiss(pg)  # a natural 20 (1 in 20) finds the "Lucky twenty" secret and opens a celebration
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

@test
async def game_night_steps(pg, mode):
    # The turn helper works without reading: big picture step buttons, tap one to hear it, the banner wears the
    # player's colour, "Next turn" glows on Done, and with "Face each other" the banner turns toward whoever is playing.
    await pg.evaluate("night.players = null; night.count = 2; night.flip = false; saveNight(); window.__said = []; window.__say = say; say = (t, f) => { __said.push(t); __say(t, f); }; true")
    await pg.click("[data-go=night]"); await pg.click("#ntStart"); await pg.click("#ntNextTurn")
    steps = pg.locator("#ntSteps button")
    assert await steps.count() == 6, "turn steps aren't buttons"
    for i in range(6):
        bb = await steps.nth(i).bounding_box()
        assert bb["height"] >= 52 and bb["width"] >= 52, f"step {i} is too small to tap ({bb})"
        assert (await steps.nth(i).inner_text()).strip()[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ", f"step {i} has no picture"
    await pg.wait_for_timeout(400)  # the banner colour fades in
    who = await pg.evaluate("(() => { const c = document.createElement('i'); c.style.color = NT_COLORS[night.turn]; document.body.appendChild(c); const want = getComputedStyle(c).color; c.remove(); return [getComputedStyle(document.getElementById('ntWho')).backgroundColor, want]; })()")
    assert who[0] == who[1], f"banner isn't in the player's colour ({who})"
    await steps.nth(4).click()
    assert await pg.evaluate("night.step") == 4, "tapping a step didn't jump to it"
    assert "Attack" in (await pg.evaluate("__said"))[-1], "tapped step wasn't read aloud"
    assert await pg.locator("#ntSteps button.now").count() == 1 and "now" in (await steps.nth(4).get_attribute("class")), "tapped step not lit"
    assert not await pg.evaluate("ntNextTurn.classList.contains('go')"), "Next turn glows too early"
    await pg.click("#ntNextStep")
    assert await pg.evaluate("ntNextTurn.classList.contains('go')"), "Next turn doesn't glow on Done"
    await pg.click("#ntFlip")
    for _ in range(2):
        t = await pg.evaluate("night.turn")
        assert await pg.evaluate("ntBanner.classList.contains('flip')") == (t == 0), f"banner doesn't face player {t}"
        await pg.click("#ntNextTurn", force=True)  # it pulses while glowing, so it never "settles"
    assert not await pg.evaluate("ntNextTurn.classList.contains('go')"), "glow stuck after the turn passed"
    await pg.click("#ntFlip"); await pg.evaluate("say = __say; true")
    await home(pg)

@test
async def level_up(pg, mode):
    await pg.evaluate("window.__quietCelebrations = false; xp = 14; stars = 0; addStar()")
    await pg.wait_for_function("!document.getElementById('celebrate').classList.contains('hidden')", timeout=3000)
    assert "Level 2" in await pg.inner_text("#celTitle"), "no level-up celebration"
    assert await pg.evaluate("stars") == 6 and await pg.evaluate("xp") == 15, "level-up bonus wrong"
    assert "Spark Student" in await pg.inner_text("#lvlLine"), "home level line not updated"
    await pg.evaluate("window.__quietCelebrations = true"); await dismiss(pg)

@test
async def star_shop(pg, mode):
    await pg.evaluate("stars = 100; xp = Math.max(xp, 100); renderStars()")
    await pg.click("[data-go=maker]")
    assert await pg.locator('#kindRow .pick.locked[data-k="fox"]').count() == 1, "fox should start locked"
    await pg.evaluate("go('shop', true)")
    await pg.click('[data-item="kind:fox"] button'); assert await pg.evaluate("!owned['kind:fox']"), "one tap shouldn't buy"
    await pg.click('[data-item="kind:fox"] button', force=True)
    assert await pg.evaluate("!!owned['kind:fox'] && stars === 85"), "fox not bought"
    await dismiss(pg)
    await pg.click('[data-item="theme:rainbow"] button'); await pg.click('[data-item="theme:rainbow"] button', force=True); await dismiss(pg)
    assert await pg.evaluate("document.body.classList.contains('theme-rainbow')"), "theme not applied"
    await pg.click('[data-item="theme:night"] button')
    assert await pg.evaluate("!document.body.classList.contains('theme-rainbow')"), "couldn't switch back to night"
    await pg.click('[data-item="brush:unicorn"] button'); await pg.click('[data-item="brush:unicorn"] button', force=True); await dismiss(pg)
    lv = await pg.evaluate("levelFor(xp)")
    await pg.evaluate("go('maker', true)")
    assert await pg.locator('#kindRow .pick.locked[data-k="fox"]').count() == 0, "fox still locked after buying"
    assert await pg.evaluate("levelFor(xp)") == lv, "shopping changed the level"
    assert await pg.locator('.tool[data-tool="emo:🦄"]').count() == 1, "unicorn stamp missing from Art Studio"
    await home(pg)

@test
async def secrets(pg, mode):
    await home(pg)
    for _ in range(7): await pg.click("#roothaImg")
    assert await pg.evaluate("!!eggs.rootha"), "Rootha secret not found"; await dismiss(pg)
    for _ in range(5): await pg.click("#titleSpark")
    assert await pg.evaluate("!!eggs.shower"), "star shower secret not found"; await dismiss(pg)
    await pg.click("[data-go=window]")
    for b in ["#addBlue", "#addRed", "#addBlue", "#addRed", "#addPurple"]: await pg.click(b)
    assert await pg.evaluate("!!eggs.spell"), "secret spell not found"; await dismiss(pg)
    await pg.evaluate("go('night', true)")
    if await pg.is_visible("#ntStart"): await pg.click("#ntStart")
    await pg.evaluate("window.__r = Math.random; Math.random = () => 0.999")
    await pg.click("[data-roll='20']"); await pg.evaluate("Math.random = window.__r")
    assert await pg.evaluate("!!eggs.nat20"), "natural twenty secret not found"; await dismiss(pg)
    await pg.evaluate("go('maker', true); draft.name = 'Luna Moonbeam'; draft.p = 9; draft.t = 9; draft.custom = true; renderMaker()")
    await pg.click("#savePet"); await pg.wait_for_timeout(1500); await dismiss(pg)
    assert await pg.evaluate("!!eggs.luna && !!eggs.mega"), "creature secrets not found"
    await pg.evaluate("go('book', true)")
    assert f"6 of {await pg.evaluate('EGGS.length')}" in await pg.inner_text("#eggCount"), "spellbook secret count wrong"
    await home(pg)

@test
async def spell_echo(pg, mode):
    s0 = await pg.evaluate("stars")
    await pg.click("[data-go=echo]"); await pg.click("#echoGo")
    for n in (1, 2, 3):
        await pg.wait_for_function(f"echo.on && !echo.busy && echo.seq.length === {n}", timeout=12000)
        for k in await pg.evaluate("echo.seq"): await pg.click(f'[data-pad="{k}"]')
    await pg.wait_for_function("echo.seq.length === 4 && !echo.busy", timeout=12000)
    assert await pg.evaluate("stars") >= s0 + 1, "no star after round 3"
    for _ in range(2):
        wrong = await pg.evaluate("['U','R','P','G'].find(k => k !== echo.seq[echo.pos])")
        await pg.click(f'[data-pad="{wrong}"]')
        await pg.wait_for_timeout(200)
        if await pg.evaluate("echo.on"): await pg.wait_for_function("!echo.busy", timeout=12000)
    assert await pg.evaluate("!echo.on") and await pg.is_visible("#echoGo"), "game didn't end after two misses"
    await dismiss(pg); await home(pg)

@test
async def faerie_pop(pg, mode):
    s0 = await pg.evaluate("stars")
    await pg.click("[data-go=pop]"); await pg.evaluate("pop.dur = 3000"); await pg.click("#popGo")
    for _ in range(30):
        if not await pg.evaluate("pop.on") and await pg.evaluate("pop.end > 0") and _ > 2: break
        await pg.evaluate("Object.keys(pop.up).forEach(i => popHit(+i))"); await pg.wait_for_timeout(150)
    await pg.wait_for_function("!pop.on", timeout=6000)
    assert await pg.evaluate("stars") >= s0 + 1, "no stars from Faerie Pop"
    assert await pg.is_visible("#celebrate"), "no end-of-round celebration"
    await dismiss(pg); await home(pg)

@test
async def magic_fog(pg, mode):
    s0 = await pg.evaluate("stars")
    await pg.click("[data-go=fog]")
    assert "blur" in await pg.evaluate("document.getElementById('fogImg').style.filter"), "picture isn't foggy"
    await pg.evaluate("[...document.querySelectorAll('#fogOpts button')].find(b => b.dataset.name === fog.card.name).click()")
    assert await pg.is_visible("#fogNext") and await pg.evaluate("stars") > s0, "right answer not rewarded"
    await home(pg)


async def solve_page(pg):
    kind = await pg.evaluate("lsn.l.pages[lsn.i].t")
    if kind == "quiz": await pg.click("#lOpts .lopt[data-ok='1']")
    elif kind == "hot":
        for k in (await pg.get_attribute("#lHot", "data-order")).split(","): await pg.click(f'#lHot [data-spot="{k}"]')
    elif kind == "pay":
        n = await pg.locator("#lLands .land").count()
        for i in range(n):
            if await pg.locator("#lNext").count(): break
            await pg.click(f"#lLands .land >> nth={i}")
    elif kind == "order":
        n = await pg.locator("#lOrd button").count()
        for r in range(n): await pg.click(f'#lOrd button[data-rank="{r}"]')
    await pg.click("#lNext")

@test
async def magic_school(pg, mode):
    s0 = await pg.evaluate("stars")
    await pg.click("[data-go=school]")
    assert await pg.locator("#lessonList .ltile:not(.bonus)").count() == 12, "should have 12 lessons"
    assert await pg.locator("#lessonList .ltile.upnext").count() == 1, "next lesson not highlighted"
    # a wrong answer shakes and doesn't advance
    await pg.click('[data-lesson="colors"]', force=True)
    for _ in range(4): await solve_page(pg)
    wrong = pg.locator("#lOpts .lopt:not([data-ok])").first
    await wrong.click(); assert await pg.locator("#lNext").count() == 0, "wrong answer advanced the lesson"
    await solve_page(pg); await dismiss(pg)
    assert await pg.evaluate("!!stats.lessons.colors"), "lesson 1 not recorded"
    for lid in await pg.evaluate("CORE.map(l => l.id).filter(id => id !== 'colors')"):
        await pg.evaluate("go('school', true)"); await pg.click(f'[data-lesson="{lid}"]', force=True)
        for _ in range(await pg.evaluate("lsn.l.pages.length")): await solve_page(pg)
        await dismiss(pg)
    assert await pg.evaluate("Object.keys(stats.lessons).length") == 12, "not all lessons recorded"
    assert await pg.evaluate("stats.perfectTurn") == 1, "perfect practice turn not recorded"
    assert await pg.evaluate("stars") >= s0 + 36, "lessons should give 3 stars each"
    await pg.evaluate("go('school', true)"); assert await pg.is_visible("#diplomaBtn"), "diploma button missing"
    await pg.wait_for_timeout(200); await pg.evaluate("checkTreasures()")
    assert await pg.evaluate("!!treasures.scholar && !!treasures.turn"), "school treasures not awarded"
    await pg.click("#diplomaBtn"); await pg.wait_for_selector("#celImg:not(.hidden)", timeout=5000)
    await pg.click("#celPrint"); await pg.wait_for_timeout(2500)
    if mode == "web": names = [s["filename"] for s in await pg.evaluate("window.__saved")]
    else: names = [c["saved"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "saved" in c]
    assert any("Diploma" in n for n in names), f"diploma PDF not saved ({names})"
    await dismiss(pg); await home(pg)

@test
async def practice_turn_2(pg, mode):
    # A harder bonus turn (Goldspan Dragon, Treasure, blocking). It glows once school is done but never hides the diploma.
    await pg.evaluate("go('school', true)")
    tile = '[data-lesson="practice2"]'
    assert await pg.locator(tile + ".bonus").count() == 1, "no bonus Practice Turn 2 tile"
    if not await pg.evaluate("!!stats.lessons.practice2"):
        assert await pg.locator(tile + ".upnext").count() == 1, "bonus lesson should glow after the twelve"
    assert await pg.is_visible("#diplomaBtn"), "a bonus lesson hid the diploma"
    s0 = await pg.evaluate("stars"); first = await pg.evaluate("!stats.lessons.practice2")
    await pg.click(tile, force=True)
    kinds = await pg.evaluate("lsn.l.pages.map(p => p.t)"); text = await pg.evaluate("JSON.stringify(lsn.l.pages)")
    assert "pay" in kinds and kinds.count("quiz") >= 8, f"Practice Turn 2 too thin: {kinds}"
    for word in ("Goldspan Dragon", "Treasure", "block", "tapped"): assert word in text, f"Practice Turn 2 never mentions {word}"
    wrong = None
    for i in range(len(kinds)):
        if kinds[i] == "quiz" and wrong is None:
            wrong = pg.locator("#lOpts .lopt:not([data-ok])").first; await wrong.click()
            assert await pg.locator("#lNext").count() == 0, "wrong answer advanced the lesson"
        await solve_page(pg)
    await dismiss(pg)
    assert await pg.evaluate("!!stats.lessons.practice2"), "Practice Turn 2 not recorded"
    if first: assert await pg.evaluate("stars") >= s0 + 3, "no stars for the bonus lesson"
    await pg.evaluate("go('school', true)"); assert await pg.is_visible("#diplomaBtn"), "diploma gone after the bonus"
    await home(pg)

@test
async def listen_mode(pg, mode):
    # Eyes-closed car mode: lessons are read aloud, info pages turn by themselves, answers are two big colored halves.
    await pg.evaluate("go('school', true)"); await pg.click("#listenBtn")
    assert await pg.evaluate("listenMode") and await pg.is_visible("#lessonList .ltile.listen"), "listen mode didn't switch on"
    s0 = await pg.evaluate("stars")
    await pg.click('[data-lesson="zones"]', force=True)
    assert await pg.evaluate("lsn.listen && lsn.lp.every(p => p.t === 'info' || p.t === 'quiz')"), "listen mode kept tap-only pages"
    await pg.wait_for_function("lsn && lsn.lp[lsn.i].t === 'quiz'", timeout=15000)  # info pages turned by themselves
    halves = pg.locator("#lPage .lhalf"); assert await halves.count() == 2, "quiz should be two big halves"
    box = await halves.first.bounding_box(); vp = pg.viewport_size
    assert box["height"] >= vp["height"] * 0.4 and box["width"] >= vp["width"] * 0.4, f"halves too small: {box}"
    if mode == "android":
        spoken = [c["t"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "t" in c]
        assert "Tap blue" in spoken[-1] and "red" in spoken[-1], f"answers not read aloud: {spoken[-1:]}"
    i0 = await pg.evaluate("lsn.i"); await pg.click("#lPage .lhalf:not([data-ok])"); await pg.wait_for_timeout(300)
    assert await pg.evaluate("lsn.i") == i0, "a wrong half advanced the lesson"
    while await pg.evaluate("current === 'lesson'"):
        await pg.wait_for_function("current !== 'lesson' || (lsn.lp[lsn.i].t === 'quiz' && !lsn.answered)", timeout=15000)
        if await pg.evaluate("current === 'lesson'"): await pg.click("#lPage .lhalf[data-ok]")
    assert await pg.is_visible("#celebrate") and await pg.evaluate("stars") >= s0 + 1, "no celebration/star after listening"
    await dismiss(pg)
    # leaving in the middle never lets a late voice callback turn pages on a hidden screen
    await pg.evaluate("go('school', true)"); await pg.click('[data-lesson="colors"]', force=True); await home(pg)
    i0 = await pg.evaluate("lsn.i"); await pg.wait_for_timeout(2500)
    assert await pg.evaluate("current") == "home" and await pg.evaluate("lsn.i") == i0, "listen lesson kept going after leaving"
    await pg.evaluate("listenMode = false"); await home(pg)

@test
async def practice_turn_3(pg, mode):
    # A second bonus turn: Dad attacks and Luna chooses blockers (best blocker, flyers, taking damage, double block).
    await pg.evaluate("go('school', true)"); tile = '[data-lesson="practice3"]'
    assert await pg.locator(tile + ".bonus").count() == 1, "no bonus Practice Turn 3 tile"
    s0 = await pg.evaluate("stars"); first = await pg.evaluate("!stats.lessons.practice3")
    await pg.click(tile, force=True)
    kinds = await pg.evaluate("lsn.l.pages.map(p => p.t)"); text = await pg.evaluate("JSON.stringify(lsn.l.pages)")
    assert kinds.count("quiz") >= 7, f"Practice Turn 3 too thin: {kinds}"
    for word in ("block", "flying", "double block", "life"): assert word in text, f"Practice Turn 3 never mentions {word}"
    for _ in kinds: await solve_page(pg)
    await dismiss(pg)
    assert await pg.evaluate("!!stats.lessons.practice3"), "Practice Turn 3 not recorded"
    if first: assert await pg.evaluate("stars") >= s0 + 3, "no stars for the bonus lesson"
    await pg.evaluate("go('school', true)"); assert await pg.is_visible("#diplomaBtn"), "a bonus lesson hid the diploma"
    await home(pg)

@test
async def practice_turn_5(pg, mode):
    # The turn after Dragon Day: a spell before combat wakes Rootha's trick, the Dragon and the Elemental fly in together,
    # and on Dad's turn Rootha (who stayed home) blocks. Playable by tapping, and eyes-closed in listen mode.
    await pg.evaluate("go('school', true)"); tile = '[data-lesson="practice5"]'
    assert await pg.locator(tile + ".bonus").count() == 1, "no bonus Practice Turn 5 tile"
    s0 = await pg.evaluate("stars"); first = await pg.evaluate("!stats.lessons.practice5")
    await pg.click(tile, force=True)
    kinds = await pg.evaluate("lsn.l.pages.map(p => p.t)"); text = await pg.evaluate("JSON.stringify(lsn.l.pages)")
    assert kinds.count("quiz") >= 7 and "pay" in kinds, f"Practice Turn 5 too thin: {kinds}"
    for word in ("before combat", "Elemental", "Goldspan Dragon", "flying", "block", "tapped", "life"):
        assert word in text, f"Practice Turn 5 never mentions {word}"
    for _ in kinds: await solve_page(pg)
    await dismiss(pg)
    assert await pg.evaluate("!!stats.lessons.practice5"), "Practice Turn 5 not recorded"
    if first: assert await pg.evaluate("stars") >= s0 + 3, "no stars for the bonus lesson"
    await pg.evaluate("go('school', true); listenMode = true; renderSchool()"); await pg.click(tile, force=True)
    assert await pg.evaluate("lsn.lp.every(p => p.t === 'info' || p.t === 'quiz')"), "listen mode kept a tap-only page"
    while await pg.evaluate("current === 'lesson'"):
        await pg.wait_for_function("current !== 'lesson' || (lsn.lp[lsn.i].t === 'quiz' && !lsn.answered)", timeout=15000)
        if await pg.evaluate("current === 'lesson'"):
            assert await pg.locator("#lPage .lhalf").count() == 2; await pg.click("#lPage .lhalf[data-ok]")
    await dismiss(pg); await pg.evaluate("listenMode = false"); await home(pg)

@test
async def listen_mode_all_pages(pg, mode):
    # Eyes-closed mode keeps every lesson whole: tap-only pages become spoken two-choice questions.
    await pg.evaluate("go('school', true); listenMode = true; renderSchool()")
    await pg.click('[data-lesson="parts"]', force=True)
    qs = await pg.evaluate("lsn.lp.filter(p => p.t === 'quiz').map(p => p.q)")
    assert sum("Where is" in q for q in qs) == 6, f"card-part spots not turned into questions: {qs}"
    await pg.evaluate("go('school', true)"); await pg.click('[data-lesson="mana"]', force=True)
    qs = await pg.evaluate("lsn.lp.filter(p => p.t === 'quiz').map(p => p.q)")
    assert any("Goldspan Dragon cost in all" in q for q in qs), f"paying pages not turned into questions: {qs}"
    await pg.evaluate("go('school', true)"); s0 = await pg.evaluate("stars")
    await pg.click('[data-lesson="turn"]', force=True)
    assert await pg.evaluate("lsn.lp.length") >= 8, "turn order not turned into a question per step"
    while await pg.evaluate("current === 'lesson'"):
        await pg.wait_for_function("current !== 'lesson' || (lsn.lp[lsn.i].t === 'quiz' && !lsn.answered)", timeout=15000)
        if await pg.evaluate("current === 'lesson'"):
            assert await pg.locator("#lPage .lhalf").count() == 2; await pg.click("#lPage .lhalf[data-ok]")
    assert await pg.evaluate("stars") >= s0 + 1, "no star after listening to the whole turn lesson"
    await dismiss(pg); await pg.evaluate("listenMode = false"); await home(pg)

@test
async def star_map_treasures(pg, mode):
    await pg.evaluate("setStat('battleStreak', 10); setStat('countStreak', 9); setStat('bubbleCasts', 10); checkTreasures()")
    assert await pg.evaluate("!!treasures.battle && !!treasures.bubble && !treasures.count"), "treasure thresholds wrong"
    await pg.evaluate("go('stars', true)")
    assert await pg.locator("#skySvg svg [data-star]").count() == 12, "sky should have 12 stars"
    assert "of 12" in await pg.inner_text("#skyCap"), "star count caption missing"
    assert "9 of 10" in await pg.inner_text("#tGrid"), "progress for unfinished treasure missing"
    # the full constellation unlocks the Starlight theme
    await pg.evaluate("TREASURES.forEach(t => { if (t.id !== 'painter') treasures[t.id] = 1; }); setStat('paintings', 8); checkTreasures()")
    assert await pg.evaluate("!!owned['theme:starlight']"), "Starlight theme not unlocked"
    await pg.evaluate("go('shop', true)"); assert await pg.locator('[data-item="theme:starlight"]').count() == 1, "Starlight not shown in shop"
    await dismiss(pg); await home(pg)

async def fresh_backup(pg):
    # Tap Save and wait for THIS backup to land (a fixed sleep read a stale one when familiar was busy).
    n = await pg.evaluate("window.__saved.filter(s => s.filename.endsWith('.json')).length")
    await pg.click("#bkSave")
    await pg.wait_for_function(f"window.__saved.filter(s => s.filename.endsWith('.json')).length > {n}", timeout=10000)
    return json.loads([s for s in await pg.evaluate("window.__saved") if s["filename"].endswith(".json")][-1]["text"])

@test
async def backup_has_progress(pg, mode):
    if mode != "web": return
    await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
    assert d["v"] == 4 and d["xp"] >= 15 and d["owned"].get("kind:fox") and d["eggs"].get("rootha"), "backup is missing levels, purchases, or secrets"
    done = await pg.evaluate("Object.keys(stats.lessons)")
    assert len(done) >= 12 and set(d["stats"]["lessons"]) == set(done) and d["treasures"].get("scholar"), "backup is missing Magic School or Star Map progress"
    await home(pg)

@test
async def new_tags_clear(pg, mode):
    # "NEW" on a home tile goes away once Luna has opened that game, and stays gone (it's saved and backed up).
    tag = "[data-go=stars] .newtag"
    await pg.evaluate("delete seenGames.stars; store('luna_seen', seenGames); renderNewTags()")
    assert await pg.is_visible(tag), "NEW tag missing on a game she hasn't opened"
    await pg.click("[data-go=stars]"); await home(pg)
    assert not await pg.is_visible(tag) and await pg.evaluate("!!load('luna_seen', {}).stars"), "NEW tag didn't clear after a visit"
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        assert d.get("seen", {}).get("stars"), "backup is missing which games she's seen"
        await home(pg)

@test
async def gentle_feedback(pg, mode):
    # Little moments that used to be silent or confusing.
    await pg.click("[data-go=memory]")
    order = await pg.evaluate("mem.map(m => m.k)"); b = next(i for i, k in enumerate(order) if k != order[0])
    n0 = await pg.evaluate("tonesPlayed")
    await pg.click("#memGrid .mcard >> nth=0"); await pg.click(f"#memGrid .mcard >> nth={b}"); await pg.wait_for_timeout(500)
    assert await pg.evaluate("tonesPlayed") >= n0 + 3, "no sound when two cards don't match"
    if mode == "android":
        spoken = [c["t"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "t" in c]
        assert "try again" in spoken[-1].lower(), f"mismatch not spoken: {spoken[-1:]}"
    await home(pg)
    await pg.click("[data-go=echo]")
    assert "Spell Echo" not in await pg.inner_text("#echoRound"), "Spell Echo name shown twice"
    await home(pg)
    keep = await pg.evaluate("drawings"); await pg.evaluate("drawings = []")
    try:
        await pg.click("[data-go=studio]"); assert await pg.is_visible("#stGallery .empty-note"), "empty Art Studio has no friendly note"
    finally:
        await pg.evaluate("d => { drawings = d; }", keep)
    await home(pg)

@test
async def home_layout(pg, mode):
    # Landscape tablets get three columns of games; an odd tile out never sits alone in half a row.
    tiles = ".games .game-btn:not(.hidden):not(.wide)"
    try:
        await pg.set_viewport_size({"width": 1280, "height": 800}); await home(pg); await pg.wait_for_timeout(100)
        xs = await pg.evaluate(f"[...new Set([...document.querySelectorAll('{tiles}')].map(b => Math.round(b.getBoundingClientRect().x)))].length")
        assert xs == 3, f"landscape home should have 3 columns, has {xs}"
        await pg.set_viewport_size({"width": 800, "height": 1280}); await home(pg); await pg.wait_for_timeout(100)
        gw = await pg.evaluate("document.querySelector('.games').getBoundingClientRect().width")
        widths = await pg.evaluate(f"[...document.querySelectorAll('{tiles}')].map(b => b.getBoundingClientRect().width)")
        if len(widths) % 2: assert widths[-1] > gw * 0.9, f"orphan tile in portrait ({len(widths)} tiles, last {widths[-1]:.0f}px of {gw:.0f}px)"
        else: assert all(w < gw * 0.6 for w in widths), "a tile spans the row when the count is even"
        await pg.evaluate("$('storyTile').classList.toggle('hidden'); updateHomeGrid()")  # the other parity
        widths = await pg.evaluate(f"[...document.querySelectorAll('{tiles}')].map(b => b.getBoundingClientRect().width)")
        if len(widths) % 2: assert widths[-1] > gw * 0.9, "orphan tile after the story tile changed"
        else: assert all(w < gw * 0.6 for w in widths), "a tile stayed full-width after the count became even"
        await pg.evaluate("$('storyTile').classList.toggle('hidden'); updateHomeGrid()")
    finally:
        await pg.set_viewport_size({"width": 400, "height": 860}); await home(pg)
    assert await pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "home scrolls sideways on a phone"

async def drag(pg, frm, x, y):
    b = await frm.bounding_box()
    await pg.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2); await pg.mouse.down()
    await pg.mouse.move(x, y, steps=8); await pg.mouse.up(); await pg.wait_for_timeout(100)

@test
async def sticker_scene(pg, mode):
    # Earned stickers go onto a scene (tap or drag), can be moved or dragged off, persist per scene, and back up.
    await pg.evaluate("window.__xp0 = xp; xp = Math.max(xp, 40); store('luna_scene', { bg: 'castle', items: {} }); scene = load('luna_scene'); true")
    await pg.evaluate("go('book', true)"); await pg.click("#scOpen")
    assert await pg.is_visible("#scene"), "sticker scene didn't open"
    tray = pg.locator("#scTray button")
    assert await tray.count() == await pg.evaluate("Math.min(Math.floor(xp / 10), STICKERS.length)"), "tray isn't the earned stickers"
    bb = await tray.first.bounding_box(); assert bb["height"] >= 52 and bb["width"] >= 52, f"tray sticker too small ({bb})"
    await tray.nth(0).click()
    assert await pg.evaluate("scene.items.castle.length") == 1 and await pg.locator("#scStage .sc-st").count() == 1, "tapping a sticker didn't place it"
    st = await pg.locator("#scStage").bounding_box()
    await drag(pg, tray.nth(1), st["x"] + st["width"] * 0.3, st["y"] + st["height"] * 0.4)
    it = await pg.evaluate("scene.items.castle[1]")
    assert it and abs(it["x"] - 0.3) < 0.05 and abs(it["y"] - 0.4) < 0.05, f"drag didn't drop where the finger let go ({it})"
    assert it["s"] == await pg.evaluate("STICKERS[1]"), "wrong sticker dropped"
    await drag(pg, pg.locator("#scStage .sc-st").nth(1), st["x"] + st["width"] * 0.7, st["y"] + st["height"] * 0.6)
    it = await pg.evaluate("scene.items.castle[1]")
    assert abs(it["x"] - 0.7) < 0.05 and abs(it["y"] - 0.6) < 0.05, f"placed sticker didn't move ({it})"
    assert len(await pg.evaluate("load('luna_scene').items.castle")) == 2, "placements not saved"
    await pg.click("[data-scene=sky]")
    assert await pg.locator("#scStage .sc-st").count() == 0 and await pg.evaluate("load('luna_scene').bg") == "sky", "sky scene didn't switch"
    await pg.click("[data-scene=castle]"); assert await pg.locator("#scStage .sc-st").count() == 2, "castle stickers lost after switching"
    await drag(pg, pg.locator("#scStage .sc-st").first, st["x"] + st["width"] / 2, st["y"] + st["height"] + 140)
    assert await pg.evaluate("scene.items.castle.length") == 1, "dragging a sticker off didn't remove it"
    assert await pg.evaluate("window.__back()") == "stay" and await pg.is_visible("#book"), "Back from the scene should go to My Spellbook"
    if mode == "web":
        d = await fresh_backup(pg)
        assert len(d["scene"]["items"]["castle"]) == 1, "backup is missing the sticker scene"
        # restoring adds the backup's stickers to the scene without erasing what's there; junk is dropped
        d["scene"]["items"] = {"castle": [{"id": "r1", "s": "🦄", "x": 0.5, "y": 0.5}, {"id": "bad", "s": "<b>", "x": 0.1, "y": 0.1}],
                               "meadow": [{"id": "r2", "s": "🌈", "x": 9, "y": -3}]}
        await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
        await pg.wait_for_function("(load('luna_scene').items.meadow || []).length > 0", timeout=10000)  # restore is async (FileReader)
        sc = await pg.evaluate("load('luna_scene')")
        assert len(sc["items"]["castle"]) == 2 and not any(i["s"] == "<b>" for i in sc["items"]["castle"]), f"restore didn't merge the scene ({sc})"
        assert sc["items"]["meadow"][0]["x"] == 1 and sc["items"]["meadow"][0]["y"] == 0, "restored positions not kept on the picture"
    await pg.evaluate("xp = __xp0; true"); await home(pg)

@test
async def treasure_catch(pg, mode):
    # Goldspan Dragon drops treasure; slide the basket to catch it. 30-second rounds, no penalties.
    await pg.click("[data-go=catch]"); s0 = await pg.evaluate("stars")
    await pg.click("#catchGo"); assert await pg.evaluate("tc.on"), "round didn't start"
    f = await pg.locator("#catchField").bounding_box()
    await pg.mouse.click(f["x"] + f["width"] * 0.2, f["y"] + f["height"] * 0.9)
    assert abs(await pg.evaluate("tc.x") - 0.2) < 0.05, "basket didn't follow the finger"
    b = await pg.locator("#catchBasket").bounding_box(); assert b["width"] >= 100, f"basket too small to catch in a bumpy car ({b['width']:.0f}px)"
    n = await pg.evaluate("tc.score")
    await pg.evaluate("catchSpawn(); const it = tc.items[tc.items.length - 1]; it.x = tc.x; it.y = 0.8; catchAdvance(0.2)")
    assert await pg.evaluate("tc.score") > n, "treasure over the basket wasn't caught"
    m = await pg.evaluate("tc.score")
    await pg.evaluate("catchSpawn(); const it = tc.items[tc.items.length - 1]; it.x = tc.x > 0.5 ? 0.1 : 0.9; it.y = 0.8; catchAdvance(0.2)")
    assert await pg.evaluate("tc.score") == m, "treasure far from the basket was caught"
    await pg.evaluate("tc.end = Date.now()"); await pg.wait_for_function("!tc.on", timeout=5000)
    assert await pg.evaluate("stars") > s0 and await pg.evaluate("stats.catchBest") >= m, "no stars or best score after the round"
    assert await pg.is_visible("#catchGo"), "no Play again button"
    await dismiss(pg)
    await pg.click("#catchGo"); await home(pg)
    assert not await pg.evaluate("tc.on") and await pg.locator("#catchField .tcoin").count() == 0, "round kept running after leaving"
    await pg.click("[data-go=catch]"); assert await pg.is_visible("#catchGo"), "no Start button after leaving mid-round and coming back"
    await home(pg)

@test
async def daily_hello(pg, mode):
    # The first open each day: Rootha says hello for the time of day, with a small gift. Never twice a day, no streaks.
    # one star short of a sticker, so the gift also earns one: the hello must still come first
    await pg.evaluate("setStat('lastHello', 0); xp = Math.floor(xp / 10) * 10 + 9; window.__quietCelebrations = false; celebQueue.length = 0")
    try:
        s0 = await pg.evaluate("stars"); await pg.evaluate("dailyHello()")
        await pg.wait_for_selector("#celebrate:not(.hidden)", timeout=4000)
        title = await pg.inner_text("#celTitle")
        assert "Luna" in title and any(w in title for w in ("morning", "afternoon", "evening", "Hello")), f"odd greeting: {title}"
        assert await pg.evaluate("stars") == s0 + 2, "no daily gift"
        assert await pg.evaluate("stats.lastHello") == await pg.evaluate("todayNum()"), "today not remembered"
        await pg.click("#celOk"); await pg.wait_for_selector("#celebrate:not(.hidden)", timeout=4000)
        assert "sticker" in (await pg.inner_text("#celTitle")).lower(), "the sticker the gift earned wasn't celebrated after the hello"
        await dismiss(pg); await pg.evaluate("dailyHello()"); await pg.wait_for_timeout(1200)
        assert not await pg.is_visible("#celebrate") and await pg.evaluate("stars") == s0 + 2, "daily gift given twice in one day"
        for h, word in ((8, "morning"), (14, "afternoon"), (19, "evening")):
            assert word in await pg.evaluate(f"helloFor({h}).title"), f"wrong greeting at {h}:00"
    finally:
        await pg.evaluate("window.__quietCelebrations = true")
    await dismiss(pg); await home(pg)

@test
async def todays_pick(pg, mode):
    # "Rootha's pick": one gentle suggestion on home, the game she plays least, fixed for the day. The first star she
    # earns in it today brings two bonus stars; nothing is lost if she ignores it (no streaks).
    games = await pg.evaluate("Object.keys(GAME_NAMES)")
    keep = await pg.evaluate("JSON.stringify({ xp, stars, plays: Object.fromEntries(Object.keys(GAME_NAMES).map(g => [g, stats['play_' + g]])) })")
    plays = "; ".join(f"stats.play_{g} = {0 if g == 'memory' else 5}" for g in games)
    await pg.evaluate(f"{plays}; stats.pickDay = 0; stats.pickDone = 0; store('luna_stats', stats); go('home', true)")
    assert await pg.evaluate("todayPick()") == "memory", "the pick isn't the least-played game"
    assert await pg.is_visible('[data-go="memory"] .picktag'), "no Rootha's pick tag on the least-played game"
    assert await pg.locator(".picktag:visible").count() == 1, "more than one pick on home"
    await pg.evaluate("window.__said = []; window.__say = say; say = (t, f) => { __said.push(t); __say(t, f); }; go('home')")
    assert "Memory Match" in " ".join(await pg.evaluate("__said")), "home doesn't say today's pick out loud"
    await pg.evaluate("stats.play_memory = 50; go('home', true)")
    assert await pg.evaluate("todayPick()") == "memory", "the pick changed during the day"
    await pg.evaluate("window.__quietCelebrations = false; celebQueue.length = 0")
    try:
        await pg.evaluate("go('count', true)"); s0 = await pg.evaluate("stars"); await pg.evaluate("addStar(1)")
        assert await pg.evaluate("stars") == s0 + 1, "a star in another game paid the pick bonus"
        await pg.evaluate("go('memory', true)"); s0 = await pg.evaluate("stars"); await pg.evaluate("addStar(1)")
        assert await pg.evaluate("stars") == s0 + 3, "no pick bonus for the first star in today's pick"
        await pg.wait_for_selector("#celebrate:not(.hidden)", timeout=4000)
        assert "pick" in (await pg.inner_text("#celTitle")).lower(), "the pick bonus wasn't celebrated"
        await dismiss(pg); s0 = await pg.evaluate("stars"); await pg.evaluate("addStar(1)")
        assert await pg.evaluate("stars") == s0 + 1, "pick bonus paid twice in one day"
    finally:
        # put back the stars and play counts, so later tests' sticker and level-up timing doesn't shift
        await pg.evaluate(f"say = __say; window.__quietCelebrations = true; const k = {keep}; xp = k.xp; stars = k.stars; "
                          "Object.entries(k.plays).forEach(([g, n]) => { if (n == null) delete stats['play_' + g]; else stats['play_' + g] = n; }); "
                          "store('luna_xp', xp); store('luna_stars', stars); store('luna_stats', stats); renderStars()")
    await home(pg)
    assert not await pg.is_visible('[data-go="memory"] .picktag'), "the pick tag stays after she played it"

@test
async def weekly_challenge(pg, mode):
    # One goal per week (rotating) with a special sticker; progress shows on home and is read aloud.
    await pg.evaluate("window.__chalIdx = CHALLENGES.findIndex(c => c.id === 'casts'); store('luna_week', null); week = loadWeek(); delete badges[weekNo()]; store('luna_badges', badges); go('home', true)")
    assert "Window Magic" in await pg.inner_text("#chalCard"), "home doesn't show this week's challenge"
    s0 = await pg.evaluate("stars")
    await pg.evaluate("chal('faeries', 50)"); assert await pg.evaluate("week.n") == 0, "another game's progress counted"
    for _ in range(4): await pg.evaluate("chal('casts')")
    assert await pg.evaluate("week.n") == 4 and not await pg.evaluate("!!badges[weekNo()]"), "finished too early"
    assert "4" in await pg.inner_text("#chalCard"), "progress not shown on home"
    if mode == "android":
        await pg.click("#chalCard")
        spoken = [c["t"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "t" in c]
        assert "challenge" in spoken[-1].lower() and "4" in spoken[-1], f"challenge not read aloud: {spoken[-1:]}"
    await pg.evaluate("chal('casts')")
    assert await pg.evaluate("badges[weekNo()] && badges[weekNo()].s === CHALLENGES[__chalIdx].sticker"), "no special sticker"
    assert await pg.evaluate("stars") >= s0 + 5, "no bonus stars"
    assert await pg.locator("#chalCard.done").count() == 1, "home card doesn't show it's done"
    s1 = await pg.evaluate("stars"); await pg.evaluate("chal('casts')"); assert await pg.evaluate("stars") == s1, "rewarded twice"
    await pg.evaluate("go('book', true)")
    assert await pg.evaluate("CHALLENGES[__chalIdx].sticker") in await pg.inner_text("#badges"), "challenge sticker not in My Spellbook"
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        assert d.get("badges", {}).get(str(await pg.evaluate("weekNo()"))) and d.get("week"), "backup is missing challenge stickers or progress"
    # a real game feeds it: Count the Mana
    await pg.evaluate("window.__chalIdx = CHALLENGES.findIndex(c => c.id === 'count'); store('luna_week', null); week = loadWeek(); delete badges[weekNo()]")
    await pg.evaluate("go('count', true)")
    await pg.evaluate("[...document.querySelectorAll('#cAns .ans')].find(b => +b.textContent === total(cCur)).click()")
    assert await pg.evaluate("week.n") == 1, "Count the Mana didn't count toward the challenge"
    await pg.evaluate("delete window.__chalIdx; week = loadWeek(); go('home', true)")

@test
async def secret_garden(pg, mode):
    # Three more secrets live inside games; finding every secret opens the hidden Secret Garden colors.
    await pg.click("[data-go=pop]"); await pg.click("#popGo")
    await pg.evaluate("for (let k = 0; k < 3; k++){ pop.up[0] = { who: POP_WHO.find(w => w[1] === 0), t: 0 }; popHit(0); }")
    assert await pg.evaluate("pop.on"), "waking the owl stopped the game"
    await pg.evaluate("pop.end = Date.now()"); await pg.wait_for_function("!pop.on", timeout=5000)
    await pg.wait_for_function("!!eggs.owl", timeout=3000)  # recorded just after the round's own celebration
    await dismiss(pg); await home(pg)
    await pg.click("[data-go=catch]"); await pg.click("#catchGo")
    await pg.evaluate("for (let k = 0; k < 3; k++){ const el = document.createElement('div'); catchGot({ el, pts: 3 }); }")
    assert await pg.evaluate("tc.on"), "a gem secret interrupted the round"
    await pg.evaluate("tc.end = Date.now()"); await pg.wait_for_function("!tc.on", timeout=5000)
    await pg.wait_for_function("!!eggs.gems", timeout=3000)  # recorded just after the round's own celebration
    await dismiss(pg); await home(pg)
    # with every other secret already found, the last one opens the garden
    await pg.evaluate("EGGS.forEach(e => { if (e.id !== 'ears' && !eggs[e.id]) eggs[e.id] = 1; }); delete eggs.ears; delete owned['theme:garden']; store('luna_eggs', eggs)")
    assert await pg.evaluate("shopHidden(SHOP.find(i => i.id === 'theme:garden'))"), "garden visible before it's unlocked"
    await pg.evaluate("go('school', true); listenMode = true; renderSchool()"); await pg.click('[data-lesson="win"]', force=True)
    while await pg.evaluate("current === 'lesson'"):
        await pg.wait_for_function("current !== 'lesson' || (lsn.lp[lsn.i].t === 'quiz' && !lsn.answered)", timeout=15000)
        if await pg.evaluate("current === 'lesson'"): await pg.click("#lPage .lhalf[data-ok]")
    await pg.wait_for_function("!!eggs.ears", timeout=3000)
    assert await pg.evaluate("!!owned['theme:garden']"), "finding every secret didn't open the Secret Garden"
    await dismiss(pg); await pg.evaluate("listenMode = false; go('shop', true)")
    await pg.click('[data-item="theme:garden"] button')
    assert await pg.evaluate("theme") == "garden" and await pg.evaluate("document.body.classList.contains('theme-garden')"), "garden colors don't apply"
    await pg.click('[data-item="theme:night"] button'); await home(pg)

FCP_NOTICE = ("Luna's Spell Car is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. "
              "Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.")

@test
async def fan_content_notice(pg, mode):
    # Wizards' Fan Content Policy notice, word for word, in the app's grown-ups panel and the README.
    await pg.evaluate("document.querySelector('.grownup').open = true")
    assert (await pg.inner_text("#fcpNotice")).strip() == FCP_NOTICE, "Fan Content notice missing or changed in the app"
    assert FCP_NOTICE in open(os.path.join(ROOT, "README.md"), encoding="utf-8").read(), "Fan Content notice missing from README"
    await pg.evaluate("document.querySelector('.grownup').open = false")

@test
async def creature_backgrounds(pg, mode):
    # Make a Creature: pick where it lives (the magic picture's background), plus the mermaid in the Star Shop.
    await pg.click("[data-go=maker]")
    assert await pg.locator("#bgRow .pick").count() >= 5, "no background choices"
    plain = await pg.evaluate("petImg({ ...draft, bg: 'sparkle' })")
    await pg.click('#bgRow [data-bg="space"]')
    assert await pg.evaluate("draft.bg") == "space" and await pg.evaluate("petImg(draft)") != plain, "background didn't change the picture"
    assert await pg.evaluate("petImg({ kind: draft.kind, color: draft.color, acc: draft.acc }) === petImg({ kind: draft.kind, color: draft.color, acc: draft.acc, bg: 'sparkle' })"), "old creatures' pictures changed"
    assert await pg.locator('#kindRow [data-k="mermaid"].locked').count() == 1 or await pg.evaluate("isOwned('kind:mermaid')"), "mermaid should be a Star Shop creature"
    await pg.evaluate("owned['kind:mermaid'] = 1; renderKindRow()"); await pg.click('#kindRow [data-k="mermaid"]')
    n0 = await pg.evaluate("pets.length"); await pg.click("#savePet"); await dismiss(pg)
    p = await pg.evaluate("pets[pets.length - 1]")
    assert pets_ok(p), f"saved creature lost its kind or background: {p}"
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        d["pets"] = [dict(p, id="bg1"), dict(p, id="bg2", bg="<script>")]
        await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
        await pg.wait_for_function("pets.some(x => x.id === 'bg2')", timeout=5000)
        got = await pg.evaluate("[pets.find(x => x.id === 'bg1').bg, pets.find(x => x.id === 'bg2').bg]")
        assert got[0] == "space" and got[1] in (None, "sparkle"), f"restore didn't keep/clean backgrounds: {got}"
        await pg.evaluate("pets = pets.filter(x => !['bg1', 'bg2'].includes(x.id)); store('luna_pets', pets)")
    await pg.evaluate("pets = pets.filter(x => x.id !== %s); store('luna_pets', pets)" % json.dumps(p["id"]))
    await home(pg)

def pets_ok(p): return p and p.get("kind") == "mermaid" and p.get("bg") == "space"

@test
async def parent_stats(pg, mode):
    # For grown-ups: which games she plays and how her first-try accuracy is going. On the device only.
    f0 = await pg.evaluate("stats.play_fog || 0")
    for _ in range(2): await pg.click("[data-go=fog]"); await home(pg)
    assert await pg.evaluate("stats.play_fog") == f0 + 2, "game plays not counted"
    await pg.click("[data-go=count]")
    t0, r0 = await pg.evaluate("[stats.countTries || 0, stats.countFirst || 0]")
    await pg.evaluate("[...document.querySelectorAll('#cAns .ans')].find(b => +b.textContent === total(cCur)).click()")
    await pg.click("#cNext")
    await pg.evaluate("[...document.querySelectorAll('#cAns .ans')].find(b => +b.textContent !== total(cCur)).click()")
    await pg.evaluate("[...document.querySelectorAll('#cAns .ans')].find(b => +b.textContent === total(cCur)).click()")
    assert await pg.evaluate("[stats.countTries, stats.countFirst]") == [t0 + 2, r0 + 1], "first-try accuracy counted wrong"
    await home(pg)
    await pg.evaluate("document.querySelector('.grownup').open = true"); await pg.wait_for_timeout(100)
    txt = await pg.inner_text("#parentStats")
    assert "Magic Fog" in txt and "%" in txt and "first try" in txt, f"grown-up stats missing: {txt[:200]}"
    await pg.evaluate("document.querySelector('.grownup').open = false")

@test
async def parent_stats_game_levels(pg, mode):
    # For grown-ups: each mini game's level (1 to 5), so a parent can see which games have got trickier. Unplayed games stay out.
    keep = await pg.evaluate("JSON.stringify(stats.gxp || {})")
    try:
        await pg.evaluate("stats.gxp = { echo: 30, pop: 12, fog: 0 }; store('luna_stats', stats)")
        await pg.evaluate("document.querySelector('.grownup').open = true"); await pg.wait_for_timeout(100)
        line = await pg.evaluate("[...document.querySelectorAll('#parentStats div')].map(d => d.textContent).find(t => t.startsWith('Game levels')) || ''")
        assert line == "Game levels (1 to 5): Spell Echo 3, Faerie Pop 2", f"game levels line wrong: {line!r}"
        await pg.evaluate("document.querySelector('.grownup').open = false; stats.gxp = {}; store('luna_stats', stats)")
        await pg.evaluate("document.querySelector('.grownup').open = true"); await pg.wait_for_timeout(100)
        assert "Game levels (1 to 5): none yet" in await pg.inner_text("#parentStats"), "no-games case missing"
    finally:
        await pg.evaluate("stats.gxp = JSON.parse(%s); store('luna_stats', stats); document.querySelector('.grownup').open = false" % json.dumps(keep))

@test
async def movie_night(pg, mode):
    # My Spellbook → Movie night: every magic movie she has, back to back, then "The end".
    keep = await pg.evaluate("[...clipKeys]")
    try:
        await pg.evaluate("clipKeys.clear(); go('book', true)")
        assert not await pg.is_visible("#theaterBtn"), "Movie night shown with no movies"
        await pg.evaluate("""(async () => { for (const n of ['Stormcatch Mentor', 'Faerie Mastermind']){ cast[n] = cast[n] || 1;
            const c = CARDS.find(x => x.name === n), k = clipKeyFor(c); await clipDB.put(k, new Blob(['not a real clip'], { type: 'video/mp4' })); clipKeys.add(k); }
            store('luna_cast', cast); go('book', true); })()""")
        assert await pg.is_visible("#theaterBtn"), "no Movie night button"
        names = await pg.evaluate("theaterList().map(c => c.name)")
        assert names[:2] == ["Stormcatch Mentor", "Faerie Mastermind"] or set(names) >= {"Stormcatch Mentor", "Faerie Mastermind"}, f"playlist wrong: {names}"
        await pg.click("#theaterBtn"); assert await pg.is_visible("#theater"), "theater didn't open"
        assert await pg.inner_text("#thName") == names[0], "first movie not showing"
        await pg.click("#thNext"); assert await pg.inner_text("#thName") == names[1], "Next didn't move on"
        # a clip that can't play moves on by itself instead of getting stuck
        await pg.evaluate("theaterAt(theater.list.length - 1)"); await pg.wait_for_function("document.getElementById('thName').textContent.includes('The end')", timeout=6000)
        assert await pg.evaluate("window.__back()") == "stay" and not await pg.is_visible("#theater"), "Back didn't close Movie night"
    finally:
        await pg.evaluate("""async ks => { for (const k of [...clipKeys]) if (!ks.includes(k)) await clipDB.del(k);
            clipKeys.clear(); ks.forEach(k => clipKeys.add(k)); }""", keep)
    await home(pg)

@test
async def kid_tap_targets(pg, mode):
    # Every button Luna taps is at least 52px both ways, on every screen. Grown-up controls are exempt: the grown-ups
    # panel, Backup/Restore, and Game Night (a table tool for the adults).
    small = await pg.evaluate("""(() => { const out = [];
      for (const s of Object.keys(screens)){
        if (s === 'night') continue;
        go(s, true);
        document.querySelectorAll('button, .lopt').forEach(e => {
          if (e.offsetParent === null || e.closest('.grownup') || ['bkSave', 'bkLoad'].includes(e.id)) return;
          const r = e.getBoundingClientRect();
          if (r.width && r.height && (r.width < 52 || r.height < 52)) out.push(`${s}: ${e.id || e.className || e.tagName} "${e.textContent.trim().slice(0, 20)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
        });
      }
      return [...new Set(out)]; })()""")
    await home(pg)
    assert not small, f"tap targets under 52px: {small}"

@test
async def accent_button_contrast(pg, mode):
    # White text on the green, blue and red buttons (Start/Stop, the right answer, Coloring page, Done, ✓) stays readable
    # (at least 4.5:1) in dark mode too, where the plain accent colors turn light.
    try:
        for scheme in ("light", "dark"):
            await pg.emulate_media(color_scheme=scheme)
            bad = await pg.evaluate("""() => {
              const lum = c => { const m = c.match(/[\\d.]+/g).map(Number), f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
                                 return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]); };
              const box = document.createElement('div'); box.style.cssText = 'position:fixed;left:-9999px';
              box.innerHTML = '<button class="bigplay">a</button><button class="bigplay stop">a</button><button class="ans right">1</button>'
                + '<div class="paint"><div class="pbar2"><button class="done">a</button></div></div><div class="orderdone"><span>a</span></div><div class="ltile done">a</div>';
              document.body.appendChild(box);
              const els = [...box.querySelectorAll('button, .orderdone span')].map(e => [e.className || e.parentElement.className, getComputedStyle(e)])
                .concat([['stColor', getComputedStyle($('stColor'))], ['ltile ✓', getComputedStyle(box.querySelector('.ltile'), '::after')]]);
              const out = {};
              for (const [n, cs] of els){ const a = lum(cs.color), b = lum(cs.backgroundColor), r = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
                if (r < 4.5) out[n] = Math.round(r * 100) / 100; }
              box.remove(); return out; }""")
            assert not bad, f"{scheme}: white text on accent buttons is hard to read: {bad}"
    finally:
        await pg.emulate_media(color_scheme="light")

@test
async def button_contrast(pg, mode):
    # White text on filled buttons stays readable (at least 4.5:1) in every app theme, light and dark.
    try:
        for scheme in ("light", "dark"):
            await pg.emulate_media(color_scheme=scheme)
            r = await pg.evaluate("""() => {
              const lum = c => { const m = c.match(/[\\d.]+/g).map(Number), f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
                                 return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]); };
              const keep = theme, probe = document.createElement('div'); probe.style.background = 'var(--btn)'; document.body.appendChild(probe);
              const out = {};
              for (const t of Object.keys(THEMES)){ theme = t; applyTheme(); const c = getComputedStyle(probe).backgroundColor;
                out[t] = /rgba\\(.*,\\s*0\\)$/.test(c) || c === 'transparent' ? 0 : 1.05 / (lum(c) + 0.05); }
              theme = keep; applyTheme(); probe.remove(); return out; }""")
            bad = {t: round(v, 2) for t, v in r.items() if v < 4.5}
            assert not bad, f"{scheme}: white text on buttons is hard to read in {bad}"
    finally:
        await pg.emulate_media(color_scheme="light")

@test
async def pegasus(pg, mode):
    # Pegasus: a Star Shop creature drawn as a horse with real feathered wings (no pegasus emoji on older tablets).
    k = await pg.evaluate("KINDS.find(k => k.id === 'pegasus')")
    assert k and k.get("shop") and k.get("wings"), f"no winged pegasus in the shop: {k}"
    white = """(p => { const d = petArt(p).getContext('2d').getImageData(200, 10, 200, 150).data; let n = 0;
               for (let i = 0; i < d.length; i += 4) if (d[i] > 235 && d[i + 1] > 235 && d[i + 2] > 235) n++; return n; })"""
    with_wings = await pg.evaluate(f"{white}({{ kind: 'pegasus', color: 'P', acc: 'none', bg: 'space' }})")
    without = await pg.evaluate(f"(() => {{ const k = KINDS.find(k => k.id === 'pegasus'); k.wings = false; for (const c in artCache) delete artCache[c];"
                                f" const n = {white}({{ kind: 'pegasus', color: 'P', acc: 'none', bg: 'space' }}); k.wings = true; for (const c in artCache) delete artCache[c]; return n; }})()")
    assert with_wings - without > 1500, f"wings not drawn (white px {with_wings} vs {without})"
    await pg.click("[data-go=maker]")
    assert await pg.locator('#kindRow [data-k="pegasus"] svg').count() == 1, "picker has no pegasus icon"
    await home(pg)

@test
async def restore_rejects_html_ids(pg, mode):
    # A crafted backup file can't inject markup through creature or painting ids (they reach the gallery's HTML).
    if mode != "web": return
    await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
    bad = '"><img src=x onerror="window.__xss=1">'
    img = await pg.evaluate("(() => { const c = document.createElement('canvas'); c.width = 8; c.height = 6; return c.toDataURL('image/jpeg', .8); })()")
    d["drawings"] = [{"id": bad, "img": img, "at": 1}]
    d["pets"] = [{"id": bad + "p", "kind": "unicorn", "color": "P", "p": 1, "t": 1, "power": "fly", "name": "Safe"}]
    await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
    await pg.wait_for_function("drawings.some(x => x.img.length < 2000) && pets.some(x => x.name === 'Safe')", timeout=5000)
    await pg.evaluate("cloudCaps = { video: true }; go('studio', true)"); await pg.wait_for_timeout(300)
    assert not await pg.evaluate("window.__xss"), "markup in a restored id ran script"
    # and the gallery itself never builds markup from an id (even one that skipped restore's checks)
    await pg.evaluate("i => { drawings.push({ id: i, img: drawings[0].img, at: 1 }); renderStudio(); }", bad + "2"); await pg.wait_for_timeout(200)
    assert not await pg.evaluate("window.__xss"), "the gallery built markup from a painting id"
    await pg.evaluate("i => { drawings = drawings.filter(x => x.id !== i); }", bad + "2")
    ids = await pg.evaluate("drawings.concat(pets).map(x => x.id)")
    assert all(__import__("re").fullmatch(r"[A-Za-z0-9_-]{1,40}", i) for i in ids), f"unsafe ids kept: {ids[-3:]}"
    await pg.evaluate("cloudCaps = null; drawings = drawings.filter(x => x.img.length >= 2000); store('luna_drawings', drawings); pets = pets.filter(x => x.name !== 'Safe'); store('luna_pets', pets)")
    await home(pg)

@test
async def restore_rejects_bad_images(pg, mode):
    # Images in a backup must be real base64 data URLs: a quote can't break out of an <img src="..."> anywhere.
    if mode != "web": return
    await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
    bad = 'data:image/png;base64,AA" onerror="window.__xss2=1'
    d["drawings"] = [{"id": "badimg1", "img": bad, "at": 1}]
    d["pets"] = [{"id": "badpet1", "kind": "unicorn", "color": "P", "p": 1, "t": 1, "power": "fly", "name": "Sneaky", "art": bad}]
    await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
    await pg.wait_for_timeout(600)
    assert not await pg.evaluate("drawings.some(x => x.id === 'badimg1') || pets.some(x => x.id === 'badpet1')"), "restore kept a quote-breaking image"
    # even data that skipped restore's checks never reaches markup as a raw src
    await pg.evaluate("""b => { drawings.push({ id: 'badimg2', img: b, at: 1 }); pets.push({ id: 'badpet2', kind: 'unicorn', color: 'P', p: 1, t: 1, power: 'fly', name: 'Sneaky2', art: b });
        cloudCaps = { video: true }; renderBook(); go('studio', true); go('window', true); }""", bad)
    await pg.wait_for_timeout(300)
    assert not await pg.evaluate("window.__xss2"), "a bad image src ran script"
    await pg.evaluate("drawings = drawings.filter(x => x.id !== 'badimg2'); pets = pets.filter(x => x.id !== 'badpet2'); cloudCaps = null")
    await home(pg)

@test
async def more_scenes(pg, mode):
    # Sticker scene part 2: beach, space, and under-the-sea pictures, each keeping its own stickers (and in backups).
    await pg.evaluate("window.__xp0 = xp; xp = Math.max(xp, 40); go('book', true)"); await pg.click("#scOpen")
    castle_bg = await pg.evaluate("getComputedStyle(document.getElementById('scStage')).backgroundImage")
    seen = set()
    for k in ("beach", "space", "sea"):
        await pg.click(f"[data-scene={k}]")
        assert await pg.evaluate("scene.bg") == k and await pg.get_attribute("#scStage", "data-bg") == k, f"{k} scene didn't open"
        bg = await pg.evaluate("getComputedStyle(document.getElementById('scStage')).backgroundImage")
        assert bg != castle_bg and bg not in seen, f"{k} has no picture of its own"; seen.add(bg)
        assert await pg.locator("#scStage .sc-deco").count() >= 3, f"{k} has no decorations"
    await pg.click("#scTray button >> nth=0")
    assert await pg.evaluate("scene.items.sea.length") >= 1, "sticker not placed in the sea"
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        assert d["scene"]["items"].get("sea"), "backup is missing the sea stickers"
    await pg.evaluate("scene.items.sea = []; scene.bg = 'castle'; saveScene(); xp = __xp0"); await home(pg)

@test
async def print_scene(pg, mode):
    # "Print my scene": the sticker picture (background, decorations, her stickers) as a PDF for the fridge.
    await pg.evaluate("window.__xp0 = xp; xp = Math.max(xp, 40); scene.bg = 'beach'; scene.items.beach = []; saveScene(); go('book', true)")
    await pg.click("#scOpen")
    assert not await pg.is_visible("#scPrint"), "Print shown for an empty picture"
    await pg.click("#scTray button >> nth=0"); await pg.click("#scTray button >> nth=1")
    assert await pg.is_visible("#scPrint"), "no Print my scene button"
    plain = await pg.evaluate("(() => { const keep = scene.items.beach; scene.items.beach = []; const a = sceneCanvas().toDataURL(); scene.items.beach = keep; return a; })()")
    assert plain != await pg.evaluate("sceneCanvas().toDataURL()"), "stickers not drawn in the printed picture"
    assert await pg.evaluate("(() => { const c = sceneCanvas(); return c.width > c.height; })()"), "print should be landscape"
    await pg.click("#scPrint"); await pg.wait_for_timeout(2500)
    if mode == "web": names = [x["filename"] for x in await pg.evaluate("window.__saved")]
    else: names = [c["saved"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "saved" in c]
    assert any("Sticker_Scene" in n and n.endswith(".pdf") for n in names), f"scene PDF not saved ({names[-3:]})"
    await pg.evaluate("scene.items.beach = []; scene.bg = 'castle'; saveScene(); xp = __xp0"); await home(pg)

@test
async def sticker_sizes(pg, mode):
    # Tap a sticker on the picture to make it bigger (normal → bigger → biggest → normal). Saved, printed, and backed up.
    await pg.evaluate("window.__xp0 = xp; xp = Math.max(xp, 40); scene.bg = 'meadow'; scene.items.meadow = []; saveScene(); go('book', true)")
    await pg.click("#scOpen"); await pg.click("#scTray button >> nth=0")
    st = pg.locator("#scStage .sc-st").first
    size = lambda: pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#scStage .sc-st')).fontSize)")
    small = await size(); plain = await pg.evaluate("sceneCanvas().toDataURL()")
    await st.click(); assert await size() > small * 1.3 and await pg.evaluate("scene.items.meadow[0].z") == 1.5, "tap didn't make it bigger"
    assert await pg.evaluate("sceneCanvas().toDataURL()") != plain, "the print ignores sticker size"
    await pg.locator("#scStage .sc-st").first.click(); assert await pg.evaluate("scene.items.meadow[0].z") == 2, "second tap didn't make it biggest"
    await pg.locator("#scStage .sc-st").first.click(); assert not await pg.evaluate("scene.items.meadow[0].z > 1"), "third tap didn't go back to normal"
    assert abs(await size() - small) < 1, "size didn't come back"
    await pg.locator("#scStage .sc-st").first.click()
    assert await pg.evaluate("load('luna_scene').items.meadow[0].z") == 1.5, "size not saved"
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        d["scene"]["items"]["meadow"] = [{"id": "big1", "s": d["scene"]["items"]["meadow"][0]["s"], "x": .5, "y": .5, "z": 2},
                                         {"id": "bad z", "s": d["scene"]["items"]["meadow"][0]["s"], "x": .3, "y": .3, "z": 99}]
        await pg.evaluate("scene.items.meadow = []; saveScene()")
        await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
        await pg.wait_for_function("scene.items.meadow.length === 2", timeout=5000)
        got = await pg.evaluate("scene.items.meadow.map(i => [i.id, i.z || 1])")
        assert got[0] == ["big1", 2] and got[1][1] == 1 and got[1][0] != "bad z", f"restore didn't keep/clean sizes and ids: {got}"
    await pg.evaluate("scene.items.meadow = []; scene.bg = 'castle'; saveScene(); xp = __xp0"); await home(pg)

@test
async def bucket_bridges_gaps(pg, mode):
    # Kids' drawings rarely close: the 🪣 bucket bridges small gaps in her lines, fills right up to them, and big openings still let paint through.
    async def ring(gap_deg):
        return await pg.evaluate("""g => { pWall = null; px.fillStyle = '#fff'; px.fillRect(0, 0, pc.width, pc.height);
            px.strokeStyle = '#1E1033'; px.lineWidth = 8; px.beginPath(); px.arc(480, 360, 200, (g / 2) * Math.PI / 180, (360 - g / 2) * Math.PI / 180); px.stroke();
            floodFill(480, 360, '#FF0000'); const at = (x, y) => Array.from(px.getImageData(x, y, 1, 1).data.slice(0, 3));
            return { outside: at(900, 360), far: at(40, 40), nearLine: at(480 - 193, 360) }; }""", gap_deg)
    await pg.click("[data-go=studio]"); await pg.click("#stNew")
    small = await ring(2)  # about 7 px gap at the right edge
    assert small["outside"] == [255, 255, 255] and small["far"] == [255, 255, 255], f"paint leaked through a small gap: {small}"
    assert small["nearLine"] == [255, 0, 0], f"pale gap left next to the line: {small}"
    big = await ring(18)  # about 63 px opening
    assert big["far"] == [255, 0, 0], f"a big opening should let paint through: {big}"
    await pg.evaluate("px.clearRect(0, 0, pc.width, pc.height); pUndoStack = []"); await pg.click("#pCancel"); await home(pg)

@test
async def bonus_lessons(pg, mode):
    for lid in await pg.evaluate("LESSONS.filter(l => l.bonus).map(l => l.id)"):
        await pg.evaluate("go('school', true)"); await pg.click(f'[data-lesson="{lid}"]', force=True)
        for _ in range(await pg.evaluate("lsn.l.pages.length")): await solve_page(pg)
        await dismiss(pg)
        assert await pg.evaluate(f"!!stats.lessons['{lid}']"), f"bonus lesson {lid} not recorded"
    assert await pg.evaluate("LESSONS.some(l => l.id === 'practice4') && LESSONS.some(l => l.id === 'instants')"), "new bonus lessons missing"
    await home(pg)

@test
async def game_levels_and_trophies(pg, mode):
    await pg.evaluate("window.__quietCelebrations = false; stats.gxp = { pop: 9 }; go('pop', true); stars = 0; addStar(1)")
    await pg.wait_for_function("!document.getElementById('celebrate').classList.contains('hidden')", timeout=4000)
    assert "Faerie Pop: level 2" in await pg.inner_text("#celTitle"), "no game level-up celebration"
    assert await pg.evaluate("gameLevel('pop')") == 2 and await pg.evaluate("stars") == 4, "game level or bonus stars wrong"
    await pg.evaluate("window.__quietCelebrations = true"); await dismiss(pg)
    await pg.evaluate("go('lesson', true); addStar(1)")  # lessons don't count toward any game
    assert await pg.evaluate("Object.keys(stats.gxp).join()") == "pop", "stars outside games leaked into a game level"
    await pg.evaluate("stats.gxp = { fog: 30, echo: 100 }; go('stars', true)")
    txt = await pg.inner_text("#gGrid")
    assert "Spell Echo" in txt and "top level" in txt and "Level 3" in txt, "trophy grid wrong"
    await pg.evaluate("go('fog', true)"); assert await pg.locator("#fogOpts button").count() == 4, "Magic Fog level 3 should offer 4 choices"
    await pg.evaluate("stats.gxp = {}; go('fog', true)"); assert await pg.locator("#fogOpts button").count() == 3, "Magic Fog level 1 should offer 3 choices"
    await home(pg)

@test
async def celebrations_wait_for_the_round(pg, mode):
    # A level-up earned mid-round must not cover Spell Echo's next pattern or talk over Rootha Says.
    shown = "!document.getElementById('celebrate').classList.contains('hidden')"
    await pg.evaluate("window.__quietCelebrations = false; celebQueue.length = 0; stats.gxp = { echo: 9 }; echo.best = 99")
    await pg.click("[data-go=echo]"); await pg.click("#echoGo")
    for n in (1, 2, 3):
        await pg.wait_for_function(f"echo.on && !echo.busy && echo.seq.length === {n}", timeout=12000)
        for k in await pg.evaluate("echo.seq"): await pg.click(f'[data-pad="{k}"]')
    assert await pg.evaluate("gameLevel('echo')") == 2, "round 3's star didn't reach Spell Echo level 2"
    await pg.wait_for_timeout(1600)  # the queue used to open the overlay after 900 ms, over round 4's pattern
    assert await pg.evaluate("echo.on") and not await pg.evaluate(shown), "a celebration covered Spell Echo mid-game"
    await pg.wait_for_function("!echo.busy", timeout=12000)
    for _ in range(2):
        wrong = await pg.evaluate("['U','R','P','G'].find(k => k !== echo.seq[echo.pos])")
        await pg.click(f'[data-pad="{wrong}"]'); await pg.wait_for_timeout(200)
        if await pg.evaluate("echo.on"): await pg.wait_for_function("!echo.busy", timeout=12000)
    await pg.wait_for_function(shown, timeout=4000)
    assert "Spell Echo: level 2" in await pg.inner_text("#celTitle"), "the level-up never came after the game"
    await pg.click("#celOk")
    await pg.evaluate("stats.gxp = { says: 9 }; go('says', true)"); await pg.click("#saysPlay")
    await pg.evaluate("addStar(1)")  # a star for a right move, mid-game
    await pg.wait_for_timeout(1600)
    assert await pg.evaluate("saysOn") and not await pg.evaluate(shown), "a celebration interrupted Rootha Says"
    await pg.click("#saysPlay"); await pg.wait_for_function(shown, timeout=4000)
    assert "Rootha Says: level 2" in await pg.inner_text("#celTitle"), "Rootha Says level-up lost"
    await pg.evaluate("window.__quietCelebrations = true; stats.gxp = {}; echo.best = load('luna_echo_best', 0)"); await dismiss(pg); await home(pg)

@test
async def game_difficulty(pg, mode):
    await pg.evaluate("stats.gxp = { memory: 25, count: 25, battle: 25 }")
    await pg.click("[data-go=memory]"); assert await pg.locator("#memGrid .mcard").count() == 16, "Memory level 3 should have 8 pairs"
    await pg.evaluate("stats.gxp = {}; go('memory', true)"); assert await pg.locator("#memGrid .mcard").count() == 12, "Memory level 1 should have 6 pairs"
    await pg.evaluate("stats.gxp = { count: 25 }; go('count', true)")
    await pg.click("#cCost button >> nth=0"); assert await pg.inner_text("#cRun") == "?", "Count level 3 should hide the running total"
    # Who Wins twist: Prismari Command's 2 damage adds to the attacker's power
    await pg.evaluate("stats.gxp = { battle: 25 }; go('battle', true)")
    ok = await pg.evaluate("""(() => { for (let i = 0; i < 60; i++){ newBattle(); if (bTwist) break; }
      if (!bTwist) return 'no twist in 60 tries';
      const want = bAtk.p + 2 >= bDef.t;
      document.querySelector(`#battle .yesno .ans[data-yes="${want ? 1 : 0}"]`).click();
      return document.getElementById('bNext').classList.contains('hidden') ? 'right answer rejected' : (document.getElementById('bExplain').textContent.includes('2 + ') ? 'ok' : 'no sum shown'); })()""")
    assert ok == "ok", f"battle twist: {ok}"
    await pg.evaluate("stats.gxp = {}"); await home(pg)

STACK = None

async def stroke(pg):
    box = await pg.locator("#pCanvas").bounding_box()
    await pg.mouse.move(box["x"] + 60, box["y"] + 60); await pg.mouse.down(); await pg.mouse.move(box["x"] + 160, box["y"] + 140, steps=6); await pg.mouse.up()

@test
async def kid_friendly_asks(pg, mode):
    # Questions are a big spoken pop-up with picture buttons (never a browser dialog), and art is never lost by accident.
    await pg.click("[data-go=book]"); keep = await pg.evaluate("pets[pets.length - 1]"); n0 = await pg.evaluate("pets.length")
    await pg.click("#petBook .bk >> nth=0"); await pg.click("#pmDel")
    assert await pg.is_visible("#ask"), "removing a creature didn't ask"
    if mode == "android":
        spoken = [c["t"] for c in await pg.evaluate("window.__calls") if isinstance(c, dict) and "t" in c]
        assert spoken and keep["name"] in spoken[-1], f"question not read aloud: {spoken[-1:]}"
    await pg.wait_for_timeout(450)  # let the pop-in animation finish before measuring
    assert (await pg.locator("#askYes").bounding_box())["height"] >= 72, "answer buttons too small"
    await pg.click("#askNo"); assert await pg.evaluate("pets.length") == n0 and not await pg.is_visible("#ask"), "No removed it"
    await pg.click("#pmDel"); await pg.click("#askYes")
    assert await pg.evaluate("pets.length") == n0 - 1, "Yes didn't remove it"
    await pg.evaluate("p => { pets = pets.concat([p]); store('luna_pets', pets); }", keep); await home(pg)

    await pg.click("[data-go=studio]"); d0 = await pg.evaluate("drawings.length")
    await pg.click("#stNew"); await pg.click("#pCancel")
    assert not await pg.is_visible("#paint") and not await pg.is_visible("#ask"), "an empty page shouldn't ask"
    await pg.click("#stNew"); await stroke(pg)
    assert await pg.evaluate("window.__back()") == "stay" and await pg.is_visible("#paint"), "Back threw the painting away"
    assert await pg.is_visible("#ask"), "Back didn't ask about the painting"
    assert await pg.evaluate("window.__back()") == "stay" and await pg.is_visible("#paint") and not await pg.is_visible("#ask"), "Back on the question should just close it"
    await pg.click("#pClear"); assert await pg.is_visible("#ask"); await pg.click("#askNo")
    assert await pg.evaluate("px.getImageData(0, 0, pc.width, pc.height).data.some(v => v)"), "Keep drawing wiped the page"
    await pg.click("#pCancel"); await pg.click("#askYes"); await pg.click("#celOk")
    assert await pg.evaluate("drawings.length") == d0 + 1, "Keep it didn't save the painting"
    await pg.click("#stNew"); await stroke(pg); await pg.click("#pCancel"); await pg.click("#askNo")
    assert not await pg.is_visible("#paint") and await pg.evaluate("drawings.length") == d0 + 1, "Throw away saved it anyway"
    await pg.click("#stGallery .bk >> nth=0 >> .del"); await pg.click("#askYes")
    assert await pg.evaluate("drawings.length") == d0, "painting not removed"
    await home(pg)

    await pg.click("[data-go=night]")
    if await pg.is_visible("#ntStart"): await pg.click("#ntStart")
    await pg.click("#ntNew"); await pg.click("#askNo"); assert await pg.is_visible("#ntGame"), "Keep playing ended the game"
    await pg.click("#ntNew"); await pg.click("#askYes"); assert await pg.is_visible("#ntSetup"), "New game didn't reset"
    await home(pg)

@test
async def tablet_size_games(pg, mode):
    # On the tablet the games fill the screen (big targets for a bumpy car), and in landscape Start stays on screen.
    async def size(sel): b = await pg.locator(sel).first.bounding_box(); return b["width"], b["y"] + b["height"]
    try:
        await pg.set_viewport_size({"width": 800, "height": 1280})
        await pg.click("[data-go=echo]"); w, _ = await size(".pad"); assert w >= 300, f"Spell Echo pads only {w:.0f}px"
        await home(pg); await pg.click("[data-go=pop]"); w, _ = await size(".hole"); assert w >= 200, f"Faerie Pop pools only {w:.0f}px"
        await home(pg); await pg.click("[data-go=says]"); w, _ = await size("#saysFace"); assert w >= 240, f"Rootha only {w:.0f}px"
        await home(pg); await pg.click("[data-go=bubbles]"); await pg.wait_for_timeout(300)
        w, _ = await size(".bub"); assert w >= 100, f"bubbles only {w:.0f}px"
        h = (await pg.locator("#bubField").bounding_box())["height"]; assert h >= 600, f"bubble field only {h:.0f}px tall"
        await home(pg)
        await pg.set_viewport_size({"width": 1280, "height": 800})
        for game, btn in (("echo", "#echoGo"), ("pop", "#popGo")):
            await pg.click(f"[data-go={game}]"); _, bottom = await size(btn)
            assert bottom <= 800, f"{game}: Start is below the screen in landscape ({bottom:.0f}px)"
            await home(pg)
        await pg.click("[data-go=says]"); _, bottom = await size("#saysPlay"); assert bottom <= 800, f"says: Start below the screen ({bottom:.0f}px)"
        await home(pg)
    finally:
        await pg.set_viewport_size({"width": 400, "height": 860})
    await pg.click("[data-go=echo]"); w, _ = await size(".pad")
    assert w <= 200 and await pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "phone layout broke"
    await home(pg)

@test
async def small_phone_top_bar(pg, mode):
    # On a small phone (360px) the top bar fits on every screen: the ⭐ button and its level badge aren't pushed off the edge.
    try:
        await pg.set_viewport_size({"width": 360, "height": 640})
        # Big numbers (888 stars, Lv 12) make the ⭐ button its widest.
        off = await pg.evaluate("""(() => { const keep = [$('starCount').textContent, $('lvlBadge').textContent], out = [], fits = s => {
            if (document.documentElement.scrollWidth > innerWidth + 1) out.push(`${s}: page ${document.documentElement.scrollWidth}px wide`);
            document.querySelectorAll('.top > *').forEach(e => { const r = e.getBoundingClientRect();
              if (r.width && r.right > innerWidth + 1) out.push(`${s}: ${e.id} ends at ${Math.round(r.right)}px`); });
            const t = $('screenTitle').firstChild, rg = document.createRange(); let i = 0;  // no word split across two lines
            if (t) for (const w of t.textContent.split(' ')){ rg.setStart(t, i); rg.setEnd(t, i + w.length); i += w.length + 1;
              if (new Set([...rg.getClientRects()].map(q => Math.round(q.top))).size > 1) out.push(`${s}: "${w}" split across lines`); } };
          $('starCount').textContent = '888'; $('lvlBadge').textContent = 'Lv 12';
          for (const s of Object.keys(screens)){ if (s === 'lesson') continue; go(s, true); fits(s); }
          const longest = LESSONS.reduce((a, l) => l.title.length > a.title.length ? l : a);
          startLesson(longest.id); fits('lesson ' + longest.id);
          [$('starCount').textContent, $('lvlBadge').textContent] = keep;
          return [...new Set(out)]; })()""")
        assert not off, f"top bar doesn't fit at 360px: {off}"
    finally:
        await pg.set_viewport_size({"width": 400, "height": 860})
        await home(pg)

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
async def cloud_magic_words(pg, mode):
    if mode != "android": return
    await pg.click("[data-go=maker]"); await pg.evaluate("draft = newDraft(); renderMaker()")
    assert await pg.is_visible("#wordBox"), "magic words missing when AI pictures are on"
    for w in ["fluffy", "rainbow", "sleepy", "silly"]: await pg.click(f'#wordRow [data-w="{w}"]')
    assert await pg.evaluate("draft.words.join(',')") == "fluffy,rainbow,sleepy", "should keep at most three magic words"
    await pg.click('#wordRow [data-w="sleepy"]'); assert await pg.evaluate("draft.words.length") == 2, "tapping a word again should remove it"
    await pg.click('#sceneRow [data-bg="space"]')
    await pg.click("#artAI"); await pg.wait_for_function("draft.artBy === 'ai'", timeout=8000)
    from stack import FakeAzure
    gen = json.loads([b for p, b in FakeAzure.seen if "/images/generations" in p][-1])["prompt"]
    assert "fluffy" in gen and "rainbow" in gen and "outer space" in gen and "sleepy" not in gen, f"prompt missed her words: {gen[:160]}"
    await home(pg)

@test
async def cloud_drawing_magic(pg, mode):
    if mode != "android": return
    await pg.click("[data-go=maker]"); await pg.evaluate("draft = newDraft(); renderMaker()")
    assert not await pg.is_visible("#artRemix"), "repaint shown before there is a drawing"
    await pg.evaluate("draft.art = document.createElement('canvas').toDataURL('image/jpeg', .8); draft.artBy = 'draw'; renderMaker()")
    assert await pg.is_visible("#artRemix"), "Make my drawing magic missing"
    mine = await pg.evaluate("draft.art")
    await pg.click("#artRemix"); await pg.wait_for_function("draft.artBy === 'remix'", timeout=8000)
    assert await pg.is_visible("#artUndo"), "no way back to her own drawing"
    await pg.click("#artUndo"); assert await pg.evaluate("draft.art") == mine and await pg.evaluate("draft.artBy") == "draw", "undo didn't restore her drawing"
    await home(pg)

@test
async def remixed_creature_keeps_her_drawing(pg, mode):
    # After saving a "made magic" creature, editing it still offers ↩️ My drawing; restore checks the kept drawing.
    if mode == "android":
        await pg.click("[data-go=maker]")
        await pg.evaluate("draft = newDraft(); draft.name = 'Remix Test'; draft.art = document.createElement('canvas').toDataURL('image/jpeg', .8); draft.artBy = 'draw'; renderMaker()")
        mine = await pg.evaluate("draft.art")
        await pg.click("#artRemix"); await pg.wait_for_function("draft.artBy === 'remix'", timeout=8000)
        await pg.click("#savePet"); await dismiss(pg)
        await pg.evaluate("modalPet = pets.find(p => p.name === 'Remix Test'); $('pmEdit').click()")
        assert await pg.is_visible("#artUndo"), "her drawing is gone after saving the magic version"
        await pg.click("#artUndo"); assert await pg.evaluate("draft.art") == mine, "↩️ didn't bring back her own drawing"
        # an AI picture stays an AI picture after saving: no "make my drawing magic" on it
        await pg.evaluate("draft.artBy = 'ai'; delete draft.artOrig; $('savePet').click()"); await dismiss(pg)
        await pg.evaluate("modalPet = pets.find(p => p.name === 'Remix Test'); $('pmEdit').click()")
        assert not await pg.is_visible("#artRemix"), "an AI picture was offered as her drawing to repaint"
        await pg.evaluate("editId = null; pets = pets.filter(p => p.name !== 'Remix Test'); store('luna_pets', pets)"); await home(pg)
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        img = await pg.evaluate("document.createElement('canvas').toDataURL('image/jpeg', .8)")
        base = {"kind": "unicorn", "color": "P", "p": 1, "t": 1, "power": "fly"}
        d["pets"] = [dict(base, id="rmx1", name="Kept", art=img, artBy="remix", artOrig=img),
                     dict(base, id="rmx2", name="Odd", art=img, artBy="remix", artOrig='data:image/png;base64,AA" onerror="x', ),
                     dict(base, id="rmx3", name="Weird", art=img, artBy="<b>")]
        await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
        await pg.wait_for_function("pets.some(p => p.name === 'Weird')", timeout=5000)
        got = await pg.evaluate("Object.fromEntries(pets.filter(p => p.id.startsWith('rmx')).map(p => [p.name, [p.artBy || '', !!p.artOrig]]))")
        assert got == {"Kept": ["remix", True], "Odd": ["", False], "Weird": ["", False]}, f"restore kept bad art fields: {got}"
        await pg.evaluate("pets = pets.filter(p => !p.id.startsWith('rmx')); store('luna_pets', pets)"); await home(pg)

@test
async def creature_keeps_magic_words(pg, mode):
    # Her magic words are saved with the creature (and checked on restore), so editing it to repaint keeps them.
    if mode == "android":
        await pg.click("[data-go=maker]"); await pg.evaluate("draft = newDraft(); draft.name = 'Word Test'; renderMaker()")
        for w in ["fluffy", "sleepy"]: await pg.click(f'#wordRow [data-w="{w}"]')
        await pg.click("#savePet"); await dismiss(pg)
        await pg.evaluate("modalPet = pets.find(p => p.name === 'Word Test'); $('pmEdit').click()")
        on = await pg.evaluate("[...document.querySelectorAll('#wordRow .pick.on')].map(b => b.dataset.w).join()")
        assert on == "fluffy,sleepy", f"her magic words were lost on save: {on!r}"
        await pg.evaluate("editId = null; pets = pets.filter(p => p.name !== 'Word Test'); store('luna_pets', pets)"); await home(pg)
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        d["pets"] = [{"id": "wrd1", "kind": "unicorn", "color": "P", "p": 1, "t": 1, "power": "fly", "name": "Wordy",
                      "words": ["fluffy", "<b>", "fluffy", "tiny", "giant", "happy"]},
                     {"id": "wrd2", "kind": "unicorn", "color": "P", "p": 1, "t": 1, "power": "fly", "name": "Wordless", "words": "fluffy"}]
        await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
        await pg.wait_for_function("pets.some(p => p.name === 'Wordless')", timeout=5000)
        got = await pg.evaluate("Object.fromEntries(pets.filter(p => p.id.startsWith('wrd')).map(p => [p.name, (p.words || []).join()]))")
        assert got == {"Wordy": "fluffy,tiny,giant", "Wordless": ""}, f"restore kept bad magic words: {got}"
        await pg.evaluate("pets = pets.filter(p => !p.id.startsWith('wrd')); store('luna_pets', pets)"); await home(pg)

@test
async def cloud_painting_magic(pg, mode):
    if mode != "android": return
    await pg.evaluate("drawings.push({ id: 'p-test', img: document.createElement('canvas').toDataURL('image/jpeg', .8), at: Date.now() }); store('luna_drawings', drawings)")
    n = await pg.evaluate("drawings.length")
    await pg.evaluate("go('studio', true)")
    await pg.click('[data-magic="p-test"]')
    await pg.wait_for_function(f"drawings.length === {n + 1}", timeout=8000)
    assert await pg.evaluate("drawings[drawings.length - 1].magic === 'p-test'"), "magic painting not linked to the original"
    assert await pg.evaluate("drawings.some(d => d.id === 'p-test')"), "the original painting must be kept"
    await dismiss(pg); await home(pg)

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
async def voice_cache(pg, mode):
    # Cloud-voice phrases she has heard are kept on the tablet, so they still play when the car loses signal.
    if mode != "android": return
    tts = lambda: len([x for x in FakeAzure.seen if "cognitive" in x[0]])
    await pg.evaluate("document.querySelector('.grownup').open = true"); await pg.click("[data-cv=all]")
    n0 = tts(); await pg.evaluate("ttsCache.clear(); say('Sparkle sparkle, cache me!')")
    for _ in range(40):  # evaluate() awaits the IndexedDB promise (wait_for_function would not)
        if await pg.evaluate("voiceDB.get(voiceKey('Sparkle sparkle, cache me!')).then(v => !!(v && v.blob))"): break
        await pg.wait_for_timeout(200)
    else: raise AssertionError("phrase never stored on the tablet")
    assert tts() > n0, "phrase never fetched from the server"
    await pg.wait_for_timeout(500); n1 = tts()
    real = await pg.evaluate("cloud.url")
    try:
        await pg.evaluate("cloud.url = 'http://127.0.0.1:9'; ttsCache.clear()")  # the car lost signal
        calls0 = await pg.evaluate("window.__calls.length")
        await pg.evaluate("say('Sparkle sparkle, cache me!')"); await pg.wait_for_timeout(1200)
        fell_back = await pg.evaluate(f"window.__calls.slice({calls0}).some(c => c && c.t === 'Sparkle sparkle, cache me!')")
        assert not fell_back, "cached phrase fell back to the tablet voice while offline"
        assert tts() == n1, "cached phrase went to the server instead of the tablet's store"
        await pg.evaluate("say('A brand new phrase')"); await pg.wait_for_timeout(1500)
        assert await pg.evaluate(f"window.__calls.slice({calls0}).some(c => c && c.t === 'A brand new phrase')"), "uncached phrase didn't fall back to the tablet voice"
        # the store keeps only the newest clips
        left = await pg.evaluate("""(async () => { const b = new Blob(['x']);
          await voiceDB.put('old-1', { blob: b, at: 1 }); await voiceDB.put('old-2', { blob: b, at: 2 });
          const n = (await voiceDB.keys()).length; await trimVoices(n - 2); return voiceDB.keys(); })()""")
        assert "old-1" not in left and "old-2" not in left and await pg.evaluate("voiceKey('Sparkle sparkle, cache me!')") in left, f"trim removed the wrong clips: {left}"
    finally:
        await pg.evaluate("u => { cloud.url = u; }", real); await pg.click("[data-cv=off]")
    await home(pg)

@test
async def magic_movies(pg, mode):
    if mode != "android": return
    await pg.evaluate("clipPollMs = 300")
    starts0 = len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]])
    await pg.evaluate("openViewer(CARDS.find(c => c.name === 'Goldspan Dragon'))")
    assert await pg.is_visible("#vMake"), "Make it move button missing"
    await pg.click("#vMake")
    await pg.wait_for_function("clipKeys.has('card:Goldspan Dragon')", timeout=40000)  # the fake Veo job can lag under load
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


@test
async def movie_night_plays(pg, mode):
    # With a real clip (made by the fake Veo in magic_movies), Movie night plays it to the end and then moves on.
    if mode != "android": return
    await pg.evaluate("CARDS.forEach(c => { if (clipKeys.has(clipKeyFor(c))) cast[c.name] = cast[c.name] || 1; }); go('book', true)")
    lst = await pg.evaluate("theaterList().map(c => c.name)")
    assert lst, "no real clip to play"
    await pg.evaluate("""theater.list = theaterList().slice(0, 1); $('theater').classList.remove('hidden'); window.__ended = false; theaterAt(0);
        const iv = setInterval(() => { const v = document.querySelector('#thMedia video'); if (v){ v.addEventListener('ended', () => { window.__ended = true; }); clearInterval(iv); } }, 20);""")
    await pg.wait_for_function("document.getElementById('thName').textContent.includes('The end')", timeout=12000)
    assert await pg.evaluate("window.__ended"), "Movie night moved on without the clip playing to the end"
    await pg.click("#thStop"); await home(pg)


@test
async def rootha_movies_shelf(pg, mode):
    # Rootha's shorts: the family's own movies come from the server, stay on the device, and play with sound at normal speed.
    if mode == "web":
        await pg.evaluate("go('book', true)"); assert not await pg.is_visible("#shortsSec"), "Rootha's movies shown with no server"
        return await home(pg)
    await pg.evaluate("go('book', true); syncShorts()")
    await pg.wait_for_function("document.querySelectorAll('#shortRow .short').length === 2", timeout=15000)
    names = await pg.evaluate("[...document.querySelectorAll('#shortRow .short > span')].map(t => t.firstChild.textContent.trim())")  # the title, not its NEW tag
    assert names == ["Rootha's big movie", "Hello  b from /b  Rootha"], f"shelf shows the wrong movies: {names}"
    box = await pg.locator("#shortRow .short").first.bounding_box(); assert box["height"] >= 52 and box["width"] >= 120, f"movie tile too small: {box}"
    await pg.evaluate("""window.__ended = false; const iv = setInterval(() => { const v = document.querySelector('#thMedia video');
        if (v){ window.__vid = { muted: v.muted, rate: v.playbackRate }; v.addEventListener('ended', () => { window.__ended = true; }); clearInterval(iv); } }, 20);""")
    await pg.click('#shortRow [data-short="film"]'); assert await pg.is_visible("#theater"), "tapping a movie didn't open the theater"
    await pg.wait_for_function("document.getElementById('thName').textContent.includes('The end')", timeout=15000)
    vid = await pg.evaluate("window.__vid")
    assert vid and vid["muted"] is False and vid["rate"] == 1, f"Rootha's voice must play with sound at normal speed: {vid}"
    assert await pg.evaluate("window.__ended"), "the movie didn't play to the end"
    await pg.click("#thStop")
    # a restart, then a sync with the server, then offline after another restart: the movies are still on the device
    await pg.evaluate("shortsIndex = []; shortHave.clear(); loadShorts().then(syncShorts)")
    await pg.wait_for_function("!shortsBusy && document.querySelectorAll('#shortRow .short').length === 2", timeout=15000); await pg.wait_for_timeout(300)
    await pg.evaluate("window.__url = cloud.url; cloud.url = 'http://127.0.0.1:9'; cloudCaps = null; shortsIndex = []; shortHave.clear(); renderShorts()")
    assert not await pg.is_visible("#shortsSec"), "renderShorts didn't reset"
    await pg.evaluate("loadShorts()"); await pg.wait_for_function("document.querySelectorAll('#shortRow .short').length === 2", timeout=5000)
    await pg.evaluate("cloud.url = window.__url; cloudConnect(true)"); await home(pg)

@test
async def new_movie_badge(pg, mode):
    # A gold 🎬 NEW on My Spellbook (and on the movie) until she watches it; watched ones are kept in backups.
    if mode == "web":
        await pg.evaluate("go('book', true)"); d = await fresh_backup(pg)
        d["seen"] = {"short:film": 1, "short:../x": 1, "short:<b>": 1}
        await pg.set_input_files("#bkFile", files=[{"name": "b.json", "mimeType": "application/json", "buffer": json.dumps(d).encode()}])
        await pg.wait_for_function("!!seenGames['short:film']", timeout=5000)
        assert not await pg.evaluate("Object.keys(seenGames).some(k => k.startsWith('short:') && k !== 'short:film')"), "restore kept a bad movie id"
        await pg.evaluate("delete seenGames['short:film']; store('luna_seen', seenGames)"); return await home(pg)
    await pg.evaluate("Object.keys(seenGames).filter(k => k.startsWith('short:')).forEach(k => delete seenGames[k]); store('luna_seen', seenGames); syncShorts()")
    await pg.wait_for_function("document.querySelectorAll('#shortRow .short').length === 2 && !shortsBusy", timeout=15000)
    await home(pg); assert await pg.is_visible("#movieTag"), "no NEW on My Spellbook for new movies"
    await pg.evaluate("go('book', true)")
    assert await pg.locator('#shortRow [data-short="hello"] .newtag').count() == 1, "an unwatched movie has no NEW"
    await pg.click('#shortRow [data-short="hello"]'); await pg.click("#thStop")
    assert await pg.locator('#shortRow [data-short="hello"] .newtag').count() == 0, "NEW stayed on a watched movie"
    await home(pg); assert await pg.is_visible("#movieTag"), "NEW on My Spellbook went away with a movie still unwatched"
    await pg.evaluate("go('book', true)"); await pg.click('#shortRow [data-short="film"]'); await pg.click("#thStop")
    await home(pg); assert not await pg.is_visible("#movieTag"), "NEW stayed on My Spellbook after every movie was watched"
    assert await pg.evaluate("!!load('luna_seen', {})['short:film']"), "watched movies weren't saved"

@test
async def painting_movies(pg, mode):
    # Art Studio paintings can become magic movies too (fake Veo), and join Movie night.
    if mode != "android": return
    await pg.evaluate("clipPollMs = 300")
    pid = await pg.evaluate("""(() => { const cv = document.createElement('canvas'); cv.width = 640; cv.height = 480; const x = cv.getContext('2d');
        x.fillStyle = '#fff'; x.fillRect(0, 0, 640, 480); x.fillStyle = '#C77DFF'; x.beginPath(); x.arc(320, 240, 120, 0, 7); x.fill();
        const d = { id: 'pm' + Date.now().toString(36), img: cv.toDataURL('image/jpeg', 0.8), at: Date.now() };
        drawings = drawings.concat([d]); store('luna_drawings', drawings); return d.id; })()""")
    await pg.click("[data-go=studio]")
    btn = pg.locator(f'#stGallery [data-movie="{pid}"]')
    assert await btn.count() == 1, "no movie button on the painting"
    await btn.click(); assert await pg.is_visible("#vMake"), "Make it move missing for a painting"
    n0 = len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]])
    await pg.click("#vMake")
    key = await pg.evaluate(f"clipKeyFor(paintingCard(drawings.find(d => d.id === '{pid}')))")
    assert key.startswith("painting:"), key
    await pg.wait_for_function(f"clipKeys.has({json.dumps(key)})", timeout=15000)
    sent = json.loads([x for x in FakeAzure.seen if "predictLongRunning" in x[0]][-1][1])
    assert len([x for x in FakeAzure.seen if "predictLongRunning" in x[0]]) == n0 + 1 and "painting" in sent["instances"][0]["prompt"], "painting prompt not sent"
    await pg.click("#vClose")
    assert key in await pg.evaluate("theaterList().map(clipKeyFor)"), "painting movie not in Movie night"
    await pg.click(f'#stGallery .bk:has([data-movie="{pid}"]) .del'); await pg.click("#askYes")
    assert not await pg.evaluate(f"clipKeys.has({json.dumps(key)})"), "removing the painting left its movie behind"
    await home(pg)
@test
async def generated_icons(pg, mode):
    # Home tiles, the title bar, and the weekly challenge show drawn SVG badges, not emoji (older tablets lack some emoji).
    await home(pg)
    bad = await pg.evaluate("""[...document.querySelectorAll('.game-btn:not(.hidden)')].filter(b => {
        const ico = b.querySelector('.ico'), svg = ico && ico.querySelector('svg.gico');
        return !svg || [...ico.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) || ico.offsetWidth < 40; }).map(b => b.dataset.go)""")
    assert not bad, f"tiles without a drawn badge: {bad}"
    ids = await pg.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id).filter((x, i, a) => a.indexOf(x) !== i)")
    assert not ids, f"duplicate ids (badge gradients would collide): {ids[:5]}"
    missing = await pg.evaluate("[...document.querySelectorAll('svg.gico [fill^=\"url(#\"]')].map(e => e.getAttribute('fill').slice(5, -1)).filter(id => !document.getElementById(id))")
    assert not missing, f"badge fills point at missing gradients: {missing[:3]}"
    assert await pg.evaluate("!!document.querySelector('#chalEmo svg') || document.getElementById('chalCard').classList.contains('done')"), "weekly challenge has no badge"
    label = await pg.get_attribute("#voiceBtn", "aria-label")
    assert await pg.locator("#voiceBtn svg").count() == 1 and await pg.locator("#homeBtn svg").count() == 1, "top bar icons not drawn"
    await pg.click("#voiceBtn"); assert await pg.get_attribute("#voiceBtn", "aria-label") != label and await pg.locator("#voiceBtn svg").count() == 1, "voice icon did not switch"
    await pg.click("#voiceBtn"); assert await pg.get_attribute("#voiceBtn", "aria-label") == label, "voice did not switch back"
    await pg.evaluate("go('memory', true)")
    assert await pg.locator("#screenIco svg.gico").count() == 1, "game screen title has no badge"
    await home(pg)
    assert await pg.evaluate("document.getElementById('screenIco').innerHTML === ''"), "home title bar kept a game badge"

async def run_mode(browser, mode):
    ctx = await browser.new_context(viewport={"width": 400, "height": 860}, has_touch=True)
    await ctx.add_init_script("window.__quietCelebrations = true; window.__noDailyHello = true;" + (FAKE_CLAUDE if mode == "web" else FAKE_ANDROID) + "if(!localStorage.getItem('luna_pets')){" + SEED_PETS + "}")
    pg = await ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # A young child can't read a browser dialog: any confirm()/alert() a test reaches is a failure.
    pg.on("dialog", lambda d: (errors.append(f"native {d.type} dialog: {d.message}"), asyncio.ensure_future(d.dismiss())))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "fonts.g" not in m.text and "ERR_" not in m.text and not m.text.startswith("Failed to load resource") else None)
    await pg.goto(WEB if mode == "web" else AND); await pg.wait_for_timeout(700)
    fails = 0
    for fn in results:
        if ONLY and fn.__name__ not in ONLY: continue
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
        modes = [m for m in os.environ.get("SMOKE_MODES", "web,android").split(",") if m]  # e.g. SMOKE_MODES=android
        fails = 0
        for m in modes: fails += await run_mode(b, m)
        await b.close()
    STACK.close()
    print("\n" + ("All smoke tests passed." if not fails else f"{fails} smoke test(s) failed. Screenshots in build/test-shots/"))
    sys.exit(1 if fails else 0)

asyncio.run(main())
