# Luna's Spell Car — instructions for Claude Code

A learn-to-play Magic: The Gathering app for Luna, a young child, built around her Prismari Artistry deck.
Used in the car on an Android tablet and on claude.ai. Read DEVELOPMENT.md for the full workflow.

## Map
- `web/app.html` — the entire app (HTML/CSS/JS, no framework). `__CARDS__` and `__VERSION__` are filled by `web/build.py`.
- `web/tts-shim.js` — Web Speech API → Android TextToSpeech bridge (Android build only).
- `android/` — WebView shell: `MainActivity.java` (TTS, file save/pick, back button), `PdfProvider.java`.
- `server/spellcar_server.py` — optional self-hosted Azure bridge (stories, pictures, neural voices). Stdlib only.
- `tests/smoke.py` — Playwright tests that play every game in the web build (fake claude.ai) and Android build
  (fake AndroidBridge + fake Azure from `tests/stack.py`). `tests/test_server.py` — server tests.
- `tools/check.py` — static checks. `FEEDBACK.md` — notes from real play sessions. `ROADMAP.md` — backlog.

## Commands
- `make test` — must pass before any commit (static checks + server tests + browser smoke tests).
- `make dev` — live-reload server. `make apk` — needs the Android SDK; CI builds it, routines don't need to.

## Rules
- One `@test` in `tests/smoke.py` per feature; write it first. Never weaken or delete a test to get green.
- Saved data only through `load()`/`store()` with a `luna_` key; new kinds of data must be added to Backup/Restore.
- The Android build is offline-first. Network features go only through the Spell Car server, degrade gracefully when
  it's unreachable, and get fake-Azure coverage. Never add API keys, secrets, or new external hosts to the app.
- No ads, analytics, external links, chat, accounts, or data collection. This is a child's app.
- Content for a young child: gentle, kind, never scary or sad, no villains. Every prompt must be speakable with `say()`.
  Big tap targets (≥ 52px). A game must be playable without reading.
- Keep `web/app.html` under the size budget in `tools/check.py`. Match the existing style (Fredoka, purple palette).
- Don't bump VERSION, tag, run `make release`, or touch `android/luna-debug.keystore`; releases are done by a human.
- Card art is © Wizards of the Coast (personal use). Don't add new copyrighted art or characters.
