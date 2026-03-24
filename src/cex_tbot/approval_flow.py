from __future__ import annotations

from dataclasses import dataclass, replace
import re

from cex_tbot.decision_contracts.models import ApprovalDecision, TradeProposal
from cex_tbot.enums import ApprovalAction, ProposalStatus
from cex_tbot.proposal_store import InMemoryProposalStore


APPROVE_RE = re.compile(r"^APPROVE\s+(?P<proposal_id>\S+)$")
REJECT_RE = re.compile(r"^REJECT\s+(?P<proposal_id>\S+)$")
MODIFY_RE = re.compile(r"^MODIFY\s+(?P<proposal_id>\S+):\s+(?P<changes>.+)$")


@dataclass(frozen=True)
class ParsedApprovalCommand:
    action: ApprovalAction
    proposal_id: str
    changes: str | None = None


@dataclass(frozen=True)
class ApprovalParseResult:
    is_valid: bool
    command: ParsedApprovalCommand | None = None
    reason: str = ""


@dataclass(frozen=True)
class ApprovalApplyResult:
    decision: ApprovalDecision
    resulting_status: ProposalStatus | None
    proposal_id: str
    superseded_proposal_id: str | None = None


class ApprovalFlow:
    def __init__(self, store: InMemoryProposalStore | None = None) -> None:
        self.store = store or InMemoryProposalStore()

    def parse_command(self, raw_text: str) -> ApprovalParseResult:
        text = raw_text.strip()
        if match := APPROVE_RE.fullmatch(text):
            return ApprovalParseResult(True, ParsedApprovalCommand(ApprovalAction.APPROVE, match.group("proposal_id")))
        if match := REJECT_RE.fullmatch(text):
            return ApprovalParseResult(True, ParsedApprovalCommand(ApprovalAction.REJECT, match.group("proposal_id")))
        if match := MODIFY_RE.fullmatch(text):
            return ApprovalParseResult(True, ParsedApprovalCommand(ApprovalAction.MODIFY, match.group("proposal_id"), match.group("changes")))
        return ApprovalParseResult(False, reason="command does not match strict grammar")

    def record_decision(self, actor: str, raw_text: str) -> ApprovalDecision:
        parsed = self.parse_command(raw_text)
        if not parsed.is_valid or parsed.command is None:
            return ApprovalDecision(
                proposal_id="UNKNOWN",
                actor=actor,
                action="INVALID",
                raw_command=raw_text,
                parsed_command="",
                is_strict_match=False,
                reason_text=parsed.reason,
            )
        parsed_command = f"{parsed.command.action.value} {parsed.command.proposal_id}"
        if parsed.command.changes is not None:
            parsed_command = f"{parsed_command}: {parsed.command.changes}"
        return ApprovalDecision(
            proposal_id=parsed.command.proposal_id,
            actor=actor,
            action=parsed.command.action.value,
            raw_command=raw_text,
            parsed_command=parsed_command,
            is_strict_match=True,
        )

    def next_status(self, current_status: ProposalStatus, decision: ApprovalDecision) -> ProposalStatus:
        if not decision.is_strict_match:
            return current_status
        if decision.action == ApprovalAction.APPROVE.value:
            return ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK
        if decision.action == ApprovalAction.REJECT.value:
            return ProposalStatus.REJECTED_BY_HUMAN
        if decision.action == ApprovalAction.MODIFY.value:
            return ProposalStatus.MODIFY_REQUESTED
        return current_status

    def apply_command(self, actor: str, raw_text: str) -> ApprovalApplyResult:
        decision = self.record_decision(actor, raw_text)
        self.store.append_decision(decision)
        if not decision.is_strict_match or decision.proposal_id == "UNKNOWN":
            return ApprovalApplyResult(decision, None, decision.proposal_id)

        proposal = self.store.require(decision.proposal_id)
        next_status = self.next_status(proposal.status, decision)
        updated = self.store.update_status(proposal.proposal_id, next_status)
        return ApprovalApplyResult(decision, updated.status, updated.proposal_id)

    def revalidate_modified_proposal(
        self,
        actor: str,
        raw_text: str,
        replacement: TradeProposal,
    ) -> ApprovalApplyResult:
        decision = self.record_decision(actor, raw_text)
        self.store.append_decision(decision)
        if not decision.is_strict_match or decision.action != ApprovalAction.MODIFY.value:
            return ApprovalApplyResult(decision, None, decision.proposal_id)
        previous = self.store.require(decision.proposal_id)
        replacement = replace(replacement, status=ProposalStatus.PENDING_APPROVAL, proposal_version=previous.proposal_version + 1)
        self.store.supersede_and_add(previous.proposal_id, replacement)
        return ApprovalApplyResult(
            decision=decision,
            resulting_status=replacement.status,
            proposal_id=replacement.proposal_id,
            superseded_proposal_id=previous.proposal_id,
        )
