from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.topic_producer import TopicProposalProducer


class TopicProposalProducerTests(unittest.TestCase):
    def test_submit_and_emit_persists_and_renders_same_topic_message(self) -> None:
        backend = TradingBackendService.from_session(TradeSessionStore())
        wrapper = OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7")
        producer = TopicProposalProducer(backend, wrapper)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_topic_live_1",
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_live_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=98.5,
            take_profit_1=101.5,
            take_profit_2=103.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=10.0,
            confidence_score=0.79,
            thesis="clean reclaim after pullback",
            invalidity_condition="support fails",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.PENDING_APPROVAL,
        )

        outbound = producer.submit_and_emit(proposal)

        stored = backend.session.proposals.require("proposal_topic_live_1")
        self.assertEqual(stored.proposal_id, "proposal_topic_live_1")
        self.assertEqual(outbound.chat_id, "telegram:-1003832858724")
        self.assertEqual(outbound.thread_id, "7")
        self.assertIn("Trade approval request", outbound.text)
        self.assertIn("/trade_approve proposal_topic_live_1", outbound.text)
        self.assertIn("/modify proposal_topic_live_1", outbound.text)

    def test_submit_no_trade_and_emit_persists_and_renders_same_topic_message(self) -> None:
        backend = TradingBackendService.from_session(TradeSessionStore())
        wrapper = OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7")
        producer = TopicProposalProducer(backend, wrapper)
        decision = NoTradeDecision(
            decision_id="no_trade_topic_live_1",
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            symbol="BTC_USDT",
            timeframe="15m",
            confidence_score=0.42,
            reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
            reason_text="setup stayed below threshold",
            market_context_id="ctx_no_trade_live_1",
            liquidity_check="ok",
            data_freshness_ms=150,
        )

        outbound = producer.submit_no_trade_and_emit(decision)

        stored = backend.session.no_trades.list()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].decision_id, "no_trade_topic_live_1")
        self.assertEqual(outbound.chat_id, "telegram:-1003832858724")
        self.assertEqual(outbound.thread_id, "7")
        self.assertIn("No-trade notice", outbound.text)
        self.assertIn("reason=confidence_below_threshold", outbound.text)


if __name__ == "__main__":
    unittest.main()
