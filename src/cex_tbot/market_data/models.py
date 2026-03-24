from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.shared import ensure_utc, utc_now


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    bid: float
    ask: float
    last_price: float
    volume_24h: float
    open_interest: float
    spread_bps: float
    top_book_depth: float
    captured_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "captured_at", ensure_utc(self.captured_at))
