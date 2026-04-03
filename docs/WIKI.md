# cex_tbot Wiki

## 1. What this project is

`cex_tbot` is a semi-automatic CEX trading lab.

It is designed around one core rule:

- the strategy agent proposes
- the system validates
- the human approves or rejects
- execution runs only through guarded, deterministic paths

At the current stage, the project is **demo-safe** and **paper-sim oriented**.
It is not a hidden live trading bot.

---

## 2. What is already implemented

The repo already includes:

- proposal contracts
- validation and risk checks
- split-entry support
- approval / reject / modify flow
- execution simulator
- execution journal and snapshots
- session summaries and dashboard payloads
- richer CLI for operator workflows
- no-trade tracking
- emergency halt state
- bot-facing adapter layer for future Telegram/OpenClaw integration

---

## 3. Mental model of the system

Think of the program as 4 layers:

### Layer A — Trading decision objects

The system stores:

- trade proposals
- no-trade decisions
- approval decisions

### Layer B — Guardrails

The system checks:

- confidence threshold
- risk per trade
- aggregate risk
- pending risk reservations
- pre-execution validity
- emergency halt status

### Layer C — Operator workflows

The operator can:

- approve and execute immediately
- approve only
- execute later
- reject
- modify and revalidate
- halt the system
- inspect reports and dashboard state

### Layer D — Integration surfaces

The repo now exposes:

- Python API surface
- CLI commands
- bot-facing adapter contract

That means UI / Telegram / OpenClaw integration can be added on top without rewriting core logic.

---

## 4. Quick start

From repo root:

```bash
cd /data/.openclaw/workspace/cex_tbot
```

Use local package path:

```bash
PYTHONPATH=src python3 -m cex_tbot --format json
```

---

## 5. Bootstrap / status

Check that the app boots:

```bash
PYTHONPATH=src python3 -m cex_tbot --format json
```

or explicitly:

```bash
PYTHONPATH=src python3 -m cex_tbot status --format json
```

What this does:

- loads config
- builds runtime graph
- opens session storage
- returns current runtime/session summary

---

## 6. Run the built-in semi-auto demo

Single-step demo:

```bash
PYTHONPATH=src python3 -m cex_tbot demo --format text
PYTHONPATH=src python3 -m cex_tbot demo --format json
```

Two-step demo:

```bash
PYTHONPATH=src python3 -m cex_tbot demo --flow approve-then-execute --format text
PYTHONPATH=src python3 -m cex_tbot demo --flow approve-then-execute --format json
```

File-backed demo session:

```bash
PYTHONPATH=src python3 -m cex_tbot demo --storage-dir .runtime/demo-session --flow approve-then-execute --format json
```

What the demo does:

1. bootstraps the app
2. creates a deterministic proposal
3. stores it
4. approves it
5. executes it immediately or in a second step
6. returns reports / detail / session summary / dashboard

---

## 7. Operator CLI workflow

### 7.1 Submit demo proposal

```bash
PYTHONPATH=src python3 -m cex_tbot submit-demo --storage-dir .runtime/session --format json
```

### 7.2 List trades

```bash
PYTHONPATH=src python3 -m cex_tbot list --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot list --storage-dir .runtime/session --format json
```

### 7.3 Inspect detail

```bash
PYTHONPATH=src python3 -m cex_tbot detail proposal_demo_btc_breakout --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot detail proposal_demo_btc_breakout --storage-dir .runtime/session --format json
```

### 7.4 Approve without execution

```bash
PYTHONPATH=src python3 -m cex_tbot command "APPROVE proposal_demo_btc_breakout" --approve-only --storage-dir .runtime/session
```

### 7.5 Execute approved proposal

```bash
PYTHONPATH=src python3 -m cex_tbot execute proposal_demo_btc_breakout --storage-dir .runtime/session
```

### 7.6 Render report

```bash
PYTHONPATH=src python3 -m cex_tbot report proposal_demo_btc_breakout --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot report proposal_demo_btc_breakout --storage-dir .runtime/session --render-mode telegram
PYTHONPATH=src python3 -m cex_tbot report proposal_demo_btc_breakout --storage-dir .runtime/session --render-mode compact
```

### 7.7 Dashboard

```bash
PYTHONPATH=src python3 -m cex_tbot dashboard --storage-dir .runtime/session
PYTHONPATH=src python3 -m cex_tbot dashboard --storage-dir .runtime/session --format json
```

---

## 8. Render modes

The operator/report flow supports:

- `plain`
- `operator`
- `telegram`
- `compact`

Use them when you want the same underlying report rendered differently for shell vs messaging.

---

## 9. No-trade decisions

Store demo no-trade decision:

```bash
PYTHONPATH=src python3 -m cex_tbot no-trade-demo --storage-dir .runtime/session --format json
```

List no-trade decisions:

```bash
PYTHONPATH=src python3 -m cex_tbot list-no-trades --storage-dir .runtime/session --format json
```

Why it matters:

- not every valid market snapshot should become a trade
- the system should preserve “why we did nothing” too
- this is important for later analytics and calibration

---

## 10. Emergency halt

Activate halt:

```bash
PYTHONPATH=src python3 -m cex_tbot halt "manual-safety-stop" --storage-dir .runtime/session --format json
```

Clear halt:

```bash
PYTHONPATH=src python3 -m cex_tbot unhalt --storage-dir .runtime/session --format json
```

When halt is active:

- approve/execute paths are blocked
- the system returns a blocked response instead of mutating trade state

This is the current manual safety brake.

---

## 11. Bot-facing adapter

Python entrypoint:

