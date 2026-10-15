# Spell Car server on Cloudflare Workers (recommended)

Same API, prompts, safety rules, and tests as `server/spellcar_server.py`, running on Cloudflare:
HTTPS and a public address out of the box (works from a phone hotspot in the car), nothing to host at home,
keys stored as encrypted Worker secrets.

| Piece | Cloudflare feature |
|---|---|
| API (`/health`, `/story`, `/image`, `/tts`, `/animate`, `/video`) | Worker `fetch` handler |
| Daily caps, Veo job records | Workers KV (`STATE`) |
| Finished movie clips | R2 bucket (`CLIPS`) |
| Finishing clips while no device is asking | Cron Trigger, every minute |

## Deploy

```bash
cd worker
npx wrangler login     # once
./deploy.sh            # first run creates worker/.secrets with a fresh app token; fill it in, run again
```

`wrangler deploy` creates the KV namespace and R2 bucket automatically the first time. If Cloudflare says R2 isn't
enabled on the account, enable it once under R2 in the dashboard and rerun. Change caps or the Veo model in
`wrangler.jsonc` → `vars`, then `./deploy.sh` again.

## Develop and test

`make test-worker` runs the full server test suite against `wrangler dev` (local KV and R2) with the fake
Azure/Veo from `tests/stack.py`. `SPELLCAR_IMPL=worker python3 tests/smoke.py` runs the app's browser tests against it.

## Cost

Workers Paid ($5/month) covers this many times over; KV and R2 usage here is tiny. The real costs are Azure and
Google Veo calls, which the daily caps bound.
