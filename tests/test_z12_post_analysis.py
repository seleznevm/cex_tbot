from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.session_store import TradeSessionStore


class Z12PostAnalysisTests(unittest.TestCase):
    def test_post_analysis_summarizes_trades_and_no_trades(self) -> None:
        session = TradeSessionStore()
        service = TradingBackendService.from_session(session)
        now = datetime.now(UTC)

        executed = TradeProposal(
            proposal_id="proposal_exec",
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
            confidence_score=0.82,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.EXECUTED,
        )
        rejected = TradeProposal(
            proposal_id="proposal_reject",
            agent_name="Luma",
            strategy_id="breakout",
            strategy_version="v1",
            market_context_id="ctx_2",
            symbol="ETH_USDT",
            timeframe="15m",
            direction=TradeDirection.SHORT,
            entry_zone_min=199.0,
            entry_zone_max=200.0,
            entry_split=[EntrySplitLeg(1, 200.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=201.0,
            take_profit_1=197.0,
            take_profit_2=195.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=10.0,
            confidence_score=0.74,
            thesis="rejection setup",
            invalidity_condition="range breaks up",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.REJECTED_PRE_EXECUTION,
        )
        pending = TradeProposal(
            proposal_id="proposal_pending",
            agent_name="Luma",
            strategy_id="trend",
            strategy_version="v1",
            market_context_id="ctx_3",
            symbol="BTC_USDT",
            timeframe="5m",
            direction=TradeDirection.LONG,
            entry_zone_min=101.0,
            entry_zone_max=102.0,
            entry_split=[EntrySplitLeg(1, 101.5, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=100.0,
            take_profit_1=103.0,
            take_profit_2=104.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=10.0,
            confidence_score=0.69,
            thesis="pending idea",
            invalidity_condition="fails reclaim",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.PENDING_APPROVAL,
        )
        service.submit_proposal(executed)
        service.submit_proposal(rejected)
        service.submit_proposal(pending)

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
                market_context_id="ctx_nt_1",
                liquidity_check="ok",
                data_freshness_ms=100,
            )
        )

        payload = service.get_post_analysis_payload()

        self.assertEqual(payload["total_trades"], 3)
        self.assertEqual(payload["executed_trades"], 1)
        self.assertEqual(payload["rejected_trades"], 1)
        self.assertEqual(payload["pending_trades"], 1)
        self.assertEqual(payload["no_trade_decisions"], 1)
        self.assertIn("REJECTED_PRE_EXECUTION", payload["top_rejection_statuses"])
        self.assertIn("CONFIDENCE_BELOW_THRESHOLD", payload["no_trade_reason_counts"])
        self.assertIn("BTC_USDT", payload["symbol_activity"])
        self.assertGreater(len(payload["calibration_hints"]), 0)


if __name__ == "__main__":
    unittest.main()
