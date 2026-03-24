from __future__ import annotations

from dataclasses import dataclass, field

from cex_tbot.audit import InMemoryOperatorTranscript
from cex_tbot.execution import InMemoryExecutionJournal, InMemoryExecutionStateStore
from cex_tbot.proposal_store import InMemoryProposalStore


@dataclass
class TradeSessionStore:
    proposals: InMemoryProposalStore = field(default_factory=InMemoryProposalStore)
    execution_journal: InMemoryExecutionJournal = field(default_factory=InMemoryExecutionJournal)
    execution_state: InMemoryExecutionStateStore = field(default_factory=InMemoryExecutionStateStore)
    operator_transcript: InMemoryOperatorTranscript = field(default_factory=InMemoryOperatorTranscript)
