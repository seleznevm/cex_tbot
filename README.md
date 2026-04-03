# cex_tbot

Trading bot implementation scaffold for the semi-auto CEX trading lab.

## Scope of this commit

This first real commit covers the requested Phase 1–2 skeleton:
- base project structure
- README with short scope
- config/env loading
- shared enums and reason codes
- domain skeleton for project phases 1–2
- universe / eligibility skeleton
- project log entry inside repo
- market data normalization skeleton
- deterministic symbol eligibility query API

This is intentionally a foundation commit: contracts and module boundaries first, execution logic later.

## Initial layout

```text
src/cex_tbot/
  config.py
  enums.py
  shared/
    ids.py
    time.py
  decision_contracts/
    models.py
  universe/
    models.py
    service.py
  market_data/
    models.py
tests/
```

## Run tests

```bash
python3 -m unittest discover -s tests -t . -v
```

## What is now implemented in Phase 2

- deterministic universe refresh from raw instrument metadata
- materialization into whitelist records with refresh timestamps
- eligibility filtering for:
  - active status
  - USDT quote asset
  - listing age threshold
  - spread threshold
  - non-zero volume / open interest / book depth
- top-N whitelist ranking by liquidity score
- static in-memory sources/providers for repeatable tests
- market snapshot normalization from raw ticker input
- deterministic symbol eligibility query with stale/not-found handling
- placeholder config plumbing for `GATE_DEMO_API`
- Gate metadata adapter skeleton for raw instrument normalization
- append-only in-memory universe snapshot repository skeleton
- universe refresh orchestrator skeleton with result contract
- Gate fetch client contract with deterministic static fetcher
- Gate demo transport/client boundary that stays compatible with `GateInstrumentRecord`
- explicit `gate_demo` mode with guardrails blocking accidental live transport
- predictable config failure when `CEX_TBOT_EXECUTION_MODE=gate_demo` but `GATE_DEMO_API` is missing
- typed eligibility reason taxonomy for controlled universe decisions

## Phase 3 status

Implemented foundation pieces:
- proposal validation against universe eligibility and confidence thresholds
- split-entry total checks
- leg price checks against entry zone
- direction-aware stop-loss geometry for LONG/SHORT
- direction-aware take-profit ladder checks
- minimum reward sanity versus stop distance
- portfolio/risk evaluation against:
  - max open positions
  - max daily drawdown
  - aggregate open risk including pending reservations
  - single-trade risk above portfolio cap
- pre-execution recheck for expiry/freshness
- pending risk reservation book skeleton

## Phase 4 status

Approval-flow foundation now includes:
- strict parser for:
  - `APPROVE <proposal_id>`
  - `REJECT <proposal_id>`
  - `MODIFY <proposal_id>: <changes>`
- approval decision recording
- proposal status transition mapping for approve/reject/modify
- in-memory proposal store
- approval history per proposal
- review card builder for operator-facing proposal summaries
- `MODIFY` revalidation path that:
  - supersedes old proposal
  - inserts replacement proposal
  - bumps proposal version
  - returns replacement to `PENDING_APPROVAL`
  - yields a fresh review card for the replacement
- invalid free-text commands stay non-strict and do not transition state

## Phase 2–4 tail work completed

- market snapshot freshness service added
- universe refresh policy added
- risk consistency now checks `risk_usd` vs `risk_percent` against portfolio equity
- anti-averaging-down rule added to risk consistency checks
- review cards added for approval/revalidation flow

## Phase 5 status

Execution/simulator foundation now includes:
- simulator position model
- fill events with fee/slippage fields
- split-leg fill application
- TP1 partial close + TP2 full close lifecycle
- stop-loss handling
- realized PnL / remaining size / total fees tracking
- execution orchestrator with pre-execution risk check
- execution journal for:
  - pre-execution check
  - fills
  - TP1 partial close
  - TP2 full close
  - stop trigger
