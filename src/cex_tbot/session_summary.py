from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.session_store import TradeSessionStore


@dataclass(frozen=True)
class SessionSummary:
    total_proposals: int
    executed_proposals: int
    rejected_proposals: int
    approval_decisions: int
    execution_events: int
    state_snapshots: int
    operator_commands: int
    proposal_status_breakdown: dict[str, int]

    def to_text(self) -> str:
        lines = [
            "Session Summary",
            f"Total proposals: {self.total_proposals}",
            f"Executed proposals: {self.executed_proposals}",
            f"Rejected proposals: {self.rejected_proposals}",
            f"Approval decisions: {self.approval_decisions}",
            f"Execution events: {self.execution_events}",
            f"State snapshots: {self.state_snapshots}",
            f"Operator commands: {self.operator_commands}",
            "Status breakdown:",
        ]
        for status, count in sorted(self.proposal_status_breakdown.items()):
            lines.append(f"- {status}: {count}")
        return "\n".join(lines)


class SessionSummaryBuilder:
    def build(self, session: TradeSessionStore) -> SessionSummary:
        proposals = list(session.proposals._proposals.values())
        status_breakdown: dict[str, int] = {}
        for proposal in proposals:
            status_breakdown[proposal.status.value] = status_breakdown.get(proposal.status.value, 0) + 1
        decisions = sum(len(session.proposals.history(proposal.proposal_id)) for proposal in proposals)
        executed = sum(1 for proposal in proposals if proposal.status.value == "EXECUTED")
        rejected = sum(1 for proposal in proposals if "REJECTED" in proposal.status.value)
        return SessionSummary(
            total_proposals=len(proposals),
            executed_proposals=executed,
            rejected_proposals=rejected,
            approval_decisions=decisions,
            execution_events=len(session.execution_journal.list_events()),
            state_snapshots=sum(len(session.execution_state.list_snapshots(proposal.proposal_id)) for proposal in proposals),
            operator_commands=len(session.operator_transcript.list_entries()),
            proposal_status_breakdown=status_breakdown,
        )
