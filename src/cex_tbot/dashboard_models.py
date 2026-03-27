from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.config import BotConfig
from cex_tbot.read_models import QueryService, TradeListItem
from cex_tbot.risk_engine import PendingRiskBook
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.session_summary import SessionSummaryBuilder


@dataclass(frozen=True)
class KpiWidget:
    total_proposals: int
    total_no_trade_decisions: int
    executed_proposals: int
    rejected_proposals: int
    operator_commands: int


@dataclass(frozen=True)
class RiskWidget:
    active_trades: int
    avg_confidence_score: float
    approval_decisions: int
    execution_events: int
    emergency_halt_active: bool
    halt_reason: str | None = None
    max_open_risk_percent: float = 0.0
    reserved_pending_risk_percent: float = 0.0
    active_risk_percent: float = 0.0
    free_risk_budget_percent: float = 0.0


@dataclass(frozen=True)
class OperatorActivityWidget:
    command_count: int
    latest_outcomes: list[str]


@dataclass(frozen=True)
class DashboardView:
    kpis: KpiWidget
    risk: RiskWidget
    latest_trades: list[TradeListItem]
    operator_activity: OperatorActivityWidget


class DashboardBuilder:
    def __init__(
        self,
        session: TradeSessionStore,
        query_service: QueryService,
        *,
        config: BotConfig | None = None,
        pending_risk_book: PendingRiskBook | None = None,
    ) -> None:
        self.session = session
        self.query_service = query_service
        self.summary_builder = SessionSummaryBuilder()
        self.config = config or BotConfig()
        self.pending_risk_book = pending_risk_book or PendingRiskBook()

    def build(self, latest_limit: int = 5) -> DashboardView:
        summary = self.summary_builder.build(self.session)
        trades = self.query_service.list_trades()
        latest_trades = sorted(trades, key=lambda item: item.proposal_id, reverse=True)[:latest_limit]
        avg_conf = round(sum(item.confidence_score for item in trades) / len(trades), 4) if trades else 0.0
        operator_entries = self.session.operator_transcript.list_entries()
        active_risk = round(
            sum(
                proposal.risk_percent
                for proposal in self.session.proposals._proposals.values()
                if proposal.status.value in {"EXECUTED", "EXECUTION_READY", "APPROVED_PENDING_EXECUTION_CHECK"}
            ),
            4,
        )
        reserved_risk = round(self.pending_risk_book.total_reserved_risk_pct, 4)
        max_open_risk = round(self.config.max_aggregate_open_risk_percent, 4)
        free_risk = round(max(0.0, max_open_risk - active_risk - reserved_risk), 4)
        return DashboardView(
            kpis=KpiWidget(
                total_proposals=summary.total_proposals,
                total_no_trade_decisions=summary.total_no_trade_decisions,
                executed_proposals=summary.executed_proposals,
                rejected_proposals=summary.rejected_proposals,
                operator_commands=summary.operator_commands,
            ),
            risk=RiskWidget(
                active_trades=sum(1 for item in trades if item.status not in {"EXECUTED", "REJECTED_BY_HUMAN", "REJECTED_PRE_EXECUTION", "SUPERSEDED"}),
                avg_confidence_score=avg_conf,
                approval_decisions=summary.approval_decisions,
                execution_events=summary.execution_events,
                emergency_halt_active=summary.emergency_halt_active,
                halt_reason=summary.halt_reason,
                max_open_risk_percent=max_open_risk,
                reserved_pending_risk_percent=reserved_risk,
                active_risk_percent=active_risk,
                free_risk_budget_percent=free_risk,
            ),
            latest_trades=latest_trades,
            operator_activity=OperatorActivityWidget(
                command_count=len(operator_entries),
                latest_outcomes=[entry.outcome for entry in operator_entries[-5:]],
            ),
        )
