from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.live_market_runner import LiveMarketPipelineRunner
from cex_tbot.session_store import TradeSessionStore


class StubRefreshPipeline:
    def __init__(self, market_dir: Path, *, change_pct: float) -> None:
        self.market_dir = market_dir
        self.change_pct = change_pct
        self.calls = 0

    def run_once(self) -> dict[str, object]:
        self.calls += 1
        (self.market_dir / "snapshots").mkdir(parents=True, exist_ok=True)
        (self.market_dir / "universe.json").write_text(
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
        (self.market_dir / "snapshots" / "BTC_USDT.json").write_text(
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
                    "price_change_pct_24h": self.change_pct,
                    "high_price_24h": 104.0,
                    "low_price_24h": 96.0,
                    "count_24h": 150000,
                }
            ),
            encoding="utf-8",
        )
        return {
            "status": "ok",
            "selected_symbols": 1,
            "snapshot_files_written": 1,
        }


class LiveMarketPipelineRunnerTests(unittest.TestCase):
    def test_run_once_refreshes_market_and_emits_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            market_dir = Path(tmp) / "market"
            session = TradeSessionStore()
            backend = TradingBackendService.from_session(session)
            pipeline = StubRefreshPipeline(market_dir, change_pct=8.0)
            runner = LiveMarketPipelineRunner(
                backend,
                config=BotConfig(min_confidence_score=0.70),
                market_dir=market_dir,
                chat_id="chat-1",
                thread_id="topic-7",
                pipeline=pipeline,
            )

            result = runner.run_once()

            self.assertEqual(pipeline.calls, 1)
            self.assertEqual(result.refresh["status"], "ok")
            self.assertEqual(result.decision.selected_symbol, "BTC_USDT")
            self.assertEqual(len(session.proposals._proposals), 1)
            self.assertIn("Trade approval request", result.outbound.text)
            self.assertEqual(result.outbound.chat_id, "chat-1")
            self.assertEqual(result.outbound.thread_id, "topic-7")
            payload = result.to_payload()
            self.assertEqual(payload["decision_kind"], "proposal")
            self.assertIn("proposal_id", payload)

    def test_run_once_refreshes_market_and_emits_no_trade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            market_dir = Path(tmp) / "market"
            session = TradeSessionStore()
            backend = TradingBackendService.from_session(session)
            pipeline = StubRefreshPipeline(market_dir, change_pct=1.0)
            runner = LiveMarketPipelineRunner(
                backend,
                config=BotConfig(min_confidence_score=0.80),
                market_dir=market_dir,
                chat_id="chat-1",
                thread_id="topic-7",
                pipeline=pipeline,
            )

            result = runner.run_once()

            self.assertEqual(pipeline.calls, 1)
            self.assertEqual(len(session.proposals._proposals), 0)
            self.assertEqual(len(session.no_trades.list()), 1)
            self.assertIn("No-trade notice", result.outbound.text)
            payload = result.to_payload()
            self.assertEqual(payload["decision_kind"], "no_trade")
            self.assertEqual(payload["reason_code"], "CONFIDENCE_BELOW_THRESHOLD")


if __name__ == "__main__":
    unittest.main()
