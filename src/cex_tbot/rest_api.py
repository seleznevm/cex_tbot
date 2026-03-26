from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
        return TradeProposal(
            proposal_id=payload.get("proposal_id", "proposal"),
            proposal_version=int(payload.get("proposal_version", 1)),
            agent_name=payload["agent_name"],
            strategy_id=payload["strategy_id"],
            strategy_version=payload["strategy_version"],
            market_context_id=payload["market_context_id"],
            symbol=payload["symbol"],
            timeframe=payload["timeframe"],
            direction=TradeDirection(payload["direction"]),
            entry_zone_min=float(payload["entry_zone_min"]),
            entry_zone_max=float(payload["entry_zone_max"]),
            entry_split=entry_split,
            stop_loss=float(payload["stop_loss"]),
            take_profit_1=float(payload["take_profit_1"]),
            take_profit_2=float(payload["take_profit_2"]),
            risk_percent=float(payload["risk_percent"]),
            risk_usd=float(payload["risk_usd"]),
            position_size=float(payload["position_size"]),
            confidence_score=float(payload["confidence_score"]),
            thesis=payload["thesis"],
            invalidity_condition=payload["invalidity_condition"],
            liquidity_check=payload["liquidity_check"],
            data_freshness_ms=int(payload["data_freshness_ms"]),
            created_at=ProposalPayloadMapper._parse_datetime(payload.get("created_at")),
            expires_at=ProposalPayloadMapper._parse_datetime(payload.get("expires_at")),
            exchange=Exchange(payload.get("exchange", Exchange.GATE.value)),
            market_type=MarketType(payload.get("market_type", MarketType.USDT_PERPETUAL.value)),
            contract_type=ContractType(payload.get("contract_type", ContractType.PERPETUAL.value)),
            status=ProposalStatus(payload.get("status", ProposalStatus.GENERATED.value)),
        )

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
            return value
        if value is None:
            return datetime.now().astimezone()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def create_rest_app(*, storage_dir: str | Path | None = None) -> RestAppBundle:
    try:
        from fastapi import FastAPI, HTTPException
    except ModuleNotFoundError as exc:
        raise RestApiDependencyError(
            "FastAPI is not installed. Install optional dependencies to use the REST bridge."
        ) from exc

    resolved_storage = Path(storage_dir) if storage_dir is not None else None
    trading_app = build_app(storage_dir=resolved_storage)
    api = trading_app.api
    app = FastAPI(title="cex_tbot REST bridge", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "storage": str(resolved_storage) if resolved_storage is not None else None}

    @app.get("/session/summary")
    def session_summary() -> dict[str, object]:
        return api.session_summary()

    @app.get("/dashboard")
    def dashboard() -> dict[str, object]:
        return api.dashboard()

    @app.get("/trades")
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

    @app.get("/trades/{proposal_id}")
    def trade_detail(proposal_id: str) -> dict[str, object]:
        try:
            return api.trade_detail(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown proposal_id: {proposal_id}") from exc

    @app.get("/trades/{proposal_id}/report")
    def trade_report(proposal_id: str) -> dict[str, object]:
        try:
            return api.trade_report(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown proposal_id: {proposal_id}") from exc

    @app.post("/proposals")
    def submit_proposal(payload: dict[str, Any]) -> dict[str, object]:
        proposal = ProposalPayloadMapper.from_dict(payload)
        return api.submit_proposal(ProposalSubmitRequest(proposal))

    @app.post("/commands")
    def command(payload: dict[str, Any]) -> dict[str, object]:
        try:
            return api.command(
                CommandRequest(
                    actor=payload.get("actor", "Mike"),
                    command=payload["command"],
                    portfolio_equity=float(payload.get("portfolio_equity", 10_000.0)),
                    aggregate_open_risk_pct=float(payload.get("aggregate_open_risk_pct", 0.0)),
                    daily_drawdown_pct=float(payload.get("daily_drawdown_pct", 0.0)),
                    open_positions_count=int(payload.get("open_positions_count", 0)),
                    execute_on_approve=bool(payload.get("execute_on_approve", True)),
                    render_mode=str(payload.get("render_mode", "plain")),
                    now=ProposalPayloadMapper._parse_datetime(payload["now"]) if payload.get("now") else None,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc

    @app.post("/trades/{proposal_id}/execute")
    def execute(proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        payload = payload or {}
        try:
            return api.execute_approved_proposal(
                proposal_id,
                actor=payload.get("actor", "Mike"),
                portfolio_equity=float(payload.get("portfolio_equity", 10_000.0)),
                aggregate_open_risk_pct=float(payload.get("aggregate_open_risk_pct", 0.0)),
                daily_drawdown_pct=float(payload.get("daily_drawdown_pct", 0.0)),
                open_positions_count=int(payload.get("open_positions_count", 0)),
                render_mode=str(payload.get("render_mode", "plain")),
                now=ProposalPayloadMapper._parse_datetime(payload["now"]) if payload.get("now") else None,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown proposal_id: {proposal_id}") from exc

    return RestAppBundle(app=app, api=api)
