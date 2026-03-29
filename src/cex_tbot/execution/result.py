from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.enums import ProposalStatus
from cex_tbot.simulator import Position


@dataclass(frozen=True)
class ExecutionResult:
    proposal_id: str
    status: ProposalStatus
    position: Position | None = None
    reason: str = ""
