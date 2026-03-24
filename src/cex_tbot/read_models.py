from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.execution import TradeTimelineBuilder, TradeTimelineView
from cex_tbot.session_store import TradeSessionStore


@dataclass(frozen=True)
class TradeListItem:
    proposal_id: str
    symbol: str
    direction: str
    timeframe: str
    status: str
    confidence_score: float
    event_count: int
    snapshot_count: int


@dataclass(frozen=True)
class TradeDetailView:
    proposal_id: str
    status: str
    symbol: str
    direction: str
    timeframe: str
    confidence_score: float
    timeline: TradeTimelineView
    approval_decision_count: int
    operator_command_count: int


class QueryService:
    def __init__(self, session: TradeSessionStore, timeline_builder: TradeTimelineBuilder) -> None:
        self.session = session
        self.timeline_builder = timeline_builder

    def list_trades(self) -> list[TradeListItem]:
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
                    event_count=timeline.event_count,
                    snapshot_count=timeline.snapshot_count,
                )
            )
        items.sort(key=lambda item: item.proposal_id)
        return items

    def get_trade_detail(self, proposal_id: str) -> TradeDetailView:
        proposal = self.session.proposals.require(proposal_id)
        timeline = self.timeline_builder.build(proposal_id)
        return TradeDetailView(
            proposal_id=proposal.proposal_id,
            status=proposal.status.value,
            symbol=proposal.symbol,
            direction=proposal.direction.value,
            timeframe=proposal.timeframe,
            confidence_score=proposal.confidence_score,
            timeline=timeline,
            approval_decision_count=len(self.session.proposals.history(proposal_id)),
            operator_command_count=len(self.session.operator_transcript.list_entries(proposal_id)),
        )
