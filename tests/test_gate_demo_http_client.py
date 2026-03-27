from __future__ import annotations

import unittest

from cex_tbot.market_data.gate_client import HttpxGateDemoInstrumentClient


class GateDemoHttpClientTests(unittest.TestCase):
    def test_httpx_gate_demo_client_maps_contract_payload(self) -> None:
        httpx = __import__("httpx")

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertTrue(str(request.url).endswith("/futures/usdt/contracts"))
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "BTC_USDT",
                        "trade_status": "tradable",
                        "is_new_listing": False,
                        "listing_age_hours": 500,
                        "quote_asset": "USDT",
                        "volume_24h": 2000000,
                        "open_interest": 1000000,
                        "spread_bps": 4.0,
                        "top_book_depth": 400000,
                    }
                ],
            )

        transport = httpx.MockTransport(handler)
        client = HttpxGateDemoInstrumentClient("https://demo.gate", transport=transport)

        records = client.list_instruments()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].name, "BTC_USDT")
        self.assertEqual(records[0].trade_status, "tradable")
        self.assertEqual(records[0].volume_24h, 2000000)

    def test_httpx_gate_demo_client_healthcheck(self) -> None:
        httpx = __import__("httpx")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"name": "BTC_USDT"}, {"name": "ETH_USDT"}])

        transport = httpx.MockTransport(handler)
        client = HttpxGateDemoInstrumentClient("https://demo.gate", transport=transport)

        payload = client.healthcheck()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["contracts_seen"], 2)
        self.assertIn("/futures/usdt/contracts", payload["endpoint"])

    def test_httpx_gate_demo_client_account_status_requires_credentials(self) -> None:
        client = HttpxGateDemoInstrumentClient("https://demo.gate")

        with self.assertRaisesRegex(Exception, "GATE_DEMO_KEY and GATE_DEMO_SECRET"):
            client.account_status()

    def test_httpx_gate_demo_client_positions_snapshot_maps_payload(self) -> None:
        httpx = __import__("httpx")

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/futures/usdt/positions"):
                return httpx.Response(200, json=[{"contract": "BTC_USDT", "size": 1, "entry_price": "100", "mark_price": "101", "unrealised_pnl": "1", "leverage": "5", "mode": "single"}])
            if url.endswith("/futures/usdt/orders"):
                return httpx.Response(200, json=[{"id": "42", "contract": "BTC_USDT", "size": 1, "price": "100", "status": "open", "tif": "gtc"}])
            if url.endswith("/futures/usdt/orders/42"):
                return httpx.Response(200, json={"id": "42", "contract": "BTC_USDT", "size": 1, "price": "100", "status": "open", "left": 1, "fill_price": None})
            return httpx.Response(200, json={"currency": "USDT", "available": "1000", "total": "1000"})

        transport = httpx.MockTransport(handler)
        client = HttpxGateDemoInstrumentClient("https://demo.gate", transport=transport, gate_demo_key="k", gate_demo_secret="s")

        positions = client.positions_snapshot()
        orders = client.open_orders()
        order = client.order_status("42")

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["contract"], "BTC_USDT")
        self.assertEqual(positions[0]["unrealised_pnl"], "1")
        self.assertEqual(orders[0]["id"], "42")
        self.assertEqual(order["status"], "open")

    def test_httpx_gate_demo_client_place_test_order_not_enabled_yet(self) -> None:
        client = HttpxGateDemoInstrumentClient("https://demo.gate", gate_demo_key="k", gate_demo_secret="s")

        with self.assertRaisesRegex(NotImplementedError, "write trading is not enabled"):
            client.place_test_order("BTC_USDT", size=1.0, side="buy")


if __name__ == "__main__":
    unittest.main()
