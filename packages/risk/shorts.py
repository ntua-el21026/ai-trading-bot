"""Paper-only short-side risk policy helpers for v0.6.

These helpers are pure validation logic. They do not submit broker orders and are intentionally
limited to paper-only broad-ETF validation policy.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.core.config import ShortsConfig
from packages.execution.models import ExecutionSide, PositionSide

ShortEligibilityReason = Literal[
    "shorts_disabled",
    "paper_environment_required",
    "symbol_not_short_eligible",
    "asset_not_tradable",
    "asset_not_marginable",
    "asset_not_shortable",
    "asset_not_easy_to_borrow",
    "account_shorting_not_enabled",
    "account_equity_below_2000",
    "fractional_short_quantity_forbidden",
    "individual_stock_short_forbidden",
    "sector_etf_short_forbidden",
    "leveraged_or_inverse_etf_short_forbidden",
    "ambiguous_broker_state",
    "opposite_side_position_present",
    "pending_entry_present",
    "unresolved_symbol_incident",
    "bearish_signal_required",
    "execution_intent_required",
    "protective_buy_stop_required",
    "short_entry_allowed",
]

_BROAD_SHORT_ETFS = frozenset({"SPY", "QQQ", "DIA", "IWM"})
_SECTOR_ETFS = frozenset({"XLK", "XLF", "XLE", "XLV"})
_LEVERAGED_OR_INVERSE_MARKERS = frozenset(
    {"TQQQ", "SQQQ", "UPRO", "SPXU", "SOXL", "SOXS", "UVXY", "SVXY"}
)


class ShortRiskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ShortAssetSnapshot(ShortRiskModel):
    symbol: str
    asset_class: Literal["equity", "etf"]
    tradable: bool | None
    marginable: bool | None
    shortable: bool | None
    easy_to_borrow: bool | None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol


class ShortAccountSnapshot(ShortRiskModel):
    environment: Literal["paper", "live"]
    equity: float = Field(gt=0)
    shorting_enabled: bool | None


class ShortEntryRiskInput(ShortRiskModel):
    symbol: str
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    asset: ShortAssetSnapshot
    account: ShortAccountSnapshot
    broker_state_ambiguous: bool
    existing_position_side: PositionSide = "flat"
    pending_entry_present: bool = False
    unresolved_symbol_incident: bool = False
    deterministic_bearish_signal: bool = False
    execution_intent_present: bool = False
    protective_buy_stop_planned: bool = False

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_symbol_consistency(self) -> Self:
        if self.symbol != self.asset.symbol:
            raise ValueError("short risk input symbol must match asset symbol")
        if self.stop_price <= self.entry_price:
            raise ValueError("short protective buy stop must be above entry price")
        return self


class ShortEntryRiskResult(ShortRiskModel):
    symbol: str
    allowed: bool
    reason_codes: tuple[ShortEligibilityReason, ...]
    broker_side: ExecutionSide = "sell"
    position_side: PositionSide = "short"
    signed_quantity: float
    protective_side: ExecutionSide = "buy"


def evaluate_short_entry_risk(
    *,
    policy: ShortsConfig,
    short_input: ShortEntryRiskInput,
) -> ShortEntryRiskResult:
    """Evaluate dormant short-entry gates without creating or submitting any order."""

    reasons: list[ShortEligibilityReason] = []
    asset = short_input.asset
    account = short_input.account

    if not policy.enabled:
        reasons.append("shorts_disabled")
    if account.environment != "paper" or not policy.paper_only_short_exposure:
        reasons.append("paper_environment_required")
    if short_input.symbol not in policy.eligible_symbols:
        reasons.append("symbol_not_short_eligible")
    if asset.tradable is not True:
        reasons.append("asset_not_tradable")
    if policy.require_marginable and asset.marginable is not True:
        reasons.append("asset_not_marginable")
    if policy.require_shortable and asset.shortable is not True:
        reasons.append("asset_not_shortable")
    if policy.require_easy_to_borrow and asset.easy_to_borrow is not True:
        reasons.append("asset_not_easy_to_borrow")
    if policy.require_account_shorting_enabled and account.shorting_enabled is not True:
        reasons.append("account_shorting_not_enabled")
    if account.equity < 2_000:
        reasons.append("account_equity_below_2000")
    if policy.require_whole_shares and not float(short_input.quantity).is_integer():
        reasons.append("fractional_short_quantity_forbidden")
    if not policy.allow_individual_stock_shorts and asset.asset_class == "equity":
        reasons.append("individual_stock_short_forbidden")
    if not policy.allow_sector_etf_shorts and short_input.symbol in _SECTOR_ETFS:
        reasons.append("sector_etf_short_forbidden")
    if (
        not policy.allow_leveraged_etf_shorts
        or not policy.allow_inverse_etf_shorts
    ) and short_input.symbol in _LEVERAGED_OR_INVERSE_MARKERS:
        reasons.append("leveraged_or_inverse_etf_short_forbidden")
    if short_input.broker_state_ambiguous:
        reasons.append("ambiguous_broker_state")
    if short_input.existing_position_side == "long":
        reasons.append("opposite_side_position_present")
    if short_input.pending_entry_present:
        reasons.append("pending_entry_present")
    if short_input.unresolved_symbol_incident:
        reasons.append("unresolved_symbol_incident")
    if not short_input.deterministic_bearish_signal:
        reasons.append("bearish_signal_required")
    if not short_input.execution_intent_present:
        reasons.append("execution_intent_required")
    if not short_input.protective_buy_stop_planned:
        reasons.append("protective_buy_stop_required")

    if not reasons and short_input.symbol in _BROAD_SHORT_ETFS:
        reasons.append("short_entry_allowed")

    allowed = reasons == ["short_entry_allowed"]
    return ShortEntryRiskResult(
        symbol=short_input.symbol,
        allowed=allowed,
        reason_codes=tuple(dict.fromkeys(reasons)),
        signed_quantity=-float(short_input.quantity),
    )
