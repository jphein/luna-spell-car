# Changelog

## Unreleased

## 1.6.0 (2026-10-15)
- Three new mini games: 🎵 Spell Echo (copy the color-and-sound pattern; gets longer and faster), 🧚 Faerie Pop
  (30-second catch-the-faeries, unicorns worth 3, don't wake the owl), 🌫️ Magic Fog (guess who's hiding as the fog clears).
- Levels: ten wizard ranks from Apprentice to Planeswalker, earned from lifetime stars, with a level-up celebration and
  +5 bonus stars. Level shown in the top bar and on the home screen.
- ⭐ Star Shop (tap the star counter): 6 new creatures, 6 accessories, 4 app color themes, and 3 Art Studio brushes
  (gold glitter, unicorn stamp, star stamp). Two taps to buy. Spending never lowers levels or stickers.
- 🔮 Six hidden secrets (+5 stars each) with hints in My Spellbook; seasonal decorations (Halloween week, December).
- Backup v3 carries levels, purchases, secrets, and theme. Server accepts the new creatures and accessories.
- Fixes: Faerie Pop style clash; "No creatures yet" wrapping. New static check catches CSS class clashes.

## 1.5.0 (2026-10-14)
- 🎬 Magic movies with Google Veo: tap a card in My Spellbook (or 🎬 on a creature) → Make it move. Clips play
  in the cast celebration, stretch 8 s → 10 s, keep a sound toggle, and are stored on the device for offline play.
  Grown-ups can make all 14 deck cards move at once. Clips are shared across devices without paying twice.
- Spell Car server: `/animate` + background Veo poller, disk cache, `VIDEOS_PER_DAY` cap, Docker volume for clips.
- Tests: fake Veo (long-running operations + a real WebM clip), 11 new server tests, end-to-end movie smoke test.

## 1.4.0 (2026-10-14)
- Mana Bubbles: 🐢 Slow / 🐇 Normal / ⚡ Fast speed, remembered; switching restarts the bubbles at the new speed.
- Game Night: turn helper. "Next turn" passes to the next player who's still in, highlights their panel, and reads the turn steps (Untap, Draw, Land, Cast spells, Attack!, Done); "Who goes first?" starts the first turn.
- Quiet car mode in For grown-ups: voice only, no chimes.
- Nightly iteration setup: CLAUDE.md, routine prompt, cloud setup script, FEEDBACK.md inbox.

## 1.3.0 (2026-10-14)
- Spell Car server (`server/`): self-hosted, stdlib-only bridge to Azure OpenAI and Azure AI Speech. Keys stay on the server; endpoints accept only structured input; daily caps; Docker Compose.
- Tablet app: Story Time via the server, 🪄 AI picture in Make a Creature, neural cloud voices (Ana, Jenny, Aria, Ava, Emma, Guy) for stories or everything, with automatic fallback to the tablet voice.
- Android: INTERNET permission (used only for the optional server).
- Tests: fake Azure stack, 15 server tests, cloud smoke tests through the Android build.
- `make dev` prints the computer's real LAN address for opening on the tablet.

## 1.2.0 (2026-10-14)
- Art Studio: free painting with a saved gallery (tap a painting to keep working on it); paintings are included in backups.
- Development cycle: VERSION file, `make dev` live-reload server, `make test` (static checks + Playwright smoke tests for web and Android builds), `make release`, `make install`, CI workflow.
- Version number shown in the For grown-ups panel.

## 1.1.0 (2026-10-14)
- Mana Bubbles, Game Night (life counter + dice), draw-your-own creature art, backup & restore, Android file picker.
- Fix: Story Time character picker wraps instead of scrolling sideways.

## 1.0.0 (2026-10-14)
- First Android build: native TTS bridge, voice settings, offline assets, printable creature cards.
- Games: Window Magic, Make a Creature, Story Time (web), Memory Match, Count the Mana, Who Wins?, Rootha Says, My Spellbook.
