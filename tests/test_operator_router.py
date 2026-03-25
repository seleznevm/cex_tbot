from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator, InMemoryExecutionJournal, InMemoryExecutionStateStore, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.operator_router import OperatorCommandRouter
from cex_tbot.proposal_store import InMemoryProposalStore
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.simulator import SimulatorService
from cex_tbot.workflow import TradeWorkflowService


class OperatorRouterTests(unittest.TestCase):
    def _proposal(self, proposal_id: str = "proposal_1") -> TradeProposal:
        now = datetime.now(UTC)
        return TradeProposal(
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
            status=ProposalStatus.PENDING_APPROVAL,
        )

    def _router(self, store: InMemoryProposalStore) -> OperatorCommandRouter:
        approval = ApprovalFlow(store)
        journal = InMemoryExecutionJournal()
        state_store = InMemoryExecutionStateStore()
        execution = ExecutionOrchestrator(RiskEngine(BotConfig()), SimulatorService(), journal=journal, state_store=state_store)
        handoff = ApprovalExecutionHandoff(approval, execution)
        workflow = TradeWorkflowService(approval, handoff, TradeTimelineBuilder(journal, state_store))
        return OperatorCommandRouter(workflow, approval)

    def test_routes_approve_for_execution(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal()
        store.upsert(proposal)
        response = self._router(store).route("Mike", "APPROVE proposal_1", PortfolioState(equity=1000.0), now=proposal.created_at)
        self.assertIn("Trade Report", response.text)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.EXECUTED)

    def test_routes_reject_with_report(self) -> None:
        store = InMemoryProposalStore()
        store.upsert(self._proposal())
        response = self._router(store).route("Mike", "REJECT proposal_1", PortfolioState(equity=1000.0), execute_on_approve=False)
        self.assertIn("Trade Report", response.text)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.REJECTED_BY_HUMAN)

    def test_requires_replacement_for_modify(self) -> None:
        store = InMemoryProposalStore()
        store.upsert(self._proposal())
        response = self._router(store).route("Mike", "MODIFY proposal_1: stop_loss=98.5", PortfolioState(equity=1000.0))
        self.assertIn("requires replacement proposal", response.text)

    def test_renders_operator_mode_with_spacing(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal()
        store.upsert(proposal)
        response = self._router(store).route(
            "Mike",
            "APPROVE proposal_1",
            PortfolioState(equity=1000.0),
            now=proposal.created_at,
            render_mode="operator",
        )
        self.assertIn("\n\nTimeline events:", response.text)

    def test_renders_compact_mode(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal()
        store.upsert(proposal)
        response = self._router(store).route(
            "Mike",
            "APPROVE proposal_1",
            PortfolioState(equity=1000.0),
            now=proposal.created_at,
            render_mode="compact",
        )
        self.assertIn("Trade Report", response.text)
        self.assertIn("Timeline events:", response.text)


if __name__ == "__main__":
    unittest.main()
