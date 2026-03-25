from __future__ import annotations

import argparse
import json
from pathlib import Path

from cex_tbot import build_app
from cex_tbot.api_surface import CommandRequest, ProposalSubmitRequest, TradeListRequest
from cex_tbot.decision_contracts import NoTradeDecision
from cex_tbot.demo import build_demo_proposal, render_demo
from cex_tbot.enums import NoTradeReasonCode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cex_tbot local runtime entrypoint")
    parser.add_argument(
        "--storage-dir",
        type=Path,
        help="Optional base directory for file-backed session state (works for default status mode and subcommands)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for default status mode and subcommands",
    )
    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser("status", help="Print bootstrap/runtime status")
    status_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    status_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format for bootstrap status")

    demo_parser = subparsers.add_parser("demo", help="Run deterministic semi-auto demo flow")
    demo_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    demo_parser.add_argument("--format", choices=("text", "json"), default="text", help="Demo output format")
    demo_parser.add_argument(
        "--flow",
        choices=("approve-execute", "approve-then-execute"),
        default="approve-execute",
        help="Choose immediate execution or explicit two-step execution",
    )

    submit_parser = subparsers.add_parser("submit-demo", help="Submit the deterministic demo proposal into the current session store")
    submit_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    submit_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    command_parser = subparsers.add_parser("command", help="Run operator command against stored proposals")
    command_parser.add_argument("raw_command", help="Operator command, e.g. APPROVE proposal_1")
    command_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    command_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    command_parser.add_argument("--render-mode", choices=("plain", "operator", "telegram", "compact"), default="operator")
    command_parser.add_argument("--actor", default="Mike")
    command_parser.add_argument("--portfolio-equity", type=float, default=10_000.0)
    command_parser.add_argument("--aggregate-open-risk-pct", type=float, default=0.0)
    command_parser.add_argument("--daily-drawdown-pct", type=float, default=0.0)
    command_parser.add_argument("--open-positions-count", type=int, default=0)
    command_parser.add_argument("--approve-only", action="store_true", help="For APPROVE, stop after approval without execution")

    execute_parser = subparsers.add_parser("execute", help="Execute an already approved proposal")
    execute_parser.add_argument("proposal_id")
    execute_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    execute_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    execute_parser.add_argument("--render-mode", choices=("plain", "operator", "telegram", "compact"), default="operator")
    execute_parser.add_argument("--actor", default="Mike")
    execute_parser.add_argument("--portfolio-equity", type=float, default=10_000.0)
    execute_parser.add_argument("--aggregate-open-risk-pct", type=float, default=0.0)
    execute_parser.add_argument("--daily-drawdown-pct", type=float, default=0.0)
    execute_parser.add_argument("--open-positions-count", type=int, default=0)

    list_parser = subparsers.add_parser("list", help="List stored trades")
    list_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    list_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    list_parser.add_argument("--status")
    list_parser.add_argument("--symbol")
    list_parser.add_argument("--direction")
    list_parser.add_argument("--sort-by", default="proposal_id")
    list_parser.add_argument("--descending", action="store_true")
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--offset", type=int, default=0)

    detail_parser = subparsers.add_parser("detail", help="Show stored trade detail")
    detail_parser.add_argument("proposal_id")
    detail_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    detail_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    report_parser = subparsers.add_parser("report", help="Render a report for a stored trade")
    report_parser.add_argument("proposal_id")
    report_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    report_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    report_parser.add_argument("--render-mode", choices=("plain", "operator", "telegram", "compact"), default="operator")

    dashboard_parser = subparsers.add_parser("dashboard", help="Show dashboard payload")
    dashboard_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    dashboard_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    no_trade_parser = subparsers.add_parser("no-trade-demo", help="Store a deterministic no-trade decision")
    no_trade_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    no_trade_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    no_trade_list_parser = subparsers.add_parser("list-no-trades", help="List stored no-trade decisions")
    no_trade_list_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    no_trade_list_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    halt_parser = subparsers.add_parser("halt", help="Activate emergency halt")
    halt_parser.add_argument("reason")
    halt_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    halt_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    unhalt_parser = subparsers.add_parser("unhalt", help="Clear emergency halt")
    unhalt_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    unhalt_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    return parser


