import unittest

from cex_tbot.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = load_config({})
        self.assertEqual(cfg.whitelist_size, 20)
        self.assertEqual(cfg.execution_mode, "paper_sim")

    def test_env_override(self) -> None:
        cfg = load_config({"CEX_TBOT_WHITELIST_SIZE": "10", "CEX_TBOT_EXECUTION_MODE": "dry_run"})
        self.assertEqual(cfg.whitelist_size, 10)
        self.assertEqual(cfg.execution_mode, "dry_run")


if __name__ == "__main__":
    unittest.main()
