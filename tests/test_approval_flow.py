from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ApprovalAction, ProposalStatus, TradeDirection
from cex_tbot.proposal_store import InMemoryProposalStore


class ApprovalFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = ApprovalFlow()

    def test_parses_approve_command(self) -> None:
        result = self.flow.parse_command("APPROVE proposal_123")
        self.assertTrue(result.is_valid)
        assert result.command is not None
        self.assertEqual(result.command.action, ApprovalAction.APPROVE)
        self.assertEqual(result.command.proposal_id, "proposal_123")

    def test_parses_modify_command(self) -> None:
        result = self.flow.parse_command("MODIFY proposal_123: stop_loss=98.5")
        self.assertTrue(result.is_valid)
        assert result.command is not None
        self.assertEqual(result.command.action, ApprovalAction.MODIFY)
        self.assertEqual(result.command.changes, "stop_loss=98.5")

    def test_rejects_non_strict_command(self) -> None:
        result = self.flow.parse_command("please approve proposal_123")
        self.assertFalse(result.is_valid)

    def test_maps_status_transition(self) -> None:
        decision = self.flow.record_decision("Mike", "APPROVE proposal_123")
        next_status = self.flow.next_status(ProposalStatus.PENDING_APPROVAL, decision)
        self.assertEqual(next_status, ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK)

    def test_unknown_proposal_does_not_create_orphan_decision(self) -> None:
        store = InMemoryProposalStore()
        flow = ApprovalFlow(store)
        with self.assertRaises(KeyError):
            flow.apply_command("Mike", "APPROVE proposal_missing")
        self.assertEqual(store.history("proposal_missing"), [])

    def test_unknown_modify_does_not_create_orphan_decision(self) -> None:
        store = InMemoryProposalStore()
        flow = ApprovalFlow(store)
        now = datetime.now(UTC)
        replacement = TradeProposal(
            proposal_id="proposal_new",
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
        with self.assertRaises(KeyError):
            flow.revalidate_modified_proposal("Mike", "MODIFY proposal_missing: stop_loss=98.5", replacement)
        self.assertEqual(store.history("proposal_missing"), [])


if __name__ == "__main__":
    unittest.main()
