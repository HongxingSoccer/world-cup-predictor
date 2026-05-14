# M9.5 — Live Hedging Flow

> Closes the loop on M9 by turning the calculator into a workflow:
> position-of-record → live monitor → push alert → settlement.

## Why M9.5

M9 shipped the hedge math + advisor + history, but the user had no way
to *opt into ongoing monitoring*. They had to manually paste their bet
into the calculator and check periodically. M9.5 introduces:

1. A first-class **UserPosition** record the user creates after placing
   a bet on an external bookmaker.
2. A **live-monitor worker** that sweeps open positions every 60 s and
   detects hedge windows using the same calculator + advisor.
3. A **notification dispatcher** that fans alerts out to DB +
   web-push (and stubs for APNs / FCM / WeChat).
4. **Settlement reflection** — when the match settles, the position
   transitions to `settled` with a realised P&L and the user gets a
   notification with the final number.

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Next.js   │───►│  Java business   │───►│  Python ml-api  │
│  /positions │    │  /api/v1/        │    │ /api/v1/        │
│             │    │   positions      │    │  positions      │
│             │    │   notifications  │    │  hedge          │
└─────────────┘    └────────┬─────────┘    └────────┬────────┘
                            │                       │
                            ▼                       ▼
                   ┌──────────────────────────────────────┐
                   │  Postgres                            │
                   │  - user_positions                    │
                   │  - push_notifications  (ext'd)       │
                   │  - hedge_scenarios   (+ position_id) │
                   └─────────────┬────────────────────────┘
                                 │
                                 ▼
                   ┌──────────────────────────────────────┐
                   │  live-monitor-worker  (Celery)       │
                   │  scan_active_positions, every 60 s   │
                   └──────────────────────────────────────┘
```

## Data model (Alembic 0007)

### `user_positions` (new)

| column          | type            | notes                                  |
|-----------------|-----------------|----------------------------------------|
| id              | bigserial       |                                        |
| user_id         | bigint FK       | cascade delete                          |
| match_id        | bigint FK       | restrict (preserve audit)              |
| platform        | varchar(50)     | bookmaker name                         |
| market          | varchar(30)     | CHECK 1x2/over_under/asian_handicap/btts |
| outcome         | varchar(30)     | home/draw/away/over/under/yes/no       |
| stake / odds    | numeric         | CHECK stake > 0, odds > 1.0            |
| placed_at       | timestamptz     | client-supplied                        |
| status          | varchar(20)     | CHECK active/hedged/settled/cancelled  |
| last_alert_at   | timestamptz?    | live-monitor 30-min throttle anchor    |
| settlement_pnl  | numeric?        | filled by settlement worker            |

Plus `idx_positions_user_status`, `idx_positions_match`, and the partial
index `idx_positions_active_alert` (built via raw SQL since SQLAlchemy's
`Index()` doesn't compose `WHERE` clauses cleanly).

### `hedge_scenarios` + `push_notifications`

Both gain a nullable `position_id` FK (`ON DELETE SET NULL`).
`push_notifications` also gains `match_id` + `read_at`. New indexes back
the unread-count + per-position scans.

## Backend layers

### Python (ml-api)

```
src/services/position_service.py    # static-method CRUD + auth
src/ml/hedge/opportunity_detector.py # 15% odds-shift + EV-flip trigger
src/push/dispatcher.py              # write DB + fan-out web-push
src/push/stubs.py                   # APNs / FCM / wechat log-and-skip
src/tasks/live_monitor_tasks.py     # @app.task scan_active_positions
src/api/routes/positions.py         # 6 endpoints behind X-User-Id
src/api/routes/notifications.py     # 4 endpoints
```

The detector triggers on **either** signal:

- **odds_shift**: current best hedge odds vs the baseline (closest
  snapshot before `placed_at`) is ≥ +15% in the user's favour, AND the
  hedge EV is not catastrophically negative.
- **ev_flipped**: the original side has fallen to EV ≤ −0.03 AND the
  hedge side has EV ≥ −0.03 — i.e. it's now rational to lock in.

The Celery worker enforces a 30-minute per-position cool-down via
`UserPosition.last_alert_at`, so an oscillating market can't spam.

### Java (business API)

```
com/wcp/positions/    PositionController, Service, Repo, Entity, DTOs
com/wcp/notifications/  NotificationController, Service, Repo, Entity, DTO
```

Tier gate: **basic+** is required for the bookkeeping surface. Premium
gating stays on M9 calculator results. The Java side is JPA-only — does
not call ml-api directly; the live-monitor worker handles the alert
side, and the Java service just reads/writes `user_positions` +
`push_notifications`.

### Frontend (Next.js)

```
src/types/positions.ts
src/lib/positionsApi.ts
src/lib/notificationsApi.ts
src/components/positions/CreatePositionForm.tsx
src/components/notifications/NotificationBell.tsx
src/components/notifications/NotificationDrawer.tsx
src/app/(public)/positions/page.tsx
```

The header now mounts `<NotificationBell />` (polls
`/api/v1/notifications/unread-count` every 30 s) plus a "Positions"
nav link for basic+ users. The drawer renders newest-first with
kind-tinted backgrounds; rows are clickable and route to `targetUrl`
when present.

i18n adds two new top-level namespaces (`positions.*` and
`notificationCentre.*`) — kept distinct from the existing
`notifications.*` push-preferences namespace to avoid clashes.

## Settlement reflection

`src/tasks/settlement_tasks.py` now calls a new
`settle_positions_for_match(match_id)` after each prediction
settlement. It derives 1x2 / OU(2.5) / BTTS outcomes from the final
score, computes `pnl = stake × (odds − 1)` if the position won, else
`−stake`, sets `status='settled'`, and fires the
`position_settled` notification. Failures are caught + logged so
prediction settlement is never blocked.

## Operational notes

* New container: `live-monitor-worker` (concurrency 2, queue
  `live_monitor`). Beat schedule fires
  `live_monitor.scan_active_positions` every 60 s.
* Web-push (VAPID) is the only real channel today; APNs / FCM / wechat
  ship as no-op stubs that log + return False so the DB row still saves.
* All notifications save to `push_notifications` with `channel='db'`.
  External-channel success only flips `status` from `sent_db_only` →
  `sent`. So even if every external channel is misconfigured, the
  in-app notification centre still works.
