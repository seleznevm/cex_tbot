from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys

from cex_tbot import build_app
from cex_tbot.api_surface import CommandRequest, ProposalSubmitRequest, TradeListRequest
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.demo import build_demo_proposal, render_demo
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.execution.demo_order_status_poller import DemoOrderStatusPoller
from cex_tbot.live_market_runner import LiveMarketPipelineRunner
from cex_tbot.market_pipeline import BinanceMarketDataPipeline
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.periodic_runner import PeriodicRunner
from cex_tbot.topic_producer import TopicProposalProducer
from cex_tbot.execution.policy import ConservativePolicyAssessment
from cex_tbot.proposal_contract import proposal_contract_text
from cex_tbot.proposal_json_parser import JsonTradeProposalParser
from cex_tbot.rest_api import RestApiDependencyError, create_rest_app
from cex_tbot.shared import utc_now


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

    sync_demo_parser = subparsers.add_parser("sync-demo", help="Sync Gate demo order states for a stored trade")
    sync_demo_parser.add_argument("proposal_id")
    sync_demo_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    sync_demo_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    dashboard_parser = subparsers.add_parser("dashboard", help="Show dashboard payload")
    dashboard_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    dashboard_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    post_analysis_parser = subparsers.add_parser("post-analysis", help="Show post-analysis and calibration summary")
    post_analysis_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    post_analysis_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    export_post_analysis_parser = subparsers.add_parser("post-analysis-export", help="Export post-analysis review snapshot to a file")
    export_post_analysis_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    export_post_analysis_parser.add_argument("--format", choices=("text", "json"), default="json", help="Export format")
    export_post_analysis_parser.add_argument("--out", type=Path, help="Optional explicit output path")

    diff_post_analysis_parser = subparsers.add_parser("post-analysis-diff", help="Diff two post-analysis review snapshots")
    diff_post_analysis_parser.add_argument("--current", type=Path, required=True, help="Current snapshot path")
    diff_post_analysis_parser.add_argument("--previous", type=Path, help="Previous snapshot path; defaults to prior file in the same directory")
    diff_post_analysis_parser.add_argument("--format", choices=("text", "json"), default="json", help="Output format")

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

    clear_safety_parser = subparsers.add_parser("clear-safety", help="Clear warning/block safety state without touching halt")
    clear_safety_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    clear_safety_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    demo_status_report_parser = subparsers.add_parser("demo-status-report", help="Emit a cron-friendly consolidated demo status report")
    demo_status_report_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    demo_status_report_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    demo_audit_report_parser = subparsers.add_parser("demo-audit-report", help="Emit a cron-friendly demo audit report")
    demo_audit_report_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    demo_audit_report_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    emit_demo_proposal_parser = subparsers.add_parser("emit-demo-proposal", help="Persist a deterministic proposal and render same-topic approval request")
    emit_demo_proposal_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    emit_demo_proposal_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    emit_demo_proposal_parser.add_argument("--chat-id", default="telegram:-1003832858724", help="Target chat id for rendered outbound payload")
    emit_demo_proposal_parser.add_argument("--thread-id", default="7", help="Target thread/topic id for rendered outbound payload")

    submit_and_emit_parser = subparsers.add_parser("submit-and-emit-demo", help="Submit deterministic proposal through workflow glue and render same-topic approval request")
    submit_and_emit_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    submit_and_emit_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    submit_and_emit_parser.add_argument("--chat-id", default="telegram:-1003832858724", help="Target chat id for rendered outbound payload")
    submit_and_emit_parser.add_argument("--thread-id", default="7", help="Target thread/topic id for rendered outbound payload")

    submit_and_emit_file_parser = subparsers.add_parser("submit-and-emit", help="Submit proposal JSON through same-topic producer")
    submit_and_emit_file_parser.add_argument("proposal_file", type=Path, nargs="?", help="Path to proposal JSON file")
    submit_and_emit_file_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    submit_and_emit_file_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    submit_and_emit_file_parser.add_argument("--chat-id", default="telegram:-1003832858724", help="Target chat id for rendered outbound payload")
    submit_and_emit_file_parser.add_argument("--thread-id", default="7", help="Target thread/topic id for rendered outbound payload")
    submit_and_emit_file_parser.add_argument("--print-contract", action="store_true", help="Print expected JSON contract and exit")

    serve_rest_parser = subparsers.add_parser("serve-rest", help="Run optional FastAPI REST bridge")
    serve_rest_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    serve_rest_parser.add_argument("--host", default="127.0.0.1")
    serve_rest_parser.add_argument("--port", type=int, default=8000)

    market_sync_parser = subparsers.add_parser("market-sync", help="Fetch Binance public market data into host-side JSON files")
    market_sync_parser.add_argument("--output-dir", type=Path, default=Path("/data/.openclaw/workspace/market"))
    market_sync_parser.add_argument("--universe-limit", type=int, default=150)
    market_sync_parser.add_argument("--interval-sec", type=int, default=300)
    market_sync_parser.add_argument("--loop", action="store_true", help="Keep refreshing on a fixed interval")
    market_sync_parser.add_argument("--runs", type=int, help="Optional max runs when used with --loop")
    market_sync_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    live_market_run_parser = subparsers.add_parser("live-market-run", help="Refresh market data, run live market proposal flow, and emit same-topic proposal/no-trade output")
    live_market_run_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    live_market_run_parser.add_argument("--market-dir", type=Path, default=Path("/data/.openclaw/workspace/market"), help="Directory for refreshed market JSON payloads")
    live_market_run_parser.add_argument("--chat-id", default="telegram:-1003832858724", help="Target chat id for rendered outbound payload")
    live_market_run_parser.add_argument("--thread-id", default="7", help="Target thread/topic id for rendered outbound payload")
    live_market_run_parser.add_argument("--universe-limit", type=int, default=150)
    live_market_run_parser.add_argument("--loop", action="store_true", help="Keep running the internal live-market loop instead of a single pass")
    live_market_run_parser.add_argument("--interval-sec", type=int, default=300, help="Periodic live-market loop interval in seconds")
    live_market_run_parser.add_argument("--runs", type=int, help="Optional max runs when used with --loop")
    live_market_run_parser.add_argument("--continue-on-error", action="store_true", help="Keep the loop alive when a run_once call raises or returns a structured failure")
    live_market_run_parser.add_argument("--stop-after-consecutive-failures", type=int, help="Optional failure threshold for tolerant loop mode")
    live_market_run_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    autosync_parser = subparsers.add_parser("autosync-demo", help="Continuously sync Gate demo order states for all tracked proposals")
    autosync_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    autosync_parser.add_argument("--interval-sec", type=int, default=30)
    autosync_parser.add_argument("--runs", type=int, default=1)
    autosync_parser.add_argument("--emit-telegram-alerts", action="store_true", help="Render Telegram topic payloads for conservative alerts after sync")
    autosync_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    alert_parser = subparsers.add_parser("emit-conservative-alert", help="Render conservative alert payload for Telegram topic delivery")
    alert_parser.add_argument("proposal_id")
    alert_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    alert_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")

    tg_runner_parser = subparsers.add_parser("tg-runner", help="Run Telegram group/topic polling bridge")
    tg_runner_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    tg_runner_parser.add_argument("--token", help="Telegram bot token; falls back to CEX_TBOT_TELEGRAM_BOT_TOKEN")
    tg_runner_parser.add_argument("--allowed-sender-ids", default="125619710", help="Comma-separated Telegram user ids allowed to operate the bot")
    tg_runner_parser.add_argument(
        "--allowed-json-sender-ids",
        default=None,
        help="Optional comma-separated Telegram user ids allowed to submit proposal JSON; defaults to --allowed-sender-ids",
    )
    tg_runner_parser.add_argument("--allowed-chat-ids", default="", help="Optional comma-separated Telegram chat ids")
    tg_runner_parser.add_argument("--allowed-thread-ids", default="", help="Optional comma-separated Telegram topic ids")

    return parser


