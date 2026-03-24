import unittest

from cex_tbot.market_data import GateInstrumentRecord, StaticGateInstrumentFetcher


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


if __name__ == "__main__":
    unittest.main()
