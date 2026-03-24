from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.market_data.models import MarketSnapshot
from cex_tbot.shared import ensure_utc, utc_now


@dataclass(frozen=True)
class RawMarketTicker:
    symbol: str
    best_bid: float
    best_ask: float
    last_price: float
    volume_24h: float
    open_interest: float
    top_book_depth: float
    captured_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "captured_at", ensure_utc(self.captured_at))


class MarketDataNormalizer:
    """Deterministic Phase 2 normalizer from raw exchange ticker data to MarketSnapshot."""

    def normalize_ticker(self, ticker: RawMarketTicker) -> MarketSnapshot:
        spread_bps = self._compute_spread_bps(ticker.best_bid, ticker.best_ask)
        return MarketSnapshot(
            symbol=ticker.symbol,
            bid=ticker.best_bid,
            ask=ticker.best_ask,
            last_price=ticker.last_price,
            volume_24h=ticker.volume_24h,
            open_interest=ticker.open_interest,
            spread_bps=spread_bps,
            top_book_depth=ticker.top_book_depth,
            captured_at=ticker.captured_at,
        )

    @staticmethod
    def _compute_spread_bps(best_bid: float, best_ask: float) -> float:
        if best_bid <= 0 or best_ask <= 0:
            raise ValueError("best_bid and best_ask must be positive")
        if best_ask < best_bid:
            raise ValueError("best_ask must be >= best_bid")
        midpoint = (best_bid + best_ask) / 2
        if midpoint <= 0:
            raise ValueError("midpoint must be positive")
        return ((best_ask - best_bid) / midpoint) * 10_000

    def normalize_minimal(
        self,
        *,
        symbol: str,
        best_bid: float,
        best_ask: float,
        last_price: float,
        volume_24h: float,
        open_interest: float,
        top_book_depth: float,
        captured_at: datetime | None = None,
    ) -> MarketSnapshot:
        return self.normalize_ticker(
            RawMarketTicker(
                symbol=symbol,
                best_bid=best_bid,
                best_ask=best_ask,
                last_price=last_price,
                volume_24h=volume_24h,
                open_interest=open_interest,
                top_book_depth=top_book_depth,
                captured_at=captured_at or utc_now(),
            )
        )
