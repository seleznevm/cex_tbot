from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.config import BotConfig
from cex_tbot.live_market_flow import LiveMarketProposalFlow, LiveMarketFlowDecision
from cex_tbot.market_pipeline import BinanceMarketDataPipeline
from cex_tbot.openclaw_wrapper import OpenClawOutboundMessage, OpenClawTopicWrapper
from cex_tbot.proposal_emitter import TopicProposalEmitter
from cex_tbot.proposal_workflow_glue import ProposalWorkflowGlue


class MarketRefreshPipeline(Protocol):
    def run_once(self) -> dict[str, object]: ...


LiveMarketRunStage = Literal["refresh", "decide", "emit"]


@dataclass(frozen=True)
class LiveMarketRunError:
    stage: LiveMarketRunStage
    error_type: str
    error_message: str

    def to_payload(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class LiveMarketRunResult:
    refresh: dict[str, object] | None
    decision: LiveMarketFlowDecision | None
    outbound: OpenClawOutboundMessage | None
    error: LiveMarketRunError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def decision_kind(self) -> str:
        if self.error is not None:
            return "error"
        if self.decision is None:
            return "unknown"
        return "proposal" if self.decision.proposal is not None else "no_trade"

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": self.ok,
            "decision_kind": self.decision_kind,
            "refresh": self.refresh,
            "selected_symbol": self.decision.selected_symbol if self.decision is not None else None,
            "chat_id": self.outbound.chat_id if self.outbound is not None else None,
            "thread_id": self.outbound.thread_id if self.outbound is not None else None,
            "text": self.outbound.text if self.outbound is not None else None,
        }
        if self.decision is not None and self.decision.proposal is not None:
            payload["proposal_id"] = self.decision.proposal.proposal_id
            payload["symbol"] = self.decision.proposal.symbol
        if self.decision is not None and self.decision.no_trade is not None:
            payload["reason_code"] = self.decision.no_trade.reason_code.value
            payload["symbol"] = self.decision.no_trade.symbol
        if self.error is not None:
            payload["error"] = self.error.to_payload()
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

    def _error_result(
        self,
        *,
        stage: LiveMarketRunStage,
        exc: Exception,
        refresh: dict[str, object] | None = None,
        decision: LiveMarketFlowDecision | None = None,
    ) -> LiveMarketRunResult:
        return LiveMarketRunResult(
            refresh=refresh,
            decision=decision,
            outbound=None,
            error=LiveMarketRunError(
                stage=stage,
                error_type=type(exc).__name__,
                error_message=str(exc) or repr(exc),
            ),
        )

    def run_once(self) -> LiveMarketRunResult:
        try:
            refresh = self.pipeline.run_once()
        except Exception as exc:
            return self._error_result(stage="refresh", exc=exc)

        try:
            decision = self.flow.decide()
        except Exception as exc:
            return self._error_result(stage="decide", exc=exc, refresh=refresh)

        try:
            if decision.proposal is not None:
                outbound = self.glue.submit_and_emit_proposal(decision.proposal)
            elif decision.no_trade is not None:
                outbound = self.glue.submit_and_emit_no_trade(decision.no_trade)
            else:
                raise RuntimeError("live market flow produced no proposal and no no-trade decision")
        except Exception as exc:
            return self._error_result(stage="emit", exc=exc, refresh=refresh, decision=decision)

        return LiveMarketRunResult(refresh=refresh, decision=decision, outbound=outbound)
