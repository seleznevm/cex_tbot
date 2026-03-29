from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import os
import sys


class AutoSyncTelegramPayloadsTests(unittest.TestCase):
    def test_autosync_can_emit_telegram_alert_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            storage = str(Path(tmp) / "runtime")

            submit = subprocess.run(
                [sys.executable, "-m", "cex_tbot", "submit-demo", "--storage-dir", storage, "--format", "json"],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            proposal_id = json.loads(submit.stdout)["proposal_id"]

            subprocess.run(
                [sys.executable, "-m", "cex_tbot", "command", f"APPROVE {proposal_id}", "--storage-dir", storage, "--format", "json"],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            result = subprocess.run(
                [sys.executable, "-m", "cex_tbot", "autosync-demo", "--storage-dir", storage, "--runs", "1", "--emit-telegram-alerts", "--format", "json"],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            payload = json.loads(result.stdout)
            self.assertIsInstance(payload, list)


if __name__ == "__main__":
    unittest.main()
