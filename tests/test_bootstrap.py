from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cex_tbot import TradeSessionStore, build_app
from cex_tbot.storage import FileTradeSessionStore


class BootstrapTests(unittest.TestCase):
    def test_build_app_wires_runtime_in_memory(self) -> None:
        app = build_app()

        self.assertIsInstance(app.session, TradeSessionStore)
        self.assertIs(app.backend.session, app.session)
        self.assertIs(app.api.backend, app.backend)
        self.assertIs(app.workflow.approval_flow, app.approval_flow)
        self.assertIs(app.execution.risk_engine, app.risk_engine)
        self.assertIs(app.execution.state_store, app.session.execution_state)
        self.assertIs(app.execution.journal, app.session.execution_journal)
        self.assertIs(app.router.transcript, app.session.operator_transcript)
        self.assertIs(app.query_service.session, app.session)
        self.assertIs(app.dashboard_builder.session, app.session)

    def test_build_app_supports_file_backed_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(storage_dir=Path(tmp) / "runtime")

            self.assertIsInstance(app.session, FileTradeSessionStore)
            self.assertTrue((Path(tmp) / "runtime").exists())
            self.assertEqual(app.backend.get_session_summary().total_proposals, 0)
            self.assertEqual(app.backend.get_dashboard_view().kpis.total_proposals, 0)
            self.assertEqual(app.backend.list_trades(), [])

    def test_build_app_accepts_explicit_session_without_missing_dependency_crashes(self) -> None:
        session = TradeSessionStore()
        app = build_app(session=session)

        self.assertIs(app.session, session)
        self.assertEqual(app.backend.get_session_summary_payload()["total_proposals"], 0)
        self.assertEqual(app.backend.get_dashboard_payload()["kpis"]["total_proposals"], 0)
        self.assertEqual(app.api.list_trades(), [])

    def test_python_m_bootstrap_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            completed = subprocess.run(
                [sys.executable, "-m", "cex_tbot", "--storage-dir", str(Path(tmp) / "runtime"), "--format", "json"],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["storage"], "file")
            self.assertEqual(payload["session_summary"]["total_proposals"], 0)


if __name__ == "__main__":
    unittest.main()
