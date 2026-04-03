from __future__ import annotations

import asyncio
import json
import unittest
from datetime import UTC, datetime, timedelta

from cex_tbot.bot_adapter import BotReply
from cex_tbot.proposal_json_parser import JsonTradeProposalParser
from cex_tbot.tg_runner import TelegramRunnerPolicy, TelegramTransportRunner


class _BridgeStub:
    def __init__(self) -> None:
        self.messages = []

    def handle_message(self, message):
        self.messages.append(message)
        return BotReply("ok", parse_mode="Markdown")


class _MessageStub:
    def __init__(self, text: str, message_thread_id: int | None = None) -> None:
        self.text = text
        self.message_thread_id = message_thread_id
        self.replies: list[tuple[str, str | None, dict[str, object]]] = []

    async def reply_text(self, text: str, parse_mode: str | None = None, **kwargs):
        self.replies.append((text, parse_mode, kwargs))


class _Obj:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class TelegramTransportRunnerTests(unittest.TestCase):
    def _update(self, *, text: str, chat_id: int = -100, chat_type: str = "supergroup", user_id: int = 125, thread_id: int | None = 7):
        message = _MessageStub(text, message_thread_id=thread_id)
        return _Obj(
            effective_message=message,
            effective_chat=_Obj(id=chat_id, type=chat_type),
            effective_user=_Obj(id=user_id, username="tester"),
        ), message

    def test_runner_forwards_group_message_to_bridge(self) -> None:
        bridge = _BridgeStub()
        runner = TelegramTransportRunner(bridge, bot_token="token")
        update, message = self._update(text="/status")

        asyncio.run(runner.handle_update(update, None))

        self.assertEqual(len(bridge.messages), 1)
        self.assertEqual(bridge.messages[0].text, "/status")
        self.assertEqual(bridge.messages[0].chat_id, "telegram:-100")
        self.assertEqual(message.replies[0][0], "ok")
        self.assertEqual(message.replies[0][1], "Markdown")
        self.assertEqual(message.replies[0][2]["message_thread_id"], 7)

    def test_runner_ignores_non_group_chat(self) -> None:
        bridge = _BridgeStub()
        runner = TelegramTransportRunner(bridge, bot_token="token")
        update, message = self._update(text="/status", chat_type="private")

        asyncio.run(runner.handle_update(update, None))

        self.assertEqual(bridge.messages, [])
        self.assertEqual(message.replies, [])

    def test_runner_applies_chat_and_thread_policy(self) -> None:
        bridge = _BridgeStub()
        runner = TelegramTransportRunner(
            bridge,
            bot_token="token",
            policy=TelegramRunnerPolicy(
                allowed_chat_ids=frozenset({"-100"}),
                allowed_thread_ids=frozenset({"7"}),
            ),
        )
        update_ok, message_ok = self._update(text="/status", chat_id=-100, thread_id=7)
        update_blocked, message_blocked = self._update(text="/status", chat_id=-100, thread_id=9)

        asyncio.run(runner.handle_update(update_ok, None))
        asyncio.run(runner.handle_update(update_blocked, None))

        self.assertEqual(len(bridge.messages), 1)
        self.assertEqual(message_ok.replies[0][0], "ok")
        self.assertEqual(message_blocked.replies, [])

    def test_runner_parses_json_and_submits_proposal(self) -> None:
        bridge = _BridgeStub()
        parser = JsonTradeProposalParser(force_pending_approval=True)
        received: list[tuple[str, str | None, str]] = []

        def submitter(proposal, chat_id: str, thread_id: str | None) -> str:
            received.append((chat_id, thread_id, proposal.proposal_id))
            return "Trade approval request\n/trade_approve " + proposal.proposal_id

        now = datetime.now(UTC)
        payload = json.dumps(
            {
                "proposal_id": "proposal_json_1",
                "agent_name": "Luma",
                "strategy_id": "pullback",
                "strategy_version": "v1",
                "market_context_id": "ctx_1",
                "symbol": "BTC_USDT",
                "timeframe": "15m",
                "direction": "LONG",
                "entry_zone_min": 99.0,
                "entry_zone_max": 100.0,
                "entry_split": [
                    {
                        "leg_number": 1,
                        "planned_entry_price": 99.5,
                        "allocation_pct": 100.0,
                        "size_fraction": 1.0,
                        "valid_until": (now + timedelta(minutes=15)).isoformat(),
                    }
                ],
                "stop_loss": 98.0,
                "take_profit_1": 101.0,
                "take_profit_2": 102.0,
                "risk_percent": 0.5,
                "risk_usd": 5.0,
                "position_size": 1.0,
                "confidence_score": 0.8,
                "thesis": "json from tg",
                "invalidity_condition": "support breaks",
                "liquidity_check": "ok",
                "data_freshness_ms": 100,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=20)).isoformat(),
                "status": "PENDING_APPROVAL",
            }
        )
        runner = TelegramTransportRunner(
            bridge,
            bot_token="token",
            proposal_parser=parser.parse_text,
            proposal_submitter=submitter,
        )
        update, message = self._update(text=payload)

        asyncio.run(runner.handle_update(update, None))

        self.assertEqual(len(bridge.messages), 0)
        self.assertEqual(received, [("telegram:-100", "7", "proposal_json_1")])
        self.assertIn("/trade_approve proposal_json_1", message.replies[0][0])

    def test_runner_rejects_unauthorized_json_submission(self) -> None:
        bridge = _BridgeStub()
        bridge.sender_policy = type("Policy", (), {"is_allowed": lambda self, sender_id: sender_id == "125"})()
        parser = JsonTradeProposalParser(force_pending_approval=True)
        now = datetime.now(UTC)
        payload = json.dumps(
            {
                "proposal_id": "proposal_json_2",
                "agent_name": "Luma",
                "strategy_id": "pullback",
                "strategy_version": "v1",
                "market_context_id": "ctx_2",
                "symbol": "BTC_USDT",
                "timeframe": "15m",
                "direction": "LONG",
                "entry_zone_min": 99.0,
                "entry_zone_max": 100.0,
                "entry_split": [
                    {
                        "leg_number": 1,
                        "planned_entry_price": 99.5,
                        "allocation_pct": 100.0,
                        "size_fraction": 1.0,
                        "valid_until": (now + timedelta(minutes=15)).isoformat(),
                    }
                ],
                "stop_loss": 98.0,
                "take_profit_1": 101.0,
                "take_profit_2": 102.0,
                "risk_percent": 0.5,
                "risk_usd": 5.0,
                "position_size": 1.0,
                "confidence_score": 0.8,
                "thesis": "json from tg",
                "invalidity_condition": "support breaks",
                "liquidity_check": "ok",
                "data_freshness_ms": 100,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=20)).isoformat(),
                "status": "PENDING_APPROVAL",
            }
        )
        runner = TelegramTransportRunner(
            bridge,
            bot_token="token",
            proposal_parser=parser.parse_text,
            proposal_submitter=lambda proposal, chat_id, thread_id: proposal.proposal_id,
        )
        update, message = self._update(text=payload, user_id=999)

        asyncio.run(runner.handle_update(update, None))

        self.assertEqual(bridge.messages, [])
        self.assertEqual(message.replies[0][0], "Unauthorized operator sender.")


if __name__ == "__main__":
    unittest.main()