def _resolve_common_option(args: argparse.Namespace, name: str):
    command_value = getattr(args, name, None)
    if command_value is not None:
        return command_value
    return getattr(args, f"global_{name}")


def _print_payload(payload: object, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=not _stdout_supports_utf8())
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=not _stdout_supports_utf8(), indent=2)


def _stdout_supports_utf8() -> bool:
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    return "utf" in encoding


def _parse_csv_set(raw: str | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    return frozenset(item.strip() for item in str(raw).split(",") if item.strip())


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
        return json.dumps(payload, ensure_ascii=not _stdout_supports_utf8())
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
        f"Trade detail - {detail['proposal_id']}",
        f"Status: {detail['status']}",
        f"Agent/strategy: {detail['agent_name']} / {detail['strategy_id']}@{detail['strategy_version']}",
        f"Symbol: {detail['symbol']} {detail['direction']} {detail['timeframe']}",
        f"Confidence: {detail['confidence_score']:.2f}",
        f"Entry zone: {detail['entry_zone_min']} -> {detail['entry_zone_max']}",
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
        "KPIs:",
        f"- proposals={payload['kpis']['total_proposals']} pending_approvals={payload['kpis']['pending_approvals']} executed={payload['kpis']['executed_proposals']} rejected={payload['kpis']['rejected_proposals']} no_trades={payload['kpis']['total_no_trade_decisions']}",
        f"- commands={payload['kpis']['operator_commands']}",
        "Risk:",
        f"- halt={payload['risk']['emergency_halt_active']} halt_reason={payload['risk'].get('halt_reason')}",
        f"- max_open={payload['risk']['max_open_risk_percent']} active={payload['risk']['active_risk_percent']} reserved={payload['risk']['reserved_pending_risk_percent']} free={payload['risk']['free_risk_budget_percent']}",
        "Universe:",
        f"- snapshot={payload['universe'].get('snapshot_id')} eligible={payload['universe']['eligible_instruments']} ineligible={payload['universe']['ineligible_instruments']} stale={payload['universe']['stale_instruments']}",
    ]
    alerts = payload.get("alerts", {}).get("items", [])
    if alerts:
        lines.append("Alerts:")
        for item in alerts[:5]:
            lines.append(f"- [{item['level']}] {item['code']}: {item['message']}")
    else:
        lines.append("Alerts: none")
    activity = payload.get("operator_activity", {}).get("recent_items", [])
    if activity:
        lines.append("Operator activity:")
        for item in activity[:5]:
            lines.append(f"- {item['actor']} | {item['outcome']} | {item['raw_command']}")
    else:
        lines.append("Operator activity: none")
    latest = payload["latest_trades"]
    if latest:
        lines.append("Latest trades:")
        for item in latest[:5]:
            lines.append(f"- {item['proposal_id']} {item['symbol']} {item['status']} conf={item['confidence_score']:.2f}")
    else:
        lines.append("Latest trades: none")
    return "\n".join(lines)


