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

## Next steps

- market metadata adapters
- whitelist refresh implementation
- eligibility scoring rules
- proposal validation and risk engine
