from __future__ import annotations

from dataclasses import dataclass
import unittest

from cex_tbot.bootstrap import build_app
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.market_data import GateInstrumentRecord, StaticGateInstrumentFetcher


@dataclass(frozen=True)
class StaticDemoFetcher:
    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        return [
            GateInstrumentRecord(
                name="BTC_USDT",
                trade_status="active",
                is_new_listing=False,
                listing_age_hours=500,
                quote_asset="USDT",
                volume_24h=2_000_000,
                open_interest=1_000_000,
                spread_bps=4.0,
                top_book_depth=400_000,
            )
        ]


class GateDemoOperatorCommandTests(unittest.TestCase):
    def test_runtime_and_session_commands(self) -> None:
        app = build_app(storage_dir=".runtime/test-gate-ops")
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        self.assertIn("Runtime status", dispatcher.dispatch("/runtime_status").text)
        self.assertIn("Session paths", dispatcher.dispatch("/session_paths").text)

    def test_refresh_universe_with_static_fetcher(self) -> None:
        app = build_app(config=BotConfig(execution_mode="paper_sim"), instrument_fetcher=StaticDemoFetcher())
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        reply = dispatcher.dispatch("/refresh_universe")

        self.assertIn("Universe refresh complete", reply.text)
        self.assertIn("snapshot_id=operator_refresh_", reply.text)

    def test_refresh_universe_reports_transport_failure_cleanly_in_gate_demo_mode(self) -> None:
        app = build_app(config=BotConfig(execution_mode="gate_demo", gate_demo_api="https://demo.gate"))
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        reply = dispatcher.dispatch("/refresh_universe")

        self.assertIn("Universe refresh unavailable", reply.text)
        self.assertIn("Gate demo metadata fetch failed", reply.text)


if __name__ == "__main__":
    unittest.main()
