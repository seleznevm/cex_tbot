from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.review_cards import ReviewCardBuilder


class ReviewCardTests(unittest.TestCase):
    def test_builds_review_card(self) -> None:
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
        card = ReviewCardBuilder().build(proposal)
        self.assertEqual(card.proposal_id, "proposal_1")
        self.assertIn("leg1@100.0", card.entry_summary)


if __name__ == "__main__":
    unittest.main()
