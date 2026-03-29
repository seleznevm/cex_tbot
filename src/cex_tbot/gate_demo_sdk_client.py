from __future__ import annotations

from dataclasses import dataclass
import math

from cex_tbot.exceptions import GateDemoDependencyError, GateDemoTransportError, MissingGateDemoApiError, MissingGateDemoCredentialsError
from cex_tbot.market_data.gate_metadata import GateInstrumentRecord


@dataclass(frozen=True)
class GateDemoSdkClient:
    gate_demo_api: str
    gate_demo_key: str
    gate_demo_secret: str

    def __post_init__(self) -> None:
        if not self.gate_demo_api.strip():
            raise MissingGateDemoApiError(
                "GATE_DEMO_API is required when CEX_TBOT_EXECUTION_MODE=gate_demo"
            )

    def _sdk(self):
        try:
            import gate_api
        except ImportError as exc:  # pragma: no cover
            raise GateDemoDependencyError(
                "gate-api package is required for authenticated Gate demo actions. Install gate-api."
            ) from exc
        configuration = gate_api.Configuration(host=self.gate_demo_api.rstrip("/"))
        configuration.key = self.gate_demo_key
        configuration.secret = self.gate_demo_secret
        api_client = gate_api.ApiClient(configuration)
        return gate_api, gate_api.FuturesApi(api_client)

    def _require_credentials(self) -> None:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for authenticated demo actions."
            )

    def list_instruments(self) -> list[GateInstrumentRecord]:
        _, api = self._sdk()
        try:
            payload = api.list_futures_contracts("usdt")
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo metadata fetch failed: {exc}") from exc
        records: list[GateInstrumentRecord] = []
        for item in payload:
            records.append(
                GateInstrumentRecord(
                    name=getattr(item, "name", ""),
                    in_delisting=bool(getattr(item, "in_delisting", False)),
                    trade_status=str(getattr(item, "trade_status", "tradable")),
                    quanto_multiplier=float(getattr(item, "quanto_multiplier", 0.0) or 0.0),
                    order_size_min=float(getattr(item, "order_size_min", 0.0) or 0.0),
                    mark_price_round=str(getattr(item, "mark_price_round", "0.01") or "0.01"),
                    ref_rebate_rate=str(getattr(item, "ref_rebate_rate", "0") or "0"),
                    funding_rate_indicative=str(getattr(item, "funding_rate_indicative", "0") or "0"),
                    leverage_min=str(getattr(item, "leverage_min", "1") or "1"),
                    leverage_max=str(getattr(item, "leverage_max", "20") or "20"),
                    maker_fee_rate=str(getattr(item, "maker_fee_rate", "0") or "0"),
                    taker_fee_rate=str(getattr(item, "taker_fee_rate", "0") or "0"),
                    risk_limit_base=str(getattr(item, "risk_limit_base", "0") or "0"),
                    is_new_listing=bool(getattr(item, "is_new_listing", False)),
                    listing_age_hours=int(getattr(item, "listing_age_hours", 0) or 0),
                    quote_asset=str(getattr(item, "quote_asset", "USDT") or "USDT"),
                    volume_24h=float(getattr(item, "volume_24h", 0.0) or 0.0),
                    open_interest=float(getattr(item, "open_interest", 0.0) or 0.0),
                    spread_bps=float(getattr(item, "spread_bps", 0.0) or 0.0),
                    top_book_depth=float(getattr(item, "top_book_depth", 0.0) or 0.0),
                )
            )
        return [item for item in records if item.name]

    def healthcheck(self) -> dict[str, object]:
        contracts = self.list_instruments()
        return {
            "ok": True,
            "endpoint": self.gate_demo_api.rstrip("/") + "/futures/usdt/contracts",
            "contracts_seen": len(contracts),
        }

    def account_status(self) -> dict[str, object]:
        self._require_credentials()
        _, api = self._sdk()
        try:
            payload = api.list_futures_accounts("usdt")
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo account status failed: {exc}") from exc
        return {
            "ok": True,
            "endpoint": self.gate_demo_api.rstrip("/") + "/futures/usdt/accounts",
            "currency": getattr(payload, "currency", None),
            "available": getattr(payload, "available", None),
            "total": getattr(payload, "total", None),
        }

    def balance_snapshot(self) -> dict[str, object]:
        return self.account_status()

    def positions_snapshot(self) -> list[dict[str, object]]:
        self._require_credentials()
        _, api = self._sdk()
        try:
            payload = api.list_positions("usdt")
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo positions failed: {exc}") from exc
        return [
            {
                "contract": getattr(item, "contract", None),
                "size": getattr(item, "size", None),
                "entry_price": getattr(item, "entry_price", None),
                "mark_price": getattr(item, "mark_price", None),
                "unrealised_pnl": getattr(item, "unrealised_pnl", None) or getattr(item, "unrealized_pnl", None),
                "leverage": getattr(item, "leverage", None),
                "mode": getattr(item, "mode", None),
            }
            for item in payload
        ]

    def open_orders(self) -> list[dict[str, object]]:
        self._require_credentials()
        _, api = self._sdk()
        try:
            payload = api.list_futures_orders("usdt", status="open")
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo open orders failed: {exc}") from exc
        return [
            {
                "id": getattr(item, "id", None),
                "contract": getattr(item, "contract", None),
                "size": getattr(item, "size", None),
                "price": getattr(item, "price", None),
                "status": getattr(item, "status", None),
                "tif": getattr(item, "tif", None),
            }
            for item in payload
        ]

    def order_status(self, order_id: str) -> dict[str, object]:
        self._require_credentials()
        _, api = self._sdk()
        try:
            item = api.get_futures_order("usdt", order_id)
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo order status failed: {exc}") from exc
        return {
            "id": getattr(item, "id", None),
            "contract": getattr(item, "contract", None),
            "size": getattr(item, "size", None),
            "price": getattr(item, "price", None),
            "status": getattr(item, "status", None),
            "left": getattr(item, "left", None),
            "fill_price": getattr(item, "fill_price", None),
        }

    def trigger_order_status(self, order_id: str) -> dict[str, object]:
        self._require_credentials()
        _, api = self._sdk()
        try:
            item = api.get_price_triggered_order("usdt", order_id)
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo trigger order status failed: {exc}") from exc
        initial = getattr(item, "initial", None)
        trigger = getattr(item, "trigger", None)
        return {
            "id": getattr(item, "id", None),
            "status": getattr(item, "status", None),
            "contract": getattr(initial, "contract", None) if initial is not None else None,
            "size": getattr(initial, "size", None) if initial is not None else None,
            "price": getattr(initial, "price", None) if initial is not None else None,
            "reduce_only": getattr(initial, "reduce_only", None) if initial is not None else None,
            "trigger_price": getattr(trigger, "price", None) if trigger is not None else None,
        }

    def place_test_order(self, contract: str, *, size: float, side: str) -> dict[str, object]:
        self._require_credentials()
        gate_api, api = self._sdk()
        try:
            contracts = self._normalize_contract_size(api, contract, size)
            signed_size = contracts if side == "buy" else -contracts
            order = gate_api.FuturesOrder(contract=contract, size=signed_size, price="0", tif="ioc")
            payload = api.create_futures_order("usdt", order)
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo place order failed: {exc}") from exc
        return {
            "id": getattr(payload, "id", None),
            "contract": getattr(payload, "contract", None),
            "side": side,
            "size": getattr(payload, "size", None),
            "requested_base_size": size,
            "normalized_contracts": contracts,
            "status": getattr(payload, "status", None),
        }

    def _normalize_contract_size(self, api, contract: str, base_size: float) -> int:
        if base_size <= 0:
            raise GateDemoTransportError("Gate demo place order failed: size must be positive")
        try:
            instruments = api.list_futures_contracts("usdt")
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo contract lookup failed: {exc}") from exc
        record = next((item for item in instruments if getattr(item, "name", None) == contract), None)
        if record is None:
            raise GateDemoTransportError(f"Gate demo contract lookup failed: unknown contract {contract}")
        quanto_multiplier = float(getattr(record, "quanto_multiplier", 0.0) or 0.0)
        min_contracts = int(float(getattr(record, "order_size_min", 1) or 1))
        if quanto_multiplier <= 0:
            raise GateDemoTransportError(f"Gate demo contract lookup failed: invalid quanto_multiplier for {contract}")
        contracts = math.ceil(base_size / quanto_multiplier)
        return max(min_contracts, contracts)

    def place_trigger_order(
        self,
        contract: str,
        *,
        trigger_price: float,
        order_price: float,
        size: int,
        side: str,
        reduce_only: bool = True,
        text: str = "cex_tbot_trigger",
    ) -> dict[str, object]:
        self._require_credentials()
        gate_api, api = self._sdk()
        try:
            signed_size = abs(int(size)) if side == "buy" else -abs(int(size))
            initial = {
                "contract": contract,
                "size": signed_size,
                "price": str(order_price),
                "tif": "gtc",
                "reduce_only": reduce_only,
                "text": text,
            }
            trigger = {
                "strategy_type": 0,
                "price_type": 0,
                "price": str(trigger_price),
                "rule": 1 if side == "buy" else 2,
            }
            payload = api.create_price_triggered_order(
                "usdt",
                gate_api.FuturesPriceTriggeredOrder(initial=initial, trigger=trigger),
            )
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo trigger order failed: {exc}") from exc
        return {
            "id": getattr(payload, "id", None),
            "status": getattr(payload, "status", None),
            "contract": contract,
            "size": signed_size,
            "trigger_price": trigger_price,
            "order_price": order_price,
            "reduce_only": reduce_only,
            "text": text,
        }

    def cancel_order(self, order_id: str) -> dict[str, object]:
        self._require_credentials()
        _, api = self._sdk()
        try:
            payload = api.cancel_futures_order("usdt", order_id)
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo cancel order failed: {exc}") from exc
        return {
            "id": getattr(payload, "id", None),
            "status": getattr(payload, "status", None),
        }
