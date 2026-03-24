from __future__ import annotations

from dataclasses import dataclass
import os

from .enums import Exchange, MarketType


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
    )
