from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.universe import InMemoryUniverseSnapshotRepository, UniverseRefreshPolicy, WhitelistedInstrument


class UniverseRefreshPolicyTests(unittest.TestCase):
    def test_requests_refresh_without_snapshot(self) -> None:
        policy = UniverseRefreshPolicy(refresh_interval_minutes=60)
        decision = policy.should_refresh(None)
        self.assertTrue(decision.should_refresh)

    def test_respects_refresh_interval(self) -> None:
        repo = InMemoryUniverseSnapshotRepository()
        now = datetime.now(UTC)
        repo.append([WhitelistedInstrument(symbol="BTC_USDT", eligible_until=now + timedelta(minutes=30))], snapshot_id="snap_1", created_at=now - timedelta(minutes=61))
        policy = UniverseRefreshPolicy(refresh_interval_minutes=60)
        decision = policy.should_refresh(repo.latest(), now=now)
        self.assertTrue(decision.should_refresh)


if __name__ == "__main__":
    unittest.main()
