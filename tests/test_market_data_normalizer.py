from datetime import UTC, datetime
import unittest

from cex_tbot.market_data import MarketDataNormalizer, RawMarketTicker


class MarketDataNormalizerTests(unittest.TestCase):
    def test_normalizes_raw_ticker_to_snapshot(self) -> None:
        normalizer = MarketDataNormalizer()
        captured_at = datetime.now(UTC)
        snapshot = normalizer.normalize_ticker(
            RawMarketTicker(
                symbol="BTC_USDT",
                best_bid=100.0,
                best_ask=100.2,
                last_price=100.1,
                volume_24h=1_000_000,
                open_interest=500_000,
                top_book_depth=250_000,
                captured_at=captured_at,
            )
        )
        self.assertEqual(snapshot.symbol, "BTC_USDT")
        self.assertAlmostEqual(snapshot.spread_bps, 19.98001998001985)
        self.assertEqual(snapshot.captured_at, captured_at)

    def test_rejects_crossed_book(self) -> None:
        normalizer = MarketDataNormalizer()
        with self.assertRaises(ValueError):
            normalizer.normalize_ticker(
                RawMarketTicker(
                    symbol="BTC_USDT",
                    best_bid=101.0,
                    best_ask=100.0,
                    last_price=100.5,
                    volume_24h=1_000_000,
                    open_interest=500_000,
                    top_book_depth=250_000,
                    captured_at=datetime.now(UTC),
                )
            )


if __name__ == "__main__":
    unittest.main()
