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
        if mode == "telegram":
            return self._render_telegram(result.report)
        return result.report.to_text()

    @staticmethod
    def _render_telegram(report: TradeReport) -> str:
        return "\n".join(
            [
                f"**{report.headline}**",
                *report.summary_lines,
                *report.timeline_lines,
            ]
        )
