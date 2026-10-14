#!/usr/bin/env bash
# Local alternative to the cloud routine, for a home server with Claude Code installed and logged in.
# crontab -e:   30 2 * * *  /path/to/luna-spell-car/tools/iterate-local.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/iterate
git fetch -q origin && git checkout -q main && git pull -q --ff-only
claude -p "$(cat .claude/iterate-prompt.md)" \
  --permission-mode acceptEdits \
  --allowedTools "Bash(make *)" "Bash(git *)" "Bash(gh pr *)" "Bash(python3 *)" "Read" "Edit" "Write" \
  --max-turns 150 > "build/iterate/$(date +%F-%H%M).log" 2>&1 || echo "iteration run failed; see build/iterate/" >&2
git checkout -q main
