from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.session_store import TradeSessionStore


class BotAdapterTests(unittest.TestCase):
    def test_help_status_and_dashboard(self) -> None:
        adapter = BotCommandAdapter(TradingBackendService.from_session(TradeSessionStore()))
        self.assertIn("/help", adapter.handle_help().text)
        self.assertIn("/post_analysis", adapter.handle_help().text)
        self.assertIn("/clear_safety", adapter.handle_help().text)
        self.assertIn("Session Summary", adapter.handle_status().text)
        self.assertIn("Dashboard", adapter.handle_dashboard().text)

    def test_approve_report_and_no_trade_views(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        adapter = BotCommandAdapter(service)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_1",
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
        service.submit_no_trade_decision(
            NoTradeDecision(
                agent_name="Luma",
                strategy_id="pullback",
                strategy_version="v1",
                symbol="ETH_USDT",
                timeframe="15m",
                confidence_score=0.4,
                reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
                reason_text="below threshold",
                market_context_id="ctx_2",
                liquidity_check="ok",
                data_freshness_ms=100,
            )
        )

        approved = adapter.handle_approve("proposal_1")
        rejected = adapter.handle_reject("proposal_1")
        modified = adapter.handle_modify("proposal_1", "stop_loss=98.5, thesis=clean retest")
        report = adapter.handle_report("proposal_1")
        pending = adapter.handle_pending()
        expired = adapter.handle_expired()
        detail = adapter.handle_detail("proposal_1")
        post_analysis = adapter.handle_post_analysis()
        no_trades = adapter.handle_no_trades()

        self.assertEqual(approved.parse_mode, "Markdown")
        self.assertIn("Approval processed for proposal_1", approved.text)
        self.assertIn("Reject processed for proposal_1", rejected.text)
        self.assertIn("Modify processed for proposal_1", modified.text)
        self.assertIn("Pending proposals", pending.text)
        self.assertIn("Expired proposals", expired.text)
        self.assertEqual(report.parse_mode, "Markdown")
        self.assertIn("Report for proposal_1", report.text)
        self.assertIn("**Trade Report", report.text)
        self.assertIn("Trade detail", detail.text)
        self.assertIn("Post-analysis and calibration review snapshot", post_analysis.text)
        self.assertIn("No-trade decisions", no_trades.text)

    def test_halt_blocks_approve(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        adapter = BotCommandAdapter(service)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_2",
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
        adapter.handle_halt("manual stop")
        blocked = adapter.handle_approve("proposal_2")
        self.assertIn("Emergency halt active", blocked.text)
        self.assertIn("Safety status", adapter.handle_safety().text)
        self.assertIn("inactive", BotCommandAdapter(service, config=BotConfig()).handle_gate_demo_status().text)
        self.assertIn("cleared", adapter.handle_unhalt().text)

    def test_missing_proposal_returns_diagnostic_reply_instead_of_keyerror(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        adapter = BotCommandAdapter(service)

        approve = adapter.handle_approve("proposal_missing_1")
        execute = adapter.handle_execute("proposal_missing_1")
        detail = adapter.handle_detail("proposal_missing_1")
        report = adapter.handle_report("proposal_missing_1")
        modify = adapter.handle_modify("proposal_missing_1", "stop_loss=98.5")
        sync = adapter.handle_demo_sync("proposal_missing_1")

        for reply in (approve, execute, detail, report, modify):
            self.assertIn("Proposal not found: proposal_missing_1", reply.text)
            self.assertIn("runtime_store=missing proposal_id", reply.text)

        self.assertIn("Gate demo sync", sync.text)
        self.assertIn("demo_orders=none", sync.text)


if __name__ == "__main__":
    unittest.main()
