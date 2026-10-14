# Development cycle

```
 edit web/app.html ──► make dev (live reload, phone/tablet on Wi-Fi) ──► make test ──► note it in CHANGELOG "Unreleased"
        ▲                                                                                      │
        └──────────── feedback from Luna ◄── make install (adb) ◄── make release PART=minor ◄──┘
```

## One-time setup

- JDK 17+, Python 3.10+, `pip install playwright && python -m playwright install chromium`
- Android SDK: `sdkmanager "platforms;android-34" "build-tools;34.0.0"`, then `export ANDROID_HOME=...`
- `make hooks` runs the fast static checks before every commit.
- Wireless installs: on the tablet enable Developer options → Wireless debugging, then
  `adb pair <ip>:<pair-port>` once and `adb connect <ip>:<port>`. Fire tablets: enable ADB in Developer options.

## Everyday loop

| Step | Command | What it does |
|---|---|---|
| Develop | `make dev` | Rebuilds on every save and serves at `http://localhost:8000`; the page reloads itself. Open `http://<computer-ip>:8000` on the tablet's browser to try it on the real screen. |
| Check | `make check` | Static checks: duplicate names, `$("id")` references that don't exist, duplicate ids, home tiles without screens, storage keys saved but never loaded, card data shape. Seconds. |
| Test | `make test` | `check` plus Playwright smoke tests that play every game in both builds: the web build with a fake claude.ai runtime, and the Android build with a fake `AndroidBridge` (TTS, file saving). Fails on any console error. Failure screenshots go to `build/test-shots/`. |
| Release | `make release PART=patch\|minor\|major` | Bumps `VERSION`, moves CHANGELOG's Unreleased notes under the new version, runs tests, builds the APK, commits, tags `vX.Y.Z`. |
| Ship | `make install` | `adb install -r` onto the connected tablet. Her data is kept. |

`versionCode` is derived from `VERSION` (1.2.3 → 10203), so every release installs over the last one.

## Rules of thumb

- Add a smoke test with every new game (see `tests/smoke.py`, one `@test` function per feature).
- All saved data goes through `load()` / `store()` with a `luna_` key, and new kinds of data get added to Backup/Restore.
- Everything must work offline in the Android build: no network fetches; vendor files go in `web/vendor/`.
- Every prompt should be speakable (`say()`); a young child can't read most of the screen.
- The web build is also published as a claude.ai artifact (that's where Story Time works).

## CI

`.github/workflows/ci.yml` runs `make test` and `make apk` on pushes and PRs, uploads the APK as an
artifact, and attaches it to a GitHub release when you push a `v*` tag. It uses only standard
actions, so it should also run on Forgejo/Gitea Actions with an Ubuntu runner that has the Android SDK.
