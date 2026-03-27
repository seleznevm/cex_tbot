from __future__ import annotations

from dataclasses import dataclass, field

from cex_tbot.bot_adapter import BotReply
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.write_safety import WriteActionArmState


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


_WRITE_COMMANDS = {
    "/demo_place_test_order",
    "/demo_cancel_order",
    "/demo_smoke",
}


class TransportCommandBridge:
    def __init__(
        self,
        dispatcher: BotCommandDispatcher,
        *,
        sender_policy: SenderPolicy | None = None,
        write_sender_policy: SenderPolicy | None = None,
        arm_state: WriteActionArmState | None = None,
        arm_ttl_seconds: int = 120,
    ) -> None:
        self.dispatcher = dispatcher
        self.sender_policy = sender_policy or SenderPolicy()
        self.write_sender_policy = write_sender_policy or self.sender_policy
        self.arm_state = arm_state or WriteActionArmState()
        self.arm_ttl_seconds = arm_ttl_seconds

    def handle_message(self, message: TransportMessage) -> BotReply:
        if not self.sender_policy.is_allowed(message.sender_id):
            return BotReply("Unauthorized operator sender.")
        stripped = message.text.strip()
        if not stripped.startswith("/"):
            return BotReply("Ignored non-command message.")
        if stripped.startswith('/demo_arm'):
            expires_at = self.arm_state.arm(message.sender_id, ttl_seconds=self.arm_ttl_seconds)
            return BotReply(f"Demo write actions armed until {expires_at.isoformat()}")
        command = stripped.split()[0]
        if command in _WRITE_COMMANDS:
            if not self.write_sender_policy.is_allowed(message.sender_id):
                return BotReply("Unauthorized writer sender.")
            if not self.arm_state.is_armed_for(message.sender_id):
                return BotReply("Demo write action rejected: send /demo_arm first.")
            reply = self.dispatcher.dispatch(stripped)
            self.arm_state.clear()
            return reply
        return self.dispatcher.dispatch(stripped)
