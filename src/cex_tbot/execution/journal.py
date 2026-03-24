from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.shared import ensure_utc, new_id, utc_now


@dataclass(frozen=True)
class ExecutionEvent:
    proposal_id: str
    kind: str
    message: str
    event_time: datetime = field(default_factory=utc_now)
    position_id: str | None = None
    payload: dict[str, str | float | int | bool] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("event"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_time", ensure_utc(self.event_time))


@dataclass
class InMemoryExecutionJournal:
    _events: list[ExecutionEvent] = field(default_factory=list)

    def append(self, event: ExecutionEvent) -> ExecutionEvent:
        self._events.append(event)
        return event

    def list_events(self, proposal_id: str | None = None) -> list[ExecutionEvent]:
        if proposal_id is None:
            return list(self._events)
        return [event for event in self._events if event.proposal_id == proposal_id]
