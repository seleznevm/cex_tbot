from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import TradeProposal
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

    def emit_conservative_alert(self, assessment: ConservativePolicyAssessment) -> OpenClawOutboundMessage:
        emitter = TopicProposalEmitter(self.wrapper)
        return emitter.emit_conservative_alert(assessment)
