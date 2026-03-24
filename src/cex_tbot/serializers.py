from __future__ import annotations

from dataclasses import asdict

from cex_tbot.operator_router import RenderedResponse
from cex_tbot.read_models import TradeDetailView, TradeListItem
from cex_tbot.reporting import TradeReport
from cex_tbot.session_summary import SessionSummary


class ApiSerializer:
    def trade_list_item(self, item: TradeListItem) -> dict[str, object]:
        return asdict(item)

    def trade_detail(self, detail: TradeDetailView) -> dict[str, object]:
        data = asdict(detail)
        data["timeline"] = {
            "proposal_id": detail.timeline.proposal_id,
            "event_count": detail.timeline.event_count,
            "snapshot_count": detail.timeline.snapshot_count,
            "events": detail.timeline.events,
            "snapshots": detail.timeline.snapshots,
        }
        return data

    def trade_report(self, report: TradeReport) -> dict[str, object]:
        return {
            "proposal_id": report.proposal_id,
            "headline": report.headline,
            "summary_lines": list(report.summary_lines),
            "timeline_lines": list(report.timeline_lines),
            "text": report.to_text(),
        }

    def session_summary(self, summary: SessionSummary) -> dict[str, object]:
        return asdict(summary)

    def rendered_response(self, response: RenderedResponse) -> dict[str, object]:
        return asdict(response)
