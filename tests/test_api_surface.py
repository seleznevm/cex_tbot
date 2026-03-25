from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.api_surface import ApiSurface, CommandRequest, ProposalSubmitRequest
from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.session_store import TradeSessionStore


class ApiSurfaceTests(unittest.TestCase):
    def test_submit_and_command_via_api_surface(self) -> None:
        backend = TradingBackendService.from_session(TradeSessionStore())
        api = ApiSurface(backend)
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
        submit = api.submit_proposal(ProposalSubmitRequest(proposal))
        self.assertEqual(submit["proposal_id"], "proposal_1")
        cmd = api.command(CommandRequest(actor="Mike", command="APPROVE proposal_1", portfolio_equity=1000.0, now=now))
        self.assertEqual(cmd["mode"], "plain")
        trades = api.list_trades()
        self.assertEqual(len(trades), 1)
        detail = api.trade_detail("proposal_1")
        report = api.trade_report("proposal_1")
        summary = api.session_summary()
        self.assertEqual(detail["proposal_id"], "proposal_1")
        self.assertIn("Trade Report", report["text"])
        self.assertEqual(summary["executed_proposals"], 1)

    def test_execute_approved_proposal_via_api_surface(self) -> None:
        backend = TradingBackendService.from_session(TradeSessionStore())
        api = ApiSurface(backend)
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_2",
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_2",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=98.5,
            take_profit_1=101.5,
            take_profit_2=103.0,
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
        api.submit_proposal(ProposalSubmitRequest(proposal))
        api.command(
            CommandRequest(
                actor="Mike",
                command="APPROVE proposal_2",
                portfolio_equity=1000.0,
                execute_on_approve=False,
                now=now,
            )
        )
        execution = api.execute_approved_proposal(
            "proposal_2",
            actor="Mike",
            portfolio_equity=1000.0,
            now=now,
        )
        detail = api.trade_detail("proposal_2")
        self.assertEqual(execution["mode"], "plain")
        self.assertEqual(detail["status"], "EXECUTED")


if __name__ == "__main__":
    unittest.main()
