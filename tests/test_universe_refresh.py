from datetime import UTC, datetime
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.enums import EligibilityReasonCode, EligibilityStatus
from cex_tbot.universe import RawInstrument, UniverseService


class UniverseRefreshTests(unittest.TestCase):
    def test_refresh_materializes_and_marks_eligible(self) -> None:
        service = UniverseService(BotConfig())
        refreshed = service.refresh_universe(
            [
                RawInstrument(
                    symbol="BTC_USDT",
                    listing_age_hours=500,
                    spread_bps=1.5,
                    volume_24h=2_000_000,
                    open_interest=1_500_000,
                    top_book_depth=250_000,
                )
            ]
        )
        self.assertEqual(len(refreshed), 1)
        self.assertEqual(refreshed[0].eligibility_status, EligibilityStatus.ELIGIBLE)
        self.assertGreater(refreshed[0].eligible_until, datetime.now(UTC))

    def test_refresh_filters_non_usdt_and_inactive(self) -> None:
        service = UniverseService(BotConfig())
        refreshed = service.refresh_universe(
            [
                RawInstrument(symbol="BTC_BTC", quote_asset="BTC", listing_age_hours=500, spread_bps=1.0, volume_24h=1000, open_interest=1000, top_book_depth=1000),
                RawInstrument(symbol="ETH_USDT", status="settling", listing_age_hours=500, spread_bps=1.0, volume_24h=1000, open_interest=1000, top_book_depth=1000),
            ]
        )
        reasons = {item.symbol: item.eligibility_reason for item in refreshed}
        self.assertEqual(reasons["BTC_BTC"], EligibilityReasonCode.QUOTE_ASSET_NOT_USDT)
        self.assertEqual(reasons["ETH_USDT"], EligibilityReasonCode.INSTRUMENT_INACTIVE)


if __name__ == "__main__":
    unittest.main()
