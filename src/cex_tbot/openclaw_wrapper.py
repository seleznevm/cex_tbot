from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.bot_adapter import BotReply
from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.transport_bridge import TransportCommandBridge, TransportMessage


@dataclass(frozen=True)
class OpenClawInboundMessage:
    sender_id: str
    text: str
    sender_name: str | None = None
    channel: str | None = None
    chat_id: str | None = None
    thread_id: str | None = None


@dataclass(frozen=True)
class OpenClawOutboundMessage:
    text: str
    chat_id: str | None = None
    thread_id: str | None = None


class OpenClawTopicWrapper:
    def __init__(
        self,
        bridge: TransportCommandBridge | None,
        *,
        default_chat_id: str | None = None,
        default_thread_id: str | None = None,
    ) -> None:
        self.bridge = bridge
        self.default_chat_id = default_chat_id
        self.default_thread_id = default_thread_id

    def handle_inbound(self, inbound: OpenClawInboundMessage) -> OpenClawOutboundMessage:
        if self.bridge is None:
            return OpenClawOutboundMessage(
                text="Topic bridge unavailable: no transport bridge configured.",
                chat_id=inbound.chat_id or self.default_chat_id,
                thread_id=inbound.thread_id or self.default_thread_id,
            )
        reply = self.bridge.handle_message(
            TransportMessage(
                sender_id=inbound.sender_id,
                text=inbound.text,
                sender_name=inbound.sender_name,
                channel=inbound.channel,
                chat_id=inbound.chat_id,
            )
        )
        return OpenClawOutboundMessage(
            text=reply.text,
            chat_id=inbound.chat_id or self.default_chat_id,
            thread_id=inbound.thread_id or self.default_thread_id,
        )

    def render_approval_request(
        self,
        proposal: TradeProposal,
        *,
        chat_id: str | None = None,
        thread_id: str | None = None,
    ) -> OpenClawOutboundMessage:
        lines = [
            "Trade approval request",
            f"{proposal.symbol} {proposal.direction.value} | {proposal.timeframe}",
            f"proposal_id={proposal.proposal_id}",
            f"entry {proposal.entry_zone_min}..{proposal.entry_zone_max} | sl {proposal.stop_loss} | tp1 {proposal.take_profit_1} | tp2 {proposal.take_profit_2}",
            f"confidence {proposal.confidence_score} | risk {proposal.risk_percent}%",
            f"thesis: {proposal.thesis}",
            f"/trade_approve {proposal.proposal_id}",
            f"/trade_reject {proposal.proposal_id}",
            f"/modify {proposal.proposal_id} stop_loss=<value>, take_profit_1=<value>, take_profit_2=<value>, thesis=<text>",
            f"/trade_report {proposal.proposal_id}",
        ]
        return OpenClawOutboundMessage(
            text="\n".join(lines),
            chat_id=chat_id or self.default_chat_id,
            thread_id=thread_id or self.default_thread_id,
        )
