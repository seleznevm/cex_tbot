from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow, ApprovalApplyResult
from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.enums import ProposalStatus
from cex_tbot.execution import TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff, ApprovalExecutionResult
from cex_tbot.reporting import TradeReport, TradeReportBuilder
from cex_tbot.review_cards import ReviewCardBuilder
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.shared import utc_now


@dataclass(frozen=True)
class WorkflowResult:
    approval_execution: ApprovalExecutionResult | None = None
    approval_only: ApprovalApplyResult | None = None
    report: TradeReport | None = None


class TradeWorkflowService:
    def __init__(
        self,
        approval_flow: ApprovalFlow,
        handoff: ApprovalExecutionHandoff,
        timeline_builder: TradeTimelineBuilder,
        report_builder: TradeReportBuilder | None = None,
        review_cards: ReviewCardBuilder | None = None,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self.approval_flow = approval_flow
        self.handoff = handoff
        self.timeline_builder = timeline_builder
        self.report_builder = report_builder or TradeReportBuilder()
        self.review_cards = review_cards or ReviewCardBuilder()
        self.risk_engine = risk_engine

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
        proposal = self.approval_flow.store.require(proposal_id)
        if result.execution is None:
            review_card = self.review_cards.build(proposal)
            timeline = self.timeline_builder.build(proposal_id)
            report = self.report_builder.build(review_card, timeline, None)
            return WorkflowResult(approval_execution=result, report=report)
        review_card = self.review_cards.build(proposal)
        timeline = self.timeline_builder.build(proposal_id)
        report = self.report_builder.build(review_card, timeline, result.execution.position)
        return WorkflowResult(approval_execution=result, report=report)

    def approve_only(self, actor: str, raw_text: str) -> WorkflowResult:
        result = self.approval_flow.apply_command(actor, raw_text)
        report = None
        if result.proposal_id != "UNKNOWN" and result.resulting_status is not None:
            proposal = self.approval_flow.store.require(result.proposal_id)
            report = self.report_builder.build(
                self.review_cards.build(proposal),
                self.timeline_builder.build(result.proposal_id),
                None,
            )
        return WorkflowResult(approval_only=result, report=report)

    def reject_and_report(self, actor: str, raw_text: str) -> WorkflowResult:
        return self.approve_only(actor, raw_text)

    def modify_revalidate_and_report(
        self,
        actor: str,
        raw_text: str,
        replacement: TradeProposal,
        portfolio: PortfolioState | None = None,
    ) -> WorkflowResult:
        risk_evaluation = (
            self.risk_engine.evaluate(replacement, portfolio)
            if self.risk_engine is not None and portfolio is not None
            else None
        )
        replacement_status = replacement.status
        if risk_evaluation is not None:
            replacement_status = ProposalStatus.PENDING_APPROVAL if risk_evaluation.is_approved else ProposalStatus.REJECTED_BY_RISK
        result = self.approval_flow.revalidate_modified_proposal(
            actor,
            raw_text,
            replace(replacement, status=replacement_status),
            risk_evaluation=risk_evaluation,
        )
        if (
            self.risk_engine is not None
            and risk_evaluation is not None
            and risk_evaluation.is_approved
            and result.superseded_proposal_id is not None
        ):
            self.risk_engine.release_pending_risk(result.superseded_proposal_id)
            self.risk_engine.reserve_pending_risk(self.approval_flow.store.require(result.proposal_id))
        report = result.review_card and self.report_builder.build(
            result.review_card,
            self.timeline_builder.build(result.proposal_id),
            None,
        )
        return WorkflowResult(approval_only=result, report=report)
