from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.enums import ProposalStatus
from cex_tbot.execution.journal import ExecutionEvent, InMemoryExecutionJournal
from cex_tbot.execution.state_store import InMemoryExecutionStateStore
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.shared import utc_now
from cex_tbot.simulator import Position, SimulatorService
from cex_tbot.execution.gate_demo_executor import GateDemoExecutionAdapter


@dataclass(frozen=True)
class ExecutionResult:
    proposal_id: str
    status: ProposalStatus
    position: Position | None = None
    reason: str = ""


class ExecutionOrchestrator:
    def __init__(
        self,
        risk_engine: RiskEngine,
        simulator: SimulatorService,
        journal: InMemoryExecutionJournal | None = None,
        state_store: InMemoryExecutionStateStore | None = None,
        gate_demo_executor: GateDemoExecutionAdapter | None = None,
    ) -> None:
        self.risk_engine = risk_engine
        self.simulator = simulator
        self.journal = journal or InMemoryExecutionJournal()
        self.state_store = state_store or InMemoryExecutionStateStore()
        self.gate_demo_executor = gate_demo_executor

    def execute(self, proposal: TradeProposal, portfolio: PortfolioState, *, now: datetime | None = None) -> ExecutionResult:
        if self.gate_demo_executor is not None:
            return self.gate_demo_executor.execute(proposal, portfolio, now=now)

        effective_now = now or utc_now()
        self.journal.append(ExecutionEvent(proposal.proposal_id, "PRE_EXECUTION_CHECK", "starting pre-execution check"))
        check = self.risk_engine.pre_execution_check(proposal, portfolio, now=effective_now)
        if not check.is_approved:
            self.journal.append(
                ExecutionEvent(
                    proposal.proposal_id,
                    "PRE_EXECUTION_REJECTED",
                    check.reason_code.value,
                    payload={"reason": check.reason_code.value},
                )
            )
            return ExecutionResult(proposal.proposal_id, ProposalStatus.REJECTED_PRE_EXECUTION, reason=check.reason_code.value)
        position = self.simulator.open_position(proposal)
        self.state_store.append_snapshot(position)
        self.journal.append(ExecutionEvent(proposal.proposal_id, "POSITION_OPENED", "position opened", position_id=position.position_id))
        for leg in proposal.entry_split:
            fill = self.simulator.build_fill(proposal, leg.leg_number, leg.planned_entry_price, proposal.position_size * leg.size_fraction)
            position = self.simulator.execute_fill(position, fill)
            self.state_store.append_snapshot(position)
            self.journal.append(
                ExecutionEvent(
                    proposal.proposal_id,
                    "FILL_APPLIED",
                    f"leg {leg.leg_number} filled",
                    position_id=position.position_id,
                    payload={"leg_number": leg.leg_number, "price": fill.price, "size": fill.size},
                )
            )
        return ExecutionResult(proposal.proposal_id, ProposalStatus.EXECUTED, position=position)

    def process_market_tick(self, proposal_id: str, position: Position, snapshot) -> Position:
        updated = self.simulator.process_protective_levels(position, snapshot)
        if updated.status != position.status or updated.remaining_size != position.remaining_size:
            self.state_store.append_snapshot(updated)
            kind = "POSITION_UPDATED"
            message = f"status={updated.status} remaining={updated.remaining_size}"
            if updated.status == "STOPPED":
                kind = "STOP_TRIGGERED"
                message = "stop loss triggered"
            elif updated.status == "PARTIALLY_CLOSED":
                kind = "TP1_PARTIAL_CLOSE"
                message = "tp1 partial close"
            elif updated.status == "CLOSED":
                kind = "TP2_FULL_CLOSE"
                message = "tp2 full close"
            self.journal.append(
                ExecutionEvent(
                    proposal_id,
                    kind,
                    message,
                    position_id=updated.position_id,
                    payload={"status": updated.status, "remaining_size": updated.remaining_size, "realized_pnl": updated.realized_pnl},
                )
            )
        return updated
