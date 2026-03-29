from __future__ import annotations

from dataclasses import dataclass

from cex_tbot.decision_contracts import TradeProposal
from cex_tbot.enums import ProposalStatus, TradeDirection
from cex_tbot.execution.journal import ExecutionEvent, InMemoryExecutionJournal
from cex_tbot.execution.result import ExecutionResult
from cex_tbot.execution.state_store import InMemoryExecutionStateStore
from cex_tbot.execution.demo_sync import DemoOrderRecord, InMemoryDemoOrderStore
from cex_tbot.risk_engine import PortfolioState, RiskEngine
from cex_tbot.shared import utc_now
from cex_tbot.simulator.models import Position, PositionStatus


@dataclass(frozen=True)
class GateDemoBracketOrders:
    entry_order_id: str
    stop_order_id: str
    tp1_order_id: str
    tp2_order_id: str
    entry_contracts: int | None = None
    tp1_contracts: int | None = None
    tp2_contracts: int | None = None


class GateDemoExecutionAdapter:
    def __init__(
        self,
        risk_engine: RiskEngine,
        demo_client,
        journal: InMemoryExecutionJournal | None = None,
        state_store: InMemoryExecutionStateStore | None = None,
        demo_order_store: InMemoryDemoOrderStore | None = None,
        leverage: int = 10,
    ) -> None:
        self.risk_engine = risk_engine
        self.demo_client = demo_client
        self.journal = journal or InMemoryExecutionJournal()
        self.state_store = state_store or InMemoryExecutionStateStore()
        self.demo_order_store = demo_order_store or InMemoryDemoOrderStore()
        self.leverage = int(leverage)

    def execute(self, proposal: TradeProposal, portfolio: PortfolioState, *, now=None) -> ExecutionResult:
        effective_now = now or utc_now()
        self.journal.append(ExecutionEvent(proposal.proposal_id, "PRE_EXECUTION_CHECK", "starting pre-execution check"))
        check = self.risk_engine.pre_execution_check(proposal, portfolio, now=effective_now)
        if not check.is_approved:
            self.journal.append(
                ExecutionEvent(
                    proposal.proposal_id,
                    "PRE_EXECUTION_REJECTED",
                    check.reason_code.value,
                    payload={"reason": check.reason_code.value},
                )
            )
            return ExecutionResult(proposal.proposal_id, ProposalStatus.REJECTED_PRE_EXECUTION, reason=check.reason_code.value)

        side = "buy" if proposal.direction == TradeDirection.LONG else "sell"
        stop_side = "sell" if proposal.direction == TradeDirection.LONG else "buy"
        self.demo_client.set_leverage(proposal.symbol, min(self.leverage, 10))
        entry = self.demo_client.place_test_order(proposal.symbol, size=proposal.position_size, side=side)
        entry_order_id = str(entry.get("id") or "")
        entry_contracts = int(entry.get("normalized_contracts") or abs(int(entry.get("size") or 0)) or 0)
        if entry_contracts <= 0:
            entry_contracts = max(1, int(abs(float(entry.get("size") or 1))))

        protective = self._place_protective_orders(proposal, entry_order_id, entry_contracts)
        position = self._build_position(proposal)
        self.state_store.append_snapshot(position)

        self.journal.append(
            ExecutionEvent(
                proposal.proposal_id,
                "ENTRY_ORDER_PLACED",
                "gate demo entry order placed",
                position_id=position.position_id,
                payload={
                    "order_id": entry_order_id,
                    "side": side,
                    "requested_size": proposal.position_size,
                    "normalized_contracts": entry_contracts,
                    "status": str(entry.get("status") or "unknown"),
                },
            )
        )
        self.journal.append(
            ExecutionEvent(
                proposal.proposal_id,
                "BRACKET_ORDERS_PLACED",
                "gate demo protective orders placed",
                position_id=position.position_id,
                payload={
                    "stop_order_id": protective.stop_order_id,
                    "tp1_order_id": protective.tp1_order_id,
                    "tp2_order_id": protective.tp2_order_id,
                    "entry_order_id": protective.entry_order_id,
                    "tp1_contracts": protective.tp1_contracts or 0,
                    "tp2_contracts": protective.tp2_contracts or 0,
                },
            )
        )
        self.demo_order_store.replace_for_proposal(
            proposal.proposal_id,
            [
                DemoOrderRecord(
                    order_id=entry_order_id,
                    proposal_id=proposal.proposal_id,
                    role="entry",
                    contract=proposal.symbol,
                    side=side,
                    size=float(entry_contracts),
                    status=str(entry.get("status") or "unknown"),
                ),
                DemoOrderRecord(
                    order_id=protective.stop_order_id,
                    proposal_id=proposal.proposal_id,
                    role="stop_loss",
                    contract=proposal.symbol,
                    side=stop_side,
                    size=float(entry_contracts),
                    status="open",
                    trigger_price=proposal.stop_loss,
                    order_price=proposal.stop_loss,
                    reduce_only=True,
                    linked_entry_order_id=entry_order_id,
                ),
                DemoOrderRecord(
                    order_id=protective.tp1_order_id,
                    proposal_id=proposal.proposal_id,
                    role="take_profit_1",
                    contract=proposal.symbol,
                    side=stop_side,
                    size=float(protective.tp1_contracts or 0),
                    status="open",
                    trigger_price=proposal.take_profit_1,
                    order_price=proposal.take_profit_1,
                    reduce_only=True,
                    linked_entry_order_id=entry_order_id,
                ),
                DemoOrderRecord(
                    order_id=protective.tp2_order_id,
                    proposal_id=proposal.proposal_id,
                    role="take_profit_2",
                    contract=proposal.symbol,
                    side=stop_side,
                    size=float(protective.tp2_contracts or 0),
                    status="open",
                    trigger_price=proposal.take_profit_2,
                    order_price=proposal.take_profit_2,
                    reduce_only=True,
                    linked_entry_order_id=entry_order_id,
                ),
            ],
        )
        return ExecutionResult(proposal.proposal_id, ProposalStatus.EXECUTED, position=position, reason="gate_demo_bracket_submitted")

    def _build_position(self, proposal: TradeProposal) -> Position:
        avg_entry = sum((leg.planned_entry_price * leg.size_fraction) for leg in proposal.entry_split)
        return Position(
            proposal_id=proposal.proposal_id,
            symbol=proposal.symbol,
            direction=proposal.direction,
            status=PositionStatus.OPEN,
            planned_legs=len(proposal.entry_split),
            filled_legs=len(proposal.entry_split),
            avg_entry=avg_entry,
            total_size=proposal.position_size,
            remaining_size=proposal.position_size,
            realized_pnl=0.0,
            total_fees=0.0,
            stop_loss=proposal.stop_loss,
            take_profit_1=proposal.take_profit_1,
            take_profit_2=proposal.take_profit_2,
            tp1_hit=False,
            opened_at=proposal.created_at,
        )

    def _place_protective_orders(self, proposal: TradeProposal, entry_order_id: str, entry_contracts: int) -> GateDemoBracketOrders:
        stop_side = "sell" if proposal.direction == TradeDirection.LONG else "buy"
        tp_side = stop_side
        tp1_contracts = max(1, entry_contracts // 2)
        tp2_contracts = max(1, entry_contracts - tp1_contracts)
        stop_rule, tp_rule = self._protective_trigger_rules(proposal.direction)
        stop = self.demo_client.place_trigger_order(
            proposal.symbol,
            trigger_price=proposal.stop_loss,
            order_price=proposal.stop_loss,
            size=entry_contracts,
            side=stop_side,
            trigger_rule=stop_rule,
            reduce_only=True,
            text="cex_tbot_sl",
        )
        tp1 = self.demo_client.place_trigger_order(
            proposal.symbol,
            trigger_price=proposal.take_profit_1,
            order_price=proposal.take_profit_1,
            size=tp1_contracts,
            side=tp_side,
            trigger_rule=tp_rule,
            reduce_only=True,
            text="cex_tbot_tp1",
        )
        tp2 = self.demo_client.place_trigger_order(
            proposal.symbol,
            trigger_price=proposal.take_profit_2,
            order_price=proposal.take_profit_2,
            size=tp2_contracts,
            side=tp_side,
            trigger_rule=tp_rule,
            reduce_only=True,
            text="cex_tbot_tp2",
        )
        return GateDemoBracketOrders(
            entry_order_id=entry_order_id,
            stop_order_id=str(stop.get("id") or ""),
            tp1_order_id=str(tp1.get("id") or ""),
            tp2_order_id=str(tp2.get("id") or ""),
            entry_contracts=entry_contracts,
            tp1_contracts=tp1_contracts,
            tp2_contracts=tp2_contracts,
        )

    @staticmethod
    def _protective_trigger_rules(direction: TradeDirection) -> tuple[int, int]:
        if direction == TradeDirection.LONG:
            return 2, 1
        return 1, 2
