# Disco Backend — Scraping + Adapters

FastAPI backend with **server-side scraping** and **adapter-aware** suggestions.

## Endpoints
- `GET /health`
- `GET /adapters`
- `POST /scrape` — accepts { domain, url?, html? } and returns codes
- `POST /suggest` — seeds + successes + live scraping
- `POST /rank` — scores codes (success, recency, avg saved, priors)
- `POST /seed` — add seed codes (Bearer `DISCO_API_KEY`)
- `POST /event` — log attempts

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload
```

## Docker
```bash
docker build -t disco-backend .
docker run -p 8000:8000 --env-file .env -v $PWD/disco.db:/app/disco.db disco-backend
```

## Notes
- Light-touch scraping (≤ 6 pages, 7s timeout, 10m cache).
- For SPA checkouts, send `html` to `/scrape` for better extraction.
- Replace SQLite with Postgres via `DATABASE_URL`.
