from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.simulator import SimulatorService


class ExecutionOrchestratorTests(unittest.TestCase):
    def _proposal(self, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        payload = dict(
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
        payload.update(overrides)
        return TradeProposal(**payload)

    def test_executes_approved_proposal(self) -> None:
        orchestrator = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService())
        result = orchestrator.execute(self._proposal(), PortfolioState(equity=1000.0))
        self.assertEqual(result.status, ProposalStatus.EXECUTED)
        assert result.position is not None
        self.assertEqual(result.position.status, "OPEN")

    def test_blocks_pre_execution_failure(self) -> None:
        orchestrator = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService())
        bad = self._proposal(expires_at=datetime.now(UTC) - timedelta(minutes=1), created_at=datetime.now(UTC) - timedelta(minutes=2))
        result = orchestrator.execute(bad, PortfolioState(equity=1000.0))
        self.assertEqual(result.status, ProposalStatus.REJECTED_PRE_EXECUTION)


if __name__ == "__main__":
    unittest.main()
