from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot import PortfolioState, RiskEngine
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalReasonCode, TradeDirection


class RiskEngineConsistencyTests(unittest.TestCase):
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
            stop_loss=99.5,
            take_profit_1=101.0,
            take_profit_2=102.0,
            risk_percent=0.5,
            risk_usd=50.0,
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

    def test_rejects_risk_math_mismatch(self) -> None:
        engine = RiskEngine(BotConfig())
        proposal = self._proposal(risk_usd=5.0, risk_percent=2.0)
        result = engine.evaluate(proposal, PortfolioState(equity=1000.0))
        self.assertFalse(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.RISK_CALCULATION_MISMATCH)

    def test_rejects_averaging_down_pattern_for_long(self) -> None:
        engine = RiskEngine(BotConfig())
        now = datetime.now(UTC)
        proposal = self._proposal(
            entry_split=[
                EntrySplitLeg(1, 100.0, 50.0, 0.5, now + timedelta(minutes=15)),
                EntrySplitLeg(2, 99.0, 50.0, 0.5, now + timedelta(minutes=15)),
            ],
            stop_loss=98.0,
            risk_usd=5.0,
            risk_percent=0.5,
        )
        result = engine.check_proposal_consistency(proposal, equity=1000.0)
        self.assertEqual(result, ProposalReasonCode.AVERAGING_DOWN_FORBIDDEN)

    def test_allows_scale_in_higher_for_short(self) -> None:
        engine = RiskEngine(BotConfig())
        now = datetime.now(UTC)
        proposal = self._proposal(
            direction=TradeDirection.SHORT,
            entry_zone_min=100.0,
            entry_zone_max=102.0,
            entry_split=[
                EntrySplitLeg(1, 100.0, 50.0, 0.5, now + timedelta(minutes=15)),
                EntrySplitLeg(2, 101.0, 50.0, 0.5, now + timedelta(minutes=15)),
            ],
            stop_loss=103.0,
            take_profit_1=98.0,
            take_profit_2=96.0,
            risk_usd=5.0,
            risk_percent=0.5,
        )
        result = engine.check_proposal_consistency(proposal, equity=1000.0)
        self.assertIsNone(result)

    def test_rejects_averaging_down_pattern_for_short(self) -> None:
        engine = RiskEngine(BotConfig())
        now = datetime.now(UTC)
        proposal = self._proposal(
            direction=TradeDirection.SHORT,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[
                EntrySplitLeg(1, 100.0, 50.0, 0.5, now + timedelta(minutes=15)),
                EntrySplitLeg(2, 99.0, 50.0, 0.5, now + timedelta(minutes=15)),
            ],
            stop_loss=101.0,
            take_profit_1=98.0,
            take_profit_2=97.0,
            risk_usd=5.0,
            risk_percent=0.5,
        )
        result = engine.check_proposal_consistency(proposal, equity=1000.0)
        self.assertEqual(result, ProposalReasonCode.AVERAGING_DOWN_FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
