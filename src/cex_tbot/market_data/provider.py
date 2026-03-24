from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cex_tbot.market_data.models import MarketSnapshot


@dataclass(frozen=True)
class StaticMarketDataProvider:
    """Deterministic in-memory provider for early Phase 2 development/tests."""

    snapshots: tuple[MarketSnapshot, ...]

    @classmethod
    def from_iterable(cls, snapshots: Iterable[MarketSnapshot]) -> "StaticMarketDataProvider":
        return cls(tuple(snapshots))

    def list_snapshots(self) -> list[MarketSnapshot]:
        return list(self.snapshots)

    def get_snapshot(self, symbol: str) -> MarketSnapshot | None:
        for snapshot in self.snapshots:
            if snapshot.symbol == symbol:
                return snapshot
        return None
