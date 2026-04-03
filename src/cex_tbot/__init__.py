"""cex_tbot package."""

from .api_surface import ApiSurface, CommandRequest, ExecuteRequest, ProposalSubmitRequest, TradeListRequest
from .bot_adapter import BotCommandAdapter, BotReply
from .bot_dispatcher import BotCommandDispatcher, ParsedBotCommand
from .openclaw_wrapper import OpenClawInboundMessage, OpenClawOutboundMessage, OpenClawTopicWrapper
from .transport_bridge import SenderPolicy, TransportCommandBridge, TransportMessage
from .write_safety import WriteActionArmState
from .demo import DemoArtifacts, build_demo_proposal, render_demo, run_demo
from .approval_flow import ApprovalFlow
from .audit import AuditEntry, InMemoryOperatorTranscript
from .backend_service import TradingBackendService
from .bootstrap import TradingApplication, build_app
from .exceptions import GateDemoTransportError, GateLiveModeBlockedError, MissingGateDemoApiError
from .gate_demo_sdk_client import GateDemoSdkClient
from .live_market_flow import LiveMarketFlowDecision, LiveMarketProposalFlow
from .live_market_runner import LiveMarketPipelineRunner, LiveMarketRunResult
from .periodic_runner import PeriodicRunner, PeriodicRunSummary
from .market_data import (
    GateDemoInstrumentClient,
    GateDemoInstrumentFetcher,
    GateInstrumentFetcher,
    GateInstrumentRecord,
    HttpxGateDemoInstrumentClient,
    StaticGateInstrumentFetcher,
    UnimplementedGateDemoInstrumentClient,
)
from .config import BotConfig, load_config
from .dashboard_models import DashboardBuilder, DashboardView, KpiWidget, OperatorActivityWidget, RiskWidget
from .handoff import ApprovalExecutionHandoff, ApprovalExecutionResult
from .operator_router import OperatorCommandRouter, RenderedResponse
from .post_analysis import PostAnalysisBuilder, PostAnalysisSummary
from .proposal_store import InMemoryProposalStore
from .proposal_workflow_glue import ProposalWorkflowGlue
from .proposal_emitter import TopicProposalEmitter
from .query_params import TradeQuery
from .read_models import QueryService, TradeDetailView, TradeListItem
from .reporting import TradeReport, TradeReportBuilder
from .serializers import ApiSerializer
from .review_cards import ReviewCard, ReviewCardBuilder
from .risk_engine import PendingRiskBook, PortfolioState, RiskEngine, RiskEvaluation
from .safety_controls import SafetyController, SafetyEvaluationResult
from .session_store import TradeSessionStore
from .session_summary import SessionSummary, SessionSummaryBuilder
from .system_state import SystemState
from .no_trade_store import InMemoryNoTradeStore
from .storage import FileExecutionJournal, FileExecutionStateStore, FileNoTradeStore, FileOperatorTranscript, FileProposalStore, FileSystemState, FileTradeSessionStore
from .workflow import TradeWorkflowService, WorkflowResult

try:
    from .rest_api import ProposalPayloadMapper, RestApiDependencyError, RestAppBundle, create_rest_app
except ModuleNotFoundError as exc:
    _rest_import_error = exc

    class RestApiDependencyError(RuntimeError):
        """Raised when optional REST dependencies are unavailable."""

    class _MissingRestDependency:
        def __init__(self, name: str) -> None:
            self._name = name

        def __call__(self, *args, **kwargs):
            raise RestApiDependencyError(
                f"{self._name} requires optional REST dependencies ({_rest_import_error.name})."
            ) from _rest_import_error

    def _missing_rest_dependency(*args, **kwargs):
        raise RestApiDependencyError(
            f"REST features require optional REST dependencies ({_rest_import_error.name})."
        ) from _rest_import_error

    ProposalPayloadMapper = _MissingRestDependency("ProposalPayloadMapper")
    RestAppBundle = object
    create_rest_app = _missing_rest_dependency

__all__ = [
    "ApiSurface",
    "CommandRequest",
    "ExecuteRequest",
    "ProposalSubmitRequest",
    "TradeListRequest",
    "BotCommandAdapter",
    "BotReply",
    "BotCommandDispatcher",
    "ParsedBotCommand",
    "OpenClawInboundMessage",
    "OpenClawOutboundMessage",
    "OpenClawTopicWrapper",
    "SenderPolicy",
    "TransportCommandBridge",
    "TransportMessage",
    "WriteActionArmState",
    "DemoArtifacts",
    "build_demo_proposal",
    "render_demo",
    "run_demo",
    "ApprovalFlow",
    "TradingApplication",
    "build_app",
    "BotConfig",
    "GateInstrumentFetcher",
    "GateDemoInstrumentClient",
    "GateDemoInstrumentFetcher",
    "GateDemoSdkClient",
    "HttpxGateDemoInstrumentClient",
    "GateDemoTransportError",
    "GateLiveModeBlockedError",
    "MissingGateDemoApiError",
    "StaticGateInstrumentFetcher",
    "UnimplementedGateDemoInstrumentClient",
    "GateInstrumentRecord",
    "DashboardBuilder",
    "DashboardView",
    "KpiWidget",
    "OperatorActivityWidget",
    "RiskWidget",
    "load_config",
    "TradingBackendService",
    "ApprovalExecutionHandoff",
    "ApprovalExecutionResult",
    "AuditEntry",
    "InMemoryOperatorTranscript",
    "InMemoryProposalStore",
    "OperatorCommandRouter",
    "RenderedResponse",
    "PostAnalysisBuilder",
    "PostAnalysisSummary",
    "TopicProposalEmitter",
    "ProposalWorkflowGlue",
    "LiveMarketFlowDecision",
    "LiveMarketProposalFlow",
    "LiveMarketPipelineRunner",
    "LiveMarketRunResult",
    "PeriodicRunner",
    "PeriodicRunSummary",
    "TradeQuery",
    "QueryService",
    "TradeListItem",
    "TradeDetailView",
    "ApiSerializer",
    "TradeReport",
    "TradeReportBuilder",
    "ReviewCard",
    "ReviewCardBuilder",
    "TradeSessionStore",
    "SessionSummary",
    "SessionSummaryBuilder",
    "SystemState",
    "InMemoryNoTradeStore",
    "TradeWorkflowService",
    "WorkflowResult",
    "FileExecutionJournal",
    "FileExecutionStateStore",
    "FileNoTradeStore",
    "FileOperatorTranscript",
    "FileProposalStore",
    "FileSystemState",
    "FileTradeSessionStore",
    "PendingRiskBook",
    "PortfolioState",
    "RiskEngine",
    "RiskEvaluation",
    "SafetyController",
    "SafetyEvaluationResult",
    "ProposalPayloadMapper",
    "RestApiDependencyError",
    "RestAppBundle",
    "create_rest_app",
]
