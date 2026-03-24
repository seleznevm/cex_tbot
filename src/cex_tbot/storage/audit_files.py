from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from cex_tbot.audit import AuditEntry, InMemoryOperatorTranscript
from cex_tbot.shared import ensure_utc


class FileOperatorTranscript(InMemoryOperatorTranscript):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def append(self, entry: AuditEntry) -> AuditEntry:
        saved = super().append(entry)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._serialize(saved), ensure_ascii=False) + "\n")
        return saved

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            self._entries.append(
                AuditEntry(
                    actor=raw["actor"],
                    raw_command=raw["raw_command"],
                    outcome=raw["outcome"],
                    proposal_id=raw.get("proposal_id"),
                    created_at=ensure_utc(datetime.fromisoformat(raw["created_at"])),
                    entry_id=raw["entry_id"],
                )
            )

    @staticmethod
    def _serialize(entry: AuditEntry) -> dict[str, object]:
        data = asdict(entry)
        data["created_at"] = entry.created_at.isoformat()
        return data
