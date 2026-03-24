from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from cex_tbot.exceptions import GateDemoTransportError, GateLiveModeBlockedError, MissingGateDemoApiError
from cex_tbot.market_data.gate_metadata import GateInstrumentRecord


class GateInstrumentFetcher(Protocol):
    """Fetch contract for Gate instrument metadata without binding Phase 2 to live transport."""

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        ...


class GateDemoInstrumentClient(Protocol):
    """Boundary for demo-safe Gate metadata access.

    Concrete HTTP/network transport is intentionally kept outside the core repo for now.
    Tests and integrations can inject a client implementation that returns existing
    ``GateInstrumentRecord`` values without changing the Phase 2 pipeline.
    """

    def list_instruments(self) -> list[GateInstrumentRecord]:
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


@dataclass(frozen=True)
class GateDemoInstrumentFetcher:
    """Adapter from the Gate demo client boundary to the existing metadata pipeline."""

    client: GateDemoInstrumentClient

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        return self.client.list_instruments()


@dataclass(frozen=True)
class UnimplementedGateDemoInstrumentClient:
    """Safe placeholder used until an explicit demo HTTP client is introduced.

    This keeps the integration path demo-only and prevents accidental drift into a
    hidden live transport. Real network behavior must be injected deliberately.
    """

    gate_demo_api: str

    def __post_init__(self) -> None:
        if not self.gate_demo_api.strip():
            raise MissingGateDemoApiError(
                "GATE_DEMO_API is required when CEX_TBOT_EXECUTION_MODE=gate_demo"
            )

    def list_instruments(self) -> list[GateInstrumentRecord]:
        raise NotImplementedError(
            "Gate demo transport boundary is wired, but no concrete demo client is installed. "
            "Inject GateDemoInstrumentClient explicitly; live transport remains blocked."
        )
