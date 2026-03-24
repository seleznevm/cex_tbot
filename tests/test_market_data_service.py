from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.market_data import MarketDataService, MarketSnapshot


class MarketDataServiceTests(unittest.TestCase):
    def test_marks_recent_snapshot_fresh(self) -> None:
        now = datetime.now(UTC)
        service = MarketDataService(max_snapshot_age_ms=60_000)
        snapshot = MarketSnapshot("BTC_USDT", 100, 100.1, 100.05, 1_000_000, 500_000, 1.0, 100_000, captured_at=now - timedelta(seconds=10))
        result = service.get_freshness(snapshot, now=now)
        self.assertTrue(result.is_fresh)

    def test_marks_old_snapshot_stale(self) -> None:
        now = datetime.now(UTC)
        service = MarketDataService(max_snapshot_age_ms=5_000)
        snapshot = MarketSnapshot("BTC_USDT", 100, 100.1, 100.05, 1_000_000, 500_000, 1.0, 100_000, captured_at=now - timedelta(seconds=10))
        result = service.get_freshness(snapshot, now=now)
        self.assertFalse(result.is_fresh)


if __name__ == "__main__":
    unittest.main()
