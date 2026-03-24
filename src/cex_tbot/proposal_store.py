from __future__ import annotations

from dataclasses import replace

from cex_tbot.decision_contracts.models import ApprovalDecision, TradeProposal
from cex_tbot.enums import ProposalStatus


class InMemoryProposalStore:
    def __init__(self) -> None:
        self._proposals: dict[str, TradeProposal] = {}
        self._history: dict[str, list[ApprovalDecision]] = {}

    def upsert(self, proposal: TradeProposal) -> TradeProposal:
        self._proposals[proposal.proposal_id] = proposal
        self._history.setdefault(proposal.proposal_id, [])
        return proposal

    def get(self, proposal_id: str) -> TradeProposal | None:
        return self._proposals.get(proposal_id)

    def require(self, proposal_id: str) -> TradeProposal:
        proposal = self.get(proposal_id)
        if proposal is None:
            raise KeyError(f"unknown proposal_id={proposal_id}")
        return proposal

    def update_status(self, proposal_id: str, status: ProposalStatus) -> TradeProposal:
        proposal = self.require(proposal_id)
        updated = replace(proposal, status=status)
        self._proposals[proposal_id] = updated
        return updated

    def supersede_and_add(self, old_proposal_id: str, new_proposal: TradeProposal) -> tuple[TradeProposal, TradeProposal]:
        previous = self.update_status(old_proposal_id, ProposalStatus.SUPERSEDED)
        self.upsert(new_proposal)
        return previous, new_proposal

    def append_decision(self, decision: ApprovalDecision) -> None:
        self._history.setdefault(decision.proposal_id, []).append(decision)

    def history(self, proposal_id: str) -> list[ApprovalDecision]:
        return list(self._history.get(proposal_id, []))
