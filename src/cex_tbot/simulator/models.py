from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from cex_tbot.enums import TradeDirection
from cex_tbot.shared import ensure_utc, new_id, utc_now


class PositionStatus:
    PENDING_EXECUTION = "PENDING_EXECUTION"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class FillEvent:
    proposal_id: str
    leg_number: int
    price: float
    size: float
    fee: float = 0.0
    slippage_bps: float = 0.0
    filled_at: datetime = field(default_factory=utc_now)
    fill_id: str = field(default_factory=lambda: new_id("fill"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "filled_at", ensure_utc(self.filled_at))


@dataclass(frozen=True)
class Position:
    proposal_id: str
    symbol: str
    direction: TradeDirection
    status: str
    planned_legs: int
    filled_legs: int
    avg_entry: float
    total_size: float
    remaining_size: float
    realized_pnl: float
    total_fees: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    tp1_hit: bool
    opened_at: datetime
    closed_at: datetime | None = None
    position_id: str = field(default_factory=lambda: new_id("position"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "opened_at", ensure_utc(self.opened_at))
        if self.closed_at is not None:
            object.__setattr__(self, "closed_at", ensure_utc(self.closed_at))

    def apply_fill(self, fill: FillEvent) -> "Position":
        new_filled_legs = self.filled_legs + 1
        new_total_size = self.total_size + fill.size
        new_avg = ((self.avg_entry * self.total_size) + (fill.price * fill.size)) / new_total_size if new_total_size else fill.price
        new_status = PositionStatus.OPEN if new_filled_legs >= self.planned_legs else PositionStatus.PARTIALLY_FILLED
        return replace(
            self,
            filled_legs=new_filled_legs,
            total_size=new_total_size,
            remaining_size=self.remaining_size + fill.size,
            avg_entry=new_avg,
            total_fees=self.total_fees + fill.fee,
            status=new_status,
        )

    def partial_close(self, price: float, size: float, fee: float = 0.0) -> "Position":
        close_size = min(size, self.remaining_size)
        if close_size <= 0:
            return self
        pnl_per_unit = (price - self.avg_entry) if self.direction == TradeDirection.LONG else (self.avg_entry - price)
        new_remaining = self.remaining_size - close_size
        new_status = PositionStatus.CLOSED if new_remaining <= 0 else PositionStatus.PARTIALLY_CLOSED
        return replace(
            self,
            remaining_size=new_remaining,
            realized_pnl=self.realized_pnl + (pnl_per_unit * close_size) - fee,
            total_fees=self.total_fees + fee,
            status=new_status,
            closed_at=utc_now() if new_remaining <= 0 else self.closed_at,
        )

    def close(self, *, stopped: bool, closed_at: datetime | None = None) -> "Position":
        return replace(self, status=PositionStatus.STOPPED if stopped else PositionStatus.CLOSED, remaining_size=0.0, closed_at=closed_at or utc_now())
