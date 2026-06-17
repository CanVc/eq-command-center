from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TLP_AUCTIONS_BASE_URL = "https://tlp-auctions.com"
PARSER_VERSION = "tlp_auctions_v3"

SERVER_NAMES = {
    "teek": "Teek",
    "yelinak": "Yelinak",
    "mischief": "Mischief",
    "thornblade": "Thornblade",
    "oakwynd": "Oakwynd",
    "frostreaver": "Frostreaver",
}


class TlpAuctionsError(RuntimeError):
    pass


class TlpAuctionsNotFoundError(TlpAuctionsError):
    pass


@dataclass(frozen=True)
class CatalogItem:
    item_id: int
    name: str
    price: float | None


@dataclass(frozen=True)
class KronoPrice:
    server_name: str
    average_price: float
    sample_size: int
    last_updated: str | None


@dataclass(frozen=True)
class KronoPriceWindow:
    days: int
    average_price: float
    sample_size: int


@dataclass(frozen=True)
class PricePoint:
    datetime: str
    plat_price: float
    krono_price: float
    is_buy: bool
    auctioneer: str | None


@dataclass(frozen=True)
class PriceStats:
    median_pp: int
    p25_pp: int
    p75_pp: int
    avg_pp: int
    min_pp: int
    max_pp: int
    sample_size: int
    confidence: str
    raw_payload: str


def api_server_name(server_name: str) -> str:
    key = server_name.strip().lower()
    if key not in SERVER_NAMES:
        valid = ", ".join(SERVER_NAMES.values())
        raise TlpAuctionsError(f"Invalid TLP Auctions server '{server_name}'. Valid servers: {valid}")
    return SERVER_NAMES[key]


def db_server_name(server_name: str) -> str:
    return api_server_name(server_name).lower()


class TlpAuctionsClient:
    def __init__(self, base_url: str = TLP_AUCTIONS_BASE_URL, timeout_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_catalog(self, server_name: str) -> list[CatalogItem]:
        payload = self._get_json("/api/items/catalog", {"serverName": api_server_name(server_name)})
        items = payload.get("items") or []
        catalog: list[CatalogItem] = []
        for item in items:
            item_id = _as_int(item.get("itemId"))
            name = item.get("name")
            if item_id is None or not name:
                continue
            catalog.append(CatalogItem(item_id=item_id, name=str(name), price=_as_float(item.get("price"))))
        return catalog

    def get_krono_price(self, server_name: str) -> KronoPrice | None:
        api_server = api_server_name(server_name)
        window_price = self._get_krono_price_window(api_server, preferred_days=1)
        if window_price is not None:
            return window_price

        try:
            payload = self._get_json(f"/api/krono-prices/{api_server}")
        except TlpAuctionsNotFoundError:
            return None
        if not payload:
            return None
        price = _as_float(payload.get("averagePrice"))
        if price is None or price <= 0:
            return None
        return KronoPrice(
            server_name=str(payload.get("serverName") or api_server),
            average_price=price,
            sample_size=_as_int(payload.get("sampleSize")) or 0,
            last_updated=payload.get("lastUpdated"),
        )

    def get_krono_price_windows(self, server_name: str) -> list[KronoPriceWindow]:
        payload = self._get_json(f"/api/krono-prices/{api_server_name(server_name)}/windows")
        windows = payload.get("windows") or []
        result: list[KronoPriceWindow] = []
        for window in windows:
            days = _as_int(window.get("days"))
            price = _as_float(window.get("averagePrice"))
            if days is None or price is None or price <= 0:
                continue
            result.append(
                KronoPriceWindow(
                    days=days,
                    average_price=price,
                    sample_size=_as_int(window.get("sampleSize")) or 0,
                )
            )
        return result

    def _get_krono_price_window(self, api_server: str, preferred_days: int) -> KronoPrice | None:
        try:
            payload = self._get_json(f"/api/krono-prices/{api_server}/windows")
        except TlpAuctionsNotFoundError:
            return None
        except TlpAuctionsError:
            return None

        for window in payload.get("windows") or []:
            days = _as_int(window.get("days"))
            price = _as_float(window.get("averagePrice"))
            if days != preferred_days or price is None or price <= 0:
                continue
            return KronoPrice(
                server_name=str(payload.get("serverName") or api_server),
                average_price=price,
                sample_size=_as_int(window.get("sampleSize")) or 0,
                last_updated=payload.get("lastUpdated"),
            )
        return None

    def get_item_history(self, item_id: int, server_name: str) -> list[PricePoint]:
        try:
            payload = self._get_json(f"/api/items/{item_id}/history/{api_server_name(server_name)}")
        except TlpAuctionsNotFoundError:
            return []
        points = payload.get("points") or []
        result: list[PricePoint] = []
        for point in points:
            result.append(
                PricePoint(
                    datetime=str(point.get("datetime") or ""),
                    plat_price=_as_float(point.get("platPrice")) or 0.0,
                    krono_price=_as_float(point.get("kronoPrice")) or 0.0,
                    is_buy=bool(point.get("isBuy")),
                    auctioneer=point.get("auctioneer"),
                )
            )
        return result

    def _get_json(self, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{self.base_url}{path}{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "eq-command-center/0.1",
            },
        )

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read().decode("utf-8", errors="replace")
                if not body.strip():
                    raise TlpAuctionsError(f"TLP Auctions returned an empty response for {path}")
                try:
                    return json.loads(body)
                except json.JSONDecodeError as exc:
                    snippet = body[:500].replace("\n", " ")
                    raise TlpAuctionsError(f"TLP Auctions returned non-JSON for {path}: {snippet}") from exc
            except HTTPError as exc:
                if exc.code == 404:
                    raise TlpAuctionsNotFoundError(f"TLP Auctions returned 404 for {path}") from exc
                body = exc.read().decode("utf-8", errors="replace")[:500]
                last_error = TlpAuctionsError(f"TLP Auctions HTTP {exc.code} for {path}: {body}")
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError, TlpAuctionsError) as exc:
                last_error = exc

            if attempt < 3:
                time.sleep(0.5 * attempt)

        raise TlpAuctionsError(str(last_error) if last_error else f"TLP Auctions request failed for {path}")


