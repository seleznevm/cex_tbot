from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.shared import ensure_utc, utc_now


@dataclass(frozen=True)
class DemoOrderRecord:
    order_id: str
    proposal_id: str
    role: str
    contract: str
    side: str
    size: float
    status: str
    trigger_price: float | None = None
    order_price: float | None = None
    reduce_only: bool = False
    linked_entry_order_id: str | None = None
    synced_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "synced_at", ensure_utc(self.synced_at))


@dataclass
class InMemoryDemoOrderStore:
    _by_proposal: dict[str, list[DemoOrderRecord]] = field(default_factory=dict)

    def replace_for_proposal(self, proposal_id: str, records: list[DemoOrderRecord]) -> None:
        self._by_proposal[proposal_id] = list(records)

    def list_for_proposal(self, proposal_id: str) -> list[DemoOrderRecord]:
        return list(self._by_proposal.get(proposal_id, []))

    def find(self, proposal_id: str, role: str) -> DemoOrderRecord | None:
        for item in self._by_proposal.get(proposal_id, []):
            if item.role == role:
                return item
        return None