- execution state snapshots via in-memory state store
- combined trade timeline builder (events + snapshots)
- file-backed JSONL persistence for:
  - execution events
  - position state snapshots
- expired proposal rejection at execution time using actual current time

## Operator-facing output

The repo now includes:
- a text report builder that combines review card, execution timeline, and latest position state
- a workflow service with higher-level branches:
  - approve only
  - approve + execute + report
  - reject + report
  - modify + revalidate + report
- an operator command router that can:
  - parse approval commands
  - choose the matching workflow branch
  - render plain or Telegram-friendly output
- operator transcript / audit entries for command outcomes
- a unified in-memory session store for proposal + execution + operator layers
- a file-backed session bundle that reloads:
  - proposals
  - approval decisions
  - execution events
  - position snapshots
  - operator transcript

## Session visibility

The repo now includes a session summary builder that can aggregate:
- proposal counts and status breakdowns
- approval decision counts
- execution event volume
- state snapshot volume
- operator command counts

into a compact dashboard-like textual summary.

It also now includes dashboard-oriented widgets/read models for:
- KPI overview
- risk/activity overview
- latest trades
- operator activity

## Backend service layer

The repo now also includes a backend facade service that exposes a simpler API for:
- submit proposal
- run operator command
- get trade report
- get session summary
- list trades
- get trade detail

It also includes:
- a query/read-model layer
- serializer helpers for API-ready payloads
- payload-returning backend methods for command, trade, and session responses
- a thin API-surface layer with endpoint-like request contracts
- dashboard payload access for UI-oriented consumers
- trade query semantics for filtering / sorting / pagination

This is the intended bridge layer for future CLI, bot, web, or dashboard integrations.

## Application bootstrap + service wiring

This repo now has a single composition root:

- `cex_tbot.bootstrap.build_app(...)`

It wires the runtime graph in one place and returns a `TradingApplication` bundle with:

- config
- session storage (`TradeSessionStore` or `FileTradeSessionStore`)
- risk engine + pending-risk book
- simulator / execution orchestrator
- approval / workflow / operator router
- backend facade + API surface
- query / dashboard / summary services
- universe + validation services
- deterministic placeholder adapters for market data and instrument fetchers

The bootstrap intentionally stays away from live network logic. By default it uses in-memory runtime components and deterministic static providers/fetchers. If you pass `storage_dir=...`, session state becomes file-backed without changing service wiring.

### Gate demo boundary / guardrails

The repo now exposes a demo-safe integration path for Gate metadata wiring without introducing live transport:

- default runtime remains `paper_sim`
- supported execution modes are only `paper_sim`, `dry_run`, and `gate_demo`
- any live-like mode (`live`, `gate_live`, `prod`, etc.) fails fast during config load
- `gate_demo` mode requires `GATE_DEMO_API` and fails predictably if it is missing
- bootstrap wires a `GateDemoInstrumentFetcher` only in `gate_demo` mode
- the fetcher talks to a `GateDemoInstrumentClient` boundary that returns normal `GateInstrumentRecord` items, so the existing universe pipeline stays unchanged
- includes an optional `HttpxGateDemoInstrumentClient` for demo HTTP paths (metadata, account/order reads, `place_test_order`, `cancel_order`) without SDK dependency
- live-mode transport remains blocked by config guardrails

### Bootstrap usage

```python
from cex_tbot import build_app

app = build_app()
summary = app.backend.get_session_summary_payload()
```

### Runtime smoke check

```bash
PYTHONPATH=src python3 -m cex_tbot --format json
PYTHONPATH=src python3 -m cex_tbot --storage-dir .runtime/session --format json
PYTHONPATH=src python3 -m cex_tbot status --format json
PYTHONPATH=src python3 -m cex_tbot status --storage-dir .runtime/session --format json
```

### First runnable semi-auto demo flow

This repo now includes a deterministic local demo that exercises the semi-auto path end-to-end through the public API/service layer:

