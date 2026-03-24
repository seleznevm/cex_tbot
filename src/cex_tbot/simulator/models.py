from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from cex_tbot.enums import ProposalStatus, TradeDirection
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
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
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
        return replace(self, filled_legs=new_filled_legs, total_size=new_total_size, avg_entry=new_avg, status=new_status)

    def close(self, *, stopped: bool, closed_at: datetime | None = None) -> "Position":
        return replace(self, status=PositionStatus.STOPPED if stopped else PositionStatus.CLOSED, closed_at=closed_at or utc_now())
