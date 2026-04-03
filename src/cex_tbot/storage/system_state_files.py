from __future__ import annotations

import json
from pathlib import Path

from cex_tbot.enums import SafetyState
from cex_tbot.system_state import SystemState


class FileSystemState(SystemState):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def refresh_from_disk(self) -> None:
        self.emergency_halt_active = False
        self.halt_reason = None
        self.safety_state = SafetyState.NORMAL
        self.block_new_trades = False
        self.block_reason = None
        if self.path.exists():
            self._load()

    def activate_halt(self, reason: str) -> None:
        super().activate_halt(reason)
        self._save()

    def clear_halt(self) -> None:
        super().clear_halt()
        self._save()

    def set_block(self, reason: str, *, safety_state=None) -> None:
        if safety_state is None:
            super().set_block(reason)
        else:
            super().set_block(reason, safety_state=safety_state)
        self._save()

    def clear_block(self) -> None:
        super().clear_block()
        self._save()

    def set_warning(self, reason: str) -> None:
        super().set_warning(reason)
        self._save()

    def clear_warning(self) -> None:
        super().clear_warning()
        self._save()

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "emergency_halt_active": self.emergency_halt_active,
                    "halt_reason": self.halt_reason,
                    "safety_state": self.safety_state.value,
                    "block_new_trades": self.block_new_trades,
                    "block_reason": self.block_reason,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.emergency_halt_active = bool(raw.get("emergency_halt_active", False))
        self.halt_reason = raw.get("halt_reason")
        self.safety_state = SafetyState(raw.get("safety_state", SafetyState.NORMAL.value))
        self.block_new_trades = bool(raw.get("block_new_trades", False))
        self.block_reason = raw.get("block_reason")
