from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.enums import SafetyState


@dataclass
class SystemState:
    emergency_halt_active: bool = False
    halt_reason: str | None = None
    safety_state: SafetyState = SafetyState.NORMAL
    block_new_trades: bool = False
    block_reason: str | None = None

    def activate_halt(self, reason: str) -> None:
        self.emergency_halt_active = True
        self.halt_reason = reason
        self.safety_state = SafetyState.HALTED
        self.block_new_trades = True
        self.block_reason = reason

    def clear_halt(self) -> None:
        self.emergency_halt_active = False
        self.halt_reason = None
        self.safety_state = SafetyState.NORMAL
        self.block_new_trades = False
        self.block_reason = None

    def set_block(self, reason: str, *, safety_state: SafetyState = SafetyState.BLOCK_NEW_TRADES) -> None:
        self.block_new_trades = True
        self.block_reason = reason
        self.safety_state = safety_state

    def clear_block(self) -> None:
        if not self.emergency_halt_active:
            self.block_new_trades = False
            self.block_reason = None
            self.safety_state = SafetyState.NORMAL

    def set_warning(self, reason: str) -> None:
        if not self.emergency_halt_active and not self.block_new_trades:
            self.safety_state = SafetyState.WARNING
            self.block_reason = reason

    def clear_warning(self) -> None:
        if not self.emergency_halt_active and not self.block_new_trades and self.safety_state == SafetyState.WARNING:
            self.safety_state = SafetyState.NORMAL
            self.block_reason = None
