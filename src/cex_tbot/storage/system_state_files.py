from __future__ import annotations

import json
from pathlib import Path

from cex_tbot.system_state import SystemState


class FileSystemState(SystemState):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def activate_halt(self, reason: str) -> None:
        super().activate_halt(reason)
        self._save()

    def clear_halt(self) -> None:
        super().clear_halt()
        self._save()

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "emergency_halt_active": self.emergency_halt_active,
                    "halt_reason": self.halt_reason,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.emergency_halt_active = bool(raw.get("emergency_halt_active", False))
        self.halt_reason = raw.get("halt_reason")
