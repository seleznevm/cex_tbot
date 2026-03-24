from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.execution.journal import InMemoryExecutionJournal
from cex_tbot.execution.state_store import InMemoryExecutionStateStore


@dataclass(frozen=True)
class TradeTimelineView:
    proposal_id: str
    event_count: int
    snapshot_count: int
    events: list[dict[str, object]]
    snapshots: list[dict[str, object]]


class TradeTimelineBuilder:
    def __init__(self, journal: InMemoryExecutionJournal, state_store: InMemoryExecutionStateStore) -> None:
        self.journal = journal
        self.state_store = state_store

    def build(self, proposal_id: str) -> TradeTimelineView:
        events = [event.__dict__.copy() for event in self.journal.list_events(proposal_id)]
        snapshots = self.state_store.export_timeline(proposal_id)
        return TradeTimelineView(
            proposal_id=proposal_id,
            event_count=len(events),
            snapshot_count=len(snapshots),
            events=events,
            snapshots=snapshots,
        )
