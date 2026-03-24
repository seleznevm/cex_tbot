from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot import PendingRiskBook, PortfolioState, RiskEngine
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalReasonCode, TradeDirection


class RiskEngineTests(unittest.TestCase):
    def _proposal(self, risk_percent: float = 0.5) -> TradeProposal:
        now = datetime.now(UTC)
        return TradeProposal(
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
            risk_percent=risk_percent,
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

    def test_risk_passes_when_under_limits(self) -> None:
        engine = RiskEngine(BotConfig())
        result = engine.evaluate(self._proposal(), PortfolioState(equity=1000.0))
        self.assertTrue(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.RISK_BUDGET_RESERVED)

    def test_risk_rejects_on_max_positions(self) -> None:
        engine = RiskEngine(BotConfig(max_open_positions=2))
        result = engine.evaluate(self._proposal(), PortfolioState(equity=1000.0, open_positions_count=2))
        self.assertFalse(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.MAX_OPEN_POSITIONS_REACHED)

    def test_pending_reservation_blocks_excess_risk(self) -> None:
        book = PendingRiskBook()
        engine = RiskEngine(BotConfig(max_aggregate_open_risk_percent=1.0), pending_risk_book=book)
        first = self._proposal(risk_percent=0.6)
        second = self._proposal(risk_percent=0.5)
        engine.reserve_pending_risk(first)
        result = engine.evaluate(second, PortfolioState(equity=1000.0))
        self.assertFalse(result.is_approved)
        self.assertEqual(result.reason_code, ProposalReasonCode.TOTAL_OPEN_RISK_EXCEEDED)


if __name__ == "__main__":
    unittest.main()
