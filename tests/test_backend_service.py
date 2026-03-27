from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.risk_engine import PendingRiskBook, PortfolioState, RiskEngine
from cex_tbot.session_store import TradeSessionStore


class BackendServiceTests(unittest.TestCase):
    def test_submit_command_report_and_summary(self) -> None:
        session = TradeSessionStore()
        service = TradingBackendService.from_session(session)
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
        rendered = service.run_operator_command("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=now)
        self.assertIn("Trade Report", rendered.text)
        report = service.get_trade_report("proposal_1")
        self.assertEqual(report.proposal_id, "proposal_1")
        summary = service.get_session_summary()
        self.assertEqual(summary.total_proposals, 1)
        self.assertEqual(summary.executed_proposals, 1)

    def test_trade_detail_exposes_extended_fields(self) -> None:
        session = TradeSessionStore()
        service = TradingBackendService.from_session(session)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_2",
            agent_name="Luma",
            strategy_id="reclaim",
            strategy_version="v2",
            market_context_id="ctx_2",
            symbol="ETH_USDT",
            timeframe="1h",
            direction=TradeDirection.SHORT,
            entry_zone_min=2000.0,
            entry_zone_max=2015.0,
            entry_split=[EntrySplitLeg(1, 2008.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=2030.0,
            take_profit_1=1980.0,
            take_profit_2=1960.0,
            risk_percent=0.5,
            risk_usd=25.0,
            position_size=1.5,
            confidence_score=0.77,
            thesis="local failure into resistance",
            invalidity_condition="acceptance above local supply",
            liquidity_check="spread ok",
            data_freshness_ms=250,
            created_at=now,
            expires_at=now + timedelta(minutes=20),
            status=ProposalStatus.PENDING_APPROVAL,
        )
        service.submit_proposal(proposal)
        detail = service.get_trade_detail_payload("proposal_2")
        self.assertEqual(detail["agent_name"], "Luma")
        self.assertEqual(detail["strategy_id"], "reclaim")
        self.assertEqual(detail["entry_zone_min"], 2000.0)
        self.assertIn("created_at", detail)

    def test_trade_report_text_supports_operator_mode(self) -> None:
        session = TradeSessionStore()
        service = TradingBackendService.from_session(session)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_3",
            agent_name="Luma",
            strategy_id="breakout",
            strategy_version="v1",
            market_context_id="ctx_3",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=100.0,
            entry_zone_max=101.0,
            entry_split=[EntrySplitLeg(1, 100.5, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=99.0,
            take_profit_1=102.0,
            take_profit_2=103.0,
            risk_percent=0.5,
            risk_usd=10.0,
            position_size=2.0,
            confidence_score=0.81,
            thesis="trend continuation",
            invalidity_condition="range failure",
            liquidity_check="good",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=20),
            status=ProposalStatus.PENDING_APPROVAL,
        )
        service.submit_proposal(proposal)
        text = service.get_trade_report_text("proposal_3", render_mode="operator")
        self.assertIn("Invalidation:", text)
        self.assertIn("\n\nTimeline events:", text)


    def test_dashboard_payload_exposes_halt_reason(self) -> None:
        session = TradeSessionStore()
        pending_risk_book = PendingRiskBook()
        risk_engine = RiskEngine(BotConfig(max_aggregate_open_risk_percent=1.0), pending_risk_book)
        service = TradingBackendService.from_session(session, risk_engine=risk_engine)
        session.system_state.activate_halt("manual-stop")
        pending_risk_book.reserve("proposal_pending", 0.2)

        payload = service.get_dashboard_payload()

        self.assertTrue(payload["risk"]["emergency_halt_active"])
        self.assertEqual(payload["risk"]["halt_reason"], "manual-stop")
        self.assertEqual(payload["risk"]["max_open_risk_percent"], 1.0)
        self.assertEqual(payload["risk"]["reserved_pending_risk_percent"], 0.2)
        self.assertEqual(payload["risk"]["active_risk_percent"], 0.0)
        self.assertEqual(payload["risk"]["free_risk_budget_percent"], 0.8)
        self.assertEqual(payload["kpis"]["pending_approvals"], 0)
        self.assertEqual(payload["kpis"]["status_breakdown"], {})
        self.assertIn("latest_outcomes", payload["operator_activity"])
        self.assertIsInstance(payload["operator_activity"]["latest_outcomes"], list)


if __name__ == "__main__":
    unittest.main()
