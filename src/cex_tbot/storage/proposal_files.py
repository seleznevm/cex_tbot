from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from cex_tbot.decision_contracts.models import ApprovalDecision, EntrySplitLeg, TradeProposal
from cex_tbot.enums import ContractType, Exchange, MarketType, ProposalStatus, TradeDirection
from cex_tbot.proposal_store import InMemoryProposalStore
from cex_tbot.shared import ensure_utc


class FileProposalStore(InMemoryProposalStore):
    def __init__(self, proposals_path: str | Path, decisions_path: str | Path) -> None:
        super().__init__()
        self.proposals_path = Path(proposals_path)
        self.decisions_path = Path(decisions_path)
        self.proposals_path.parent.mkdir(parents=True, exist_ok=True)
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)
        if self.proposals_path.exists():
            self._load_proposals()
        if self.decisions_path.exists():
            self._load_decisions()

    def upsert(self, proposal: TradeProposal) -> TradeProposal:
        saved = super().upsert(proposal)
        self._append_proposal(saved)
        return saved

    def update_status(self, proposal_id: str, status: ProposalStatus) -> TradeProposal:
        updated = super().update_status(proposal_id, status)
        self._append_proposal(updated)
        return updated

    def append_decision(self, decision: ApprovalDecision) -> None:
        super().append_decision(decision)
        with self.decisions_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._serialize_decision(decision), ensure_ascii=False) + "\n")

    def _append_proposal(self, proposal: TradeProposal) -> None:
        with self.proposals_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._serialize_proposal(proposal), ensure_ascii=False) + "\n")

    def _load_proposals(self) -> None:
        latest: dict[str, TradeProposal] = {}
        for line in self.proposals_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            proposal = self._deserialize_proposal(raw)
            latest[proposal.proposal_id] = proposal
        for proposal in latest.values():
            self._proposals[proposal.proposal_id] = proposal
            self._history.setdefault(proposal.proposal_id, [])

    def _load_decisions(self) -> None:
        for line in self.decisions_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            decision = ApprovalDecision(
                proposal_id=raw["proposal_id"],
                actor=raw["actor"],
                action=raw["action"],
                raw_command=raw["raw_command"],
                parsed_command=raw["parsed_command"],
                is_strict_match=raw["is_strict_match"],
                reason_text=raw.get("reason_text"),
                approval_decision_id=raw["approval_decision_id"],
                created_at=ensure_utc(datetime.fromisoformat(raw["created_at"])),
            )
            self._history.setdefault(decision.proposal_id, []).append(decision)

    @staticmethod
    def _serialize_proposal(proposal: TradeProposal) -> dict[str, object]:
        data = asdict(proposal)
        data["created_at"] = proposal.created_at.isoformat()
        data["expires_at"] = proposal.expires_at.isoformat()
        data["direction"] = proposal.direction.value
        data["exchange"] = proposal.exchange.value
        data["market_type"] = proposal.market_type.value
        data["contract_type"] = proposal.contract_type.value
        data["status"] = proposal.status.value
        for leg in data["entry_split"]:
            leg["valid_until"] = leg["valid_until"].isoformat()
        return data

    @staticmethod
    def _serialize_decision(decision: ApprovalDecision) -> dict[str, object]:
        data = asdict(decision)
        data["created_at"] = decision.created_at.isoformat()
        return data

    @staticmethod
    def _deserialize_proposal(raw: dict[str, object]) -> TradeProposal:
        legs = [
            EntrySplitLeg(
                leg_number=leg["leg_number"],
                planned_entry_price=leg["planned_entry_price"],
                allocation_pct=leg["allocation_pct"],
                size_fraction=leg["size_fraction"],
                valid_until=ensure_utc(datetime.fromisoformat(leg["valid_until"])),
            )
            for leg in raw["entry_split"]
        ]
        return TradeProposal(
            proposal_id=raw["proposal_id"],
            proposal_version=raw["proposal_version"],
            agent_name=raw["agent_name"],
            strategy_id=raw["strategy_id"],
            strategy_version=raw["strategy_version"],
            market_context_id=raw["market_context_id"],
            symbol=raw["symbol"],
            timeframe=raw["timeframe"],
            direction=TradeDirection(raw["direction"]),
            entry_zone_min=raw["entry_zone_min"],
            entry_zone_max=raw["entry_zone_max"],
            entry_split=legs,
            stop_loss=raw["stop_loss"],
            take_profit_1=raw["take_profit_1"],
            take_profit_2=raw["take_profit_2"],
            risk_percent=raw["risk_percent"],
            risk_usd=raw["risk_usd"],
            position_size=raw["position_size"],
            confidence_score=raw["confidence_score"],
            thesis=raw["thesis"],
            invalidity_condition=raw["invalidity_condition"],
            liquidity_check=raw["liquidity_check"],
            data_freshness_ms=raw["data_freshness_ms"],
            created_at=ensure_utc(datetime.fromisoformat(raw["created_at"])),
            expires_at=ensure_utc(datetime.fromisoformat(raw["expires_at"])),
            exchange=Exchange(raw["exchange"]),
            market_type=MarketType(raw["market_type"]),
            contract_type=ContractType(raw["contract_type"]),
            status=ProposalStatus(raw["status"]),
        )
