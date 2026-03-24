import unittest

from cex_tbot.market_data import GateInstrumentMetadataAdapter, GateInstrumentRecord


class GateMetadataAdapterTests(unittest.TestCase):
    def test_normalizes_tradable_gate_record(self) -> None:
        adapter = GateInstrumentMetadataAdapter()
        instrument = adapter.normalize_record(
            GateInstrumentRecord(
                name="BTC_USDT",
                trade_status="tradable",
                listing_age_hours=240,
                volume_24h=2_000_000,
                open_interest=1_500_000,
                spread_bps=1.2,
                top_book_depth=400_000,
            )
        )
        self.assertEqual(instrument.symbol, "BTC_USDT")
        self.assertEqual(instrument.status, "active")
        self.assertEqual(instrument.quote_asset, "USDT")

    def test_marks_delisting_as_non_active(self) -> None:
        adapter = GateInstrumentMetadataAdapter()
        instrument = adapter.normalize_record(
            GateInstrumentRecord(
                name="ETH_USDT",
                in_delisting=True,
                trade_status="tradable",
            )
        )
        self.assertEqual(instrument.status, "delisting")


if __name__ == "__main__":
    unittest.main()
