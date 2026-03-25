from __future__ import annotations

from dataclasses import dataclass, field

from cex_tbot.audit import InMemoryOperatorTranscript
from cex_tbot.execution import InMemoryExecutionJournal, InMemoryExecutionStateStore
from cex_tbot.no_trade_store import InMemoryNoTradeStore
from cex_tbot.proposal_store import InMemoryProposalStore
from cex_tbot.system_state import SystemState


@dataclass
class TradeSessionStore:
    proposals: InMemoryProposalStore = field(default_factory=InMemoryProposalStore)
    no_trades: InMemoryNoTradeStore = field(default_factory=InMemoryNoTradeStore)
    execution_journal: InMemoryExecutionJournal = field(default_factory=InMemoryExecutionJournal)
    execution_state: InMemoryExecutionStateStore = field(default_factory=InMemoryExecutionStateStore)
    operator_transcript: InMemoryOperatorTranscript = field(default_factory=InMemoryOperatorTranscript)
    system_state: SystemState = field(default_factory=SystemState)
