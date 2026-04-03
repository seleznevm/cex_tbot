from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import math
import time
from typing import Any, Protocol
from urllib.parse import urlencode, urlparse

from cex_tbot.exceptions import GateDemoDependencyError, GateDemoTransportError, GateLiveModeBlockedError, MissingGateDemoApiError, MissingGateDemoCredentialsError
from cex_tbot.market_data.gate_metadata import GateInstrumentRecord


class GateInstrumentFetcher(Protocol):
    """Fetch contract for Gate instrument metadata without binding Phase 2 to live transport."""

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        ...


class GateDemoInstrumentClient(Protocol):
    """Boundary for demo-safe Gate metadata access.

    Concrete HTTP/network transport is intentionally kept outside the core repo for now.
    Tests and integrations can inject a client implementation that returns existing
    ``GateInstrumentRecord`` values without changing the Phase 2 pipeline.
    """

    def list_instruments(self) -> list[GateInstrumentRecord]:
        ...

    def healthcheck(self) -> dict[str, object]:
        ...

    def account_status(self) -> dict[str, object]:
        ...

    def balance_snapshot(self) -> dict[str, object]:
        ...

    def positions_snapshot(self) -> list[dict[str, object]]:
        ...

    def open_orders(self) -> list[dict[str, object]]:
        ...

    def order_status(self, order_id: str) -> dict[str, object]:
        ...

    def place_test_order(self, contract: str, *, size: float, side: str) -> dict[str, object]:
        ...

    def cancel_order(self, order_id: str) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class StaticGateInstrumentFetcher:
    """Deterministic in-memory Gate metadata fetcher for tests and local Phase 2 flow."""

    records: tuple[GateInstrumentRecord, ...] = field(default_factory=tuple)

    @classmethod
    def from_iterable(cls, records: Iterable[GateInstrumentRecord]) -> "StaticGateInstrumentFetcher":
        return cls(tuple(records))

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        return list(self.records)


@dataclass(frozen=True)
class GateDemoInstrumentFetcher:
    """Adapter from the Gate demo client boundary to the existing metadata pipeline."""

    client: GateDemoInstrumentClient

    def fetch_instruments(self) -> list[GateInstrumentRecord]:
        return self.client.list_instruments()


@dataclass(frozen=True)
class UnimplementedGateDemoInstrumentClient:
    """Safe placeholder used until an explicit demo HTTP client is introduced.

    This keeps the integration path demo-only and prevents accidental drift into a
    hidden live transport. Real network behavior must be injected deliberately.
    """

    gate_demo_api: str

    def __post_init__(self) -> None:
        if not self.gate_demo_api.strip():
            raise MissingGateDemoApiError(
                "GATE_DEMO_API is required when CEX_TBOT_EXECUTION_MODE=gate_demo"
            )

    def list_instruments(self) -> list[GateInstrumentRecord]:
        raise NotImplementedError(
            "Gate demo transport boundary is wired, but no concrete demo client is installed. "
            "Inject GateDemoInstrumentClient explicitly; live transport remains blocked."
        )

    def healthcheck(self) -> dict[str, object]:
        raise NotImplementedError(
            "Gate demo transport boundary is wired, but no concrete demo client is installed. "
            "Inject GateDemoInstrumentClient explicitly; live transport remains blocked."
        )

    def account_status(self) -> dict[str, object]:
        raise NotImplementedError(
            "Gate demo account boundary is wired, but no concrete authenticated demo client is installed."
        )

    def balance_snapshot(self) -> dict[str, object]:
        raise NotImplementedError(
            "Gate demo balance boundary is wired, but no concrete authenticated demo client is installed."
        )

    def positions_snapshot(self) -> list[dict[str, object]]:
        raise NotImplementedError(
            "Gate demo positions boundary is wired, but no concrete authenticated demo client is installed."
        )

    def open_orders(self) -> list[dict[str, object]]:
        raise NotImplementedError(
            "Gate demo open-orders boundary is wired, but no concrete authenticated demo client is installed."
        )

    def order_status(self, order_id: str) -> dict[str, object]:
        raise NotImplementedError(
            "Gate demo order-status boundary is wired, but no concrete authenticated demo client is installed."
        )

    def place_test_order(self, contract: str, *, size: float, side: str) -> dict[str, object]:
        raise NotImplementedError(
            "Gate demo place-order boundary is wired, but no concrete authenticated demo client is installed."
        )

    def cancel_order(self, order_id: str) -> dict[str, object]:
        raise NotImplementedError(
            "Gate demo cancel-order boundary is wired, but no concrete authenticated demo client is installed."
        )


