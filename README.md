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

This is the intended bridge layer for future CLI, bot, web, or dashboard integrations.

## Next steps

- richer partial-close accounting per target leg
- richer report formatting / channel-specific rendering
- more operator commands and workflow branches
- higher-level dashboard/UI views
