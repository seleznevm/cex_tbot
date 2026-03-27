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
- no concrete HTTP/live trading transport is shipped in this commit; integrations must inject a demo client explicitly

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

Run it once optional deps are installed:

```bash
PYTHONPATH=src python3 -m cex_tbot serve-rest --storage-dir .runtime/session --host 127.0.0.1 --port 8000
```

This now also serves a built-in static SPA at `/` and frontend assets at `/app/...`.
The SPA polls the REST endpoints for dashboard, proposals, detail/report, and no-trade updates without full-page reloads.
It now also includes submit-proposal and halt/unhalt controls for operator-side MVP use.

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
