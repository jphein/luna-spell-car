You are iterating on Luna's Spell Car, a learn-to-play Magic app for a young child. Read CLAUDE.md first and follow it.
Each run ships exactly ONE small, finished, tested improvement as a pull request.

1. Orient: read CLAUDE.md, FEEDBACK.md, ROADMAP.md, CHANGELOG.md, and `git log --oneline -15`.
   Run `gh pr list --state open`. If a previous `claude/` PR is open and its CI failed, fix that PR (push to its branch)
   and stop. If one is open and green, still awaiting review, pick work that doesn't touch the same code.
2. Choose, in this order: (a) unchecked items in FEEDBACK.md, bugs first; (b) the top unchecked item under
   ROADMAP "Next"; (c) a real bug or rough edge you find by running `make test` and reading the code.
   If the item is big, do the first useful slice and add the rest back to ROADMAP.
3. Add or extend a test in tests/smoke.py (and tests/test_server.py for server work) that fails without your change.
4. Implement it in web/app.html (and server/ or android/ only if needed). Run `make test` until everything passes.
5. Add a line under "## Unreleased" in CHANGELOG.md. Tick the item in FEEDBACK.md/ROADMAP.md. Add follow-ups to ROADMAP.
6. Commit to a new `claude/` branch and open a PR. Title: the change in plain words. Body: what changed, where to find it
   in the app, what Luna will notice, the test results, and anything a grown-up should check by hand on the tablet.

Never: merge PRs, bump VERSION, tag, run `make release`, edit the keystore, add secrets/API keys/new external hosts,
add ads, analytics, external links, chat, or data collection, or add anything scary, sad, or unkind.
If nothing is safe and worthwhile to do, open no PR and explain why in your final message.
