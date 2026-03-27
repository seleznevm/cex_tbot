from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.openclaw_wrapper import OpenClawOutboundMessage
from cex_tbot.proposal_emitter import TopicProposalEmitter


@dataclass(frozen=True)
class ProposalWorkflowGlue:
    backend: TradingBackendService
    emitter: TopicProposalEmitter

    def submit_and_emit_proposal(self, proposal: TradeProposal) -> OpenClawOutboundMessage:
        self.backend.submit_proposal(proposal)
        return self.emitter.emit_proposal_request(proposal)

    def submit_and_emit_no_trade(self, decision: NoTradeDecision) -> OpenClawOutboundMessage:
        self.backend.submit_no_trade_decision(decision)
        return self.emitter.emit_no_trade_notice(decision)

    def emit_rejection(self, proposal: TradeProposal, *, reason: str) -> OpenClawOutboundMessage:
        return self.emitter.emit_rejection_notice(proposal, reason=reason)
