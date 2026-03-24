from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cex_tbot.universe.models import RawInstrument


@dataclass(frozen=True)
class StaticUniverseSource:
    """Deterministic source of raw instrument metadata for Phase 2 tests."""

    instruments: tuple[RawInstrument, ...]

    @classmethod
    def from_iterable(cls, instruments: Iterable[RawInstrument]) -> "StaticUniverseSource":
        return cls(tuple(instruments))

    def list_instruments(self) -> list[RawInstrument]:
        return list(self.instruments)
