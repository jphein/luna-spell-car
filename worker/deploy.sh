#!/usr/bin/env bash
# Deploy the Spell Car server to Cloudflare Workers.
#   First time:  npx wrangler login      (opens a browser to authorize your Cloudflare account)
#   Then:        ./deploy.sh             (creates KV + R2 automatically, uploads secrets from worker/.secrets)
set -euo pipefail
cd "$(dirname "$0")"
export WRANGLER_SEND_METRICS=false
[ -d node_modules ] || npm install --silent

if [ ! -f .secrets ]; then
  cat > .secrets <<EOT
# Spell Car secrets. This file stays on your machine (gitignored). Leave a line empty to turn that feature off.
SPELLCAR_TOKEN=$(openssl rand -hex 24)
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_KEY=
AZURE_OPENAI_CHAT_DEPLOYMENT=
AZURE_OPENAI_IMAGE_DEPLOYMENT=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
GEMINI_API_KEY=
EOT
  chmod 600 .secrets
  echo "Created worker/.secrets with a fresh app token. Fill in your Azure and Gemini values, then run ./deploy.sh again."
  exit 1
fi

npx wrangler deploy

tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
python3 - "$tmp" <<'PY'
import json, sys
vals = {}
for line in open(".secrets"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); v = v.strip().strip('"').strip("'")
        if v: vals[k.strip()] = v
if len(vals.get("SPELLCAR_TOKEN", "")) < 16: sys.exit("SPELLCAR_TOKEN in worker/.secrets must be 16+ characters")
json.dump(vals, open(sys.argv[1], "w"))
print("Uploading secrets:", ", ".join(sorted(vals)))
PY
npx wrangler secret bulk "$tmp"

echo
echo "Done. In the app: For grown-ups → Spell Car server"
echo "  Address: the https://spellcar.<your-subdomain>.workers.dev URL printed above"
echo "  Token:   $(grep '^SPELLCAR_TOKEN=' .secrets | cut -d= -f2)"
