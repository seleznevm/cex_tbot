from __future__ import annotations

import unittest

from cex_tbot.execution.policy import ConservativePolicyAssessment
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.proposal_emitter import TopicProposalEmitter


class ConservativeAlertTopicRenderingTests(unittest.TestCase):
    def test_emitter_renders_alert_to_expected_topic(self) -> None:
        emitter = TopicProposalEmitter(
            OpenClawTopicWrapper(None, default_chat_id="telegram:-1003832858724", default_thread_id="7")
        )
        outbound = emitter.emit_conservative_alert(
            ConservativePolicyAssessment(
                proposal_id="proposal_1",
                mode="conservative",
                alerts=["Entry order cancelled. Review protective orders manually; no auto-cancel in conservative mode."],
                auto_actions=[],
            )
        )
        self.assertEqual(outbound.chat_id, "telegram:-1003832858724")
        self.assertEqual(outbound.thread_id, "7")
        self.assertIn("Gate demo conservative alert", outbound.text)
        self.assertIn("proposal_id=proposal_1", outbound.text)


if __name__ == "__main__":
    unittest.main()
