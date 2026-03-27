from __future__ import annotations

import unittest

from cex_tbot.bootstrap import build_app
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.exceptions import GateDemoTransportError
from tests.test_gate_demo_operator_commands import _HealthyDemoClient


class _FilledOrderClient(_HealthyDemoClient):
    def cancel_order(self, order_id: str) -> dict[str, object]:
        raise GateDemoTransportError('Gate demo cancel order failed: ORDER_NOT_FOUND')

    def order_status(self, order_id: str) -> dict[str, object]:
        return {"id": order_id, "contract": "BTC_USDT", "size": 1, "price": "100", "status": "finished", "left": 0, "fill_price": "101"}


class DemoExecutionPolishTests(unittest.TestCase):
    def test_cancel_reports_already_finalized_for_filled_order(self) -> None:
        app = build_app(
            config=BotConfig(execution_mode="gate_demo", gate_demo_api="https://demo.gate", gate_demo_key="k", gate_demo_secret="s"),
            gate_demo_client=_FilledOrderClient(),
        )
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        reply = dispatcher.dispatch('/demo_cancel_order 42')

        self.assertIn('already_finalized', reply.text)
        outcomes = [entry.outcome for entry in app.backend.session.operator_transcript.list_entries()]
        self.assertIn('DEMO_ORDER_ALREADY_FINAL', outcomes)

    def test_demo_smoke_runs_place_status_cancel_flow(self) -> None:
        app = build_app(
            config=BotConfig(execution_mode="gate_demo", gate_demo_api="https://demo.gate", gate_demo_key="k", gate_demo_secret="s"),
            gate_demo_client=_HealthyDemoClient(),
        )
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        reply = dispatcher.dispatch('/demo_smoke BTC_USDT buy')

        self.assertIn('Gate demo test order', reply.text)
        self.assertIn('Gate demo order status', reply.text)
        self.assertIn('Gate demo cancel order', reply.text)
        outcomes = [entry.outcome for entry in app.backend.session.operator_transcript.list_entries()]
        self.assertIn('DEMO_ORDER_PLACED', outcomes)
        self.assertIn('DEMO_ORDER_CANCELLED', outcomes)


if __name__ == '__main__':
    unittest.main()
