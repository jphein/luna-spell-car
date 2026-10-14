# Luna's Spell Car ✨

A car-friendly Magic: The Gathering learning app for a young child, built around her
**Prismari Artistry** Commander deck. Every prompt is read aloud, buttons are big, and
most games work without reading.

## Games

| Game | What it teaches |
|---|---|
| **Window Magic** | Spot blue/red/purple things outside to build a mana pool, then cast cards she can afford. Real cost rules: colored symbols need that color, gray numbers take any color. |
| **Make a Creature** | Design a creature card (kind, picture, color, power/toughness, special power, accessory, name). **Draw it myself** opens a paint canvas (crayon, rainbow, sparkle and heart brushes, trace-along guide). Stronger creatures cost more. Saved creatures show up in every other game. |
| **Mana Bubbles** | Pop floating blue/red bubbles to fill a card's cost slots; colored slots need that color, gray slots take any. |
| **Story Time** | Claude writes a gentle story starring her creatures, read aloud with sentence highlighting. *Web version only (uses the claude.ai `sample` capability).* |
| **Memory Match** | Flip-and-find pairs with deck art and her creatures. |
| **Count the Mana** | Tap each mana symbol to count it, then pick the total. |
| **Who Wins?** | Power vs. toughness, with dots to compare. |
| **Rootha Says** | Simon Says read aloud; eyes-free. |
| **Game Night** | Life counter for real games: 2–4 players, 20 or 40 life, ±1/±5, "face each other" flip for tablets on the table, d6/d20, coin, who goes first. |
| **My Spellbook** | Stickers every 10 stars, her creatures (tap to edit), cards she's cast, **Print my creatures** (real-card-size PDF, 63 × 88 mm, 9 per US Letter page), and **Backup / Restore** (JSON file; restore merges and never deletes). |

## Layout

```
web/app.html          the whole app (HTML/CSS/JS); __CARDS__ is filled from cards.json
web/cards.json        deck cards with embedded art (base64 JPEG)
web/tts-shim.js       maps the Web Speech API onto Android's native TextToSpeech
web/build.py          builds dist/web/index.html and android/assets/
web/fonts, web/vendor bundled Fredoka font and jsPDF 2.5.1 for offline use
android/              manifest, MainActivity (WebView + TTS + file bridge), PdfProvider, icons
build_apk.sh          Gradle-free build: aapt2 → javac → d8 → zipalign → apksigner
```

## Build

Requirements: JDK 17+, Python 3, Android SDK with `platforms;android-34` and `build-tools;34.0.0`.

```bash
export ANDROID_HOME=/path/to/android-sdk
./build_apk.sh                      # → build/luna-spell-car.apk
VERSION_NAME=1.1.0 VERSION_CODE=2 ./build_apk.sh   # bump for updates
python3 web/build.py                # web only → dist/web/index.html
```

The APK is signed with `android/luna-debug.keystore` (password `android`, alias `luna`).
It's a throwaway family key, committed on purpose so any machine can build an update that
installs over the old one. Bump `VERSION_CODE` for each update.

## Install on the tablet

1. Copy `luna-spell-car.apk` to the tablet (USB, Drive, email, or `adb install`).
2. Open it and allow "Install unknown apps" for whichever app opened it.
3. Fire tablets: Settings → Security & Privacy → Apps from Unknown Sources.

## Text-to-speech

Android's WebView has no `speechSynthesis`, so `tts-shim.js` replaces it with a bridge to the
system `TextToSpeech` engine (`AndroidBridge.speak/stop/voices`), including end-of-speech
callbacks so Rootha Says and Story Time pace correctly. In the app's **For grown-ups** panel:
reading speed, voice picker, and a shortcut to the tablet's voice settings. For better voices,
install/update **Speech Services by Google** and download a high-quality English voice there.

## Notes

- Saved data (stars, creatures, stories) lives in each device's local storage. Use **My Spellbook → Backup**
  to move it between the tablet and the web version.

## Changelog

- **1.1.0** Mana Bubbles, Game Night, draw-your-own creature art, backup & restore, Android file picker,
  Story Time character picker wraps instead of scrolling sideways.
- **1.0.0** First Android build: native TTS bridge, voice settings, offline assets, printable cards.
- Card art is © Wizards of the Coast via Scryfall. This is unofficial fan content for personal family
  use; keep the repo private.
