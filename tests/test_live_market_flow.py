from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.live_market_flow import LiveMarketProposalFlow
from cex_tbot.openclaw_wrapper import OpenClawTopicWrapper
from cex_tbot.proposal_emitter import TopicProposalEmitter
from cex_tbot.proposal_workflow_glue import ProposalWorkflowGlue
from cex_tbot.session_store import TradeSessionStore


class LiveMarketFlowTests(unittest.TestCase):
    def _write_market_fixture(
        self,
        root: Path,
        *,
        spread_bps: float = 1.2,
        change_pct: float = 8.0,
        volume_quote_24h: float = 2_500_000.0,
    ) -> None:
        (root / "snapshots").mkdir(parents=True, exist_ok=True)
        (root / "universe.json").write_text(
            json.dumps(
                {
                    "symbols": [
                        {
                            "symbol": "BTC_USDT",
                            "quote_asset": "USDT",
                            "status": "TRADING",
                            "volume_quote_24h": volume_quote_24h,
                            "trade_count_24h": 150000,
                            "last_price": 100.0,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "snapshots" / "BTC_USDT.json").write_text(
            json.dumps(
                {
                    "symbol": "BTC_USDT",
                    "quote_asset": "USDT",
                    "status": "TRADING",
                    "last_price": 100.0,
                    "bid_price": 99.9,
                    "ask_price": 100.1,
                    "spread_bps": spread_bps,
                    "volume_quote_24h": volume_quote_24h,
                    "price_change_pct_24h": change_pct,
                    "high_price_24h": 104.0,
                    "low_price_24h": 96.0,
                    "count_24h": 150000,
                }
            ),
            encoding="utf-8",
        )

    def _build_flow(self, market_dir: Path, *, min_confidence_score: float = 0.70) -> tuple[TradeSessionStore, LiveMarketProposalFlow]:
        session = TradeSessionStore()
        backend = TradingBackendService.from_session(session)
        wrapper = OpenClawTopicWrapper(None, default_chat_id="chat-1", default_thread_id="topic-7")
        glue = ProposalWorkflowGlue(backend, TopicProposalEmitter(wrapper))
        flow = LiveMarketProposalFlow(
            glue,
            config=BotConfig(min_confidence_score=min_confidence_score),
            market_dir=market_dir,
        )
        return session, flow

    def test_submit_latest_generates_pending_proposal_and_reuses_topic_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            market_dir = Path(tmp)
            self._write_market_fixture(market_dir, spread_bps=1.0, change_pct=8.0)
            session, flow = self._build_flow(market_dir)

            outbound = flow.submit_latest()

            proposals = session.proposals._proposals
            self.assertEqual(len(proposals), 1)
            proposal = next(iter(proposals.values()))
            self.assertEqual(proposal.symbol, "BTC_USDT")
            self.assertEqual(proposal.status.value, "PENDING_APPROVAL")
            self.assertEqual(outbound.chat_id, "chat-1")
            self.assertEqual(outbound.thread_id, "topic-7")
            self.assertIn("Trade approval request", outbound.text)
            self.assertIn(proposal.proposal_id, outbound.text)

    def test_submit_latest_emits_no_trade_when_confidence_is_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            market_dir = Path(tmp)
            self._write_market_fixture(market_dir, spread_bps=1.0, change_pct=1.0)
            session, flow = self._build_flow(market_dir, min_confidence_score=0.80)

            outbound = flow.submit_latest()

            self.assertEqual(len(session.proposals._proposals), 0)
            decisions = session.no_trades.list()
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0].symbol, "BTC_USDT")
            self.assertIn("No-trade notice", outbound.text)
            self.assertIn("CONFIDENCE_BELOW_THRESHOLD", outbound.text)


if __name__ == "__main__":
    unittest.main()
