from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.storage import FileProposalStore


class FileProposalStoreTests(unittest.TestCase):
    def test_persists_and_reloads_proposals_and_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposals_path = Path(tmp) / "proposals.jsonl"
            decisions_path = Path(tmp) / "decisions.jsonl"
            store = FileProposalStore(proposals_path, decisions_path)
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
            store.upsert(proposal)
            ApprovalFlow(store).apply_command("Mike", "APPROVE proposal_1")

            reloaded = FileProposalStore(proposals_path, decisions_path)
            self.assertEqual(reloaded.get("proposal_1").status, ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK)
            self.assertEqual(len(reloaded.history("proposal_1")), 1)


if __name__ == "__main__":
    unittest.main()
