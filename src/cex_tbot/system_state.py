from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SystemState:
    emergency_halt_active: bool = False
    halt_reason: str | None = None

    def activate_halt(self, reason: str) -> None:
        self.emergency_halt_active = True
        self.halt_reason = reason

    def clear_halt(self) -> None:
        self.emergency_halt_active = False
        self.halt_reason = None
