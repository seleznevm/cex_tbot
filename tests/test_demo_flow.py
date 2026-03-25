from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from cex_tbot.demo import run_demo


class DemoFlowTests(unittest.TestCase):
    def test_run_demo_approve_execute_in_memory(self) -> None:
        artifacts = run_demo(flow="approve-execute")
        self.assertEqual(artifacts.proposal_submit["status"], "PENDING_APPROVAL")
        self.assertIsNone(artifacts.execution_response)
        self.assertEqual(artifacts.trade_detail["status"], "EXECUTED")
        self.assertEqual(artifacts.session_summary["executed_proposals"], 1)
        self.assertEqual(artifacts.trade_detail["timeline"]["event_count"], 4)
        self.assertEqual(artifacts.trade_detail["timeline"]["snapshot_count"], 3)
        self.assertIn("Trade Report", artifacts.trade_report["text"])

    def test_run_demo_approve_then_execute_with_file_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage_dir = Path(tmp) / "session"
            artifacts = run_demo(flow="approve-then-execute", storage_dir=storage_dir)
            self.assertIsNotNone(artifacts.execution_response)
            assert artifacts.execution_response is not None
            self.assertEqual(artifacts.trade_detail["status"], "EXECUTED")
            self.assertEqual(artifacts.session_summary["operator_commands"], 2)
            self.assertTrue((storage_dir / "proposals.jsonl").exists())
            self.assertTrue((storage_dir / "execution-events.jsonl").exists())
            self.assertTrue((storage_dir / "execution-state.jsonl").exists())
            self.assertTrue((storage_dir / "operator-transcript.jsonl").exists())

    def test_cli_demo_json_output(self) -> None:
        proc = subprocess.run(
            ["python3", "-m", "cex_tbot", "demo", "--format", "json", "--flow", "approve-then-execute"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["flow"], "approve-then-execute")
        self.assertEqual(payload["trade_detail"]["status"], "EXECUTED")
        self.assertEqual(payload["session_summary"]["operator_commands"], 2)


if __name__ == "__main__":
    unittest.main()