- build app
- seed a realistic sample proposal
- approve it
- either execute immediately or execute in an explicit second step
- emit operator-facing text plus machine-readable JSON
- optionally persist the session to JSONL files

Run the default single-step demo:

```bash
PYTHONPATH=src python3 -m cex_tbot demo
PYTHONPATH=src python3 -m cex_tbot demo --format json
```

Run the explicit two-step variant with file-backed session storage:

```bash
PYTHONPATH=src python3 -m cex_tbot demo --flow approve-then-execute --storage-dir .runtime/demo-session
```

The demo stays fully deterministic and demo-safe: no live exchange transport, no hidden network calls, only in-memory/file-backed components already wired by bootstrap.

## Operator-oriented CLI

The repo now also exposes simple local commands on top of the same public API surface.

Seed the demo proposal into file-backed storage:

```bash
PYTHONPATH=src python3 -m cex_tbot submit-demo --storage-dir .runtime/session --format json
```

List stored trades:

```bash
PYTHONPATH=src python3 -m cex_tbot list --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot list --storage-dir .runtime/session --format json
```

Approve only, then execute explicitly:

```bash
PYTHONPATH=src python3 -m cex_tbot command "APPROVE proposal_demo_btc_breakout" --approve-only --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot execute proposal_demo_btc_breakout --storage-dir .runtime/session
```

Inspect detail/report/dashboard/post-analysis views:

```bash
PYTHONPATH=src python3 -m cex_tbot detail proposal_demo_btc_breakout --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot report proposal_demo_btc_breakout --storage-dir .runtime/session --render-mode telegram
PYTHONPATH=src python3 -m cex_tbot dashboard --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot post-analysis --storage-dir .runtime/session
```

Available render modes for operator output:

- `plain`
- `operator`
- `telegram`
- `compact`

This gives us a cleaner operator UX and a stable shell-level integration surface for a later Telegram bot or UI layer.

## Telegram transport runner (group/topic -> bridge)

The repo now includes a minimal polling runner (`python-telegram-bot v20`) that:

- listens to group/supergroup text messages
- forwards them into `TransportCommandBridge`
- sends `BotReply` back into the same chat/topic thread
- parses inbound JSON proposal messages into `TradeProposal` with validation and stores them as `PENDING_APPROVAL`
- responds with same-topic approval request (`/trade_approve`, `/trade_reject`, `/modify`, `/trade_report`)
- supports separate sender policies for JSON proposal submitters and slash-command operators

Install optional Telegram dependency:

```bash
pip install .[telegram]
```

Run with explicit token:

```bash
PYTHONPATH=src python3 -m cex_tbot tg-runner --storage-dir .runtime/session --token "<telegram_bot_token>" --allowed-sender-ids 125619710 --allowed-json-sender-ids 225619711 --allowed-chat-ids -1003832858724 --allowed-thread-ids 7
```

Or via environment:

```bash
export CEX_TBOT_TELEGRAM_BOT_TOKEN="<telegram_bot_token>"
export CEX_TBOT_JSON_SUBMITTER_IDS="225619711"
PYTHONPATH=src python3 -m cex_tbot tg-runner --storage-dir .runtime/session --allowed-sender-ids 125619710
```

Role split:

- `--allowed-sender-ids` / `CEX_TBOT_ALLOWED_SENDER_IDS` control slash-command operators (`/trade_approve`, `/trade_reject`, `/modify`, status commands)
- `--allowed-json-sender-ids` / `CEX_TBOT_JSON_SUBMITTER_IDS` control who may submit proposal JSON into the topic
- if JSON submitters are not set explicitly, `tg-runner` falls back to the operator sender list

Example JSON message body for Telegram topic input:

