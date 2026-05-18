from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from packages.data.models import AdjustedDailyBar
from packages.data.primary_signal_gate import (
    PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH,
    PrimarySignalDataGateRequest,
    build_frozen_readiness_m44c_packet,
    run_primary_signal_data_gate,
    write_frozen_readiness_m44c_artifact,
    write_primary_signal_data_gate_m44c_artifact,
)
from packages.data.tiingo import (
    TiingoEodProviderError,
    normalize_tiingo_eod_records,
)

AS_OF = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
SYMBOLS = ("SPY", "QQQ", "AAPL", "MSFT", "XLK")


class _SuccessfulTiingoClient:
    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        return _bars(symbol, count=260, end=end)


class _ShortHistoryTiingoClient:
    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        return _bars(symbol, count=30, end=end)


class _UnauthorizedTiingoClient:
    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        raise TiingoEodProviderError("unauthorized", "tiingo_http_403")


class _RateLimitedTiingoClient:
    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        raise TiingoEodProviderError("rate_limited", "tiingo_http_429")


class _MissingFieldsTiingoClient:
    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        raise TiingoEodProviderError("missing_ohlcv_fields", "tiingo_missing_fields_adjClose")


def _request(**updates: object) -> PrimarySignalDataGateRequest:
    data = {
        "mode": "verify",
        "provider": "tiingo",
        "feed": "eod",
        "symbols": SYMBOLS,
        "confirm_read_only": True,
        "confirm_no_broker_writes": True,
        "confirm_no_schedules": True,
        "confirm_no_frozen_validation_start": True,
    }
    data.update(updates)
    return PrimarySignalDataGateRequest.model_validate(data)


