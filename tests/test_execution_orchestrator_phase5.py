from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.execution import ExecutionOrchestrator
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.simulator import SimulatorService


class ExecutionOrchestratorPhase5Tests(unittest.TestCase):
    def test_execution_applies_slippage_and_fees(self) -> None:
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
        orchestrator = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService())
        result = orchestrator.execute(proposal, PortfolioState(equity=1000.0), now=now)
        assert result.position is not None
        self.assertGreater(result.position.avg_entry, 100.0)
        self.assertGreater(result.position.total_fees, 0.0)


if __name__ == "__main__":
    unittest.main()
