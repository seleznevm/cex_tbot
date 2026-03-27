from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.config import BotConfig
from cex_tbot.read_models import QueryService, TradeListItem
from cex_tbot.risk_engine import PendingRiskBook
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.session_summary import SessionSummaryBuilder
from cex_tbot.universe.repository import InMemoryUniverseSnapshotRepository


@dataclass(frozen=True)
class KpiWidget:
    total_proposals: int
    total_no_trade_decisions: int
    executed_proposals: int
    rejected_proposals: int
    pending_approvals: int
    operator_commands: int
    status_breakdown: dict[str, int]


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
class OperatorActivityItem:
    actor: str
    raw_command: str
    outcome: str
    proposal_id: str | None
    created_at: str


@dataclass(frozen=True)
class OperatorActivityWidget:
    command_count: int
    latest_outcomes: list[str]
    recent_items: list[OperatorActivityItem]


@dataclass(frozen=True)
class AlertItem:
    level: str
    code: str
    message: str


@dataclass(frozen=True)
class AlertsWidget:
    items: list[AlertItem]


@dataclass(frozen=True)
class UniverseWidget:
    snapshot_id: str | None = None
    refresh_reason: str | None = None
    last_refresh_at: str | None = None
    total_instruments: int = 0
    eligible_instruments: int = 0
    ineligible_instruments: int = 0
    stale_instruments: int = 0
    eligible_symbols: list[str] = None


@dataclass(frozen=True)
class DashboardView:
    kpis: KpiWidget
    risk: RiskWidget
    latest_trades: list[TradeListItem]
    operator_activity: OperatorActivityWidget
    alerts: AlertsWidget
    universe: UniverseWidget


class DashboardBuilder:
    def __init__(
        self,
        session: TradeSessionStore,
        query_service: QueryService,
        *,
        config: BotConfig | None = None,
        pending_risk_book: PendingRiskBook | None = None,
        universe_repository: InMemoryUniverseSnapshotRepository | None = None,
    ) -> None:
        self.session = session
        self.query_service = query_service
        self.summary_builder = SessionSummaryBuilder()
        self.config = config or BotConfig()
        self.pending_risk_book = pending_risk_book or PendingRiskBook()
        self.universe_repository = universe_repository or InMemoryUniverseSnapshotRepository()

    def build(self, latest_limit: int = 5) -> DashboardView:
        summary = self.summary_builder.build(self.session)
        trades = self.query_service.list_trades()
        latest_trades = sorted(trades, key=lambda item: item.created_at, reverse=True)[:latest_limit]
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
        alerts: list[AlertItem] = []
        pending_approvals = summary.proposal_status_breakdown.get("PENDING_APPROVAL", 0)
        if summary.emergency_halt_active:
            alerts.append(AlertItem(level="critical", code="HALT_ACTIVE", message=f"Emergency halt active: {summary.halt_reason or 'no reason provided'}"))
        if pending_approvals > 0:
            alerts.append(AlertItem(level="warning", code="PENDING_APPROVALS", message=f"{pending_approvals} proposal(s) waiting for approval"))
        if trades and free_risk <= 0.0:
            alerts.append(AlertItem(level="critical", code="RISK_BUDGET_EXHAUSTED", message="Free risk budget is exhausted"))
        elif trades and free_risk <= min(0.25, max_open_risk * 0.25):
            alerts.append(AlertItem(level="warning", code="LOW_FREE_RISK", message=f"Free risk budget is low: {free_risk}% remaining"))
        if not trades and summary.total_no_trade_decisions == 0:
            alerts.append(AlertItem(level="info", code="EMPTY_STATE", message="No proposals or no-trade decisions recorded yet"))
        latest_universe = self.universe_repository.latest()
        if latest_universe is None:
            universe = UniverseWidget(eligible_symbols=[])
            alerts.append(AlertItem(level="info", code="UNIVERSE_NOT_REFRESHED", message="Universe snapshot has not been refreshed yet"))
        else:
            eligible_count = sum(1 for item in latest_universe.instruments if item.eligibility_status.value == "ELIGIBLE")
            stale_count = sum(1 for item in latest_universe.instruments if item.eligibility_status.value == "STALE")
            ineligible_count = len(latest_universe.instruments) - eligible_count - stale_count
            universe = UniverseWidget(
                snapshot_id=latest_universe.snapshot_id,
                refresh_reason=latest_universe.refresh_reason,
                last_refresh_at=latest_universe.created_at.isoformat(),
                total_instruments=len(latest_universe.instruments),
                eligible_instruments=eligible_count,
                ineligible_instruments=ineligible_count,
                stale_instruments=stale_count,
                eligible_symbols=self.universe_repository.latest_eligible_symbols(),
            )
        return DashboardView(
            kpis=KpiWidget(
                total_proposals=summary.total_proposals,
                total_no_trade_decisions=summary.total_no_trade_decisions,
                executed_proposals=summary.executed_proposals,
                rejected_proposals=summary.rejected_proposals,
                pending_approvals=pending_approvals,
                operator_commands=summary.operator_commands,
                status_breakdown=summary.proposal_status_breakdown,
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
                recent_items=[
                    OperatorActivityItem(
                        actor=entry.actor,
                        raw_command=entry.raw_command,
                        outcome=entry.outcome,
                        proposal_id=entry.proposal_id,
                        created_at=entry.created_at.isoformat(),
                    )
                    for entry in operator_entries[-5:]
                ],
            ),
            alerts=AlertsWidget(items=alerts),
            universe=universe,
        )
