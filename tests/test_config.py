import unittest

from cex_tbot.config import load_config
from cex_tbot.market_data import GateLiveModeBlockedError, MissingGateDemoApiError


class ConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = load_config({})
        self.assertEqual(cfg.whitelist_size, 20)
        self.assertEqual(cfg.execution_mode, "paper_sim")
        self.assertEqual(cfg.gate_demo_api, "")
        self.assertEqual(cfg.gate_demo_key, "")
        self.assertEqual(cfg.gate_demo_secret, "")
        self.assertEqual(cfg.gate_demo_test_order_size, 1.0)

    def test_env_override(self) -> None:
        cfg = load_config(
            {
                "CEX_TBOT_WHITELIST_SIZE": "10",
                "CEX_TBOT_EXECUTION_MODE": "dry_run",
                "GATE_DEMO_API": "demo-secret-placeholder",
                "GATE_DEMO_KEY": "demo-key",
                "GATE_DEMO_SECRET": "demo-secret",
                "GATE_DEMO_TEST_ORDER_SIZE": "0.25",
            }
        )
        self.assertEqual(cfg.whitelist_size, 10)
        self.assertEqual(cfg.execution_mode, "dry_run")
        self.assertEqual(cfg.gate_demo_api, "demo-secret-placeholder")
        self.assertEqual(cfg.gate_demo_key, "demo-key")
        self.assertEqual(cfg.gate_demo_secret, "demo-secret")
        self.assertEqual(cfg.gate_demo_test_order_size, 0.25)

    def test_gate_demo_requires_demo_api(self) -> None:
        with self.assertRaisesRegex(MissingGateDemoApiError, "GATE_DEMO_API"):
            load_config({"CEX_TBOT_EXECUTION_MODE": "gate_demo"})

    def test_gate_demo_normalizes_mode_and_trims_api(self) -> None:
        cfg = load_config(
            {
                "CEX_TBOT_EXECUTION_MODE": " GATE_DEMO ",
                "GATE_DEMO_API": "  demo-secret-placeholder  ",
            }
        )
        self.assertEqual(cfg.execution_mode, "gate_demo")
        self.assertEqual(cfg.gate_demo_api, "demo-secret-placeholder")

    def test_live_mode_is_explicitly_blocked(self) -> None:
        with self.assertRaisesRegex(GateLiveModeBlockedError, "blocked"):
            load_config({"CEX_TBOT_EXECUTION_MODE": "live"})


if __name__ == "__main__":
    unittest.main()
