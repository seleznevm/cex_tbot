from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.openclaw_wrapper import OpenClawOutboundMessage, OpenClawTopicWrapper
from cex_tbot.execution.policy import ConservativePolicyAssessment
from cex_tbot.proposal_emitter import TopicProposalEmitter
from cex_tbot.proposal_workflow_glue import ProposalWorkflowGlue


@dataclass(frozen=True)
class TopicProposalProducer:
    backend: TradingBackendService
    wrapper: OpenClawTopicWrapper

    def submit_and_emit(self, proposal: TradeProposal) -> OpenClawOutboundMessage:
        glue = ProposalWorkflowGlue(self.backend, TopicProposalEmitter(self.wrapper))
        return glue.submit_and_emit_proposal(proposal)

    def submit_no_trade_and_emit(self, decision: NoTradeDecision) -> OpenClawOutboundMessage:
        glue = ProposalWorkflowGlue(self.backend, TopicProposalEmitter(self.wrapper))
        outbound = glue.submit_and_emit_no_trade(decision)
        return self._normalize_no_trade_reason(outbound, decision.reason_code.value)

    def emit_conservative_alert(self, assessment: ConservativePolicyAssessment) -> OpenClawOutboundMessage:
        emitter = TopicProposalEmitter(self.wrapper)
        return emitter.emit_conservative_alert(assessment)

    @staticmethod
    def _normalize_no_trade_reason(outbound: OpenClawOutboundMessage, reason_code: str) -> OpenClawOutboundMessage:
        lower_reason = reason_code.lower()
        normalized_lines: Iterable[str] = (
            line.replace(f"reason={reason_code}", f"reason={lower_reason}") for line in outbound.text.splitlines()
        )
        return OpenClawOutboundMessage(
            text="\n".join(normalized_lines),
            chat_id=outbound.chat_id,
            thread_id=outbound.thread_id,
        )
