from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow
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
    def __init__(self, workflow: TradeWorkflowService, approval_flow: ApprovalFlow) -> None:
        self.workflow = workflow
        self.approval_flow = approval_flow

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
            return RenderedResponse(render_mode, f"Invalid command: {parsed.reason}")

        if parsed.command.action == ApprovalAction.APPROVE:
            result = (
                self.workflow.approve_execute_and_report(actor, raw_text, portfolio, now=effective_now)
                if execute_on_approve
                else self.workflow.approve_only(actor, raw_text)
            )
            return RenderedResponse(render_mode, self.render(result, render_mode))

        if parsed.command.action == ApprovalAction.REJECT:
            result = self.workflow.reject_and_report(actor, raw_text)
            return RenderedResponse(render_mode, self.render(result, render_mode))

        if parsed.command.action == ApprovalAction.MODIFY:
            if replacement is None:
                return RenderedResponse(render_mode, "MODIFY requires replacement proposal")
            result = self.workflow.modify_revalidate_and_report(actor, raw_text, replacement)
            return RenderedResponse(render_mode, self.render(result, render_mode))

        return RenderedResponse(render_mode, "Unsupported command")

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
