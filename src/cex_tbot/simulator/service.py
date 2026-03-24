from __future__ import annotations

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.market_data import MarketSnapshot
from cex_tbot.simulator.models import FillEvent, Position, PositionStatus


class SimulatorService:
    def __init__(self, fee_rate: float = 0.0005, default_slippage_bps: float = 1.0) -> None:
        self.fee_rate = fee_rate
        self.default_slippage_bps = default_slippage_bps

    def open_position(self, proposal: TradeProposal) -> Position:
        return Position(
            proposal_id=proposal.proposal_id,
            symbol=proposal.symbol,
            direction=proposal.direction,
            status=PositionStatus.PENDING_EXECUTION,
            planned_legs=len(proposal.entry_split),
            filled_legs=0,
            avg_entry=0.0,
            total_size=0.0,
            remaining_size=0.0,
            realized_pnl=0.0,
            total_fees=0.0,
            stop_loss=proposal.stop_loss,
            take_profit_1=proposal.take_profit_1,
            take_profit_2=proposal.take_profit_2,
            tp1_hit=False,
            opened_at=proposal.created_at,
        )

    def build_fill(self, proposal: TradeProposal, leg_number: int, planned_price: float, size: float) -> FillEvent:
        slipped_price = planned_price * (1 + self.default_slippage_bps / 10_000)
        fee = slipped_price * size * self.fee_rate
        return FillEvent(proposal.proposal_id, leg_number, slipped_price, size, fee=fee, slippage_bps=self.default_slippage_bps)

    def execute_fill(self, position: Position, fill: FillEvent) -> Position:
        return position.apply_fill(fill)

    def process_protective_levels(self, position: Position, snapshot: MarketSnapshot) -> Position:
        if position.remaining_size <= 0:
            return position
        if position.direction.value == "LONG":
            if snapshot.last_price <= position.stop_loss:
                return position.close(stopped=True)
            if not position.tp1_hit and snapshot.last_price >= position.take_profit_1:
                updated = position.partial_close(snapshot.last_price, position.remaining_size / 2, fee=snapshot.last_price * (position.remaining_size / 2) * self.fee_rate)
                return Position(**{**updated.__dict__, "tp1_hit": True})
            if snapshot.last_price >= position.take_profit_2:
                return position.partial_close(snapshot.last_price, position.remaining_size, fee=snapshot.last_price * position.remaining_size * self.fee_rate)
        else:
            if snapshot.last_price >= position.stop_loss:
                return position.close(stopped=True)
            if not position.tp1_hit and snapshot.last_price <= position.take_profit_1:
                updated = position.partial_close(snapshot.last_price, position.remaining_size / 2, fee=snapshot.last_price * (position.remaining_size / 2) * self.fee_rate)
                return Position(**{**updated.__dict__, "tp1_hit": True})
            if snapshot.last_price <= position.take_profit_2:
                return position.partial_close(snapshot.last_price, position.remaining_size, fee=snapshot.last_price * position.remaining_size * self.fee_rate)
        return position
