from __future__ import annotations

from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.execution.journal import ExecutionEvent, InMemoryExecutionJournal
from cex_tbot.execution.state_store import InMemoryExecutionStateStore
from cex_tbot.simulator.models import Position, PositionStatus
from cex_tbot.shared import utc_now


class DemoLifecycleSync:
    def __init__(self, journal: InMemoryExecutionJournal, state_store: InMemoryExecutionStateStore) -> None:
        self.journal = journal
        self.state_store = state_store

    def apply(self, proposal_id: str, position: Position | None, orders: list[DemoOrderRecord]) -> Position | None:
        if position is None:
            return None
        entry = next((item for item in orders if item.role == "entry"), None)
        stop = next((item for item in orders if item.role == "stop_loss"), None)
        tp1 = next((item for item in orders if item.role == "take_profit_1"), None)
        tp2 = next((item for item in orders if item.role == "take_profit_2"), None)

        normalized = {item.role: str(item.status).lower() for item in orders}
        updated = position

        if entry is not None and str(entry.status).lower() in {"cancelled", "canceled"} and position.status not in {PositionStatus.CLOSED, PositionStatus.STOPPED, PositionStatus.CANCELLED}:
            updated = Position(**{**updated.__dict__, "status": PositionStatus.CANCELLED, "remaining_size": 0.0, "closed_at": utc_now()})
            self._append(proposal_id, updated, "ENTRY_CANCELLED", "entry order cancelled before completion")
            return updated

        if stop is not None and normalized.get("stop_loss") in {"finished", "triggered", "closed"} and position.status not in {PositionStatus.STOPPED, PositionStatus.CLOSED}:
            updated = Position(**{**updated.__dict__, "status": PositionStatus.STOPPED, "remaining_size": 0.0, "closed_at": utc_now()})
            self._append(proposal_id, updated, "STOP_TRIGGERED_SYNC", "stop loss synced from Gate demo")
            return updated

        tp1_filled = tp1 is not None and normalized.get("take_profit_1") in {"finished", "triggered", "closed"}
        tp2_filled = tp2 is not None and normalized.get("take_profit_2") in {"finished", "triggered", "closed"}

        if tp1_filled and not position.tp1_hit and position.remaining_size > 0:
            half_size = max(position.remaining_size / 2, 0.0)
            updated = Position(**{**updated.partial_close(position.take_profit_1, half_size).__dict__, "tp1_hit": True})
            self._append(proposal_id, updated, "TP1_SYNC", "tp1 synced from Gate demo")

        if tp2_filled and updated.remaining_size > 0:
            updated = updated.partial_close(position.take_profit_2, updated.remaining_size)
            final_kind = "TP2_SYNC_FULL_CLOSE" if updated.remaining_size <= 0 else "TP2_SYNC"
            self._append(proposal_id, updated, final_kind, "tp2 synced from Gate demo")

        return updated

    def _append(self, proposal_id: str, position: Position, kind: str, message: str) -> None:
        self.state_store.append_snapshot(position)
        self.journal.append(
            ExecutionEvent(
                proposal_id,
                kind,
                message,
                position_id=position.position_id,
                payload={"status": position.status, "remaining_size": position.remaining_size},
            )
        )
