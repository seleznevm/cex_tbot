from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliCommandTests(unittest.TestCase):
    def _run(self, tmp: str, *args: str) -> subprocess.CompletedProcess[str]:
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

    def test_submit_list_detail_report_and_execute_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")

            submit = self._run(tmp, "submit-demo", "--storage-dir", storage, "--format", "json")
            submit_payload = json.loads(submit.stdout)
            proposal_id = submit_payload["proposal_id"]
            self.assertEqual(submit_payload["status"], "PENDING_APPROVAL")

            listed = self._run(tmp, "list", "--storage-dir", storage, "--format", "json")
            list_payload = json.loads(listed.stdout)
            self.assertEqual(len(list_payload), 1)
            self.assertEqual(list_payload[0]["proposal_id"], proposal_id)

            detail = self._run(tmp, "detail", proposal_id, "--storage-dir", storage, "--format", "json")
            detail_payload = json.loads(detail.stdout)
            self.assertEqual(detail_payload["proposal_id"], proposal_id)
            self.assertEqual(detail_payload["agent_name"], "Luma")

            command = self._run(
                tmp,
                "command",
                f"APPROVE {proposal_id}",
                "--approve-only",
                "--storage-dir",
                storage,
                "--format",
                "json",
            )
            command_payload = json.loads(command.stdout)
            self.assertEqual(command_payload["mode"], "operator")

            execute = self._run(tmp, "execute", proposal_id, "--storage-dir", storage, "--format", "json")
            execute_payload = json.loads(execute.stdout)
            self.assertEqual(execute_payload["mode"], "operator")

            report = self._run(tmp, "report", proposal_id, "--storage-dir", storage)
            self.assertIn("Trade Report", report.stdout)
            self.assertIn("Invalidation:", report.stdout)

    def test_dashboard_text_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            self._run(tmp, "submit-demo", "--storage-dir", storage, "--format", "json")
            dashboard = self._run(tmp, "dashboard", "--storage-dir", storage)
            self.assertIn("Dashboard", dashboard.stdout)
            self.assertIn("KPIs:", dashboard.stdout)
            self.assertIn("Risk:", dashboard.stdout)
            self.assertIn("Universe:", dashboard.stdout)
            self.assertIn("Alerts:", dashboard.stdout)
            self.assertIn("Operator activity:", dashboard.stdout)
            self.assertIn("Latest trades", dashboard.stdout)

    def test_demo_reports_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            status = self._run(tmp, "demo-status-report", "--storage-dir", storage)
            audit = self._run(tmp, "demo-audit-report", "--storage-dir", storage)
            self.assertIn("Gate demo capabilities", status.stdout)
            self.assertIn("Demo audit", audit.stdout)


if __name__ == "__main__":
    unittest.main()
