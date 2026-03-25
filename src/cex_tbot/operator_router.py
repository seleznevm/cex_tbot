from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.audit import AuditEntry, InMemoryOperatorTranscript
from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.enums import ApprovalAction
from cex_tbot.reporting import TradeReport
from cex_tbot.risk_engine import PortfolioState
from cex_tbot.shared import utc_now
from cex_tbot.workflow import TradeWorkflowService, WorkflowResult


@dataclass(frozen=True)
class RenderedResponse:
    mode: str
    text: str


class OperatorCommandRouter:
    def __init__(self, workflow: TradeWorkflowService, approval_flow: ApprovalFlow, transcript: InMemoryOperatorTranscript | None = None) -> None:
        self.workflow = workflow
        self.approval_flow = approval_flow
        self.transcript = transcript or InMemoryOperatorTranscript()

    def route(
        self,
        actor: str,
        raw_text: str,
        portfolio: PortfolioState,
        *,
        replacement: TradeProposal | None = None,
        execute_on_approve: bool = True,
        render_mode: str = "plain",
        now: datetime | None = None,
    ) -> RenderedResponse:
        effective_now = now or utc_now()
        parsed = self.approval_flow.parse_command(raw_text)
        if not parsed.is_valid or parsed.command is None:
            rendered = RenderedResponse(render_mode, f"Invalid command: {parsed.reason}")
            self.transcript.append(AuditEntry(actor=actor, raw_command=raw_text, outcome="INVALID_COMMAND"))
            return rendered

        if parsed.command.action == ApprovalAction.APPROVE:
            result = (
                self.workflow.approve_execute_and_report(actor, raw_text, portfolio, now=effective_now)
                if execute_on_approve
                else self.workflow.approve_only(actor, raw_text)
            )
            rendered = RenderedResponse(render_mode, self.render(result, render_mode))
            self.transcript.append(AuditEntry(actor=actor, raw_command=raw_text, outcome="APPROVE", proposal_id=parsed.command.proposal_id))
            return rendered

        if parsed.command.action == ApprovalAction.REJECT:
            result = self.workflow.reject_and_report(actor, raw_text)
            rendered = RenderedResponse(render_mode, self.render(result, render_mode))
            self.transcript.append(AuditEntry(actor=actor, raw_command=raw_text, outcome="REJECT", proposal_id=parsed.command.proposal_id))
            return rendered

        if parsed.command.action == ApprovalAction.MODIFY:
            if replacement is None:
                rendered = RenderedResponse(render_mode, "MODIFY requires replacement proposal")
                self.transcript.append(AuditEntry(actor=actor, raw_command=raw_text, outcome="MODIFY_MISSING_REPLACEMENT", proposal_id=parsed.command.proposal_id))
                return rendered
            result = self.workflow.modify_revalidate_and_report(actor, raw_text, replacement)
            rendered = RenderedResponse(render_mode, self.render(result, render_mode))
            self.transcript.append(AuditEntry(actor=actor, raw_command=raw_text, outcome="MODIFY", proposal_id=parsed.command.proposal_id))
            return rendered

        rendered = RenderedResponse(render_mode, "Unsupported command")
        self.transcript.append(AuditEntry(actor=actor, raw_command=raw_text, outcome="UNSUPPORTED", proposal_id=parsed.command.proposal_id))
        return rendered

    def render(self, result: WorkflowResult, mode: str) -> str:
        if result.report is None:
            return "Command processed, but no report available."
        return self.render_report(result.report, mode)

    @staticmethod
    def render_report(report: TradeReport, mode: str) -> str:
        if mode == "telegram":
            return report.to_telegram_text()
        if mode == "operator":
            return report.to_operator_text()
        if mode == "compact":
            return report.to_compact_text()
        return report.to_text()

    @classmethod
    def render_trade_report(cls, report: TradeReport, mode: str = "plain") -> str:
        return cls.render_report(report, mode)
