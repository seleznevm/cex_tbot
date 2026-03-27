from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.audit import AuditEntry, InMemoryOperatorTranscript
from cex_tbot.enums import SafetyState
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.system_state import SystemState


@dataclass(frozen=True)
class SafetyEvaluationResult:
    safety_state: SafetyState
    block_new_trades: bool
    reason: str | None = None


class SafetyController:
    def __init__(
        self,
        system_state: SystemState,
        transcript: InMemoryOperatorTranscript,
        risk_engine: RiskEngine,
    ) -> None:
        self.system_state = system_state
        self.transcript = transcript
        self.risk_engine = risk_engine

    def clear_safety_controls(self) -> None:
        if self.system_state.emergency_halt_active:
            self.transcript.append(
                AuditEntry(actor="system", raw_command="CLEAR_SAFETY_SKIPPED", outcome="CLEAR_SAFETY_SKIPPED")
            )
            return
        had_block = self.system_state.block_new_trades
        had_warning = self.system_state.safety_state == SafetyState.WARNING
        self.system_state.clear_block()
        self.system_state.clear_warning()
        if had_block or had_warning:
            self.transcript.append(
                AuditEntry(actor="system", raw_command="CLEAR_SAFETY", outcome="CLEAR_SAFETY")
            )

    def evaluate(self, portfolio: PortfolioState) -> SafetyEvaluationResult:
        if self.system_state.emergency_halt_active:
            return SafetyEvaluationResult(SafetyState.HALTED, True, self.system_state.halt_reason)

        previous_block = self.system_state.block_reason if self.system_state.block_new_trades else None
        previous_warning = self.system_state.block_reason if self.system_state.safety_state == SafetyState.WARNING else None

        def apply_block(reason: str) -> SafetyEvaluationResult:
            self.system_state.set_block(reason, safety_state=SafetyState.BLOCK_NEW_TRADES)
            if previous_block != reason:
                self.transcript.append(
                    AuditEntry(actor="system", raw_command=f"AUTO_BLOCK {reason}", outcome="AUTO_BLOCK_ON")
                )
            return SafetyEvaluationResult(SafetyState.BLOCK_NEW_TRADES, True, reason)

        def apply_warning(reason: str) -> SafetyEvaluationResult:
            self.system_state.set_warning(reason)
            if previous_warning != reason:
                self.transcript.append(
                    AuditEntry(actor="system", raw_command=f"AUTO_WARNING {reason}", outcome="AUTO_WARNING_ON")
                )
            return SafetyEvaluationResult(SafetyState.WARNING, False, reason)

        max_drawdown = self.risk_engine.config.max_daily_drawdown_percent
        max_positions = self.risk_engine.config.max_open_positions
        max_risk = self.risk_engine.config.max_aggregate_open_risk_percent
        projected_reserved = self.risk_engine.pending_risk_book.total_reserved_risk_pct + portfolio.aggregate_open_risk_pct

        if portfolio.daily_drawdown_pct >= max_drawdown:
            return apply_block(f"daily drawdown limit reached: {portfolio.daily_drawdown_pct:.2f}%")
        if portfolio.open_positions_count >= max_positions:
            return apply_block(f"max open positions reached: {portfolio.open_positions_count}")
        if projected_reserved >= max_risk:
            return apply_block(f"aggregate open risk exhausted: {projected_reserved:.2f}%")

        warning_reason = None
        if max_drawdown > 0 and portfolio.daily_drawdown_pct >= max_drawdown * 0.8:
            warning_reason = f"daily drawdown nearing limit: {portfolio.daily_drawdown_pct:.2f}%"
        elif max_positions > 1 and portfolio.open_positions_count >= max_positions - 1:
            warning_reason = f"open positions near limit: {portfolio.open_positions_count}/{max_positions}"
        elif max_risk > 0 and projected_reserved >= max_risk * 0.8:
            warning_reason = f"aggregate open risk nearing cap: {projected_reserved:.2f}%"

        if self.system_state.block_new_trades:
            self.transcript.append(
                AuditEntry(actor="system", raw_command="AUTO_BLOCK_CLEAR", outcome="AUTO_BLOCK_OFF")
            )
        self.system_state.clear_block()

        if warning_reason is not None:
            return apply_warning(warning_reason)

        if self.system_state.safety_state == SafetyState.WARNING:
            self.transcript.append(
                AuditEntry(actor="system", raw_command="AUTO_WARNING_CLEAR", outcome="AUTO_WARNING_OFF")
            )
        self.system_state.clear_warning()
        return SafetyEvaluationResult(SafetyState.NORMAL, False, None)
