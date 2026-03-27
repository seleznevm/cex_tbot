from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.dashboard_models import DashboardBuilder
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator, InMemoryExecutionJournal, InMemoryExecutionStateStore, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.operator_router import OperatorCommandRouter
from cex_tbot.read_models import QueryService
from cex_tbot.risk_engine import PendingRiskBook, PortfolioState, RiskEngine
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.simulator import SimulatorService
from cex_tbot.workflow import TradeWorkflowService


class DashboardModelTests(unittest.TestCase):
    def test_builds_dashboard_widgets(self) -> None:
        session = TradeSessionStore(
            execution_journal=InMemoryExecutionJournal(),
            execution_state=InMemoryExecutionStateStore(),
        )
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
        session.proposals.upsert(proposal)
        approval = ApprovalFlow(session.proposals)
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService(), journal=session.execution_journal, state_store=session.execution_state)
        handoff = ApprovalExecutionHandoff(approval, execution)
        workflow = TradeWorkflowService(approval, handoff, TradeTimelineBuilder(session.execution_journal, session.execution_state))
        router = OperatorCommandRouter(workflow, approval, transcript=session.operator_transcript)
        router.route("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=now)
        query = QueryService(session, TradeTimelineBuilder(session.execution_journal, session.execution_state))
        pending_risk_book = PendingRiskBook()
        pending_risk_book.reserve("proposal_pending", 0.2)
        session.system_state.activate_halt("manual-stop")
        dashboard = DashboardBuilder(session, query, config=BotConfig(max_aggregate_open_risk_percent=1.0), pending_risk_book=pending_risk_book).build()
        self.assertEqual(dashboard.kpis.total_proposals, 1)
        self.assertEqual(dashboard.kpis.pending_approvals, 0)
        self.assertEqual(dashboard.kpis.executed_proposals, 1)
        self.assertEqual(dashboard.kpis.status_breakdown["EXECUTED"], 1)
        self.assertEqual(dashboard.operator_activity.command_count, 1)
        self.assertEqual(dashboard.operator_activity.recent_items[0].actor, "Mike")
        self.assertEqual(dashboard.operator_activity.recent_items[0].proposal_id, "proposal_1")
        self.assertEqual(len(dashboard.latest_trades), 1)
        self.assertEqual(dashboard.latest_trades[0].created_at, proposal.created_at.isoformat())
        self.assertTrue(dashboard.risk.emergency_halt_active)
        self.assertEqual(dashboard.risk.halt_reason, "manual-stop")
        self.assertEqual(dashboard.risk.max_open_risk_percent, 1.0)
        self.assertEqual(dashboard.risk.reserved_pending_risk_percent, 0.2)
        self.assertEqual(dashboard.risk.active_risk_percent, 0.5)
        self.assertEqual(dashboard.risk.free_risk_budget_percent, 0.3)
        self.assertTrue(any(item.code == "HALT_ACTIVE" for item in dashboard.alerts.items))


if __name__ == "__main__":
    unittest.main()
