from __future__ import annotations

from datetime import UTC, datetime
import unittest

from cex_tbot.enums import TradeDirection
from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.execution.journal import InMemoryExecutionJournal
from cex_tbot.execution.lifecycle import DemoLifecycleSync
from cex_tbot.execution.state_store import InMemoryExecutionStateStore
from cex_tbot.simulator.models import Position, PositionStatus


class DemoLifecycleSyncTests(unittest.TestCase):
    def _position(self) -> Position:
        now = datetime.now(UTC)
        return Position(
            proposal_id="proposal_1",
            symbol="BTC_USDT",
            direction=TradeDirection.LONG,
            status=PositionStatus.OPEN,
            planned_legs=1,
            filled_legs=1,
            avg_entry=100.0,
            total_size=10.0,
            remaining_size=10.0,
            realized_pnl=0.0,
            total_fees=0.0,
            stop_loss=99.0,
            take_profit_1=101.0,
            take_profit_2=102.0,
            tp1_hit=False,
            opened_at=now,
            position_id="pos_1",
        )

    def test_tp1_and_tp2_sync_close_position(self) -> None:
        journal = InMemoryExecutionJournal()
        store = InMemoryExecutionStateStore()
        sync = DemoLifecycleSync(journal, store)
        updated = sync.apply(
            "proposal_1",
            self._position(),
            [
                DemoOrderRecord("entry", "proposal_1", "entry", "BTC_USDT", "buy", 10, "open"),
                DemoOrderRecord("sl", "proposal_1", "stop_loss", "BTC_USDT", "sell", 10, "open", trigger_price=99.0),
                DemoOrderRecord("tp1", "proposal_1", "take_profit_1", "BTC_USDT", "sell", 5, "finished", trigger_price=101.0),
                DemoOrderRecord("tp2", "proposal_1", "take_profit_2", "BTC_USDT", "sell", 5, "finished", trigger_price=102.0),
            ],
        )
        assert updated is not None
        self.assertEqual(updated.status, PositionStatus.CLOSED)
        self.assertEqual(updated.remaining_size, 0.0)
        kinds = [item.kind for item in journal.list_events("proposal_1")]
        self.assertIn("TP1_SYNC", kinds)
        self.assertIn("TP2_SYNC_FULL_CLOSE", kinds)

    def test_stop_sync_stops_position(self) -> None:
        journal = InMemoryExecutionJournal()
        store = InMemoryExecutionStateStore()
        sync = DemoLifecycleSync(journal, store)
        updated = sync.apply(
            "proposal_1",
            self._position(),
            [
                DemoOrderRecord("entry", "proposal_1", "entry", "BTC_USDT", "buy", 10, "open"),
                DemoOrderRecord("sl", "proposal_1", "stop_loss", "BTC_USDT", "sell", 10, "finished", trigger_price=99.0),
            ],
        )
        assert updated is not None
        self.assertEqual(updated.status, PositionStatus.STOPPED)
        kinds = [item.kind for item in journal.list_events("proposal_1")]
        self.assertIn("STOP_TRIGGERED_SYNC", kinds)


if __name__ == "__main__":
    unittest.main()
