from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.risk_engine import PortfolioState
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


if __name__ == "__main__":
    unittest.main()
