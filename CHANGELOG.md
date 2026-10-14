# Changelog

## Unreleased
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