```json
{
  "proposal_id": "proposal_live_btc_001",
  "agent_name": "Luma",
  "strategy_id": "pullback",
  "strategy_version": "v1",
  "market_context_id": "ctx_live_btc_001",
  "symbol": "BTC_USDT",
  "timeframe": "15m",
  "direction": "LONG",
  "entry_zone_min": 66000.0,
  "entry_zone_max": 66100.0,
  "entry_split": [
    {
      "leg_number": 1,
      "planned_entry_price": 66050.0,
      "allocation_pct": 100.0,
      "size_fraction": 1.0,
      "valid_until": "2026-04-03T12:20:00+00:00"
    }
  ],
  "stop_loss": 65750.0,
  "take_profit_1": 66400.0,
  "take_profit_2": 66750.0,
  "risk_percent": 0.5,
  "risk_usd": 5.0,
  "position_size": 1.0,
  "confidence_score": 0.78,
  "thesis": "Pullback reclaim and continuation setup.",
  "invalidity_condition": "Loss of reclaimed support.",
  "liquidity_check": "ok",
  "data_freshness_ms": 100,
  "created_at": "2026-04-03T12:00:00+00:00",
  "expires_at": "2026-04-03T12:30:00+00:00",
  "status": "PENDING_APPROVAL"
}
```

## Gate demo order status poller

`autosync-demo` now runs as a `PeriodicRunner` task:

- every cycle scans tracked proposals
- syncs only proposals that still have open demo orders
- calls Gate demo status endpoints via existing sync flow
- updates local position lifecycle state from synced order statuses

Run one cycle:

```bash
PYTHONPATH=src python3 -m cex_tbot autosync-demo --storage-dir .runtime/session --runs 1 --interval-sec 30 --format json
```

Run periodic cycles with optional Telegram conservative alerts:

```bash
PYTHONPATH=src python3 -m cex_tbot autosync-demo --storage-dir .runtime/session --runs 20 --interval-sec 15 --emit-telegram-alerts --format text
```

## VPS deployment baseline (.env + docker compose)

The repo now includes:

- `.env.example` - baseline runtime/env variables
- `.env.hostinger.example` - VPS-ready template with your Telegram group/topic wiring
- `docker-compose.yml` - REST + Telegram services
- persistent mount for `.runtime/` into container `/app/.runtime`

Quick start:

```bash
cp .env.example .env
mkdir -p .runtime/session
docker compose up -d
```

Services:

- `cex_tbot_rest`: serves FastAPI bridge on `:8000`
- `cex_tbot_telegram`: runs Telegram group/topic polling runner

Both services share `.runtime/session` state through host-mounted `.runtime/`.

Compose notes:

- `cex_tbot_rest` installs `.[dev]` only, because the REST bridge does not require Telegram runtime dependencies
- `cex_tbot_telegram` installs `.[dev,telegram]` and passes both `--allowed-sender-ids` and `--allowed-json-sender-ids`
- `httpx` is pinned to the `python-telegram-bot v20` compatible range in optional dependencies so both services can build cleanly
- file-backed session stores are refreshed on each REST request and Telegram update, so both processes can observe the same shared `.runtime/session` state
- `cex_tbot_rest` is now bound to `127.0.0.1:8000` in compose, so it is not exposed directly to the internet; publish it through a reverse proxy or SSH tunnel

Local smoke-run:

```bash
docker compose up -d cex_tbot_rest
docker compose run --rm -T cex_tbot_telegram sh -lc \
  "pip install --no-cache-dir -e .[dev,telegram] >/tmp/pip.log && \
   PYTHONPATH=src python scripts/docker_smoke_flow.py \
     --storage-dir .runtime/session \
     --chat-id -1003832858724 \
     --thread-id 7 \
     --operator-id 125619710 \
     --json-submitter-id 225619711"
curl -H "X-API-Key: ${CEX_TBOT_API_TOKEN}" http://127.0.0.1:8000/proposals/proposal_smoke_btc_001
```

That smoke-run verifies:

