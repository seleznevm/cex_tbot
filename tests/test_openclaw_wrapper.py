from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.openclaw_wrapper import OpenClawInboundMessage, OpenClawTopicWrapper
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge


class OpenClawWrapperTests(unittest.TestCase):
    def test_handle_inbound_routes_command_to_same_topic(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig())),
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
        )
        wrapper = OpenClawTopicWrapper(bridge, default_chat_id="telegram:-100", default_thread_id="7")

        outbound = wrapper.handle_inbound(
            OpenClawInboundMessage(
                sender_id="125619710",
                text="/status",
                chat_id="telegram:-100",
                thread_id="7",
            )
        )

        self.assertIn("Session Summary", outbound.text)
        self.assertEqual(outbound.chat_id, "telegram:-100")
        self.assertEqual(outbound.thread_id, "7")

    def test_render_approval_request_targets_same_topic(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig())))
        wrapper = OpenClawTopicWrapper(bridge, default_chat_id="telegram:-100", default_thread_id="7")
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_topic_1",
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

        outbound = wrapper.render_approval_request(proposal)

        self.assertIn("Trade approval request", outbound.text)
        self.assertIn("BTC_USDT LONG | 15m", outbound.text)
        self.assertIn("proposal_id=proposal_topic_1", outbound.text)
        self.assertIn("/trade_approve proposal_topic_1", outbound.text)
        self.assertEqual(outbound.chat_id, "telegram:-100")
        self.assertEqual(outbound.thread_id, "7")
    def test_handle_inbound_without_bridge_returns_explicit_error(self) -> None:
        wrapper = OpenClawTopicWrapper(None, default_chat_id="telegram:-100", default_thread_id="7")
        outbound = wrapper.handle_inbound(
            OpenClawInboundMessage(
                sender_id="125619710",
                text="/trade_status",
                chat_id="telegram:-100",
                thread_id="7",
            )
        )
        self.assertIn("Topic bridge unavailable", outbound.text)
        self.assertEqual(outbound.thread_id, "7")


if __name__ == "__main__":
    unittest.main()
