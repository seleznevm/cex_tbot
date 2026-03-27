from __future__ import annotations

from dataclasses import dataclass

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

    def place_test_order(self, contract: str, *, size: float, side: str) -> dict[str, object]:
        self._require_credentials()
        gate_api, api = self._sdk()
        try:
            order = gate_api.FuturesOrder(contract=contract, size=size if side == "buy" else -size, price="0", tif="ioc")
            payload = api.create_futures_order("usdt", order)
        except Exception as exc:  # pragma: no cover
            raise GateDemoTransportError(f"Gate demo place order failed: {exc}") from exc
        return {
            "id": getattr(payload, "id", None),
            "contract": getattr(payload, "contract", None),
            "side": side,
            "size": getattr(payload, "size", None),
            "status": getattr(payload, "status", None),
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
