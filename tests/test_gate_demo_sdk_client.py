from __future__ import annotations

import sys
import types
import unittest

from cex_tbot.gate_demo_sdk_client import GateDemoSdkClient


class _Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class GateDemoSdkClientTests(unittest.TestCase):
    def test_sdk_client_maps_read_and_write_calls(self) -> None:
        fake_gate_api = types.ModuleType("gate_api")

        class Configuration:
            def __init__(self, host: str):
                self.host = host
                self.key = None
                self.secret = None

        class ApiClient:
            def __init__(self, configuration):
                self.configuration = configuration

        class FuturesOrder:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class FuturesPriceTriggeredOrder:
            def __init__(self, initial=None, trigger=None):
                self.initial = initial
                self.trigger = trigger

        class FuturesApi:
            def __init__(self, api_client):
                self.api_client = api_client

            def list_futures_contracts(self, settle):
                return [_Obj(name="BTC_USDT", trade_status="tradable", volume_24h=1000, open_interest=500, quanto_multiplier="0.0001", order_size_min="1")]

            def list_futures_accounts(self, settle):
                return _Obj(currency="USDT", available="1000", total="1000")

            def list_positions(self, settle):
                return [_Obj(contract="BTC_USDT", size=1, entry_price="100", mark_price="101", unrealised_pnl="1")]

            def list_futures_orders(self, settle, status="open"):
                return [_Obj(id="42", contract="BTC_USDT", size=1, price="100", status="open", tif="gtc")]

            def get_futures_order(self, settle, order_id):
                return _Obj(id=order_id, contract="BTC_USDT", size=1, price="100", status="open", left=1, fill_price=None)

            def create_futures_order(self, settle, order):
                return _Obj(id="99", contract=order.contract, size=order.size, status="open")

            def create_price_triggered_order(self, settle, order):
                return _Obj(id="pt-1", status="open", initial=_Obj(**order.initial), trigger=_Obj(**order.trigger))

            def get_price_triggered_order(self, settle, order_id):
                return _Obj(id=order_id, status="open", initial=_Obj(contract="BTC_USDT", size=-465, price="99.0", reduce_only=True), trigger=_Obj(price="99.0"))

            def cancel_futures_order(self, settle, order_id):
                return _Obj(id=order_id, status="cancelled")

        fake_gate_api.Configuration = Configuration
        fake_gate_api.ApiClient = ApiClient
        fake_gate_api.FuturesApi = FuturesApi
        fake_gate_api.FuturesOrder = FuturesOrder
        fake_gate_api.FuturesPriceTriggeredOrder = FuturesPriceTriggeredOrder

        original = sys.modules.get("gate_api")
        sys.modules["gate_api"] = fake_gate_api
        try:
            client = GateDemoSdkClient("https://api-testnet.gateapi.io/api/v4", "k", "s")
            self.assertEqual(client.list_instruments()[0].name, "BTC_USDT")
            self.assertEqual(client.account_status()["currency"], "USDT")
            self.assertEqual(client.positions_snapshot()[0]["contract"], "BTC_USDT")
            self.assertEqual(client.open_orders()[0]["id"], "42")
            self.assertEqual(client.order_status("42")["status"], "open")
            placed = client.place_test_order("BTC_USDT", size=0.0465, side="buy")
            self.assertEqual(placed["id"], "99")
            self.assertEqual(placed["normalized_contracts"], 465)
            triggered = client.place_trigger_order("BTC_USDT", trigger_price=99.0, order_price=99.0, size=465, side="sell", reduce_only=True)
            self.assertEqual(triggered["id"], "pt-1")
            self.assertEqual(triggered["reduce_only"], True)
            trigger_status = client.trigger_order_status("pt-1")
            self.assertEqual(trigger_status["id"], "pt-1")
            self.assertEqual(trigger_status["contract"], "BTC_USDT")
            self.assertEqual(client.cancel_order("42")["status"], "cancelled")
        finally:
            if original is None:
                del sys.modules["gate_api"]
            else:
                sys.modules["gate_api"] = original


if __name__ == "__main__":
    unittest.main()
