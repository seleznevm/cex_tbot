from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.decision_contracts.models import TradeProposal
from cex_tbot.risk_engine import RiskEvaluation


@dataclass(frozen=True)
class ReviewCard:
    proposal_id: str
    symbol: str
    direction: str
    timeframe: str
    confidence_score: float
    entry_zone_min: float
    entry_zone_max: float
    entry_summary: str
    stop_loss: float
    tp_summary: str
    risk_summary: str
    thesis: str
    invalidity_condition: str
    liquidity_check: str


class ReviewCardBuilder:
    def build(self, proposal: TradeProposal, risk_evaluation: RiskEvaluation | None = None) -> ReviewCard:
        entry_summary = ", ".join(
            f"leg{leg.leg_number}@{leg.planned_entry_price} ({leg.allocation_pct:.1f}%)"
            for leg in proposal.entry_split
        )
        tp_summary = f"TP1={proposal.take_profit_1}, TP2={proposal.take_profit_2}"
        risk_summary = f"risk={proposal.risk_percent:.2f}% / ${proposal.risk_usd:.2f}"
        if risk_evaluation is not None:
            risk_summary = f"{risk_summary}; gate={risk_evaluation.reason_code.value}"
        return ReviewCard(
            proposal_id=proposal.proposal_id,
            symbol=proposal.symbol,
            direction=proposal.direction.value,
            timeframe=proposal.timeframe,
            confidence_score=proposal.confidence_score,
            entry_zone_min=proposal.entry_zone_min,
            entry_zone_max=proposal.entry_zone_max,
            entry_summary=entry_summary,
            stop_loss=proposal.stop_loss,
            tp_summary=tp_summary,
            risk_summary=risk_summary,
            thesis=proposal.thesis,
            invalidity_condition=proposal.invalidity_condition,
            liquidity_check=proposal.liquidity_check,
        )
