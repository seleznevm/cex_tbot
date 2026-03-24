from __future__ import annotations

from dataclasses import dataclass, field

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts.models import TradeProposal
from cex_tbot.enums import ProposalReasonCode
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
        if portfolio.open_positions_count >= self.config.max_open_positions:
            return RiskEvaluation(False, ProposalReasonCode.MAX_OPEN_POSITIONS_REACHED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)
        if portfolio.daily_drawdown_pct >= self.config.max_daily_drawdown_percent:
            return RiskEvaluation(False, ProposalReasonCode.MAX_DAILY_DRAWDOWN_REACHED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)
        total_projected_risk = portfolio.aggregate_open_risk_pct + self.pending_risk_book.total_reserved_risk_pct + proposal.risk_percent
        if total_projected_risk > self.config.max_aggregate_open_risk_percent:
            return RiskEvaluation(False, ProposalReasonCode.TOTAL_OPEN_RISK_EXCEEDED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct, notes=f"projected_risk={total_projected_risk}")
        return RiskEvaluation(True, ProposalReasonCode.RISK_BUDGET_RESERVED, portfolio.aggregate_open_risk_pct, self.pending_risk_book.total_reserved_risk_pct)

    def reserve_pending_risk(self, proposal: TradeProposal) -> str:
        reservation_id = new_id("reserve")
        self.pending_risk_book.reserve(proposal.proposal_id, proposal.risk_percent)
        return reservation_id

    def release_pending_risk(self, proposal_id: str) -> None:
        self.pending_risk_book.release(proposal_id)
