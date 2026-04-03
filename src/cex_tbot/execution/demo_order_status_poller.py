from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.backend_service import TradingBackendService
from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.execution.policy import ConservativePolicyAssessment
from cex_tbot.topic_producer import TopicProposalProducer


_FINAL_ORDER_STATUSES = frozenset({"finished", "closed", "triggered", "cancelled", "canceled"})


@dataclass(frozen=True)
class DemoOrderPollRunResult:
    ok: bool
    scanned_proposals: int
    synced_proposals: int
    synced_orders: int
    items: list[dict[str, object]]
    errors: list[dict[str, str]]

    def to_payload(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "scanned_proposals": self.scanned_proposals,
            "synced_proposals": self.synced_proposals,
            "synced_orders": self.synced_orders,
            "items": self.items,
            "errors": self.errors,
        }


class DemoOrderStatusPoller:
    def __init__(
        self,
        backend: TradingBackendService,
        *,
        emit_telegram_alerts: bool = False,
        alert_producer: TopicProposalProducer | None = None,
    ) -> None:
        self.backend = backend
        self.emit_telegram_alerts = emit_telegram_alerts
        self.alert_producer = alert_producer

    def run_once(self) -> DemoOrderPollRunResult:
        proposal_ids = [str(item["proposal_id"]) for item in self.backend.list_trades_payload()]
        items: list[dict[str, object]] = []
        errors: list[dict[str, str]] = []
        synced_orders = 0
        for proposal_id in proposal_ids:
            records = self.backend.session.demo_orders.list_for_proposal(proposal_id)
            if not self._has_open_orders(records):
                continue
            try:
                synced = self.backend.sync_demo_orders(proposal_id)
                policy = self.backend.get_demo_policy_assessment_payload(proposal_id)
            except Exception as exc:
                errors.append(
                    {
                        "proposal_id": proposal_id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc) or repr(exc),
                    }
                )
                continue
            payload: dict[str, object] = {
                "proposal_id": proposal_id,
                "orders": [
                    {
                        "order_id": item.order_id,
                        "role": item.role,
                        "status": item.status,
                        "size": item.size,
                        "trigger_price": item.trigger_price,
                    }
                    for item in synced
                ],
                "policy": policy,
            }
            if self.emit_telegram_alerts and self.alert_producer is not None:
                alert_texts = [text for text in policy["alerts"] if "No policy alerts" not in text]
                if alert_texts:
                    outbound = self.alert_producer.emit_conservative_alert(ConservativePolicyAssessment(**policy))
                    payload["telegram_alert"] = {
                        "chat_id": outbound.chat_id,
                        "thread_id": outbound.thread_id,
                        "text": outbound.text,
                    }
            synced_orders += len(synced)
            items.append(payload)
        return DemoOrderPollRunResult(
            ok=not errors,
            scanned_proposals=len(proposal_ids),
            synced_proposals=len(items),
            synced_orders=synced_orders,
            items=items,
            errors=errors,
        )

    @staticmethod
    def _has_open_orders(records: list[DemoOrderRecord]) -> bool:
        for record in records:
            if str(record.status).lower() not in _FINAL_ORDER_STATUSES:
                return True
        return False
