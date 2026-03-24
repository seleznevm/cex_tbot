from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from cex_tbot.execution.journal import ExecutionEvent, InMemoryExecutionJournal
from cex_tbot.execution.state_store import InMemoryExecutionStateStore, PositionSnapshot
from cex_tbot.shared import ensure_utc


class FileExecutionJournal(InMemoryExecutionJournal):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def append(self, event: ExecutionEvent) -> ExecutionEvent:
        saved = super().append(event)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._serialize_event(saved), ensure_ascii=False) + "\n")
        return saved

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            self._events.append(
                ExecutionEvent(
                    proposal_id=raw["proposal_id"],
                    kind=raw["kind"],
                    message=raw["message"],
                    event_time=ensure_utc(__import__("datetime").datetime.fromisoformat(raw["event_time"])),
                    position_id=raw.get("position_id"),
                    payload=raw.get("payload", {}),
                    event_id=raw["event_id"],
                )
            )

    @staticmethod
    def _serialize_event(event: ExecutionEvent) -> dict[str, object]:
        data = asdict(event)
        data["event_time"] = event.event_time.isoformat()
        return data


class FileExecutionStateStore(InMemoryExecutionStateStore):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def append_snapshot(self, position) -> PositionSnapshot:
        snapshot = super().append_snapshot(position)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._serialize_snapshot(snapshot), ensure_ascii=False) + "\n")
        return snapshot

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            snapshot = PositionSnapshot(
                proposal_id=raw["proposal_id"],
                position_id=raw["position_id"],
                status=raw["status"],
                remaining_size=raw["remaining_size"],
                realized_pnl=raw["realized_pnl"],
                total_fees=raw["total_fees"],
                captured_at=ensure_utc(__import__("datetime").datetime.fromisoformat(raw["captured_at"])),
            )
            self._snapshots.setdefault(snapshot.proposal_id, []).append(snapshot)

    @staticmethod
    def _serialize_snapshot(snapshot: PositionSnapshot) -> dict[str, object]:
        data = asdict(snapshot)
        data["captured_at"] = snapshot.captured_at.isoformat()
        return data
