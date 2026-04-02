from __future__ import annotations

import unittest

from cex_tbot.periodic_runner import PeriodicRunner


class _StubResult:
    def __init__(self, index: int) -> None:
        self.index = index

    def to_payload(self) -> dict[str, object]:
        return {"index": self.index}


class _StubTarget:
    def __init__(self) -> None:
        self.calls = 0

    def run_once(self) -> _StubResult:
        self.calls += 1
        return _StubResult(self.calls)


class _ReentrantTarget:
    def __init__(self) -> None:
        self.runner: PeriodicRunner | None = None

    def run_once(self) -> dict[str, object]:
        assert self.runner is not None
        with self.assert_raises_runtime_error():
            self.runner.run_single()
        return {"status": "ok"}

    class assert_raises_runtime_error:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            if exc_type is RuntimeError:
                return True
            raise AssertionError("expected RuntimeError")


class PeriodicRunnerTests(unittest.TestCase):
    def test_run_single_executes_exactly_once(self) -> None:
        target = _StubTarget()
        sleeper_calls: list[float] = []
        runner = PeriodicRunner(target, interval_sec=15, sleeper=sleeper_calls.append)

        summary = runner.run_single()

        self.assertEqual(target.calls, 1)
        self.assertEqual(summary.runs_completed, 1)
        self.assertFalse(summary.periodic)
        self.assertEqual(summary.last_payload, {"index": 1})
        self.assertEqual(sleeper_calls, [])

    def test_run_periodic_executes_fixed_number_of_runs(self) -> None:
        target = _StubTarget()
        sleeper_calls: list[float] = []
        runner = PeriodicRunner(target, interval_sec=12, sleeper=sleeper_calls.append)

        summary = runner.run_periodic(runs=3)

        self.assertEqual(target.calls, 3)
        self.assertEqual(summary.runs_completed, 3)
        self.assertTrue(summary.periodic)
        self.assertEqual(summary.last_payload, {"index": 3})
        self.assertEqual(sleeper_calls, [12, 12])

    def test_reentrant_execution_is_blocked(self) -> None:
        target = _ReentrantTarget()
        runner = PeriodicRunner(target, interval_sec=5)
        target.runner = runner

        summary = runner.run_single()

        self.assertEqual(summary.runs_completed, 1)
        self.assertEqual(summary.last_payload, {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
