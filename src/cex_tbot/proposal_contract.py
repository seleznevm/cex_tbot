from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


REQUIRED_FIELDS = {
    "proposal_id",
    "agent_name",
    "strategy_id",
    "strategy_version",
    "market_context_id",
    "symbol",
    "timeframe",
    "direction",
    "entry_zone_min",
    "entry_zone_max",
    "entry_split",
    "stop_loss",
    "take_profit_1",
    "take_profit_2",
    "risk_percent",
    "risk_usd",
    "position_size",
    "confidence_score",
    "thesis",
    "invalidity_condition",
    "liquidity_check",
    "data_freshness_ms",
    "created_at",
    "expires_at",
}

VALID_DIRECTIONS = {"LONG", "SHORT"}
VALID_STATUSES = {"PENDING_APPROVAL", "GENERATED"}


@dataclass(frozen=True)
class ProposalValidationResult:
    ok: bool
    errors: list[str]


def validate_proposal_payload(payload: dict[str, object]) -> ProposalValidationResult:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(payload.keys()))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
        return ProposalValidationResult(False, errors)

    direction = str(payload.get("direction"))
    if direction not in VALID_DIRECTIONS:
        errors.append(f"direction must be one of {sorted(VALID_DIRECTIONS)}")

    status = str(payload.get("status", "PENDING_APPROVAL"))
    if status not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}")

    try:
        entry_min = float(payload["entry_zone_min"])
        entry_max = float(payload["entry_zone_max"])
        stop_loss = float(payload["stop_loss"])
        tp1 = float(payload["take_profit_1"])
        tp2 = float(payload["take_profit_2"])
        confidence = float(payload["confidence_score"])
        risk_percent = float(payload["risk_percent"])
        datetime.fromisoformat(str(payload["created_at"]))
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
    except (TypeError, ValueError) as exc:
        errors.append(f"type/format error: {exc}")
        return ProposalValidationResult(False, errors)

    if entry_min > entry_max:
        errors.append("entry_zone_min must be <= entry_zone_max")
    if tp1 <= 0 or tp2 <= 0 or stop_loss <= 0:
        errors.append("stop_loss and take profits must be positive")
    if confidence < 0 or confidence > 1:
        errors.append("confidence_score must be between 0 and 1")
    if risk_percent <= 0:
        errors.append("risk_percent must be positive")
    if expires_at <= created_at:
        errors.append("expires_at must be later than created_at")

    entry_split = payload.get("entry_split")
    if not isinstance(entry_split, list) or not entry_split:
        errors.append("entry_split must be a non-empty list")
    else:
        for index, leg in enumerate(entry_split, start=1):
            if not isinstance(leg, dict):
                errors.append(f"entry_split[{index}] must be an object")
                continue
            for key in {"leg_number", "planned_entry_price", "allocation_pct", "size_fraction", "valid_until"}:
                if key not in leg:
                    errors.append(f"entry_split[{index}] missing {key}")

    return ProposalValidationResult(not errors, errors)


def proposal_contract_text() -> str:
    return "\n".join([
        "Proposal JSON contract",
        "Required fields:",
        "- proposal_id, agent_name, strategy_id, strategy_version, market_context_id",
        "- symbol, timeframe, direction",
        "- entry_zone_min, entry_zone_max, entry_split[]",
        "- stop_loss, take_profit_1, take_profit_2",
        "- risk_percent, risk_usd, position_size, confidence_score",
        "- thesis, invalidity_condition, liquidity_check, data_freshness_ms",
        "- created_at, expires_at",
        "Optional:",
        "- status (default PENDING_APPROVAL; allowed: PENDING_APPROVAL, GENERATED)",
        "Rules:",
        "- direction: LONG|SHORT",
        "- confidence_score: 0..1",
        "- risk_percent > 0",
        "- entry_zone_min <= entry_zone_max",
        "- expires_at > created_at",
        "- entry_split must contain at least one leg",
    ])
