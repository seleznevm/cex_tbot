from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cex_tbot.universe.models import RawInstrument


@dataclass(frozen=True)
class GateInstrumentRecord:
    """Raw Gate instrument metadata record used by the Phase 2 adapter skeleton."""

    name: str
    in_delisting: bool = False
    trade_status: str = "tradable"
    quanto_multiplier: float = 0.0
    order_size_min: float = 0.0
    mark_price_round: str = "0.01"
    ref_rebate_rate: str = "0"
    funding_rate_indicative: str = "0"
    leverage_min: str = "1"
    leverage_max: str = "20"
    maker_fee_rate: str = "0"
    taker_fee_rate: str = "0"
    risk_limit_base: str = "0"
    is_new_listing: bool = False
    listing_age_hours: int = 0
    quote_asset: str = "USDT"
    volume_24h: float = 0.0
    open_interest: float = 0.0
    spread_bps: float = 0.0
    top_book_depth: float = 0.0


class GateInstrumentMetadataAdapter:
    """Deterministic adapter from Gate metadata records to RawInstrument skeletons."""

    def normalize_record(self, record: GateInstrumentRecord) -> RawInstrument:
        return RawInstrument(
            symbol=record.name,
            quote_asset=record.quote_asset,
            status=self._normalize_status(record),
            is_new_listing=record.is_new_listing,
            listing_age_hours=record.listing_age_hours,
            volume_24h=record.volume_24h,
            open_interest=record.open_interest,
            spread_bps=record.spread_bps,
            top_book_depth=record.top_book_depth,
        )

    def normalize_records(self, records: Iterable[GateInstrumentRecord]) -> list[RawInstrument]:
        return [self.normalize_record(record) for record in records]

    @staticmethod
    def _normalize_status(record: GateInstrumentRecord) -> str:
        if record.in_delisting:
            return "delisting"
        if record.trade_status.lower() in {"tradable", "active"}:
            return "active"
        return record.trade_status.lower()
