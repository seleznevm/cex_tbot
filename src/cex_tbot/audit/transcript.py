from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.shared import ensure_utc, new_id, utc_now


@dataclass(frozen=True)
class AuditEntry:
    actor: str
    raw_command: str
    outcome: str
    proposal_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    entry_id: str = field(default_factory=lambda: new_id("audit"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc(self.created_at))


@dataclass
class InMemoryOperatorTranscript:
    _entries: list[AuditEntry] = field(default_factory=list)

    def append(self, entry: AuditEntry) -> AuditEntry:
        self._entries.append(entry)
        return entry

    def list_entries(self, proposal_id: str | None = None) -> list[AuditEntry]:
        if proposal_id is None:
            return list(self._entries)
        return [entry for entry in self._entries if entry.proposal_id == proposal_id]
