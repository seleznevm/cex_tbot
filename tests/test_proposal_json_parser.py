from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta

from cex_tbot.enums import ProposalStatus
from cex_tbot.proposal_json_parser import JsonTradeProposalParser


class JsonTradeProposalParserTests(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        now = datetime.now(UTC)
        return {
            "proposal_id": "proposal_parser_1",
            "agent_name": "Luma",
            "strategy_id": "pullback",
            "strategy_version": "v1",
            "market_context_id": "ctx_parser_1",
            "symbol": "BTC_USDT",
            "timeframe": "15m",
            "direction": "LONG",
            "entry_zone_min": 99.0,
            "entry_zone_max": 100.0,
            "entry_split": [
                {
                    "leg_number": 1,
                    "planned_entry_price": 99.5,
                    "allocation_pct": 100.0,
                    "size_fraction": 1.0,
                    "valid_until": (now + timedelta(minutes=10)).isoformat(),
                }
            ],
            "stop_loss": 98.0,
            "take_profit_1": 101.0,
            "take_profit_2": 102.0,
            "risk_percent": 0.5,
            "risk_usd": 5.0,
            "position_size": 1.0,
            "confidence_score": 0.8,
            "thesis": "json payload",
            "invalidity_condition": "support breaks",
            "liquidity_check": "ok",
            "data_freshness_ms": 100,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=20)).isoformat(),
            "status": "GENERATED",
        }

    def test_parser_validates_and_forces_pending_status(self) -> None:
        parser = JsonTradeProposalParser(force_pending_approval=True)

        proposal = parser.parse_text(json.dumps(self._payload()))

        self.assertEqual(proposal.proposal_id, "proposal_parser_1")
        self.assertEqual(proposal.status, ProposalStatus.PENDING_APPROVAL)

    def test_parser_rejects_invalid_payload(self) -> None:
        parser = JsonTradeProposalParser(force_pending_approval=True)
        payload = self._payload()
        payload.pop("symbol")

        with self.assertRaisesRegex(ValueError, "missing fields"):
            parser.parse_text(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
