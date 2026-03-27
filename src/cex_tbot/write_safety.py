from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from cex_tbot.shared import utc_now


@dataclass
class WriteActionArmState:
    armed_sender_id: str | None = None
    armed_until: datetime | None = None

    def arm(self, sender_id: str, *, ttl_seconds: int = 120) -> datetime:
        expires_at = utc_now() + timedelta(seconds=ttl_seconds)
        self.armed_sender_id = sender_id
        self.armed_until = expires_at
        return expires_at

    def is_armed_for(self, sender_id: str) -> bool:
        return (
            self.armed_sender_id == sender_id
            and self.armed_until is not None
            and utc_now() <= self.armed_until
        )

    def clear(self) -> None:
        self.armed_sender_id = None
        self.armed_until = None
