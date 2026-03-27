from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.read_models import QueryService
from cex_tbot.session_store import TradeSessionStore


@dataclass(frozen=True)
class PostAnalysisSummary:
    total_trades: int
    executed_trades: int
    rejected_trades: int
    pending_trades: int
    no_trade_decisions: int
    avg_confidence_all: float
    avg_confidence_executed: float
    avg_confidence_no_trade: float
    top_rejection_statuses: dict[str, int]
    no_trade_reason_counts: dict[str, int]
    symbol_activity: dict[str, int]
    timeframe_activity: dict[str, int]
    strategy_activity: dict[str, int]
    outcome_matrix: dict[str, dict[str, int]]
    recent_trade_count: int
    recent_executed_trades: int
    recent_rejected_trades: int
    recent_avg_confidence: float
    trend_hint: str | None
    trade_confidence_buckets: dict[str, int]
    no_trade_confidence_buckets: dict[str, int]
    calibration_hints: list[str]

    def to_text(self) -> str:
        lines = [
            "Post-analysis and calibration",
            f"- trades={self.total_trades} executed={self.executed_trades} rejected={self.rejected_trades} pending={self.pending_trades}",
            f"- no_trades={self.no_trade_decisions}",
            f"- avg_conf_all={self.avg_confidence_all:.4f} avg_conf_executed={self.avg_confidence_executed:.4f} avg_conf_no_trade={self.avg_confidence_no_trade:.4f}",
        ]
        if self.top_rejection_statuses:
            lines.append("Top rejection statuses:")
            for key, value in self.top_rejection_statuses.items():
                lines.append(f"- {key}: {value}")
        if self.no_trade_reason_counts:
            lines.append("No-trade reasons:")
            for key, value in self.no_trade_reason_counts.items():
                lines.append(f"- {key}: {value}")
        if self.symbol_activity:
            lines.append("Symbol activity:")
            for key, value in self.symbol_activity.items():
                lines.append(f"- {key}: {value}")
        if self.timeframe_activity:
            lines.append("Timeframe activity:")
            for key, value in self.timeframe_activity.items():
                lines.append(f"- {key}: {value}")
        if self.strategy_activity:
            lines.append("Strategy activity:")
            for key, value in self.strategy_activity.items():
                lines.append(f"- {key}: {value}")
        if self.outcome_matrix:
            lines.append("Outcome matrix:")
            for key, value in self.outcome_matrix.items():
                lines.append(f"- {key}: {value}")
        lines.append(f"Recent window: trades={self.recent_trade_count} executed={self.recent_executed_trades} rejected={self.recent_rejected_trades} avg_conf={self.recent_avg_confidence:.4f}")
        if self.trend_hint:
            lines.append(f"Trend hint: {self.trend_hint}")
        if self.trade_confidence_buckets:
            lines.append("Trade confidence buckets:")
            for key, value in self.trade_confidence_buckets.items():
                lines.append(f"- {key}: {value}")
        if self.no_trade_confidence_buckets:
            lines.append("No-trade confidence buckets:")
            for key, value in self.no_trade_confidence_buckets.items():
                lines.append(f"- {key}: {value}")
        if self.calibration_hints:
            lines.append("Calibration hints:")
            for hint in self.calibration_hints:
                lines.append(f"- {hint}")
        return "\n".join(lines)


