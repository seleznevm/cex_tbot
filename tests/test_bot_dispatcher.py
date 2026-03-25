from __future__ import annotations

import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.session_store import TradeSessionStore


class BotDispatcherTests(unittest.TestCase):
    def test_help_and_unknown_paths(self) -> None:
        dispatcher = BotCommandDispatcher(BotCommandAdapter(TradingBackendService.from_session(TradeSessionStore())))
        self.assertIn("/help", dispatcher.dispatch("/help").text)
        self.assertIn("Unknown command", dispatcher.dispatch("hello").text)

    def test_seed_and_query_demo_flow(self) -> None:
        dispatcher = BotCommandDispatcher(BotCommandAdapter(TradingBackendService.from_session(TradeSessionStore())))
        self.assertIn("Proposal stored", dispatcher.dispatch("/seed_demo").text)
        self.assertIn("Latest trades", dispatcher.dispatch("/list").text)
        self.assertIn("Trade detail", dispatcher.dispatch("/detail proposal_demo_btc_breakout").text)
        self.assertIn("**Trade Report", dispatcher.dispatch("/report proposal_demo_btc_breakout").text)

    def test_no_trade_and_halt_commands(self) -> None:
        dispatcher = BotCommandDispatcher(BotCommandAdapter(TradingBackendService.from_session(TradeSessionStore())))
        self.assertIn("No-trade stored", dispatcher.dispatch("/seed_no_trade").text)
        self.assertIn("No-trade decisions", dispatcher.dispatch("/no_trades").text)
        self.assertIn("activated", dispatcher.dispatch("/halt manual stop").text)
        self.assertIn("cleared", dispatcher.dispatch("/unhalt").text)


if __name__ == "__main__":
    unittest.main()
