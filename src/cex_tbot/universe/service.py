from __future__ import annotations

from dataclasses import replace

from cex_tbot.config import BotConfig
from cex_tbot.enums import EligibilityStatus
from cex_tbot.universe.models import EligibilityDecision, WhitelistedInstrument


class UniverseService:
    """Phase 2 skeleton for whitelist/eligibility evaluation."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def compute_liquidity_score(self, instrument: WhitelistedInstrument) -> float:
        score = instrument.volume_24h + instrument.open_interest + instrument.top_book_depth
        penalty = instrument.spread_bps * 1000
        return max(score - penalty, 0.0)

    def evaluate_instrument(self, instrument: WhitelistedInstrument) -> EligibilityDecision:
        if instrument.is_new_listing or instrument.listing_age_hours < self.config.min_listing_age_hours:
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason="listing_age_below_threshold",
                liquidity_score=0.0,
            )
        if instrument.spread_bps > self.config.max_spread_bps:
            return EligibilityDecision(
                symbol=instrument.symbol,
                status=EligibilityStatus.INELIGIBLE,
                reason="spread_above_threshold",
                liquidity_score=0.0,
            )
        score = self.compute_liquidity_score(instrument)
        return EligibilityDecision(
            symbol=instrument.symbol,
            status=EligibilityStatus.ELIGIBLE,
            reason="passes_skeleton_rules",
            liquidity_score=score,
        )

    def apply_decision(self, instrument: WhitelistedInstrument) -> WhitelistedInstrument:
        decision = self.evaluate_instrument(instrument)
        return replace(
            instrument,
            liquidity_score=decision.liquidity_score,
            eligibility_status=decision.status,
            eligibility_reason=decision.reason,
        )

    def rank_whitelist(self, instruments: list[WhitelistedInstrument]) -> list[WhitelistedInstrument]:
        evaluated = [self.apply_decision(item) for item in instruments]
        eligible = [item for item in evaluated if item.eligibility_status == EligibilityStatus.ELIGIBLE]
        eligible.sort(key=lambda item: item.liquidity_score, reverse=True)
        return eligible[: self.config.whitelist_size]
