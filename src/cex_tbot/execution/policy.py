from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.execution.demo_sync import DemoOrderRecord


@dataclass(frozen=True)
class ConservativePolicyAssessment:
    proposal_id: str
    mode: str
    alerts: list[str]
    auto_actions: list[str]


class ConservativeDemoPolicy:
    mode = "conservative"

    def assess(self, proposal_id: str, orders: list[DemoOrderRecord]) -> ConservativePolicyAssessment:
        alerts: list[str] = []
        auto_actions: list[str] = []
        by_role = {item.role: item for item in orders}

        entry = by_role.get("entry")
        stop = by_role.get("stop_loss")
        tp1 = by_role.get("take_profit_1")
        tp2 = by_role.get("take_profit_2")

        if entry and str(entry.status).lower() in {"cancelled", "canceled"}:
            alerts.append("Entry order cancelled. Review protective orders manually; no auto-cancel in conservative mode.")
        if stop and str(stop.status).lower() in {"finished", "triggered", "closed"}:
            alerts.append("Stop-loss appears triggered. Verify exchange position is flat.")
        if tp1 and str(tp1.status).lower() in {"finished", "triggered", "closed"} and tp2 and str(tp2.status).lower() == "open":
            alerts.append("TP1 filled while TP2 remains open. Review residual size manually.")
        if tp2 and str(tp2.status).lower() in {"finished", "triggered", "closed"} and stop and str(stop.status).lower() == "open":
            alerts.append("TP2 filled while stop order still looks open. Conservative mode will not auto-cancel it.")
        if not alerts:
            alerts.append("No policy alerts. Conservative mode observed state only.")
        return ConservativePolicyAssessment(
            proposal_id=proposal_id,
            mode=self.mode,
            alerts=alerts,
            auto_actions=auto_actions,
        )
