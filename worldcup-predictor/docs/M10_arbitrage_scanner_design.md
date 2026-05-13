# M10 — Cross-Platform Arbitrage Scanner

> Sweeps every match's recent bookmaker odds, identifies opportunities
> where the implied probabilities sum to less than 1.0, and pushes
> alerts to users whose watchlist rules match.

## Why M10

M9 + M9.5 handle the *hedging* side: turning a single bet into a
guaranteed (or capped-loss) outcome by laying off the opposite side.
M10 attacks the orthogonal opportunity: when bookmakers disagree, a
proportional split across them locks in profit *without an
already-placed position*.

The two flows share the same NotificationDispatcher and the same
frontend pattern (list of opportunities, watchlist for push filters)
so they're cohesive in the UI.

## Math (recap)

For a market with outcomes `{o₁, …, oₙ}`:

```
implied_i  = 1 / best_odds(oᵢ)
arb_total  = Σ implied_i

if arb_total < 1.0:
    profit_margin   = (1 − arb_total) / arb_total
    stake_share_i   = implied_i / arb_total
    guaranteed_return(bankroll) = bankroll / arb_total
```

Implemented in [src/ml/arbitrage/calculator.py](../src/ml/arbitrage/calculator.py).
Markets covered: 1x2 (3-way), over_under, asian_handicap (binary), btts.

## Data model (Alembic 0008)

### `arb_opportunities` (new)

Append-only book-of-record. Status state machine:

```
active ──► expired   (next scan: odds tightened, arb gone)
        ►  stale     (kick-off passed without resolution)
```

| column              | type             | notes                              |
|---------------------|------------------|------------------------------------|
| id                  | bigserial        |                                    |
| match_id            | bigint FK        | cascade delete                     |
| market_type         | varchar(30)      | 1x2 / over_under / asian_handicap / btts |
| detected_at         | timestamptz      |                                    |
| arb_total           | numeric(8,6)     | implied-sum, < 1 iff arb exists    |
| profit_margin       | numeric(8,6)     | fraction; 0.025 = 2.5%             |
| best_odds           | jsonb            | {outcome: {odds, bookmaker, captured_at}} |
| stake_distribution  | jsonb            | {outcome: fraction-of-bankroll}    |
| status              | varchar(20)      | CHECK active / expired / stale     |
| expired_at          | timestamptz?     |                                    |

Plus a partial index `idx_arb_opp_active_margin` ordered by
`profit_margin DESC, detected_at DESC` to back the frontend list view
without a sequential scan.

### `user_arb_watchlist` (new)

Per-user filter rules driving push fan-out.

| column            | type           | notes                                |
|-------------------|----------------|--------------------------------------|
| user_id           | bigint FK      | cascade delete                       |
| competition_id    | bigint FK?     | NULL = match any competition         |
| market_types      | jsonb?         | NULL = match any market              |
| min_profit_margin | numeric(8,6)   | fraction; default 0.01 (1%)          |
| notify_enabled    | bool           | global mute toggle                   |

## Backend layers

### Python (ml-api)

```
src/ml/arbitrage/calculator.py   # pure math
src/ml/arbitrage/scanner.py      # DB sweep + persistence + expiry
src/tasks/arb_scanner_tasks.py   # Celery task @ 60s
src/api/routes/arbitrage.py      # 5 endpoints
src/api/schemas/arbitrage.py
src/models/arbitrage.py          # ORM
```

The scanner persists at most one `active` row per (match, market) pair:
on a new detection, any prior active row is flipped to `expired`. The
worker then walks the `notify_enabled` watchlist rules; matching users
get an `arbitrage`-kind notification via `NotificationDispatcher.send_arb_alert`
(introduced in M9.5).

### Java (business API)

```
com/wcp/arbitrage/ArbitrageController.java  # 5 endpoints
com/wcp/arbitrage/ArbWatchlistService.java
com/wcp/arbitrage/ArbWatchlistRepository.java
com/wcp/arbitrage/entity/ArbWatchlistEntity.java
com/wcp/arbitrage/dto/{CreateWatchlistRequest,WatchlistResponse}.java
```

Opportunity reads proxy via `MlApiClient.arbitrageOpportunities()` —
ml-api is the canonical reader. Watchlist CRUD is JPA-direct.

Tier gate: **basic+**.

### Frontend (Next.js)

```
src/types/arbitrage.ts
src/lib/arbitrageApi.ts
src/components/arbitrage/{ArbOpportunityCard,WatchlistPanel}.tsx
src/app/(public)/arbitrage/page.tsx
```

The page polls the opportunity list every 60s (matches the scanner
cadence). Each card has an inline bankroll input that recomputes the
per-leg stake and guaranteed profit on the fly. Margin ≥ 2% gets the
emerald-tinted "premium opportunity" treatment.

## Operational notes

* New container: `arb-scanner-worker` (concurrency 2, queue
  `arb_scanner`).
* Beat schedule: `arb_scanner.scan_for_arbitrage` every 60 s.
* The 0.5% `MIN_PROFIT_MARGIN` floor in `scanner.py` filters out
  bookmaker-noise arbs that vanish before the user could realistically
  execute. Tune via the constant if needed.
* Microstructure caveats apply: max-stake limits and account-closure
  risk are real-world frictions the scanner does not model. The UI
  reminds users to verify limits before staking. Reference: Hubacek &
  Sourek (2017).
