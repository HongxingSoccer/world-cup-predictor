# worldcup-predictor

World Cup 2026 Predictor — data foundation, ingest pipelines, ML engine
scaffolding, and prediction API. This repository is the Python backend; future
Phase-3+ work adds a Java business service (`java-api/`) and a Next.js frontend
(`web/`) as siblings.

## Phase 1 scope (this branch)

- 15-table PostgreSQL schema covering competitions, seasons, teams, players,
  matches, lineups, stats, valuations, injuries, odds snapshots, head-to-head
  records, Elo ratings, ingest audit logs, and team-name aliases.
- 6 data-source adapters: API-Football, the-odds-api, Transfermarkt, FBref,
  OddsPortal (Playwright skeleton), and a static-CSV importer
  (martj42/international_results).
- ETL pipelines (one base + 4 concrete) with batched ON-CONFLICT upserts,
  audit-log writes, and Kafka event emission.
- 12 Celery tasks across daily / weekly / dynamic schedules + a `dispatch_dynamic_jobs`
  scanner that handles per-match work without true dynamic cron entries.
- Kafka event envelope + 5 topics (`match.created`, `match.updated`,
  `match.finished`, `odds.updated`, `data.quality.alert`).
- Elo backfill, data-quality checks, three operational scripts.
- Test coverage for every adapter (36 tests passing as of this commit).
- **M9 Hedging Advisory** (premium): single + parlay hedge calculator at
  `/hedge` with a tri-coloured ratio slider, ML-aware recommendation
  badge, and a P/L bar chart per outcome; history + ROI / win-rate
  summary at `/hedge/history`. Backend: `src/ml/hedge/` (Python) +
  `com.wcp.hedge.*` (Java Spring Boot). Design doc:
  [`docs/M9_hedging_module_design.md`](docs/M9_hedging_module_design.md).

## Quick start

```bash
# 1. Boot infrastructure (Postgres / Redis / Kafka / Zookeeper / Celery / Flower)
docker compose up -d

# 2. Local Python environment for migrations & scripts
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
# Edit .env to set API_FOOTBALL_KEY / ODDS_API_KEY etc.

# 4. Apply schema
alembic upgrade head

# 5. (Optional) Import static historical data — Scotland-1872 → present
python -m scripts.import_static_data --year all --no-kafka

# 6. (Optional) Full historical backfill (9-step pipeline; resumable via --step)
python -m scripts.backfill_historical --from 2022-11

# 7. Watch the Celery worker / beat at http://localhost:5555 (Flower)
```

The Celery worker / beat services in `docker-compose.yml` start automatically
in step 1 and connect to the in-cluster Postgres / Redis / Kafka. To run them
locally instead of in Docker:

```bash
celery -A src.celery_app worker --loglevel=INFO
celery -A src.celery_app beat   --loglevel=INFO
```

## Verifying the install

```bash
# Migration round-trip
alembic upgrade head && alembic downgrade base && alembic upgrade head

# Import smoke test (every module loads)
python -c "from src.celery_app import app; print(len([t for t in app.tasks if not t.startswith('celery.')]), 'tasks registered')"

# Test suite (no infra required — all HTTP / Playwright is mocked)
pytest

# Data-quality checks (requires the schema to be applied)
python -m scripts.validate_data
```

## Configuration

All configuration lives in environment variables; see `.env.example` for the
full list. The key settings:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://wcp:wcp@localhost:5432/wcp` | SQLAlchemy URL. |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + result backend. |
| `KAFKA_BROKERS` | `localhost:9092` | Bootstrap servers (comma-separated for clusters). |
| `API_FOOTBALL_KEY` | _(required for live ingest)_ | API-Football v3 key. |
| `ODDS_API_KEY` | _(required for live odds)_ | the-odds-api.com key. |
| `PROXY_POOL_URL` | _(empty)_ | HTTP endpoint that returns one proxy URL on GET. |
| `LOG_LEVEL` | `INFO` | Standard Python log levels. |
| `SCRAPER_CONCURRENT` | `8` | Max in-flight scraper requests. |
| `ACTIVE_COMPETITIONS` | `1:2026` | Comma-separated `{league_id}:{year}` tokens. |

## Project layout

```
worldcup-predictor/
├── src/
│   ├── celery_app.py          Worker entrypoint (`celery -A src.celery_app`)
│   ├── adapters/              External-API adapters
│   ├── models/                15 SQLAlchemy ORM models (Phase 1)
│   ├── dto/                   Pydantic v2 boundary DTOs
│   ├── pipelines/             ETL (DTO → ORM) base + 4 concrete pipelines
│   ├── tasks/                 Celery task modules
│   ├── events/                Kafka envelope, schemas, topic constants
│   ├── scrapers/              (Phase 2 — Scrapy spiders)
│   ├── utils/                 Elo, validators, rate limiter, name mapping, …
│   └── config/                Settings, Celery, Kafka client config
├── migrations/                Alembic env + initial schema revision
├── scripts/
│   ├── import_static_data.py  One-shot CSV import (martj42 dataset)
│   ├── backfill_historical.py 9-step orchestrator (resumable via --step)
│   └── validate_data.py       CLI wrapper around the data-quality checks
├── tests/                     pytest suite (36 tests)
├── docker-compose.yml         postgres / redis / kafka / worker / beat / flower
├── Dockerfile                 Worker / beat image
├── alembic.ini                Alembic CLI config
├── pyproject.toml             ruff / mypy / pytest config
├── requirements.txt           Runtime + dev dependencies
└── .env.example               Sample environment file
```

## Operational notes

- **M9.5 live hedging**: a `live-monitor-worker` Celery container sweeps
  every active `user_positions` row every 60 s and fires hedge-window
  push notifications via `NotificationDispatcher`. See
  [docs/M9_5_live_hedging_flow.md](docs/M9_5_live_hedging_flow.md).
- **M10 arbitrage scanner**: a `arb-scanner-worker` container detects
  cross-bookmaker arbitrage every 60 s, persists each opportunity, and
  fans out pushes to users whose watchlist rules match. See
  [docs/M10_arbitrage_scanner_design.md](docs/M10_arbitrage_scanner_design.md).
- Celery `dispatch_dynamic_jobs` (every 5 min) scans the calendar and fans
  out per-match jobs (live scores, post-match stats, pre-kickoff odds). This
  intentionally replaces true dynamic cron — fewer moving parts, same outcome.
- `data_source_logs` is the audit table for every ingest run. The Phase-1
  spec's 5 quality checks are in `src.utils.quality_checks` and run both as
  a daily Celery task and as a CLI (`python -m scripts.validate_data`).
- `odds_snapshots` is append-only — the dedup window is enforced in
  `src.utils.validators.is_duplicate_odds_snapshot`, not via a UNIQUE
  constraint, so historical price movement stays intact.
- Scrapers (FBref, Transfermarkt, OddsPortal) rotate User-Agent per request
  and treat HTTP 403 as a retryable status that triggers a proxy swap via
  the `_on_blocked` hook on `BaseDataSourceAdapter`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Received unregistered task` from worker | Worker started against `src.config.celery_config` directly (no task auto-import) | Use `celery -A src.celery_app …` |
| `psycopg2.OperationalError: connection refused` from migrations | Postgres container not yet healthy | `docker compose up -d postgres && sleep 5 && alembic upgrade head` |
| `playwright._impl._errors.Error: Executable doesn't exist` | Browser binary not installed | `playwright install chromium` |
| `kafka.errors.NoBrokersAvailable` | Producer started before Kafka is reachable | Confirm `kafka` service is healthy (`docker compose logs kafka`); Kafka takes ~15s to start |