def render_demo_status_report(app) -> str:
    from cex_tbot.bot_adapter import BotCommandAdapter

    adapter = BotCommandAdapter(app.backend, config=app.config, app=app)
    return adapter.handle_demo_status().text


def render_demo_audit_report(app) -> str:
    from cex_tbot.bot_adapter import BotCommandAdapter

    adapter = BotCommandAdapter(app.backend, config=app.config, app=app)
    return adapter.handle_demo_audit().text


def load_proposal_from_json(path: Path) -> TradeProposal:
    parser = JsonTradeProposalParser(force_pending_approval=True)
    try:
        return parser.parse_text(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"Invalid proposal JSON: {exc}") from exc


def build_demo_topic_proposal(chat_id: str, thread_id: str):
    now = utc_now()
    proposal = TradeProposal(
        proposal_id="proposal_topic_demo_btc",
        agent_name="Luma",
        strategy_id="pullback",
        strategy_version="v1",
        market_context_id="ctx_topic_demo",
        symbol="BTC_USDT",
        timeframe="15m",
        direction=TradeDirection.LONG,
        entry_zone_min=66000.0,
        entry_zone_max=66100.0,
        entry_split=[EntrySplitLeg(1, 66050.0, 100.0, 1.0, now)],
        stop_loss=65750.0,
        take_profit_1=66400.0,
        take_profit_2=66750.0,
        risk_percent=0.5,
        risk_usd=5.0,
        position_size=1.0,
        confidence_score=0.78,
        thesis="Demo pullback reclaim with contained risk.",
        invalidity_condition="Local support fails and reclaim is lost.",
        liquidity_check="ok",
        data_freshness_ms=100,
        created_at=now,
        expires_at=now,
        status=ProposalStatus.PENDING_APPROVAL,
    )
    return proposal, chat_id, thread_id


def _default_post_analysis_export_path(storage_dir: Path | None, fmt: str) -> Path:
    base_dir = storage_dir or Path.cwd()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    suffix = "json" if fmt == "json" else "txt"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return reports_dir / f"post_analysis_{timestamp}.{suffix}"


