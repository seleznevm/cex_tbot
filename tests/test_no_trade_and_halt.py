from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.risk_engine import PortfolioState
from cex_tbot.session_store import TradeSessionStore


class NoTradeAndHaltTests(unittest.TestCase):
    def test_session_summary_counts_no_trade_decisions(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
        service.submit_no_trade_decision(
            NoTradeDecision(
                agent_name="Luma",
                strategy_id="breakout",
                strategy_version="v1",
                symbol="BTC_USDT",
                timeframe="15m",
                confidence_score=0.39,
                reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
                reason_text="below threshold",
                market_context_id="ctx_1",
                liquidity_check="ok",
                data_freshness_ms=100,
            )
        )
        summary = service.get_session_summary_payload()
        self.assertEqual(summary["total_no_trade_decisions"], 1)

    def test_emergency_halt_blocks_operator_commands(self) -> None:
        service = TradingBackendService.from_session(TradeSessionStore())
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
        service.activate_emergency_halt("manual safety stop")
        rendered = service.run_operator_command("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=now)
        self.assertIn("Emergency halt active", rendered.text)
        self.assertTrue(service.get_session_summary_payload()["emergency_halt_active"])


if __name__ == "__main__":
    unittest.main()
