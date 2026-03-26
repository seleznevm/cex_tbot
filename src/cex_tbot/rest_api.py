from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any

from cex_tbot.api_surface import ApiSurface, CommandRequest, ProposalSubmitRequest, TradeListRequest
from cex_tbot.bootstrap import build_app
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ContractType, Exchange, MarketType, ProposalStatus, TradeDirection


class RestApiDependencyError(RuntimeError):
    """Raised when optional REST dependencies are unavailable."""


@dataclass(frozen=True)
class RestAppBundle:
    app: Any
    api: ApiSurface


class ProposalPayloadMapper:
    @staticmethod
    def from_dict(payload: dict[str, Any]) -> TradeProposal:
        entry_split = [ProposalPayloadMapper._entry_leg(item) for item in payload["entry_split"]]
        proposal_kwargs: dict[str, Any] = {
            "agent_name": payload["agent_name"],
            "strategy_id": payload["strategy_id"],
            "strategy_version": payload["strategy_version"],
            "market_context_id": payload["market_context_id"],
            "symbol": payload["symbol"],
            "timeframe": payload["timeframe"],
            "direction": TradeDirection(payload["direction"]),
            "entry_zone_min": float(payload["entry_zone_min"]),
            "entry_zone_max": float(payload["entry_zone_max"]),
            "entry_split": entry_split,
            "stop_loss": float(payload["stop_loss"]),
            "take_profit_1": float(payload["take_profit_1"]),
            "take_profit_2": float(payload["take_profit_2"]),
            "risk_percent": float(payload["risk_percent"]),
            "risk_usd": float(payload["risk_usd"]),
            "position_size": float(payload["position_size"]),
            "confidence_score": float(payload["confidence_score"]),
            "thesis": payload["thesis"],
            "invalidity_condition": payload["invalidity_condition"],
            "liquidity_check": payload["liquidity_check"],
            "data_freshness_ms": int(payload["data_freshness_ms"]),
            "created_at": ProposalPayloadMapper._parse_datetime(payload.get("created_at")),
            "expires_at": ProposalPayloadMapper._parse_datetime(payload.get("expires_at")),
            "exchange": Exchange(payload.get("exchange", Exchange.GATE.value)),
            "market_type": MarketType(payload.get("market_type", MarketType.USDT_PERPETUAL.value)),
            "contract_type": ContractType(payload.get("contract_type", ContractType.PERPETUAL.value)),
            "status": ProposalStatus(payload.get("status", ProposalStatus.GENERATED.value)),
        }
        if "proposal_id" in payload:
            proposal_kwargs["proposal_id"] = payload["proposal_id"]
        if "proposal_version" in payload:
            proposal_kwargs["proposal_version"] = int(payload["proposal_version"])
        return TradeProposal(**proposal_kwargs)

    @staticmethod
    def _entry_leg(payload: dict[str, Any]) -> EntrySplitLeg:
        return EntrySplitLeg(
            leg_number=int(payload["leg_number"]),
            planned_entry_price=float(payload["planned_entry_price"]),
            allocation_pct=float(payload["allocation_pct"]),
            size_fraction=float(payload["size_fraction"]),
            valid_until=ProposalPayloadMapper._parse_datetime(payload["valid_until"]),
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        if value is None:
            return datetime.now(UTC)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


class RestAuth:
    def __init__(self, token: str | None = None) -> None:
        self.token = (token if token is not None else os.environ.get("CEX_TBOT_API_TOKEN", "")).strip()

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def verify(self, supplied: str | None) -> bool:
        if not self.enabled:
            return True
        return supplied == self.token


class RestErrorFactory:
    @staticmethod
    def payload(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        }


def _build_portfolio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "actor": payload.get("actor", "Mike"),
        "portfolio_equity": float(payload.get("portfolio_equity", 10_000.0)),
        "aggregate_open_risk_pct": float(payload.get("aggregate_open_risk_pct", 0.0)),
        "daily_drawdown_pct": float(payload.get("daily_drawdown_pct", 0.0)),
        "open_positions_count": int(payload.get("open_positions_count", 0)),
        "render_mode": str(payload.get("render_mode", "plain")),
        "now": ProposalPayloadMapper._parse_datetime(payload["now"]) if payload.get("now") else None,
    }


