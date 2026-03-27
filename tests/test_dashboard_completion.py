from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.audit import AuditEntry
from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import EligibilityReasonCode, EligibilityStatus, ProposalStatus, TradeDirection
from cex_tbot.execution import InMemoryExecutionJournal, InMemoryExecutionStateStore
from cex_tbot.risk_engine import PendingRiskBook, RiskEngine
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.universe import InMemoryUniverseSnapshotRepository, WhitelistedInstrument


class DashboardCompletionTests(unittest.TestCase):
    def test_dashboard_payload_contains_mvp_sections(self) -> None:
        session = TradeSessionStore(
            execution_journal=InMemoryExecutionJournal(),
            execution_state=InMemoryExecutionStateStore(),
        )
        now = datetime.now(UTC)
        proposal = TradeProposal(
            proposal_id="proposal_dashboard_1",
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
        session.operator_transcript.append(
            AuditEntry(actor="Mike", raw_command="APPROVE proposal_dashboard_1", outcome="APPROVE", proposal_id="proposal_dashboard_1")
        )
        session.system_state.activate_halt("manual-stop")

        pending_risk_book = PendingRiskBook()
        pending_risk_book.reserve("proposal_dashboard_pending", 0.2)
        risk_engine = RiskEngine(BotConfig(max_aggregate_open_risk_percent=1.0), pending_risk_book)
        service = TradingBackendService.from_session(session, risk_engine=risk_engine)

        universe_repository = InMemoryUniverseSnapshotRepository()
        universe_repository.append(
            [
                WhitelistedInstrument(
                    symbol="BTC_USDT",
                    eligibility_status=EligibilityStatus.ELIGIBLE,
                    eligibility_reason=EligibilityReasonCode.PASSES_PHASE2_RULES,
                    listing_age_hours=500,
                    volume_24h=2_000_000,
                    open_interest=1_000_000,
                    top_book_depth=400_000,
                )
            ],
            snapshot_id="universe_dashboard_1",
            refresh_reason="manual_refresh",
            created_at=now,
        )
        service.dashboard_builder.universe_repository = universe_repository

        payload = service.get_dashboard_payload()

        self.assertIn("kpis", payload)
        self.assertIn("risk", payload)
        self.assertIn("alerts", payload)
        self.assertIn("operator_activity", payload)
        self.assertIn("latest_trades", payload)
        self.assertIn("universe", payload)
        self.assertEqual(payload["kpis"]["pending_approvals"], 1)
        self.assertTrue(payload["risk"]["emergency_halt_active"])
        self.assertEqual(payload["risk"]["safety_state"], "HALTED")
        self.assertTrue(payload["risk"]["block_new_trades"])
        self.assertEqual(payload["risk"]["block_reason"], "manual-stop")
        self.assertTrue(any(item["code"] == "HALT_ACTIVE" for item in payload["alerts"]["items"]))
        self.assertEqual(payload["operator_activity"]["recent_items"][0]["proposal_id"], "proposal_dashboard_1")
        self.assertEqual(payload["latest_trades"][0]["proposal_id"], "proposal_dashboard_1")
        self.assertEqual(payload["universe"]["snapshot_id"], "universe_dashboard_1")
        self.assertEqual(payload["universe"]["eligible_symbols"], ["BTC_USDT"])


if __name__ == "__main__":
    unittest.main()
