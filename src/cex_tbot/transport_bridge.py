from __future__ import annotations

from dataclasses import dataclass, field

from cex_tbot.bot_adapter import BotReply
from cex_tbot.bot_dispatcher import BotCommandDispatcher


@dataclass(frozen=True)
class TransportMessage:
    sender_id: str
    text: str
    sender_name: str | None = None
    channel: str | None = None
    chat_id: str | None = None


@dataclass(frozen=True)
class SenderPolicy:
    allowed_sender_ids: frozenset[str] = field(default_factory=frozenset)
    allow_empty_policy: bool = True

    def is_allowed(self, sender_id: str) -> bool:
        if not self.allowed_sender_ids:
            return self.allow_empty_policy
        return sender_id in self.allowed_sender_ids


class TransportCommandBridge:
    def __init__(self, dispatcher: BotCommandDispatcher, *, sender_policy: SenderPolicy | None = None) -> None:
        self.dispatcher = dispatcher
        self.sender_policy = sender_policy or SenderPolicy()

    def handle_message(self, message: TransportMessage) -> BotReply:
        if not self.sender_policy.is_allowed(message.sender_id):
            return BotReply("Unauthorized operator sender.")
        stripped = message.text.strip()
        if not stripped.startswith("/"):
            return BotReply("Ignored non-command message.")
        return self.dispatcher.dispatch(stripped)
