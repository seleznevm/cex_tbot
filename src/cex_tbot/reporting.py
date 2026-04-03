from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.execution import TradeTimelineView
from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.review_cards import ReviewCard
from cex_tbot.simulator import Position


@dataclass(frozen=True)
class TradeReport:
    proposal_id: str
    headline: str
    summary_lines: list[str]
    timeline_lines: list[str]

    def to_text(self) -> str:
        return "\n".join([self.headline, *self.summary_lines, *self.timeline_lines])

    def to_operator_text(self) -> str:
        return "\n".join(
            [
                self.headline,
                *self.summary_lines,
                "",
                *self.timeline_lines,
            ]
        )

    def to_telegram_text(self) -> str:
        return "\n".join(
            [
                f"**{self.headline}**",
                *self.summary_lines,
                "",
                *self.timeline_lines,
            ]
        )

    def to_compact_text(self) -> str:
        first_timeline = self.timeline_lines[0] if self.timeline_lines else "Timeline events: 0"
        return "\n".join(
            [
                self.headline,
                *self.summary_lines[:4],
                first_timeline,
            ]
        )


class TradeReportBuilder:
    def build(
        self,
        review_card: ReviewCard,
        timeline: TradeTimelineView,
        position: Position | None = None,
        demo_orders: list[DemoOrderRecord] | None = None,
    ) -> TradeReport:
        headline = f"Trade Report - {review_card.symbol} {review_card.direction} [{review_card.proposal_id}]"
        summary_lines = [
            f"Timeframe: {review_card.timeframe}",
            f"Confidence: {review_card.confidence_score:.2f}",
            f"Entry zone: {review_card.entry_zone_min} -> {review_card.entry_zone_max}",
            f"Entry split: {review_card.entry_summary}",
            f"Stop: {review_card.stop_loss}",
            f"Targets: {review_card.tp_summary}",
            f"Risk: {review_card.risk_summary}",
            f"Invalidation: {review_card.invalidity_condition}",
            f"Liquidity: {review_card.liquidity_check}",
            f"Thesis: {review_card.thesis}",
        ]
        if position is not None:
            summary_lines.extend(
                [
                    f"Position status: {position.status}",
                    f"Remaining size: {position.remaining_size}",
                    f"Realized PnL: {position.realized_pnl:.4f}",
                    f"Total fees: {position.total_fees:.4f}",
                ]
            )
        if demo_orders:
            summary_lines.append(f"Demo orders: {len(demo_orders)}")
            for item in demo_orders:
                summary_lines.append(
                    f"- {item.role}: id={item.order_id} status={item.status} size={item.size} trigger={item.trigger_price}"
                )
        timeline_lines = [
            f"Timeline events: {timeline.event_count}",
            f"State snapshots: {timeline.snapshot_count}",
        ]
        for event in timeline.events[-8:]:
            timeline_lines.append(f"- {event['kind']}: {event['message']}")
        return TradeReport(
            proposal_id=review_card.proposal_id,
            headline=headline,
            summary_lines=summary_lines,
            timeline_lines=timeline_lines,
        )
