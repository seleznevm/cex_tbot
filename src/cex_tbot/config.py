from __future__ import annotations

from dataclasses import dataclass
import os

from .enums import Exchange, MarketType
from .exceptions import GateLiveModeBlockedError, MissingGateDemoApiError


_ALLOWED_EXECUTION_MODES = {"paper_sim", "dry_run", "gate_demo"}
_BLOCKED_LIVE_EXECUTION_MODES = {"live", "gate_live", "prod", "production"}


@dataclass(frozen=True)
class BotConfig:
    exchange: Exchange = Exchange.GATE
    market_type: MarketType = MarketType.USDT_PERPETUAL
    whitelist_size: int = 20
    min_listing_age_hours: int = 72
    max_spread_bps: float = 8.0
    min_confidence_score: float = 0.70
    universe_refresh_minutes: int = 60
    execution_mode: str = "paper_sim"
    default_risk_percent: float = 0.5
    max_aggregate_open_risk_percent: float = 1.0
    max_daily_drawdown_percent: float = 2.0
    max_open_positions: int = 2
    gate_demo_api: str = ""
    gate_demo_key: str = ""
    gate_demo_secret: str = ""
    gate_demo_test_order_size: float = 1.0

    def __post_init__(self) -> None:
        normalized_mode = self.execution_mode.strip().lower()
        object.__setattr__(self, "execution_mode", normalized_mode)
        object.__setattr__(self, "gate_demo_api", self.gate_demo_api.strip())
        object.__setattr__(self, "gate_demo_key", self.gate_demo_key.strip())
        object.__setattr__(self, "gate_demo_secret", self.gate_demo_secret.strip())
        object.__setattr__(self, "gate_demo_test_order_size", float(self.gate_demo_test_order_size))

        if normalized_mode in _BLOCKED_LIVE_EXECUTION_MODES or (
            "live" in normalized_mode and normalized_mode != "gate_demo"
        ):
            raise GateLiveModeBlockedError(
                "Live Gate transport is intentionally blocked in this repo. "
                "Use paper_sim, dry_run, or gate_demo."
            )
        if normalized_mode not in _ALLOWED_EXECUTION_MODES:
            raise ValueError(
                "Unsupported CEX_TBOT_EXECUTION_MODE. "
                f"Expected one of {sorted(_ALLOWED_EXECUTION_MODES)}, got {self.execution_mode!r}."
            )
        if normalized_mode == "gate_demo" and not self.gate_demo_api:
            raise MissingGateDemoApiError(
                "GATE_DEMO_API is required when CEX_TBOT_EXECUTION_MODE=gate_demo"
            )


def load_config(env: dict[str, str] | None = None) -> BotConfig:
    source = os.environ if env is None else env
    return BotConfig(
        whitelist_size=int(source.get("CEX_TBOT_WHITELIST_SIZE", "20")),
        min_listing_age_hours=int(source.get("CEX_TBOT_MIN_LISTING_AGE_HOURS", "72")),
        max_spread_bps=float(source.get("CEX_TBOT_MAX_SPREAD_BPS", "8.0")),
        min_confidence_score=float(source.get("CEX_TBOT_MIN_CONFIDENCE_SCORE", "0.70")),
        universe_refresh_minutes=int(source.get("CEX_TBOT_UNIVERSE_REFRESH_MINUTES", "60")),
        execution_mode=source.get("CEX_TBOT_EXECUTION_MODE", "paper_sim"),
        default_risk_percent=float(source.get("CEX_TBOT_DEFAULT_RISK_PERCENT", "0.5")),
        max_aggregate_open_risk_percent=float(source.get("CEX_TBOT_MAX_AGGREGATE_OPEN_RISK_PERCENT", "1.0")),
        max_daily_drawdown_percent=float(source.get("CEX_TBOT_MAX_DAILY_DRAWDOWN_PERCENT", "2.0")),
        max_open_positions=int(source.get("CEX_TBOT_MAX_OPEN_POSITIONS", "2")),
        gate_demo_api=source.get("GATE_DEMO_API", ""),
        gate_demo_key=source.get("GATE_DEMO_KEY", ""),
        gate_demo_secret=source.get("GATE_DEMO_SECRET", ""),
        gate_demo_test_order_size=float(source.get("GATE_DEMO_TEST_ORDER_SIZE", "1.0")),
    )
