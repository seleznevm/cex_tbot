"""cex_tbot package."""

from .api_surface import ApiSurface, CommandRequest, ExecuteRequest, ProposalSubmitRequest, TradeListRequest
from .demo import DemoArtifacts, build_demo_proposal, render_demo, run_demo
from .approval_flow import ApprovalFlow
from .audit import AuditEntry, InMemoryOperatorTranscript
from .backend_service import TradingBackendService
from .bootstrap import TradingApplication, build_app
from .exceptions import GateDemoTransportError, GateLiveModeBlockedError, MissingGateDemoApiError
from .market_data import (
    GateDemoInstrumentClient,
    GateDemoInstrumentFetcher,
    GateInstrumentFetcher,
    GateInstrumentRecord,
    StaticGateInstrumentFetcher,
    UnimplementedGateDemoInstrumentClient,
)
from .config import BotConfig, load_config
from .dashboard_models import DashboardBuilder, DashboardView, KpiWidget, OperatorActivityWidget, RiskWidget
from .handoff import ApprovalExecutionHandoff, ApprovalExecutionResult
from .operator_router import OperatorCommandRouter, RenderedResponse
from .proposal_store import InMemoryProposalStore
from .query_params import TradeQuery
from .read_models import QueryService, TradeDetailView, TradeListItem
from .reporting import TradeReport, TradeReportBuilder
from .serializers import ApiSerializer
from .review_cards import ReviewCard, ReviewCardBuilder
from .risk_engine import PendingRiskBook, PortfolioState, RiskEngine, RiskEvaluation
from .session_store import TradeSessionStore
from .session_summary import SessionSummary, SessionSummaryBuilder
from .storage import FileExecutionJournal, FileExecutionStateStore, FileOperatorTranscript, FileProposalStore, FileTradeSessionStore
from .workflow import TradeWorkflowService, WorkflowResult

__all__ = [
    "ApiSurface",
    "CommandRequest",
    "ExecuteRequest",
    "ProposalSubmitRequest",
    "TradeListRequest",
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
    "TradeWorkflowService",
    "WorkflowResult",
    "FileExecutionJournal",
    "FileExecutionStateStore",
    "FileOperatorTranscript",
    "FileProposalStore",
    "FileTradeSessionStore",
    "PendingRiskBook",
    "PortfolioState",
    "RiskEngine",
    "RiskEvaluation",
]
