"""Typed data-domain models for daily market data and derived features."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AssetClass = Literal[
    "equity",
    "etf",
    "option",
    "future",
    "crypto",
    "prediction_market",
    "other",
]
UniverseKind = Literal["live", "research"]


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AdjustedDailyBar(DataModel):
    symbol: str
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)
    adjusted: bool = True
    provider: str | None = None
    payload_hash: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_ohlc(self) -> Self:
        if self.low > self.high:
            raise ValueError("low cannot exceed high")
        if self.open > self.high or self.open < self.low:
            raise ValueError("open must be inside high/low range")
        if self.close > self.high or self.close < self.low:
            raise ValueError("close must be inside high/low range")
        return self


class QuoteSnapshot(DataModel):
    symbol: str
    as_of: datetime
    bid_price: float | None = Field(default=None, gt=0)
    ask_price: float | None = Field(default=None, gt=0)
    last_price: float | None = Field(default=None, gt=0)
    bid_size: int | None = Field(default=None, ge=0)
    ask_size: int | None = Field(default=None, ge=0)
    provider: str | None = None
    payload_hash: str | None = None


class AssetMetadata(DataModel):
    symbol: str
    asset_class: AssetClass
    name: str | None = None
    exchange: str | None = None
    sector: str | None = None
    is_active: bool = True
    is_tradable: bool = True
    is_leveraged_etf: bool = False
    is_inverse_etf: bool = False
    metadata_as_of: date | None = None
    point_in_time_available: bool = False
    provider: str | None = None
    payload_hash: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol


class RawProviderPayload(DataModel):
    provider: str
    endpoint: str
    fetched_at: datetime
    payload_hash: str
    payload_size_bytes: int = Field(ge=0)
    raw_payload: str
    symbol: str | None = None
    content_type: str = "application/json"


class FeatureRow(DataModel):
    symbol: str
    date: date
    close: float = Field(gt=0)
    return_1d: float | None = None
    sma_50: float | None = Field(default=None, gt=0)
    sma_200: float | None = Field(default=None, gt=0)
    ema_10: float | None = Field(default=None, gt=0)
    atr_14: float | None = Field(default=None, ge=0)
    atr_percent: float | None = Field(default=None, ge=0)
    volume_sma_20: float | None = Field(default=None, ge=0)
    volume_ratio_20: float | None = Field(default=None, ge=0)
    high_20: float | None = Field(default=None, gt=0)
    high_55: float | None = Field(default=None, gt=0)
    dollar_volume: float = Field(ge=0)
    rs_63: float | None = None
    source_bar_payload_hash: str | None = None

    @property
    def adv20_usd(self) -> float | None:
        if self.volume_sma_20 is None:
            return None
        return self.close * self.volume_sma_20


class UniverseMember(DataModel):
    symbol: str
    universe: UniverseKind
    as_of: date
    included: bool
    exclusion_reasons: tuple[str, ...] = ()
    point_in_time_available: bool
    optimistic_backtest_warning: bool


class UniverseBuildResult(DataModel):
    universe: UniverseKind
    as_of: date
    members: tuple[UniverseMember, ...]
    optimistic_backtest_warning: bool

    @property
    def included_symbols(self) -> tuple[str, ...]:
        return tuple(member.symbol for member in self.members if member.included)

