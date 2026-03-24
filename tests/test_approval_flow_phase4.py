from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.proposal_store import InMemoryProposalStore


class ApprovalFlowPhase4Tests(unittest.TestCase):
    def _proposal(self, proposal_id: str, version: int = 1) -> TradeProposal:
        now = datetime.now(UTC)
        return TradeProposal(
            proposal_id=proposal_id,
            proposal_version=version,
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
            stop_loss=97.0,
            take_profit_1=102.0,
            take_profit_2=104.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=100.0,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.PENDING_APPROVAL,
        )

    def test_apply_command_updates_status(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal("proposal_1")
        store.upsert(proposal)
        flow = ApprovalFlow(store)
        result = flow.apply_command("Mike", "APPROVE proposal_1")
        self.assertEqual(result.resulting_status, ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK)

    def test_modify_supersedes_and_creates_replacement(self) -> None:
        store = InMemoryProposalStore()
        old = self._proposal("proposal_1", version=1)
        replacement = self._proposal("proposal_2", version=1)
        store.upsert(old)
        flow = ApprovalFlow(store)
        result = flow.revalidate_modified_proposal("Mike", "MODIFY proposal_1: stop_loss=98.0", replacement)
        self.assertEqual(result.superseded_proposal_id, "proposal_1")
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.SUPERSEDED)
        self.assertEqual(store.get("proposal_2").status, ProposalStatus.PENDING_APPROVAL)
        self.assertEqual(store.get("proposal_2").proposal_version, 2)

    def test_invalid_command_keeps_state(self) -> None:
        store = InMemoryProposalStore()
        proposal = self._proposal("proposal_1")
        store.upsert(proposal)
        flow = ApprovalFlow(store)
        result = flow.apply_command("Mike", "looks good")
        self.assertIsNone(result.resulting_status)
        self.assertEqual(store.get("proposal_1").status, ProposalStatus.PENDING_APPROVAL)


if __name__ == "__main__":
    unittest.main()
