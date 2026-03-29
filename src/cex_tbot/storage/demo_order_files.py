from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from cex_tbot.execution.demo_sync import DemoOrderRecord, InMemoryDemoOrderStore
from cex_tbot.shared import ensure_utc


class FileDemoOrderStore(InMemoryDemoOrderStore):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def replace_for_proposal(self, proposal_id: str, records: list[DemoOrderRecord]) -> None:
        super().replace_for_proposal(proposal_id, records)
        all_rows: list[dict[str, object]] = []
        for _, items in self._by_proposal.items():
            for item in items:
                row = asdict(item)
                row["synced_at"] = item.synced_at.isoformat()
                all_rows.append(row)
        with self.path.open("w", encoding="utf-8") as fh:
            for row in all_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            record = DemoOrderRecord(
                order_id=raw["order_id"],
                proposal_id=raw["proposal_id"],
                role=raw["role"],
                contract=raw["contract"],
                side=raw["side"],
                size=float(raw["size"]),
                status=raw["status"],
                trigger_price=raw.get("trigger_price"),
                order_price=raw.get("order_price"),
                reduce_only=bool(raw.get("reduce_only", False)),
                linked_entry_order_id=raw.get("linked_entry_order_id"),
                synced_at=ensure_utc(datetime.fromisoformat(raw["synced_at"])),
            )
            self._by_proposal.setdefault(record.proposal_id, []).append(record)
