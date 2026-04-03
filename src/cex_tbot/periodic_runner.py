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
    success_runs: int
    failed_runs: int
    consecutive_failures: int
    max_consecutive_failures: int
    stopped_on_failure_threshold: bool
    last_error: dict[str, object] | None

    def to_payload(self) -> dict[str, object]:
        return {
            "runs_completed": self.runs_completed,
            "interval_sec": self.interval_sec,
            "periodic": self.periodic,
            "last_payload": self.last_payload,
            "success_runs": self.success_runs,
            "failed_runs": self.failed_runs,
            "consecutive_failures": self.consecutive_failures,
            "max_consecutive_failures": self.max_consecutive_failures,
            "stopped_on_failure_threshold": self.stopped_on_failure_threshold,
            "last_error": self.last_error,
        }


class PeriodicRunner:
    def __init__(
        self,
        target: RunOnceProtocol,
        *,
        interval_sec: int,
        sleeper: Callable[[float], None] | None = None,
        continue_on_error: bool = False,
        stop_after_consecutive_failures: int | None = None,
    ) -> None:
        if interval_sec <= 0:
            raise ValueError("interval_sec must be > 0")
        if stop_after_consecutive_failures is not None and stop_after_consecutive_failures <= 0:
            raise ValueError("stop_after_consecutive_failures must be > 0 when provided")
        self._target = target
        self._interval_sec = int(interval_sec)
        self._sleep = sleeper or time.sleep
        self._active = False
        self._continue_on_error = continue_on_error
        self._stop_after_consecutive_failures = stop_after_consecutive_failures

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
        success_runs = 0
        failed_runs = 0
        consecutive_failures = 0
        max_consecutive_failures = 0
        stopped_on_failure_threshold = False
        last_payload: dict[str, object] | None = None
        last_error: dict[str, object] | None = None
        try:
            while total_runs is None or completed < total_runs:
                try:
                    result = self._target.run_once()
                except Exception as exc:
                    if not self._continue_on_error:
                        raise
                    completed += 1
                    failed_runs += 1
                    consecutive_failures += 1
                    max_consecutive_failures = max(max_consecutive_failures, consecutive_failures)
                    last_error = {
                        "error_type": type(exc).__name__,
                        "error_message": str(exc) or repr(exc),
                    }
                else:
                    if hasattr(result, "to_payload"):
                        last_payload = result.to_payload()
                    elif isinstance(result, dict):
                        last_payload = result
                    else:
                        last_payload = {"result": str(result)}

                    result_ok = True
                    if hasattr(result, "ok"):
                        result_ok = bool(result.ok)
                    elif isinstance(last_payload, dict) and "ok" in last_payload:
                        result_ok = bool(last_payload["ok"])

                    completed += 1
                    if result_ok:
                        success_runs += 1
                        consecutive_failures = 0
                    else:
                        failed_runs += 1
                        consecutive_failures += 1
                        max_consecutive_failures = max(max_consecutive_failures, consecutive_failures)
                        error_payload = last_payload.get("error") if isinstance(last_payload, dict) else None
                        last_error = error_payload if isinstance(error_payload, dict) else {"error_message": "run reported failure"}

                if self._stop_after_consecutive_failures is not None and consecutive_failures >= self._stop_after_consecutive_failures:
                    stopped_on_failure_threshold = True
                    break
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
            success_runs=success_runs,
            failed_runs=failed_runs,
            consecutive_failures=consecutive_failures,
            max_consecutive_failures=max_consecutive_failures,
            stopped_on_failure_threshold=stopped_on_failure_threshold,
            last_error=last_error,
        )