def compute_price_stats(
    points: list[PricePoint],
    krono_price_pp: int | None,
    *,
    max_age_days: int | None = None,
) -> PriceStats | None:
    source_points = _filter_recent_points(points, max_age_days)
    values = _effective_sell_prices(source_points, krono_price_pp)
    if not values:
        return None

    filtered = _mad_filter(values)
    if not filtered:
        filtered = values

    filtered = sorted(filtered)
    sample_size = len(filtered)
    median_pp = round(statistics.median(filtered))
    p25_pp = round(_percentile(filtered, 0.25))
    p75_pp = round(_percentile(filtered, 0.75))
    avg_pp = round(statistics.fmean(filtered))

    payload = {
        "parser_version": PARSER_VERSION,
        "history_window_days": max_age_days,
        "raw_points_seen": len(points),
        "points_used": len(source_points),
        "raw_sell_sample_size": len(values),
        "filtered_sample_size": sample_size,
        "mad_outliers_removed": len(values) - sample_size,
        "krono_price_pp_used": krono_price_pp,
    }

    return PriceStats(
        median_pp=median_pp,
        p25_pp=p25_pp,
        p75_pp=p75_pp,
        avg_pp=avg_pp,
        min_pp=round(filtered[0]),
        max_pp=round(filtered[-1]),
        sample_size=sample_size,
        confidence=_confidence(sample_size),
        raw_payload=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def _filter_recent_points(points: list[PricePoint], max_age_days: int | None) -> list[PricePoint]:
    if max_age_days is None or max_age_days <= 0:
        return points
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    recent: list[PricePoint] = []
    for point in points:
        point_datetime = _parse_api_datetime(point.datetime)
        if point_datetime is not None and point_datetime >= cutoff:
            recent.append(point)
    return recent


def _parse_api_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _effective_sell_prices(points: list[PricePoint], krono_price_pp: int | None) -> list[float]:
    prices: list[float] = []
    for point in points:
        if point.is_buy:
            continue
        value = point.plat_price
        if point.krono_price > 0:
            if krono_price_pp is None:
                continue
            value += point.krono_price * krono_price_pp
        if value > 0:
            prices.append(value)
    return prices


def _mad_filter(values: list[float]) -> list[float]:
    if len(values) < 5:
        return values
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    mad = statistics.median(deviations)
    if mad == 0:
        return values
    return [value for value in values if (0.6745 * abs(value - median) / mad) <= 3.5]


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _confidence(sample_size: int) -> str:
    if sample_size >= 20:
        return "high"
    if sample_size >= 5:
        return "medium"
    if sample_size >= 1:
        return "low"
    return "none"


def _as_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value))
    except (TypeError, ValueError):
        return None
