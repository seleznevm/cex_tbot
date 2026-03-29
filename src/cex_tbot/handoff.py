from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow, ApprovalApplyResult
from cex_tbot.enums import ProposalStatus
from cex_tbot.execution import ExecutionOrchestrator, ExecutionResult
from cex_tbot.risk_engine import PortfolioState
from cex_tbot.shared import utc_now


@dataclass(frozen=True)
class ApprovalExecutionResult:
    approval: ApprovalApplyResult
    execution: ExecutionResult | None = None


class ApprovalExecutionHandoff:
    def __init__(self, approval_flow: ApprovalFlow, execution: ExecutionOrchestrator) -> None:
        self.approval_flow = approval_flow
        self.execution = execution

    def approve_and_execute(
        self,
        actor: str,
        raw_text: str,
        portfolio: PortfolioState,
        *,
        now: datetime | None = None,
    ) -> ApprovalExecutionResult:
        effective_now = now or utc_now()
        existing = None
        parsed = self.approval_flow.parse_command(raw_text)
        if parsed.is_valid and parsed.command is not None:
            existing = self.approval_flow.store.get(parsed.command.proposal_id)
            if existing is not None and existing.status == ProposalStatus.EXECUTED:
                approval = self.approval_flow.record_decision(actor, raw_text)
                self.approval_flow.store.append_decision(approval)
                return ApprovalExecutionResult(approval=ApprovalApplyResult(decision=approval, resulting_status=ProposalStatus.EXECUTED, proposal_id=existing.proposal_id), execution=None)
        approval = self.approval_flow.apply_command(actor, raw_text)
        if approval.resulting_status != ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK:
            return ApprovalExecutionResult(approval=approval, execution=None)
        proposal = self.approval_flow.store.require(approval.proposal_id)
        execution = self.execution.execute(proposal, portfolio, now=effective_now)
        if execution.status == ProposalStatus.EXECUTED:
            self.approval_flow.store.update_status(proposal.proposal_id, ProposalStatus.EXECUTED)
        elif execution.status == ProposalStatus.REJECTED_PRE_EXECUTION:
            self.approval_flow.store.update_status(proposal.proposal_id, ProposalStatus.REJECTED_PRE_EXECUTION)
        return ApprovalExecutionResult(approval=approval, execution=execution)
