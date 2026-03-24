from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.execution import ExecutionOrchestrator, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.operator_router import OperatorCommandRouter, RenderedResponse
from cex_tbot.read_models import QueryService, TradeDetailView, TradeListItem
from cex_tbot.reporting import TradeReport, TradeReportBuilder
from cex_tbot.review_cards import ReviewCardBuilder
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.serializers import ApiSerializer
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.session_summary import SessionSummary, SessionSummaryBuilder
from cex_tbot.shared import utc_now
from cex_tbot.simulator import SimulatorService
from cex_tbot.workflow import TradeWorkflowService


@dataclass
class TradingBackendService:
    session: TradeSessionStore
    approval_flow: ApprovalFlow
    execution: ExecutionOrchestrator
    workflow: TradeWorkflowService
    router: OperatorCommandRouter
    report_builder: TradeReportBuilder
    review_cards: ReviewCardBuilder
    summary_builder: SessionSummaryBuilder
    timeline_builder: TradeTimelineBuilder
    query_service: QueryService
    serializer: ApiSerializer

    @classmethod
    def from_session(
        cls,
        session: TradeSessionStore,
        *,
        risk_engine: RiskEngine | None = None,
        simulator: SimulatorService | None = None,
    ) -> "TradingBackendService":
        review_cards = ReviewCardBuilder()
        report_builder = TradeReportBuilder()
        timeline_builder = TradeTimelineBuilder(session.execution_journal, session.execution_state)
        approval_flow = ApprovalFlow(session.proposals, review_cards)
        execution = ExecutionOrchestrator(
            risk_engine or RiskEngine(BotConfig()),
            simulator or SimulatorService(),
            journal=session.execution_journal,
            state_store=session.execution_state,
        )
        workflow = TradeWorkflowService(approval_flow, ApprovalExecutionHandoff(approval_flow, execution), timeline_builder, report_builder, review_cards)
        router = OperatorCommandRouter(workflow, approval_flow, transcript=session.operator_transcript)
        return cls(
            session=session,
            approval_flow=approval_flow,
            execution=execution,
            workflow=workflow,
            router=router,
            report_builder=report_builder,
            review_cards=review_cards,
            summary_builder=SessionSummaryBuilder(),
            timeline_builder=timeline_builder,
            query_service=QueryService(session, timeline_builder),
            serializer=ApiSerializer(),
        )

    def submit_proposal(self, proposal: TradeProposal) -> TradeProposal:
        return self.session.proposals.upsert(proposal)

    def run_operator_command(
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
        return self.router.route(
            actor,
            raw_text,
            portfolio,
            replacement=replacement,
            execute_on_approve=execute_on_approve,
            render_mode=render_mode,
            now=now or utc_now(),
        )

    def run_operator_command_payload(
        self,
        actor: str,
        raw_text: str,
        portfolio: PortfolioState,
        *,
        replacement: TradeProposal | None = None,
        execute_on_approve: bool = True,
        render_mode: str = "plain",
        now: datetime | None = None,
    ) -> dict[str, object]:
        return self.serializer.rendered_response(
            self.run_operator_command(
                actor,
                raw_text,
                portfolio,
                replacement=replacement,
                execute_on_approve=execute_on_approve,
                render_mode=render_mode,
                now=now,
            )
        )

    def get_trade_report(self, proposal_id: str) -> TradeReport:
        proposal = self.session.proposals.require(proposal_id)
        review_card = self.review_cards.build(proposal)
        timeline = self.timeline_builder.build(proposal_id)
        snapshots = self.session.execution_state.list_snapshots(proposal_id)
        position = None
        if snapshots:
            # report builder only needs optional position-like info; no reconstruction yet
            position = None
        return self.report_builder.build(review_card, timeline, position)

    def get_session_summary(self) -> SessionSummary:
        return self.summary_builder.build(self.session)

    def list_trades(self) -> list[TradeListItem]:
        return self.query_service.list_trades()

    def get_trade_detail(self, proposal_id: str) -> TradeDetailView:
        return self.query_service.get_trade_detail(proposal_id)

    def list_trades_payload(self) -> list[dict[str, object]]:
        return [self.serializer.trade_list_item(item) for item in self.list_trades()]

    def get_trade_detail_payload(self, proposal_id: str) -> dict[str, object]:
        return self.serializer.trade_detail(self.get_trade_detail(proposal_id))

    def get_trade_report_payload(self, proposal_id: str) -> dict[str, object]:
        return self.serializer.trade_report(self.get_trade_report(proposal_id))

    def get_session_summary_payload(self) -> dict[str, object]:
        return self.serializer.session_summary(self.get_session_summary())
