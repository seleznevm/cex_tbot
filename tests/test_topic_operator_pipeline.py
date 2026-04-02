from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.openclaw_wrapper import OpenClawInboundMessage, OpenClawTopicWrapper
from cex_tbot.session_store import TradeSessionStore
from cex_tbot.topic_producer import TopicProposalProducer
from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge


class TopicOperatorPipelineTests(unittest.TestCase):
    def _proposal(self, proposal_id: str = "proposal_topic_1") -> TradeProposal:
        now = datetime.now(UTC)
        return TradeProposal(
            proposal_id=proposal_id,
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_topic_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=TradeDirection.LONG,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(hours=6))],
            stop_loss=99.0,
            take_profit_1=101.0,
            take_profit_2=102.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=10.0,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(hours=6),
            status=ProposalStatus.PENDING_APPROVAL,
        )

    def _build_stack(self) -> tuple[TradingBackendService, OpenClawTopicWrapper, TopicProposalProducer]:
        session = TradeSessionStore()
        service = TradingBackendService.from_session(session)
        bridge = TransportCommandBridge(
            BotCommandDispatcher(BotCommandAdapter(service, config=BotConfig())),
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({"125619710"}), allow_empty_policy=False),
        )
        wrapper = OpenClawTopicWrapper(bridge, default_chat_id="telegram:-100", default_thread_id="7")
        producer = TopicProposalProducer(service, wrapper)
        return service, wrapper, producer

    def test_topic_pipeline_modify_then_approve_only_keeps_replacement_in_same_topic(self) -> None:
        service, wrapper, producer = self._build_stack()
        proposal = self._proposal()

        outbound = producer.submit_and_emit(proposal)
        self.assertEqual(outbound.chat_id, "telegram:-100")
        self.assertEqual(outbound.thread_id, "7")
        self.assertIn("/modify proposal_topic_1", outbound.text)

        modify_reply = wrapper.handle_inbound(
            OpenClawInboundMessage(
                sender_id="125619710",
                text="/modify proposal_topic_1 stop_loss=98.5, thesis=tighter risk after retest",
                chat_id="telegram:-100",
                thread_id="7",
            )
        )

        self.assertEqual(modify_reply.chat_id, "telegram:-100")
        self.assertEqual(modify_reply.thread_id, "7")
        self.assertIn("Modify processed for proposal_topic_1", modify_reply.text)
        self.assertIn("Trade Report", modify_reply.text)
        self.assertEqual(service.session.proposals.require("proposal_topic_1").status, ProposalStatus.SUPERSEDED)
        replacement = service.session.proposals.require("proposal_topic_1_v2")
        self.assertEqual(replacement.status, ProposalStatus.PENDING_APPROVAL)
        self.assertEqual(replacement.stop_loss, 98.5)
        self.assertEqual(replacement.thesis, "tighter risk after retest")

        approve_reply = wrapper.handle_inbound(
            OpenClawInboundMessage(
                sender_id="125619710",
                text="/trade_approve_only proposal_topic_1_v2",
                chat_id="telegram:-100",
                thread_id="7",
            )
        )

        self.assertEqual(approve_reply.chat_id, "telegram:-100")
        self.assertEqual(approve_reply.thread_id, "7")
        self.assertIn("Approval processed for proposal_topic_1_v2", approve_reply.text)
        self.assertIn("Trade Report", approve_reply.text)
        self.assertEqual(
            service.session.proposals.require("proposal_topic_1_v2").status,
            ProposalStatus.APPROVED_PENDING_EXECUTION_CHECK,
        )
        self.assertEqual(service.session.execution_journal.list_events("proposal_topic_1_v2"), [])

    def test_topic_pipeline_reject_keeps_reply_in_same_topic_and_marks_rejected(self) -> None:
        service, wrapper, producer = self._build_stack()
        proposal = self._proposal("proposal_topic_reject_1")

        outbound = producer.submit_and_emit(proposal)
        self.assertEqual(outbound.thread_id, "7")

        reject_reply = wrapper.handle_inbound(
            OpenClawInboundMessage(
                sender_id="125619710",
                text="/trade_reject proposal_topic_reject_1",
                chat_id="telegram:-100",
                thread_id="7",
            )
        )

        self.assertEqual(reject_reply.chat_id, "telegram:-100")
        self.assertEqual(reject_reply.thread_id, "7")
        self.assertIn("Reject processed for proposal_topic_reject_1", reject_reply.text)
        self.assertIn("Trade Report", reject_reply.text)
        self.assertEqual(
            service.session.proposals.require("proposal_topic_reject_1").status,
            ProposalStatus.REJECTED_BY_HUMAN,
        )


if __name__ == "__main__":
    unittest.main()
