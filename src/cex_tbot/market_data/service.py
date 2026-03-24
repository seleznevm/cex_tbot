from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from cex_tbot.market_data.models import MarketSnapshot
from cex_tbot.shared import ensure_utc, utc_now


@dataclass(frozen=True)
class SnapshotFreshness:
    symbol: str
    is_fresh: bool
    age_ms: int
    max_age_ms: int


class MarketDataService:
    def __init__(self, max_snapshot_age_ms: int = 60_000) -> None:
        self.max_snapshot_age_ms = max_snapshot_age_ms

    def get_freshness(self, snapshot: MarketSnapshot, *, now: datetime | None = None) -> SnapshotFreshness:
        effective_now = ensure_utc(now) if now is not None else utc_now()
        age = effective_now - snapshot.captured_at
        age_ms = max(int(age / timedelta(milliseconds=1)), 0)
        return SnapshotFreshness(
            symbol=snapshot.symbol,
            is_fresh=age_ms <= self.max_snapshot_age_ms,
            age_ms=age_ms,
            max_age_ms=self.max_snapshot_age_ms,
        )

    def is_snapshot_fresh(self, snapshot: MarketSnapshot, *, now: datetime | None = None) -> bool:
        return self.get_freshness(snapshot, now=now).is_fresh