class PostAnalysisBuilder:
    def __init__(self, session: TradeSessionStore, query_service: QueryService) -> None:
        self.session = session
        self.query_service = query_service

    @staticmethod
    def _bucket(confidence: float) -> str:
        if confidence < 0.4:
            return "lt_0_40"
        if confidence < 0.6:
            return "0_40_to_0_59"
        if confidence < 0.8:
            return "0_60_to_0_79"
        return "ge_0_80"

    def build(self) -> PostAnalysisSummary:
        trades = self.query_service.list_trades()
        no_trades = self.session.no_trades.list()
        executed = [item for item in trades if item.status == "EXECUTED"]
        rejected = [item for item in trades if "REJECT" in item.status or item.status in {"INVALIDATED", "EXPIRED", "CANCELLED"}]
        pending = [item for item in trades if item.status in {"PENDING_APPROVAL", "APPROVED_PENDING_EXECUTION_CHECK", "EXECUTION_READY"}]

        top_rejection_statuses: dict[str, int] = {}
        symbol_activity: dict[str, int] = {}
        timeframe_activity: dict[str, int] = {}
        strategy_activity: dict[str, int] = {}
        outcome_matrix: dict[str, dict[str, int]] = {}
        trade_confidence_buckets: dict[str, int] = {}
        proposal_map = self.session.proposals._proposals
        for item in trades:
            symbol_activity[item.symbol] = symbol_activity.get(item.symbol, 0) + 1
            timeframe_activity[item.timeframe] = timeframe_activity.get(item.timeframe, 0) + 1
            trade_confidence_buckets[self._bucket(item.confidence_score)] = trade_confidence_buckets.get(self._bucket(item.confidence_score), 0) + 1
            proposal = proposal_map.get(item.proposal_id)
            if proposal is not None:
                strategy_activity[proposal.strategy_id] = strategy_activity.get(proposal.strategy_id, 0) + 1
                matrix_key = f"{proposal.strategy_id}|{proposal.timeframe}"
                if matrix_key not in outcome_matrix:
                    outcome_matrix[matrix_key] = {"executed": 0, "rejected": 0, "pending": 0, "no_trade": 0}
                if item.status == "EXECUTED":
                    outcome_matrix[matrix_key]["executed"] += 1
                elif item.status in {"PENDING_APPROVAL", "APPROVED_PENDING_EXECUTION_CHECK", "EXECUTION_READY"}:
                    outcome_matrix[matrix_key]["pending"] += 1
                elif "REJECT" in item.status or item.status in {"INVALIDATED", "EXPIRED", "CANCELLED"}:
                    outcome_matrix[matrix_key]["rejected"] += 1
            if item in rejected:
                top_rejection_statuses[item.status] = top_rejection_statuses.get(item.status, 0) + 1

        no_trade_reason_counts: dict[str, int] = {}
        no_trade_confidence_buckets: dict[str, int] = {}
        for item in no_trades:
            code = item.reason_code.value
            no_trade_reason_counts[code] = no_trade_reason_counts.get(code, 0) + 1
            symbol_activity[item.symbol] = symbol_activity.get(item.symbol, 0) + 1
            timeframe_activity[item.timeframe] = timeframe_activity.get(item.timeframe, 0) + 1
            strategy_activity[item.strategy_id] = strategy_activity.get(item.strategy_id, 0) + 1
            matrix_key = f"{item.strategy_id}|{item.timeframe}"
            if matrix_key not in outcome_matrix:
                outcome_matrix[matrix_key] = {"executed": 0, "rejected": 0, "pending": 0, "no_trade": 0}
            outcome_matrix[matrix_key]["no_trade"] += 1
            no_trade_confidence_buckets[self._bucket(item.confidence_score)] = no_trade_confidence_buckets.get(self._bucket(item.confidence_score), 0) + 1

        avg_conf_all = round(sum(item.confidence_score for item in trades) / len(trades), 4) if trades else 0.0
        avg_conf_executed = round(sum(item.confidence_score for item in executed) / len(executed), 4) if executed else 0.0
        avg_conf_no_trade = round(sum(item.confidence_score for item in no_trades) / len(no_trades), 4) if no_trades else 0.0

        recent_trades = sorted(trades, key=lambda item: item.created_at, reverse=True)[:3]
        recent_executed = [item for item in recent_trades if item.status == "EXECUTED"]
        recent_rejected = [item for item in recent_trades if "REJECT" in item.status or item.status in {"INVALIDATED", "EXPIRED", "CANCELLED"}]
        recent_avg_conf = round(sum(item.confidence_score for item in recent_trades) / len(recent_trades), 4) if recent_trades else 0.0
        trend_hint = None
        if recent_trades:
            if recent_avg_conf > avg_conf_all:
                trend_hint = "Recent trade confidence is above all-time average."
            elif recent_avg_conf < avg_conf_all:
                trend_hint = "Recent trade confidence is below all-time average."
            else:
                trend_hint = "Recent trade confidence matches all-time average."

        hints: list[str] = []
        if no_trade_reason_counts.get("CONFIDENCE_BELOW_THRESHOLD", 0) >= 3:
            hints.append("Review confidence threshold calibration: frequent low-confidence no-trades detected.")
        if rejected and len(rejected) >= max(3, len(trades) // 2 if trades else 3):
            hints.append("Investigate why many proposals end in rejection/invalid states before execution.")
        if executed and avg_conf_executed < avg_conf_all:
            hints.append("Executed trades have lower confidence than overall flow; tighten approval or confidence filters.")
        if trade_confidence_buckets.get("ge_0_80", 0) == 0 and trades:
            hints.append("No high-confidence trades recorded yet; strategy quality or confidence scoring may need review.")
        if no_trade_confidence_buckets.get("lt_0_40", 0) >= max(2, len(no_trades)) and no_trades:
            hints.append("No-trade flow is dominated by very low-confidence setups; upstream idea filtering may be too loose.")
        if not executed and trades:
            hints.append("No executions recorded yet; gather more samples before changing thresholds aggressively.")
        if not trades and no_trades:
            hints.append("Only no-trade decisions recorded so far; inspect whether filters are too restrictive.")
        weak_cells = [key for key, stats in outcome_matrix.items() if stats.get("rejected", 0) + stats.get("no_trade", 0) >= 2 and stats.get("executed", 0) == 0]
        if weak_cells:
            hints.append(f"Weak strategy/timeframe cells detected: {', '.join(sorted(weak_cells)[:3])}.")
        strong_cells = [key for key, stats in outcome_matrix.items() if stats.get("executed", 0) >= 1 and stats.get("rejected", 0) == 0 and stats.get("no_trade", 0) == 0]
        if strong_cells:
            hints.append(f"Strong strategy/timeframe cells worth monitoring: {', '.join(sorted(strong_cells)[:3])}.")
        if not hints:
            hints.append("Current sample looks balanced; continue collecting outcomes before major recalibration.")

        return PostAnalysisSummary(
            total_trades=len(trades),
            executed_trades=len(executed),
            rejected_trades=len(rejected),
            pending_trades=len(pending),
            no_trade_decisions=len(no_trades),
            avg_confidence_all=avg_conf_all,
            avg_confidence_executed=avg_conf_executed,
            avg_confidence_no_trade=avg_conf_no_trade,
            top_rejection_statuses=dict(sorted(top_rejection_statuses.items(), key=lambda item: (-item[1], item[0]))[:5]),
            no_trade_reason_counts=dict(sorted(no_trade_reason_counts.items(), key=lambda item: (-item[1], item[0]))[:5]),
            symbol_activity=dict(sorted(symbol_activity.items(), key=lambda item: (-item[1], item[0]))[:10]),
            timeframe_activity=dict(sorted(timeframe_activity.items(), key=lambda item: (-item[1], item[0]))[:10]),
            strategy_activity=dict(sorted(strategy_activity.items(), key=lambda item: (-item[1], item[0]))[:10]),
            outcome_matrix=dict(sorted(outcome_matrix.items(), key=lambda item: item[0])[:20]),
            recent_trade_count=len(recent_trades),
            recent_executed_trades=len(recent_executed),
            recent_rejected_trades=len(recent_rejected),
            recent_avg_confidence=recent_avg_conf,
            trend_hint=trend_hint,
            trade_confidence_buckets=dict(sorted(trade_confidence_buckets.items())),
            no_trade_confidence_buckets=dict(sorted(no_trade_confidence_buckets.items())),
            calibration_hints=hints,
        )
