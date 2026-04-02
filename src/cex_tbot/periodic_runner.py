from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Protocol, TypeVar


class RunOnceProtocol(Protocol):
    def run_once(self): ...


T = TypeVar("T")


@dataclass(frozen=True)
class PeriodicRunSummary:
    runs_completed: int
    interval_sec: int
    periodic: bool
    last_payload: dict[str, object] | None

    def to_payload(self) -> dict[str, object]:
        return {
            "runs_completed": self.runs_completed,
            "interval_sec": self.interval_sec,
            "periodic": self.periodic,
            "last_payload": self.last_payload,
        }


class PeriodicRunner:
    def __init__(
        self,
        target: RunOnceProtocol,
        *,
        interval_sec: int,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if interval_sec <= 0:
            raise ValueError("interval_sec must be > 0")
        self._target = target
        self._interval_sec = int(interval_sec)
        self._sleep = sleeper or time.sleep
        self._active = False

    @property
    def interval_sec(self) -> int:
        return self._interval_sec

    def run_single(self) -> PeriodicRunSummary:
        return self._run(total_runs=1, periodic=False)

    def run_periodic(self, *, runs: int | None = None) -> PeriodicRunSummary:
        if runs is not None and runs <= 0:
            raise ValueError("runs must be > 0 when provided")
        return self._run(total_runs=runs, periodic=True)

    def _run(self, *, total_runs: int | None, periodic: bool) -> PeriodicRunSummary:
        if self._active:
            raise RuntimeError("periodic runner is already active")
        self._active = True
        completed = 0
        last_payload: dict[str, object] | None = None
        try:
            while total_runs is None or completed < total_runs:
                result = self._target.run_once()
                if hasattr(result, "to_payload"):
                    last_payload = result.to_payload()
                elif isinstance(result, dict):
                    last_payload = result
                else:
                    last_payload = {"result": str(result)}
                completed += 1
                if not periodic:
                    break
                if total_runs is not None and completed >= total_runs:
                    break
                self._sleep(self._interval_sec)
        finally:
            self._active = False
        return PeriodicRunSummary(
            runs_completed=completed,
            interval_sec=self._interval_sec,
            periodic=periodic,
            last_payload=last_payload,
        )
