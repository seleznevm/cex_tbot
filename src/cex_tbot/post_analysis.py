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
        trade_confidence_buckets: dict[str, int] = {}
        proposal_map = self.session.proposals._proposals
        for item in trades:
            symbol_activity[item.symbol] = symbol_activity.get(item.symbol, 0) + 1
            timeframe_activity[item.timeframe] = timeframe_activity.get(item.timeframe, 0) + 1
            trade_confidence_buckets[self._bucket(item.confidence_score)] = trade_confidence_buckets.get(self._bucket(item.confidence_score), 0) + 1
            proposal = proposal_map.get(item.proposal_id)
            if proposal is not None:
                strategy_activity[proposal.strategy_id] = strategy_activity.get(proposal.strategy_id, 0) + 1
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
            no_trade_confidence_buckets[self._bucket(item.confidence_score)] = no_trade_confidence_buckets.get(self._bucket(item.confidence_score), 0) + 1

        avg_conf_all = round(sum(item.confidence_score for item in trades) / len(trades), 4) if trades else 0.0
        avg_conf_executed = round(sum(item.confidence_score for item in executed) / len(executed), 4) if executed else 0.0
        avg_conf_no_trade = round(sum(item.confidence_score for item in no_trades) / len(no_trades), 4) if no_trades else 0.0

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
            trade_confidence_buckets=dict(sorted(trade_confidence_buckets.items())),
            no_trade_confidence_buckets=dict(sorted(no_trade_confidence_buckets.items())),
            calibration_hints=hints,
        )
