from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.openclaw_wrapper import OpenClawOutboundMessage, OpenClawTopicWrapper


@dataclass(frozen=True)
class TopicProposalEmitter:
    wrapper: OpenClawTopicWrapper

    def emit_proposal_request(self, proposal: TradeProposal) -> OpenClawOutboundMessage:
        return self.wrapper.render_approval_request(proposal)

    def emit_no_trade_notice(self, decision: NoTradeDecision) -> OpenClawOutboundMessage:
        lines = [
            "No-trade notice",
            f"- symbol={decision.symbol}",
            f"- timeframe={decision.timeframe}",
            f"- strategy={decision.strategy_id}",
            f"- confidence={decision.confidence_score}",
            f"- reason={decision.reason_code.value}",
            f"- detail={decision.reason_text}",
        ]
        return OpenClawOutboundMessage(
            text="\n".join(lines),
            chat_id=self.wrapper.default_chat_id,
            thread_id=self.wrapper.default_thread_id,
        )

    def emit_rejection_notice(self, proposal: TradeProposal, *, reason: str) -> OpenClawOutboundMessage:
        lines = [
            "Trade proposal rejected",
            f"- proposal_id={proposal.proposal_id}",
            f"- symbol={proposal.symbol}",
            f"- side={proposal.direction.value}",
            f"- timeframe={proposal.timeframe}",
            f"- reason={reason}",
        ]
        return OpenClawOutboundMessage(
            text="\n".join(lines),
            chat_id=self.wrapper.default_chat_id,
            thread_id=self.wrapper.default_thread_id,
        )
