from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, UTC, timedelta


class CliCommandTests(unittest.TestCase):
    def _run(
        self,
        tmp: str,
        *args: str,
        check: bool = True,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "cex_tbot", *args],
            cwd=Path(__file__).resolve().parents[1],
            check=check,
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

    def test_emit_demo_proposal_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            result = self._run(tmp, "emit-demo-proposal", "--storage-dir", storage)
            self.assertIn("Trade approval request", result.stdout)
            self.assertIn("Symbol: BTC_USDT", result.stdout)
            self.assertIn("Direction: LONG", result.stdout)
            self.assertIn("Timeframe: 15m", result.stdout)
            self.assertIn("/trade_approve proposal_topic_demo_btc", result.stdout)

    def test_submit_and_emit_demo_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            result = self._run(tmp, "submit-and-emit-demo", "--storage-dir", storage, "--format", "json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["proposal_id"], "proposal_topic_demo_btc")
            self.assertEqual(payload["thread_id"], "7")
            self.assertIn("Trade approval request", payload["text"])

    def test_submit_and_emit_from_json_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            proposal_path = Path(tmp) / "proposal.json"
            now = datetime.now(UTC)
            proposal_path.write_text(json.dumps({
                "proposal_id": "proposal_file_live_1",
                "agent_name": "Luma",
                "strategy_id": "pullback",
                "strategy_version": "v1",
                "market_context_id": "ctx_file_live_1",
                "symbol": "BTC_USDT",
                "timeframe": "15m",
                "direction": "LONG",
                "entry_zone_min": 99.0,
                "entry_zone_max": 100.0,
                "entry_split": [{
                    "leg_number": 1,
                    "planned_entry_price": 100.0,
                    "allocation_pct": 100.0,
                    "size_fraction": 1.0,
                    "valid_until": (now + timedelta(minutes=10)).isoformat(),
                }],
                "stop_loss": 98.5,
                "take_profit_1": 101.5,
                "take_profit_2": 103.0,
                "risk_percent": 0.5,
                "risk_usd": 5.0,
                "position_size": 10.0,
                "confidence_score": 0.81,
                "thesis": "clean reclaim after pullback",
                "invalidity_condition": "support fails",
                "liquidity_check": "ok",
                "data_freshness_ms": 100,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=15)).isoformat(),
                "status": "PENDING_APPROVAL"
            }), encoding="utf-8")
            result = self._run(tmp, "submit-and-emit", str(proposal_path), "--storage-dir", storage, "--format", "json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["proposal_id"], "proposal_file_live_1")
            self.assertIn("/trade_approve proposal_file_live_1", payload["text"])

    def test_submit_and_emit_print_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, "submit-and-emit", "--print-contract")
            self.assertIn("Proposal JSON contract", result.stdout)
            self.assertIn("confidence_score: 0..1", result.stdout)

    def test_submit_and_emit_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            proposal_path = Path(tmp) / "bad_proposal.json"
            proposal_path.write_text(json.dumps({
                "proposal_id": "bad_1",
                "agent_name": "Luma",
                "direction": "UP",
                "entry_split": []
            }), encoding="utf-8")
            result = self._run(tmp, "submit-and-emit", str(proposal_path), "--storage-dir", storage, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid proposal JSON", result.stdout or result.stderr)

    def test_json_output_survives_non_utf_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            self._run(tmp, "submit-demo", "--storage-dir", storage, "--format", "json")
            result = self._run(
                tmp,
                "command",
                "APPROVE proposal_demo_btc_breakout",
                "--approve-only",
                "--storage-dir",
                storage,
                "--format",
                "json",
                extra_env={"PYTHONIOENCODING": "cp1252"},
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "operator")


if __name__ == "__main__":
    unittest.main()
