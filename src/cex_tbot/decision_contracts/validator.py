from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts.models import TradeProposal
from cex_tbot.enums import ProposalReasonCode, TradeDirection
from cex_tbot.universe import UniverseService, WhitelistedInstrument


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reason_code: ProposalReasonCode | None = None
    details: str = ""


class ProposalValidator:
    def __init__(self, config: BotConfig, universe_service: UniverseService) -> None:
        self.config = config
        self.universe_service = universe_service

    def validate(
        self,
        proposal: TradeProposal,
        instruments: list[WhitelistedInstrument],
        *,
        now: datetime | None = None,
    ) -> ValidationResult:
        effective_now = proposal.created_at if now is None else now
        if proposal.expires_at <= effective_now:
            return ValidationResult(False, ProposalReasonCode.PROPOSAL_EXPIRED, "proposal already expired")
        eligibility = self.universe_service.get_symbol_eligibility(proposal.symbol, instruments, now=effective_now)
        if eligibility.status.name != "ELIGIBLE":
            code = ProposalReasonCode.STALE_MARKET_DATA if eligibility.status.name == "STALE" else ProposalReasonCode.INSTRUMENT_NOT_ELIGIBLE
            return ValidationResult(False, code, f"symbol eligibility={eligibility.status}")
        if proposal.confidence_score < self.config.min_confidence_score:
            return ValidationResult(False, ProposalReasonCode.CONFIDENCE_TOO_LOW, "confidence below threshold")
        if proposal.stop_loss <= 0:
            return ValidationResult(False, ProposalReasonCode.STOP_LOSS_INVALID, "stop loss must be positive")
        if proposal.position_size <= 0:
            return ValidationResult(False, ProposalReasonCode.POSITION_SIZE_INVALID, "position size must be positive")
        if proposal.risk_percent <= 0 or proposal.risk_usd <= 0:
            return ValidationResult(False, ProposalReasonCode.RISK_CALCULATION_MISMATCH, "risk values must be positive")
        if proposal.data_freshness_ms < 0:
            return ValidationResult(False, ProposalReasonCode.STALE_MARKET_DATA, "negative freshness is invalid")
        if len(proposal.entry_split) > 2:
            return ValidationResult(False, ProposalReasonCode.ENTRY_SPLIT_INVALID, "max 2 legs supported")

        allocation_total = round(sum(leg.allocation_pct for leg in proposal.entry_split), 6)
        size_fraction_total = round(sum(leg.size_fraction for leg in proposal.entry_split), 6)
        if allocation_total != 100.0 or size_fraction_total != 1.0:
            return ValidationResult(False, ProposalReasonCode.ENTRY_SPLIT_INVALID, "entry split totals invalid")

        for leg in proposal.entry_split:
            if leg.planned_entry_price < proposal.entry_zone_min or leg.planned_entry_price > proposal.entry_zone_max:
                return ValidationResult(False, ProposalReasonCode.ENTRY_SPLIT_INVALID, "leg price outside entry zone")
            if leg.valid_until > proposal.expires_at:
                return ValidationResult(False, ProposalReasonCode.ENTRY_SPLIT_INVALID, "leg valid_until exceeds proposal expiry")

        avg_entry = self._average_entry(proposal)
        if proposal.direction == TradeDirection.LONG:
            if proposal.stop_loss >= proposal.entry_zone_min:
                return ValidationResult(False, ProposalReasonCode.STOP_LOSS_INVALID, "long stop loss must sit below entry zone")
            if proposal.take_profit_1 <= avg_entry or proposal.take_profit_2 <= proposal.take_profit_1:
                return ValidationResult(False, ProposalReasonCode.RISK_CALCULATION_MISMATCH, "long tp ladder must be above entry and progressive")
        elif proposal.direction == TradeDirection.SHORT:
            if proposal.stop_loss <= proposal.entry_zone_max:
                return ValidationResult(False, ProposalReasonCode.STOP_LOSS_INVALID, "short stop loss must sit above entry zone")
            if proposal.take_profit_1 >= avg_entry or proposal.take_profit_2 >= proposal.take_profit_1:
                return ValidationResult(False, ProposalReasonCode.RISK_CALCULATION_MISMATCH, "short tp ladder must be below entry and progressive")

        reward_1 = abs(proposal.take_profit_1 - avg_entry)
        reward_2 = abs(proposal.take_profit_2 - avg_entry)
        risk_distance = abs(avg_entry - proposal.stop_loss)
        if reward_1 <= 0 or reward_2 <= 0 or risk_distance <= 0:
            return ValidationResult(False, ProposalReasonCode.RISK_CALCULATION_MISMATCH, "risk/reward distances must be positive")
        if reward_1 < risk_distance * 0.5:
            return ValidationResult(False, ProposalReasonCode.RISK_CALCULATION_MISMATCH, "tp1 reward too small relative to stop distance")
        return ValidationResult(True)

    @staticmethod
    def _average_entry(proposal: TradeProposal) -> float:
        weighted_sum = sum(leg.planned_entry_price * leg.size_fraction for leg in proposal.entry_split)
        total_fraction = sum(leg.size_fraction for leg in proposal.entry_split)
        return weighted_sum / total_fraction
