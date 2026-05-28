# Premium Anime Backend — System Design Document

## Architecture Overview

A self-healing FastAPI backend that wraps the [ani-cli](https://github.com/pystardust/ani-cli) bash scraper inside a Docker container, exposing clean REST endpoints for a Flutter client.

```
Flutter App ──► FastAPI (Python) ──► ani-cli (Bash) ──► Upstream Sources
                    │
              Docker Container
                    │
              Railway Deploy
```

## Project Structure

```
premium-anime-backend/
├── .github/workflows/
│   └── auto-update.yml      # CI/CD: auto-syncs ani-cli every 12h
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI router & endpoints
│   └── executor.py          # Async subprocess wrapper for ani-cli
├── bin/
│   └── ani-cli              # The raw bash scraper script
├── Dockerfile               # Python 3.11-slim + system deps
├── requirements.txt         # FastAPI, Uvicorn, Pydantic
└── README.md                # This file
```

## API Endpoints

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| GET    | `/api/v1/stream`  | Returns a streaming URL for an anime |
| GET    | `/health`         | Health check                         |

### `GET /api/v1/stream`

**Query Parameters:**
- `query` (string, required) — Anime title to search for.
- `episode` (int, required, > 0) — Episode number.

**Success Response (200):**
```json
{
  "query": "one piece",
  "episode": 1,
  "url": "https://example.com/stream.m3u8"
}
```

**Failure Response (503):**
```json
{
  "detail": "Upstream scraper failed or is under maintenance. Try again later."
}
```

## Self-Healing Mechanism

A GitHub Actions cron job runs every 12 hours:
1. Fetches the latest `ani-cli` script from upstream.
2. Commits the change if the script has been updated.
3. Pushes to GitHub, which triggers Railway's auto-deploy.

This ensures the scraper stays in sync with upstream fixes without manual intervention.

## Deployment (Railway)

1. Push this repo to GitHub.
2. Connect the repo to [Railway](https://railway.app).
3. Railway will detect the `Dockerfile` and auto-deploy.
4. Every push (including bot-driven ani-cli updates) triggers a new deployment.

## Local Development

```bash
# Build the container
docker build -t premium-anime-backend .

# Run it
docker run -p 8000:8000 premium-anime-backend

# Test the health endpoint
curl http://localhost:8000/health
```