@dataclass(frozen=True)
class HttpxGateDemoInstrumentClient:
    """Minimal HTTP client for Gate demo/public metadata reads.

    This client only fetches contract metadata needed by the Phase 2 universe pipeline.
    It does not place orders and does not enable any live trading path.
    """

    gate_demo_api: str
    path: str = "/futures/usdt/contracts"
    account_path: str = "/futures/usdt/accounts"
    timeout_seconds: float = 10.0
    transport: Any | None = None
    gate_demo_key: str = ""
    gate_demo_secret: str = ""

    def __post_init__(self) -> None:
        if not self.gate_demo_api.strip():
            raise MissingGateDemoApiError(
                "GATE_DEMO_API is required when CEX_TBOT_EXECUTION_MODE=gate_demo"
            )

    def list_instruments(self) -> list[GateInstrumentRecord]:
        payload = self._get_json(self.path, error_prefix="Gate demo metadata fetch failed")

        if not isinstance(payload, list):
            raise GateDemoTransportError("Gate demo metadata fetch returned non-list payload")

        records: list[GateInstrumentRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            records.append(
                GateInstrumentRecord(
                    name=str(item.get("name") or item.get("contract") or ""),
                    in_delisting=bool(item.get("in_delisting", False)),
                    trade_status=str(item.get("trade_status") or item.get("status") or "tradable"),
                    quanto_multiplier=float(item.get("quanto_multiplier") or 0.0),
                    order_size_min=float(item.get("order_size_min") or 0.0),
                    mark_price_round=str(item.get("mark_price_round") or "0.01"),
                    ref_rebate_rate=str(item.get("ref_rebate_rate") or "0"),
                    funding_rate_indicative=str(item.get("funding_rate_indicative") or "0"),
                    leverage_min=str(item.get("leverage_min") or "1"),
                    leverage_max=str(item.get("leverage_max") or "20"),
                    maker_fee_rate=str(item.get("maker_fee_rate") or "0"),
                    taker_fee_rate=str(item.get("taker_fee_rate") or "0"),
                    risk_limit_base=str(item.get("risk_limit_base") or "0"),
                    is_new_listing=bool(item.get("is_new_listing", False)),
                    listing_age_hours=int(item.get("listing_age_hours") or 0),
                    quote_asset=str(item.get("quote_asset") or "USDT"),
                    volume_24h=float(item.get("volume_24h") or item.get("volume_24h_quote") or 0.0),
                    open_interest=float(item.get("open_interest") or 0.0),
                    spread_bps=float(item.get("spread_bps") or 0.0),
                    top_book_depth=float(item.get("top_book_depth") or 0.0),
                )
            )
        return [item for item in records if item.name]

    def healthcheck(self) -> dict[str, object]:
        payload = self._get_json(self.path, error_prefix="Gate demo healthcheck failed")
        if not isinstance(payload, list):
            raise GateDemoTransportError("Gate demo healthcheck returned non-list payload")
        return {
            "ok": True,
            "endpoint": self.gate_demo_api.rstrip("/") + self.path,
            "contracts_seen": len(payload),
        }

    def account_status(self) -> dict[str, object]:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for demo account status."
            )
        payload = self._get_json(
            self.account_path,
            error_prefix="Gate demo account status failed",
            authenticated=True,
        )
        if not isinstance(payload, dict):
            raise GateDemoTransportError("Gate demo account status returned non-dict payload")
        return {
            "ok": True,
            "endpoint": self.gate_demo_api.rstrip("/") + self.account_path,
            "currency": payload.get("currency"),
            "available": payload.get("available"),
            "total": payload.get("total"),
        }

    def balance_snapshot(self) -> dict[str, object]:
        return self.account_status()

    def positions_snapshot(self) -> list[dict[str, object]]:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for demo positions snapshot."
            )
        payload = self._get_json(
            "/futures/usdt/positions",
            error_prefix="Gate demo positions failed",
            authenticated=True,
        )
        if not isinstance(payload, list):
            raise GateDemoTransportError("Gate demo positions returned non-list payload")
        snapshots: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            snapshots.append(
                {
                    "contract": item.get("contract") or item.get("name"),
                    "size": item.get("size"),
                    "entry_price": item.get("entry_price"),
                    "mark_price": item.get("mark_price"),
                    "unrealised_pnl": item.get("unrealised_pnl") or item.get("unrealized_pnl"),
                    "leverage": item.get("leverage"),
                    "mode": item.get("mode"),
                }
            )
        return snapshots

    def open_orders(self) -> list[dict[str, object]]:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for demo open orders."
            )
        payload = self._get_json(
            "/futures/usdt/orders",
            error_prefix="Gate demo open orders failed",
            authenticated=True,
        )
        if not isinstance(payload, list):
            raise GateDemoTransportError("Gate demo open orders returned non-list payload")
        orders: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            orders.append(
                {
                    "id": item.get("id") or item.get("order_id"),
                    "contract": item.get("contract") or item.get("name"),
                    "size": item.get("size"),
                    "price": item.get("price"),
                    "status": item.get("status"),
                    "tif": item.get("tif"),
                }
            )
        return orders

    def order_status(self, order_id: str) -> dict[str, object]:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for demo order status."
            )
        payload = self._get_json(
            f"/futures/usdt/orders/{order_id}",
            error_prefix="Gate demo order status failed",
            authenticated=True,
        )
        if not isinstance(payload, dict):
            raise GateDemoTransportError("Gate demo order status returned non-dict payload")
        return {
            "id": payload.get("id") or payload.get("order_id"),
            "contract": payload.get("contract") or payload.get("name"),
            "size": payload.get("size"),
            "price": payload.get("price"),
            "status": payload.get("status"),
            "left": payload.get("left"),
            "fill_price": payload.get("fill_price"),
        }

    def place_test_order(self, contract: str, *, size: float, side: str) -> dict[str, object]:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for demo test orders."
            )
        normalized_side = side.strip().lower()
        if normalized_side not in {"buy", "sell"}:
            raise GateDemoTransportError("Gate demo place order failed: side must be buy or sell")
        contracts = self._normalize_contract_size(contract, size)
        signed_contracts = contracts if normalized_side == "buy" else -contracts
        payload = self._request_json(
            "POST",
            "/futures/usdt/orders",
            payload={"contract": contract, "size": signed_contracts, "price": "0", "tif": "ioc"},
            authenticated=True,
            error_prefix="Gate demo place order failed",
        )
        if not isinstance(payload, dict):
            raise GateDemoTransportError("Gate demo place order returned non-dict payload")
        return {
            "id": payload.get("id") or payload.get("order_id"),
            "contract": payload.get("contract") or contract,
            "side": normalized_side,
            "size": payload.get("size", signed_contracts),
            "requested_base_size": size,
            "normalized_contracts": contracts,
            "status": payload.get("status"),
        }

    def cancel_order(self, order_id: str) -> dict[str, object]:
        if not self.gate_demo_key or not self.gate_demo_secret:
            raise MissingGateDemoCredentialsError(
                "GATE_DEMO_KEY and GATE_DEMO_SECRET are required for demo cancel order."
            )
        payload = self._request_json(
            "DELETE",
            f"/futures/usdt/orders/{order_id}",
            authenticated=True,
            error_prefix="Gate demo cancel order failed",
        )
        if not isinstance(payload, dict):
            raise GateDemoTransportError("Gate demo cancel order returned non-dict payload")
        return {
            "id": payload.get("id") or payload.get("order_id") or order_id,
            "status": payload.get("status"),
        }

    def _normalize_contract_size(self, contract: str, base_size: float) -> int:
        if base_size <= 0:
            raise GateDemoTransportError("Gate demo place order failed: size must be positive")
        instruments = self.list_instruments()
        record = next((item for item in instruments if item.name == contract), None)
        if record is None:
            raise GateDemoTransportError(f"Gate demo contract lookup failed: unknown contract {contract}")
        if record.quanto_multiplier <= 0:
            raise GateDemoTransportError(f"Gate demo contract lookup failed: invalid quanto_multiplier for {contract}")
        min_contracts = max(1, int(record.order_size_min or 1))
        normalized = math.ceil(float(base_size) / float(record.quanto_multiplier))
        return max(min_contracts, normalized)

    def _get_json(self, path: str, *, error_prefix: str, authenticated: bool = False) -> Any:
        return self._request_json("GET", path, error_prefix=error_prefix, authenticated=authenticated)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        error_prefix: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = False,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - depends on optional env
            raise GateDemoDependencyError(
                "httpx is required for HttpxGateDemoInstrumentClient. Install cex-tbot[dev] or add httpx."
            ) from exc

        url = self.gate_demo_api.rstrip("/") + path
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) if payload is not None else ""
        query = urlencode(params or {}, doseq=True)
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            headers.update(self._auth_headers(method, path, query, body))
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    content=body if payload is not None else None,
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # pragma: no cover - thin wrapper
            raise GateDemoTransportError(f"{error_prefix}: {exc}") from exc

    def _auth_headers(self, method: str, path: str, query: str, body: str) -> dict[str, str]:
        timestamp = str(int(time.time()))
        payload_hash = hashlib.sha512(body.encode("utf-8")).hexdigest()
        signing_path = self._signing_path(path)
        sign_payload = "\n".join([method.upper(), signing_path, query, payload_hash, timestamp])
        sign = hmac.new(self.gate_demo_secret.encode("utf-8"), sign_payload.encode("utf-8"), hashlib.sha512).hexdigest()
        return {
            "KEY": self.gate_demo_key,
            "Timestamp": timestamp,
            "SIGN": sign,
        }

    def _signing_path(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        base_path = urlparse(self.gate_demo_api).path.rstrip("/")
        if not base_path:
            return path
        if path == base_path or path.startswith(base_path + "/"):
            return path
        return base_path + path
