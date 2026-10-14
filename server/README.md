# Spell Car server (Azure)

A tiny, dependency-free Python server that gives the tablet app three extras from your Azure account:

| Feature in the app | Endpoint | Azure service |
|---|---|---|
| Story Time on the tablet | `POST /story` | Azure OpenAI chat deployment (e.g. `gpt-4o-mini`) |
| 🪄 AI picture in Make a Creature | `POST /image` | Azure OpenAI image deployment (`dall-e-3` or `gpt-image-1`) |
| Natural neural voices (incl. Ana, a child's voice) | `POST /tts` | Azure AI Speech |

Each feature turns on only if its settings are present; `GET /health` tells the app which ones are available.

## Why a server

API keys inside an APK can be extracted by anyone who has the file. The keys stay here instead, and the
endpoints are deliberately narrow: the app sends structured choices (which creatures, which of six places,
which creature kind/color/accessory from fixed lists, text to speak with a voice from an allowlist), and the
server writes every prompt itself. A leaked app token can only produce gentle kids' stories, creature
pictures, and speech, up to the daily caps. Azure's default content filters stay on; filtered requests come
back as a friendly "let's try something else" in the app.

## Azure setup

1. **Azure OpenAI** (or an Azure AI Foundry resource with Azure OpenAI models): deploy a chat model and note the
   deployment name. Small fast models are ideal for 150-word stories. Optionally deploy an image model; availability
   varies by region. `dall-e-3` works with API version `2024-10-21`; `gpt-image-1` needs `2025-04-01-preview`.
2. **Azure AI Speech** (optional): create a Speech resource and copy a key and its region.
3. Copy the endpoint (`https://<resource>.openai.azure.com`) and key from Keys and Endpoint.

## Run it

```bash
cd server
cp .env.example .env            # fill in Azure values
openssl rand -hex 24            # paste as SPELLCAR_TOKEN
docker compose up -d --build    # or, without Docker: python3 spellcar_server.py  (or `make server` from the repo root)
```

Then on the tablet: **For grown-ups → Spell Car server** → enter the address and token → **Connect**.
Pick "Cloud voice for stories" (stories and Rootha Says) or "everywhere," and a voice.

## Reaching it from the car

The tablet needs to reach the server over the internet (phone hotspot in the car). Two good options:

- **Tailscale** (simplest, nothing exposed publicly): install Tailscale on the server and the tablet, then use
  `http://<server-tailscale-name>:8787`. Traffic is encrypted by WireGuard, so plain HTTP is fine here.
- **Reverse proxy with HTTPS**, e.g. Caddy: `spellcar.example.com { reverse_proxy localhost:8787 }`, then use
  `https://spellcar.example.com`. Don't expose port 8787 over plain HTTP to the internet.

## Limits and logs

Daily caps (reset at midnight server time): `STORIES_PER_DAY` (40), `IMAGES_PER_DAY` (20), `TTS_CHARS_PER_DAY`
(60,000). The server logs one line per request (method, path, status) and never logs prompts, stories, or audio.

## Testing

`make test` runs `tests/test_server.py` against a fake Azure (`tests/stack.py`) covering auth, CORS, prompt
building, rejected free-form input, content-filter mapping, caps, SSML escaping, and the voice allowlist; the
browser smoke tests then drive Story Time, AI pictures, and cloud voice through the Android build.
