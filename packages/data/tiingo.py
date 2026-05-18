"""Read-only Tiingo EOD data adapter for frozen-validation signal checks."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, Literal

from packages.data.models import AdjustedDailyBar
from packages.data.payloads import hash_payload

TiingoCheckFailure = Literal[
    "missing_api_key",
    "unauthorized",
    "rate_limited",
    "missing_ohlcv_fields",
    "provider_error",
]


class TiingoEodProviderError(RuntimeError):
    """Sanitized Tiingo EOD provider error."""

    def __init__(self, result: TiingoCheckFailure, error_class: str) -> None:
        super().__init__(error_class)
        self.result = result
        self.error_class = error_class


class TiingoEodProvider:
    """Minimal Tiingo historical EOD client.

    The adapter performs read-only historical daily-bar requests only. It never calls broker
    endpoints, live quote endpoints, order endpoints, schedules, or validation start paths.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.tiingo.com",
        endpoint_template: str = "/tiingo/daily/{symbol}/prices",
        adjusted_prices_required: bool = True,
        completed_daily_bars_only: bool = True,
        timeout_seconds: float = 20.0,
    ) -> None:
        token = api_key.strip()
        if not token:
            raise TiingoEodProviderError("missing_api_key", "tiingo_api_key_missing")
        self._api_key = token
        self._base_url = base_url.rstrip("/")
        self._endpoint_template = endpoint_template
        self._adjusted_prices_required = adjusted_prices_required
        self._completed_daily_bars_only = completed_daily_bars_only
        self._timeout_seconds = timeout_seconds

    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        normalized_symbol = symbol.strip().upper()
        path = self._endpoint_template.format(
            symbol=urllib.parse.quote(normalized_symbol, safe="")
        )
        query = urllib.parse.urlencode(
            {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "format": "json",
            }
        )
        request = urllib.request.Request(
            f"{self._base_url}{path}?{query}",
            headers={
                "Accept": "application/json",
                "Authorization": "Token " + self._api_key,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise TiingoEodProviderError("unauthorized", f"tiingo_http_{exc.code}") from exc
            if exc.code == 429:
                raise TiingoEodProviderError("rate_limited", "tiingo_http_429") from exc
            raise TiingoEodProviderError("provider_error", f"tiingo_http_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise TiingoEodProviderError("provider_error", "tiingo_network_error") from exc
        except json.JSONDecodeError as exc:
            raise TiingoEodProviderError("provider_error", "tiingo_invalid_json") from exc

        if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
            raise TiingoEodProviderError("provider_error", "tiingo_unexpected_payload_shape")
        return normalize_tiingo_eod_records(
            normalized_symbol,
            payload,
            adjusted_prices_required=self._adjusted_prices_required,
            completed_daily_bars_only=self._completed_daily_bars_only,
        )


def normalize_tiingo_eod_records(
    symbol: str,
    records: Sequence[Any],
    *,
    adjusted_prices_required: bool,
    completed_daily_bars_only: bool,
    today: date | None = None,
) -> tuple[AdjustedDailyBar, ...]:
    """Normalize Tiingo EOD records into adjusted daily bars."""

    normalized_symbol = symbol.strip().upper()
    current_date = today or datetime.now(UTC).date()
    bars: list[AdjustedDailyBar] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise TiingoEodProviderError("provider_error", "tiingo_record_not_object")
        missing = _missing_tiingo_fields(record, adjusted_prices_required=adjusted_prices_required)
        if missing:
            raise TiingoEodProviderError(
                "missing_ohlcv_fields",
                "tiingo_missing_fields_" + "_".join(missing[:5]),
            )
        bar_date = _parse_tiingo_date(record["date"])
        if completed_daily_bars_only and bar_date >= current_date:
            continue
        if adjusted_prices_required:
            open_price = float(record["adjOpen"])
            high_price = float(record["adjHigh"])
            low_price = float(record["adjLow"])
            close_price = float(record["adjClose"])
            volume_value = record.get("adjVolume", record["volume"])
            adjusted = True
        else:
            open_price = float(record["open"])
            high_price = float(record["high"])
            low_price = float(record["low"])
            close_price = float(record["close"])
            volume_value = record["volume"]
            adjusted = False
        bars.append(
            AdjustedDailyBar(
                symbol=normalized_symbol,
                date=bar_date,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=int(float(volume_value)),
                adjusted=adjusted,
                provider="tiingo",
                payload_hash=hash_payload(record),
            )
        )
    return tuple(sorted(bars, key=lambda bar: bar.date))


def _missing_tiingo_fields(
    record: Mapping[str, Any],
    *,
    adjusted_prices_required: bool,
) -> list[str]:
    required = ["date", "open", "high", "low", "close", "volume"]
    if adjusted_prices_required:
        required.extend(["adjOpen", "adjHigh", "adjLow", "adjClose"])
    missing: list[str] = []
    for field in required:
        value = record.get(field)
        if value is None or value == "":
            missing.append(field)
    return missing


def _parse_tiingo_date(value: object) -> date:
    text = str(value)
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text[:10])
