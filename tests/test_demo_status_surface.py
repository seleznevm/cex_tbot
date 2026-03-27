from __future__ import annotations

import unittest

from cex_tbot.bootstrap import build_app
from cex_tbot.bot_adapter import BotCommandAdapter
from cex_tbot.bot_dispatcher import BotCommandDispatcher
from cex_tbot.config import BotConfig
from cex_tbot.transport_bridge import SenderPolicy, TransportCommandBridge, TransportMessage
from cex_tbot.write_safety import WriteActionArmState
from tests.test_gate_demo_operator_commands import _HealthyDemoClient


class DemoStatusSurfaceTests(unittest.TestCase):
    def test_demo_status_and_disarm_flow(self) -> None:
        app = build_app(
            config=BotConfig(execution_mode='gate_demo', gate_demo_api='https://demo.gate', gate_demo_key='k', gate_demo_secret='s'),
            gate_demo_client=_HealthyDemoClient(),
        )
        arm_state = WriteActionArmState()
        adapter = BotCommandAdapter(app.backend, config=app.config, app=app, write_arm_state=arm_state)
        dispatcher = BotCommandDispatcher(adapter)
        bridge = TransportCommandBridge(
            dispatcher,
            sender_policy=SenderPolicy(allowed_sender_ids=frozenset({'125619710'}), allow_empty_policy=False),
            write_sender_policy=SenderPolicy(allowed_sender_ids=frozenset({'125619710'}), allow_empty_policy=False),
            arm_state=arm_state,
            audit_transcript=app.backend.session.operator_transcript,
        )

        bridge.handle_message(TransportMessage(sender_id='125619710', text='/demo_arm'))
        status_before = dispatcher.dispatch('/demo_status')
        disarmed = bridge.handle_message(TransportMessage(sender_id='125619710', text='/demo_disarm'))
        status_after = dispatcher.dispatch('/demo_write_status')
        audit = dispatcher.dispatch('/demo_audit')

        self.assertIn('Gate demo capabilities', status_before.text)
        self.assertIn('Demo write status', status_before.text)
        self.assertIn('Gate demo account status', status_before.text)
        self.assertIn('disarmed', disarmed.text)
        self.assertIn('is_active=False', status_after.text)
        self.assertIn('DEMO_DISARMED', audit.text)


if __name__ == '__main__':
    unittest.main()
