from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal


class ContractTests(unittest.TestCase):
    def test_trade_proposal_skeleton(self) -> None:
        now = datetime.now(UTC)
        proposal = TradeProposal(
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
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
            expires_at=now + timedelta(minutes=15),
        )
        self.assertEqual(proposal.symbol, "BTC_USDT")


if __name__ == "__main__":
    unittest.main()
