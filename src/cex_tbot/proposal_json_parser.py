from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.proposal_contract import validate_proposal_payload


@dataclass(frozen=True)
class JsonTradeProposalParser:
    force_pending_approval: bool = True

    def parse_text(self, payload_text: str) -> TradeProposal:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid json at char {exc.pos}: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError("payload root must be an object")
        return self.parse_payload(payload)

    def parse_payload(self, payload: dict[str, Any]) -> TradeProposal:
        validation = validate_proposal_payload(payload)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors))
        entry_split = [
            EntrySplitLeg(
                leg_number=int(item["leg_number"]),
                planned_entry_price=float(item["planned_entry_price"]),
                allocation_pct=float(item["allocation_pct"]),
                size_fraction=float(item["size_fraction"]),
                valid_until=datetime.fromisoformat(str(item["valid_until"])),
            )
            for item in payload["entry_split"]
        ]
        status = ProposalStatus(payload.get("status", ProposalStatus.PENDING_APPROVAL.value))
        if self.force_pending_approval:
            status = ProposalStatus.PENDING_APPROVAL
        return TradeProposal(
            proposal_id=str(payload["proposal_id"]),
            agent_name=str(payload["agent_name"]),
            strategy_id=str(payload["strategy_id"]),
            strategy_version=str(payload["strategy_version"]),
            market_context_id=str(payload["market_context_id"]),
            symbol=str(payload["symbol"]),
            timeframe=str(payload["timeframe"]),
            direction=TradeDirection(str(payload["direction"])),
            entry_zone_min=float(payload["entry_zone_min"]),
            entry_zone_max=float(payload["entry_zone_max"]),
            entry_split=entry_split,
            stop_loss=float(payload["stop_loss"]),
            take_profit_1=float(payload["take_profit_1"]),
            take_profit_2=float(payload["take_profit_2"]),
            risk_percent=float(payload["risk_percent"]),
            risk_usd=float(payload["risk_usd"]),
            position_size=float(payload["position_size"]),
            confidence_score=float(payload["confidence_score"]),
            thesis=str(payload["thesis"]),
            invalidity_condition=str(payload["invalidity_condition"]),
            liquidity_check=str(payload["liquidity_check"]),
            data_freshness_ms=int(payload["data_freshness_ms"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            status=status,
        )
