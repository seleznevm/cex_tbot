from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyHeaderAuthError(BaseModel):
    code: str = "UNAUTHORIZED"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ApiKeyHeaderAuthError


class EntrySplitLegPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leg_number: int
    planned_entry_price: float
    allocation_pct: float
    size_fraction: float
    valid_until: datetime


class ProposalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str | None = None
    proposal_version: int | None = None
    agent_name: str
    strategy_id: str
    strategy_version: str
    market_context_id: str
    symbol: str
    timeframe: str
    direction: Literal["LONG", "SHORT"]
    entry_zone_min: float
    entry_zone_max: float
    entry_split: list[EntrySplitLegPayload]
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_percent: float
    risk_usd: float
    position_size: float
    confidence_score: float
    thesis: str
    invalidity_condition: str
    liquidity_check: str
    data_freshness_ms: int
    created_at: datetime | None = None
    expires_at: datetime | None = None
    exchange: str = "gate"
    market_type: str = "usdt_perpetual"
    contract_type: str = "perpetual"
    status: str = "GENERATED"


class PortfolioContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = "Mike"
    portfolio_equity: float = 10_000.0
    aggregate_open_risk_pct: float = 0.0
    daily_drawdown_pct: float = 0.0
    open_positions_count: int = 0
    render_mode: str = "plain"
    now: datetime | None = None
    execute_on_approve: bool = True


class CommandPayload(PortfolioContextPayload):
    command: str
    execute_on_approve: bool = True


class ModifyProposalPayload(PortfolioContextPayload):
    changes: str
    replacement: ProposalPayload


class ProposalStoredResponse(BaseModel):
    proposal_id: str
    status: str


class RenderedResponsePayload(BaseModel):
    mode: str
    text: str


class TradeTimelinePayload(BaseModel):
    proposal_id: str
    event_count: int
    snapshot_count: int
    events: list[dict[str, Any]]
    snapshots: list[dict[str, Any]]


class TradeListItemPayload(BaseModel):
    proposal_id: str
    symbol: str
    direction: str
    timeframe: str
    status: str
    confidence_score: float
    event_count: int
    snapshot_count: int


class TradeDetailPayload(BaseModel):
    proposal_id: str
    proposal_version: int
    status: str
    agent_name: str
    strategy_id: str
    strategy_version: str
    market_context_id: str
    symbol: str
    timeframe: str
    direction: str
    entry_zone_min: float
    entry_zone_max: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_percent: float
    risk_usd: float
    position_size: float
    confidence_score: float
    thesis: str
    invalidity_condition: str
    liquidity_check: str
    data_freshness_ms: int
    created_at: datetime
    expires_at: datetime
    exchange: str | None = None
    market_type: str | None = None
    contract_type: str | None = None
    approval_decision_count: int
    operator_command_count: int
    timeline: TradeTimelinePayload


class TradeReportPayload(BaseModel):
    proposal_id: str
    headline: str
    summary_lines: list[str]
    timeline_lines: list[str]
    text: str
    operator_text: str
    telegram_text: str
    compact_text: str


class NoTradeDecisionPayload(BaseModel):
    decision_id: str
    agent_name: str
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    confidence_score: float
    reason_code: str
    reason_text: str
    market_context_id: str
    liquidity_check: str
    data_freshness_ms: int
    created_at: datetime


class SessionSummaryPayload(BaseModel):
    total_proposals: int
    status_counts: dict[str, int]
    approval_decisions: int
    execution_events: int
    state_snapshots: int
    operator_commands: int
    total_no_trade_decisions: int
    executed_proposals: int
    rejected_proposals: int


class DashboardKpisPayload(BaseModel):
    total_proposals: int
    total_no_trade_decisions: int
    executed_proposals: int
    rejected_proposals: int
    operator_commands: int


class DashboardRiskPayload(BaseModel):
    approval_decisions: int
    execution_events: int
    emergency_halt_active: bool
    halt_reason: str | None = None


class DashboardOperatorActivityPayload(BaseModel):
    recent_commands: list[str]
    command_count: int


class DashboardPayload(BaseModel):
    kpis: DashboardKpisPayload
    risk: DashboardRiskPayload
    latest_trades: list[TradeListItemPayload]
    operator_activity: DashboardOperatorActivityPayload


class HealthPayload(BaseModel):
    status: str
    storage: str | None = None
    auth_enabled: bool
