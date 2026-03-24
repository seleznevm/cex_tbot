from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from cex_tbot.market_data.gate_metadata import GateInstrumentRecord


class GateInstrumentFetcher(Protocol):
    """Fetch contract for Gate instrument metadata without binding Phase 2 to live transport."""

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        ...


@dataclass(frozen=True)
class StaticGateInstrumentFetcher:
    """Deterministic in-memory Gate metadata fetcher for tests and local Phase 2 flow."""

    records: tuple[GateInstrumentRecord, ...] = field(default_factory=tuple)

    @classmethod
    def from_iterable(cls, records: Iterable[GateInstrumentRecord]) -> "StaticGateInstrumentFetcher":
        return cls(tuple(records))

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        return list(self.records)
