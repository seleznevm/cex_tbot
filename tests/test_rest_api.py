from __future__ import annotations

from datetime import UTC, datetime, timedelta
import builtins
import unittest
from unittest.mock import patch

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:  # optional REST dependency
    fastapi = None

from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, TradeDirection
from cex_tbot.rest_api import NoTradePayloadMapper, ProposalPayloadMapper, RestApiDependencyError, RestAuth, RestErrorFactory, create_rest_app


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

    def test_from_dict_generates_proposal_id_when_missing(self) -> None:
        now = datetime(2026, 3, 26, 12, 0, tzinfo=UTC)
        payload = {
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
        }
        proposal = ProposalPayloadMapper.from_dict(payload)
        self.assertTrue(proposal.proposal_id.startswith("proposal_"))

    def test_no_trade_mapper_builds_decision(self) -> None:
        now = datetime(2026, 3, 26, 12, 0, tzinfo=UTC)
        payload = {
            "decision_id": "no_trade_rest_1",
            "agent_name": "Luma",
            "strategy_id": "breakout_reclaim",
            "strategy_version": "v3",
            "symbol": "BTC_USDT",
            "timeframe": "15m",
            "confidence_score": 0.41,
            "reason_code": "confidence_below_threshold",
            "reason_text": "signal stayed too weak after validation",
            "market_context_id": "ctx_demo_btc_20260326",
            "liquidity_check": "ok",
            "data_freshness_ms": 5000,
            "created_at": now.isoformat(),
        }

        decision = NoTradePayloadMapper.from_dict(payload)

        self.assertIsInstance(decision, NoTradeDecision)
        self.assertEqual(decision.decision_id, "no_trade_rest_1")
        self.assertEqual(decision.reason_code, NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD)
        self.assertEqual(decision.symbol, "BTC_USDT")

    def test_auth_and_error_helpers(self) -> None:
        auth = RestAuth("secret")
        self.assertTrue(auth.enabled)
        self.assertTrue(auth.verify("secret"))
        self.assertFalse(auth.verify("wrong"))
        self.assertEqual(
            RestErrorFactory.payload("X", "boom"),
            {"error": {"code": "X", "message": "boom", "details": {}}},
        )

    @unittest.skipIf(fastapi is None, "fastapi/pydantic REST dependencies are not installed")
    def test_create_rest_app_raises_when_fastapi_missing(self) -> None:
        real_import = builtins.__import__

        def side_effect(name, *args, **kwargs):
            if name == "fastapi":
                raise ModuleNotFoundError("No module named 'fastapi'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=side_effect):
            with self.assertRaises(RestApiDependencyError):
                create_rest_app()


if __name__ == "__main__":
    unittest.main()
