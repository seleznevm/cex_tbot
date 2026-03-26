from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import patch

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.enums import TradeDirection
from cex_tbot.rest_api import ProposalPayloadMapper, RestApiDependencyError, create_rest_app


class ProposalPayloadMapperTests(unittest.TestCase):
    def test_from_dict_builds_trade_proposal(self) -> None:
        now = datetime(2026, 3, 26, 12, 0, tzinfo=UTC)
        payload = {
            "proposal_id": "proposal_rest_1",
            "agent_name": "Luma",
            "strategy_id": "breakout_reclaim",
            "strategy_version": "v3",
            "market_context_id": "ctx_demo_btc_20260326",
            "symbol": "BTC_USDT",
            "timeframe": "15m",
            "direction": "LONG",
            "entry_zone_min": 100.0,
            "entry_zone_max": 101.0,
            "entry_split": [
                {
                    "leg_number": 1,
                    "planned_entry_price": 100.5,
                    "allocation_pct": 100.0,
                    "size_fraction": 1.0,
                    "valid_until": (now + timedelta(minutes=10)).isoformat(),
                }
            ],
            "stop_loss": 99.0,
            "take_profit_1": 103.0,
            "take_profit_2": 105.0,
            "risk_percent": 0.5,
            "risk_usd": 5.0,
            "position_size": 10.0,
            "confidence_score": 0.82,
            "thesis": "breakout held",
            "invalidity_condition": "reclaim fails",
            "liquidity_check": "ok",
            "data_freshness_ms": 5000,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=15)).isoformat(),
            "status": "PENDING_APPROVAL",
        }

        proposal = ProposalPayloadMapper.from_dict(payload)

        self.assertIsInstance(proposal, TradeProposal)
        self.assertEqual(proposal.proposal_id, "proposal_rest_1")
        self.assertEqual(proposal.direction, TradeDirection.LONG)
        self.assertEqual(len(proposal.entry_split), 1)
        self.assertEqual(proposal.status.value, "PENDING_APPROVAL")

    def test_create_rest_app_raises_when_fastapi_missing(self) -> None:
        with patch("builtins.__import__") as import_mock:
            real_import = __import__

            def side_effect(name, *args, **kwargs):
                if name == "fastapi":
                    raise ModuleNotFoundError("No module named 'fastapi'")
                return real_import(name, *args, **kwargs)

            import_mock.side_effect = side_effect
            with self.assertRaises(RestApiDependencyError):
                create_rest_app()


if __name__ == "__main__":
    unittest.main()
