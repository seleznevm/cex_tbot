import unittest

from cex_tbot.market_data import MarketSnapshot, StaticMarketDataProvider


class MarketDataProviderTests(unittest.TestCase):
    def test_returns_snapshot_by_symbol(self) -> None:
        provider = StaticMarketDataProvider.from_iterable(
            [
                MarketSnapshot("BTC_USDT", 100.0, 100.1, 100.05, 1_000_000, 500_000, 1.0, 100_000),
                MarketSnapshot("ETH_USDT", 50.0, 50.1, 50.05, 500_000, 200_000, 2.0, 50_000),
            ]
        )
        snapshot = provider.get_snapshot("ETH_USDT")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.symbol, "ETH_USDT")


if __name__ == "__main__":
    unittest.main()
