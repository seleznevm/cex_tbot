from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliHaltNoTradeTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "cex_tbot", *args],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_no_trade_and_halt_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            no_trade = self._run("no-trade-demo", "--storage-dir", storage, "--format", "json")
            no_trade_payload = json.loads(no_trade.stdout)
            self.assertEqual(no_trade_payload["symbol"], "BTC_USDT")

            listed = self._run("list-no-trades", "--storage-dir", storage, "--format", "json")
            listed_payload = json.loads(listed.stdout)
            self.assertEqual(len(listed_payload), 1)

            halted = self._run("halt", "manual-safety-stop", "--storage-dir", storage, "--format", "json")
            halted_payload = json.loads(halted.stdout)
            self.assertTrue(halted_payload["emergency_halt_active"])
            self.assertTrue(halted_payload["block_new_trades"])
            self.assertEqual(halted_payload["safety_state"], "HALTED")

            submit = self._run("submit-demo", "--storage-dir", storage, "--format", "json")
            proposal_id = json.loads(submit.stdout)["proposal_id"]
            blocked = self._run("command", f"APPROVE {proposal_id}", "--storage-dir", storage, "--format", "json")
            blocked_payload = json.loads(blocked.stdout)
            self.assertIn("Emergency halt active", blocked_payload["text"])

            unhalted = self._run("unhalt", "--storage-dir", storage, "--format", "json")
            unhalted_payload = json.loads(unhalted.stdout)
            self.assertFalse(unhalted_payload["emergency_halt_active"])

    def test_execute_is_blocked_by_stop_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            submit = self._run("submit-demo", "--storage-dir", storage, "--format", "json")
            proposal_id = json.loads(submit.stdout)["proposal_id"]
            self._run(
                "command",
                f"APPROVE {proposal_id}",
                "--approve-only",
                "--storage-dir",
                storage,
                "--format",
                "json",
            )
            blocked = self._run(
                "execute",
                proposal_id,
                "--storage-dir",
                storage,
                "--format",
                "json",
                "--daily-drawdown-pct",
                "2.0",
            )
            blocked_payload = json.loads(blocked.stdout)
            self.assertIn("New trades blocked", blocked_payload["text"])

    def test_clear_safety_command_clears_warning_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            submit = self._run("submit-demo", "--storage-dir", storage, "--format", "json")
            proposal_id = json.loads(submit.stdout)["proposal_id"]
            self._run(
                "command",
                f"APPROVE {proposal_id}",
                "--approve-only",
                "--storage-dir",
                storage,
                "--format",
                "json",
                "--daily-drawdown-pct",
                "1.7",
            )
            cleared = self._run("clear-safety", "--storage-dir", storage, "--format", "json")
            cleared_payload = json.loads(cleared.stdout)
            self.assertEqual(cleared_payload["safety_state"], "NORMAL")
            self.assertFalse(cleared_payload["block_new_trades"])


if __name__ == "__main__":
    unittest.main()
