from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.enums import ContractType, EligibilityStatus, Exchange, MarketType
from cex_tbot.shared import ensure_utc, utc_now


@dataclass(frozen=True)
class RawInstrument:
    symbol: str
    quote_asset: str = "USDT"
    status: str = "active"
    is_new_listing: bool = False
    listing_age_hours: int = 0
    volume_24h: float = 0.0
    open_interest: float = 0.0
    spread_bps: float = 0.0
    top_book_depth: float = 0.0


@dataclass(frozen=True)
class WhitelistedInstrument:
    symbol: str
    exchange: Exchange = Exchange.GATE
    market_type: MarketType = MarketType.USDT_PERPETUAL
    contract_type: ContractType = ContractType.PERPETUAL
    quote_asset: str = "USDT"
    status: str = "active"
    is_manual_safe_candidate: bool = False
    is_new_listing: bool = False
    listing_age_hours: int = 0
    volume_24h: float = 0.0
    open_interest: float = 0.0
    spread_bps: float = 0.0
    top_book_depth: float = 0.0
    liquidity_score: float = 0.0
    eligibility_status: EligibilityStatus = EligibilityStatus.UNKNOWN
    eligibility_reason: str = "not_evaluated"
    last_market_check_at: datetime = field(default_factory=utc_now)
    last_universe_refresh_at: datetime = field(default_factory=utc_now)
    eligible_until: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "last_market_check_at", ensure_utc(self.last_market_check_at))
        object.__setattr__(self, "last_universe_refresh_at", ensure_utc(self.last_universe_refresh_at))
        object.__setattr__(self, "eligible_until", ensure_utc(self.eligible_until))


@dataclass(frozen=True)
class EligibilityDecision:
    symbol: str
    status: EligibilityStatus
    reason: str
    liquidity_score: float
    evaluated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at))
