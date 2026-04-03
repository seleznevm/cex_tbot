from __future__ import annotations

import unittest

from cex_tbot.execution.demo_order_status_poller import DemoOrderStatusPoller
from cex_tbot.execution.demo_sync import DemoOrderRecord


class _DemoOrdersStub:
    def __init__(self, by_proposal: dict[str, list[DemoOrderRecord]]) -> None:
        self._by_proposal = by_proposal

    def list_for_proposal(self, proposal_id: str) -> list[DemoOrderRecord]:
        return list(self._by_proposal.get(proposal_id, []))


class _AlertProducerStub:
    class _Outbound:
        chat_id = "telegram:-100"
        thread_id = "7"
        text = "alert text"

    def __init__(self) -> None:
        self.calls = 0

    def emit_conservative_alert(self, _assessment):
        self.calls += 1
        return self._Outbound()


class _BackendStub:
    def __init__(self) -> None:
        self.session = type("Session", (), {})()
        self.session.demo_orders = _DemoOrdersStub(
            {
                "p1": [DemoOrderRecord("o1", "p1", "entry", "BTC_USDT", "buy", 1.0, "open")],
                "p2": [DemoOrderRecord("o2", "p2", "entry", "BTC_USDT", "buy", 1.0, "finished")],
            }
        )
        self.sync_calls: list[str] = []

    def list_trades_payload(self):
        return [{"proposal_id": "p1"}, {"proposal_id": "p2"}]

    def sync_demo_orders(self, proposal_id: str):
        self.sync_calls.append(proposal_id)
        return self.session.demo_orders.list_for_proposal(proposal_id)

    def get_demo_policy_assessment_payload(self, _proposal_id: str):
        return {
            "proposal_id": "p1",
            "mode": "conservative_demo",
            "alerts": ["No policy alerts: all good"],
            "auto_actions": [],
        }


class DemoOrderStatusPollerTests(unittest.TestCase):
    def test_poller_syncs_only_open_orders(self) -> None:
        backend = _BackendStub()
        poller = DemoOrderStatusPoller(backend)

        result = poller.run_once().to_payload()

        self.assertTrue(result["ok"])
        self.assertEqual(result["scanned_proposals"], 2)
        self.assertEqual(result["synced_proposals"], 1)
        self.assertEqual(result["synced_orders"], 1)
        self.assertEqual(backend.sync_calls, ["p1"])

    def test_poller_can_emit_telegram_alert_payload(self) -> None:
        backend = _BackendStub()
        producer = _AlertProducerStub()

        def _policy_with_alert(_proposal_id: str):
            return {
                "proposal_id": "p1",
                "mode": "conservative_demo",
                "alerts": ["Stale stop order detected"],
                "auto_actions": [],
            }

        backend.get_demo_policy_assessment_payload = _policy_with_alert  # type: ignore[method-assign]
        poller = DemoOrderStatusPoller(backend, emit_telegram_alerts=True, alert_producer=producer)  # type: ignore[arg-type]

        result = poller.run_once().to_payload()

        self.assertEqual(producer.calls, 1)
        item = result["items"][0]
        self.assertEqual(item["telegram_alert"]["chat_id"], "telegram:-100")
        self.assertEqual(item["telegram_alert"]["thread_id"], "7")


if __name__ == "__main__":
    unittest.main()
