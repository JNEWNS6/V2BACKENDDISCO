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

## Render deployment

The repo ships with a [Render Blueprint](https://render.com/docs/blueprint-spec) so you can spin up the full stack (web service, background scraper, Postgres, and Redis) with one click.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OneClickDeploys/V2BACKENDDISCO)

1. Commit or push the repo to your own GitHub account.
2. Create a new **Blueprint Deploy** on Render and point it at this repo (or click the button above and choose your fork).
3. Review the generated resources:
   - `disco-backend` web service running `node server.js` and executing `npm run migrate` after each deploy to apply the SQL migrations in this repo.
   - `disco-scraper` worker running `node worker.js`, which launches both the BullMQ workers and the scraper scheduler.
   - Managed Postgres (`disco-db`) and Redis (`disco-redis`).
4. Supply the required secrets in the Render dashboard (`ADMIN_TOKEN`, Stripe keys, etc.). Optional scraper knobs (`ALLOWLIST_DOMAINS`, `SCRAPE_LIMIT`, `SCRAPE_DELAY_MS`) are exposed but can be left blank.
5. Deploy. The provided `render-build.sh` installs both the Node.js dependencies and the Python scraper requirements before each deploy.

The services expect `PYTHON_BIN=python3` (configured in the blueprint) so that BullMQ workers can launch the scraping helpers defined in `scrape_cli.py`. The web service sets `START_QUEUE_IN_WEB=false` so background jobs only run on the worker service.

## Notes
- Light-touch scraping (≤ 6 pages, 7s timeout, 10m cache).
- For SPA checkouts, send `html` to `/scrape` for better extraction.
- Replace SQLite with Postgres via `DATABASE_URL`.
