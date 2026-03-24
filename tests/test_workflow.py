from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator, InMemoryExecutionJournal, InMemoryExecutionStateStore, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.proposal_store import InMemoryProposalStore
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.simulator import SimulatorService
from cex_tbot.workflow import TradeWorkflowService


class WorkflowTests(unittest.TestCase):
    def test_approve_execute_and_report(self) -> None:
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
        store = InMemoryProposalStore()
        store.upsert(proposal)
        approval = ApprovalFlow(store)
        journal = InMemoryExecutionJournal()
        state_store = InMemoryExecutionStateStore()
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService(), journal=journal, state_store=state_store)
        handoff = ApprovalExecutionHandoff(approval, execution)
        workflow = TradeWorkflowService(approval, handoff, TradeTimelineBuilder(journal, state_store))
        result = workflow.approve_execute_and_report("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=now)
        self.assertIsNotNone(result.report)
        assert result.report is not None
        self.assertIn("Trade Report", result.report.to_text())
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.EXECUTED)


if __name__ == "__main__":
    unittest.main()