def _resolve_previous_snapshot(current: Path, explicit_previous: Path | None) -> Path:
    if explicit_previous is not None:
        return explicit_previous
    candidates = sorted(path for path in current.parent.glob(current.name.split("_")[0] + "*.json") if path != current)
    if not candidates:
        raise FileNotFoundError("No previous snapshot found for diff")
    return candidates[-1]


def _diff_post_analysis_snapshots(current: dict[str, object], previous: dict[str, object]) -> dict[str, object]:
    keys = [
        "total_trades",
        "executed_trades",
        "rejected_trades",
        "pending_trades",
        "no_trade_decisions",
        "avg_confidence_all",
        "recent_trade_count",
        "recent_executed_trades",
        "recent_rejected_trades",
        "recent_avg_confidence",
    ]
    deltas = {}
    for key in keys:
        current_value = current.get(key, 0)
        previous_value = previous.get(key, 0)
        if isinstance(current_value, (int, float)) and isinstance(previous_value, (int, float)):
            deltas[key] = round(current_value - previous_value, 4)
    hint = None
    if deltas.get("executed_trades", 0) > 0 and deltas.get("rejected_trades", 0) <= 0:
        hint = "Execution count improved without additional rejections."
    elif deltas.get("rejected_trades", 0) > 0:
        hint = "Rejections increased versus previous snapshot; inspect weak cells and safety filters."
    elif deltas.get("recent_avg_confidence", 0) > 0:
        hint = "Recent confidence improved versus previous snapshot."
    else:
        hint = "No clear improvement signal versus previous snapshot yet."
    return {
        "current_path_metrics": current,
        "previous_path_metrics": previous,
        "deltas": deltas,
        "hint": hint,
    }


def _render_live_market_summary_text(payload: dict[str, object]) -> str:
    last = payload.get("last_payload") or {}
    lines = [
        "Live market pipeline run",
        (
            f"periodic={payload['periodic']} runs_completed={payload['runs_completed']} interval_sec={payload['interval_sec']} "
            f"success_runs={payload.get('success_runs', 0)} failed_runs={payload.get('failed_runs', 0)} "
            f"consecutive_failures={payload.get('consecutive_failures', 0)} max_consecutive_failures={payload.get('max_consecutive_failures', 0)}"
        ),
    ]
    if payload.get("stopped_on_failure_threshold"):
        lines.append("stopped_on_failure_threshold=true")
    if payload.get("last_error"):
        last_error = payload["last_error"]
        lines.append(
            "last_error="
            f"{last_error.get('error_type')}"
            f": {last_error.get('error_message')}"
        )
    if last:
        lines.append(f"decision={last.get('decision_kind')}")
        lines.append(f"selected_symbol={last.get('selected_symbol')}")
        lines.append(f"chat_id={last.get('chat_id')} thread_id={last.get('thread_id')}")
        refresh = last.get("refresh") or {}
        lines.append(
            f"refresh_status={refresh.get('status')} selected_symbols={refresh.get('selected_symbols')}"
        )
        if last.get("error"):
            error = last["error"]
            lines.append(
                "failure="
                f"stage={error.get('stage')} "
                f"type={error.get('error_type')} "
                f"message={error.get('error_message')}"
            )
        elif last.get("text"):
            lines.extend(["--- outbound ---", str(last.get("text", ""))])
    return "\n".join(lines)


