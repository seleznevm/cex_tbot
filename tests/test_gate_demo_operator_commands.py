from __future__ import annotations

from dataclasses import dataclass
import unittest

from cex_tbot.bootstrap import build_app
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.market_data import GateInstrumentRecord


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


class _HealthyDemoClient:
    def list_instruments(self) -> list[GateInstrumentRecord]:
        return [GateInstrumentRecord(name="BTC_USDT", trade_status="tradable", listing_age_hours=500, volume_24h=1_000_000, open_interest=500_000, spread_bps=4.0, top_book_depth=300_000)]

    def healthcheck(self) -> dict[str, object]:
        return {"ok": True, "endpoint": "https://demo.gate/futures/usdt/contracts", "contracts_seen": 1}

    def account_status(self) -> dict[str, object]:
        return {"ok": True, "endpoint": "https://demo.gate/futures/usdt/accounts", "currency": "USDT", "available": "1000", "total": "1000"}

    def balance_snapshot(self) -> dict[str, object]:
        return {"currency": "USDT", "available": "1000", "total": "1000"}

    def positions_snapshot(self) -> list[dict[str, object]]:
        return [{"contract": "BTC_USDT", "size": 1, "entry_price": "100", "mark_price": "101", "unrealised_pnl": "1"}]

    def open_orders(self) -> list[dict[str, object]]:
        return [{"id": "42", "contract": "BTC_USDT", "size": 1, "price": "100", "status": "open", "tif": "gtc"}]

    def order_status(self, order_id: str) -> dict[str, object]:
        return {"id": order_id, "contract": "BTC_USDT", "size": 1, "price": "100", "status": "open", "left": 1, "fill_price": None}

    def place_test_order(self, contract: str, *, size: float, side: str) -> dict[str, object]:
        normalized = 465 if contract == "BTC_USDT" else int(size)
        return {"id": "99", "contract": contract, "side": side, "size": normalized if side == "buy" else -normalized, "normalized_contracts": normalized, "status": "open"}

    def place_trigger_order(self, contract: str, *, trigger_price: float, order_price: float, size: int, side: str, reduce_only: bool = True, text: str = "cex_tbot_trigger") -> dict[str, object]:
        return {"id": f"{text}-1", "contract": contract, "side": side, "size": size, "trigger_price": trigger_price, "order_price": order_price, "reduce_only": reduce_only, "status": "open"}

    def trigger_order_status(self, order_id: str) -> dict[str, object]:
        return {"id": order_id, "contract": "BTC_USDT", "size": -465, "price": "99", "status": "open", "reduce_only": True, "trigger_price": "99"}

    def cancel_order(self, order_id: str) -> dict[str, object]:
        return {"id": order_id, "status": "cancelled"}


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
        self.assertTrue("Gate demo metadata fetch failed" in reply.text or "gate-api package is required" in reply.text)

    def test_demo_health_and_capabilities_commands(self) -> None:
        app = build_app(
            config=BotConfig(execution_mode="gate_demo", gate_demo_api="https://demo.gate"),
            gate_demo_client=_HealthyDemoClient(),
        )
        dispatcher = BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app))

        self.assertIn("Gate demo health", dispatcher.dispatch("/demo_health").text)
        self.assertIn("contracts_seen=1", dispatcher.dispatch("/demo_health").text)
        self.assertIn("Gate demo account status", dispatcher.dispatch("/demo_account_status").text)
        self.assertIn("available=1000", dispatcher.dispatch("/demo_account_status").text)
        self.assertIn("Gate demo balance", dispatcher.dispatch("/demo_balance").text)
        self.assertIn("Gate demo positions", dispatcher.dispatch("/demo_positions").text)
        self.assertIn("Gate demo open orders", dispatcher.dispatch("/demo_open_orders").text)
        self.assertIn("Gate demo order status", dispatcher.dispatch("/demo_order_status 42").text)
        self.assertIn("Gate demo test order", dispatcher.dispatch("/demo_place_test_order BTC_USDT buy").text)
        self.assertIn("Gate demo cancel order", dispatcher.dispatch("/demo_cancel_order 42").text)
        self.assertIn("BTC_USDT", dispatcher.dispatch("/demo_account_overview").text)
        self.assertIn("Gate demo capabilities", dispatcher.dispatch("/demo_capabilities").text)


if __name__ == "__main__":
    unittest.main()
