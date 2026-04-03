from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cex_tbot import build_app
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.proposal_json_parser import JsonTradeProposalParser
from cex_tbot.tg_runner import TelegramRunnerPolicy, TelegramTransportRunner
from cex_tbot.topic_producer import TopicProposalProducer
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge


class _MessageStub:
    def __init__(self, text: str, thread_id: int | None) -> None:
        self.text = text
        self.message_thread_id = thread_id
        self.replies: list[dict[str, object]] = []

    async def reply_text(self, text: str, parse_mode: str | None = None, **kwargs: object) -> None:
        self.replies.append(
            {
                "text": text,
                "parse_mode": parse_mode,
                "kwargs": kwargs,
            }
        )


class _Obj:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _build_update(*, text: str, chat_id: int, thread_id: int | None, user_id: int, username: str):
    message = _MessageStub(text, thread_id)
    update = _Obj(
        effective_message=message,
        effective_chat=_Obj(id=chat_id, type="supergroup"),
        effective_user=_Obj(id=user_id, username=username),
    )
    return update, message


def _proposal_payload(proposal_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "proposal_id": proposal_id,
        "agent_name": "SmokeRunner",
        "strategy_id": "compose_flow",
        "strategy_version": "v1",
        "market_context_id": "ctx_smoke_1",
        "symbol": "BTC_USDT",
        "timeframe": "15m",
        "direction": "LONG",
        "entry_zone_min": 100.0,
        "entry_zone_max": 101.0,
        "entry_split": [
            {
                "leg_number": 1,
                "planned_entry_price": 100.5,
                "allocation_pct": 100.0,
                "size_fraction": 1.0,
                "valid_until": (now + timedelta(minutes=15)).isoformat(),
            }
        ],
        "stop_loss": 99.0,
        "take_profit_1": 102.0,
        "take_profit_2": 103.0,
        "risk_percent": 0.5,
        "risk_usd": 5.0,
        "position_size": 1.0,
        "confidence_score": 0.82,
        "thesis": "compose smoke flow",
        "invalidity_condition": "support breaks",
        "liquidity_check": "ok",
        "data_freshness_ms": 100,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
        "status": "PENDING_APPROVAL",
    }
    return json.dumps(payload)


async def _run_flow(
    *,
    storage_dir: Path,
    bot_token: str,
    chat_id: int,
    thread_id: int | None,
    operator_id: str,
    json_submitter_id: str,
    proposal_id: str,
) -> dict[str, object]:
    app = build_app(storage_dir=storage_dir)
    operator_policy = SenderPolicy(allowed_sender_ids=frozenset({operator_id}), allow_empty_policy=False)
    json_policy = SenderPolicy(allowed_sender_ids=frozenset({json_submitter_id}), allow_empty_policy=False)
    bridge = TransportCommandBridge(
        BotCommandDispatcher(BotCommandAdapter(app.backend, config=app.config, app=app)),
        sender_policy=operator_policy,
        write_sender_policy=operator_policy,
        audit_transcript=app.backend.session.operator_transcript,
    )
    parser = JsonTradeProposalParser(force_pending_approval=True)

    def _submit_proposal(proposal, reply_chat_id: str, reply_thread_id: str | None) -> str:
        wrapper = OpenClawTopicWrapper(None, default_chat_id=reply_chat_id, default_thread_id=reply_thread_id)
        producer = TopicProposalProducer(app.backend, wrapper)
        return producer.submit_and_emit(proposal).text

    runner = TelegramTransportRunner(
        bridge,
        bot_token=bot_token,
        policy=TelegramRunnerPolicy(
            allowed_chat_ids=frozenset({str(chat_id)}),
            allowed_thread_ids=frozenset({str(thread_id)}) if thread_id is not None else frozenset(),
        ),
        proposal_parser=parser.parse_text,
        proposal_submitter=_submit_proposal,
        json_sender_policy=json_policy,
    )

    json_update, json_message = _build_update(
        text=_proposal_payload(proposal_id),
        chat_id=chat_id,
        thread_id=thread_id,
        user_id=int(json_submitter_id),
        username="json_submitter",
    )
    await runner.handle_update(json_update, None)

    approve_update, approve_message = _build_update(
        text=f"/trade_approve_only {proposal_id}",
        chat_id=chat_id,
        thread_id=thread_id,
        user_id=int(operator_id),
        username="operator",
    )
    await runner.handle_update(approve_update, None)

    stored = app.backend.get_trade_detail_payload(proposal_id)
    return {
        "proposal_id": proposal_id,
        "json_reply": json_message.replies[0]["text"] if json_message.replies else None,
        "approve_reply": approve_message.replies[0]["text"] if approve_message.replies else None,
        "stored_status": stored["status"],
        "chat_id": f"telegram:{chat_id}",
        "thread_id": str(thread_id) if thread_id is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic Telegram-to-runtime smoke flow")
    parser.add_argument("--storage-dir", type=Path, required=True)
    parser.add_argument("--token", default="compose-smoke-token")
    parser.add_argument("--chat-id", type=int, required=True)
    parser.add_argument("--thread-id", type=int)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--json-submitter-id", required=True)
    parser.add_argument("--proposal-id", default="proposal_smoke_btc_001")
    args = parser.parse_args()

    payload = asyncio.run(
        _run_flow(
            storage_dir=args.storage_dir,
            bot_token=args.token,
            chat_id=args.chat_id,
            thread_id=args.thread_id,
            operator_id=args.operator_id,
            json_submitter_id=args.json_submitter_id,
            proposal_id=args.proposal_id,
        )
    )
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