def _resolve_common_option(args: argparse.Namespace, name: str):
    command_value = getattr(args, name, None)
    if command_value is not None:
        return command_value
    return getattr(args, f"global_{name}")


def _print_payload(payload: object, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_status(*, storage_dir: Path | None, fmt: str) -> str:
    app = build_app(storage_dir=storage_dir)
    payload = {
        "status": "ok",
        "storage": "file" if storage_dir is not None else "memory",
        "storage_dir": str(storage_dir) if storage_dir is not None else None,
        "execution_mode": app.config.execution_mode,
        "exchange": app.config.exchange.value,
        "market_type": app.config.market_type.value,
        "session_summary": app.backend.get_session_summary_payload(),
    }
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False)
    return "\n".join(
        [
            "cex_tbot bootstrap: OK",
            f"storage={payload['storage']}",
            f"execution_mode={payload['execution_mode']}",
            f"exchange={payload['exchange']} market_type={payload['market_type']}",
            "session="
            f"proposals={payload['session_summary']['total_proposals']} "
            f"commands={payload['session_summary']['operator_commands']}",
        ]
    )


def render_trade_list_text(items: list[dict[str, object]]) -> str:
    if not items:
        return "No trades stored."
    lines = ["Stored trades:"]
    for item in items:
        lines.append(
            f"- {item['proposal_id']} | {item['symbol']} {item['direction']} | {item['status']} | conf={item['confidence_score']:.2f} | events={item['event_count']} snapshots={item['snapshot_count']}"
        )
    return "\n".join(lines)


def render_trade_detail_text(detail: dict[str, object]) -> str:
    timeline = detail["timeline"]
    lines = [
        f"Trade detail — {detail['proposal_id']}",
        f"Status: {detail['status']}",
        f"Agent/strategy: {detail['agent_name']} / {detail['strategy_id']}@{detail['strategy_version']}",
        f"Symbol: {detail['symbol']} {detail['direction']} {detail['timeframe']}",
        f"Confidence: {detail['confidence_score']:.2f}",
        f"Entry zone: {detail['entry_zone_min']} → {detail['entry_zone_max']}",
        f"Stop: {detail['stop_loss']} | TP1: {detail['take_profit_1']} | TP2: {detail['take_profit_2']}",
        f"Risk: {detail['risk_percent']:.2f}% / ${detail['risk_usd']:.2f} | size={detail['position_size']}",
        f"Liquidity: {detail['liquidity_check']}",
        f"Invalidation: {detail['invalidity_condition']}",
        f"Created: {detail['created_at']}",
        f"Expires: {detail['expires_at']}",
        f"Approvals: {detail['approval_decision_count']} | Operator commands: {detail['operator_command_count']}",
        f"Timeline: events={timeline['event_count']} snapshots={timeline['snapshot_count']}",
    ]
    for event in timeline["events"][-6:]:
        lines.append(f"- {event['kind']}: {event['message']}")
    return "\n".join(lines)


