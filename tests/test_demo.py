from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cex_tbot.demo import run_demo


class DemoFlowTests(unittest.TestCase):
    def test_run_demo_approve_execute_returns_executed_state(self) -> None:
        artifacts = run_demo(flow="approve-execute")

        self.assertEqual(artifacts.proposal_submit["status"], "PENDING_APPROVAL")
        self.assertIsNone(artifacts.execution_response)
        self.assertEqual(artifacts.trade_detail["status"], "EXECUTED")
        self.assertEqual(artifacts.session_summary["executed_proposals"], 1)
        self.assertGreaterEqual(artifacts.session_summary["execution_events"], 1)
        self.assertIn("Trade Report", artifacts.trade_report["text"])

    def test_run_demo_approve_then_execute_returns_both_steps(self) -> None:
        artifacts = run_demo(flow="approve-then-execute")

        self.assertIsNotNone(artifacts.execution_response)
        self.assertEqual(artifacts.trade_detail["status"], "EXECUTED")
        self.assertEqual(artifacts.session_summary["operator_commands"], 2)

    def test_python_m_demo_json_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cex_tbot",
                    "demo",
                    "--storage-dir",
                    str(Path(tmp) / "runtime"),
                    "--flow",
                    "approve-then-execute",
                    "--format",
                    "json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["flow"], "approve-then-execute")
            self.assertEqual(payload["storage"], "file")
            self.assertEqual(payload["trade_detail"]["status"], "EXECUTED")
            self.assertIsNotNone(payload["execution_response"])
            self.assertEqual(payload["session_summary"]["executed_proposals"], 1)


if __name__ == "__main__":
    unittest.main()
