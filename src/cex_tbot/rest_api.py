from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any

from cex_tbot.api_surface import ApiSurface, CommandRequest, ProposalSubmitRequest, TradeListRequest
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.openclaw_wrapper import OpenClawInboundMessage, OpenClawOutboundMessage, OpenClawTopicWrapper
from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge
from cex_tbot.bootstrap import build_app
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ContractType, Exchange, MarketType, ProposalStatus, TradeDirection
from cex_tbot.spa import frontend_dir
from cex_tbot.topic_producer import TopicProposalProducer
from cex_tbot.web_schemas import (
    CommandPayload,
    DashboardPayload,
    ErrorEnvelope,
    HaltPayload,
    PostAnalysisPayload,
    HealthPayload,
    ModifyProposalPayload,
    NoTradeDecisionPayload,
    PortfolioContextPayload,
    ProposalPayload,
    ProposalStoredResponse,
    RenderedResponsePayload,
    SessionSummaryPayload,
    TradeDetailPayload,
    TradeListItemPayload,
    TradeListPagePayload,
    TradeReportPayload,
)


class RestApiDependencyError(RuntimeError):
    """Raised when optional REST dependencies are unavailable."""


@dataclass(frozen=True)
class RestAppBundle:
    app: Any
    api: ApiSurface


class ProposalPayloadMapper:
    @staticmethod
    def from_dict(payload: dict[str, Any] | ProposalPayload) -> TradeProposal:
        if isinstance(payload, ProposalPayload):
            payload = payload.model_dump(mode="python")
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
        if payload.get("proposal_id"):
            proposal_kwargs["proposal_id"] = payload["proposal_id"]
        if payload.get("proposal_version") is not None:
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


@dataclass(frozen=True)
class TopicCommandPayload:
    sender_id: str
    text: str
    sender_name: str | None = None
    channel: str | None = None
    chat_id: str | None = None
    thread_id: str | None = None


