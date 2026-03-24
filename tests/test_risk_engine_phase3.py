from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot import PortfolioState, RiskEngine
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalReasonCode, TradeDirection


class RiskEnginePhase3Tests(unittest.TestCase):
    def _proposal(self, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        payload = dict(
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=15))],
            stop_loss=97.0,
            take_profit_1=102.0,
            take_profit_2=104.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=100.0,
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

    def test_pre_execution_rejects_expired_proposal(self) -> None:
        engine = RiskEngine(BotConfig())
        now = datetime.now(UTC)
        proposal = self._proposal(expires_at=now - timedelta(seconds=1), created_at=now - timedelta(minutes=5))
        result = engine.pre_execution_check(proposal, PortfolioState(equity=1000.0), now=now)
        self.assertFalse(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.PROPOSAL_EXPIRED)

    def test_pre_execution_rejects_invalid_freshness(self) -> None:
        engine = RiskEngine(BotConfig())
        now = datetime.now(UTC)
        proposal = self._proposal(data_freshness_ms=-1)
        result = engine.pre_execution_check(proposal, PortfolioState(equity=1000.0), now=now)
        self.assertFalse(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.STALE_MARKET_DATA)

    def test_rejects_single_trade_above_portfolio_cap(self) -> None:
        engine = RiskEngine(BotConfig(max_aggregate_open_risk_percent=1.0))
        result = engine.evaluate(self._proposal(risk_percent=1.2), PortfolioState(equity=1000.0))
        self.assertFalse(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.RISK_CALCULATION_MISMATCH)


if __name__ == "__main__":
    unittest.main()
