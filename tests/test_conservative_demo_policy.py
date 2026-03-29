from __future__ import annotations

import unittest

from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.execution.policy import ConservativeDemoPolicy


class ConservativeDemoPolicyTests(unittest.TestCase):
    def test_policy_emits_manual_review_alerts_without_auto_actions(self) -> None:
        policy = ConservativeDemoPolicy()
        assessment = policy.assess(
            "proposal_1",
            [
                DemoOrderRecord("entry", "proposal_1", "entry", "BTC_USDT", "buy", 10, "cancelled"),
                DemoOrderRecord("sl", "proposal_1", "stop_loss", "BTC_USDT", "sell", 10, "open", trigger_price=99.0),
                DemoOrderRecord("tp1", "proposal_1", "take_profit_1", "BTC_USDT", "sell", 5, "finished", trigger_price=101.0),
                DemoOrderRecord("tp2", "proposal_1", "take_profit_2", "BTC_USDT", "sell", 5, "open", trigger_price=102.0),
            ],
        )
        self.assertEqual(assessment.mode, "conservative")
        self.assertEqual(assessment.auto_actions, [])
        self.assertTrue(any("manual" in item.lower() or "auto" in item.lower() for item in assessment.alerts))


if __name__ == "__main__":
    unittest.main()
