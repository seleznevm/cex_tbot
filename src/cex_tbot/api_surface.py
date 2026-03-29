from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.query_params import TradeQuery
from cex_tbot.risk_engine import PortfolioState


@dataclass(frozen=True)
class CommandRequest:
    actor: str
    command: str
    portfolio_equity: float
    aggregate_open_risk_pct: float = 0.0
    daily_drawdown_pct: float = 0.0
    open_positions_count: int = 0
    execute_on_approve: bool = True
    render_mode: str = "plain"
    replacement: TradeProposal | None = None
    now: datetime | None = None


@dataclass(frozen=True)
class ProposalSubmitRequest:
    proposal: TradeProposal


@dataclass(frozen=True)
class ExecuteRequest:
    proposal_id: str
    actor: str
    portfolio_equity: float
    aggregate_open_risk_pct: float = 0.0
    daily_drawdown_pct: float = 0.0
    open_positions_count: int = 0
    render_mode: str = "plain"
    now: datetime | None = None


@dataclass(frozen=True)
class TradeListRequest:
    status: str | None = None
    symbol: str | None = None
    direction: str | None = None
    sort_by: str = "proposal_id"
    descending: bool = False
    limit: int | None = None
    offset: int = 0


class ApiSurface:
    def __init__(self, backend: TradingBackendService) -> None:
        self.backend = backend

    def submit_proposal(self, request: ProposalSubmitRequest) -> dict[str, object]:
        proposal = self.backend.submit_proposal(request.proposal)
        return {"proposal_id": proposal.proposal_id, "status": proposal.status.value}

    def command(self, request: CommandRequest) -> dict[str, object]:
        portfolio = PortfolioState(
            equity=request.portfolio_equity,
            aggregate_open_risk_pct=request.aggregate_open_risk_pct,
            daily_drawdown_pct=request.daily_drawdown_pct,
            open_positions_count=request.open_positions_count,
        )
        return self.backend.run_operator_command_payload(
            request.actor,
            request.command,
            portfolio,
            replacement=request.replacement,
            execute_on_approve=request.execute_on_approve,
            render_mode=request.render_mode,
            now=request.now,
        )

    def execute_approved_proposal(self, proposal_id: str, **kwargs: object) -> dict[str, object]:
        request = ExecuteRequest(proposal_id=proposal_id, **kwargs)
        portfolio = PortfolioState(
            equity=request.portfolio_equity,
            aggregate_open_risk_pct=request.aggregate_open_risk_pct,
            daily_drawdown_pct=request.daily_drawdown_pct,
            open_positions_count=request.open_positions_count,
        )
        return self.backend.execute_approved_proposal_payload(
            request.proposal_id,
            portfolio,
            actor=request.actor,
            render_mode=request.render_mode,
            now=request.now,
        )

    def list_trades(self, request: TradeListRequest | None = None) -> list[dict[str, object]]:
        query = None
        if request is not None:
            query = TradeQuery(
                status=request.status,
                symbol=request.symbol,
                direction=request.direction,
                sort_by=request.sort_by,
                descending=request.descending,
                limit=request.limit,
                offset=request.offset,
            )
        return self.backend.list_trades_payload(query)

    def trade_detail(self, proposal_id: str) -> dict[str, object]:
        return self.backend.get_trade_detail_payload(proposal_id)

    def trade_report(self, proposal_id: str) -> dict[str, object]:
        return self.backend.get_trade_report_payload(proposal_id)

    def session_summary(self) -> dict[str, object]:
        return self.backend.get_session_summary_payload()

    def dashboard(self) -> dict[str, object]:
        return self.backend.get_dashboard_payload()

    def post_analysis(self) -> dict[str, object]:
        return self.backend.get_post_analysis_payload()

    def sync_demo_orders(self, proposal_id: str) -> dict[str, object]:
        records = self.backend.sync_demo_orders(proposal_id)
        return {
            "proposal_id": proposal_id,
            "orders": [
                {
                    "order_id": item.order_id,
                    "role": item.role,
                    "contract": item.contract,
                    "side": item.side,
                    "size": item.size,
                    "status": item.status,
                    "trigger_price": item.trigger_price,
                    "order_price": item.order_price,
                    "reduce_only": item.reduce_only,
                    "linked_entry_order_id": item.linked_entry_order_id,
                    "synced_at": item.synced_at.isoformat(),
                }
                for item in records
            ],
        }

    def clear_safety(self) -> dict[str, object]:
        self.backend.clear_safety_controls()
        return self.backend.get_session_summary_payload()
