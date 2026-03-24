from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.execution import InMemoryExecutionStateStore
from cex_tbot.simulator import SimulatorService


class ExecutionStateStoreTests(unittest.TestCase):
    def test_appends_position_snapshots(self) -> None:
        now = datetime.now(UTC)
        proposal = TradeProposal(
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
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=99.0,
            take_profit_1=101.0,
            take_profit_2=102.0,
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
        sim = SimulatorService()
        position = sim.open_position(proposal)
        store = InMemoryExecutionStateStore()
        store.append_snapshot(position)
        self.assertEqual(store.latest_snapshot("proposal_1").status, "PENDING_EXECUTION")


if __name__ == "__main__":
    unittest.main()
