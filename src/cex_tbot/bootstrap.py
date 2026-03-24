from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cex_tbot.api_surface import ApiSurface
from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig, load_config
from cex_tbot.dashboard_models import DashboardBuilder
from cex_tbot.decision_contracts.validator import ProposalValidator
from cex_tbot.execution import ExecutionOrchestrator, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.market_data.gate_client import (
    GateDemoInstrumentClient,
    GateDemoInstrumentFetcher,
    GateInstrumentFetcher,
    StaticGateInstrumentFetcher,
    UnimplementedGateDemoInstrumentClient,
)
from cex_tbot.market_data.provider import StaticMarketDataProvider
from cex_tbot.market_data.service import MarketDataService
from cex_tbot.operator_router import OperatorCommandRouter
from cex_tbot.read_models import QueryService
from cex_tbot.reporting import TradeReportBuilder
from cex_tbot.review_cards import ReviewCardBuilder
from cex_tbot.risk_engine import PendingRiskBook, RiskEngine
from cex_tbot.serializers import ApiSerializer
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.session_summary import SessionSummaryBuilder
from cex_tbot.simulator import SimulatorService
from cex_tbot.storage import FileTradeSessionStore
from cex_tbot.universe import UniverseService
from cex_tbot.universe.orchestrator import UniverseRefreshOrchestrator
from cex_tbot.universe.policy import UniverseRefreshPolicy
from cex_tbot.universe.repository import InMemoryUniverseSnapshotRepository
from cex_tbot.workflow import TradeWorkflowService


@dataclass(frozen=True)
class TradingApplication:
    config: BotConfig
    session: TradeSessionStore
    pending_risk_book: PendingRiskBook
    risk_engine: RiskEngine
    simulator: SimulatorService
    review_cards: ReviewCardBuilder
    report_builder: TradeReportBuilder
    timeline_builder: TradeTimelineBuilder
    approval_flow: ApprovalFlow
    execution: ExecutionOrchestrator
    handoff: ApprovalExecutionHandoff
    workflow: TradeWorkflowService
    router: OperatorCommandRouter
    query_service: QueryService
    serializer: ApiSerializer
    dashboard_builder: DashboardBuilder
    summary_builder: SessionSummaryBuilder
    backend: TradingBackendService
    api: ApiSurface
    market_data_service: MarketDataService
    market_data_provider: StaticMarketDataProvider
    universe_service: UniverseService
    universe_repository: InMemoryUniverseSnapshotRepository
    universe_refresh_policy: UniverseRefreshPolicy
    universe_orchestrator: UniverseRefreshOrchestrator
    proposal_validator: ProposalValidator
    instrument_fetcher: GateInstrumentFetcher


def build_app(
    *,
    config: BotConfig | None = None,
    env: dict[str, str] | None = None,
    session: TradeSessionStore | None = None,
    storage_dir: str | Path | None = None,
    market_data_provider: StaticMarketDataProvider | None = None,
    instrument_fetcher: GateInstrumentFetcher | None = None,
    gate_demo_client: GateDemoInstrumentClient | None = None,
) -> TradingApplication:
    resolved_config = config or load_config(env)
    resolved_session = session or _build_session(storage_dir)
    pending_risk_book = PendingRiskBook()
    risk_engine = RiskEngine(resolved_config, pending_risk_book)
    simulator = SimulatorService()
    review_cards = ReviewCardBuilder()
    report_builder = TradeReportBuilder()
    timeline_builder = TradeTimelineBuilder(resolved_session.execution_journal, resolved_session.execution_state)
    approval_flow = ApprovalFlow(resolved_session.proposals, review_cards)
    execution = ExecutionOrchestrator(
        risk_engine,
        simulator,
        journal=resolved_session.execution_journal,
        state_store=resolved_session.execution_state,
    )
    handoff = ApprovalExecutionHandoff(approval_flow, execution)
    workflow = TradeWorkflowService(approval_flow, handoff, timeline_builder, report_builder, review_cards)
    router = OperatorCommandRouter(workflow, approval_flow, transcript=resolved_session.operator_transcript)
    query_service = QueryService(resolved_session, timeline_builder)
    serializer = ApiSerializer()
    dashboard_builder = DashboardBuilder(resolved_session, query_service)
    summary_builder = SessionSummaryBuilder()
    backend = TradingBackendService(
        session=resolved_session,
        approval_flow=approval_flow,
        execution=execution,
        workflow=workflow,
        router=router,
        report_builder=report_builder,
        review_cards=review_cards,
        summary_builder=summary_builder,
        timeline_builder=timeline_builder,
        query_service=query_service,
        serializer=serializer,
        dashboard_builder=dashboard_builder,
    )
    api = ApiSurface(backend)
    market_data_service = MarketDataService()
    resolved_market_data_provider = market_data_provider or StaticMarketDataProvider(())
    universe_service = UniverseService(resolved_config)
    universe_repository = InMemoryUniverseSnapshotRepository()
    universe_refresh_policy = UniverseRefreshPolicy(resolved_config.universe_refresh_minutes)
    universe_orchestrator = UniverseRefreshOrchestrator(universe_service, universe_repository)
    proposal_validator = ProposalValidator(resolved_config, universe_service)
    resolved_instrument_fetcher = instrument_fetcher or _build_default_instrument_fetcher(
        resolved_config,
        gate_demo_client=gate_demo_client,
    )
    return TradingApplication(
        config=resolved_config,
        session=resolved_session,
        pending_risk_book=pending_risk_book,
        risk_engine=risk_engine,
        simulator=simulator,
        review_cards=review_cards,
        report_builder=report_builder,
        timeline_builder=timeline_builder,
        approval_flow=approval_flow,
        execution=execution,
        handoff=handoff,
        workflow=workflow,
        router=router,
        query_service=query_service,
        serializer=serializer,
        dashboard_builder=dashboard_builder,
        summary_builder=summary_builder,
        backend=backend,
        api=api,
        market_data_service=market_data_service,
        market_data_provider=resolved_market_data_provider,
        universe_service=universe_service,
        universe_repository=universe_repository,
        universe_refresh_policy=universe_refresh_policy,
        universe_orchestrator=universe_orchestrator,
        proposal_validator=proposal_validator,
        instrument_fetcher=resolved_instrument_fetcher,
    )


def _build_session(storage_dir: str | Path | None) -> TradeSessionStore:
    if storage_dir is None:
        return TradeSessionStore()
    return FileTradeSessionStore.open(storage_dir)


def _build_default_instrument_fetcher(
    config: BotConfig,
    *,
    gate_demo_client: GateDemoInstrumentClient | None,
) -> GateInstrumentFetcher:
    if config.execution_mode == "gate_demo":
        client = gate_demo_client or UnimplementedGateDemoInstrumentClient(config.gate_demo_api)
        return GateDemoInstrumentFetcher(client)
    return StaticGateInstrumentFetcher()
