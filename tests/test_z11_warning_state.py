from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, SafetyState, TradeDirection
from cex_tbot.risk_engine import PendingRiskBook, PortfolioState, RiskEngine
from cex_tbot.session_store import TradeSessionStore


class Z11WarningStateTests(unittest.TestCase):
    def test_warning_state_is_exposed_before_block(self) -> None:
        session = TradeSessionStore()
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_warn_1",
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
        session.proposals.upsert(proposal)
        risk_engine = RiskEngine(BotConfig(max_daily_drawdown_percent=2.0), PendingRiskBook())
        service = TradingBackendService.from_session(session, risk_engine=risk_engine)

        service.run_operator_command(
            "Mike",
            "APPROVE proposal_warn_1",
            PortfolioState(equity=1000.0, daily_drawdown_pct=1.7),
            now=now,
        )

        summary = service.get_session_summary_payload()
        dashboard = service.get_dashboard_payload()
        entries = service.session.operator_transcript.list_entries()

        self.assertEqual(summary["safety_state"], SafetyState.WARNING.value)
        self.assertFalse(summary["block_new_trades"])
        self.assertIn("daily drawdown nearing limit", summary["block_reason"])
        self.assertTrue(any(item["code"] == "WARN_DAILY_DRAWDOWN" for item in dashboard["alerts"]["items"]))
        self.assertTrue(any(entry.outcome == "AUTO_WARNING_ON" for entry in entries))


if __name__ == "__main__":
    unittest.main()
