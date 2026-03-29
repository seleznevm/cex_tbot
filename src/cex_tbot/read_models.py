from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.execution import TradeTimelineBuilder, TradeTimelineView
from cex_tbot.query_params import TradeQuery
from cex_tbot.session_store import TradeSessionStore


@dataclass(frozen=True)
class TradeListItem:
    proposal_id: str
    symbol: str
    direction: str
    timeframe: str
    status: str
    confidence_score: float
    created_at: str
    event_count: int
    snapshot_count: int


@dataclass(frozen=True)
class TradeDetailView:
    proposal_id: str
    proposal_version: int
    agent_name: str
    strategy_id: str
    strategy_version: str
    market_context_id: str
    status: str
    symbol: str
    direction: str
    timeframe: str
    confidence_score: float
    entry_zone_min: float
    entry_zone_max: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_percent: float
    risk_usd: float
    position_size: float
    thesis: str
    invalidity_condition: str
    liquidity_check: str
    data_freshness_ms: int
    created_at: str
    expires_at: str
    timeline: TradeTimelineView
    approval_decision_count: int
    operator_command_count: int
    demo_order_count: int


class QueryService:
    def __init__(self, session: TradeSessionStore, timeline_builder: TradeTimelineBuilder) -> None:
        self.session = session
        self.timeline_builder = timeline_builder

    def _filtered_items(self, query: TradeQuery | None = None) -> list[TradeListItem]:
        query = query or TradeQuery()
        items: list[TradeListItem] = []
        for proposal in self.session.proposals._proposals.values():
            timeline = self.timeline_builder.build(proposal.proposal_id)
            items.append(
                TradeListItem(
                    proposal_id=proposal.proposal_id,
                    symbol=proposal.symbol,
                    direction=proposal.direction.value,
                    timeframe=proposal.timeframe,
                    status=proposal.status.value,
                    confidence_score=proposal.confidence_score,
                    created_at=proposal.created_at.isoformat(),
                    event_count=timeline.event_count,
                    snapshot_count=timeline.snapshot_count,
                )
            )
        if query.status is not None:
            items = [item for item in items if item.status == query.status]
        if query.symbol is not None:
            items = [item for item in items if item.symbol == query.symbol]
        if query.direction is not None:
            items = [item for item in items if item.direction == query.direction]
        if query.sort_by not in {"proposal_id", "confidence_score", "status", "symbol", "created_at"}:
            raise ValueError(f"unsupported sort_by={query.sort_by}")
        items.sort(key=lambda item: getattr(item, query.sort_by), reverse=query.descending)
        return items

    def count_trades(self, query: TradeQuery | None = None) -> int:
        return len(self._filtered_items(query))

    def list_trades(self, query: TradeQuery | None = None) -> list[TradeListItem]:
        query = query or TradeQuery()
        items = self._filtered_items(query)
        start = max(query.offset, 0)
        end = None if query.limit is None else start + max(query.limit, 0)
        return items[start:end]

    def get_trade_detail(self, proposal_id: str) -> TradeDetailView:
        proposal = self.session.proposals.require(proposal_id)
        timeline = self.timeline_builder.build(proposal_id)
        return TradeDetailView(
            proposal_id=proposal.proposal_id,
            proposal_version=proposal.proposal_version,
            agent_name=proposal.agent_name,
            strategy_id=proposal.strategy_id,
            strategy_version=proposal.strategy_version,
            market_context_id=proposal.market_context_id,
            status=proposal.status.value,
            symbol=proposal.symbol,
            direction=proposal.direction.value,
            timeframe=proposal.timeframe,
            confidence_score=proposal.confidence_score,
            entry_zone_min=proposal.entry_zone_min,
            entry_zone_max=proposal.entry_zone_max,
            stop_loss=proposal.stop_loss,
            take_profit_1=proposal.take_profit_1,
            take_profit_2=proposal.take_profit_2,
            risk_percent=proposal.risk_percent,
            risk_usd=proposal.risk_usd,
            position_size=proposal.position_size,
            thesis=proposal.thesis,
            invalidity_condition=proposal.invalidity_condition,
            liquidity_check=proposal.liquidity_check,
            data_freshness_ms=proposal.data_freshness_ms,
            created_at=proposal.created_at.isoformat(),
            expires_at=proposal.expires_at.isoformat(),
            timeline=timeline,
            approval_decision_count=len(self.session.proposals.history(proposal_id)),
            operator_command_count=len(self.session.operator_transcript.list_entries(proposal_id)),
            demo_order_count=len(self.session.demo_orders.list_for_proposal(proposal_id)),
        )
