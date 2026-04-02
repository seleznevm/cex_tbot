from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.proposal_emitter import TopicProposalEmitter
from cex_tbot.transport_bridge import TransportCommandBridge
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.backend_service import TradingBackendService
from cex_tbot.session_store import TradeSessionStore


class ProposalEmitterTests(unittest.TestCase):
    def test_emitters_target_same_topic(self) -> None:
        wrapper = OpenClawTopicWrapper(
            TransportCommandBridge(BotCommandDispatcher(BotCommandAdapter(TradingBackendService.from_session(TradeSessionStore())))),
            default_chat_id="telegram:-1003832858724",
            default_thread_id="7",
        )
        emitter = TopicProposalEmitter(wrapper)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_emit_1",
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
            status=ProposalStatus.PENDING_APPROVAL,
        )
        no_trade = NoTradeDecision(
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            symbol="BTC_USDT",
            timeframe="15m",
            confidence_score=0.31,
            reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
            reason_text="too weak",
            market_context_id="ctx_nt_1",
            liquidity_check="ok",
            data_freshness_ms=100,
        )

        approval = emitter.emit_proposal_request(proposal)
        rejected = emitter.emit_rejection_notice(proposal, reason="manual reject")
        no_trade_msg = emitter.emit_no_trade_notice(no_trade)

        self.assertEqual(approval.chat_id, "telegram:-1003832858724")
        self.assertEqual(approval.thread_id, "7")
        self.assertIn("/trade_approve proposal_emit_1", approval.text)
        self.assertIn("Trade proposal rejected", rejected.text)
        self.assertIn("No-trade notice", no_trade_msg.text)
        self.assertEqual(no_trade_msg.thread_id, "7")


if __name__ == "__main__":
    unittest.main()
