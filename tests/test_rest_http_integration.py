from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from cex_tbot.rest_api import create_rest_app


class RestHttpIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_token = os.environ.get("CEX_TBOT_API_TOKEN")
        os.environ["CEX_TBOT_API_TOKEN"] = "secret-token"
        bundle = create_rest_app(storage_dir=self.tempdir.name)
        self.client = TestClient(bundle.app)
        self.headers = {"X-API-Key": "secret-token"}
        self.now = datetime(2026, 3, 26, 12, 0, tzinfo=UTC)
        self.proposal_payload = {
            "proposal_id": "proposal_http_1",
            "agent_name": "Luma",
            "strategy_id": "breakout_reclaim",
            "strategy_version": "v3",
            "market_context_id": "ctx_demo_btc_20260326",
            "symbol": "BTC_USDT",
            "timeframe": "15m",
            "direction": "LONG",
            "entry_zone_min": 100.0,
            "entry_zone_max": 101.0,
            "entry_split": [
                {
                    "leg_number": 1,
                    "planned_entry_price": 100.5,
                    "allocation_pct": 100.0,
                    "size_fraction": 1.0,
                    "valid_until": (self.now + timedelta(minutes=10)).isoformat(),
                }
            ],
            "stop_loss": 99.0,
            "take_profit_1": 103.0,
            "take_profit_2": 105.0,
            "risk_percent": 0.5,
            "risk_usd": 5.0,
            "position_size": 10.0,
            "confidence_score": 0.82,
            "thesis": "breakout held",
            "invalidity_condition": "reclaim fails",
            "liquidity_check": "ok",
            "data_freshness_ms": 5000,
            "created_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=15)).isoformat(),
            "status": "PENDING_APPROVAL",
        }

    def tearDown(self) -> None:
        if self.previous_token is None:
            os.environ.pop("CEX_TBOT_API_TOKEN", None)
        else:
            os.environ["CEX_TBOT_API_TOKEN"] = self.previous_token
        self.tempdir.cleanup()

    def test_root_serves_static_spa(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("cex_tbot UI Bridge", response.text)

    def test_health_requires_api_key(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["error"]["code"], "UNAUTHORIZED")

    def test_submit_approve_execute_and_report_flow(self) -> None:
        response = self.client.post("/proposals", json=self.proposal_payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["proposal_id"], "proposal_http_1")

        listed = self.client.get("/proposals", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)
        self.assertEqual(len(listed.json()["items"]), 1)

        approved = self.client.post(
            "/proposals/proposal_http_1/approve",
            json={
                "actor": "Mike",
                "portfolio_equity": 1000.0,
                "execute_on_approve": False,
                "now": self.now.isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["mode"], "plain")

        executed = self.client.post(
            "/trades/proposal_http_1/execute",
            json={
                "actor": "Mike",
                "portfolio_equity": 1000.0,
                "now": self.now.isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(executed.status_code, 200)

        detail = self.client.get("/proposals/proposal_http_1", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "EXECUTED")

        report = self.client.get("/trades/proposal_http_1/report", headers=self.headers)
        self.assertEqual(report.status_code, 200)
        self.assertIn("Trade Report", report.json()["text"])

    def test_modify_endpoint_requires_changes_and_replacement(self) -> None:
        response = self.client.post("/proposals/proposal_http_1/modify", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 422)

    def test_no_trades_endpoint_works(self) -> None:
        response = self.client.get("/no-trades", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_openapi_contains_ui_bridge_contracts(self) -> None:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertIn("/proposals", schema["paths"])
        self.assertIn("/proposals/{proposal_id}/approve", schema["paths"])
        self.assertIn("/system/halt", schema["paths"])
        self.assertIn("ProposalPayload", schema["components"]["schemas"])
        self.assertIn("TradeDetailPayload", schema["components"]["schemas"])

    def test_halt_and_unhalt_controls(self) -> None:
        halted = self.client.post("/system/halt", json={"reason": "manual-stop"}, headers=self.headers)
        self.assertEqual(halted.status_code, 200)
        self.assertTrue(halted.json()["emergency_halt_active"])

        dashboard = self.client.get("/dashboard", headers=self.headers)
        self.assertEqual(dashboard.status_code, 200)
        self.assertTrue(dashboard.json()["risk"]["emergency_halt_active"])
        self.assertEqual(dashboard.json()["risk"]["halt_reason"], "manual-stop")
        self.assertIn("max_open_risk_percent", dashboard.json()["risk"])
        self.assertIn("reserved_pending_risk_percent", dashboard.json()["risk"])
        self.assertIn("active_risk_percent", dashboard.json()["risk"])
        self.assertIn("free_risk_budget_percent", dashboard.json()["risk"])
        self.assertIn("alerts", dashboard.json())
        self.assertTrue(any(item["code"] == "HALT_ACTIVE" for item in dashboard.json()["alerts"]["items"]))

        unhalted = self.client.post("/system/unhalt", json={}, headers=self.headers)
        self.assertEqual(unhalted.status_code, 200)
        self.assertFalse(unhalted.json()["emergency_halt_active"])

        dashboard_after = self.client.get("/dashboard", headers=self.headers)
        self.assertEqual(dashboard_after.status_code, 200)
        self.assertFalse(dashboard_after.json()["risk"]["emergency_halt_active"])
        self.assertIsNone(dashboard_after.json()["risk"]["halt_reason"])


if __name__ == "__main__":
    unittest.main()
