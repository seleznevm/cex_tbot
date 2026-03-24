from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.decision_contracts import TradeProposal
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

    def list_trades(self) -> list[dict[str, object]]:
        return self.backend.list_trades_payload()

    def trade_detail(self, proposal_id: str) -> dict[str, object]:
        return self.backend.get_trade_detail_payload(proposal_id)

    def trade_report(self, proposal_id: str) -> dict[str, object]:
        return self.backend.get_trade_report_payload(proposal_id)

    def session_summary(self) -> dict[str, object]:
        return self.backend.get_session_summary_payload()

    def dashboard(self) -> dict[str, object]:
        return self.backend.get_dashboard_payload()
