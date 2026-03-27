from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.session_store import TradeSessionStore


class BotDispatcherTests(unittest.TestCase):
    def test_dispatcher_routes_new_operator_commands(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        dispatcher = BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig()))

        self.assertIn("Post-analysis and calibration review snapshot", dispatcher.dispatch("/post_analysis").text)
        self.assertIn("Safety status", dispatcher.dispatch("/safety").text)
        self.assertIn("Gate demo transport status", dispatcher.dispatch("/gate_demo_status").text)
        self.assertIn("Safety cleared", dispatcher.dispatch("/clear_safety").text)

    def test_dispatcher_routes_trade_commands(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        adapter = BotCommandAdapter(service)
        dispatcher = BotCommandDispatcher(adapter)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_dispatch",
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=99.0,
            take_profit_1=101.0,
            take_profit_2=102.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=10.0,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.PENDING_APPROVAL,
        )
        service.submit_proposal(proposal)

        self.assertIn("Trade detail", dispatcher.dispatch("/detail proposal_dispatch").text)
        self.assertIn("Approval processed for proposal_dispatch", dispatcher.dispatch("/approve_only proposal_dispatch").text)
        self.assertIn("Report for proposal_dispatch", dispatcher.dispatch("/report proposal_dispatch").text)
        self.assertIn("Reject processed for proposal_dispatch", dispatcher.dispatch("/reject proposal_dispatch").text)

    def test_dispatcher_handles_usage_and_unknown(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        dispatcher = BotCommandDispatcher(BotCommandAdapter(service))

        self.assertIn("Usage: /detail", dispatcher.dispatch("/detail").text)
        self.assertIn("Unknown command", dispatcher.dispatch("hello there").text)


if __name__ == "__main__":
    unittest.main()
