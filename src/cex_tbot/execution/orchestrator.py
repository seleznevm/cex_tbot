from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.enums import ProposalStatus
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.shared import utc_now
from cex_tbot.simulator import FillEvent, Position, SimulatorService


@dataclass(frozen=True)
class ExecutionResult:
    proposal_id: str
    status: ProposalStatus
    position: Position | None = None
    reason: str = ""


class ExecutionOrchestrator:
    def __init__(self, risk_engine: RiskEngine, simulator: SimulatorService) -> None:
        self.risk_engine = risk_engine
        self.simulator = simulator

    def execute(self, proposal: TradeProposal, portfolio: PortfolioState, *, now: datetime | None = None) -> ExecutionResult:
        effective_now = now or utc_now()
        check = self.risk_engine.pre_execution_check(proposal, portfolio, now=effective_now)
        if not check.is_approved:
            return ExecutionResult(proposal.proposal_id, ProposalStatus.REJECTED_PRE_EXECUTION, reason=check.reason_code.value)
        position = self.simulator.open_position(proposal)
        for leg in proposal.entry_split:
            fill = FillEvent(proposal.proposal_id, leg.leg_number, leg.planned_entry_price, proposal.position_size * leg.size_fraction)
            position = self.simulator.execute_fill(position, fill)
        return ExecutionResult(proposal.proposal_id, ProposalStatus.EXECUTED, position=position)
