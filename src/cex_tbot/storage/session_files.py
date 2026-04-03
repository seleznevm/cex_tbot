from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cex_tbot.session_store import TradeSessionStore
from cex_tbot.storage.audit_files import FileOperatorTranscript
from cex_tbot.storage.demo_order_files import FileDemoOrderStore
from cex_tbot.storage.execution_files import FileExecutionJournal, FileExecutionStateStore
from cex_tbot.storage.no_trade_files import FileNoTradeStore
from cex_tbot.storage.proposal_files import FileProposalStore
from cex_tbot.storage.system_state_files import FileSystemState


@dataclass
class FileTradeSessionStore(TradeSessionStore):
    @classmethod
    def open(cls, base_dir: str | Path) -> "FileTradeSessionStore":
        root = Path(base_dir)
        root.mkdir(parents=True, exist_ok=True)
        return cls(
            proposals=FileProposalStore(root / "proposals.jsonl", root / "decisions.jsonl"),
            no_trades=FileNoTradeStore(root / "no-trades.jsonl"),
            execution_journal=FileExecutionJournal(root / "execution-events.jsonl"),
            execution_state=FileExecutionStateStore(root / "execution-state.jsonl"),
            demo_orders=FileDemoOrderStore(root / "demo-orders.jsonl"),
            operator_transcript=FileOperatorTranscript(root / "operator-transcript.jsonl"),
            system_state=FileSystemState(root / "system-state.json"),
        )

    def refresh_from_disk(self) -> None:
        for store in (
            self.proposals,
            self.no_trades,
            self.execution_journal,
            self.execution_state,
            self.demo_orders,
            self.operator_transcript,
            self.system_state,
        ):
            refresh = getattr(store, "refresh_from_disk", None)
            if callable(refresh):
                refresh()
