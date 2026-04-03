from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from cex_tbot.audit import AuditEntry
from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bootstrap import TradingApplication
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.exceptions import GateDemoTransportError, MissingGateDemoCredentialsError
from cex_tbot.query_params import TradeQuery
from cex_tbot.enums import ProposalStatus
from cex_tbot.risk_engine import PortfolioState
from cex_tbot.shared import utc_now


@dataclass(frozen=True)
class BotReply:
    text: str
    parse_mode: str | None = None


class BotCommandAdapter:
    def __init__(self, backend: TradingBackendService, *, config: BotConfig | None = None, app: TradingApplication | None = None, write_arm_state=None) -> None:
        self.backend = backend
        self.config = config or BotConfig()
        self.app = app
        self.write_arm_state = write_arm_state

    def handle_help(self) -> BotReply:
        return BotReply(
            "\n".join(
                [
                    "cex_tbot bot commands",
                    "/help - show this help",
                    "/status - session summary",
                    "/dashboard - dashboard snapshot",
                    "/post_analysis - post-analysis and calibration snapshot",
                    "/safety - current safety state",
                    "/gate_demo_status - Gate demo transport status",
                    "/demo_health - Gate demo metadata endpoint health",
                    "/demo_account_status - Gate demo account status snapshot",
                    "/demo_balance - Gate demo balance snapshot",
                    "/demo_positions - Gate demo positions snapshot",
                    "/demo_open_orders - Gate demo open orders",
                    "/demo_order_status <order_id> - Gate demo order status",
                    "/demo_sync <proposal_id> - sync stored Gate demo order states for a proposal",
                    "/demo_arm - arm demo write actions for a short window",
                    "/demo_disarm - clear demo write arm immediately",
                    "/demo_status - consolidated demo operator status",
                    "/demo_write_status - current write-arm status",
                    "/demo_audit - recent demo write audit entries",
                    "/demo_place_test_order <contract> <buy|sell> - explicit tiny demo test order",
                    "/demo_cancel_order <order_id> - cancel demo order",
                    "/demo_smoke <contract> <buy|sell> - place/status/cancel-if-open demo smoke",
                    "/demo_account_overview - Gate demo account + positions overview",
                    "/demo_capabilities - Gate demo runtime capabilities",
                    "/runtime_status - runtime/storage/fetcher status",
                    "/session_paths - session storage paths",
                    "/refresh_universe - refresh whitelist/universe snapshot",
                    "/list - latest trades",
                    "/detail <proposal_id> - trade detail",
                    "/trade_report <proposal_id> - telegram-ready trade report",
                    "/trade_approve <proposal_id> - approve and execute",
                    "/trade_approve_only <proposal_id> - approve without execution",
                    "/trade_modify <proposal_id> key=value[, key=value] - modify + revalidate",
                    "/modify <proposal_id> key=value[, key=value] - same as /trade_modify for topic workflows",
                    "/trade_execute <proposal_id> - execute approved proposal",
                    "/halt <reason> - activate emergency halt",
                    "/unhalt - clear emergency halt",
                    "/clear_safety - clear warning/block safety state",
                    "/no_trades - list no-trade decisions",
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

    def handle_demo_status(self) -> BotReply:
        chunks = [
            self.handle_demo_capabilities().text,
            self.handle_demo_write_status().text,
            self.handle_demo_account_overview().text,
        ]
        return BotReply("\n\n".join(chunks))

    def handle_demo_write_status(self) -> BotReply:
        if self.write_arm_state is None:
            return BotReply("Demo write status\n- arm_state=unbound")
        payload = self.write_arm_state.status()
        return BotReply(
            "\n".join(
                [
                    "Demo write status",
                    f"- is_active={payload['is_active']}",
                    f"- armed_sender_id={payload['armed_sender_id']}",
                    f"- armed_until={payload['armed_until']}",
                ]
            )
        )

    def handle_demo_audit(self) -> BotReply:
        entries = [
            entry for entry in self.backend.session.operator_transcript.list_entries()
            if entry.outcome.startswith("DEMO_") or entry.raw_command.startswith("DEMO_")
        ]
        if not entries:
            return BotReply("Demo audit\n- no demo write activity yet")
        lines = ["Demo audit"]
        for entry in entries[-10:]:
            lines.append(
                f"- {entry.created_at.isoformat()} {entry.outcome} cmd={entry.raw_command} ref={entry.proposal_id}"
            )
        return BotReply("\n".join(lines))

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
        self.backend.session.operator_transcript.append(
            AuditEntry(actor="operator", raw_command=f"DEMO_PLACE_TEST_ORDER {contract} {side.lower()}", outcome="DEMO_ORDER_PLACED", proposal_id=str(payload.get('id') or ''))
        )
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
        except (NotImplementedError, MissingGateDemoCredentialsError) as exc:
            return BotReply(f"Demo cancel order unavailable: {exc}")
        except GateDemoTransportError as exc:
            if "ORDER_NOT_FOUND" in str(exc):
                try:
                    status = client.order_status(order_id)
                except Exception:
                    return BotReply(f"Demo cancel order unavailable: {exc}")
                if str(status.get("status", "")).lower() in {"finished", "closed", "cancelled"} or str(status.get("left", "")) == "0":
                    self.backend.session.operator_transcript.append(
                        AuditEntry(actor="operator", raw_command=f"DEMO_CANCEL_ORDER {order_id}", outcome="DEMO_ORDER_ALREADY_FINAL", proposal_id=order_id)
                    )
                    return BotReply(f"Gate demo cancel order\n- id={order_id}\n- status=already_finalized")
            return BotReply(f"Demo cancel order unavailable: {exc}")
        self.backend.session.operator_transcript.append(
            AuditEntry(actor="operator", raw_command=f"DEMO_CANCEL_ORDER {order_id}", outcome="DEMO_ORDER_CANCELLED", proposal_id=order_id)
        )
        return BotReply(
            "\n".join(
                [
                    "Gate demo cancel order",
                    f"- id={payload.get('id')}",
                    f"- status={payload.get('status')}",
                ]
            )
        )

    def handle_demo_smoke(self, contract: str, side: str) -> BotReply:
        placed = self.handle_demo_place_test_order(contract, side).text
        order_id = None
        for line in placed.splitlines():
            if line.startswith("- id="):
                order_id = line.split("=", 1)[1].strip()
                break
        chunks = [placed]
        if order_id:
            chunks.append(self.handle_demo_order_status(order_id).text)
            chunks.append(self.handle_demo_cancel_order(order_id).text)
        return BotReply("\n\n".join(chunks))

    def handle_demo_sync(self, proposal_id: str) -> BotReply:
        records = self.backend.sync_demo_orders(proposal_id)
        if not records:
            return BotReply(f"Gate demo sync\n- proposal_id={proposal_id}\n- demo_orders=none")
        lines = ["Gate demo sync", f"- proposal_id={proposal_id}"]
        for item in records:
            lines.append(f"- {item.role}: id={item.order_id} status={item.status} size={item.size} trigger={item.trigger_price}")
        policy = self.backend.get_demo_policy_assessment_payload(proposal_id)
        lines.append(f"- policy_mode={policy['mode']}")
        for alert in policy["alerts"]:
            lines.append(f"- alert: {alert}")
        return BotReply("\n".join(lines))

    def handle_demo_account_overview(self) -> BotReply:
        account = self.handle_demo_account_status().text
        positions = self.handle_demo_positions().text
        orders = self.handle_demo_open_orders().text
        return BotReply(account + "\n\n" + positions + "\n\n" + orders)

    def handle_demo_capabilities(self) -> BotReply:
        gate_demo_exec_enabled = bool(
            self.config.execution_mode == "gate_demo"
            and self.app is not None
            and getattr(self.app.execution, "gate_demo_executor", None) is not None
        )
        lines = [
            "Gate demo capabilities",
            f"- execution_mode={self.config.execution_mode}",
            f"- metadata_fetch={'yes' if self.config.execution_mode == 'gate_demo' else 'available via static/local fetchers only'}",
            f"- account_status={'yes' if bool(self.config.gate_demo_key and self.config.gate_demo_secret) else 'credentials_missing'}",
            f"- balance_snapshot={'yes' if bool(self.config.gate_demo_key and self.config.gate_demo_secret) else 'credentials_missing'}",
            f"- positions_snapshot={'yes' if bool(self.config.gate_demo_key and self.config.gate_demo_secret) else 'credentials_missing'}",
            f"- live_trading={'demo_only' if gate_demo_exec_enabled else 'no'}",
            f"- order_placement={'entry+trigger_brackets' if gate_demo_exec_enabled else 'no'}",
            f"- account_sync={'demo_executor_attached' if gate_demo_exec_enabled else 'read_only_boundary'}",
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

    def handle_pending(self, *, limit: int = 10) -> BotReply:
        trades = self.backend.list_trades_payload(TradeQuery(limit=limit))
        pending = [item for item in trades if item["status"] == ProposalStatus.PENDING_APPROVAL.value]
        if not pending:
            return BotReply("Pending proposals: none")
        now = utc_now()
        lines = ["Pending proposals:"]
        for item in pending:
            detail = self.backend.get_trade_detail_payload(str(item["proposal_id"]))
            expires_at = datetime.fromisoformat(str(detail["expires_at"]))
            created_at = datetime.fromisoformat(str(detail["created_at"]))
            minutes_left = int((expires_at - now).total_seconds() // 60)
            age_min = int((now - created_at).total_seconds() // 60)
            stale_flag = " | EXPIRED" if minutes_left < 0 else (" | stale-soon" if minutes_left <= 5 else "")
            lines.append(
                f"- {item['proposal_id']} | {item['symbol']} {item['direction']} {item['timeframe']} | conf={item['confidence_score']:.2f} | age={age_min}m | ttl={minutes_left}m{stale_flag}"
            )
        return BotReply("\n".join(lines))

    def handle_expired(self, *, limit: int = 10) -> BotReply:
        trades = self.backend.list_trades_payload(TradeQuery(limit=limit))
        now = utc_now()
        expired = []
        for item in trades:
            if item["status"] != ProposalStatus.PENDING_APPROVAL.value:
                continue
            detail = self.backend.get_trade_detail_payload(str(item["proposal_id"]))
            expires_at = datetime.fromisoformat(str(detail["expires_at"]))
            if expires_at < now:
                expired.append((item, detail, expires_at))
        if not expired:
            return BotReply("Expired proposals: none")
        lines = ["Expired proposals:"]
        for item, detail, expires_at in expired:
            created_at = datetime.fromisoformat(str(detail["created_at"]))
            age_min = int((now - created_at).total_seconds() // 60)
            expired_min = int((now - expires_at).total_seconds() // 60)
            lines.append(
                f"- {item['proposal_id']} | {item['symbol']} {item['direction']} {item['timeframe']} | age={age_min}m | expired={expired_min}m"
            )
        return BotReply("\n".join(lines))

    def handle_detail(self, proposal_id: str) -> BotReply:
        detail = self.backend.get_trade_detail_payload(proposal_id)
        lines = [
            f"Trade detail - {detail['proposal_id']}",
            f"Status: {detail['status']}",
            f"Symbol: {detail['symbol']} {detail['direction']} {detail['timeframe']}",
            f"Confidence: {detail['confidence_score']:.2f}",
            f"Entry zone: {detail['entry_zone_min']} -> {detail['entry_zone_max']}",
            f"Stop: {detail['stop_loss']} | TP1: {detail['take_profit_1']} | TP2: {detail['take_profit_2']}",
            f"Thesis: {detail['thesis']}",
        ]
        return BotReply("\n".join(lines))

    def handle_report(self, proposal_id: str) -> BotReply:
        report = self.backend.get_trade_report_text(proposal_id, render_mode="telegram")
        return BotReply(f"Report for {proposal_id}\n\n{report}", parse_mode="Markdown")

    def handle_approve(self, proposal_id: str, *, actor: str = "Mike", portfolio_equity: float = 10_000.0, execute_on_approve: bool = True) -> BotReply:
        response = self.backend.run_operator_command_payload(
            actor,
            f"APPROVE {proposal_id}",
            portfolio=self._portfolio(portfolio_equity),
            execute_on_approve=execute_on_approve,
            render_mode="telegram",
        )
        return BotReply(f"Approval processed for {proposal_id}\n\n{response['text']}", parse_mode="Markdown")

    def handle_reject(self, proposal_id: str, *, actor: str = "Mike", portfolio_equity: float = 10_000.0) -> BotReply:
        response = self.backend.run_operator_command_payload(
            actor,
            f"REJECT {proposal_id}",
            portfolio=self._portfolio(portfolio_equity),
            execute_on_approve=False,
            render_mode="telegram",
        )
        return BotReply(f"Reject processed for {proposal_id}\n\n{response['text']}", parse_mode="Markdown")

    def handle_modify(self, proposal_id: str, changes_text: str, *, actor: str = "Mike") -> BotReply:
        proposal = self.backend.approval_flow.store.require(proposal_id)
        updates = self._parse_modify_changes(changes_text)
        replacement = replace(
            proposal,
            stop_loss=updates.get("stop_loss", proposal.stop_loss),
            take_profit_1=updates.get("take_profit_1", proposal.take_profit_1),
            take_profit_2=updates.get("take_profit_2", proposal.take_profit_2),
            thesis=updates.get("thesis", proposal.thesis),
            status=ProposalStatus.PENDING_APPROVAL,
            proposal_id=f"{proposal.proposal_id}_v{proposal.proposal_version + 1}",
        )
        response = self.backend.run_operator_command_payload(
            actor,
            f"MODIFY {proposal_id}: {changes_text}",
            portfolio=self._portfolio(10_000.0),
            execute_on_approve=False,
            render_mode="telegram",
            replacement=replacement,
        )
        return BotReply(f"Modify processed for {proposal_id}\n\n{response['text']}", parse_mode="Markdown")

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
    def _parse_modify_changes(changes_text: str) -> dict[str, float | str]:
        updates: dict[str, float | str] = {}
        for chunk in changes_text.split(","):
            item = chunk.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"stop_loss", "take_profit_1", "take_profit_2"}:
                updates[key] = float(value)
            elif key == "thesis":
                updates[key] = value
        return updates

    @staticmethod
    def _portfolio(equity: float) -> PortfolioState:
        return PortfolioState(equity=equity)
