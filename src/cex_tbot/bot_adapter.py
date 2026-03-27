from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bootstrap import TradingApplication
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.exceptions import GateDemoTransportError, MissingGateDemoCredentialsError
from cex_tbot.query_params import TradeQuery
from cex_tbot.risk_engine import PortfolioState
from cex_tbot.shared import utc_now


@dataclass(frozen=True)
class BotReply:
    text: str
    parse_mode: str | None = None


class BotCommandAdapter:
    def __init__(self, backend: TradingBackendService, *, config: BotConfig | None = None, app: TradingApplication | None = None) -> None:
        self.backend = backend
        self.config = config or BotConfig()
        self.app = app

    def handle_help(self) -> BotReply:
        return BotReply(
            "\n".join(
                [
                    "cex_tbot bot commands",
                    "/help — show this help",
                    "/status — session summary",
                    "/dashboard — dashboard snapshot",
                    "/post_analysis — post-analysis and calibration snapshot",
                    "/safety — current safety state",
                    "/gate_demo_status — Gate demo transport status",
                    "/demo_health — Gate demo metadata endpoint health",
                    "/demo_account_status — Gate demo account status snapshot",
                    "/demo_balance — Gate demo balance snapshot",
                    "/demo_positions — Gate demo positions snapshot",
                    "/demo_open_orders — Gate demo open orders",
                    "/demo_order_status <order_id> — Gate demo order status",
                    "/demo_place_test_order <contract> <buy|sell> — explicit tiny demo test order",
                    "/demo_cancel_order <order_id> — cancel demo order",
                    "/demo_account_overview — Gate demo account + positions overview",
                    "/demo_capabilities — Gate demo runtime capabilities",
                    "/runtime_status — runtime/storage/fetcher status",
                    "/session_paths — session storage paths",
                    "/refresh_universe — refresh whitelist/universe snapshot",
                    "/list — latest trades",
                    "/detail <proposal_id> — trade detail",
                    "/report <proposal_id> — telegram-ready trade report",
                    "/approve <proposal_id> — approve and execute",
                    "/approve_only <proposal_id> — approve without execution",
                    "/execute <proposal_id> — execute approved proposal",
                    "/halt <reason> — activate emergency halt",
                    "/unhalt — clear emergency halt",
                    "/clear_safety — clear warning/block safety state",
                    "/no_trades — list no-trade decisions",
                ]
            )
        )

    def handle_status(self) -> BotReply:
        return BotReply(self.backend.get_session_summary().to_text())

    def handle_dashboard(self) -> BotReply:
        payload = self.backend.get_dashboard_payload()
        latest = payload["latest_trades"]
        lines = [
            "Dashboard",
            f"- proposals={payload['kpis']['total_proposals']} no_trades={payload['kpis']['total_no_trade_decisions']} executed={payload['kpis']['executed_proposals']}",
            f"- rejected={payload['kpis']['rejected_proposals']} commands={payload['kpis']['operator_commands']} halt={payload['risk']['emergency_halt_active']}",
            f"- safety={payload['risk']['safety_state']} blocked={payload['risk']['block_new_trades']}",
        ]
        if latest:
            lines.append("Latest trades:")
            for item in latest[:5]:
                lines.append(f"- {item['proposal_id']} {item['symbol']} {item['status']} conf={item['confidence_score']:.2f}")
        else:
            lines.append("Latest trades: none")
        return BotReply("\n".join(lines))

    def handle_post_analysis(self) -> BotReply:
        return BotReply(self.backend.get_post_analysis_text())

    def handle_safety(self) -> BotReply:
        payload = self.backend.get_session_summary_payload()
        lines = [
            "Safety status",
            f"- state={payload['safety_state']} halt={payload['emergency_halt_active']} blocked={payload['block_new_trades']}",
        ]
        if payload.get('halt_reason'):
            lines.append(f"- halt_reason={payload['halt_reason']}")
        if payload.get('block_reason'):
            lines.append(f"- block_reason={payload['block_reason']}")
        return BotReply("\n".join(lines))

    def handle_gate_demo_status(self) -> BotReply:
        lines = [
            "Gate demo transport status",
            f"- execution_mode={self.config.execution_mode}",
            f"- gate_demo_api_configured={bool(self.config.gate_demo_api)}",
        ]
        if self.config.execution_mode != "gate_demo":
            lines.append("- transport=inactive (runtime not in gate_demo mode)")
        else:
            lines.append(f"- transport=demo boundary enabled via {type(self.app.instrument_fetcher).__name__ if self.app is not None else 'unknown fetcher'}")
        return BotReply("\n".join(lines))

    def handle_demo_health(self) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Gate demo health unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            payload = client.healthcheck()
        except (NotImplementedError, GateDemoTransportError) as exc:
            return BotReply(f"Gate demo health unavailable: {exc}")
        return BotReply(
            "\n".join(
                [
                    "Gate demo health",
                    f"- ok={payload.get('ok')}",
                    f"- endpoint={payload.get('endpoint')}",
                    f"- contracts_seen={payload.get('contracts_seen')}",
                ]
            )
        )

    def handle_demo_account_status(self) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Gate demo account status unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            payload = client.account_status()
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Gate demo account status unavailable: {exc}")
        return BotReply(
            "\n".join(
                [
                    "Gate demo account status",
                    f"- ok={payload.get('ok')}",
                    f"- endpoint={payload.get('endpoint')}",
                    f"- currency={payload.get('currency')}",
                    f"- available={payload.get('available')}",
                    f"- total={payload.get('total')}",
                ]
            )
        )

    def handle_demo_balance(self) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Gate demo balance unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            payload = client.balance_snapshot()
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Gate demo balance unavailable: {exc}")
        return BotReply(
            "\n".join(
                [
                    "Gate demo balance",
                    f"- currency={payload.get('currency')}",
                    f"- available={payload.get('available')}",
                    f"- total={payload.get('total')}",
                ]
            )
        )

    def handle_demo_positions(self) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Gate demo positions unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            positions = client.positions_snapshot()
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Gate demo positions unavailable: {exc}")
        if not positions:
            return BotReply("Gate demo positions\n- none")
        lines = ["Gate demo positions"]
        for item in positions[:10]:
            lines.append(
                f"- {item.get('contract')} size={item.get('size')} entry={item.get('entry_price')} mark={item.get('mark_price')} upnl={item.get('unrealised_pnl')}"
            )
        return BotReply("\n".join(lines))

    def handle_demo_open_orders(self) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Gate demo open orders unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            orders = client.open_orders()
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Gate demo open orders unavailable: {exc}")
        if not orders:
            return BotReply("Gate demo open orders\n- none")
        lines = ["Gate demo open orders"]
        for item in orders[:10]:
            lines.append(
                f"- {item.get('id')} {item.get('contract')} size={item.get('size')} price={item.get('price')} status={item.get('status')}"
            )
        return BotReply("\n".join(lines))

    def handle_demo_order_status(self, order_id: str) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Gate demo order status unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            item = client.order_status(order_id)
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Gate demo order status unavailable: {exc}")
        return BotReply(
            "\n".join(
                [
                    "Gate demo order status",
                    f"- id={item.get('id')}",
                    f"- contract={item.get('contract')}",
                    f"- size={item.get('size')}",
                    f"- price={item.get('price')}",
                    f"- status={item.get('status')}",
                    f"- left={item.get('left')}",
                    f"- fill_price={item.get('fill_price')}",
                ]
            )
        )

    def handle_demo_place_test_order(self, contract: str, side: str) -> BotReply:
        if self.config.execution_mode != "gate_demo":
            return BotReply("Demo test order rejected: runtime is not in gate_demo mode.")
        if side.lower() not in {"buy", "sell"}:
            return BotReply("Demo test order rejected: side must be buy or sell.")
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Demo test order unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            payload = client.place_test_order(contract, size=self.config.gate_demo_test_order_size, side=side.lower())
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Demo test order unavailable: {exc}")
        return BotReply(
            "\n".join(
                [
                    "Gate demo test order",
                    f"- id={payload.get('id')}",
                    f"- contract={payload.get('contract')}",
                    f"- side={payload.get('side')}",
                    f"- size={payload.get('size')}",
                    f"- status={payload.get('status')}",
                ]
            )
        )

    def handle_demo_cancel_order(self, order_id: str) -> BotReply:
        if self.app is None or not hasattr(self.app.instrument_fetcher, "client"):
            return BotReply("Demo cancel order unavailable: no demo client bound.")
        client = self.app.instrument_fetcher.client
        try:
            payload = client.cancel_order(order_id)
        except (NotImplementedError, GateDemoTransportError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Demo cancel order unavailable: {exc}")
        return BotReply(
            "\n".join(
                [
                    "Gate demo cancel order",
                    f"- id={payload.get('id')}",
                    f"- status={payload.get('status')}",
                ]
            )
        )

    def handle_demo_account_overview(self) -> BotReply:
        account = self.handle_demo_account_status().text
        positions = self.handle_demo_positions().text
        orders = self.handle_demo_open_orders().text
        return BotReply(account + "\n\n" + positions + "\n\n" + orders)

    def handle_demo_capabilities(self) -> BotReply:
        lines = [
            "Gate demo capabilities",
            f"- execution_mode={self.config.execution_mode}",
            f"- metadata_fetch={'yes' if self.config.execution_mode == 'gate_demo' else 'available via static/local fetchers only'}",
            f"- account_status={'yes' if bool(self.config.gate_demo_key and self.config.gate_demo_secret) else 'credentials_missing'}",
            f"- balance_snapshot={'yes' if bool(self.config.gate_demo_key and self.config.gate_demo_secret) else 'credentials_missing'}",
            f"- positions_snapshot={'yes' if bool(self.config.gate_demo_key and self.config.gate_demo_secret) else 'credentials_missing'}",
            "- live_trading=no",
            "- order_placement=no",
            "- account_sync=read_only_boundary",
        ]
        return BotReply("\n".join(lines))

    def handle_runtime_status(self) -> BotReply:
        lines = [
            "Runtime status",
            f"- execution_mode={self.config.execution_mode}",
            f"- fetcher={type(self.app.instrument_fetcher).__name__ if self.app is not None else 'unknown'}",
            f"- storage_dir={self.app.storage_dir if self.app is not None else None}",
        ]
        return BotReply("\n".join(lines))

    def handle_session_paths(self) -> BotReply:
        return BotReply(f"Session paths\n- storage_dir={self.app.storage_dir if self.app is not None else None}")

    def handle_refresh_universe(self) -> BotReply:
        if self.app is None:
            return BotReply("Universe refresh unavailable: adapter has no application context.")
        snapshot_id = f"operator_refresh_{utc_now().strftime('%Y%m%dT%H%M%SZ')}"
        try:
            result = self.app.universe_orchestrator.refresh_from_fetcher(
                self.app.instrument_fetcher,
                snapshot_id=snapshot_id,
                refresh_reason="operator_refresh",
            )
        except (NotImplementedError, GateDemoTransportError) as exc:
            return BotReply(f"Universe refresh unavailable: {exc}")
        lines = [
            "Universe refresh complete",
            f"- snapshot_id={result.snapshot_id}",
            f"- eligible={result.eligible_count}",
            f"- rejected={result.rejected_count}",
            f"- whitelist={', '.join(result.top_whitelist_symbols) if result.top_whitelist_symbols else 'none'}",
        ]
        return BotReply("\n".join(lines))

    def handle_submit_proposal(self, proposal: TradeProposal) -> BotReply:
        payload = self.backend.submit_proposal(proposal)
        return BotReply(f"Proposal stored: {payload.proposal_id} [{payload.status.value}]")

    def handle_submit_no_trade(self, decision: NoTradeDecision) -> BotReply:
        saved = self.backend.submit_no_trade_decision(decision)
        return BotReply(f"No-trade stored: {saved.symbol} {saved.reason_code.value}")

    def handle_list(self, *, limit: int = 5) -> BotReply:
        trades = self.backend.list_trades_payload(TradeQuery(limit=limit))
        if not trades:
            return BotReply("No trades stored.")
        lines = ["Latest trades:"]
        for item in trades:
            lines.append(f"- {item['proposal_id']} | {item['symbol']} {item['direction']} | {item['status']}")
        return BotReply("\n".join(lines))

    def handle_detail(self, proposal_id: str) -> BotReply:
        detail = self.backend.get_trade_detail_payload(proposal_id)
        lines = [
            f"Trade detail — {detail['proposal_id']}",
            f"Status: {detail['status']}",
            f"Symbol: {detail['symbol']} {detail['direction']} {detail['timeframe']}",
            f"Confidence: {detail['confidence_score']:.2f}",
            f"Entry zone: {detail['entry_zone_min']} → {detail['entry_zone_max']}",
            f"Stop: {detail['stop_loss']} | TP1: {detail['take_profit_1']} | TP2: {detail['take_profit_2']}",
            f"Thesis: {detail['thesis']}",
        ]
        return BotReply("\n".join(lines))

    def handle_report(self, proposal_id: str) -> BotReply:
        return BotReply(self.backend.get_trade_report_text(proposal_id, render_mode="telegram"), parse_mode="Markdown")

    def handle_approve(self, proposal_id: str, *, actor: str = "Mike", portfolio_equity: float = 10_000.0, execute_on_approve: bool = True) -> BotReply:
        response = self.backend.run_operator_command_payload(
            actor,
            f"APPROVE {proposal_id}",
            portfolio=self._portfolio(portfolio_equity),
            execute_on_approve=execute_on_approve,
            render_mode="telegram",
        )
        return BotReply(response["text"], parse_mode="Markdown")

    def handle_execute(self, proposal_id: str, *, actor: str = "Mike", portfolio_equity: float = 10_000.0) -> BotReply:
        response = self.backend.execute_approved_proposal_payload(
            proposal_id,
            self._portfolio(portfolio_equity),
            actor=actor,
            render_mode="telegram",
        )
        return BotReply(response["text"], parse_mode="Markdown")

    def handle_halt(self, reason: str) -> BotReply:
        self.backend.activate_emergency_halt(reason)
        return BotReply(f"Emergency halt activated: {reason}")

    def handle_unhalt(self) -> BotReply:
        self.backend.clear_emergency_halt()
        return BotReply("Emergency halt cleared")

    def handle_clear_safety(self) -> BotReply:
        self.backend.clear_safety_controls()
        payload = self.backend.get_session_summary_payload()
        return BotReply(f"Safety cleared: state={payload['safety_state']} blocked={payload['block_new_trades']}")

    def handle_no_trades(self) -> BotReply:
        decisions = self.backend.list_no_trades_payload()
        if not decisions:
            return BotReply("No no-trade decisions stored.")
        lines = ["No-trade decisions:"]
        for item in decisions[-5:]:
            lines.append(f"- {item['symbol']} | {item['reason_code']} | conf={item['confidence_score']:.2f}")
        return BotReply("\n".join(lines))

    @staticmethod
    def _portfolio(equity: float) -> PortfolioState:
        return PortfolioState(equity=equity)
