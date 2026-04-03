from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.transport_bridge import TransportCommandBridge, TransportMessage


@dataclass(frozen=True)
class TelegramRunnerPolicy:
    allowed_chat_ids: frozenset[str] = field(default_factory=frozenset)
    allowed_thread_ids: frozenset[str] = field(default_factory=frozenset)


class TelegramTransportRunner:
    def __init__(
        self,
        bridge: TransportCommandBridge,
        *,
        bot_token: str,
        policy: TelegramRunnerPolicy | None = None,
        proposal_parser: Callable[[str], TradeProposal] | None = None,
        proposal_submitter: Callable[[TradeProposal, str, str | None], str] | None = None,
    ) -> None:
        self.bridge = bridge
        self.bot_token = bot_token.strip()
        self.policy = policy or TelegramRunnerPolicy()
        self.proposal_parser = proposal_parser
        self.proposal_submitter = proposal_submitter

    def _is_authorized_sender(self, sender_id: str) -> bool:
        sender_policy = getattr(self.bridge, "sender_policy", None)
        if sender_policy is None:
            return True
        return bool(sender_policy.is_allowed(sender_id))

    async def handle_update(self, update: Any, _context: Any) -> None:
        message = getattr(update, "effective_message", None)
        chat = getattr(update, "effective_chat", None)
        user = getattr(update, "effective_user", None)
        if message is None or chat is None or user is None:
            return
        if getattr(chat, "type", "") not in {"group", "supergroup"}:
            return
        chat_id = str(getattr(chat, "id", ""))
        thread_id = getattr(message, "message_thread_id", None)
        if self.policy.allowed_chat_ids and chat_id not in self.policy.allowed_chat_ids:
            return
        if self.policy.allowed_thread_ids and str(thread_id or "") not in self.policy.allowed_thread_ids:
            return
        text = (getattr(message, "text", None) or "").strip()
        if not text:
            return
        sender_id = str(getattr(user, "id", ""))
        if text.startswith("{") and self.proposal_parser is not None and self.proposal_submitter is not None:
            if not self._is_authorized_sender(sender_id):
                await message.reply_text("Unauthorized operator sender.")
                return
            try:
                proposal = self.proposal_parser(text)
            except ValueError as exc:
                await message.reply_text(f"Invalid proposal JSON: {exc}")
                return
            reply_text = self.proposal_submitter(proposal, f"telegram:{chat_id}", str(thread_id) if thread_id is not None else None)
            kwargs: dict[str, object] = {}
            if thread_id is not None:
                kwargs["message_thread_id"] = int(thread_id)
            await message.reply_text(reply_text, **kwargs)
            return
        reply = self.bridge.handle_message(
            TransportMessage(
                sender_id=sender_id,
                sender_name=getattr(user, "username", None),
                text=text,
                channel=str(getattr(chat, "type", "") or ""),
                chat_id=f"telegram:{chat_id}",
            )
        )
        kwargs: dict[str, object] = {}
        if thread_id is not None:
            kwargs["message_thread_id"] = int(thread_id)
        await message.reply_text(reply.text, parse_mode=reply.parse_mode, **kwargs)

    def run_polling(self) -> None:
        if not self.bot_token:
            raise ValueError("Telegram bot token is required.")
        try:
            from telegram.ext import ApplicationBuilder, MessageHandler, filters
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "python-telegram-bot>=20 is required for tg runner. Install it and retry."
            ) from exc
        app = ApplicationBuilder().token(self.bot_token).build()
        app.add_handler(MessageHandler(filters.TEXT, self.handle_update))
        app.run_polling()
