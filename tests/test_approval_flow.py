import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.enums import ApprovalAction, ProposalStatus


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


if __name__ == "__main__":
    unittest.main()
