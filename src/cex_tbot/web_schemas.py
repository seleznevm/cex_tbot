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
    created_at: datetime
    event_count: int
    snapshot_count: int


class TradeListPagePayload(BaseModel):
    items: list[TradeListItemPayload]
    total: int
    limit: int
    offset: int
    has_more: bool


class DemoPolicyPayload(BaseModel):
    proposal_id: str
    mode: str
    alerts: list[str] = Field(default_factory=list)
    auto_actions: list[str] = Field(default_factory=list)


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
    demo_policy: DemoPolicyPayload | None = None


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


class NoTradeSubmitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str | None = None
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
    created_at: datetime | None = None


class SessionSummaryPayload(BaseModel):
    total_proposals: int
    total_no_trade_decisions: int
    executed_proposals: int
    rejected_proposals: int
    approval_decisions: int
    execution_events: int
    state_snapshots: int
    operator_commands: int
    emergency_halt_active: bool = False
    halt_reason: str | None = None
    safety_state: str = "NORMAL"
    block_new_trades: bool = False
    block_reason: str | None = None
    proposal_status_breakdown: dict[str, int] = Field(default_factory=dict)


class DashboardKpisPayload(BaseModel):
    total_proposals: int
    total_no_trade_decisions: int
    executed_proposals: int
    rejected_proposals: int
    pending_approvals: int
    operator_commands: int
    status_breakdown: dict[str, int] = Field(default_factory=dict)


class DashboardRiskPayload(BaseModel):
    active_trades: int
    avg_confidence_score: float
    approval_decisions: int
    execution_events: int
    emergency_halt_active: bool
    halt_reason: str | None = None
    safety_state: str = "NORMAL"
    block_new_trades: bool = False
    block_reason: str | None = None
    max_open_risk_percent: float = 0.0
    reserved_pending_risk_percent: float = 0.0
    active_risk_percent: float = 0.0
    free_risk_budget_percent: float = 0.0


class DashboardOperatorActivityItemPayload(BaseModel):
    actor: str
    raw_command: str
    outcome: str
    proposal_id: str | None = None
    created_at: datetime


class DashboardOperatorActivityPayload(BaseModel):
    command_count: int
    latest_outcomes: list[str]
    recent_items: list[DashboardOperatorActivityItemPayload] = Field(default_factory=list)


class DashboardAlertItemPayload(BaseModel):
    level: str
    code: str
    message: str


class DashboardAlertsPayload(BaseModel):
    items: list[DashboardAlertItemPayload] = Field(default_factory=list)


class DashboardUniversePayload(BaseModel):
    snapshot_id: str | None = None
    refresh_reason: str | None = None
    last_refresh_at: datetime | None = None
    total_instruments: int = 0
    eligible_instruments: int = 0
    ineligible_instruments: int = 0
    stale_instruments: int = 0
    eligible_symbols: list[str] = Field(default_factory=list)


class CalibrationRecommendationPayload(BaseModel):
    action: str
    target: str
    severity: str
    reason: str


class DashboardPostAnalysisPayload(BaseModel):
    total_trades: int = 0
    executed_trades: int = 0
    no_trade_decisions: int = 0
    avg_confidence_all: float = 0.0
    top_rejection_status: str | None = None
    top_no_trade_reason: str | None = None
    top_strategy: str | None = None
    top_timeframe: str | None = None
    recent_trade_count: int = 0
    recent_executed_trades: int = 0
    recent_rejected_trades: int = 0
    recent_avg_confidence: float = 0.0
    trend_hint: str | None = None
    recommendations: list[CalibrationRecommendationPayload] = Field(default_factory=list)
    latest_hint: str | None = None


class DashboardPayload(BaseModel):
    kpis: DashboardKpisPayload
    risk: DashboardRiskPayload
    latest_trades: list[TradeListItemPayload]
    operator_activity: DashboardOperatorActivityPayload
    alerts: DashboardAlertsPayload
    universe: DashboardUniversePayload
    post_analysis: DashboardPostAnalysisPayload


class PostAnalysisPayload(BaseModel):
    total_trades: int
    executed_trades: int
    rejected_trades: int
    pending_trades: int
    no_trade_decisions: int
    avg_confidence_all: float
    avg_confidence_executed: float
    avg_confidence_no_trade: float
    top_rejection_statuses: dict[str, int] = Field(default_factory=dict)
    no_trade_reason_counts: dict[str, int] = Field(default_factory=dict)
    symbol_activity: dict[str, int] = Field(default_factory=dict)
    timeframe_activity: dict[str, int] = Field(default_factory=dict)
    strategy_activity: dict[str, int] = Field(default_factory=dict)
    outcome_matrix: dict[str, dict[str, int]] = Field(default_factory=dict)
    recent_trade_count: int = 0
    recent_executed_trades: int = 0
    recent_rejected_trades: int = 0
    recent_avg_confidence: float = 0.0
    trend_hint: str | None = None
    trade_confidence_buckets: dict[str, int] = Field(default_factory=dict)
    no_trade_confidence_buckets: dict[str, int] = Field(default_factory=dict)
    recommendations: list[CalibrationRecommendationPayload] = Field(default_factory=list)
    calibration_hints: list[str] = Field(default_factory=list)


class HaltPayload(BaseModel):
    reason: str


class HealthPayload(BaseModel):
    status: str
    storage: str | None = None
    auth_enabled: bool
