import unittest

from cex_tbot.market_data import (
    GateDemoInstrumentFetcher,
    GateInstrumentRecord,
    MissingGateDemoApiError,
    StaticGateInstrumentFetcher,
    UnimplementedGateDemoInstrumentClient,
)


class _FakeGateDemoClient:
    def __init__(self, records: list[GateInstrumentRecord]) -> None:
        self._records = records
        self.calls = 0

    def list_instruments(self) -> list[GateInstrumentRecord]:
        self.calls += 1
        return list(self._records)


class GateClientTests(unittest.TestCase):
    def test_static_fetcher_returns_records(self) -> None:
        fetcher = StaticGateInstrumentFetcher.from_iterable(
            [
                GateInstrumentRecord(name="BTC_USDT", listing_age_hours=300),
                GateInstrumentRecord(name="ETH_USDT", listing_age_hours=300),
            ]
        )
        records = fetcher.fetch_instruments()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].name, "BTC_USDT")
        self.assertEqual(records[1].name, "ETH_USDT")

    def test_gate_demo_fetcher_passes_records_through_client_boundary(self) -> None:
        client = _FakeGateDemoClient(
            [
                GateInstrumentRecord(name="BTC_USDT", listing_age_hours=300),
                GateInstrumentRecord(name="ETH_USDT", listing_age_hours=300),
            ]
        )
        fetcher = GateDemoInstrumentFetcher(client)

        records = fetcher.fetch_instruments()

        self.assertEqual(client.calls, 1)
        self.assertEqual([record.name for record in records], ["BTC_USDT", "ETH_USDT"])

    def test_unimplemented_demo_client_fails_predictably_without_api(self) -> None:
        with self.assertRaisesRegex(MissingGateDemoApiError, "GATE_DEMO_API"):
            UnimplementedGateDemoInstrumentClient("")

    def test_unimplemented_demo_client_blocks_hidden_transport(self) -> None:
        client = UnimplementedGateDemoInstrumentClient("demo-secret-placeholder")

        with self.assertRaisesRegex(NotImplementedError, "no concrete demo client is installed"):
            client.list_instruments()


if __name__ == "__main__":
    unittest.main()