def _render_autosync_summary_text(payload: dict[str, object]) -> str:
    lines = [
        "Gate demo autosync",
        (
            f"periodic={payload['periodic']} runs_completed={payload['runs_completed']} interval_sec={payload['interval_sec']} "
            f"success_runs={payload.get('success_runs', 0)} failed_runs={payload.get('failed_runs', 0)}"
        ),
    ]
    if payload.get("last_error"):
        last_error = payload["last_error"]
        lines.append(
            "last_error="
            f"{last_error.get('error_type')}: {last_error.get('error_message')}"
        )
    last = payload.get("last_payload") or {}
    if last:
        lines.append(
            f"scanned={last.get('scanned_proposals', 0)} synced={last.get('synced_proposals', 0)} "
            f"synced_orders={last.get('synced_orders', 0)}"
        )
        for item in last.get("items", []):
            lines.append(f"- {item['proposal_id']} orders={len(item['orders'])}")
            if item.get("telegram_alert"):
                lines.append(f"  telegram_alert -> {item['telegram_alert']['chat_id']} thread={item['telegram_alert']['thread_id']}")
        for error in last.get("errors", []):
            lines.append(f"- error {error['proposal_id']}: {error['error_type']} {error['error_message']}")
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

    if command == "sync-demo":
        payload = api.sync_demo_orders(args.proposal_id)
        if fmt == "json":
            print(_print_payload(payload, fmt))
        else:
            lines = ["Gate demo sync", f"proposal_id={payload['proposal_id']}"]
            for item in payload["orders"]:
                lines.append(f"- {item['role']} id={item['order_id']} status={item['status']} size={item['size']}")
            lines.append(f"policy_mode={payload['policy']['mode']}")
            for alert in payload["policy"]["alerts"]:
                lines.append(f"- alert: {alert}")
            print("\n".join(lines))
        return 0

    if command == "live-market-run":
        runner = LiveMarketPipelineRunner(
            app.backend,
            config=app.config,
            market_dir=args.market_dir,
            chat_id=args.chat_id,
            thread_id=args.thread_id,
            pipeline=BinanceMarketDataPipeline(output_dir=args.market_dir, universe_limit=args.universe_limit),
        )
        periodic = PeriodicRunner(
            runner,
            interval_sec=args.interval_sec,
            continue_on_error=args.continue_on_error,
            stop_after_consecutive_failures=args.stop_after_consecutive_failures,
        )
        summary = periodic.run_periodic(runs=args.runs) if args.loop else periodic.run_single()
        payload = summary.to_payload()
        if fmt == "json":
            print(_print_payload(payload, fmt))
        else:
            print(_render_live_market_summary_text(payload))
        return 0

    if command == "autosync-demo":
        wrapper = OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7")
        producer = TopicProposalProducer(app.backend, wrapper) if args.emit_telegram_alerts else None
        poller = DemoOrderStatusPoller(
            app.backend,
            emit_telegram_alerts=args.emit_telegram_alerts,
            alert_producer=producer,
        )
        periodic = PeriodicRunner(
            poller,
            interval_sec=max(1, args.interval_sec),
            continue_on_error=True,
        )
        payload = periodic.run_periodic(runs=max(1, args.runs)).to_payload()
        if fmt == "json":
            print(_print_payload(payload, fmt))
        else:
            print(_render_autosync_summary_text(payload))
        return 0

    if command == "emit-conservative-alert":
        assessment = api.conservative_alert_payload(args.proposal_id)
        wrapper = OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7")
        producer = TopicProposalProducer(app.backend, wrapper)
        outbound = producer.emit_conservative_alert(ConservativePolicyAssessment(**assessment))
        payload = {
            "proposal_id": args.proposal_id,
            "chat_id": outbound.chat_id,
            "thread_id": outbound.thread_id,
            "text": outbound.text,
            "policy": assessment,
        }
        print(_print_payload(payload, fmt) if fmt == "json" else outbound.text)
        return 0

    if command == "tg-runner":
        from cex_tbot.bot_adapter import BotCommandAdapter
        from cex_tbot.bot_dispatcher import BotCommandDispatcher
        from cex_tbot.tg_runner import TelegramRunnerPolicy, TelegramTransportRunner
        from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge

        token = (args.token or os.environ.get("CEX_TBOT_TELEGRAM_BOT_TOKEN", "")).strip()
        if not token:
            print("Telegram token missing. Set --token or CEX_TBOT_TELEGRAM_BOT_TOKEN.")
            return 2
        operator_sender_policy = SenderPolicy(
            allowed_sender_ids=_parse_csv_set(args.allowed_sender_ids),
            allow_empty_policy=False,
        )
        json_sender_ids_raw = args.allowed_json_sender_ids
        if json_sender_ids_raw is None:
            json_sender_ids_raw = os.environ.get("CEX_TBOT_JSON_SUBMITTER_IDS") or os.environ.get("CEX_TBOT_TELEGRAM_JSON_SENDER_IDS")
        json_sender_policy = SenderPolicy(
            allowed_sender_ids=_parse_csv_set(json_sender_ids_raw) if json_sender_ids_raw is not None else operator_sender_policy.allowed_sender_ids,
            allow_empty_policy=False,
        )
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app)),
            sender_policy=operator_sender_policy,
            write_sender_policy=operator_sender_policy,
            audit_transcript=app.backend.session.operator_transcript,
        )
        proposal_parser = JsonTradeProposalParser(force_pending_approval=True)

        def _submit_proposal_to_topic(proposal: TradeProposal, chat_id: str, thread_id: str | None) -> str:
            wrapper = OpenClawTopicWrapper(None, default_chat_id=chat_id, default_thread_id=thread_id)
            producer = TopicProposalProducer(app.backend, wrapper)
            return producer.submit_and_emit(proposal).text

        runner = TelegramTransportRunner(
            bridge,
            bot_token=token,
            policy=TelegramRunnerPolicy(
                allowed_chat_ids=_parse_csv_set(args.allowed_chat_ids),
                allowed_thread_ids=_parse_csv_set(args.allowed_thread_ids),
            ),
            proposal_parser=proposal_parser.parse_text,
            proposal_submitter=_submit_proposal_to_topic,
            json_sender_policy=json_sender_policy,
            state_sync=getattr(app.session, "refresh_from_disk", None),
        )
        runner.run_polling()
        return 0

    if command == "dashboard":
        payload = api.dashboard()
        print(_print_payload(payload, fmt) if fmt == "json" else render_dashboard_text(payload))
        return 0

    if command == "post-analysis":
        payload = api.post_analysis()
        print(_print_payload(payload, fmt) if fmt == "json" else app.backend.get_post_analysis_text())
        return 0

    if command == "post-analysis-export":
        payload = api.post_analysis()
        output_path = args.out or _default_post_analysis_export_path(storage_dir, fmt)
        rendered = _print_payload(payload, fmt) if fmt == "json" else app.backend.get_post_analysis_text()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
        print(_print_payload({"status": "ok", "path": str(output_path), "format": fmt}, fmt))
        return 0

    if command == "post-analysis-diff":
        current_path = args.current
        previous_path = _resolve_previous_snapshot(current_path, args.previous)
        current_payload = json.loads(current_path.read_text(encoding="utf-8"))
        previous_payload = json.loads(previous_path.read_text(encoding="utf-8"))
        diff_payload = _diff_post_analysis_snapshots(current_payload, previous_payload)
        print(_print_payload(diff_payload, fmt))
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

    if command == "clear-safety":
        app.backend.clear_safety_controls()
        payload = app.backend.get_session_summary_payload()
        print(_print_payload(payload, fmt))
        return 0

    if command == "demo-status-report":
        rendered = render_demo_status_report(app)
        print(_print_payload({"report": rendered}, fmt) if fmt == "json" else rendered)
        return 0

    if command == "demo-audit-report":
        rendered = render_demo_audit_report(app)
        print(_print_payload({"report": rendered}, fmt) if fmt == "json" else rendered)
        return 0

    if command in {"emit-demo-proposal", "submit-and-emit-demo", "submit-and-emit"}:
        if command == "submit-and-emit" and getattr(args, "print_contract", False):
            print(proposal_contract_text())
            return 0
        if command == "submit-and-emit":
            if args.proposal_file is None:
                print("Usage: submit-and-emit <proposal_file.json> [--print-contract]")
                return 2
            try:
                proposal = load_proposal_from_json(args.proposal_file)
            except ValueError as exc:
                print(str(exc))
                return 2
            chat_id = args.chat_id
            thread_id = args.thread_id
        else:
            proposal, chat_id, thread_id = build_demo_topic_proposal(args.chat_id, args.thread_id)
        wrapper = OpenClawTopicWrapper(api.bridge if hasattr(api, 'bridge') else None, default_chat_id=chat_id, default_thread_id=thread_id)
        producer = TopicProposalProducer(app.backend, wrapper)
        outbound = producer.submit_and_emit(proposal)
        payload = {
            "proposal_id": proposal.proposal_id,
            "chat_id": outbound.chat_id,
            "thread_id": outbound.thread_id,
            "text": outbound.text,
        }
        print(_print_payload(payload, fmt) if fmt == "json" else outbound.text)
        return 0

    if command == "serve-rest":
        try:
            bundle = create_rest_app(storage_dir=storage_dir)
        except RestApiDependencyError as exc:
            print(str(exc))
            return 2
        try:
            import uvicorn
        except ModuleNotFoundError:
            print("uvicorn is not installed. Install optional REST dependencies to serve the FastAPI app.")
            return 2
        uvicorn.run(bundle.app, host=args.host, port=args.port)
        return 0

    print(render_status(storage_dir=storage_dir, fmt=fmt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
