"""Deterministic live and research universe filtering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from packages.core.config import LiveUniverseConfig, ResearchUniverseConfig
from packages.data.models import AssetMetadata, FeatureRow, UniverseBuildResult, UniverseMember

DISALLOWED_ASSET_CLASSES = {"option", "future", "crypto", "prediction_market"}


def build_live_universe(
    *,
    assets: Sequence[AssetMetadata],
    latest_features: Mapping[str, FeatureRow],
    config: LiveUniverseConfig,
    as_of: date,
) -> UniverseBuildResult:
    configured_symbols = set(config.symbols)
    members = [
        _evaluate_live_asset(
            asset,
            latest_features.get(asset.symbol),
            config,
            configured_symbols,
            as_of,
        )
        for asset in sorted(assets, key=lambda item: item.symbol)
    ]
    return UniverseBuildResult(
        universe="live",
        as_of=as_of,
        members=tuple(members),
        optimistic_backtest_warning=False,
    )


def build_research_universe(
    *,
    assets: Sequence[AssetMetadata],
    latest_features: Mapping[str, FeatureRow],
    config: ResearchUniverseConfig,
    as_of: date,
) -> UniverseBuildResult:
    members = [
        _evaluate_research_asset(asset, latest_features.get(asset.symbol), config, as_of)
        for asset in sorted(assets, key=lambda item: item.symbol)
    ]
    optimistic = any(member.optimistic_backtest_warning for member in members if member.included)
    return UniverseBuildResult(
        universe="research",
        as_of=as_of,
        members=tuple(members),
        optimistic_backtest_warning=optimistic,
    )


def _evaluate_live_asset(
    asset: AssetMetadata,
    feature: FeatureRow | None,
    config: LiveUniverseConfig,
    configured_symbols: set[str],
    as_of: date,
) -> UniverseMember:
    reasons = _base_exclusion_reasons(asset)
    if asset.symbol not in configured_symbols:
        reasons.append("not_in_approved_live_symbols")
    if asset.asset_class == "etf" and not config.allow_etfs:
        reasons.append("etfs_disabled")
    if asset.asset_class == "equity" and not config.allow_common_stocks:
        reasons.append("common_stocks_disabled")
    if asset.asset_class not in {"equity", "etf"}:
        reasons.append("live_universe_allows_equities_and_etfs_only")
    _append_price_liquidity_reasons(
        reasons,
        feature,
        min_price=config.min_price,
        min_adv20_usd=float(config.min_adv20_usd),
    )
    return UniverseMember(
        symbol=asset.symbol,
        universe="live",
        as_of=as_of,
        included=not reasons,
        exclusion_reasons=tuple(reasons),
        point_in_time_available=asset.point_in_time_available,
        optimistic_backtest_warning=False,
    )


def _evaluate_research_asset(
    asset: AssetMetadata,
    feature: FeatureRow | None,
    config: ResearchUniverseConfig,
    as_of: date,
) -> UniverseMember:
    reasons = _base_exclusion_reasons(asset)
    if asset.asset_class == "equity" and not config.include_us_common_stocks:
        reasons.append("common_stocks_disabled")
    if asset.asset_class == "etf" and not config.include_major_etfs:
        reasons.append("major_etfs_disabled")
    if asset.asset_class not in {"equity", "etf"}:
        reasons.append("research_universe_allows_equities_and_etfs_only")
    _append_price_liquidity_reasons(
        reasons,
        feature,
        min_price=config.min_price,
        min_adv20_usd=float(config.min_adv20_usd),
    )
    included = not reasons
    optimistic_warning = included and not asset.point_in_time_available
    return UniverseMember(
        symbol=asset.symbol,
        universe="research",
        as_of=as_of,
        included=included,
        exclusion_reasons=tuple(reasons),
        point_in_time_available=asset.point_in_time_available,
        optimistic_backtest_warning=optimistic_warning,
    )


def _base_exclusion_reasons(asset: AssetMetadata) -> list[str]:
    reasons: list[str] = []
    if not asset.is_active:
        reasons.append("inactive_asset")
    if not asset.is_tradable:
        reasons.append("not_tradable")
    if asset.asset_class in DISALLOWED_ASSET_CLASSES:
        reasons.append(f"disallowed_asset_class:{asset.asset_class}")
    if asset.is_leveraged_etf:
        reasons.append("leveraged_etf_excluded")
    if asset.is_inverse_etf:
        reasons.append("inverse_etf_excluded")
    return reasons


def _append_price_liquidity_reasons(
    reasons: list[str],
    feature: FeatureRow | None,
    *,
    min_price: float,
    min_adv20_usd: float,
) -> None:
    if feature is None:
        reasons.append("missing_feature_row")
        return
    if feature.close < min_price:
        reasons.append("below_min_price")
    adv20_usd = feature.adv20_usd
    if adv20_usd is None:
        reasons.append("missing_adv20_usd")
    elif adv20_usd < min_adv20_usd:
        reasons.append("below_min_adv20_usd")
