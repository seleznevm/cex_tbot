from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

from cex_tbot.rest_api import create_rest_app


class Z12CliRestTests(unittest.TestCase):
    def test_post_analysis_cli_outputs_payload(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            subprocess.run([sys.executable, "-m", "cex_tbot", "submit-demo", "--storage-dir", storage, "--format", "json"], cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True, env=env)
            result = subprocess.run([sys.executable, "-m", "cex_tbot", "post-analysis", "--storage-dir", storage, "--format", "json"], cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True, env=env)
            payload = json.loads(result.stdout)
            self.assertIn("total_trades", payload)
            self.assertIn("calibration_hints", payload)

    def test_post_analysis_rest_endpoint_exists(self) -> None:
        bundle = create_rest_app()
        client = TestClient(bundle.app)
        response = client.get("/post-analysis")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("total_trades", payload)
        self.assertIn("calibration_hints", payload)

    def test_post_analysis_export_writes_file(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        with tempfile.TemporaryDirectory() as tmp:
            storage = str(Path(tmp) / "runtime")
            subprocess.run([sys.executable, "-m", "cex_tbot", "submit-demo", "--storage-dir", storage, "--format", "json"], cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True, env=env)
            out_path = Path(tmp) / "review.json"
            result = subprocess.run([sys.executable, "-m", "cex_tbot", "post-analysis-export", "--storage-dir", storage, "--format", "json", "--out", str(out_path)], cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True, env=env)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["path"], str(out_path))
            self.assertTrue(out_path.exists())
            exported = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("total_trades", exported)


if __name__ == "__main__":
    unittest.main()
