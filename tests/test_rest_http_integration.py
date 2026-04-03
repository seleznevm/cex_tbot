from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # optional REST dependency
    TestClient = None

from cex_tbot.rest_api import RestApiDependencyError, create_rest_app


@unittest.skipIf(TestClient is None, "fastapi test dependencies are not installed")


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

    def test_topic_command_endpoint_routes_same_topic(self) -> None:
        response = self.client.post(
            "/topic/command",
            json={
                "sender_id": "125619710",
                "text": "/trade_status",
                "chat_id": "telegram:-1003832858724",
                "thread_id": "7",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Session Summary", response.json()["text"])
        self.assertEqual(response.json()["thread_id"], "7")

    def test_topic_proposal_endpoint_persists_and_returns_same_topic_payload(self) -> None:
        response = self.client.post("/topic/proposals", json=self.proposal_payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["proposal_id"], "proposal_http_1")
        self.assertIn("Trade approval request", payload["text"])
        self.assertIn("/trade_approve proposal_http_1", payload["text"])

        detail = self.client.get("/proposals/proposal_http_1", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["proposal_id"], "proposal_http_1")

    def test_topic_no_trade_endpoint_persists_and_returns_same_topic_payload(self) -> None:
        response = self.client.post(
            "/topic/no-trades",
            json={
                "decision_id": "no_trade_http_1",
                "agent_name": "Luma",
                "strategy_id": "breakout_reclaim",
                "strategy_version": "v3",
                "symbol": "BTC_USDT",
                "timeframe": "15m",
                "confidence_score": 0.41,
                "reason_code": "confidence_below_threshold",
                "reason_text": "signal stayed too weak after validation",
                "market_context_id": "ctx_demo_btc_20260326",
                "liquidity_check": "ok",
                "data_freshness_ms": 5000,
                "created_at": self.now.isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["decision_id"], "no_trade_http_1")
        self.assertIn("No-trade notice", payload["text"])
        self.assertIn("reason=confidence_below_threshold", payload["text"])

        listed = self.client.get("/no-trades", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["decision_id"], "no_trade_http_1")

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
        self.assertIn("/topic/proposals", schema["paths"])
        self.assertIn("/topic/no-trades", schema["paths"])
        self.assertIn("/proposals/{proposal_id}/approve", schema["paths"])
        self.assertIn("/system/halt", schema["paths"])
        self.assertIn("ProposalPayload", schema["components"]["schemas"])
        self.assertIn("NoTradeSubmitPayload", schema["components"]["schemas"])
        self.assertIn("TradeDetailPayload", schema["components"]["schemas"])
        self.assertIn("DashboardPayload", schema["components"]["schemas"])
        self.assertIn("DashboardUniversePayload", schema["components"]["schemas"])

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
        self.assertIn("recent_items", dashboard.json()["operator_activity"])
        self.assertIn("universe", dashboard.json())
        self.assertEqual(dashboard.json()["universe"]["eligible_symbols"], [])

        unhalted = self.client.post("/system/unhalt", json={}, headers=self.headers)
        self.assertEqual(unhalted.status_code, 200)
        self.assertFalse(unhalted.json()["emergency_halt_active"])

        dashboard_after = self.client.get("/dashboard", headers=self.headers)
        self.assertEqual(dashboard_after.status_code, 200)
        self.assertFalse(dashboard_after.json()["risk"]["emergency_halt_active"])
        self.assertIsNone(dashboard_after.json()["risk"]["halt_reason"])

    def test_execute_endpoint_is_blocked_by_stop_conditions(self) -> None:
        response = self.client.post("/proposals", json=self.proposal_payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)

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

        executed = self.client.post(
            "/trades/proposal_http_1/execute",
            json={
                "actor": "Mike",
                "portfolio_equity": 1000.0,
                "daily_drawdown_pct": 2.0,
                "now": self.now.isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(executed.status_code, 200)
        self.assertIn("New trades blocked", executed.json()["text"])

        detail = self.client.get("/proposals/proposal_http_1", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "APPROVED_PENDING_EXECUTION_CHECK")

    def test_clear_safety_endpoint_clears_warning_state(self) -> None:
        response = self.client.post("/proposals", json=self.proposal_payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)

        warned = self.client.post(
            "/proposals/proposal_http_1/approve",
            json={
                "actor": "Mike",
                "portfolio_equity": 1000.0,
                "daily_drawdown_pct": 1.7,
                "execute_on_approve": False,
                "now": self.now.isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(warned.status_code, 200)

        summary_before = self.client.get("/session/summary", headers=self.headers)
        self.assertEqual(summary_before.status_code, 200)
        self.assertEqual(summary_before.json()["safety_state"], "WARNING")

        cleared = self.client.post("/system/clear-safety", json={}, headers=self.headers)
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["safety_state"], "NORMAL")
        self.assertFalse(cleared.json()["block_new_trades"])


if __name__ == "__main__":
    unittest.main()
