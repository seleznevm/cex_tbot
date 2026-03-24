from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from cex_tbot.shared import ensure_utc, utc_now
from cex_tbot.simulator import Position


@dataclass(frozen=True)
class PositionSnapshot:
    proposal_id: str
    position_id: str
    status: str
    remaining_size: float
    realized_pnl: float
    total_fees: float
    captured_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "captured_at", ensure_utc(self.captured_at))


@dataclass
class InMemoryExecutionStateStore:
    _snapshots: dict[str, list[PositionSnapshot]] = field(default_factory=dict)

    def append_snapshot(self, position: Position) -> PositionSnapshot:
        snapshot = PositionSnapshot(
            proposal_id=position.proposal_id,
            position_id=position.position_id,
            status=position.status,
            remaining_size=position.remaining_size,
            realized_pnl=position.realized_pnl,
            total_fees=position.total_fees,
        )
        self._snapshots.setdefault(position.proposal_id, []).append(snapshot)
        return snapshot

    def latest_snapshot(self, proposal_id: str) -> PositionSnapshot | None:
        items = self._snapshots.get(proposal_id, [])
        return items[-1] if items else None

    def list_snapshots(self, proposal_id: str) -> list[PositionSnapshot]:
        return list(self._snapshots.get(proposal_id, []))

    def export_timeline(self, proposal_id: str) -> list[dict[str, object]]:
        return [asdict(item) for item in self._snapshots.get(proposal_id, [])]
