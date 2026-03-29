from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from cex_tbot.decision_contracts import NoTradeDecision
from cex_tbot.operator_router import RenderedResponse
from cex_tbot.post_analysis import PostAnalysisSummary
from cex_tbot.read_models import TradeDetailView, TradeListItem
from cex_tbot.reporting import TradeReport
from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.session_summary import SessionSummary


class ApiSerializer:
    @staticmethod
    def _json_ready(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: ApiSerializer._json_ready(item) for key, item in value.items()}
        if isinstance(value, list):
            return [ApiSerializer._json_ready(item) for item in value]
        if isinstance(value, tuple):
            return [ApiSerializer._json_ready(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        return value

    def trade_list_item(self, item: TradeListItem) -> dict[str, object]:
        return self._json_ready(asdict(item))

    def trade_detail(self, detail: TradeDetailView, demo_orders: list[DemoOrderRecord] | None = None) -> dict[str, object]:
        data = asdict(detail)
        data["timeline"] = {
            "proposal_id": detail.timeline.proposal_id,
            "event_count": detail.timeline.event_count,
            "snapshot_count": detail.timeline.snapshot_count,
            "events": detail.timeline.events,
            "snapshots": detail.timeline.snapshots,
        }
        data["demo_orders"] = [asdict(item) for item in (demo_orders or [])]
        return self._json_ready(data)

    def trade_report(self, report: TradeReport) -> dict[str, object]:
        return self._json_ready(
            {
                "proposal_id": report.proposal_id,
                "headline": report.headline,
                "summary_lines": list(report.summary_lines),
                "timeline_lines": list(report.timeline_lines),
                "text": report.to_text(),
                "operator_text": report.to_operator_text(),
                "telegram_text": report.to_telegram_text(),
                "compact_text": report.to_compact_text(),
            }
        )

    def no_trade_decision(self, decision: NoTradeDecision) -> dict[str, object]:
        return self._json_ready(asdict(decision))

    def session_summary(self, summary: SessionSummary) -> dict[str, object]:
        return self._json_ready(asdict(summary))

    def rendered_response(self, response: RenderedResponse) -> dict[str, object]:
        return self._json_ready(asdict(response))

    def post_analysis(self, summary: PostAnalysisSummary) -> dict[str, object]:
        return self._json_ready(asdict(summary))
