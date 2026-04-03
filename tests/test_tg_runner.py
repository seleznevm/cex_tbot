from __future__ import annotations

import asyncio
import unittest

from cex_tbot.bot_adapter import BotReply
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


if __name__ == "__main__":
    unittest.main()
