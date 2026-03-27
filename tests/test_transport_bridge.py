from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge, TransportMessage


class TransportBridgeTests(unittest.TestCase):
    def test_bridge_blocks_unauthorized_sender(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(service)),
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
        )

        reply = bridge.handle_message(TransportMessage(sender_id="999", text="/status"))

        self.assertIn("Unauthorized", reply.text)

    def test_bridge_ignores_non_command_text(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(BotCommandDispatcher(BotCommandAdapter(service)))

        reply = bridge.handle_message(TransportMessage(sender_id="125619710", text="hello"))

        self.assertIn("Ignored non-command", reply.text)

    def test_bridge_dispatches_operator_command(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig())),
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
        )
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_bridge",
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
        service.submit_proposal(proposal)

        reply = bridge.handle_message(TransportMessage(sender_id="125619710", text="/detail proposal_bridge"))

        self.assertIn("Trade detail", reply.text)

    def test_bridge_requires_arm_for_demo_write_actions(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig(execution_mode='gate_demo', gate_demo_api='https://api-testnet.gateapi.io/api/v4'))),
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
            write_sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
        )

        rejected = bridge.handle_message(TransportMessage(sender_id="125619710", text="/demo_place_test_order BTC_USDT buy"))
        armed = bridge.handle_message(TransportMessage(sender_id="125619710", text="/demo_arm"))

        self.assertIn("send /demo_arm first", rejected.text)
        self.assertIn("armed until", armed.text)

    def test_bridge_blocks_unauthorized_writer_sender(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig(execution_mode='gate_demo', gate_demo_api='https://api-testnet.gateapi.io/api/v4'))),
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710", "999"}), allow_empty_policy=False),
            write_sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
        )

        reply = bridge.handle_message(TransportMessage(sender_id="999", text="/demo_place_test_order BTC_USDT buy"))

        self.assertIn("Unauthorized writer", reply.text)


if __name__ == "__main__":
    unittest.main()
