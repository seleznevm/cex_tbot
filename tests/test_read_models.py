from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator, InMemoryExecutionJournal, InMemoryExecutionStateStore, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.operator_router import OperatorCommandRouter
from cex_tbot.read_models import QueryService
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.simulator import SimulatorService
from cex_tbot.workflow import TradeWorkflowService


class ReadModelTests(unittest.TestCase):
    def test_lists_and_details_trades(self) -> None:
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
        listing = query.list_trades()
        detail = query.get_trade_detail("proposal_1")

        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0].status, "EXECUTED")
        self.assertEqual(detail.proposal_id, "proposal_1")
        self.assertGreaterEqual(detail.timeline.event_count, 3)
        self.assertEqual(detail.operator_command_count, 1)


if __name__ == "__main__":
    unittest.main()