```python
from cex_tbot import BotCommandAdapter, build_app

app = build_app(storage_dir=".runtime/session")
bot = BotCommandAdapter(app.backend)

reply = bot.handle_help()
print(reply.text)
print(reply.parse_mode)
```

Useful handlers:

- `handle_help()`
- `handle_status()`
- `handle_dashboard()`
- `handle_list()`
- `handle_detail(proposal_id)`
- `handle_report(proposal_id)`
- `handle_approve(proposal_id)`
- `handle_execute(proposal_id)`
- `handle_halt(reason)`
- `handle_unhalt()`
- `handle_no_trades()`

What this is for:

- Telegram bot integration
- OpenClaw-driven messaging integration
- future chat UI glue

What this is not:

- a network bot by itself
- a webhook server
- a Telegram SDK wrapper

It is intentionally an adapter layer only.

---

## 12. Bot command dispatcher

There is now also a text-command dispatcher layer on top of the adapter.

Python entrypoint:

```python
from cex_tbot import BotCommandAdapter, BotCommandDispatcher, build_app

app = build_app(storage_dir=".runtime/session")
adapter = BotCommandAdapter(app.backend)
dispatcher = BotCommandDispatcher(adapter)

reply = dispatcher.dispatch("/help")
print(reply.text)
```

Supported text commands:

- `/help`
- `/status`
- `/dashboard`
- `/list [limit]`
- `/detail <proposal_id>`
- `/report <proposal_id>`
- `/approve <proposal_id>`
- `/approve_only <proposal_id>`
- `/execute <proposal_id>`
- `/halt <reason>`
- `/unhalt`
- `/no_trades`
- `/seed_demo`
- `/seed_no_trade`

Why it exists:

- chat platforms deliver raw text
- the adapter exposes semantic operations
- the dispatcher bridges raw command text to semantic adapter calls

This is the most direct handoff point for a real Telegram/OpenClaw chat integration layer.

---

## Telegram runner

There is now a direct Telegram polling runner that bridges group/topic messages into `TransportCommandBridge`.

Install optional dependency:

```bash
pip install .[telegram]
```

Run it:

```bash
PYTHONPATH=src python3 -m cex_tbot tg-runner --storage-dir .runtime/session --token "<telegram_bot_token>" --allowed-sender-ids 125619710 --allowed-chat-ids -1003832858724 --allowed-thread-ids 7
```

Token can also be supplied with `CEX_TBOT_TELEGRAM_BOT_TOKEN`.

---

## 13. Minimal REST bridge

The repo now also contains an optional FastAPI-based REST bridge in `cex_tbot.rest_api`.

It is designed as a thin web wrapper over the existing `ApiSurface`, not as a second backend.

Endpoints:

- `GET /health`
- `GET /session/summary`
- `GET /dashboard`
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

FastAPI/uvicorn/pydantic are now declared project dependencies, so the REST bridge is part of the installable MVP surface.

The web layer now uses typed Pydantic schemas for request/response contracts, so `/openapi.json` and Swagger docs reflect the UI bridge properly instead of exposing raw anonymous dict payloads.

For minimal operator safety, the bridge can be protected with `CEX_TBOT_API_TOKEN`.
If set, every request must include `X-API-Key`.

Serve it like this once optional deps are available:

```bash
PYTHONPATH=src python3 -m cex_tbot serve-rest --storage-dir .runtime/session --host 127.0.0.1 --port 8000
```

The server now also serves a built-in static SPA at `/` plus assets under `/app/...`.
That SPA uses REST polling to refresh dashboard, proposals, proposal detail/report, and no-trade views without full-page reloads.

This is the current UI-first bridge layer for local REST integration.

---

## 14. Safe usage pattern right now

Recommended operator sequence:

1. `status`
2. `submit-demo` or store a real proposal via Python API
3. `detail`
4. `command "APPROVE ..." --approve-only`
5. `report`
6. `execute`
7. `dashboard`

If anything looks wrong:

8. `halt "reason"`

That keeps the system aligned with the semi-auto design.

---

## 13. Current limitations

Important: the project is still pre-product.

Current limits:

- no real Telegram transport in this repo yet
- no real exchange live trading transport
- no production-grade historical analytics warehouse yet (current review snapshots are file-based)
- no production-grade policy automation beyond current MVP warning/block/halt stack
- demo proposal timestamps are deterministic, so delayed execution can legitimately fail pre-exec checks

That last point is not a bug — it proves guardrails are alive.

---

## 14. Current milestone status

### Done (MVP)

- Z-01 Architecture and boundaries
- Z-02 Universe / whitelist logic
- Z-03 Risk engine and guardrails
- Z-04 Proposal schema
- Z-05 Confidence + no-trade logic
- Z-06 Split-entry logic
- Z-07 Semi-auto approval flow
- Z-08 Paper/test execution layer
- Z-09 Journal of trades and no-trade decisions
- Z-10 Dashboard and reporting
- Z-11 Stop conditions and auto-blocks
- Z-12 Post-analysis and calibration

### Remaining beyond current MVP

- real transport integration on top of bot adapter
- richer execution realism / paper-trading operational loop
- stronger historical analytics and review automation
- production-grade policy automation and deployment hardening

---

## 15. Testing

Run full test suite:

```bash
python3 -m unittest discover -s tests -t .
```

Run focused test groups:

```bash
python3 -m unittest tests.test_demo tests.test_cli_commands tests.test_bot_adapter -v
python3 -m unittest tests.test_no_trade_and_halt tests.test_cli_halt_no_trade -v
```

---

## 16. Short conclusion

Right now `cex_tbot` is best understood as:

**a guarded semi-auto trading lab core with CLI + bot-adapter integration surfaces**

Not a toy anymore.
Not a live bot yet.
Exactly the awkward and useful middle stage where the system starts becoming real.