def _flat_cleanup_packet(tmp_path: Path) -> Path:
    path = tmp_path / "flat_start_cleanup_m44.json"
    path.write_text(
        json.dumps(
            {
                "flat_start_cleanup": {
                    "final_open_orders_count": 0,
                    "final_positions_count": 0,
                    "final_reconciliation": "flat_zero_positions_zero_open_orders",
                    "m45_flat_start_ready": True,
                    "blockers": [],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _m44_readiness_packet(tmp_path: Path) -> Path:
    path = tmp_path / "frozen_readiness_m44.json"
    path.write_text(
        json.dumps(
            {
                "frozen_readiness": {
                    "m45_readiness": False,
                    "blockers": ["non_iex_primary_signal_data_not_verified"],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _bars(symbol: str, *, count: int, end: date) -> tuple[AdjustedDailyBar, ...]:
    first = end - timedelta(days=count - 1)
    return tuple(
        AdjustedDailyBar(
            symbol=symbol,
            date=first + timedelta(days=index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000_000,
            adjusted=True,
            provider="tiingo",
            payload_hash=f"hash-{symbol}-{index}",
        )
        for index in range(count)
    )


def test_tiingo_missing_api_key_produces_no_go() -> None:
    result = run_primary_signal_data_gate(
        _request(),
        environ={},
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert result.packet.tiingo_api_key_present is False
    assert result.packet.data_check_result == "missing_api_key"
    assert "non_iex_primary_signal_data_not_verified" in result.blockers


def test_tiingo_provider_normalizes_adjusted_eod_ohlcv_records() -> None:
    records = [
        {
            "date": "2026-05-15T00:00:00.000Z",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10.5,
            "volume": 100,
            "adjOpen": 20,
            "adjHigh": 22,
            "adjLow": 18,
            "adjClose": 21,
            "adjVolume": 200,
        }
    ]

    bars = normalize_tiingo_eod_records(
        "SPY",
        records,
        adjusted_prices_required=True,
        completed_daily_bars_only=True,
        today=date(2026, 5, 18),
    )

    assert len(bars) == 1
    assert bars[0].symbol == "SPY"
    assert bars[0].open == 20
    assert bars[0].high == 22
    assert bars[0].low == 18
    assert bars[0].close == 21
    assert bars[0].volume == 200
    assert bars[0].adjusted is True
    assert bars[0].payload_hash


def test_tiingo_missing_ohlcv_fields_produce_no_go() -> None:
    with pytest.raises(TiingoEodProviderError, match="tiingo_missing_fields"):
        normalize_tiingo_eod_records(
            "SPY",
            [
                {
                    "date": "2026-05-15",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 100,
                }
            ],
            adjusted_prices_required=True,
            completed_daily_bars_only=True,
            today=date(2026, 5, 18),
        )

    result = run_primary_signal_data_gate(
        _request(symbols=("SPY",)),
        environ={"TIINGO_API_KEY": "not-a-real-test-token"},
        tiingo_client=_MissingFieldsTiingoClient(),
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert result.packet.data_check_result == "missing_ohlcv_fields"
    assert result.packet.per_symbol_result[0].missing_fields == ("adjClose",)


def test_tiingo_insufficient_history_produces_no_go() -> None:
    result = run_primary_signal_data_gate(
        _request(symbols=("SPY",)),
        environ={"TIINGO_API_KEY": "not-a-real-test-token"},
        tiingo_client=_ShortHistoryTiingoClient(),
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert result.packet.data_check_result == "insufficient_history"
    assert result.packet.per_symbol_result[0].bars_returned == 30


def test_successful_tiingo_sample_verifies_non_iex_primary_signal_data() -> None:
    result = run_primary_signal_data_gate(
        _request(),
        environ={"TIINGO_API_KEY": "not-a-real-test-token"},
        tiingo_client=_SuccessfulTiingoClient(),
        now=AS_OF,
    )

    assert result.go_no_go == "go"
    assert result.packet.configured_primary_signal_provider == "tiingo"
    assert result.packet.configured_primary_signal_feed == "eod"
    assert result.packet.configured_primary_signal_mode == "historical_completed_daily_bars"
    assert result.packet.tiingo_api_key_present is True
    assert result.packet.non_iex_primary_signal_data_verified is True
    assert result.packet.data_check_result == "verified"
    assert len(result.packet.per_symbol_result) == 5
    assert all(item.required_history_available for item in result.packet.per_symbol_result)


def test_tiingo_provider_errors_are_sanitized_no_go() -> None:
    unauthorized = run_primary_signal_data_gate(
        _request(symbols=("SPY",)),
        environ={"TIINGO_API_KEY": "not-a-real-test-token"},
        tiingo_client=_UnauthorizedTiingoClient(),
        now=AS_OF,
    )
    limited = run_primary_signal_data_gate(
        _request(symbols=("SPY",)),
        environ={"TIINGO_API_KEY": "not-a-real-test-token"},
        tiingo_client=_RateLimitedTiingoClient(),
        now=AS_OF,
    )

    assert unauthorized.go_no_go == "no_go"
    assert unauthorized.packet.data_check_result == "unauthorized"
    assert unauthorized.packet.data_check_error_class == "tiingo_http_403"
    assert limited.go_no_go == "no_go"
    assert limited.packet.data_check_result == "rate_limited"
    assert limited.packet.data_check_error_class == "tiingo_http_429"


def test_m44c_evidence_and_readiness_packets_exclude_secrets(tmp_path: Path) -> None:
    gate = run_primary_signal_data_gate(
        _request(),
        environ={"TIINGO_API_KEY": "not-a-real-test-token"},
        tiingo_client=_SuccessfulTiingoClient(),
        now=AS_OF,
    )
    gate_path = write_primary_signal_data_gate_m44c_artifact(gate, tmp_path / "gate.json")
    readiness = build_frozen_readiness_m44c_packet(
        gate.packet,
        flat_cleanup_packet_path=str(_flat_cleanup_packet(tmp_path)),
        m44_readiness_packet_path=str(_m44_readiness_packet(tmp_path)),
        m44b_gate_packet_path=PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH,
        m44c_gate_packet_path=str(gate_path),
        now=AS_OF,
    )
    readiness_path = write_frozen_readiness_m44c_artifact(readiness, tmp_path / "readiness.json")

    gate_payload = json.loads(gate_path.read_text())
    readiness_payload = json.loads(readiness_path.read_text())
    assert gate_payload["primary_signal_data_gate_m44c"]["tiingo_api_key_present"] is True
    assert gate_payload["primary_signal_data_gate_m44c"]["broker_writes_performed"] is False
    assert readiness_payload["frozen_readiness_m44c"]["m45_readiness"] is True
    assert readiness_payload["frozen_readiness_m44c"][
        "m44b_primary_signal_data_gate_packet_reference"
    ] == PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH
    assert readiness_payload["frozen_readiness_m44c"][
        "m44c_primary_signal_data_gate_packet_reference"
    ] == str(gate_path)
    combined = gate_path.read_text() + readiness_path.read_text()
    assert "TIINGO_API_KEY" not in combined
    assert "not-a-real-test-token" not in combined
    assert "ALPACA_API_KEY" not in combined


def test_m45_readiness_false_when_tiingo_gate_not_satisfied(tmp_path: Path) -> None:
    gate = run_primary_signal_data_gate(
        _request(symbols=("SPY",)),
        environ={},
        now=AS_OF,
    )
    readiness = build_frozen_readiness_m44c_packet(
        gate.packet,
        flat_cleanup_packet_path=str(_flat_cleanup_packet(tmp_path)),
        m44_readiness_packet_path=str(_m44_readiness_packet(tmp_path)),
        m44c_gate_packet_path="docs/evidence/primary_signal_data_gate_m44c.json",
        now=AS_OF,
    )

    assert readiness.go_no_go == "no_go"
    assert readiness.packet.m45_readiness is False
    assert "primary_signal_data_gate_not_satisfied" in readiness.blockers
