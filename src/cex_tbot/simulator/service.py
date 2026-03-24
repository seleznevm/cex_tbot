from __future__ import annotations

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.market_data import MarketSnapshot
from cex_tbot.simulator.models import FillEvent, Position, PositionStatus


class SimulatorService:
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
            stop_loss=proposal.stop_loss,
            take_profit_1=proposal.take_profit_1,
            take_profit_2=proposal.take_profit_2,
            opened_at=proposal.created_at,
        )

    def execute_fill(self, position: Position, fill: FillEvent) -> Position:
        return position.apply_fill(fill)

    def process_protective_levels(self, position: Position, snapshot: MarketSnapshot) -> Position:
        if position.direction.value == "LONG":
            if snapshot.last_price <= position.stop_loss:
                return position.close(stopped=True)
            if snapshot.last_price >= position.take_profit_2:
                return position.close(stopped=False)
        else:
            if snapshot.last_price >= position.stop_loss:
                return position.close(stopped=True)
            if snapshot.last_price <= position.take_profit_2:
                return position.close(stopped=False)
        return position
