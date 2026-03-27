from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.session_store import TradeSessionStore


class Z12CompletionTests(unittest.TestCase):
    def test_z12_surface_is_available_for_review_and_calibration(self) -> None:
        session = TradeSessionStore()
        service = TradingBackendService.from_session(session)
        now = datetime.now(UTC)

        executed = TradeProposal(
            proposal_id="proposal_z12_exec",
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
            proposal_id="proposal_z12_reject",
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
            confidence_score=0.51,
            thesis="rejection setup",
            invalidity_condition="range breaks up",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.REJECTED_PRE_EXECUTION,
        )
        service.submit_proposal(executed)
        service.submit_proposal(rejected)
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
        dashboard = service.get_dashboard_payload()
        text = service.get_post_analysis_text()

        self.assertIn("outcome_matrix", payload)
        self.assertIn("recommendations", payload)
        self.assertIn("trend_hint", payload)
        self.assertGreater(len(payload["recommendations"]), 0)
        self.assertIn("review snapshot", text)
        self.assertIn("post_analysis", dashboard)
        self.assertGreaterEqual(len(dashboard["post_analysis"]["recommendations"]), 1)

        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.json"
            second = Path(tmp) / "second.json"
            first.write_text(json.dumps(payload), encoding="utf-8")
            service.submit_no_trade_decision(
                NoTradeDecision(
                    agent_name="Luma",
                    strategy_id="scalp",
                    strategy_version="v1",
                    symbol="SOL_USDT",
                    timeframe="5m",
                    confidence_score=0.35,
                    reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
                    reason_text="below threshold again",
                    market_context_id="ctx_nt_2",
                    liquidity_check="ok",
                    data_freshness_ms=100,
                )
            )
            second.write_text(json.dumps(service.get_post_analysis_payload()), encoding="utf-8")
            first_payload = json.loads(first.read_text(encoding="utf-8"))
            second_payload = json.loads(second.read_text(encoding="utf-8"))
            self.assertLess(first_payload["no_trade_decisions"], second_payload["no_trade_decisions"])


if __name__ == "__main__":
    unittest.main()
