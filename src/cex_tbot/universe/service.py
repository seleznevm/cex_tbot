from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from cex_tbot.config import BotConfig
from cex_tbot.enums import EligibilityReasonCode, EligibilityStatus
from cex_tbot.shared import utc_now
from cex_tbot.universe.models import EligibilityDecision, RawInstrument, WhitelistedInstrument


class UniverseService:
    """Phase 2 service for deterministic whitelist/eligibility evaluation."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def compute_liquidity_score(self, instrument: WhitelistedInstrument) -> float:
        score = instrument.volume_24h + instrument.open_interest + instrument.top_book_depth
        penalty = instrument.spread_bps * 1000
        return max(score - penalty, 0.0)

    def evaluate_instrument(self, instrument: WhitelistedInstrument) -> EligibilityDecision:
        if instrument.status != "active":
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason=EligibilityReasonCode.INSTRUMENT_INACTIVE,
                liquidity_score=0.0,
            )
        if instrument.quote_asset != "USDT":
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason=EligibilityReasonCode.QUOTE_ASSET_NOT_USDT,
                liquidity_score=0.0,
            )
        if instrument.is_new_listing or instrument.listing_age_hours < self.config.min_listing_age_hours:
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason=EligibilityReasonCode.LISTING_AGE_BELOW_THRESHOLD,
                liquidity_score=0.0,
            )
        if instrument.spread_bps > self.config.max_spread_bps:
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason=EligibilityReasonCode.SPREAD_ABOVE_THRESHOLD,
                liquidity_score=0.0,
            )
        if instrument.volume_24h <= 0 or instrument.open_interest <= 0 or instrument.top_book_depth <= 0:
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason=EligibilityReasonCode.INSUFFICIENT_MARKET_DEPTH,
                liquidity_score=0.0,
            )
        score = self.compute_liquidity_score(instrument)
        return EligibilityDecision(
            symbol=instrument.symbol,
            status=EligibilityStatus.ELIGIBLE,
            reason=EligibilityReasonCode.PASSES_PHASE2_RULES,
            liquidity_score=score,
        )

    def materialize_instrument(self, raw: RawInstrument) -> WhitelistedInstrument:
        now = utc_now()
        eligible_until = now + timedelta(minutes=self.config.universe_refresh_minutes)
        return WhitelistedInstrument(
            symbol=raw.symbol,
            quote_asset=raw.quote_asset,
            status=raw.status,
            is_new_listing=raw.is_new_listing,
            listing_age_hours=raw.listing_age_hours,
            volume_24h=raw.volume_24h,
            open_interest=raw.open_interest,
            spread_bps=raw.spread_bps,
            top_book_depth=raw.top_book_depth,
            last_market_check_at=now,
            last_universe_refresh_at=now,
            eligible_until=eligible_until,
        )

    def apply_decision(self, instrument: WhitelistedInstrument) -> WhitelistedInstrument:
        decision = self.evaluate_instrument(instrument)
        return replace(
            instrument,
            liquidity_score=decision.liquidity_score,
            eligibility_status=decision.status,
            eligibility_reason=decision.reason,
        )

    def refresh_universe(self, raw_instruments: list[RawInstrument]) -> list[WhitelistedInstrument]:
        materialized = [self.materialize_instrument(item) for item in raw_instruments]
        return [self.apply_decision(item) for item in materialized]

    def get_symbol_eligibility(
        self,
        symbol: str,
        instruments: list[WhitelistedInstrument],
        *,
        now: datetime | None = None,
    ) -> EligibilityDecision:
        effective_now = now or utc_now()
        for instrument in instruments:
            if instrument.symbol != symbol:
                continue
            if instrument.eligible_until <= effective_now:
                return EligibilityDecision(
                    symbol=symbol,
                    status=EligibilityStatus.STALE,
                    reason=EligibilityReasonCode.ELIGIBILITY_WINDOW_EXPIRED,
                    liquidity_score=instrument.liquidity_score,
                    evaluated_at=effective_now,
                )
            if instrument.eligibility_status == EligibilityStatus.UNKNOWN:
                return self.evaluate_instrument(instrument)
            return EligibilityDecision(
                symbol=symbol,
                status=instrument.eligibility_status,
                reason=instrument.eligibility_reason,
                liquidity_score=instrument.liquidity_score,
                evaluated_at=effective_now,
            )
        return EligibilityDecision(
            symbol=symbol,
            status=EligibilityStatus.UNKNOWN,
            reason=EligibilityReasonCode.SYMBOL_NOT_FOUND,
            liquidity_score=0.0,
            evaluated_at=effective_now,
        )

    def rank_whitelist(self, instruments: list[WhitelistedInstrument]) -> list[WhitelistedInstrument]:
        normalized = [
            self.apply_decision(item) if item.eligibility_status == EligibilityStatus.UNKNOWN else item
            for item in instruments
        ]
        eligible = [item for item in normalized if item.eligibility_status == EligibilityStatus.ELIGIBLE]
        eligible.sort(key=lambda item: (item.liquidity_score, item.volume_24h, item.open_interest), reverse=True)
        return eligible[: self.config.whitelist_size]
