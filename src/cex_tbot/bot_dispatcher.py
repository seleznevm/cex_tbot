from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cex_tbot.bot_adapter import BotCommandAdapter, BotReply
from cex_tbot.decision_contracts import NoTradeDecision
from cex_tbot.demo import FIXED_DEMO_NOW, build_demo_proposal
from cex_tbot.enums import NoTradeReasonCode


@dataclass(frozen=True)
class ParsedBotCommand:
    name: str
    args: list[str]


class BotCommandDispatcher:
    def __init__(self, adapter: BotCommandAdapter) -> None:
        self.adapter = adapter

    def dispatch(self, text: str) -> BotReply:
        parsed = self.parse(text)
        if parsed is None:
            return BotReply("Unknown command. Use /help")

        if parsed.name == "help":
            return self.adapter.handle_help()
        if parsed.name == "status":
            return self.adapter.handle_status()
        if parsed.name == "dashboard":
            return self.adapter.handle_dashboard()
        if parsed.name == "post_analysis":
            return self.adapter.handle_post_analysis()
        if parsed.name == "demo_status":
            return self.adapter.handle_demo_status()
        if parsed.name == "demo_write_status":
            return self.adapter.handle_demo_write_status()
        if parsed.name == "demo_audit":
            return self.adapter.handle_demo_audit()
        if parsed.name == "safety":
            return self.adapter.handle_safety()
        if parsed.name == "gate_demo_status":
            return self.adapter.handle_gate_demo_status()
        if parsed.name == "demo_health":
            return self.adapter.handle_demo_health()
        if parsed.name == "demo_account_status":
            return self.adapter.handle_demo_account_status()
        if parsed.name == "demo_balance":
            return self.adapter.handle_demo_balance()
        if parsed.name == "demo_positions":
            return self.adapter.handle_demo_positions()
        if parsed.name == "demo_open_orders":
            return self.adapter.handle_demo_open_orders()
        if parsed.name == "demo_order_status":
            if not parsed.args:
                return BotReply("Usage: /demo_order_status <order_id>")
            return self.adapter.handle_demo_order_status(parsed.args[0])
        if parsed.name == "demo_place_test_order":
            if len(parsed.args) < 2:
                return BotReply("Usage: /demo_place_test_order <contract> <buy|sell>")
            return self.adapter.handle_demo_place_test_order(parsed.args[0], parsed.args[1])
        if parsed.name == "demo_cancel_order":
            if not parsed.args:
                return BotReply("Usage: /demo_cancel_order <order_id>")
            return self.adapter.handle_demo_cancel_order(parsed.args[0])
        if parsed.name == "demo_smoke":
            if len(parsed.args) < 2:
                return BotReply("Usage: /demo_smoke <contract> <buy|sell>")
            return self.adapter.handle_demo_smoke(parsed.args[0], parsed.args[1])
        if parsed.name == "demo_account_overview":
            return self.adapter.handle_demo_account_overview()
        if parsed.name == "demo_capabilities":
            return self.adapter.handle_demo_capabilities()
        if parsed.name == "runtime_status":
            return self.adapter.handle_runtime_status()
        if parsed.name == "session_paths":
            return self.adapter.handle_session_paths()
        if parsed.name == "refresh_universe":
            return self.adapter.handle_refresh_universe()
        if parsed.name == "list":
            limit = self._parse_limit(parsed.args)
            return self.adapter.handle_list(limit=limit)
        if parsed.name == "pending":
            limit = self._parse_limit(parsed.args) if parsed.args else 10
            return self.adapter.handle_pending(limit=limit)
        if parsed.name == "expired":
            limit = self._parse_limit(parsed.args) if parsed.args else 10
            return self.adapter.handle_expired(limit=limit)
        if parsed.name == "detail":
            if not parsed.args:
                return BotReply("Usage: /detail <proposal_id>")
            return self.adapter.handle_detail(parsed.args[0])
        if parsed.name == "report":
            if not parsed.args:
                return BotReply("Usage: /report <proposal_id>")
            return self.adapter.handle_report(parsed.args[0])
        if parsed.name == "approve":
            if not parsed.args:
                return BotReply("Usage: /approve <proposal_id>")
            return self.adapter.handle_approve(parsed.args[0], execute_on_approve=True)
        if parsed.name == "approve_only":
            if not parsed.args:
                return BotReply("Usage: /approve_only <proposal_id>")
            return self.adapter.handle_approve(parsed.args[0], execute_on_approve=False)
        if parsed.name == "reject":
            if not parsed.args:
                return BotReply("Usage: /reject <proposal_id>")
            return self.adapter.handle_reject(parsed.args[0])
        if parsed.name == "modify":
            if len(parsed.args) < 2:
                return BotReply("Usage: /modify <proposal_id> key=value[, key=value]")
            return self.adapter.handle_modify(parsed.args[0], " ".join(parsed.args[1:]))
        if parsed.name == "execute":
            if not parsed.args:
                return BotReply("Usage: /execute <proposal_id>")
            return self.adapter.handle_execute(parsed.args[0])
        if parsed.name == "halt":
            if not parsed.args:
                return BotReply("Usage: /halt <reason>")
            return self.adapter.handle_halt(" ".join(parsed.args))
        if parsed.name == "unhalt":
            return self.adapter.handle_unhalt()
        if parsed.name == "clear_safety":
            return self.adapter.handle_clear_safety()
        if parsed.name == "no_trades":
            return self.adapter.handle_no_trades()
        if parsed.name == "seed_demo":
            return self.adapter.handle_submit_proposal(build_demo_proposal(now=FIXED_DEMO_NOW))
        if parsed.name == "seed_no_trade":
            return self.adapter.handle_submit_no_trade(self._build_demo_no_trade())
        return BotReply("Unknown command. Use /help")

    @staticmethod
    def parse(text: str) -> ParsedBotCommand | None:
        stripped = text.strip()
        if not stripped.startswith("/"):
            return None
        parts = stripped[1:].split()
        if not parts:
            return None
        return ParsedBotCommand(name=parts[0].lower(), args=parts[1:])

    @staticmethod
    def _parse_limit(args: list[str]) -> int:
        if not args:
            return 5
        try:
            return max(1, int(args[0]))
        except ValueError:
            return 5

    @staticmethod
    def _build_demo_no_trade() -> NoTradeDecision:
        now = datetime(2026, 3, 25, 12, 0, tzinfo=UTC)
        return NoTradeDecision(
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
            created_at=now + timedelta(minutes=1),
        )
