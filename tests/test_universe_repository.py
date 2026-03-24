from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.enums import EligibilityStatus
from cex_tbot.universe import InMemoryUniverseSnapshotRepository, WhitelistedInstrument


class UniverseRepositoryTests(unittest.TestCase):
    def test_append_and_read_latest_snapshot(self) -> None:
        repository = InMemoryUniverseSnapshotRepository()
        now = datetime.now(UTC)
        eligible = WhitelistedInstrument(
            symbol="BTC_USDT",
            listing_age_hours=500,
            spread_bps=1.0,
            volume_24h=2_000_000,
            open_interest=1_500_000,
            top_book_depth=400_000,
            eligibility_status=EligibilityStatus.ELIGIBLE,
            eligibility_reason="passes_phase2_rules",
            eligible_until=now + timedelta(minutes=30),
        )
        snapshot = repository.append(
            [eligible],
            snapshot_id="universe_001",
            refresh_reason="manual_refresh",
            created_at=now,
        )

        self.assertEqual(snapshot.snapshot_id, "universe_001")
        self.assertEqual(snapshot.refresh_reason, "manual_refresh")
        self.assertEqual(repository.latest(), snapshot)
        self.assertEqual(repository.latest_for_symbol("BTC_USDT"), eligible)
        self.assertEqual(repository.latest_eligible_symbols(), ["BTC_USDT"])

    def test_latest_eligible_symbols_filters_non_eligible(self) -> None:
        repository = InMemoryUniverseSnapshotRepository()
        now = datetime.now(UTC)
        eligible = WhitelistedInstrument(
            symbol="BTC_USDT",
            listing_age_hours=500,
            spread_bps=1.0,
            volume_24h=2_000_000,
            open_interest=1_500_000,
            top_book_depth=400_000,
            eligibility_status=EligibilityStatus.ELIGIBLE,
            eligibility_reason="passes_phase2_rules",
            eligible_until=now + timedelta(minutes=30),
        )
        stale = WhitelistedInstrument(
            symbol="ETH_USDT",
            listing_age_hours=500,
            spread_bps=1.0,
            volume_24h=2_000_000,
            open_interest=1_500_000,
            top_book_depth=400_000,
            eligibility_status=EligibilityStatus.STALE,
            eligibility_reason="eligibility_window_expired",
            eligible_until=now - timedelta(minutes=1),
        )
        repository.append([eligible, stale], snapshot_id="universe_002", created_at=now)

        self.assertEqual(repository.latest_eligible_symbols(), ["BTC_USDT"])
        self.assertIsNone(repository.latest_for_symbol("SOL_USDT"))


if __name__ == "__main__":
    unittest.main()
