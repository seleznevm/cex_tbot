from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.approval_flow import ApprovalFlow
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution import ExecutionOrchestrator, InMemoryExecutionJournal, InMemoryExecutionStateStore, TradeTimelineBuilder
from cex_tbot.handoff import ApprovalExecutionHandoff
from cex_tbot.operator_router import OperatorCommandRouter
from cex_tbot.query_params import TradeQuery
from cex_tbot.read_models import QueryService
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.simulator import SimulatorService
from cex_tbot.workflow import TradeWorkflowService


class QueryParamsTests(unittest.TestCase):
    def test_filters_and_sorts_trade_list(self) -> None:
        session = TradeSessionStore(
            execution_journal=InMemoryExecutionJournal(),
            execution_state=InMemoryExecutionStateStore(),
        )
        now = datetime.now(UTC)
        proposals = [
            TradeProposal(
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
                thesis="btc long",
                invalidity_condition="breakdown",
                liquidity_check="ok",
                data_freshness_ms=100,
                created_at=now,
                expires_at=now + timedelta(minutes=15),
                status=ProposalStatus.PENDING_APPROVAL,
            ),
            TradeProposal(
                proposal_id="proposal_2",
                agent_name="Luma",
                strategy_id="pullback",
                strategy_version="v1",
                market_context_id="ctx_2",
                symbol="ETH_USDT",
                timeframe="15m",
                direction=TradeDirection.SHORT,
                entry_zone_min=99.0,
                entry_zone_max=100.0,
                entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
                stop_loss=101.0,
                take_profit_1=98.0,
                take_profit_2=96.0,
                risk_percent=0.5,
                risk_usd=5.0,
                position_size=10.0,
                confidence_score=0.6,
                thesis="eth short",
                invalidity_condition="breakout",
                liquidity_check="ok",
                data_freshness_ms=100,
                created_at=now,
                expires_at=now + timedelta(minutes=15),
                status=ProposalStatus.REJECTED_BY_HUMAN,
            ),
        ]
        for proposal in proposals:
            session.proposals.upsert(proposal)
        query = QueryService(session, TradeTimelineBuilder(session.execution_journal, session.execution_state))
        filtered = query.list_trades(TradeQuery(status="PENDING_APPROVAL", sort_by="confidence_score", descending=True))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].symbol, "BTC_USDT")
        paged = query.list_trades(TradeQuery(limit=1, offset=1, sort_by="proposal_id"))
        self.assertEqual(len(paged), 1)
        self.assertEqual(paged[0].proposal_id, "proposal_2")


if __name__ == "__main__":
    unittest.main()
