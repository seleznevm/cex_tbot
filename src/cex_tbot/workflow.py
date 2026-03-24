from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.execution import TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff, ApprovalExecutionResult
from cex_tbot.reporting import TradeReport, TradeReportBuilder
from cex_tbot.review_cards import ReviewCardBuilder
from cex_tbot.risk_engine import PortfolioState
from cex_tbot.shared import utc_now


@dataclass(frozen=True)
class WorkflowResult:
    approval_execution: ApprovalExecutionResult
    report: TradeReport | None = None


class TradeWorkflowService:
    def __init__(
        self,
        approval_flow: ApprovalFlow,
        handoff: ApprovalExecutionHandoff,
        timeline_builder: TradeTimelineBuilder,
        report_builder: TradeReportBuilder | None = None,
        review_cards: ReviewCardBuilder | None = None,
    ) -> None:
        self.approval_flow = approval_flow
        self.handoff = handoff
        self.timeline_builder = timeline_builder
        self.report_builder = report_builder or TradeReportBuilder()
        self.review_cards = review_cards or ReviewCardBuilder()

    def approve_execute_and_report(
        self,
        actor: str,
        raw_text: str,
        portfolio: PortfolioState,
        *,
        now: datetime | None = None,
    ) -> WorkflowResult:
        effective_now = now or utc_now()
        result = self.handoff.approve_and_execute(actor, raw_text, portfolio, now=effective_now)
        proposal_id = result.approval.proposal_id
        if result.execution is None:
            return WorkflowResult(approval_execution=result, report=None)
        proposal = self.approval_flow.store.require(proposal_id)
        review_card = self.review_cards.build(proposal)
        timeline = self.timeline_builder.build(proposal_id)
        report = self.report_builder.build(review_card, timeline, result.execution.position)
        return WorkflowResult(approval_execution=result, report=report)
