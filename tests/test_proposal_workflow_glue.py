from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.proposal_emitter import TopicProposalEmitter
from cex_tbot.proposal_workflow_glue import ProposalWorkflowGlue
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.transport_bridge import TransportCommandBridge
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.bot_adapter import BotCommandAdapter


class ProposalWorkflowGlueTests(unittest.TestCase):
    def test_submit_and_emit_proposal_and_no_trade(self) -> None:
        backend = TradingBackendService.from_session(TradeSessionStore())
        wrapper = OpenClawTopicWrapper(
            TransportCommandBridge(BotCommandDispatcher(BotCommandAdapter(backend))),
            default_chat_id="telegram:-1003832858724",
            default_thread_id="7",
        )
        glue = ProposalWorkflowGlue(backend=backend, emitter=TopicProposalEmitter(wrapper))
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_glue_1",
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

        proposal_msg = glue.submit_and_emit_proposal(proposal)
        no_trade_msg = glue.submit_and_emit_no_trade(no_trade)
        reject_msg = glue.emit_rejection(proposal, reason="manual reject")

        self.assertEqual(backend.session.proposals.require("proposal_glue_1").proposal_id, "proposal_glue_1")
        self.assertEqual(len(backend.session.no_trades.list()), 1)
        self.assertIn("Trade approval request", proposal_msg.text)
        self.assertIn("No-trade notice", no_trade_msg.text)
        self.assertIn("manual reject", reject_msg.text)
        self.assertEqual(proposal_msg.thread_id, "7")


if __name__ == "__main__":
    unittest.main()
