from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.enums import EligibilityStatus
from cex_tbot.universe import UniverseService, WhitelistedInstrument


class UniverseTests(unittest.TestCase):
    def test_rejects_new_listing(self) -> None:
        service = UniverseService(BotConfig())
        instrument = WhitelistedInstrument(
            symbol="BTC_USDT",
            is_new_listing=True,
            listing_age_hours=12,
            spread_bps=2.0,
            volume_24h=1_000_000,
            open_interest=500_000,
            top_book_depth=100_000,
            eligible_until=datetime.now(UTC) + timedelta(hours=1),
        )
        decision = service.evaluate_instrument(instrument)
        self.assertEqual(decision.status, EligibilityStatus.INELIGIBLE)

    def test_ranks_eligible_instruments(self) -> None:
        service = UniverseService(BotConfig(whitelist_size=1))
        now = datetime.now(UTC) + timedelta(hours=1)
        low = WhitelistedInstrument(symbol="ETH_USDT", listing_age_hours=200, spread_bps=2.0, volume_24h=1000, open_interest=1000, top_book_depth=1000, eligible_until=now)
        high = WhitelistedInstrument(symbol="BTC_USDT", listing_age_hours=200, spread_bps=1.0, volume_24h=2000, open_interest=2000, top_book_depth=2000, eligible_until=now)
        ranked = service.rank_whitelist([low, high])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].symbol, "BTC_USDT")


if __name__ == "__main__":
    unittest.main()
