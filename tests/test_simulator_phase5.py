from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.market_data import MarketSnapshot
from cex_tbot.simulator import SimulatorService


class SimulatorPhase5Tests(unittest.TestCase):
    def _proposal(self, direction: TradeDirection = TradeDirection.LONG) -> TradeProposal:
        now = datetime.now(UTC)
        return TradeProposal(
            proposal_id="proposal_1",
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=direction,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=97.0 if direction == TradeDirection.LONG else 103.0,
            take_profit_1=102.0 if direction == TradeDirection.LONG else 98.0,
            take_profit_2=104.0 if direction == TradeDirection.LONG else 96.0,
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

    def test_tp1_causes_partial_close(self) -> None:
        sim = SimulatorService()
        proposal = self._proposal()
        position = sim.open_position(proposal)
        fill = sim.build_fill(proposal, 1, 100.0, 10.0)
        position = sim.execute_fill(position, fill)
        updated = sim.process_protective_levels(position, MarketSnapshot("BTC_USDT", 102.0, 102.1, 102.0, 1_000_000, 500_000, 1.0, 100_000))
        self.assertEqual(updated.status, "PARTIALLY_CLOSED")
        self.assertTrue(updated.tp1_hit)
        self.assertLess(updated.remaining_size, position.remaining_size)

    def test_short_tp2_closes_position(self) -> None:
        sim = SimulatorService()
        proposal = self._proposal(TradeDirection.SHORT)
        position = sim.open_position(proposal)
        fill = sim.build_fill(proposal, 1, 100.0, 10.0)
        position = sim.execute_fill(position, fill)
        position = sim.process_protective_levels(position, MarketSnapshot("BTC_USDT", 98.0, 98.1, 98.0, 1_000_000, 500_000, 1.0, 100_000))
        closed = sim.process_protective_levels(position, MarketSnapshot("BTC_USDT", 96.0, 96.1, 96.0, 1_000_000, 500_000, 1.0, 100_000))
        self.assertEqual(closed.status, "CLOSED")
        self.assertEqual(closed.remaining_size, 0.0)


if __name__ == "__main__":
    unittest.main()
