from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.proposal_store import InMemoryProposalStore


class ProposalStoreTests(unittest.TestCase):
    def _proposal(self, proposal_id: str = "proposal_1", version: int = 1) -> TradeProposal:
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

    def test_upsert_and_update_status(self) -> None:
        store = InMemoryProposalStore()
        store.upsert(self._proposal())
        updated = store.update_status("proposal_1", ProposalStatus.REJECTED_BY_HUMAN)
        self.assertEqual(updated.status, ProposalStatus.REJECTED_BY_HUMAN)

    def test_supersede_and_add(self) -> None:
        store = InMemoryProposalStore()
        old = self._proposal("proposal_old", 1)
        new = self._proposal("proposal_new", 1)
        store.upsert(old)
        previous, replacement = store.supersede_and_add(old.proposal_id, new)
        self.assertEqual(previous.status, ProposalStatus.SUPERSEDED)
        self.assertEqual(replacement.proposal_id, "proposal_new")


if __name__ == "__main__":
    unittest.main()
