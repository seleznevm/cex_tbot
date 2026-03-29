from __future__ import annotations

import unittest

from cex_tbot.bootstrap import build_app
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from tests.test_gate_demo_operator_commands import _HealthyDemoClient


class GateDemoOperatorSmokeTests(unittest.TestCase):
    def test_demo_operator_smoke_flow(self) -> None:
        app = build_app(
            config=BotConfig(
                execution_mode="gate_demo",
                gate_demo_api="https://api-testnet.gateapi.io/api/v4",
                gate_demo_key="demo-key",
                gate_demo_secret="demo-secret",
                gate_demo_test_order_size=0.25,
            ),
            gate_demo_client=_HealthyDemoClient(),
        )
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        steps = [
            dispatcher.dispatch("/demo_capabilities").text,
            dispatcher.dispatch("/demo_account_overview").text,
            dispatcher.dispatch("/demo_place_test_order BTC_USDT buy").text,
            dispatcher.dispatch("/demo_open_orders").text,
            dispatcher.dispatch("/demo_order_status 42").text,
            dispatcher.dispatch("/demo_cancel_order 42").text,
        ]

        self.assertIn("balance_snapshot=yes", steps[0])
        self.assertIn("order_placement=entry+trigger_brackets", steps[0])
        self.assertIn("Gate demo account status", steps[1])
        self.assertIn("Gate demo test order", steps[2])
        self.assertIn("Gate demo open orders", steps[3])
        self.assertIn("Gate demo order status", steps[4])
        self.assertIn("Gate demo cancel order", steps[5])


if __name__ == "__main__":
    unittest.main()
