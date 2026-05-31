---
title: op-anime
emoji: 🎥
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# op-anime — Self-Healing Anime Backend

A FastAPI backend that wraps the [ani-cli](https://github.com/pystardust/ani-cli) bash scraper, exposing clean REST endpoints for a Flutter client (or any HTTP consumer).

When the upstream community updates `ani-cli` (new providers, API changes, bug fixes), a GitHub Actions cron job pulls the latest script and triggers a redeploy — **zero manual maintenance**.

```
Flutter / Web Client
        │  HTTP
        ▼
  FastAPI (Python)
        │
  ani-cli-api.sh (wrapper)
        │  sources functions from
        ▼
  ani-cli (upstream bash script)
        │
        └──▸ AllAnime GraphQL API
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/search` | Search anime by title |
| `GET` | `/api/v1/episodes` | List episodes for an anime |
| `GET` | `/api/v1/stream` | Get a direct stream URL |
| `GET` | `/health` | Health check |

### `GET /api/v1/search`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | Anime title to search |
| `mode` | string | ❌ | `sub` (default) or `dub` |

```json
// GET /api/v1/search?query=one+piece
[
  { "id": "RzN3aGNwZ", "title": "One Piece (1122 episodes)" },
  { "id": "kE9wYWtrZ", "title": "One Piece Film: Red (1 episodes)" }
]
```

### `GET /api/v1/episodes`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `anime_id` | string | ✅ | ID from search results |
| `mode` | string | ❌ | `sub` (default) or `dub` |

```json
// GET /api/v1/episodes?anime_id=RzN3aGNwZ
{
  "anime_id": "RzN3aGNwZ",
  "mode": "sub",
  "episodes": ["1", "2", "3", "...", "1122"],
  "count": 1122
}
```

### `GET /api/v1/stream`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `anime_id` | string | ✅ | ID from search results |
| `episode` | string | ✅ | Episode number (e.g. `1`, `5.5`) |
| `mode` | string | ❌ | `sub` (default) or `dub` |
| `quality` | string | ❌ | `best` (default), `worst`, `720p`, `1080p` |

```json
// GET /api/v1/stream?anime_id=RzN3aGNwZ&episode=1&quality=1080p
{
  "anime_id": "RzN3aGNwZ",
  "episode": "1",
  "url": "https://example.com/stream/ep1.m3u8",
  "referer": "https://youtu-chan.com",
  "quality": "1080p"
}
```

> **Note:** Include the `referer` value as the `Referer` header when fetching the stream URL to avoid hotlink blocks.

### Error Responses

| Code | Meaning |
|------|---------|
| `404` | No results / episodes found |
| `503` | Upstream scraper failed (try again later) |

## Project Structure

```
op-anime/
├── .github/workflows/
│   └── auto-update.yml        # Syncs ani-cli from upstream every 12h
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI routes & models
│   └── executor.py            # Async subprocess bridge to ani-cli
├── bin/
│   ├── ani-cli                # Upstream bash scraper (auto-updated)
│   └── ani-cli-api.sh         # Headless wrapper (sources ani-cli functions)
├── Dockerfile
├── requirements.txt
└── README.md
```

## Self-Healing Architecture

1. **GitHub Actions** runs every 12 hours (or on manual trigger)
2. Downloads the latest `ani-cli` script from [pystardust/ani-cli](https://github.com/pystardust/ani-cli)
3. If the script changed, commits and pushes
4. Railway (or any CI/CD) detects the push and redeploys
5. `ani-cli-api.sh` sources the updated functions at runtime — **instant sync**

## How the Wrapper Works

`bin/ani-cli-api.sh` uses `awk` + `eval` to load all function definitions and variables from `ani-cli` **without** running its interactive main flow:

```sh
# Load everything before the argument-parsing while-loop
eval "$(awk '/^while \[ \$# -gt 0 \]; do/{exit} {print}' ani-cli)"

# Now we have: search_anime(), episodes_list(), get_episode_url(), etc.
# Plus all variables: agent, allanime_api, allanime_key, etc.
```

This means when upstream changes a GraphQL query, API URL, decryption key, or provider parser — **our backend automatically inherits the fix**.

## Local Development

```bash
# Build the Docker image
docker build -t op-anime .

# Run it
docker run -p 8000:8000 op-anime

# Test endpoints
curl "http://localhost:8000/health"
curl "http://localhost:8000/api/v1/search?query=naruto"
curl "http://localhost:8000/api/v1/episodes?anime_id=SOME_ID"
curl "http://localhost:8000/api/v1/stream?anime_id=SOME_ID&episode=1"
```

## Deployment (Railway)

1. Push this repo to GitHub
2. Connect it to [Railway](https://railway.app)
3. Railway auto-detects the Dockerfile and deploys
4. Every push (including bot-driven ani-cli updates) triggers a new deployment

## Tech Stack

- **Runtime:** Python 3.11 + FastAPI + Uvicorn
- **Scraper:** [ani-cli](https://github.com/pystardust/ani-cli) (POSIX sh)
- **Container:** Docker (python:3.11-slim)
- **CI/CD:** GitHub Actions → Railway
