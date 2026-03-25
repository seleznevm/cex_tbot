from __future__ import annotations

from cex_tbot.decision_contracts import NoTradeDecision


class InMemoryNoTradeStore:
    def __init__(self) -> None:
        self._decisions: dict[str, NoTradeDecision] = {}

    def add(self, decision: NoTradeDecision) -> NoTradeDecision:
        self._decisions[decision.decision_id] = decision
        return decision

    def list(self) -> list[NoTradeDecision]:
        return list(self._decisions.values())

    def by_symbol(self, symbol: str) -> list[NoTradeDecision]:
        return [decision for decision in self._decisions.values() if decision.symbol == symbol]
