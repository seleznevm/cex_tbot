from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from cex_tbot.enums import ContractType, Exchange, MarketType, NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.shared import ensure_utc, new_id, utc_now


@dataclass(frozen=True)
class EntrySplitLeg:
    leg_number: int
    planned_entry_price: float
    allocation_pct: float
    size_fraction: float
    valid_until: datetime

    def __post_init__(self) -> None:
        if self.leg_number not in {1, 2}:
            raise ValueError("leg_number must be 1 or 2")
        object.__setattr__(self, "valid_until", ensure_utc(self.valid_until))


@dataclass(frozen=True)
class TradeProposal:
    agent_name: str
    strategy_id: str
    strategy_version: str
    market_context_id: str
    symbol: str
    timeframe: str
    direction: TradeDirection
    entry_zone_min: float
    entry_zone_max: float
    entry_split: Sequence[EntrySplitLeg]
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_percent: float
    risk_usd: float
    position_size: float
    confidence_score: float
    thesis: str
    invalidity_condition: str
    liquidity_check: str
    data_freshness_ms: int
    proposal_id: str = field(default_factory=lambda: new_id("proposal"))
    proposal_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=utc_now)
    exchange: Exchange = Exchange.GATE
    market_type: MarketType = MarketType.USDT_PERPETUAL
    contract_type: ContractType = ContractType.PERPETUAL
    status: ProposalStatus = ProposalStatus.GENERATED

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc(self.created_at))
        object.__setattr__(self, "expires_at", ensure_utc(self.expires_at))
        if self.entry_zone_min > self.entry_zone_max:
            raise ValueError("entry_zone_min must be <= entry_zone_max")
        if not self.entry_split or len(self.entry_split) > 2:
            raise ValueError("entry_split must contain 1 or 2 legs")


@dataclass(frozen=True)
class NoTradeDecision:
    agent_name: str
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    confidence_score: float
    reason_code: NoTradeReasonCode
    reason_text: str
    market_context_id: str
    liquidity_check: str
    data_freshness_ms: int
    decision_id: str = field(default_factory=lambda: new_id("no_trade"))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc(self.created_at))


@dataclass(frozen=True)
class ApprovalDecision:
    proposal_id: str
    actor: str
    action: str
    raw_command: str
    parsed_command: str
    is_strict_match: bool
    reason_text: str | None = None
    approval_decision_id: str = field(default_factory=lambda: new_id("approval"))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc(self.created_at))
