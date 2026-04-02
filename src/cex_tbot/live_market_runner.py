from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.live_market_flow import LiveMarketProposalFlow, LiveMarketFlowDecision
from cex_tbot.market_pipeline import BinanceMarketDataPipeline
from cex_tbot.openclaw_wrapper import OpenClawOutboundMessage, OpenClawTopicWrapper
from cex_tbot.proposal_emitter import TopicProposalEmitter
from cex_tbot.proposal_workflow_glue import ProposalWorkflowGlue


class MarketRefreshPipeline(Protocol):
    def run_once(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class LiveMarketRunResult:
    refresh: dict[str, object]
    decision: LiveMarketFlowDecision
    outbound: OpenClawOutboundMessage

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "refresh": self.refresh,
            "chat_id": self.outbound.chat_id,
            "thread_id": self.outbound.thread_id,
            "text": self.outbound.text,
            "selected_symbol": self.decision.selected_symbol,
            "decision_kind": "proposal" if self.decision.proposal is not None else "no_trade",
        }
        if self.decision.proposal is not None:
            payload["proposal_id"] = self.decision.proposal.proposal_id
            payload["symbol"] = self.decision.proposal.symbol
        if self.decision.no_trade is not None:
            payload["reason_code"] = self.decision.no_trade.reason_code.value
            payload["symbol"] = self.decision.no_trade.symbol
        return payload


class LiveMarketPipelineRunner:
    def __init__(
        self,
        backend: TradingBackendService,
        *,
        config: BotConfig | None = None,
        market_dir: str | Path,
        chat_id: str,
        thread_id: str,
        pipeline: MarketRefreshPipeline | None = None,
    ) -> None:
        self.config = config or BotConfig()
        self.market_dir = Path(market_dir)
        self.wrapper = OpenClawTopicWrapper(None, default_chat_id=chat_id, default_thread_id=thread_id)
        self.glue = ProposalWorkflowGlue(backend, TopicProposalEmitter(self.wrapper))
        self.pipeline = pipeline or BinanceMarketDataPipeline(output_dir=self.market_dir)
        self.flow = LiveMarketProposalFlow(self.glue, config=self.config, market_dir=self.market_dir)

    def run_once(self) -> LiveMarketRunResult:
        refresh = self.pipeline.run_once()
        decision = self.flow.decide()
        if decision.proposal is not None:
            outbound = self.glue.submit_and_emit_proposal(decision.proposal)
        elif decision.no_trade is not None:
            outbound = self.glue.submit_and_emit_no_trade(decision.no_trade)
        else:
            raise RuntimeError("live market flow produced no proposal and no no-trade decision")
        return LiveMarketRunResult(refresh=refresh, decision=decision, outbound=outbound)
