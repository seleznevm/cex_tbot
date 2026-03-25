from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cex_tbot.api_surface import ApiSurface, CommandRequest, ProposalSubmitRequest
from cex_tbot.bootstrap import build_app
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection


@dataclass(frozen=True)
class DemoArtifacts:
    proposal_id: str
    flow: str
    storage: str
    storage_dir: str | None
    proposal_submit: dict[str, object]
    approval_response: dict[str, object]
    execution_response: dict[str, object] | None
    trade_detail: dict[str, object]
    trade_report: dict[str, object]
    session_summary: dict[str, object]
    dashboard: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return _json_ready(asdict(self))

    def to_text(self) -> str:
        lines = [
            "cex_tbot semi-auto demo",
            f"flow={self.flow}",
            f"storage={self.storage}",
            f"proposal_id={self.proposal_id}",
            f"submit_status={self.proposal_submit['status']}",
            f"approval_mode={self.approval_response['mode']}",
            "approval_report:",
            str(self.approval_response["text"]),
        ]
        if self.execution_response is not None:
            lines.extend(
                [
                    "execution_report:",
                    str(self.execution_response["text"]),
                ]
            )
        lines.extend(
            [
                "session_summary:",
                f"- total_proposals={self.session_summary['total_proposals']}",
                f"- executed_proposals={self.session_summary['executed_proposals']}",
                f"- execution_events={self.session_summary['execution_events']}",
                f"- operator_commands={self.session_summary['operator_commands']}",
                "dashboard_latest_trade:",
            ]
        )
        latest = self.dashboard["latest_trades"][0] if self.dashboard["latest_trades"] else None
        if latest is None:
            lines.append("- none")
        else:
            lines.append(
                f"- {latest['symbol']} {latest['direction']} status={latest['status']} events={latest['event_count']} snapshots={latest['snapshot_count']}"
            )
        return "\n".join(lines)


FIXED_DEMO_NOW = datetime(2026, 3, 25, 12, 0, tzinfo=UTC)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def build_demo_proposal(*, now: datetime = FIXED_DEMO_NOW) -> TradeProposal:
    return TradeProposal(
        proposal_id="proposal_demo_btc_breakout",
        agent_name="Luma",
        strategy_id="breakout_reclaim",
        strategy_version="v3",
        market_context_id="ctx_demo_btc_20260325",
        symbol="BTC_USDT",
        timeframe="15m",
        direction=TradeDirection.LONG,
        entry_zone_min=84150.0,
        entry_zone_max=84300.0,
        entry_split=[
            EntrySplitLeg(1, 84180.0, 60.0, 0.6, now + timedelta(minutes=8)),
            EntrySplitLeg(2, 84260.0, 40.0, 0.4, now + timedelta(minutes=10)),
        ],
        stop_loss=83890.0,
        take_profit_1=84680.0,
        take_profit_2=85120.0,
        risk_percent=0.5,
        risk_usd=50.0,
        position_size=0.02,
        confidence_score=0.84,
        thesis="15m reclaim holds above local range with clean liquidity and acceptable spread.",
        invalidity_condition="acceptance back below reclaim and failure to hold the entry zone",
        liquidity_check="spread<8bps depth>1m OI stable",
        data_freshness_ms=12_000,
        created_at=now,
        expires_at=now + timedelta(minutes=20),
        status=ProposalStatus.PENDING_APPROVAL,
    )


def run_demo(*, flow: str = "approve-execute", storage_dir: str | Path | None = None, now: datetime = FIXED_DEMO_NOW) -> DemoArtifacts:
    app = build_app(storage_dir=storage_dir)
    api = app.api
    proposal = build_demo_proposal(now=now)
    proposal_submit = api.submit_proposal(ProposalSubmitRequest(proposal))

    approval_response = api.command(
        CommandRequest(
            actor="Mike",
            command=f"APPROVE {proposal.proposal_id}",
            portfolio_equity=10_000.0,
            aggregate_open_risk_pct=0.0,
            daily_drawdown_pct=0.0,
            open_positions_count=0,
            execute_on_approve=flow == "approve-execute",
            now=now,
        )
    )

    execution_response = None
    if flow == "approve-then-execute":
        execution_response = api.execute_approved_proposal(
            proposal.proposal_id,
            actor="Mike",
            portfolio_equity=10_000.0,
            aggregate_open_risk_pct=0.0,
            daily_drawdown_pct=0.0,
            open_positions_count=0,
            now=now,
        )

    trade_detail = api.trade_detail(proposal.proposal_id)
    trade_report = api.trade_report(proposal.proposal_id)
    session_summary = api.session_summary()
    dashboard = api.dashboard()

    return DemoArtifacts(
        proposal_id=proposal.proposal_id,
        flow=flow,
        storage="file" if storage_dir is not None else "memory",
        storage_dir=str(storage_dir) if storage_dir is not None else None,
        proposal_submit=proposal_submit,
        approval_response=approval_response,
        execution_response=execution_response,
        trade_detail=trade_detail,
        trade_report=trade_report,
        session_summary=session_summary,
        dashboard=dashboard,
    )


def render_demo(flow: str = "approve-execute", *, storage_dir: str | Path | None = None, fmt: str = "text") -> str:
    artifacts = run_demo(flow=flow, storage_dir=storage_dir)
    if fmt == "json":
        return json.dumps(artifacts.to_payload(), ensure_ascii=False)
    return artifacts.to_text()
