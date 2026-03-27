from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import NoTradeDecision, TradeProposal
from cex_tbot.query_params import TradeQuery
from cex_tbot.risk_engine import PortfolioState


@dataclass(frozen=True)
class BotReply:
    text: str
    parse_mode: str | None = None


class BotCommandAdapter:
    def __init__(self, backend: TradingBackendService, *, config: BotConfig | None = None) -> None:
        self.backend = backend
        self.config = config or BotConfig()

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
            lines.append("- transport=demo boundary enabled")
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
