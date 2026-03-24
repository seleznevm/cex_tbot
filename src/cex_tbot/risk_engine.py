from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts.models import TradeProposal
from cex_tbot.enums import ProposalReasonCode, TradeDirection
from cex_tbot.shared import new_id


@dataclass(frozen=True)
class PortfolioState:
    equity: float
    daily_drawdown_pct: float = 0.0
    aggregate_open_risk_pct: float = 0.0
    reserved_pending_risk_pct: float = 0.0
    open_positions_count: int = 0


@dataclass(frozen=True)
class RiskEvaluation:
    is_approved: bool
    reason_code: ProposalReasonCode
    open_risk_pct: float
    reserved_risk_pct: float
    notes: str = ""


@dataclass
class PendingRiskBook:
    reservations: dict[str, float] = field(default_factory=dict)

    def reserve(self, proposal_id: str, risk_percent: float) -> None:
        self.reservations[proposal_id] = risk_percent

    def release(self, proposal_id: str) -> None:
        self.reservations.pop(proposal_id, None)

    @property
    def total_reserved_risk_pct(self) -> float:
        return sum(self.reservations.values())


class RiskEngine:
    def __init__(self, config: BotConfig, pending_risk_book: PendingRiskBook | None = None) -> None:
        self.config = config
        self.pending_risk_book = pending_risk_book or PendingRiskBook()

    def evaluate(self, proposal: TradeProposal, portfolio: PortfolioState) -> RiskEvaluation:
        consistency = self.check_proposal_consistency(proposal, portfolio.equity)
        if consistency is not None:
            return RiskEvaluation(False, consistency, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)
        if portfolio.open_positions_count >= self.config.max_open_positions:
            return RiskEvaluation(False, ProposalReasonCode.MAX_OPEN_POSITIONS_REACHED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)
        if portfolio.daily_drawdown_pct >= self.config.max_daily_drawdown_percent:
            return RiskEvaluation(False, ProposalReasonCode.MAX_DAILY_DRAWDOWN_REACHED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)
        total_projected_risk = portfolio.aggregate_open_risk_pct + self.pending_risk_book.total_reserved_risk_pct + proposal.risk_percent
        if total_projected_risk > self.config.max_aggregate_open_risk_percent:
            return RiskEvaluation(False, ProposalReasonCode.TOTAL_OPEN_RISK_EXCEEDED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct, notes=f"projected_risk={total_projected_risk}")
        return RiskEvaluation(True, ProposalReasonCode.RISK_BUDGET_RESERVED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)

    def check_proposal_consistency(self, proposal: TradeProposal, equity: float) -> ProposalReasonCode | None:
        if proposal.risk_percent > self.config.max_aggregate_open_risk_percent:
            return ProposalReasonCode.RISK_CALCULATION_MISMATCH
        avg_entry = self._average_entry(proposal)
        stop_distance = abs(avg_entry - proposal.stop_loss)
        if stop_distance <= 0:
            return ProposalReasonCode.STOP_LOSS_INVALID
        if proposal.direction == TradeDirection.LONG and any(leg.planned_entry_price < avg_entry for leg in proposal.entry_split[1:]):
            return ProposalReasonCode.AVERAGING_DOWN_FORBIDDEN
        if proposal.direction == TradeDirection.SHORT and any(leg.planned_entry_price > avg_entry for leg in proposal.entry_split[1:]):
            return ProposalReasonCode.AVERAGING_DOWN_FORBIDDEN
        if proposal.risk_usd <= 0 or equity <= 0:
            return ProposalReasonCode.RISK_CALCULATION_MISMATCH
        expected_risk_pct = (proposal.risk_usd / equity) * 100
        if abs(expected_risk_pct - proposal.risk_percent) > max(0.05, proposal.risk_percent * 0.2):
            return ProposalReasonCode.RISK_CALCULATION_MISMATCH
        return None

    def pre_execution_check(
        self,
        proposal: TradeProposal,
        portfolio: PortfolioState,
        *,
        now: datetime,
    ) -> RiskEvaluation:
        if proposal.expires_at <= now:
            return RiskEvaluation(False, ProposalReasonCode.PROPOSAL_EXPIRED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)
        if proposal.data_freshness_ms < 0:
            return RiskEvaluation(False, ProposalReasonCode.STALE_MARKET_DATA, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct, notes="invalid freshness")
        return self.evaluate(proposal, portfolio)

    def reserve_pending_risk(self, proposal: TradeProposal) -> str:
        reservation_id = new_id("reserve")
        self.pending_risk_book.reserve(proposal.proposal_id, proposal.risk_percent)
        return reservation_id

    def release_pending_risk(self, proposal_id: str) -> None:
        self.pending_risk_book.release(proposal_id)

    @staticmethod
    def _average_entry(proposal: TradeProposal) -> float:
        weighted_sum = sum(leg.planned_entry_price * leg.size_fraction for leg in proposal.entry_split)
        total_fraction = sum(leg.size_fraction for leg in proposal.entry_split)
        return weighted_sum / total_fraction
