from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeQuery:
    status: str | None = None
    symbol: str | None = None
    direction: str | None = None
    sort_by: str = "proposal_id"
    descending: bool = False
    limit: int | None = None
    offset: int = 0