def render_dashboard_text(payload: dict[str, object]) -> str:
    lines = [
        "Dashboard",
        f"- proposals={payload['kpis']['total_proposals']} no_trades={payload['kpis']['total_no_trade_decisions']} executed={payload['kpis']['executed_proposals']} rejected={payload['kpis']['rejected_proposals']}",
        f"- commands={payload['kpis']['operator_commands']} approval_decisions={payload['risk']['approval_decisions']} execution_events={payload['risk']['execution_events']} halt={payload['risk']['emergency_halt_active']}",
    ]
    latest = payload["latest_trades"]
    if latest:
        lines.append("Latest trades:")
        for item in latest[:5]:
            lines.append(f"- {item['proposal_id']} {item['symbol']} {item['status']} conf={item['confidence_score']:.2f}")
    else:
        lines.append("Latest trades: none")
    return "\n".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    setattr(args, "global_storage_dir", getattr(args, "storage_dir", None))
    setattr(args, "global_format", getattr(args, "format", "text"))

    command = args.command or "status"
    storage_dir = _resolve_common_option(args, "storage_dir")
    fmt = _resolve_common_option(args, "format")
    app = build_app(storage_dir=storage_dir)
    api = app.api

    if command == "demo":
        print(render_demo(flow=args.flow, storage_dir=storage_dir, fmt=fmt))
        return 0

    if command == "submit-demo":
        payload = api.submit_proposal(ProposalSubmitRequest(build_demo_proposal()))
        print(_print_payload(payload, fmt))
        return 0

    if command == "command":
        payload = api.command(
            CommandRequest(
                actor=args.actor,
                command=args.raw_command,
                portfolio_equity=args.portfolio_equity,
                aggregate_open_risk_pct=args.aggregate_open_risk_pct,
                daily_drawdown_pct=args.daily_drawdown_pct,
                open_positions_count=args.open_positions_count,
                execute_on_approve=not args.approve_only,
                render_mode=args.render_mode,
            )
        )
        print(_print_payload(payload, fmt))
        return 0

    if command == "execute":
        payload = api.execute_approved_proposal(
            args.proposal_id,
            actor=args.actor,
            portfolio_equity=args.portfolio_equity,
            aggregate_open_risk_pct=args.aggregate_open_risk_pct,
            daily_drawdown_pct=args.daily_drawdown_pct,
            open_positions_count=args.open_positions_count,
            render_mode=args.render_mode,
        )
        print(_print_payload(payload, fmt))
        return 0

    if command == "list":
        items = api.list_trades(
            TradeListRequest(
                status=args.status,
                symbol=args.symbol,
                direction=args.direction,
                sort_by=args.sort_by,
                descending=args.descending,
                limit=args.limit,
                offset=args.offset,
            )
        )
        print(_print_payload(items, fmt) if fmt == "json" else render_trade_list_text(items))
        return 0

    if command == "detail":
        detail = api.trade_detail(args.proposal_id)
        print(_print_payload(detail, fmt) if fmt == "json" else render_trade_detail_text(detail))
        return 0

    if command == "report":
        if fmt == "json":
            print(_print_payload(api.trade_report(args.proposal_id), fmt))
        else:
            print(app.backend.get_trade_report_text(args.proposal_id, render_mode=args.render_mode))
        return 0

    if command == "dashboard":
        payload = api.dashboard()
        print(_print_payload(payload, fmt) if fmt == "json" else render_dashboard_text(payload))
        return 0

    if command == "no-trade-demo":
        decision = app.backend.submit_no_trade_decision(
            NoTradeDecision(
                agent_name="Luma",
                strategy_id="breakout_reclaim",
                strategy_version="v3",
                symbol="BTC_USDT",
                timeframe="15m",
                confidence_score=0.41,
                reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
                reason_text="Confidence stayed below execution threshold after validation.",
                market_context_id="ctx_demo_btc_20260325",
                liquidity_check="spread ok but setup confidence insufficient",
                data_freshness_ms=12_000,
            )
        )
        payload = app.backend.serializer.no_trade_decision(decision)
        print(_print_payload(payload, fmt))
        return 0

    if command == "list-no-trades":
        payload = app.backend.list_no_trades_payload()
        print(_print_payload(payload, fmt))
        return 0

    if command == "halt":
        app.backend.activate_emergency_halt(args.reason)
        payload = app.backend.get_session_summary_payload()
        print(_print_payload(payload, fmt))
        return 0

    if command == "unhalt":
        app.backend.clear_emergency_halt()
        payload = app.backend.get_session_summary_payload()
        print(_print_payload(payload, fmt))
        return 0

    print(render_status(storage_dir=storage_dir, fmt=fmt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
