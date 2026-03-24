from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cex_tbot.session_store import TradeSessionStore
from cex_tbot.storage.audit_files import FileOperatorTranscript
from cex_tbot.storage.execution_files import FileExecutionJournal, FileExecutionStateStore
from cex_tbot.storage.proposal_files import FileProposalStore


@dataclass
class FileTradeSessionStore(TradeSessionStore):
    @classmethod
    def open(cls, base_dir: str | Path) -> "FileTradeSessionStore":
        root = Path(base_dir)
        root.mkdir(parents=True, exist_ok=True)
        return cls(
            proposals=FileProposalStore(root / "proposals.jsonl", root / "decisions.jsonl"),
            execution_journal=FileExecutionJournal(root / "execution-events.jsonl"),
            execution_state=FileExecutionStateStore(root / "execution-state.jsonl"),
            operator_transcript=FileOperatorTranscript(root / "operator-transcript.jsonl"),
        )
