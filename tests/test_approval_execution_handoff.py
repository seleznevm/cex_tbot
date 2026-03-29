from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.proposal_store import InMemoryProposalStore
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.simulator import SimulatorService


class ApprovalExecutionHandoffTests(unittest.TestCase):
    def _proposal(self, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        payload = dict(
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
        payload.update(overrides)
        return TradeProposal(**payload)

    def test_approve_and_execute_updates_status(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal()
        store.upsert(proposal)
        approval = ApprovalFlow(store)
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService())
        handoff = ApprovalExecutionHandoff(approval, execution)
        result = handoff.approve_and_execute("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=proposal.created_at)
        self.assertIsNotNone(result.execution)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.EXECUTED)

    def test_approve_but_pre_execution_reject_updates_status(self) -> None:
        store = InMemoryProposalStore()
        now = datetime.now(UTC)
        proposal = self._proposal(created_at=now - timedelta(minutes=10), expires_at=now - timedelta(minutes=1))
        store.upsert(proposal)
        approval = ApprovalFlow(store)
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService())
        handoff = ApprovalExecutionHandoff(approval, execution)
        result = handoff.approve_and_execute("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=now)
        self.assertIsNotNone(result.execution)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.REJECTED_PRE_EXECUTION)

    def test_reapprove_executed_proposal_does_not_execute_again(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal(status=ProposalStatus.EXECUTED)
        store.upsert(proposal)
        approval = ApprovalFlow(store)
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService())
        handoff = ApprovalExecutionHandoff(approval, execution)
        result = handoff.approve_and_execute("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=proposal.created_at)
        self.assertIsNone(result.execution)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.EXECUTED)


if __name__ == "__main__":
    unittest.main()
