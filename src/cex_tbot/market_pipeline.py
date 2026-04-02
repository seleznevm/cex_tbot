from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
BINANCE_BASE_URL = "https://api.binance.com"
DEFAULT_OUTPUT_DIR = Path("/data/.openclaw/workspace/market")
DEFAULT_UNIVERSE_LIMIT = 150
DEFAULT_REQUEST_TIMEOUT_SEC = 20


class MarketPipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class BinanceSymbolRecord:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    is_spot_trading_allowed: bool
    filters: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class SnapshotRecord:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    last_price: float
    bid_price: float
    ask_price: float
    spread_bps: float
    volume_base_24h: float
    volume_quote_24h: float
    price_change_pct_24h: float
    high_price_24h: float
    low_price_24h: float
    count_24h: int
    weighted_avg_price_24h: float
    open_price_24h: float
    close_time_ms: int
    open_time_ms: int
    generated_at: str


class BinancePublicClient:
    def __init__(self, *, base_url: str = BINANCE_BASE_URL, timeout_sec: int = DEFAULT_REQUEST_TIMEOUT_SEC) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "openclaw-market-pipeline/1.0",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise MarketPipelineError(f"HTTP {exc.code} for {url}: {body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise MarketPipelineError(f"Network error for {url}: {exc}") from exc
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MarketPipelineError(f"Invalid JSON from {url}: {exc}") from exc

    def get_exchange_info(self) -> dict[str, Any]:
        data = self.get_json("/api/v3/exchangeInfo")
        if not isinstance(data, dict):
            raise MarketPipelineError("exchangeInfo payload is not an object")
        return data

    def get_book_tickers(self) -> list[dict[str, Any]]:
        data = self.get_json("/api/v3/ticker/bookTicker")
        if not isinstance(data, list):
            raise MarketPipelineError("bookTicker payload is not a list")
        return data

    def get_tickers_24h(self) -> list[dict[str, Any]]:
        data = self.get_json("/api/v3/ticker/24hr")
        if not isinstance(data, list):
            raise MarketPipelineError("24hr ticker payload is not a list")
        return data


def _to_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(result) or math.isinf(result):
        return 0.0
    return result


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        tmp_path = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    tmp_path.replace(path)


class BinanceMarketDataPipeline:
    def __init__(
        self,
        *,
        client: BinancePublicClient | None = None,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        universe_limit: int = DEFAULT_UNIVERSE_LIMIT,
    ) -> None:
        self.client = client or BinancePublicClient()
        self.output_dir = Path(output_dir)
        self.universe_limit = universe_limit

    @property
    def snapshots_dir(self) -> Path:
        return self.output_dir / "snapshots"

    @property
    def universe_path(self) -> Path:
        return self.output_dir / "universe.json"

    def load_existing_universe_symbols(self) -> set[str]:
        if not self.universe_path.exists():
            return set()
        try:
            payload = json.loads(self.universe_path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        symbols = payload.get("symbols", [])
        if not isinstance(symbols, list):
            return set()
        result: set[str] = set()
        for item in symbols:
            if isinstance(item, dict) and isinstance(item.get("symbol"), str):
                result.add(item["symbol"])
        return result

    def build_symbol_records(self, exchange_info: dict[str, Any]) -> list[BinanceSymbolRecord]:
        raw_symbols = exchange_info.get("symbols", [])
        records: list[BinanceSymbolRecord] = []
        for item in raw_symbols:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            quote_asset = item.get("quoteAsset")
            base_asset = item.get("baseAsset")
            if not isinstance(symbol, str) or not isinstance(quote_asset, str) or not isinstance(base_asset, str):
                continue
            if quote_asset != "USDT":
                continue
            if item.get("status") != "TRADING":
                continue
            if not bool(item.get("isSpotTradingAllowed", False)):
                continue
            filters: dict[str, dict[str, Any]] = {}
            for raw_filter in item.get("filters", []):
                if isinstance(raw_filter, dict) and isinstance(raw_filter.get("filterType"), str):
                    filters[raw_filter["filterType"]] = raw_filter
            records.append(
                BinanceSymbolRecord(
                    symbol=symbol,
                    base_asset=base_asset,
                    quote_asset=quote_asset,
                    status=str(item.get("status")),
                    is_spot_trading_allowed=bool(item.get("isSpotTradingAllowed", False)),
                    filters=filters,
                )
            )
        return records

    def select_universe(
        self,
        records: list[BinanceSymbolRecord],
        tickers_24h: list[dict[str, Any]],
    ) -> list[BinanceSymbolRecord]:
        by_symbol = {record.symbol: record for record in records}
        ranked: list[tuple[float, BinanceSymbolRecord]] = []
        for row in tickers_24h:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol")
            if not isinstance(symbol, str) or symbol not in by_symbol:
                continue
            volume_quote = _to_float(row.get("quoteVolume"))
            count = _to_int(row.get("count"))
            last_price = _to_float(row.get("lastPrice"))
            score = volume_quote + (count * 10.0) + last_price
            ranked.append((score, by_symbol[symbol]))
        ranked.sort(key=lambda item: item[0], reverse=True)
        selected: list[BinanceSymbolRecord] = []
        seen: set[str] = set()
        for _, record in ranked:
            if record.symbol in seen:
                continue
            selected.append(record)
            seen.add(record.symbol)
            if len(selected) >= self.universe_limit:
                break
        return selected

    def build_universe_payload(
        self,
        selected: list[BinanceSymbolRecord],
        tickers_24h: list[dict[str, Any]],
        *,
        generated_at: str,
    ) -> dict[str, Any]:
        ticker_map = {item.get("symbol"): item for item in tickers_24h if isinstance(item, dict) and isinstance(item.get("symbol"), str)}
        symbols: list[dict[str, Any]] = []
        for record in selected:
            ticker = ticker_map.get(record.symbol, {})
            lot_filter = record.filters.get("LOT_SIZE", {})
            price_filter = record.filters.get("PRICE_FILTER", {})
            min_notional_filter = record.filters.get("NOTIONAL") or record.filters.get("MIN_NOTIONAL") or {}
            symbols.append(
                {
                    "symbol": record.symbol,
                    "base_asset": record.base_asset,
                    "quote_asset": record.quote_asset,
                    "status": record.status,
                    "price_tick_size": price_filter.get("tickSize"),
                    "quantity_step_size": lot_filter.get("stepSize"),
                    "min_quantity": lot_filter.get("minQty"),
                    "min_notional": min_notional_filter.get("minNotional"),
                    "volume_quote_24h": _to_float(ticker.get("quoteVolume")),
                    "trade_count_24h": _to_int(ticker.get("count")),
                    "last_price": _to_float(ticker.get("lastPrice")),
                }
            )
        return {
            "schema_version": 1,
            "exchange": "binance",
            "market_type": "spot",
            "generated_at": generated_at,
            "selection": {
                "quote_asset": "USDT",
                "status": "TRADING",
                "spot_only": True,
                "limit": self.universe_limit,
                "ranking": "quoteVolume_24h_then_trade_count",
            },
            "symbols": symbols,
        }

    def build_snapshot_records(
        self,
        selected: list[BinanceSymbolRecord],
        tickers_24h: list[dict[str, Any]],
        book_tickers: list[dict[str, Any]],
        *,
        generated_at: str,
    ) -> list[SnapshotRecord]:
        ticker_map = {item.get("symbol"): item for item in tickers_24h if isinstance(item, dict) and isinstance(item.get("symbol"), str)}
        book_map = {item.get("symbol"): item for item in book_tickers if isinstance(item, dict) and isinstance(item.get("symbol"), str)}
        snapshots: list[SnapshotRecord] = []
        for record in selected:
            ticker = ticker_map.get(record.symbol)
            book = book_map.get(record.symbol)
            if ticker is None or book is None:
                continue
            bid = _to_float(book.get("bidPrice"))
            ask = _to_float(book.get("askPrice"))
            last_price = _to_float(ticker.get("lastPrice"))
            spread_bps = 0.0
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2.0
                if mid > 0:
                    spread_bps = ((ask - bid) / mid) * 10_000.0
            snapshots.append(
                SnapshotRecord(
                    symbol=record.symbol,
                    base_asset=record.base_asset,
                    quote_asset=record.quote_asset,
                    status=record.status,
                    last_price=last_price,
                    bid_price=bid,
                    ask_price=ask,
                    spread_bps=spread_bps,
                    volume_base_24h=_to_float(ticker.get("volume")),
                    volume_quote_24h=_to_float(ticker.get("quoteVolume")),
                    price_change_pct_24h=_to_float(ticker.get("priceChangePercent")),
                    high_price_24h=_to_float(ticker.get("highPrice")),
                    low_price_24h=_to_float(ticker.get("lowPrice")),
                    count_24h=_to_int(ticker.get("count")),
                    weighted_avg_price_24h=_to_float(ticker.get("weightedAvgPrice")),
                    open_price_24h=_to_float(ticker.get("openPrice")),
                    close_time_ms=_to_int(ticker.get("closeTime")),
                    open_time_ms=_to_int(ticker.get("openTime")),
                    generated_at=generated_at,
                )
            )
        return snapshots

    def write_snapshot_files(self, snapshots: list[SnapshotRecord]) -> list[str]:
        written: list[str] = []
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        for snapshot in snapshots:
            atomic_write_json(self.snapshots_dir / f"{snapshot.symbol}.json", asdict(snapshot))
            written.append(snapshot.symbol)
        return written

    def prune_stale_snapshots(self, active_symbols: set[str]) -> list[str]:
        removed: list[str] = []
        if not self.snapshots_dir.exists():
            return removed
        for path in self.snapshots_dir.glob("*.json"):
            if path.stem in active_symbols:
                continue
            path.unlink(missing_ok=True)
            removed.append(path.stem)
        return removed

    def run_once(self) -> dict[str, Any]:
        generated_at = _iso_now()
        previous_symbols = self.load_existing_universe_symbols()
        exchange_info = self.client.get_exchange_info()
        tickers_24h = self.client.get_tickers_24h()
        book_tickers = self.client.get_book_tickers()

        records = self.build_symbol_records(exchange_info)
        selected = self.select_universe(records, tickers_24h)
        universe_payload = self.build_universe_payload(selected, tickers_24h, generated_at=generated_at)
        snapshots = self.build_snapshot_records(selected, tickers_24h, book_tickers, generated_at=generated_at)

        if not selected:
            raise MarketPipelineError("Universe selection returned zero symbols")
        if not snapshots:
            raise MarketPipelineError("No snapshots could be built for selected universe")

        atomic_write_json(self.universe_path, universe_payload)
        written_symbols = self.write_snapshot_files(snapshots)
        removed_symbols = self.prune_stale_snapshots({item.symbol for item in selected})

        result = {
            "status": "ok",
            "generated_at": generated_at,
            "universe_path": str(self.universe_path),
            "snapshots_dir": str(self.snapshots_dir),
            "selected_symbols": len(selected),
            "snapshot_files_written": len(written_symbols),
            "symbols_added": sorted(set(written_symbols) - previous_symbols),
            "symbols_removed": sorted(set(previous_symbols) - set(written_symbols)),
            "stale_snapshot_files_removed": sorted(removed_symbols),
        }
        atomic_write_json(self.output_dir / "last_run.json", result)
        return result

    def run_forever(self, *, interval_sec: int, stop_after_runs: int | None = None) -> int:
        runs = 0
        while True:
            runs += 1
            started = time.monotonic()
            try:
                result = self.run_once()
                LOGGER.info("Market pipeline run ok: %s", json.dumps(result, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                payload = {
                    "status": "error",
                    "generated_at": _iso_now(),
                    "error": str(exc),
                    "run_number": runs,
                }
                atomic_write_json(self.output_dir / "last_run.json", payload)
                LOGGER.exception("Market pipeline run failed: %s", exc)
            if stop_after_runs is not None and runs >= stop_after_runs:
                return runs
            elapsed = time.monotonic() - started
            sleep_for = max(1.0, float(interval_sec) - elapsed)
            time.sleep(sleep_for)
