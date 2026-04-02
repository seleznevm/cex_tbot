from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, NoTradeDecision, TradeProposal
from cex_tbot.enums import NoTradeReasonCode, ProposalStatus, TradeDirection
from cex_tbot.proposal_workflow_glue import ProposalWorkflowGlue
from cex_tbot.shared import utc_now
from cex_tbot.universe import RawInstrument, UniverseService


@dataclass(frozen=True)
class LiveMarketFlowDecision:
    proposal: TradeProposal | None = None
    no_trade: NoTradeDecision | None = None
    selected_symbol: str | None = None


class LiveMarketProposalFlow:
    def __init__(
        self,
        glue: ProposalWorkflowGlue,
        *,
        config: BotConfig | None = None,
        market_dir: str | Path,
    ) -> None:
        self.glue = glue
        self.config = config or BotConfig()
        self.market_dir = Path(market_dir)
        self.universe_service = UniverseService(self.config)

    @property
    def universe_path(self) -> Path:
        return self.market_dir / "universe.json"

    @property
    def snapshots_dir(self) -> Path:
        return self.market_dir / "snapshots"

    def load_universe_payload(self) -> dict[str, Any]:
        return json.loads(self.universe_path.read_text(encoding="utf-8"))

    def load_snapshot_payload(self, symbol: str) -> dict[str, Any]:
        return json.loads((self.snapshots_dir / f"{symbol}.json").read_text(encoding="utf-8"))

    def _raw_instrument_from_market(self, universe_item: dict[str, Any], snapshot: dict[str, Any]) -> RawInstrument:
        volume_24h = float(snapshot.get("volume_quote_24h") or universe_item.get("volume_quote_24h") or 0.0)
        spread_bps = float(snapshot.get("spread_bps") or 0.0)
        trade_count = float(snapshot.get("count_24h") or universe_item.get("trade_count_24h") or 0.0)
        synthetic_depth = max(volume_24h * 0.01, trade_count * 10.0, 1_000.0)
        synthetic_open_interest = max(volume_24h * 0.05, synthetic_depth)
        status = str(universe_item.get("status") or snapshot.get("status") or "TRADING").lower()
        return RawInstrument(
            symbol=str(universe_item["symbol"]),
            quote_asset=str(universe_item.get("quote_asset") or snapshot.get("quote_asset") or "USDT"),
            status="active" if status == "trading" else status,
            listing_age_hours=365 * 24,
            volume_24h=volume_24h,
            open_interest=synthetic_open_interest,
            spread_bps=spread_bps,
            top_book_depth=synthetic_depth,
        )

    def _iter_ranked_market_inputs(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        payload = self.load_universe_payload()
        items = payload.get("symbols", [])
        if not isinstance(items, list):
            return []
        ranked: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
        for item in items:
            if not isinstance(item, dict) or "symbol" not in item:
                continue
            symbol = str(item["symbol"])
            snapshot_path = self.snapshots_dir / f"{symbol}.json"
            if not snapshot_path.exists():
                continue
            snapshot = self.load_snapshot_payload(symbol)
            score = float(snapshot.get("volume_quote_24h") or item.get("volume_quote_24h") or 0.0)
            ranked.append((score, item, snapshot))
        ranked.sort(key=lambda row: row[0], reverse=True)
        return [(item, snapshot) for _, item, snapshot in ranked]

    def decide(self) -> LiveMarketFlowDecision:
        ranked = self._iter_ranked_market_inputs()
        if not ranked:
            return LiveMarketFlowDecision(
                no_trade=NoTradeDecision(
                    agent_name="market_pipeline",
                    strategy_id="live_market_scan",
                    strategy_version="v1",
                    symbol="UNIVERSE",
                    timeframe="15m",
                    confidence_score=0.0,
                    reason_code=NoTradeReasonCode.UNIVERSE_NOT_ELIGIBLE,
                    reason_text="market pipeline has no usable universe/snapshot pair",
                    market_context_id="market_pipeline_empty",
                    liquidity_check="missing live market payload",
                    data_freshness_ms=0,
                )
            )

        raw_inputs = [self._raw_instrument_from_market(item, snapshot) for item, snapshot in ranked]
        refreshed = self.universe_service.refresh_universe(raw_inputs)
        eligible = self.universe_service.rank_whitelist(refreshed)
        if not eligible:
            return LiveMarketFlowDecision(
                no_trade=NoTradeDecision(
                    agent_name="market_pipeline",
                    strategy_id="live_market_scan",
                    strategy_version="v1",
                    symbol=raw_inputs[0].symbol,
                    timeframe="15m",
                    confidence_score=0.0,
                    reason_code=NoTradeReasonCode.UNIVERSE_NOT_ELIGIBLE,
                    reason_text="no live market symbols passed universe eligibility",
                    market_context_id=f"market_pipeline_{raw_inputs[0].symbol}",
                    liquidity_check="universe eligibility rejected all candidates",
                    data_freshness_ms=0,
                ),
                selected_symbol=raw_inputs[0].symbol,
            )

        selected = eligible[0]
        snapshot = next(snapshot for item, snapshot in ranked if str(item["symbol"]) == selected.symbol)
        change_pct = float(snapshot.get("price_change_pct_24h") or 0.0)
        confidence = min(0.95, 0.55 + (min(abs(change_pct), 20.0) / 40.0))
        if confidence < self.config.min_confidence_score:
            return LiveMarketFlowDecision(
                no_trade=NoTradeDecision(
                    agent_name="market_pipeline",
                    strategy_id="live_market_scan",
                    strategy_version="v1",
                    symbol=selected.symbol,
                    timeframe="15m",
                    confidence_score=confidence,
                    reason_code=NoTradeReasonCode.CONFIDENCE_BELOW_THRESHOLD,
                    reason_text=(
                        f"derived confidence {confidence:.2f} below threshold {self.config.min_confidence_score:.2f}"
                    ),
                    market_context_id=f"market_pipeline_{selected.symbol}",
                    liquidity_check=f"spread={selected.spread_bps:.2f}bps liquidity_score={selected.liquidity_score:.0f}",
                    data_freshness_ms=0,
                ),
                selected_symbol=selected.symbol,
            )

        return LiveMarketFlowDecision(
            proposal=self._build_proposal(selected.symbol, snapshot, confidence),
            selected_symbol=selected.symbol,
        )

    def _build_proposal(self, symbol: str, snapshot: dict[str, Any], confidence: float) -> TradeProposal:
        now = utc_now()
        last_price = max(float(snapshot.get("last_price") or 0.0), 0.01)
        high_price = max(float(snapshot.get("high_price_24h") or last_price), last_price)
        low_price = min(float(snapshot.get("low_price_24h") or last_price), last_price)
        range_width = max((high_price - low_price) * 0.15, last_price * 0.0025, 0.01)
        direction = TradeDirection.LONG if float(snapshot.get("price_change_pct_24h") or 0.0) >= 0 else TradeDirection.SHORT
        if direction == TradeDirection.LONG:
            entry_zone_min = max(last_price - range_width, 0.01)
            entry_zone_max = last_price
            stop_loss = max(entry_zone_min - range_width, 0.01)
            take_profit_1 = last_price + (range_width * 2.0)
            take_profit_2 = last_price + (range_width * 4.0)
        else:
            entry_zone_min = max(last_price, 0.01)
            entry_zone_max = last_price + range_width
            stop_loss = entry_zone_max + range_width
            take_profit_1 = max(last_price - (range_width * 2.0), 0.01)
            take_profit_2 = max(last_price - (range_width * 4.0), 0.01)
        position_size = max(100.0 / last_price, 0.001)
        entry_price = (entry_zone_min + entry_zone_max) / 2.0
        return TradeProposal(
            agent_name="market_pipeline",
            strategy_id="live_market_scan",
            strategy_version="v1",
            market_context_id=f"market_pipeline_{symbol}_{now.strftime('%Y%m%dT%H%M%S')}",
            symbol=symbol,
            timeframe="15m",
            direction=direction,
            entry_zone_min=entry_zone_min,
            entry_zone_max=entry_zone_max,
            entry_split=[EntrySplitLeg(1, entry_price, 100.0, 1.0, now + timedelta(minutes=15))],
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            risk_percent=self.config.default_risk_percent,
            risk_usd=5.0,
            position_size=position_size,
            confidence_score=confidence,
            thesis=(
                f"Live market scan selected {symbol} from market pipeline; "
                f"24h_change={float(snapshot.get('price_change_pct_24h') or 0.0):.2f}%"
            ),
            invalidity_condition="market momentum flips through stop before entry thesis confirms",
            liquidity_check=f"spread={float(snapshot.get('spread_bps') or 0.0):.2f}bps volume={float(snapshot.get('volume_quote_24h') or 0.0):.0f}",
            data_freshness_ms=0,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            status=ProposalStatus.PENDING_APPROVAL,
        )

    def submit_latest(self):
        decision = self.decide()
        if decision.proposal is not None:
            return self.glue.submit_and_emit_proposal(decision.proposal)
        if decision.no_trade is not None:
            return self.glue.submit_and_emit_no_trade(decision.no_trade)
        raise RuntimeError("live market flow produced no proposal and no no-trade decision")
