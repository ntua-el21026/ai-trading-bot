"""Milestone 44B primary signal data gate.

This module verifies or explicitly waives the v0.5 requirement that frozen-validation signal data
must not be IEX-only. It performs market-data reads only and never calls broker order endpoints,
starts schedules, or starts frozen validation.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.core.config import AppConfig, MarketDataConfig, load_app_config
from packages.data.models import AdjustedDailyBar
from packages.data.tiingo import TiingoEodProvider, TiingoEodProviderError
from packages.paper.frozen_readiness import (
    FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
    FROZEN_READINESS_M44_EVIDENCE_PATH,
    LATEST_V05_SPEC_PATH,
)

PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH = "docs/evidence/primary_signal_data_gate_m44b.json"
FROZEN_READINESS_M44B_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44b.json"
PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH = "docs/evidence/primary_signal_data_gate_m44c.json"
FROZEN_READINESS_M44C_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44c.json"
M44B_NON_IEX_DATA_GATE_WAIVER_APPROVAL = "MILESTONE_44B_NON_IEX_DATA_GATE_WAIVER"
ALPACA_MARKET_DATA_BASE_URL = "https://data.alpaca.markets"

SECRET_FIELD_NAMES = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TIINGO_API_KEY",
)

PrimarySignalMode = Literal["verify", "waive"]
PrimarySignalFeed = Literal["sip", "iex", "delayed_sip", "eod", "other"]
FeedClassification = Literal["non_iex", "iex_only", "delayed_non_iex", "unknown"]
DataCheckResult = Literal[
    "verified",
    "unavailable",
    "unauthorized",
    "missing_api_key",
    "rate_limited",
    "insufficient_history",
    "missing_ohlcv_fields",
    "provider_error",
    "inconclusive",
    "not_performed",
    "waived",
]


class PrimarySignalDataClient(Protocol):
    def latest_bars(self, *, symbols: Sequence[str], feed: str) -> Mapping[str, Any]:
        """Fetch read-only latest bar data for a feed."""


class TiingoSignalDataClient(Protocol):
    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        """Fetch read-only adjusted daily bars for a symbol."""


class PrimarySignalGateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PrimarySignalDataGateRequest(PrimarySignalGateModel):
    mode: PrimarySignalMode
    provider: str | None = None
    feed: PrimarySignalFeed | None = None
    symbols: tuple[str, ...] = ()
    operator_approval: str | None = None
    waiver_reason: str = ""
    confirm_read_only: bool = False
    confirm_no_broker_writes: bool = False
    confirm_no_schedules: bool = False
    confirm_no_frozen_validation_start: bool = False

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_optional_provider(cls, provider: object) -> object:
        if provider is None:
            return None
        return str(provider).strip().lower()

    @field_validator("feed", mode="before")
    @classmethod
    def normalize_optional_feed(cls, feed: object) -> object:
        if feed is None:
            return None
        normalized = str(feed).strip().lower().replace("-", "_")
        if normalized == "sip_delayed":
            return "delayed_sip"
        return normalized

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(symbol.strip().upper() for symbol in symbols if symbol.strip())
        if any(symbol != symbol.upper() for symbol in normalized):
            raise ValueError("data-check symbols must be uppercase")
        return normalized


class AlpacaSipDataCheck(PrimarySignalGateModel):
    performed: bool
    symbols: tuple[str, ...]
    result: DataCheckResult
    error_class: str | None = None
    sample_bar_count: int = Field(default=0, ge=0)


class TiingoSymbolDataCheckResult(PrimarySignalGateModel):
    symbol: str
    result: DataCheckResult
    bars_returned: int = Field(ge=0)
    first_date: date | None = None
    last_completed_date: date | None = None
    required_history_available: bool
    missing_fields: tuple[str, ...] = ()


class TiingoEodDataCheck(PrimarySignalGateModel):
    performed: bool
    symbols: tuple[str, ...]
    result: DataCheckResult
    error_class: str | None = None
    per_symbol_result: tuple[TiingoSymbolDataCheckResult, ...] = ()
    api_key_present: bool = False


class PrimarySignalDataGatePacket(PrimarySignalGateModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str = LATEST_V05_SPEC_PATH
    latest_spec_version: Literal["v0.5"] = "v0.5"
    mode: PrimarySignalMode
    configured_primary_signal_provider: str
    configured_primary_signal_feed: str
    configured_primary_signal_mode: str | None = None
    require_non_iex_primary_signal_data: bool
    allow_iex_only_for_frozen_validation: bool
    tiingo_api_key_present: bool | None = None
    non_iex_primary_signal_data_verified: bool
    non_iex_primary_signal_data_waived: bool
    waiver_reason: str | None = None
    validation_limitation: str | None = None
    data_check_performed: bool
    data_check_symbols: tuple[str, ...]
    data_check_result: DataCheckResult
    data_check_error_class: str | None = None
    per_symbol_result: tuple[TiingoSymbolDataCheckResult, ...] = ()
    broker_writes_performed: bool = False
    schedules_activated: bool = False
    frozen_validation_started: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    shorts_enabled: bool = False
    m45_readiness_impact: Literal["go", "no_go"]
    blockers: tuple[str, ...]


class PrimarySignalDataGateResult(PrimarySignalGateModel):
    packet: PrimarySignalDataGatePacket
    go_no_go: Literal["go", "no_go"]
    blockers: tuple[str, ...]


class FrozenReadinessM44BPacket(PrimarySignalGateModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str = LATEST_V05_SPEC_PATH
    latest_spec_version: Literal["v0.5"] = "v0.5"
    m44_flat_cleanup_packet_reference: str
    m44_frozen_readiness_packet_reference: str
    m44b_primary_signal_data_gate_packet_reference: str
    broker_baseline_source: str
    broker_baseline_rechecked: bool
    flat_start_achieved: bool
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str
    non_iex_gate_status: Literal["verified", "waived", "not_verified"]
    non_iex_primary_signal_data_verified: bool
    non_iex_primary_signal_data_waived: bool
    validation_limitation: str | None = None
    m45_readiness: bool
    blockers: tuple[str, ...]
    frozen_validation_started: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    shorts_enabled: bool = False
    level4_ready: bool = False


class FrozenReadinessM44BResult(PrimarySignalGateModel):
    packet: FrozenReadinessM44BPacket
    go_no_go: Literal["go", "no_go"]
    blockers: tuple[str, ...]


class FrozenReadinessM44CPacket(PrimarySignalGateModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str = LATEST_V05_SPEC_PATH
    latest_spec_version: Literal["v0.5"] = "v0.5"
    m44_flat_cleanup_packet_reference: str
    m44_frozen_readiness_packet_reference: str
    m44b_primary_signal_data_gate_packet_reference: str
    m44c_primary_signal_data_gate_packet_reference: str
    broker_baseline_source: str
    broker_baseline_rechecked: bool
    flat_start_achieved: bool
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str
    primary_signal_provider: str
    primary_signal_feed: str
    primary_signal_mode: str
    non_iex_gate_status: Literal["verified", "not_verified"]
    non_iex_primary_signal_data_verified: bool
    m45_readiness: bool
    blockers: tuple[str, ...]
    frozen_validation_started: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    shorts_enabled: bool = False
    level4_ready: bool = False
    operator_approval_required_for_m45: bool = True


class FrozenReadinessM44CResult(PrimarySignalGateModel):
    packet: FrozenReadinessM44CPacket
    go_no_go: Literal["go", "no_go"]
    blockers: tuple[str, ...]


class AlpacaMarketDataHttpClient:
    """Minimal read-only Alpaca market-data client for the SIP gate."""

    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        base_url: str = ALPACA_MARKET_DATA_BASE_URL,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def latest_bars(self, *, symbols: Sequence[str], feed: str) -> Mapping[str, Any]:
        params = {
            "symbols": ",".join(symbols),
            "feed": feed,
        }
        url = f"{self._base_url}/v2/stocks/bars/latest?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={
                "APCA-API-KEY-ID": self._api_key,
                "APCA-API-SECRET-KEY": self._secret_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Alpaca market-data response was not a JSON object")
        return payload


def classify_primary_signal_feed(
    feed: str,
    *,
    delayed_sip_allowed: bool = False,
) -> FeedClassification:
    normalized = normalize_primary_signal_feed(feed)
    if normalized == "sip":
        return "non_iex"
    if normalized == "eod":
        return "non_iex"
    if normalized == "iex":
        return "iex_only"
    if normalized == "delayed_sip":
        return "non_iex" if delayed_sip_allowed else "delayed_non_iex"
    return "unknown"


def normalize_primary_signal_feed(feed: str) -> PrimarySignalFeed:
    normalized = feed.strip().lower().replace("-", "_")
    if normalized == "sip_delayed":
        normalized = "delayed_sip"
    if normalized not in {"sip", "iex", "delayed_sip", "eod", "other"}:
        return "other"
    return normalized  # type: ignore[return-value]


def run_primary_signal_data_gate(
    request: PrimarySignalDataGateRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    data_client: PrimarySignalDataClient | None = None,
    tiingo_client: TiingoSignalDataClient | None = None,
    now: datetime | None = None,
) -> PrimarySignalDataGateResult:
    active_config = load_app_config() if app_config is None else app_config
    env = {} if environ is None else dict(environ)
    market_data = market_data_config_with_env_overrides(active_config.market_data, env)
    timestamp = now or datetime.now(UTC)
    provider = request.provider or market_data.primary_signal_provider
    feed = request.feed or market_data.primary_signal_feed
    symbols = request.symbols or _default_data_check_symbols(active_config, provider, market_data)
    blockers: list[str] = []

    blockers.extend(_confirmation_blockers(request))
    blockers.extend(_app_safety_blockers(active_config))
    if provider != market_data.primary_signal_provider:
        blockers.append("requested_provider_does_not_match_market_data_config")
    if feed != market_data.primary_signal_feed:
        blockers.append("requested_feed_does_not_match_market_data_config")
    if not market_data.require_non_iex_primary_signal_data:
        blockers.append("non_iex_primary_signal_data_not_required_by_config")
    if market_data.allow_iex_only_for_frozen_validation and request.mode != "waive":
        blockers.append("iex_only_allowed_without_waiver_mode")

    verified = False
    waived = False
    validation_limitation: str | None = None
    data_check: AlpacaSipDataCheck | TiingoEodDataCheck = AlpacaSipDataCheck(
        performed=False,
        symbols=symbols,
        result="not_performed",
    )

    if request.mode == "waive":
        waiver_blockers = _waiver_blockers(request)
        blockers.extend(waiver_blockers)
        if not waiver_blockers:
            waived = True
            validation_limitation = (
                "M45 may start only as operational paper validation with market-data "
                "limitations; strategy-performance conclusions are limited."
            )
            data_check = AlpacaSipDataCheck(
                performed=False,
                symbols=symbols,
                result="waived",
            )
    else:
        feed_classification = classify_primary_signal_feed(
            feed,
            delayed_sip_allowed=market_data.allow_delayed_sip_for_signal_generation,
        )
        blockers.extend(_feed_classification_blockers(feed, feed_classification, provider=provider))
        if not blockers and provider == "alpaca" and feed == "sip":
            data_check = _run_alpaca_sip_data_check(
                symbols=symbols,
                feed=feed,
                environ=env,
                data_client=data_client,
            )
            if data_check.result == "verified":
                verified = True
            else:
                blockers.append("non_iex_primary_signal_data_not_verified")
        elif not blockers and provider == "tiingo" and feed == "eod":
            data_check = _run_tiingo_eod_data_check(
                symbols=symbols,
                environ=env,
                market_data=market_data,
                tiingo_client=tiingo_client,
                now=timestamp,
            )
            if data_check.result == "verified":
                verified = True
            else:
                blockers.append("non_iex_primary_signal_data_not_verified")
        elif provider not in {"alpaca", "tiingo"}:
            blockers.append("primary_signal_provider_not_verifiable")
        elif provider == "alpaca" and feed != "sip":
            blockers.append("primary_signal_feed_not_verified_as_real_time_sip")
        elif provider == "tiingo" and feed != "eod":
            blockers.append("primary_signal_feed_not_verified_as_tiingo_eod")

    unique_blockers = _unique(tuple(blockers))
    go = (verified or waived) and not unique_blockers
    packet = PrimarySignalDataGatePacket(
        packet_id=str(uuid5(NAMESPACE_URL, f"m44b-primary-signal:{timestamp.isoformat()}")),
        timestamp=timestamp,
        mode=request.mode,
        configured_primary_signal_provider=market_data.primary_signal_provider,
        configured_primary_signal_feed=market_data.primary_signal_feed,
        configured_primary_signal_mode=market_data.primary_signal_mode,
        require_non_iex_primary_signal_data=market_data.require_non_iex_primary_signal_data,
        allow_iex_only_for_frozen_validation=(
            market_data.allow_iex_only_for_frozen_validation
        ),
        tiingo_api_key_present=(
            data_check.api_key_present if isinstance(data_check, TiingoEodDataCheck) else None
        ),
        non_iex_primary_signal_data_verified=verified,
        non_iex_primary_signal_data_waived=waived,
        waiver_reason=request.waiver_reason.strip() if waived else None,
        validation_limitation=validation_limitation,
        data_check_performed=data_check.performed,
        data_check_symbols=data_check.symbols,
        data_check_result=data_check.result,
        data_check_error_class=data_check.error_class,
        per_symbol_result=(
            data_check.per_symbol_result if isinstance(data_check, TiingoEodDataCheck) else ()
        ),
        live_trading_enabled=active_config.system.live_trading_enabled,
        autonomous_live_execution_enabled=active_config.system.autonomous_execution_enabled,
        leverage_enabled=active_config.risk_level_4_micro_live.allow_margin,
        shorts_enabled=active_config.shorts.enabled,
        m45_readiness_impact="go" if go else "no_go",
        blockers=unique_blockers,
    )
    return PrimarySignalDataGateResult(
        packet=packet,
        go_no_go="go" if go else "no_go",
        blockers=unique_blockers,
    )


def build_frozen_readiness_m44b_packet(
    gate_packet: PrimarySignalDataGatePacket,
    *,
    flat_cleanup_packet_path: str = FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
    m44_readiness_packet_path: str = FROZEN_READINESS_M44_EVIDENCE_PATH,
    gate_packet_path: str = PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH,
    app_config: AppConfig | None = None,
    now: datetime | None = None,
) -> FrozenReadinessM44BResult:
    active_config = load_app_config() if app_config is None else app_config
    timestamp = now or datetime.now(UTC)
    flat_payload = _load_json_mapping(Path(flat_cleanup_packet_path))
    m44_payload = _load_json_mapping(Path(m44_readiness_packet_path))
    cleanup = flat_payload.get("flat_start_cleanup")
    flat_achieved = False
    open_orders_count = 0
    positions_count = 0
    reconciliation = "flat_cleanup_packet_missing_or_invalid"
    blockers: list[str] = []

    if isinstance(cleanup, Mapping):
        open_orders_count = int(cleanup.get("final_open_orders_count") or 0)
        positions_count = int(cleanup.get("final_positions_count") or 0)
        reconciliation = str(cleanup.get("final_reconciliation") or "unknown")
        flat_achieved = (
            bool(cleanup.get("m45_flat_start_ready"))
            and open_orders_count == 0
            and positions_count == 0
            and reconciliation == "flat_zero_positions_zero_open_orders"
            and not tuple(cleanup.get("blockers", ()))
        )
    if not flat_achieved:
        blockers.append("flat_broker_baseline_not_achieved")
    if not isinstance(m44_payload.get("frozen_readiness"), Mapping):
        blockers.append("m44_frozen_readiness_packet_missing_or_invalid")

    blockers.extend(gate_packet.blockers)
    blockers.extend(_app_safety_blockers(active_config))
    gate_go = gate_packet.m45_readiness_impact == "go"
    if not gate_go:
        blockers.append("primary_signal_data_gate_not_satisfied")
    blockers = list(_unique(tuple(blockers)))
    non_iex_status: Literal["verified", "waived", "not_verified"] = "not_verified"
    if gate_packet.non_iex_primary_signal_data_verified:
        non_iex_status = "verified"
    elif gate_packet.non_iex_primary_signal_data_waived:
        non_iex_status = "waived"

    m45_ready = flat_achieved and gate_go and not blockers
    packet = FrozenReadinessM44BPacket(
        packet_id=str(uuid5(NAMESPACE_URL, f"m44b-readiness:{timestamp.isoformat()}")),
        timestamp=timestamp,
        m44_flat_cleanup_packet_reference=flat_cleanup_packet_path,
        m44_frozen_readiness_packet_reference=m44_readiness_packet_path,
        m44b_primary_signal_data_gate_packet_reference=gate_packet_path,
        broker_baseline_source="m44_flat_start_cleanup_packet",
        broker_baseline_rechecked=False,
        flat_start_achieved=flat_achieved,
        open_orders_count=open_orders_count,
        positions_count=positions_count,
        reconciliation_summary=reconciliation,
        non_iex_gate_status=non_iex_status,
        non_iex_primary_signal_data_verified=gate_packet.non_iex_primary_signal_data_verified,
        non_iex_primary_signal_data_waived=gate_packet.non_iex_primary_signal_data_waived,
        validation_limitation=gate_packet.validation_limitation,
        m45_readiness=m45_ready,
        blockers=tuple(blockers),
        live_trading_enabled=active_config.system.live_trading_enabled,
        autonomous_live_execution_enabled=active_config.system.autonomous_execution_enabled,
        leverage_enabled=active_config.risk_level_4_micro_live.allow_margin,
        shorts_enabled=active_config.shorts.enabled,
    )
    return FrozenReadinessM44BResult(
        packet=packet,
        go_no_go="go" if m45_ready else "no_go",
        blockers=packet.blockers,
    )


def build_frozen_readiness_m44c_packet(
    gate_packet: PrimarySignalDataGatePacket,
    *,
    flat_cleanup_packet_path: str = FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
    m44_readiness_packet_path: str = FROZEN_READINESS_M44_EVIDENCE_PATH,
    m44b_gate_packet_path: str = PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH,
    m44c_gate_packet_path: str = PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH,
    app_config: AppConfig | None = None,
    now: datetime | None = None,
) -> FrozenReadinessM44CResult:
    active_config = load_app_config() if app_config is None else app_config
    timestamp = now or datetime.now(UTC)
    flat_payload = _load_json_mapping(Path(flat_cleanup_packet_path))
    m44_payload = _load_json_mapping(Path(m44_readiness_packet_path))
    cleanup = flat_payload.get("flat_start_cleanup")
    frozen_readiness = m44_payload.get("frozen_readiness")
    flat_achieved = False
    open_orders_count = 0
    positions_count = 0
    reconciliation = "flat_cleanup_packet_missing_or_invalid"
    blockers: list[str] = []

    if isinstance(cleanup, Mapping):
        open_orders_count = int(cleanup.get("final_open_orders_count") or 0)
        positions_count = int(cleanup.get("final_positions_count") or 0)
        reconciliation = str(cleanup.get("final_reconciliation") or "unknown")
        flat_achieved = (
            bool(cleanup.get("m45_flat_start_ready"))
            and open_orders_count == 0
            and positions_count == 0
            and reconciliation == "flat_zero_positions_zero_open_orders"
            and not tuple(cleanup.get("blockers", ()))
        )
    if not flat_achieved:
        blockers.append("flat_broker_baseline_not_achieved")
    if isinstance(frozen_readiness, Mapping):
        unresolved_m44_blockers = tuple(
            blocker
            for blocker in frozen_readiness.get("blockers", ())
            if blocker != "non_iex_primary_signal_data_not_verified"
        )
        blockers.extend(str(blocker) for blocker in unresolved_m44_blockers)
    else:
        blockers.append("m44_frozen_readiness_packet_missing_or_invalid")

    blockers.extend(gate_packet.blockers)
    blockers.extend(_app_safety_blockers(active_config))
    gate_go = (
        gate_packet.m45_readiness_impact == "go"
        and gate_packet.non_iex_primary_signal_data_verified
    )
    if not gate_go:
        blockers.append("primary_signal_data_gate_not_satisfied")
    blockers = list(_unique(tuple(blockers)))
    m45_ready = flat_achieved and gate_go and not blockers
    packet = FrozenReadinessM44CPacket(
        packet_id=str(uuid5(NAMESPACE_URL, f"m44c-readiness:{timestamp.isoformat()}")),
        timestamp=timestamp,
        m44_flat_cleanup_packet_reference=flat_cleanup_packet_path,
        m44_frozen_readiness_packet_reference=m44_readiness_packet_path,
        m44b_primary_signal_data_gate_packet_reference=m44b_gate_packet_path,
        m44c_primary_signal_data_gate_packet_reference=m44c_gate_packet_path,
        broker_baseline_source="m44_flat_start_cleanup_packet",
        broker_baseline_rechecked=False,
        flat_start_achieved=flat_achieved,
        open_orders_count=open_orders_count,
        positions_count=positions_count,
        reconciliation_summary=reconciliation,
        primary_signal_provider=gate_packet.configured_primary_signal_provider,
        primary_signal_feed=gate_packet.configured_primary_signal_feed,
        primary_signal_mode=gate_packet.configured_primary_signal_mode or "unknown",
        non_iex_gate_status="verified" if gate_go else "not_verified",
        non_iex_primary_signal_data_verified=gate_packet.non_iex_primary_signal_data_verified,
        m45_readiness=m45_ready,
        blockers=tuple(blockers),
        live_trading_enabled=active_config.system.live_trading_enabled,
        autonomous_live_execution_enabled=active_config.system.autonomous_execution_enabled,
        leverage_enabled=active_config.risk_level_4_micro_live.allow_margin,
        shorts_enabled=active_config.shorts.enabled,
    )
    return FrozenReadinessM44CResult(
        packet=packet,
        go_no_go="go" if m45_ready else "no_go",
        blockers=packet.blockers,
    )


def write_primary_signal_data_gate_artifact(
    result: PrimarySignalDataGateResult,
    output_path: str | Path = PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "44B",
        "primary_signal_data_gate": result.packet.model_dump(mode="json"),
        "result": {
            "go_no_go": result.go_no_go,
            "blockers": list(result.blockers),
            "non_iex_primary_signal_data_verified": (
                result.packet.non_iex_primary_signal_data_verified
            ),
            "non_iex_primary_signal_data_waived": (
                result.packet.non_iex_primary_signal_data_waived
            ),
            "broker_writes_performed": False,
            "schedules_activated": False,
            "frozen_validation_started": False,
        },
    }
    _assert_no_secret_markers(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_primary_signal_data_gate_m44c_artifact(
    result: PrimarySignalDataGateResult,
    output_path: str | Path = PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "44C",
        "primary_signal_data_gate_m44c": result.packet.model_dump(mode="json"),
        "result": {
            "go_no_go": result.go_no_go,
            "blockers": list(result.blockers),
            "non_iex_primary_signal_data_verified": (
                result.packet.non_iex_primary_signal_data_verified
            ),
            "broker_writes_performed": False,
            "schedules_activated": False,
            "frozen_validation_started": False,
        },
    }
    _assert_no_secret_markers(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_frozen_readiness_m44b_artifact(
    result: FrozenReadinessM44BResult,
    output_path: str | Path = FROZEN_READINESS_M44B_EVIDENCE_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "44B",
        "frozen_readiness_m44b": result.packet.model_dump(mode="json"),
        "result": {
            "go_no_go": result.go_no_go,
            "m45_readiness": result.packet.m45_readiness,
            "blockers": list(result.blockers),
            "frozen_validation_started": False,
            "schedules_activated": False,
        },
    }
    _assert_no_secret_markers(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_frozen_readiness_m44c_artifact(
    result: FrozenReadinessM44CResult,
    output_path: str | Path = FROZEN_READINESS_M44C_EVIDENCE_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "44C",
        "frozen_readiness_m44c": result.packet.model_dump(mode="json"),
        "result": {
            "go_no_go": result.go_no_go,
            "m45_readiness": result.packet.m45_readiness,
            "blockers": list(result.blockers),
            "frozen_validation_started": False,
            "schedules_activated": False,
        },
    }
    _assert_no_secret_markers(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def market_data_config_with_env_overrides(
    config: MarketDataConfig,
    environ: Mapping[str, str],
) -> MarketDataConfig:
    data = config.model_dump()
    mapping = {
        "MARKET_DATA_PRIMARY_PROVIDER": "primary_signal_provider",
        "MARKET_DATA_PRIMARY_FEED": "primary_signal_feed",
        "MARKET_DATA_PRIMARY_SIGNAL_MODE": "primary_signal_mode",
        "MARKET_DATA_NON_IEX_WAIVER_REASON": "non_iex_primary_signal_data_waiver_reason",
    }
    bool_mapping = {
        "MARKET_DATA_REQUIRE_NON_IEX": "require_non_iex_primary_signal_data",
        "MARKET_DATA_FAIL_IF_PRIMARY_SIGNAL_FEED_IS_IEX": "fail_if_primary_signal_feed_is_iex",
        "MARKET_DATA_ALLOW_IEX_ONLY_FOR_FROZEN_VALIDATION": (
            "allow_iex_only_for_frozen_validation"
        ),
        "MARKET_DATA_ALLOW_DELAYED_SIP_FOR_SIGNAL_GENERATION": (
            "allow_delayed_sip_for_signal_generation"
        ),
        "MARKET_DATA_NON_IEX_WAIVER_ENABLED": "non_iex_primary_signal_data_waiver_enabled",
    }
    for env_name, field_name in mapping.items():
        if env_name in environ:
            data[field_name] = environ[env_name]
    for env_name, field_name in bool_mapping.items():
        if env_name in environ:
            data[field_name] = _env_bool(environ[env_name])
    return MarketDataConfig.model_validate(data)


def build_alpaca_market_data_client_from_env(
    environ: Mapping[str, str],
) -> AlpacaMarketDataHttpClient | None:
    api_key = environ.get("ALPACA_API_KEY", "").strip()
    secret_key = environ.get("ALPACA_SECRET_KEY", "").strip()
    if not api_key or not secret_key:
        return None
    base_url = environ.get("ALPACA_MARKET_DATA_BASE_URL", ALPACA_MARKET_DATA_BASE_URL).strip()
    if not base_url:
        base_url = ALPACA_MARKET_DATA_BASE_URL
    return AlpacaMarketDataHttpClient(
        api_key=api_key,
        secret_key=secret_key,
        base_url=base_url,
    )


def build_tiingo_eod_client_from_env(
    environ: Mapping[str, str],
    config: MarketDataConfig,
) -> TiingoEodProvider | None:
    tiingo_config = config.tiingo
    if tiingo_config is None or not tiingo_config.enabled:
        return None
    api_key = environ.get(tiingo_config.api_key_env, "").strip()
    if not api_key:
        return None
    return TiingoEodProvider(
        api_key=api_key,
        base_url=tiingo_config.base_url,
        endpoint_template=tiingo_config.eod_endpoint_template,
        adjusted_prices_required=tiingo_config.adjusted_prices_required,
        completed_daily_bars_only=tiingo_config.completed_daily_bars_only,
    )


def _run_alpaca_sip_data_check(
    *,
    symbols: tuple[str, ...],
    feed: str,
    environ: Mapping[str, str],
    data_client: PrimarySignalDataClient | None,
) -> AlpacaSipDataCheck:
    client = data_client or build_alpaca_market_data_client_from_env(environ)
    if client is None:
        return AlpacaSipDataCheck(
            performed=False,
            symbols=symbols,
            result="unavailable",
            error_class="alpaca_market_data_credentials_unavailable",
        )
    try:
        payload = client.latest_bars(symbols=symbols, feed=feed)
    except urllib.error.HTTPError as exc:
        return AlpacaSipDataCheck(
            performed=True,
            symbols=symbols,
            result="unauthorized" if exc.code in {401, 403} else "unavailable",
            error_class=f"alpaca_market_data_http_{exc.code}",
        )
    except urllib.error.URLError:
        return AlpacaSipDataCheck(
            performed=True,
            symbols=symbols,
            result="unavailable",
            error_class="alpaca_market_data_network_error",
        )
    except Exception as exc:
        return AlpacaSipDataCheck(
            performed=True,
            symbols=symbols,
            result="inconclusive",
            error_class=f"alpaca_market_data_{type(exc).__name__}",
        )
    sample_count = _count_latest_bar_payload(payload, symbols)
    return AlpacaSipDataCheck(
        performed=True,
        symbols=symbols,
        result="verified" if sample_count > 0 else "inconclusive",
        error_class=None if sample_count > 0 else "alpaca_market_data_empty_payload",
        sample_bar_count=sample_count,
    )


def _run_tiingo_eod_data_check(
    *,
    symbols: tuple[str, ...],
    environ: Mapping[str, str],
    market_data: MarketDataConfig,
    tiingo_client: TiingoSignalDataClient | None,
    now: datetime,
) -> TiingoEodDataCheck:
    tiingo_config = market_data.tiingo
    if tiingo_config is None or not tiingo_config.enabled:
        return TiingoEodDataCheck(
            performed=False,
            symbols=symbols,
            result="unavailable",
            error_class="tiingo_config_unavailable",
            api_key_present=False,
        )
    api_key_present = bool(environ.get(tiingo_config.api_key_env, "").strip())
    client = tiingo_client or build_tiingo_eod_client_from_env(environ, market_data)
    if client is None:
        error_class = (
            "tiingo_api_key_missing" if not api_key_present else "tiingo_client_unavailable"
        )
        return TiingoEodDataCheck(
            performed=False,
            symbols=symbols,
            result="missing_api_key" if not api_key_present else "unavailable",
            error_class=error_class,
            api_key_present=api_key_present,
        )

    end = (now - timedelta(days=1)).date()
    start = end - timedelta(days=430)
    per_symbol: list[TiingoSymbolDataCheckResult] = []
    aggregate_result: DataCheckResult = "verified"
    aggregate_error: str | None = None
    for symbol in symbols:
        try:
            bars = tuple(client.adjusted_daily_bars(symbol, start, end))
        except TiingoEodProviderError as exc:
            per_symbol.append(
                TiingoSymbolDataCheckResult(
                    symbol=symbol,
                    result=exc.result,
                    bars_returned=0,
                    required_history_available=False,
                    missing_fields=_missing_fields_from_tiingo_error(exc.error_class),
                )
            )
            aggregate_result = _worse_data_check_result(aggregate_result, exc.result)
            aggregate_error = aggregate_error or exc.error_class
            continue
        except Exception as exc:
            per_symbol.append(
                TiingoSymbolDataCheckResult(
                    symbol=symbol,
                    result="provider_error",
                    bars_returned=0,
                    required_history_available=False,
                )
            )
            aggregate_result = _worse_data_check_result(aggregate_result, "provider_error")
            aggregate_error = aggregate_error or f"tiingo_{type(exc).__name__}"
            continue

        missing_fields = _missing_adjusted_bar_fields(bars)
        history_ok = len(bars) >= tiingo_config.min_history_bars
        if missing_fields:
            symbol_result: DataCheckResult = "missing_ohlcv_fields"
        elif not history_ok:
            symbol_result = "insufficient_history"
        else:
            symbol_result = "verified"
        per_symbol.append(
            TiingoSymbolDataCheckResult(
                symbol=symbol,
                result=symbol_result,
                bars_returned=len(bars),
                first_date=bars[0].date if bars else None,
                last_completed_date=bars[-1].date if bars else None,
                required_history_available=history_ok and not missing_fields,
                missing_fields=missing_fields,
            )
        )
        aggregate_result = _worse_data_check_result(aggregate_result, symbol_result)

    if aggregate_result != "verified" and aggregate_error is None:
        aggregate_error = f"tiingo_{aggregate_result}"
    return TiingoEodDataCheck(
        performed=True,
        symbols=symbols,
        result=aggregate_result,
        error_class=aggregate_error,
        per_symbol_result=tuple(per_symbol),
        api_key_present=api_key_present,
    )


def _count_latest_bar_payload(payload: Mapping[str, Any], symbols: Sequence[str]) -> int:
    bars = payload.get("bars")
    if not isinstance(bars, Mapping):
        return 0
    count = 0
    for symbol in symbols:
        item = bars.get(symbol)
        if isinstance(item, Mapping) and item:
            count += 1
    return count


def _default_data_check_symbols(
    app_config: AppConfig,
    provider: str,
    market_data: MarketDataConfig,
) -> tuple[str, ...]:
    if provider == "tiingo" and market_data.tiingo is not None:
        return market_data.tiingo.validation_sample_symbols
    return tuple(app_config.live_universe.symbols[:1])


def _missing_adjusted_bar_fields(bars: Sequence[AdjustedDailyBar]) -> tuple[str, ...]:
    if not bars:
        return ("date", "open", "high", "low", "close", "volume")
    missing: set[str] = set()
    for bar in bars:
        if bar.date is None:
            missing.add("date")
        if bar.open <= 0:
            missing.add("open")
        if bar.high <= 0:
            missing.add("high")
        if bar.low <= 0:
            missing.add("low")
        if bar.close <= 0:
            missing.add("close")
        if bar.volume < 0:
            missing.add("volume")
    return tuple(sorted(missing))


def _missing_fields_from_tiingo_error(error_class: str) -> tuple[str, ...]:
    prefix = "tiingo_missing_fields_"
    if not error_class.startswith(prefix):
        return ()
    raw = error_class.removeprefix(prefix)
    return tuple(part for part in raw.split("_") if part)


def _worse_data_check_result(
    current: DataCheckResult,
    candidate: DataCheckResult,
) -> DataCheckResult:
    priority = {
        "verified": 0,
        "waived": 0,
        "not_performed": 1,
        "inconclusive": 2,
        "unavailable": 3,
        "insufficient_history": 4,
        "missing_ohlcv_fields": 5,
        "missing_api_key": 6,
        "rate_limited": 7,
        "provider_error": 8,
        "unauthorized": 9,
    }
    return candidate if priority[candidate] > priority[current] else current


def _confirmation_blockers(request: PrimarySignalDataGateRequest) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.mode == "verify" and not request.confirm_read_only:
        blockers.append("confirm_read_only_missing")
    if not request.confirm_no_broker_writes:
        blockers.append("confirm_no_broker_writes_missing")
    if not request.confirm_no_schedules:
        blockers.append("confirm_no_schedules_missing")
    if not request.confirm_no_frozen_validation_start:
        blockers.append("confirm_no_frozen_validation_start_missing")
    return tuple(blockers)


def _app_safety_blockers(app_config: AppConfig) -> tuple[str, ...]:
    blockers: list[str] = []
    if app_config.system.live_trading_enabled or app_config.validation.live_trading_enabled:
        blockers.append("live_trading_enabled")
    if (
        app_config.system.autonomous_execution_enabled
        or app_config.validation.autonomous_live_execution_enabled
        or app_config.execution.autonomous_execution_enabled
    ):
        blockers.append("autonomous_live_execution_enabled")
    if app_config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_enabled")
    if app_config.shorts.enabled:
        blockers.append("shorts_enabled")
    if (
        app_config.validation.validation_clock_started
        or app_config.validation.frozen_validation_enabled
    ):
        blockers.append("frozen_validation_started_or_enabled")
    return tuple(blockers)


def _waiver_blockers(request: PrimarySignalDataGateRequest) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval != M44B_NON_IEX_DATA_GATE_WAIVER_APPROVAL:
        blockers.append("waiver_approval_missing")
    if not request.waiver_reason.strip():
        blockers.append("waiver_reason_missing")
    return tuple(blockers)


def _feed_classification_blockers(
    feed: str,
    classification: FeedClassification,
    *,
    provider: str,
) -> tuple[str, ...]:
    if classification == "iex_only":
        return ("primary_signal_feed_is_iex",)
    if classification == "delayed_non_iex":
        return ("delayed_sip_not_allowed_for_frozen_validation",)
    if classification == "unknown":
        return ("primary_signal_feed_classification_unknown",)
    if provider == "tiingo" and feed == "eod":
        return ()
    if feed != "sip":
        return ("primary_signal_feed_not_verified_as_real_time_sip",)
    return ()


def _load_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _env_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def _assert_no_secret_markers(payload: Mapping[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    if any(token in text for token in SECRET_FIELD_NAMES):
        raise ValueError("M44B evidence payload contains a sensitive token name")


def utc_timestamp_for_cli() -> str:
    return datetime.now(UTC).isoformat()


def sleep_briefly_for_dashboard_visibility() -> None:
    """Tiny no-op helper kept for future explicit read-only smoke pacing."""

    time.sleep(0)
