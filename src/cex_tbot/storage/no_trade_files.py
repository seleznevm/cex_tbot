from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from cex_tbot.decision_contracts import NoTradeDecision
from cex_tbot.enums import NoTradeReasonCode
from cex_tbot.no_trade_store import InMemoryNoTradeStore
from cex_tbot.shared import ensure_utc


class FileNoTradeStore(InMemoryNoTradeStore):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def refresh_from_disk(self) -> None:
        self._decisions.clear()
        if self.path.exists():
            self._load()

    def add(self, decision: NoTradeDecision) -> NoTradeDecision:
        saved = super().add(decision)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._serialize(saved), ensure_ascii=False) + "\n")
        return saved

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            decision = NoTradeDecision(
                agent_name=raw["agent_name"],
                strategy_id=raw["strategy_id"],
                strategy_version=raw["strategy_version"],
                symbol=raw["symbol"],
                timeframe=raw["timeframe"],
                confidence_score=raw["confidence_score"],
                reason_code=NoTradeReasonCode(raw["reason_code"]),
                reason_text=raw["reason_text"],
                market_context_id=raw["market_context_id"],
                liquidity_check=raw["liquidity_check"],
                data_freshness_ms=raw["data_freshness_ms"],
                decision_id=raw["decision_id"],
                created_at=ensure_utc(datetime.fromisoformat(raw["created_at"])),
            )
            self._decisions[decision.decision_id] = decision

    @staticmethod
    def _serialize(decision: NoTradeDecision) -> dict[str, object]:
        data = asdict(decision)
        data["reason_code"] = decision.reason_code.value
        data["created_at"] = decision.created_at.isoformat()
        return data
