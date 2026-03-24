from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts.models import TradeProposal
from cex_tbot.enums import ProposalReasonCode
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

    def validate(self, proposal: TradeProposal, instruments: list[WhitelistedInstrument]) -> ValidationResult:
        if proposal.expires_at <= proposal.created_at:
            return ValidationResult(False, ProposalReasonCode.PROPOSAL_EXPIRED, "proposal already expired")
        eligibility = self.universe_service.get_symbol_eligibility(proposal.symbol, instruments)
        if eligibility.reason is not None and eligibility.status.name != "ELIGIBLE":
            code = (
                ProposalReasonCode.STALE_MARKET_DATA
                if eligibility.status.name == "STALE"
                else ProposalReasonCode.INSTRUMENT_NOT_ELIGIBLE
            )
            return ValidationResult(False, code, f"symbol eligibility={eligibility.status}")
        if proposal.confidence_score < self.config.min_confidence_score:
            return ValidationResult(False, ProposalReasonCode.CONFIDENCE_TOO_LOW, "confidence below threshold")
        if proposal.stop_loss <= 0:
            return ValidationResult(False, ProposalReasonCode.STOP_LOSS_INVALID, "stop loss must be positive")
        if proposal.position_size <= 0:
            return ValidationResult(False, ProposalReasonCode.POSITION_SIZE_INVALID, "position size must be positive")
        if proposal.risk_percent <= 0 or proposal.risk_usd <= 0:
            return ValidationResult(False, ProposalReasonCode.RISK_CALCULATION_MISMATCH, "risk values must be positive")
        if len(proposal.entry_split) > 2:
            return ValidationResult(False, ProposalReasonCode.ENTRY_SPLIT_INVALID, "max 2 legs supported")
        allocation_total = round(sum(leg.allocation_pct for leg in proposal.entry_split), 6)
        size_fraction_total = round(sum(leg.size_fraction for leg in proposal.entry_split), 6)
        if allocation_total != 100.0 or size_fraction_total != 1.0:
            return ValidationResult(False, ProposalReasonCode.ENTRY_SPLIT_INVALID, "entry split totals invalid")
        return ValidationResult(True)
