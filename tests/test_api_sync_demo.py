from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.bootstrap import build_app
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.risk_engine import PortfolioState
from tests.test_gate_demo_operator_commands import _HealthyDemoClient


class ApiSyncDemoTests(unittest.TestCase):
    def test_api_sync_demo_orders_returns_order_payloads(self) -> None:
        now = datetime.now(UTC)
        app = build_app(
            config=BotConfig(
                execution_mode="gate_demo",
                gate_demo_api="https://api-testnet.gateapi.io/api/v4",
                gate_demo_key="demo-key",
                gate_demo_secret="demo-secret",
            ),
            gate_demo_client=_HealthyDemoClient(),
        )
        proposal = TradeProposal(
            proposal_id="proposal_sync_1",
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
            position_size=0.0465,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.PENDING_APPROVAL,
        )
        app.backend.submit_proposal(proposal)
        app.backend.run_operator_command("Mike", "APPROVE proposal_sync_1", PortfolioState(equity=1000.0), now=now)

        payload = app.api.sync_demo_orders("proposal_sync_1")

        self.assertEqual(payload["proposal_id"], "proposal_sync_1")
        self.assertEqual(len(payload["orders"]), 4)
        roles = {item["role"] for item in payload["orders"]}
        self.assertEqual(roles, {"entry", "stop_loss", "take_profit_1", "take_profit_2"})


if __name__ == "__main__":
    unittest.main()
