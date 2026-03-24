from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.enums import EligibilityStatus
from cex_tbot.shared import ensure_utc, utc_now
from cex_tbot.universe.models import WhitelistedInstrument


@dataclass(frozen=True)
class UniverseSnapshot:
    snapshot_id: str
    created_at: datetime
    instruments: tuple[WhitelistedInstrument, ...]
    refresh_reason: str = "scheduled_refresh"

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc(self.created_at))


@dataclass
class InMemoryUniverseSnapshotRepository:
    """Append-only in-memory repository for Phase 2 universe snapshots."""

    _snapshots: list[UniverseSnapshot] = field(default_factory=list)

    def append(
        self,
        instruments: list[WhitelistedInstrument],
        *,
        snapshot_id: str,
        refresh_reason: str = "scheduled_refresh",
        created_at: datetime | None = None,
    ) -> UniverseSnapshot:
        snapshot = UniverseSnapshot(
            snapshot_id=snapshot_id,
            created_at=created_at or utc_now(),
            instruments=tuple(instruments),
            refresh_reason=refresh_reason,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def list_snapshots(self) -> list[UniverseSnapshot]:
        return list(self._snapshots)

    def latest(self) -> UniverseSnapshot | None:
        if not self._snapshots:
            return None
        return self._snapshots[-1]

    def latest_for_symbol(self, symbol: str) -> WhitelistedInstrument | None:
        latest = self.latest()
        if latest is None:
            return None
        for instrument in latest.instruments:
            if instrument.symbol == symbol:
                return instrument
        return None

    def latest_eligible_symbols(self) -> list[str]:
        latest = self.latest()
        if latest is None:
            return []
        return [
            instrument.symbol
            for instrument in latest.instruments
            if instrument.eligibility_status == EligibilityStatus.ELIGIBLE
        ]
