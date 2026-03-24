from datetime import UTC, datetime
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.market_data import GateInstrumentRecord, StaticGateInstrumentFetcher
from cex_tbot.universe import InMemoryUniverseSnapshotRepository, RawInstrument, UniverseService
from cex_tbot.universe.orchestrator import UniverseRefreshOrchestrator


class UniverseOrchestratorTests(unittest.TestCase):
    def test_refresh_from_gate_records_builds_snapshot_and_result(self) -> None:
        orchestrator = UniverseRefreshOrchestrator(
            service=UniverseService(BotConfig(whitelist_size=2)),
            repository=InMemoryUniverseSnapshotRepository(),
        )
        now = datetime.now(UTC)
        result = orchestrator.refresh_from_gate_records(
            [
                GateInstrumentRecord(
                    name="BTC_USDT",
                    trade_status="tradable",
                    listing_age_hours=400,
                    volume_24h=2_000_000,
                    open_interest=1_500_000,
                    spread_bps=1.0,
                    top_book_depth=300_000,
                ),
                GateInstrumentRecord(
                    name="NEW_USDT",
                    trade_status="tradable",
                    is_new_listing=True,
                    listing_age_hours=12,
                    volume_24h=500_000,
                    open_interest=400_000,
                    spread_bps=1.5,
                    top_book_depth=100_000,
                ),
            ],
            snapshot_id="snap_001",
            refresh_reason="scheduled_refresh",
            created_at=now,
        )

        self.assertEqual(result.snapshot_id, "snap_001")
        self.assertEqual(result.total_symbols_seen, 2)
        self.assertEqual(result.eligible_count, 1)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.top_whitelist_symbols, ("BTC_USDT",))
        self.assertEqual(result.snapshot.snapshot_id, "snap_001")
        self.assertEqual(len(result.snapshot.instruments), 2)

    def test_refresh_from_raw_instruments_uses_existing_universe_service(self) -> None:
        orchestrator = UniverseRefreshOrchestrator(
            service=UniverseService(BotConfig(whitelist_size=1)),
            repository=InMemoryUniverseSnapshotRepository(),
        )
        result = orchestrator.refresh_from_raw_instruments(
            [
                RawInstrument(
                    symbol="ETH_USDT",
                    listing_age_hours=500,
                    volume_24h=1_000_000,
                    open_interest=900_000,
                    spread_bps=2.0,
                    top_book_depth=200_000,
                )
            ],
            snapshot_id="snap_002",
        )

        self.assertEqual(result.eligible_count, 1)
        self.assertEqual(result.rejected_count, 0)
        self.assertEqual(result.top_whitelist_symbols, ("ETH_USDT",))
        self.assertIsNotNone(orchestrator.repository.latest())

    def test_refresh_from_fetcher_uses_fetch_contract(self) -> None:
        orchestrator = UniverseRefreshOrchestrator(
            service=UniverseService(BotConfig(whitelist_size=2)),
            repository=InMemoryUniverseSnapshotRepository(),
        )
        fetcher = StaticGateInstrumentFetcher.from_iterable(
            [
                GateInstrumentRecord(
                    name="BTC_USDT",
                    trade_status="tradable",
                    listing_age_hours=300,
                    volume_24h=2_000_000,
                    open_interest=1_500_000,
                    spread_bps=1.0,
                    top_book_depth=300_000,
                )
            ]
        )

        result = orchestrator.refresh_from_fetcher(fetcher, snapshot_id="snap_003")

        self.assertEqual(result.snapshot_id, "snap_003")
        self.assertEqual(result.eligible_count, 1)
        self.assertEqual(result.top_whitelist_symbols, ("BTC_USDT",))


if __name__ == "__main__":
    unittest.main()