- Telegram JSON from the allowed topic is accepted
- proposal is persisted into shared `.runtime/session`
- slash approve command from a different allowed operator is accepted
- REST sees the same stored proposal state through the shared runtime mount

Hostinger/VPS quick notes:

- copy [`.env.hostinger.example`](c:\dev\cex_tbot\cex_tbot\.env.hostinger.example) to `.env`
- Telegram bot token env var name is `CEX_TBOT_TELEGRAM_BOT_TOKEN`
- the UI `X-API-Key` value is the same string you set in `CEX_TBOT_API_TOKEN`
- your group is already prefilled as `-1003832858724`
- your topic/thread is already prefilled as `7`
- you still need to set your own Telegram user id lists in `CEX_TBOT_ALLOWED_SENDER_IDS` and `CEX_TBOT_JSON_SUBMITTER_IDS`

Hostinger `Compose from URL`:

- use [`docker-compose.hostinger-url.yml`](c:\dev\cex_tbot\cex_tbot\docker-compose.hostinger-url.yml) instead of the local-dev [`docker-compose.yml`](c:\dev\cex_tbot\cex_tbot\docker-compose.yml)
- raw compose URL: `https://raw.githubusercontent.com/seleznevm/cex_tbot/main/docker-compose.hostinger-url.yml`
- this variant does not rely on `./:/app` bind mounts
- each container bootstraps the repo from `CEX_TBOT_REPO_ARCHIVE_URL`, installs the package, and then starts REST or Telegram
- shared runtime state is kept in the named volume `cex_tbot_runtime`
- set `CEX_TBOT_PUBLIC_PORT=8000` or another port in the Hostinger env screen if you want the UI exposed publicly
- the original [`docker-compose.yml`](c:\dev\cex_tbot\cex_tbot\docker-compose.yml) remains the better choice for SSH/VPS deploys where you already cloned the repo onto disk

Telegram proposal reply behavior:

- after a JSON proposal is accepted, the bot replies in the same topic with a human-readable approval card
- that card now includes symbol, direction, timeframe, proposal id, entry zone, stop loss, targets, risk, confidence, thesis, and ready-to-use action commands

## Runnable live-market pipeline entrypoint

The repo now also includes a minimal cron-friendly orchestrator that:

- refreshes public Binance market files into a market directory
- runs `LiveMarketProposalFlow`
- emits either a same-topic trade approval request or a same-topic no-trade notice
- persists the resulting proposal/no-trade into the existing operator/session workflow

Run it with file-backed session storage:

```bash
PYTHONPATH=src python3 -m cex_tbot live-market-run --storage-dir .runtime/session --market-dir /data/.openclaw/workspace/market --chat-id telegram:-1003832858724 --thread-id 7
PYTHONPATH=src python3 -m cex_tbot live-market-run --storage-dir .runtime/session --format json
```

The same entrypoint can now also act as the bot's internal scheduler/orchestrator instead of relying on OpenClaw cron as the primary trigger:

```bash
PYTHONPATH=src python3 -m cex_tbot live-market-run --storage-dir .runtime/session --market-dir /data/.openclaw/workspace/market --loop --interval-sec 300
PYTHONPATH=src python3 -m cex_tbot live-market-run --storage-dir .runtime/session --market-dir /data/.openclaw/workspace/market --loop --interval-sec 60 --runs 2 --format json
```

Behavior:
- default mode stays single-run for safe/manual invocation
- `--loop` enables the internal periodic runner
- `--runs` makes the loop bounded and testable
- re-entrant loop execution is blocked inside the runner

## Minimal REST bridge (FastAPI, optional)

The repo now also includes an optional FastAPI bridge layer in `cex_tbot.rest_api`.

What it exposes:

