from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from cex_tbot.shared import ensure_utc, utc_now
from cex_tbot.universe.repository import UniverseSnapshot


@dataclass(frozen=True)
class RefreshPolicyDecision:
    should_refresh: bool
    reason: str


class UniverseRefreshPolicy:
    def __init__(self, refresh_interval_minutes: int) -> None:
        self.refresh_interval_minutes = refresh_interval_minutes

    def should_refresh(self, latest_snapshot: UniverseSnapshot | None, *, now: datetime | None = None) -> RefreshPolicyDecision:
        if latest_snapshot is None:
            return RefreshPolicyDecision(True, "no_snapshot")
        effective_now = ensure_utc(now) if now is not None else utc_now()
        age = effective_now - latest_snapshot.created_at
        if age >= timedelta(minutes=self.refresh_interval_minutes):
            return RefreshPolicyDecision(True, "refresh_interval_elapsed")
        return RefreshPolicyDecision(False, "snapshot_still_fresh")
