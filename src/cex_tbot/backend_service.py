from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.audit import AuditEntry
from cex_tbot.config import BotConfig
from cex_tbot.dashboard_models import DashboardBuilder, DashboardView
from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.execution import ExecutionOrchestrator, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.operator_router import OperatorCommandRouter, RenderedResponse
from cex_tbot.query_params import TradeQuery
from cex_tbot.enums import ProposalStatus, SafetyState
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
    dashboard_builder: DashboardBuilder

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
            dashboard_builder=DashboardBuilder(
                session,
                QueryService(session, timeline_builder),
                config=(risk_engine.config if risk_engine is not None else BotConfig()),
                pending_risk_book=((risk_engine.pending_risk_book) if risk_engine is not None else None),
            ),
        )

    def submit_proposal(self, proposal: TradeProposal) -> TradeProposal:
        return self.session.proposals.upsert(proposal)

    def submit_no_trade_decision(self, decision: NoTradeDecision) -> NoTradeDecision:
        return self.session.no_trades.add(decision)

    def activate_emergency_halt(self, reason: str) -> None:
        self.session.system_state.activate_halt(reason)
        self.session.operator_transcript.append(
            AuditEntry(actor="system", raw_command=f"HALT {reason}", outcome="HALT_ON")
        )

    def clear_emergency_halt(self) -> None:
        previous_reason = self.session.system_state.halt_reason or "manual clear"
        self.session.system_state.clear_halt()
        self.session.operator_transcript.append(
            AuditEntry(actor="system", raw_command=f"UNHALT {previous_reason}", outcome="HALT_OFF")
        )

    def evaluate_stop_conditions(self, portfolio: PortfolioState) -> None:
        if self.session.system_state.emergency_halt_active:
            return
        if portfolio.daily_drawdown_pct >= self.execution.risk_engine.config.max_daily_drawdown_percent:
            self.session.system_state.set_block(
                f"daily drawdown limit reached: {portfolio.daily_drawdown_pct:.2f}%",
                safety_state=SafetyState.BLOCK_NEW_TRADES,
            )
            return
        if portfolio.open_positions_count >= self.execution.risk_engine.config.max_open_positions:
            self.session.system_state.set_block(
                f"max open positions reached: {portfolio.open_positions_count}",
                safety_state=SafetyState.BLOCK_NEW_TRADES,
            )
            return
        projected_reserved = self.execution.risk_engine.pending_risk_book.total_reserved_risk_pct + portfolio.aggregate_open_risk_pct
        if projected_reserved >= self.execution.risk_engine.config.max_aggregate_open_risk_percent:
            self.session.system_state.set_block(
                f"aggregate open risk exhausted: {projected_reserved:.2f}%",
                safety_state=SafetyState.BLOCK_NEW_TRADES,
            )
            return
        self.session.system_state.clear_block()

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
        self.evaluate_stop_conditions(portfolio)
        if self.session.system_state.emergency_halt_active:
            return RenderedResponse(
                render_mode,
                f"Emergency halt active: {self.session.system_state.halt_reason or 'no reason provided'}",
            )
        if self.session.system_state.block_new_trades:
            return RenderedResponse(
                render_mode,
                f"New trades blocked: {self.session.system_state.block_reason or 'safety policy active'}",
            )
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

    def execute_approved_proposal(
        self,
        proposal_id: str,
        portfolio: PortfolioState,
        *,
        actor: str = "operator",
        render_mode: str = "plain",
        now: datetime | None = None,
    ) -> RenderedResponse:
        if self.session.system_state.emergency_halt_active:
            return RenderedResponse(
                render_mode,
                f"Emergency halt active: {self.session.system_state.halt_reason or 'no reason provided'}",
            )
        proposal = self.session.proposals.require(proposal_id)
        if proposal.status != ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK:
            return RenderedResponse(
                render_mode,
                f"Proposal {proposal_id} is not ready for execution: status={proposal.status.value}",
            )
        result = self.execution.execute(proposal, portfolio, now=now or utc_now())
        if result.status == ProposalStatus.EXECUTED:
            self.session.proposals.update_status(proposal_id, ProposalStatus.EXECUTED)
        elif result.status == ProposalStatus.REJECTED_PRE_EXECUTION:
            self.session.proposals.update_status(proposal_id, ProposalStatus.REJECTED_PRE_EXECUTION)
        updated = self.session.proposals.require(proposal_id)
        report = self.report_builder.build(
            self.review_cards.build(updated),
            self.timeline_builder.build(proposal_id),
            result.position,
        )
        self.session.operator_transcript.append(
            AuditEntry(
                actor=actor,
                raw_command=f"EXECUTE {proposal_id}",
                outcome="EXECUTE",
                proposal_id=proposal_id,
            )
        )
        rendered_text = self.router.render_report(report, render_mode)
        return RenderedResponse(render_mode, rendered_text)

    def execute_approved_proposal_payload(
        self,
        proposal_id: str,
        portfolio: PortfolioState,
        *,
        actor: str = "operator",
        render_mode: str = "plain",
        now: datetime | None = None,
    ) -> dict[str, object]:
        return self.serializer.rendered_response(
            self.execute_approved_proposal(
                proposal_id,
                portfolio,
                actor=actor,
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
            position = None
        return self.report_builder.build(review_card, timeline, position)

    def get_trade_report_text(self, proposal_id: str, *, render_mode: str = "plain") -> str:
        return self.router.render_report(self.get_trade_report(proposal_id), render_mode)

    def get_session_summary(self) -> SessionSummary:
        return self.summary_builder.build(self.session)

    def list_trades(self, query: TradeQuery | None = None) -> list[TradeListItem]:
        return self.query_service.list_trades(query)

    def get_trade_detail(self, proposal_id: str) -> TradeDetailView:
        return self.query_service.get_trade_detail(proposal_id)

    def list_no_trades_payload(self) -> list[dict[str, object]]:
        return [self.serializer.no_trade_decision(item) for item in self.session.no_trades.list()]

    def list_trades_payload(self, query: TradeQuery | None = None) -> list[dict[str, object]]:
        return [self.serializer.trade_list_item(item) for item in self.list_trades(query)]

    def list_trades_page_payload(self, query: TradeQuery | None = None) -> dict[str, object]:
        query = query or TradeQuery()
        items = self.list_trades_payload(query)
        total = self.query_service.count_trades(query)
        limit = query.limit if query.limit is not None else total
        offset = max(query.offset, 0)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_trade_detail_payload(self, proposal_id: str) -> dict[str, object]:
        return self.serializer.trade_detail(self.get_trade_detail(proposal_id))

    def get_trade_report_payload(self, proposal_id: str) -> dict[str, object]:
        return self.serializer.trade_report(self.get_trade_report(proposal_id))

    def get_session_summary_payload(self) -> dict[str, object]:
        return self.serializer.session_summary(self.get_session_summary())

    def get_dashboard_view(self) -> DashboardView:
        return self.dashboard_builder.build()

    def get_dashboard_payload(self) -> dict[str, object]:
        dashboard = self.get_dashboard_view()
        return {
            "kpis": dashboard.kpis.__dict__.copy(),
            "risk": dashboard.risk.__dict__.copy(),
            "latest_trades": [self.serializer.trade_list_item(item) for item in dashboard.latest_trades],
            "operator_activity": {
                "command_count": dashboard.operator_activity.command_count,
                "latest_outcomes": list(dashboard.operator_activity.latest_outcomes),
                "recent_items": [item.__dict__.copy() for item in dashboard.operator_activity.recent_items],
            },
            "alerts": {"items": [item.__dict__.copy() for item in dashboard.alerts.items]},
            "universe": dashboard.universe.__dict__.copy(),
        }
