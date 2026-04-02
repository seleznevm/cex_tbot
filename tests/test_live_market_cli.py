from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cex_tbot import __main__ as cli


class StubPipeline:
    def __init__(self, *args, **kwargs) -> None:
        self.output_dir = Path(kwargs["output_dir"])

    def run_once(self) -> dict[str, object]:
        (self.output_dir / "snapshots").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "universe.json").write_text(
            json.dumps(
                {
                    "symbols": [
                        {
                            "symbol": "BTC_USDT",
                            "quote_asset": "USDT",
                            "status": "TRADING",
                            "volume_quote_24h": 2_500_000.0,
                            "trade_count_24h": 150000,
                            "last_price": 100.0,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (self.output_dir / "snapshots" / "BTC_USDT.json").write_text(
            json.dumps(
                {
                    "symbol": "BTC_USDT",
                    "quote_asset": "USDT",
                    "status": "TRADING",
                    "last_price": 100.0,
                    "bid_price": 99.9,
                    "ask_price": 100.1,
                    "spread_bps": 1.0,
                    "volume_quote_24h": 2_500_000.0,
                    "price_change_pct_24h": 8.0,
                    "high_price_24h": 104.0,
                    "low_price_24h": 96.0,
                    "count_24h": 150000,
                }
            ),
            encoding="utf-8",
        )
        return {"status": "ok", "selected_symbols": 1}


class LiveMarketCliTests(unittest.TestCase):
    def test_live_market_run_cli_outputs_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage_dir = Path(tmp) / "runtime"
            market_dir = Path(tmp) / "market"
            stdout = io.StringIO()
            with patch.object(cli, "BinanceMarketDataPipeline", StubPipeline):
                with patch("sys.argv", [
                    "cex_tbot",
                    "live-market-run",
                    "--storage-dir",
                    str(storage_dir),
                    "--market-dir",
                    str(market_dir),
                    "--chat-id",
                    "chat-1",
                    "--thread-id",
                    "topic-7",
                    "--format",
                    "json",
                ]), patch("sys.stdout", stdout):
                    exit_code = cli.main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["decision_kind"], "proposal")
            self.assertEqual(payload["chat_id"], "chat-1")
            self.assertEqual(payload["thread_id"], "topic-7")
            self.assertEqual(payload["refresh"]["status"], "ok")
            self.assertIn("Trade approval request", payload["text"])


if __name__ == "__main__":
    unittest.main()
