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

## Next steps

- real market metadata adapter
- Gate instrument fetcher
- proposal validation and risk engine
- journal/state persistence
