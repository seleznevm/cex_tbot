from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.execution import ExecutionOrchestrator, InMemoryExecutionJournal
from cex_tbot.market_data import MarketSnapshot
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.simulator import SimulatorService


class ExecutionJournalTests(unittest.TestCase):
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

    def test_journal_records_execution_events(self) -> None:
        journal = InMemoryExecutionJournal()
        orchestrator = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService(), journal=journal)
        result = orchestrator.execute(self._proposal(), PortfolioState(equity=1000.0))
        events = journal.list_events("proposal_1")
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual(events[0].kind, "PRE_EXECUTION_CHECK")
        assert result.position is not None
        updated = orchestrator.process_market_tick("proposal_1", result.position, MarketSnapshot("BTC_USDT", 101.0, 101.1, 101.0, 1_000_000, 500_000, 1.0, 100_000))
        events = journal.list_events("proposal_1")
        self.assertTrue(any(event.kind == "TP1_PARTIAL_CLOSE" for event in events))
        self.assertEqual(updated.status, "PARTIALLY_CLOSED")


if __name__ == "__main__":
    unittest.main()
