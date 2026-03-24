from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cex_tbot.enums import EligibilityStatus
from cex_tbot.market_data.gate_metadata import GateInstrumentMetadataAdapter, GateInstrumentRecord
from cex_tbot.shared import ensure_utc, utc_now
from cex_tbot.universe.repository import InMemoryUniverseSnapshotRepository, UniverseSnapshot
from cex_tbot.universe.service import UniverseService
from cex_tbot.universe.models import RawInstrument


@dataclass(frozen=True)
class UniverseRefreshResult:
    snapshot_id: str
    created_at: datetime
    refresh_reason: str
    total_symbols_seen: int
    eligible_count: int
    rejected_count: int
    top_whitelist_symbols: tuple[str, ...]
    snapshot: UniverseSnapshot

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc(self.created_at))


@dataclass
class UniverseRefreshOrchestrator:
    service: UniverseService
    repository: InMemoryUniverseSnapshotRepository
    adapter: GateInstrumentMetadataAdapter = field(default_factory=GateInstrumentMetadataAdapter)

    def refresh_from_gate_records(
        self,
        records: list[GateInstrumentRecord],
        *,
        snapshot_id: str,
        refresh_reason: str = "scheduled_refresh",
        created_at: datetime | None = None,
    ) -> UniverseRefreshResult:
        raw_instruments = self._normalize_records(records)
        refreshed = self.service.refresh_universe(raw_instruments)
        ranked = self.service.rank_whitelist(refreshed)
        effective_now = created_at or utc_now()
        snapshot = self.repository.append(
            refreshed,
            snapshot_id=snapshot_id,
            refresh_reason=refresh_reason,
            created_at=effective_now,
        )
        return UniverseRefreshResult(
            snapshot_id=snapshot.snapshot_id,
            created_at=effective_now,
            refresh_reason=refresh_reason,
            total_symbols_seen=len(raw_instruments),
            eligible_count=len([item for item in refreshed if item.eligibility_status == EligibilityStatus.ELIGIBLE]),
            rejected_count=len([item for item in refreshed if item.eligibility_status != EligibilityStatus.ELIGIBLE]),
            top_whitelist_symbols=tuple(item.symbol for item in ranked),
            snapshot=snapshot,
        )

    def refresh_from_raw_instruments(
        self,
        raw_instruments: list[RawInstrument],
        *,
        snapshot_id: str,
        refresh_reason: str = "scheduled_refresh",
        created_at: datetime | None = None,
    ) -> UniverseRefreshResult:
        refreshed = self.service.refresh_universe(raw_instruments)
        ranked = self.service.rank_whitelist(refreshed)
        effective_now = created_at or utc_now()
        snapshot = self.repository.append(
            refreshed,
            snapshot_id=snapshot_id,
            refresh_reason=refresh_reason,
            created_at=effective_now,
        )
        return UniverseRefreshResult(
            snapshot_id=snapshot.snapshot_id,
            created_at=effective_now,
            refresh_reason=refresh_reason,
            total_symbols_seen=len(raw_instruments),
            eligible_count=len([item for item in refreshed if item.eligibility_status == EligibilityStatus.ELIGIBLE]),
            rejected_count=len([item for item in refreshed if item.eligibility_status != EligibilityStatus.ELIGIBLE]),
            top_whitelist_symbols=tuple(item.symbol for item in ranked),
            snapshot=snapshot,
        )

    def _normalize_records(self, records: list[GateInstrumentRecord]) -> list[RawInstrument]:
        return self.adapter.normalize_records(records)
