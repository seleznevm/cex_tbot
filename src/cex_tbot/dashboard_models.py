from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.read_models import QueryService, TradeListItem
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.session_summary import SessionSummaryBuilder


@dataclass(frozen=True)
class KpiWidget:
    total_proposals: int
    executed_proposals: int
    rejected_proposals: int
    operator_commands: int


@dataclass(frozen=True)
class RiskWidget:
    active_trades: int
    avg_confidence_score: float
    approval_decisions: int
    execution_events: int


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
    def __init__(self, session: TradeSessionStore, query_service: QueryService) -> None:
        self.session = session
        self.query_service = query_service
        self.summary_builder = SessionSummaryBuilder()

    def build(self, latest_limit: int = 5) -> DashboardView:
        summary = self.summary_builder.build(self.session)
        trades = self.query_service.list_trades()
        latest_trades = sorted(trades, key=lambda item: item.proposal_id, reverse=True)[:latest_limit]
        avg_conf = round(sum(item.confidence_score for item in trades) / len(trades), 4) if trades else 0.0
        operator_entries = self.session.operator_transcript.list_entries()
        return DashboardView(
            kpis=KpiWidget(
                total_proposals=summary.total_proposals,
                executed_proposals=summary.executed_proposals,
                rejected_proposals=summary.rejected_proposals,
                operator_commands=summary.operator_commands,
            ),
            risk=RiskWidget(
                active_trades=sum(1 for item in trades if item.status not in {"EXECUTED", "REJECTED_BY_HUMAN", "REJECTED_PRE_EXECUTION", "SUPERSEDED"}),
                avg_confidence_score=avg_conf,
                approval_decisions=summary.approval_decisions,
                execution_events=summary.execution_events,
            ),
            latest_trades=latest_trades,
            operator_activity=OperatorActivityWidget(
                command_count=len(operator_entries),
                latest_outcomes=[entry.outcome for entry in operator_entries[-5:]],
            ),
        )
