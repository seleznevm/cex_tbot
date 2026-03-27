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


if __name__ == "__main__":
    unittest.main()