def create_rest_app(*, storage_dir: str | Path | None = None, api_token: str | None = None) -> RestAppBundle:
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
    except ModuleNotFoundError as exc:
        raise RestApiDependencyError(
            "FastAPI is not installed. Install optional dependencies to use the REST bridge."
        ) from exc

    resolved_storage = Path(storage_dir) if storage_dir is not None else None
    trading_app = build_app(storage_dir=resolved_storage)
    api = trading_app.api
    auth = RestAuth(api_token)
    app = FastAPI(title="cex_tbot REST bridge", version="0.2.0")

    def require_auth(x_api_key: str | None = Header(default=None)) -> None:
        if not auth.verify(x_api_key):
            raise HTTPException(
                status_code=401,
                detail=RestErrorFactory.payload("UNAUTHORIZED", "Missing or invalid X-API-Key header"),
            )

    def http_error(status_code: int, code: str, message: str, *, details: dict[str, Any] | None = None) -> HTTPException:
        return HTTPException(status_code=status_code, detail=RestErrorFactory.payload(code, message, details=details))

    @app.get("/health", dependencies=[Depends(require_auth)])
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "storage": str(resolved_storage) if resolved_storage is not None else None,
            "auth_enabled": auth.enabled,
        }

    @app.get("/session/summary", dependencies=[Depends(require_auth)])
    def session_summary() -> dict[str, object]:
        return api.session_summary()

    @app.get("/dashboard", dependencies=[Depends(require_auth)])
    def dashboard() -> dict[str, object]:
        return api.dashboard()

    @app.get("/proposals", dependencies=[Depends(require_auth)])
    @app.get("/trades", dependencies=[Depends(require_auth)])
    def list_trades(
        status: str | None = None,
        symbol: str | None = None,
        direction: str | None = None,
        sort_by: str = "proposal_id",
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        return api.list_trades(
            TradeListRequest(
                status=status,
                symbol=symbol,
                direction=direction,
                sort_by=sort_by,
                descending=descending,
                limit=limit,
                offset=offset,
            )
        )

    @app.get("/proposals/{proposal_id}", dependencies=[Depends(require_auth)])
    @app.get("/trades/{proposal_id}", dependencies=[Depends(require_auth)])
    def trade_detail(proposal_id: str) -> dict[str, object]:
        try:
            return api.trade_detail(proposal_id)
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    @app.get("/trades/{proposal_id}/report", dependencies=[Depends(require_auth)])
    def trade_report(proposal_id: str) -> dict[str, object]:
        try:
            return api.trade_report(proposal_id)
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    @app.get("/no-trades", dependencies=[Depends(require_auth)])
    def list_no_trades() -> list[dict[str, object]]:
        return trading_app.backend.list_no_trades_payload()

    @app.post("/proposals", dependencies=[Depends(require_auth)])
    def submit_proposal(payload: dict[str, Any]) -> dict[str, object]:
        try:
            proposal = ProposalPayloadMapper.from_dict(payload)
        except KeyError as exc:
            raise http_error(400, "INVALID_PAYLOAD", f"Missing field: {exc.args[0]}") from exc
        except ValueError as exc:
            raise http_error(400, "INVALID_PAYLOAD", str(exc)) from exc
        return api.submit_proposal(ProposalSubmitRequest(proposal))

    @app.post("/commands", dependencies=[Depends(require_auth)])
    def command(payload: dict[str, Any]) -> dict[str, object]:
        try:
            portfolio = _build_portfolio_payload(payload)
            return api.command(
                CommandRequest(
                    actor=portfolio["actor"],
                    command=payload["command"],
                    portfolio_equity=portfolio["portfolio_equity"],
                    aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                    daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                    open_positions_count=portfolio["open_positions_count"],
                    execute_on_approve=bool(payload.get("execute_on_approve", True)),
                    render_mode=portfolio["render_mode"],
                    now=portfolio["now"],
                )
            )
        except KeyError as exc:
            raise http_error(400, "INVALID_PAYLOAD", f"Missing field: {exc.args[0]}") from exc

    @app.post("/proposals/{proposal_id}/approve", dependencies=[Depends(require_auth)])
    def approve_proposal(proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        payload = payload or {}
        portfolio = _build_portfolio_payload(payload)
        return api.command(
            CommandRequest(
                actor=portfolio["actor"],
                command=f"APPROVE {proposal_id}",
                portfolio_equity=portfolio["portfolio_equity"],
                aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                open_positions_count=portfolio["open_positions_count"],
                execute_on_approve=bool(payload.get("execute_on_approve", True)),
                render_mode=portfolio["render_mode"],
                now=portfolio["now"],
            )
        )

    @app.post("/proposals/{proposal_id}/reject", dependencies=[Depends(require_auth)])
    def reject_proposal(proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        payload = payload or {}
        portfolio = _build_portfolio_payload(payload)
        return api.command(
            CommandRequest(
                actor=portfolio["actor"],
                command=f"REJECT {proposal_id}",
                portfolio_equity=portfolio["portfolio_equity"],
                aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                open_positions_count=portfolio["open_positions_count"],
                render_mode=portfolio["render_mode"],
                now=portfolio["now"],
            )
        )

    @app.post("/proposals/{proposal_id}/modify", dependencies=[Depends(require_auth)])
    def modify_proposal(proposal_id: str, payload: dict[str, Any]) -> dict[str, object]:
        if "replacement" not in payload or "changes" not in payload:
            raise http_error(400, "INVALID_PAYLOAD", "Fields 'changes' and 'replacement' are required for modify")
        portfolio = _build_portfolio_payload(payload)
        try:
            replacement = ProposalPayloadMapper.from_dict(payload["replacement"])
        except (KeyError, ValueError) as exc:
            raise http_error(400, "INVALID_PAYLOAD", f"Invalid replacement payload: {exc}") from exc
        return api.command(
            CommandRequest(
                actor=portfolio["actor"],
                command=f"MODIFY {proposal_id}: {payload['changes']}",
                portfolio_equity=portfolio["portfolio_equity"],
                aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                open_positions_count=portfolio["open_positions_count"],
                render_mode=portfolio["render_mode"],
                replacement=replacement,
                now=portfolio["now"],
            )
        )

    @app.post("/trades/{proposal_id}/execute", dependencies=[Depends(require_auth)])
    def execute(proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        payload = payload or {}
        portfolio = _build_portfolio_payload(payload)
        try:
            return api.execute_approved_proposal(
                proposal_id,
                actor=portfolio["actor"],
                portfolio_equity=portfolio["portfolio_equity"],
                aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                open_positions_count=portfolio["open_positions_count"],
                render_mode=portfolio["render_mode"],
                now=portfolio["now"],
            )
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    return RestAppBundle(app=app, api=api)