def _build_portfolio_payload(payload: dict[str, Any] | PortfolioContextPayload) -> dict[str, Any]:
    if isinstance(payload, PortfolioContextPayload):
        payload = payload.model_dump(mode="python")
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
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ModuleNotFoundError as exc:
        raise RestApiDependencyError(
            "FastAPI is not installed. Install optional dependencies to use the REST bridge."
        ) from exc

    resolved_storage = Path(storage_dir) if storage_dir is not None else None
    trading_app = build_app(storage_dir=resolved_storage)
    api = trading_app.api
    auth = RestAuth(api_token)
    app = FastAPI(title="cex_tbot REST bridge", version="0.3.0")
    allowed_sender_ids = os.environ.get("CEX_TBOT_ALLOWED_SENDER_IDS", "125619710")
    bridge = TransportCommandBridge(
        BotCommandDispatcher(BotCommandAdapter(trading_app.backend, config=trading_app.config, app=trading_app)),
        sender_policy=SenderPolicy(
            allowed_sender_ids=frozenset(item.strip() for item in allowed_sender_ids.split(",") if item.strip()),
            allow_empty_policy=False,
        ),
        write_sender_policy=SenderPolicy(
            allowed_sender_ids=frozenset(item.strip() for item in allowed_sender_ids.split(",") if item.strip()),
            allow_empty_policy=False,
        ),
        audit_transcript=trading_app.backend.session.operator_transcript,
    )
    topic_wrapper = OpenClawTopicWrapper(bridge)
    static_dir = frontend_dir()

    def require_auth(x_api_key: str | None = Header(default=None)) -> None:
        if not auth.verify(x_api_key):
            raise HTTPException(
                status_code=401,
                detail=RestErrorFactory.payload("UNAUTHORIZED", "Missing or invalid X-API-Key header"),
            )

    def http_error(status_code: int, code: str, message: str, *, details: dict[str, Any] | None = None) -> HTTPException:
        return HTTPException(status_code=status_code, detail=RestErrorFactory.payload(code, message, details=details))

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/app-config", dependencies=[Depends(require_auth)], include_in_schema=False)
    def app_config() -> dict[str, object]:
        return {
            "apiBase": "",
            "authEnabled": auth.enabled,
            "pollingMsDefault": 5000,
        }

    app.mount("/app", StaticFiles(directory=static_dir), name="app")

    @app.get("/health", dependencies=[Depends(require_auth)], response_model=HealthPayload, responses={401: {"model": ErrorEnvelope}})
    def health() -> HealthPayload:
        return HealthPayload(
            status="ok",
            storage=str(resolved_storage) if resolved_storage is not None else None,
            auth_enabled=auth.enabled,
        )

    @app.get("/session/summary", dependencies=[Depends(require_auth)], response_model=SessionSummaryPayload, responses={401: {"model": ErrorEnvelope}})
    def session_summary() -> SessionSummaryPayload:
        return SessionSummaryPayload.model_validate(api.session_summary())

    @app.get("/dashboard", dependencies=[Depends(require_auth)], response_model=DashboardPayload, responses={401: {"model": ErrorEnvelope}})
    def dashboard() -> DashboardPayload:
        return DashboardPayload.model_validate(api.dashboard())

    @app.get("/post-analysis", dependencies=[Depends(require_auth)], response_model=PostAnalysisPayload, responses={401: {"model": ErrorEnvelope}})
    def post_analysis() -> PostAnalysisPayload:
        return PostAnalysisPayload.model_validate(api.post_analysis())

    @app.get("/proposals", dependencies=[Depends(require_auth)], response_model=TradeListPagePayload, responses={401: {"model": ErrorEnvelope}})
    @app.get("/trades", dependencies=[Depends(require_auth)], response_model=TradeListPagePayload, responses={401: {"model": ErrorEnvelope}})
    def list_trades(
        status: str | None = None,
        symbol: str | None = None,
        direction: str | None = None,
        sort_by: str = "proposal_id",
        descending: bool = False,
        limit: int | None = 10,
        offset: int = 0,
    ) -> TradeListPagePayload:
        payload = trading_app.backend.list_trades_page_payload(
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
        return TradeListPagePayload.model_validate(payload)

    @app.get("/proposals/{proposal_id}", dependencies=[Depends(require_auth)], response_model=TradeDetailPayload, responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}})
    @app.get("/trades/{proposal_id}", dependencies=[Depends(require_auth)], response_model=TradeDetailPayload, responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}})
    def trade_detail(proposal_id: str) -> TradeDetailPayload:
        try:
            return TradeDetailPayload.model_validate(api.trade_detail(proposal_id))
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    @app.get("/trades/{proposal_id}/report", dependencies=[Depends(require_auth)], response_model=TradeReportPayload, responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}})
    def trade_report(proposal_id: str) -> TradeReportPayload:
        try:
            return TradeReportPayload.model_validate(api.trade_report(proposal_id))
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    @app.get("/no-trades", dependencies=[Depends(require_auth)], response_model=list[NoTradeDecisionPayload], responses={401: {"model": ErrorEnvelope}})
    def list_no_trades() -> list[NoTradeDecisionPayload]:
        return [NoTradeDecisionPayload.model_validate(item) for item in trading_app.backend.list_no_trades_payload()]

    @app.post("/system/halt", dependencies=[Depends(require_auth)], response_model=SessionSummaryPayload, responses={401: {"model": ErrorEnvelope}})
    def halt_system(payload: HaltPayload) -> SessionSummaryPayload:
        trading_app.backend.activate_emergency_halt(payload.reason)
        return SessionSummaryPayload.model_validate(api.session_summary())

    @app.post("/system/unhalt", dependencies=[Depends(require_auth)], response_model=SessionSummaryPayload, responses={401: {"model": ErrorEnvelope}})
    def unhalt_system() -> SessionSummaryPayload:
        trading_app.backend.clear_emergency_halt()
        return SessionSummaryPayload.model_validate(api.session_summary())

    @app.post("/system/clear-safety", dependencies=[Depends(require_auth)], response_model=SessionSummaryPayload, responses={401: {"model": ErrorEnvelope}})
    def clear_safety() -> SessionSummaryPayload:
        return SessionSummaryPayload.model_validate(api.clear_safety())

    @app.post("/proposals", dependencies=[Depends(require_auth)], response_model=ProposalStoredResponse, responses={401: {"model": ErrorEnvelope}, 400: {"model": ErrorEnvelope}})
    def submit_proposal(payload: ProposalPayload) -> ProposalStoredResponse:
        try:
            proposal = ProposalPayloadMapper.from_dict(payload)
        except ValueError as exc:
            raise http_error(400, "INVALID_PAYLOAD", str(exc)) from exc
        return ProposalStoredResponse.model_validate(api.submit_proposal(ProposalSubmitRequest(proposal)))

    @app.post("/commands", dependencies=[Depends(require_auth)], response_model=RenderedResponsePayload, responses={401: {"model": ErrorEnvelope}, 400: {"model": ErrorEnvelope}})
    def command(payload: CommandPayload) -> RenderedResponsePayload:
        portfolio = _build_portfolio_payload(payload)
        return RenderedResponsePayload.model_validate(
            api.command(
                CommandRequest(
                    actor=portfolio["actor"],
                    command=payload.command,
                    portfolio_equity=portfolio["portfolio_equity"],
                    aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                    daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                    open_positions_count=portfolio["open_positions_count"],
                    execute_on_approve=payload.execute_on_approve,
                    render_mode=portfolio["render_mode"],
                    now=portfolio["now"],
                )
            )
        )

    @app.post("/topic/command", dependencies=[Depends(require_auth)])
    def topic_command(payload: TopicCommandPayload) -> dict[str, str | None]:
        outbound: OpenClawOutboundMessage = topic_wrapper.handle_inbound(
            OpenClawInboundMessage(
                sender_id=payload.sender_id,
                text=payload.text,
                sender_name=payload.sender_name,
                channel=payload.channel,
                chat_id=payload.chat_id,
                thread_id=payload.thread_id,
            )
        )
        return {
            "text": outbound.text,
            "chat_id": outbound.chat_id,
            "thread_id": outbound.thread_id,
        }

    @app.post("/proposals/{proposal_id}/approve", dependencies=[Depends(require_auth)], response_model=RenderedResponsePayload, responses={401: {"model": ErrorEnvelope}})
    def approve_proposal(proposal_id: str, payload: PortfolioContextPayload | None = None) -> RenderedResponsePayload:
        payload = payload or PortfolioContextPayload()
        portfolio = _build_portfolio_payload(payload)
        return RenderedResponsePayload.model_validate(
            api.command(
                CommandRequest(
                    actor=portfolio["actor"],
                    command=f"APPROVE {proposal_id}",
                    portfolio_equity=portfolio["portfolio_equity"],
                    aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                    daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                    open_positions_count=portfolio["open_positions_count"],
                    execute_on_approve=getattr(payload, "execute_on_approve", True),
                    render_mode=portfolio["render_mode"],
                    now=portfolio["now"],
                )
            )
        )

    @app.post("/proposals/{proposal_id}/reject", dependencies=[Depends(require_auth)], response_model=RenderedResponsePayload, responses={401: {"model": ErrorEnvelope}})
    def reject_proposal(proposal_id: str, payload: PortfolioContextPayload | None = None) -> RenderedResponsePayload:
        payload = payload or PortfolioContextPayload()
        portfolio = _build_portfolio_payload(payload)
        return RenderedResponsePayload.model_validate(
            api.command(
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
        )

    @app.post("/proposals/{proposal_id}/modify", dependencies=[Depends(require_auth)], response_model=RenderedResponsePayload, responses={401: {"model": ErrorEnvelope}, 400: {"model": ErrorEnvelope}})
    def modify_proposal(proposal_id: str, payload: ModifyProposalPayload) -> RenderedResponsePayload:
        portfolio = _build_portfolio_payload(payload)
        try:
            replacement = ProposalPayloadMapper.from_dict(payload.replacement)
        except ValueError as exc:
            raise http_error(400, "INVALID_PAYLOAD", f"Invalid replacement payload: {exc}") from exc
        return RenderedResponsePayload.model_validate(
            api.command(
                CommandRequest(
                    actor=portfolio["actor"],
                    command=f"MODIFY {proposal_id}: {payload.changes}",
                    portfolio_equity=portfolio["portfolio_equity"],
                    aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                    daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                    open_positions_count=portfolio["open_positions_count"],
                    render_mode=portfolio["render_mode"],
                    replacement=replacement,
                    now=portfolio["now"],
                )
            )
        )

    @app.post("/trades/{proposal_id}/sync-demo", dependencies=[Depends(require_auth)], responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}})
    def sync_demo(proposal_id: str) -> dict[str, object]:
        try:
            return api.sync_demo_orders(proposal_id)
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    @app.post("/trades/{proposal_id}/emit-conservative-alert", dependencies=[Depends(require_auth)], responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}})
    def emit_conservative_alert(proposal_id: str) -> dict[str, object]:
        try:
            assessment = api.conservative_alert_payload(proposal_id)
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc
        producer = TopicProposalProducer(
            trading_app.backend,
            OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7"),
        )
        outbound = producer.emit_conservative_alert(ConservativePolicyAssessment(**assessment))
        return {
            "text": outbound.text,
            "chat_id": outbound.chat_id,
            "thread_id": outbound.thread_id,
            "policy": assessment,
        }

    @app.post("/cron/autosync-demo", dependencies=[Depends(require_auth)], responses={401: {"model": ErrorEnvelope}})
    def cron_autosync_demo() -> dict[str, object]:
        producer = TopicProposalProducer(
            trading_app.backend,
            OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7"),
        )
        results = []
        proposal_ids = [item["proposal_id"] for item in api.list_trades() if trading_app.backend.session.demo_orders.list_for_proposal(str(item["proposal_id"]))]
        for proposal_id in proposal_ids:
            synced = api.sync_demo_orders(str(proposal_id))
            policy = synced["policy"]
            alert_texts = [a for a in policy["alerts"] if "No policy alerts" not in a]
            payload = {"proposal_id": proposal_id, "sync": synced}
            if alert_texts:
                outbound = producer.emit_conservative_alert(ConservativePolicyAssessment(**policy))
                payload["telegram_alert"] = {
                    "chat_id": outbound.chat_id,
                    "thread_id": outbound.thread_id,
                    "text": outbound.text,
                }
            results.append(payload)
        return {"items": results, "count": len(results)}

    @app.post("/trades/{proposal_id}/execute", dependencies=[Depends(require_auth)], response_model=RenderedResponsePayload, responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}})
    def execute(proposal_id: str, payload: PortfolioContextPayload | None = None) -> RenderedResponsePayload:
        payload = payload or PortfolioContextPayload()
        portfolio = _build_portfolio_payload(payload)
        try:
            return RenderedResponsePayload.model_validate(
                api.execute_approved_proposal(
                    proposal_id,
                    actor=portfolio["actor"],
                    portfolio_equity=portfolio["portfolio_equity"],
                    aggregate_open_risk_pct=portfolio["aggregate_open_risk_pct"],
                    daily_drawdown_pct=portfolio["daily_drawdown_pct"],
                    open_positions_count=portfolio["open_positions_count"],
                    render_mode=portfolio["render_mode"],
                    now=portfolio["now"],
                )
            )
        except KeyError as exc:
            raise http_error(404, "PROPOSAL_NOT_FOUND", f"Unknown proposal_id: {proposal_id}") from exc

    return RestAppBundle(app=app, api=api)
