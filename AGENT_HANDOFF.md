# Deploy the Spell Car server (instructions for a home agent)

You're deploying the **Spell Car server** for Luna's Spell Car, a kids' learning app, to the owner's Cloudflare
account, then checking it live. Read `worker/README.md` and `CLAUDE.md` for background.

## Rules
- Never print, log, commit, or paste secret values (Azure keys, Gemini key, Cloudflare tokens, the app token)
  anywhere except `worker/.secrets` (gitignored, chmod 600) and the `wrangler secret bulk` upload.
- Never put Azure or Google keys into the app, the APK, or any file under `web/` or `android/`.
- Don't create new Cloudflare resources: KV namespace `spellcar-state` (id f6623b0bd3c44f83a20b340855a4b950)
  and R2 bucket `spellcar-clips` already exist and are pinned in `worker/wrangler.jsonc`.
- Don't change app code. If something fails, stop and report what failed and the exact error (with secrets removed).

## Steps
1. Unzip `luna-spell-car-repo.zip` (it includes the full git history and tags) and `cd luna-spell-car`.
   Check `git status` is clean. Create a **private** GitHub repo `luna-spell-car` under the owner's account
   (private because it contains Wizards of the Coast card art for personal use), then
   `git remote add origin <repo URL>` and `git push -u origin main --tags`.
   Pushing starts the CI workflow (`.github/workflows/ci.yml`: tests + APK build, no secrets needed).
2. Needs Node 20+ and Python 3.10+. `cd worker && npm ci`.
3. Confirm the Cloudflare account: `npx wrangler whoami`, then confirm `spellcar-state` shows in
   `npx wrangler kv namespace list` and `spellcar-clips` in `npx wrangler r2 bucket list`.
   If they're missing, you're in the wrong account: stop and report.
4. Run the server tests (no real keys used): from the repo root, `SPELLCAR_IMPL=worker python3 tests/test_server.py`.
   Every line should say ok.
5. `cd worker && ./deploy.sh`. The first run creates `worker/.secrets` with a fresh `SPELLCAR_TOKEN` and stops.
   Fill in from the credential store (leave a line empty if that credential doesn't exist; that feature stays off):
   `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT` (the deployment name),
   `AZURE_OPENAI_IMAGE_DEPLOYMENT`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `GEMINI_API_KEY`.
   If the image deployment is `gpt-image-1`, also set `AZURE_OPENAI_IMAGE_API_VERSION` to `2025-04-01-preview` in
   `worker/wrangler.jsonc` → `vars`.
6. Run `./deploy.sh` again. It deploys and uploads the secrets. Note the `https://spellcar.<subdomain>.workers.dev` URL.
7. Live check, from the repo root: `python3 tools/live_check.py --url <worker URL>`.
   If story, picture, and voice pass and the video capability is enabled, run it once more with `--video`
   (makes ONE real Veo clip, about $0.80). It reads the app token from `worker/.secrets` and prints no secrets.
   Fixes for common failures: Azure 404 means the deployment name is wrong; Azure 400 on images usually means the image
   API version (see step 5); Veo 403 or 429 usually means billing isn't enabled on the Gemini key's Google Cloud project.
8. Optional, only if the Android SDK (platform 34, build-tools 34.0.0) and JDK 17 are installed:
   `SPELLCAR_URL=<worker URL> SPELLCAR_APP_TOKEN=<SPELLCAR_TOKEN from worker/.secrets> make apk`
   builds `build/luna-spell-car.apk` already connected to the server (it contains only the URL and the narrow app
   token, never Azure or Google keys).

## Report back
- The private repo URL and whether the first CI run passed (if it failed, the failing step and log excerpt).
- The Worker URL and which features `/health` reports enabled.
- The live check output (PASS/FAIL lines).
- Where `build/live/` (story.txt, picture.*, voice.mp3, clip.mp4) and the APK (if built) are.
- Give the owner the app token privately; it goes into the app under For grown-ups → Spell Car server.
