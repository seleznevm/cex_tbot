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


class WorkflowBranchTests(unittest.TestCase):
    def _proposal(self, proposal_id: str = "proposal_1", status: ProposalStatus = ProposalStatus.PENDING_APPROVAL, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        payload = dict(
            proposal_id=proposal_id,
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
            status=status,
        )
        payload.update(overrides)
        return TradeProposal(**payload)

    def _workflow(self, store: InMemoryProposalStore) -> TradeWorkflowService:
        approval = ApprovalFlow(store)
        journal = InMemoryExecutionJournal()
        state_store = InMemoryExecutionStateStore()
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService(), journal=journal, state_store=state_store)
        handoff = ApprovalExecutionHandoff(approval, execution)
        return TradeWorkflowService(approval, handoff, TradeTimelineBuilder(journal, state_store))

    def test_approve_only_keeps_pre_execution_status(self) -> None:
        store = InMemoryProposalStore()
        store.upsert(self._proposal())
        workflow = self._workflow(store)
        result = workflow.approve_only("Mike", "APPROVE proposal_1")
        self.assertIsNotNone(result.approval_only)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK)
        self.assertIsNotNone(result.report)

    def test_reject_and_report(self) -> None:
        store = InMemoryProposalStore()
        store.upsert(self._proposal())
        workflow = self._workflow(store)
        result = workflow.reject_and_report("Mike", "REJECT proposal_1")
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.REJECTED_BY_HUMAN)
        self.assertIsNotNone(result.report)

    def test_modify_revalidate_and_report(self) -> None:
        store = InMemoryProposalStore()
        store.upsert(self._proposal("proposal_1"))
        workflow = self._workflow(store)
        replacement = self._proposal("proposal_2")
        result = workflow.modify_revalidate_and_report("Mike", "MODIFY proposal_1: stop_loss=98.5", replacement)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.SUPERSEDED)
        self.assertEqual(store.get("proposal_2").status, ProposalStatus.PENDING_APPROVAL)
        self.assertIsNotNone(result.report)


if __name__ == "__main__":
    unittest.main()
