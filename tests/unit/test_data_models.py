from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from packages.data.models import AdjustedDailyBar
from packages.data.payloads import build_raw_provider_payload, hash_payload


def test_adjusted_daily_bar_validates_ohlc_range() -> None:
    bar = AdjustedDailyBar(
        symbol="SPY",
        date=date(2024, 1, 2),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000_000,
    )

    assert bar.adjusted is True


def test_adjusted_daily_bar_rejects_close_outside_range() -> None:
    with pytest.raises(ValidationError):
        AdjustedDailyBar(
            symbol="SPY",
            date=date(2024, 1, 2),
            open=100.0,
            high=102.0,
            low=99.0,
            close=103.0,
            volume=1_000_000,
        )


def test_payload_hash_is_stable_for_mapping_key_order() -> None:
    left = {"symbol": "SPY", "close": 500.0, "nested": {"b": 2, "a": 1}}
    right = {"nested": {"a": 1, "b": 2}, "close": 500.0, "symbol": "SPY"}

    assert hash_payload(left) == hash_payload(right)


def test_raw_provider_payload_preserves_raw_text_and_hash() -> None:
    payload = {"symbol": "SPY", "close": 500.0}
    fetched_at = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)

    raw_payload = build_raw_provider_payload(
        provider="fixture",
        endpoint="/v1/bars",
        payload=payload,
        fetched_at=fetched_at,
        symbol="SPY",
    )

    assert raw_payload.provider == "fixture"
    assert raw_payload.symbol == "SPY"
    assert raw_payload.payload_hash == hash_payload(payload)
    assert raw_payload.payload_size_bytes == len(raw_payload.raw_payload.encode("utf-8"))