- `GET /health`
- `GET /session/summary`
- `GET /dashboard`
- `GET /post-analysis`
- `GET /proposals` (alias: `GET /trades`)
- `GET /proposals/{proposal_id}` (alias: `GET /trades/{proposal_id}`)
- `GET /trades/{proposal_id}/report`
- `GET /no-trades`
- `POST /proposals`
- `POST /commands`
- `POST /proposals/{proposal_id}/approve`
- `POST /proposals/{proposal_id}/reject`
- `POST /proposals/{proposal_id}/modify`
- `POST /trades/{proposal_id}/execute`

FastAPI/uvicorn/pydantic are now declared as real project dependencies, so the REST bridge is part of the installable MVP surface.

The REST layer now uses typed Pydantic request/response schemas, which makes the generated OpenAPI contract UI-friendly and predictable.

For MVP safety, the bridge also supports a simple API key gate via `CEX_TBOT_API_TOKEN`.
When it is set, clients must send `X-API-Key: <token>`.
In the built-in UI, the API key field should contain exactly the `CEX_TBOT_API_TOKEN` value from your `.env`.

Run it once optional deps are installed:

```bash
PYTHONPATH=src python3 -m cex_tbot serve-rest --storage-dir .runtime/session --host 127.0.0.1 --port 8000
```

This now also serves a built-in static SPA at `/` and frontend assets at `/app/...`.
The SPA polls the REST endpoints for dashboard, proposals, detail/report, and no-trade updates without full-page reloads.
It now also includes submit-proposal and halt/unhalt controls for operator-side MVP use.
For safety, the UI only stores the API key in browser session storage when you explicitly opt in, not persistent local storage.

If FastAPI/uvicorn are missing, the command fails fast with a clear message instead of breaking the core runtime.

This gives the project a real REST-shaped UI bridge without pulling transport/web concerns into the core trading modules.

## No-trade decisions and emergency halt

The local runtime now also supports two important semi-auto controls:

- first-class no-trade decisions
- emergency halt that blocks operator approval/execution flows

Store and inspect a demo no-trade decision:

```bash
PYTHONPATH=src python3 -m cex_tbot no-trade-demo --storage-dir .runtime/session --format json
PYTHONPATH=src python3 -m cex_tbot list-no-trades --storage-dir .runtime/session --format json
```

Activate and clear emergency halt:

```bash
PYTHONPATH=src python3 -m cex_tbot halt "manual-safety-stop" --storage-dir .runtime/session --format json
PYTHONPATH=src python3 -m cex_tbot unhalt --storage-dir .runtime/session --format json
PYTHONPATH=src python3 -m cex_tbot clear-safety --storage-dir .runtime/session --format json
```

When halt is active, operator commands and explicit execution requests return a blocked response instead of mutating trade state. The runtime also supports warning/block safety states, dashboard visibility for those states, and a manual `clear-safety` control for non-halt safety conditions.

## Bot-facing adapter layer

The repo now also exposes a bot-facing adapter contract that can sit behind Telegram/OpenClaw delivery without changing core trading logic.

Main entrypoint:

- `cex_tbot.bot_adapter.BotCommandAdapter`

It provides high-level handlers for:

- help
- status
- dashboard
- list
- detail
- report
- approve / approve_only
- execute
- halt / unhalt
- no-trade listing

The adapter returns simple `BotReply(text, parse_mode)` objects, so a messaging integration can decide how to deliver them.

This is an integration layer, not a network bot by itself. That is intentional: messaging transport stays outside the core repo logic.

## Current roadmap state

MVP-closed layers:

- dashboard and reporting (Z-10)
- stop conditions and auto-blocks (Z-11)
- post-analysis and calibration (Z-12)

The project now has:

- dashboard UI + REST + CLI surfaces
- safety controller with warning/block/halt logic
- post-analysis summaries, recommendations, export, and snapshot diffing

## Next steps

- richer partial-close accounting per target leg
- deeper paper-trading / execution realism
- real Telegram/OpenClaw message transport binding on top of the bot adapter
- stronger historical analytics / periodic review automation
- production-ready FastAPI dependency wiring + auth/rate-limit layer for the REST bridge
