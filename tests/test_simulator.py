from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.market_data import MarketSnapshot
from cex_tbot.simulator import FillEvent, SimulatorService


class SimulatorTests(unittest.TestCase):
    def _proposal(self) -> TradeProposal:
        now = datetime.now(UTC)
        return TradeProposal(
            proposal_id="proposal_1",
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[
                EntrySplitLeg(1, 100.0, 50.0, 0.5, now + timedelta(minutes=10)),
                EntrySplitLeg(2, 99.8, 50.0, 0.5, now + timedelta(minutes=10)),
            ],
            stop_loss=97.0,
            take_profit_1=102.0,
            take_profit_2=104.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=10.0,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
        )

    def test_open_and_fill_position(self) -> None:
        sim = SimulatorService()
        proposal = self._proposal()
        position = sim.open_position(proposal)
        position = sim.execute_fill(position, FillEvent(proposal.proposal_id, 1, 100.0, 5.0))
        self.assertEqual(position.filled_legs, 1)
        self.assertEqual(position.status, "PARTIALLY_FILLED")

    def test_hits_take_profit(self) -> None:
        sim = SimulatorService()
        proposal = self._proposal()
        position = sim.open_position(proposal)
        position = sim.execute_fill(position, FillEvent(proposal.proposal_id, 1, 100.0, 5.0))
        position = sim.execute_fill(position, FillEvent(proposal.proposal_id, 2, 99.8, 5.0))
        partial = sim.process_protective_levels(position, MarketSnapshot("BTC_USDT", 102.0, 102.1, 102.0, 1_000_000, 500_000, 1.0, 100_000))
        closed = sim.process_protective_levels(partial, MarketSnapshot("BTC_USDT", 104.0, 104.1, 104.0, 1_000_000, 500_000, 1.0, 100_000))
        self.assertEqual(closed.status, "CLOSED")


if __name__ == "__main__":
    unittest.main()
