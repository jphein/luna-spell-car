# Changelog

## Unreleased
- 🏰 Make a Creature: "Where does it live?" puts the magic picture in a castle, on a beach, in space, or in a meadow
  (or the original sparkles). Older creatures look exactly the same, and their movie clips still match.
- 🧜‍♀️ The Mermaid joins the Star Shop creatures (15 stars). The Spell Car server can draw and animate her.
- Going public as free fan content: the Wizards Fan Content Policy notice is in For grown-ups and the README, the
  README is rewritten for the public (install from Releases, screenshots, offline by default, credits and licenses),
  Fredoka's OFL license now ships with the font, and public files no longer mention the kids' ages or names.

## 1.9.0 (2026-10-15)
- **Fixes:** leaving Treasure Catch mid-round could hide Start when she came back (in 1.8.0). Please update from 1.8.0.
- 🌷 Three new secrets (nine in all): wake Faerie Pop's sleepy owl, catch three gems in one Treasure Catch round, and
  finish a lesson with your eyes closed. Finding every secret opens the hidden **Secret Garden** colors (pink and
  green, with drifting petals) in the Star Shop. Secrets found mid-game celebrate after the round, not over it.
- Seasonal and garden decorations now float behind the app instead of over the game tiles.
- 🗓️ Weekly challenge: a different goal each week (catch 20 faeries, cast 5 spells, win Memory Match twice, …) shown on
  home and read aloud when tapped. Finishing earns a special sticker (its own row in My Spellbook) and +5 stars.
  Missing a week costs nothing. Progress and challenge stickers are in backups.
- New static check: released CHANGELOG sections must match what the last tag shipped (the `merge=union` rule can
  slide an Unreleased line into a release during a rebase; this catches it).
- 🌞 Daily hello: the first time she opens Spell Car each day, Rootha says good morning, afternoon, or evening with a
  little gift (+2 stars). No streaks, nothing to lose by skipping a day.
- 🖍️ Coloring pages in Art Studio: six line drawings to color (heart, star, flower, rainbow, castle, butterfly). The new
  🪣 paint bucket fills a space with one tap and stops at the lines (it also works on her own paintings). Finished pages
  save to her gallery with the lines on top.

## 1.8.0 (2026-10-15)
- 💰 New mini game, **Treasure Catch**: Goldspan Dragon flies across the night sky dropping coins (+1) and gems (+3);
  slide the big basket to catch them. 30-second rounds, nothing to lose, stars like Faerie Pop, and a best score
  (kept in progress stats, so it's in backups).
- "NEW" tags on small home tiles now look like the wide ones (gold pill).
- 🛡️ Magic School bonus lesson: **Practice Turn 3**, Dad's turn: pick the best blocker, only flyers block flyers,
  sometimes it's smarter to take a little damage, and a double block.
- 🎧 Eyes-closed mode now plays every lesson whole: putting a turn in order, paying with lands, and finding the parts of
  a card become spoken two-choice questions ("Where is the mana cost on a card? Tap blue for in the top corner…").
- 📶 Cloud voice works offline for phrases she's heard: neural-voice clips are kept on the tablet (newest 400) and
  played from there first, so lessons and games keep their voice when the car loses signal. New phrases still fall
  back to the tablet voice. The cache is re-fetchable, so it isn't part of backups.
- 🏠 Home in landscape shows three games per row; an odd game out spans its whole row instead of sitting alone.
- 🎧 Eyes-closed car mode in Magic School: "Listen with eyes closed" plays any lesson as voice only. Pages turn by
  themselves, and she answers by tapping the big blue half or red half of the screen ("Tap blue for Library. Tap red
  for Graveyard."). Finishing one earns a star.
- 🐲 Magic School bonus lesson: **Practice Turn 2**, a harder guided turn: pay for Goldspan Dragon, haste, Treasure,
  flyers blocking flyers, who's defeated, blocked attackers don't hit the player, tapped creatures can't block, and
  Treasure worth two with Goldspan out. It glows once the twelve are done and never hides the diploma.
- 🖼️ Sticker scene: My Spellbook → "My sticker scene". Drag (or tap) her earned stickers onto a castle, sky, or meadow
  picture, drag them around, or drag one off to take it away. Each picture keeps its own stickers, and they're in Backup.
- ✨ Little polish: "NEW" on a home tile goes away once she's opened that game (saved and in backups); Memory Match
  gives a soft sound on a miss and says "Try again!" the first two times; an empty Art Studio says where paintings
  will live; Spell Echo no longer shows its name twice.
- 📏 Bigger games on the tablet: Spell Echo pads, Faerie Pop pools, Rootha's face, and Mana Bubbles (field and bubbles)
  grow to fill the screen, and in landscape everything (Start included) still fits without scrolling. Phones unchanged.
- ❤️ Game Night turn helper, easier without reading: the six turn steps are big picture buttons (🔄 🃏 ⛰️ ✨ ⚔️ ✅);
  tap one to hear it again. The "whose turn" banner wears that player's colour, "Next turn" glows on Done, and with
  "Face each other" the banner turns around to face whoever is playing.
- 💬 Questions are now a big, spoken pop-up with picture buttons (Remove a creature or painting, Start over, New game)
  instead of browser dialogs Luna couldn't read. Back or tapping outside just closes the question.
- 🎨 Art is never lost by accident: ✖ or the tablet's Back button while painting asks "Keep your painting?" (empty pages
  still close straight away).
- New static check: no browser dialogs in the games (the grown-up "make all movies" button keeps its one on purpose).
  Smoke tests fail on any browser dialog; `SMOKE_ONLY=name,name` runs a few tests while developing.
- `tools/live_check.py`: checks a deployed server end to end (story, picture, voice, optional one Veo clip), never prints secrets.
- `SPELLCAR_URL` + `SPELLCAR_APP_TOKEN` at build time preconnect the tablet APK to the server (no Azure/Google keys in the app).
- `AGENT_HANDOFF.md`: step-by-step deploy instructions for a home agent.
- Tests: fixed a 1-in-20 flake (a natural 20 in Game Night opened a celebration that blocked the next test).

## 1.7.0 (2026-10-15)
- 🎓 Magic School: the printed Spellbook as twelve spoken, tappable lessons: colors, zones, parts of a card
  (tap the real card), kinds of cards, tapping lands to pay costs, putting a turn in order, combat with flying and
  haste, prowess and magecraft, Treasure, Rootha's Elemental trick, how to win, and a full guided Practice Turn.
  Finishing all twelve unlocks a printable Magic School diploma (PDF).
- 🌌 Star Map: twelve harder hidden treasures (Spell Echo 8 in a row, 25 faeries, cast every card, 10-answer
  streaks, a mistake-free Practice Turn, and more) light up Galazeth's constellation, with a glowing reveal and
  progress for each. Finding all twelve unlocks a secret Starlight theme.
- Progress stats (streaks, casts, creatures, paintings, lessons) are tracked and included in backups (v4).
- New static check: state classes that reuse a component's name (the cause of the blank lesson tile).
- Spell Car server for Cloudflare Workers (`worker/`): KV for caps and jobs, R2 for movie clips, a cron trigger that
  finishes clips in the background, and `./deploy.sh` (KV/R2 auto-created, secrets uploaded from `worker/.secrets`).
  The same server tests and app smoke tests pass against it.

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
