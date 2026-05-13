"""Deterministic long-only candidate and signal generation."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date
from typing import cast

from packages.core.config import LiveUniverseConfig, ResearchUniverseConfig, StrategyConfig
from packages.data.models import FeatureRow, UniverseMember
from packages.strategy.models import (
    BreakoutLookback,
    CandidateEvaluation,
    EarningsBlackoutEvaluation,
    RegimeClassification,
    RegimeState,
    StrategyMode,
)
from packages.strategy.scoring import relative_strength_score, technical_score


def evaluate_earnings_blackout(
    *,
    as_of: date,
    earnings_date: date | None,
    trading_calendar: Sequence[date],
    block_entries_before_trading_sessions: int = 2,
    block_entries_after_trading_sessions: int = 1,
    allow_exits_during_blackout: bool = True,
) -> EarningsBlackoutEvaluation:
    if block_entries_before_trading_sessions < 0:
        raise ValueError("block_entries_before_trading_sessions cannot be negative")
    if block_entries_after_trading_sessions < 0:
        raise ValueError("block_entries_after_trading_sessions cannot be negative")
    if earnings_date is None:
        return EarningsBlackoutEvaluation(
            status="unknown",
            as_of=as_of,
            earnings_date=None,
            allow_entries=False,
            allow_exits=allow_exits_during_blackout,
            reason_codes=("earnings_date_unknown",),
        )

    sorted_calendar = tuple(sorted(set(trading_calendar)))
    try:
        as_of_index = sorted_calendar.index(as_of)
        earnings_index = sorted_calendar.index(earnings_date)
    except ValueError:
        return EarningsBlackoutEvaluation(
            status="unknown",
            as_of=as_of,
            earnings_date=earnings_date,
            allow_entries=False,
            allow_exits=allow_exits_during_blackout,
            reason_codes=("earnings_calendar_missing_session",),
        )

    window_start = earnings_index - block_entries_before_trading_sessions
    window_end = earnings_index + block_entries_after_trading_sessions
    if window_start <= as_of_index <= window_end:
        return EarningsBlackoutEvaluation(
            status="blackout",
            as_of=as_of,
            earnings_date=earnings_date,
            allow_entries=False,
            allow_exits=allow_exits_during_blackout,
            reason_codes=("earnings_blackout_active",),
        )

    return EarningsBlackoutEvaluation(
        status="clear",
        as_of=as_of,
        earnings_date=earnings_date,
        allow_entries=True,
        allow_exits=allow_exits_during_blackout,
        reason_codes=("earnings_blackout_clear",),
    )


def evaluate_candidate(
    feature: FeatureRow,
    *,
    universe_member: UniverseMember,
    strategy_config: StrategyConfig,
    live_universe_config: LiveUniverseConfig | None = None,
    research_universe_config: ResearchUniverseConfig | None = None,
    regime: RegimeClassification | RegimeState,
    earnings: EarningsBlackoutEvaluation,
    prior_high_20: float | None,
    prior_high_55: float | None = None,
    rs_percentile: float | None = None,
    currently_held_symbols: Collection[str] = (),
    scale_in_candidate_symbols: Collection[str] = (),
    active_intent_symbols: Collection[str] = (),
    breakout_lookback: BreakoutLookback | None = None,
) -> CandidateEvaluation:
    """Evaluate one feature row into an accepted/rejected long-only candidate record."""

    mode = universe_member.universe
    if feature.symbol != universe_member.symbol:
        raise ValueError("feature and universe member symbols must match")
    rejection_reasons: list[str] = []
    reason_codes: list[str] = ["side:long"]

    _append_universe_rejections(rejection_reasons, universe_member)
    _append_regime_rejections(rejection_reasons, reason_codes, regime)
    _append_price_liquidity_rejections(
        rejection_reasons,
        feature,
        mode=mode,
        live_universe_config=live_universe_config,
        research_universe_config=research_universe_config,
    )
    _append_feature_rejections(rejection_reasons, feature)

    if (
        feature.symbol in currently_held_symbols
        and feature.symbol not in scale_in_candidate_symbols
    ):
        rejection_reasons.append("symbol_already_held")
    elif feature.symbol in currently_held_symbols:
        reason_codes.append("held_symbol_scale_in_signal_evaluation")
    if feature.symbol in active_intent_symbols:
        rejection_reasons.append("active_duplicate_intent")
    if not earnings.allow_entries:
        rejection_reasons.append(f"earnings_{earnings.status}")

    trend_passed = (
        feature.sma_50 is not None
        and feature.sma_200 is not None
        and feature.close > feature.sma_50
        and feature.sma_50 > feature.sma_200
    )
    if not trend_passed:
        rejection_reasons.append("trend_filter_failed")
    else:
        reason_codes.append("trend_filter_passed")

    selected_breakout = _select_breakout(
        feature=feature,
        strategy_config=strategy_config,
        mode=mode,
        prior_high_20=prior_high_20,
        prior_high_55=prior_high_55,
        breakout_lookback=breakout_lookback,
    )
    breakout_passed = selected_breakout is not None
    if selected_breakout is None:
        rejection_reasons.append("breakout_filter_failed")
        breakout_level = None
        selected_lookback = None
    else:
        selected_lookback, breakout_level = selected_breakout
        reason_codes.append(f"breakout_{selected_lookback}_passed")

    volume_passed = (
        feature.volume_ratio_20 is not None
        and feature.volume_ratio_20 >= strategy_config.volume_ratio_min
    )
    if not volume_passed:
        rejection_reasons.append("volume_ratio_filter_failed")
    else:
        reason_codes.append("volume_ratio_filter_passed")

    rs_passed = feature.rs_63 is not None and feature.rs_63 > strategy_config.relative_strength_min
    if not rs_passed:
        rejection_reasons.append("rs63_filter_failed")
    else:
        reason_codes.append("rs63_filter_passed")

    if mode == "research" and rs_percentile is not None:
        if rs_percentile < strategy_config.relative_strength_percentile_floor_research:
            rejection_reasons.append("rs_percentile_filter_failed")
        else:
            reason_codes.append("rs_percentile_filter_passed")
    elif mode == "research":
        reason_codes.append("rs_percentile_unavailable")

    atr_pct = _atr_percent(feature)
    volatility_passed = (
        atr_pct is not None
        and strategy_config.atr_pct_min <= atr_pct <= strategy_config.atr_pct_max
    )
    if not volatility_passed:
        rejection_reasons.append("atr_percent_filter_failed")
    else:
        reason_codes.append("atr_percent_filter_passed")

    deduped_rejections = tuple(dict.fromkeys(rejection_reasons))
    accepted = not deduped_rejections
    return CandidateEvaluation(
        symbol=feature.symbol,
        date=feature.date,
        mode=mode,
        accepted=accepted,
        breakout_lookback=selected_lookback if accepted else None,
        breakout_level=breakout_level if accepted else None,
        technical_score=technical_score(
            trend_passed=trend_passed,
            breakout_passed=breakout_passed,
            volume_passed=volume_passed,
            volatility_passed=volatility_passed,
        ),
        relative_strength_score=relative_strength_score(feature.rs_63, rs_percentile),
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        rejection_reasons=() if accepted else deduped_rejections,
    )


def generate_candidates(
    features: Mapping[str, FeatureRow],
    *,
    universe_members: Mapping[str, UniverseMember],
    strategy_config: StrategyConfig,
    live_universe_config: LiveUniverseConfig | None = None,
    research_universe_config: ResearchUniverseConfig | None = None,
    regime: RegimeClassification | RegimeState,
    earnings_by_symbol: Mapping[str, EarningsBlackoutEvaluation],
    prior_high_20_by_symbol: Mapping[str, float],
    prior_high_55_by_symbol: Mapping[str, float] | None = None,
    rs_percentile_by_symbol: Mapping[str, float] | None = None,
    currently_held_symbols: Collection[str] = (),
    scale_in_candidate_symbols: Collection[str] = (),
    active_intent_symbols: Collection[str] = (),
) -> tuple[CandidateEvaluation, ...]:
    evaluations: list[CandidateEvaluation] = []
    for symbol in sorted(features):
        universe_member = universe_members.get(symbol)
        earnings = earnings_by_symbol.get(symbol)
        if universe_member is None or earnings is None:
            continue
        evaluations.append(
            evaluate_candidate(
                features[symbol],
                universe_member=universe_member,
                strategy_config=strategy_config,
                live_universe_config=live_universe_config,
                research_universe_config=research_universe_config,
                regime=regime,
                earnings=earnings,
                prior_high_20=prior_high_20_by_symbol.get(symbol),
                prior_high_55=(prior_high_55_by_symbol or {}).get(symbol),
                rs_percentile=(rs_percentile_by_symbol or {}).get(symbol),
                currently_held_symbols=currently_held_symbols,
                scale_in_candidate_symbols=scale_in_candidate_symbols,
                active_intent_symbols=active_intent_symbols,
            )
        )
    return tuple(evaluation for evaluation in evaluations if evaluation.accepted)


def _append_universe_rejections(
    rejection_reasons: list[str],
    universe_member: UniverseMember,
) -> None:
    if not universe_member.included:
        rejection_reasons.append("universe_member_excluded")
        rejection_reasons.extend(universe_member.exclusion_reasons)


def _append_regime_rejections(
    rejection_reasons: list[str],
    reason_codes: list[str],
    regime: RegimeClassification | RegimeState,
) -> None:
    if isinstance(regime, RegimeClassification):
        state = regime.state
        if not regime.new_entries_allowed:
            rejection_reasons.append("regime_blocks_new_entries")
    else:
        state = regime
    if state == "RISK_OFF":
        rejection_reasons.append("regime_risk_off")
    else:
        reason_codes.append(f"regime_{state.lower()}")


def _append_price_liquidity_rejections(
    rejection_reasons: list[str],
    feature: FeatureRow,
    *,
    mode: StrategyMode,
    live_universe_config: LiveUniverseConfig | None,
    research_universe_config: ResearchUniverseConfig | None,
) -> None:
    if mode == "live":
        if live_universe_config is None:
            rejection_reasons.append("missing_live_universe_config")
            return
        min_price = live_universe_config.min_price
        min_adv20_usd = float(live_universe_config.min_adv20_usd)
    else:
        if research_universe_config is None:
            rejection_reasons.append("missing_research_universe_config")
            return
        min_price = research_universe_config.min_price
        min_adv20_usd = float(research_universe_config.min_adv20_usd)

    if feature.close < min_price:
        rejection_reasons.append("below_min_price")
    adv20_usd = feature.adv20_usd
    if adv20_usd is None:
        rejection_reasons.append("missing_adv20_usd")
    elif adv20_usd < min_adv20_usd:
        rejection_reasons.append("below_min_adv20_usd")


def _append_feature_rejections(rejection_reasons: list[str], feature: FeatureRow) -> None:
    if feature.sma_50 is None:
        rejection_reasons.append("missing_sma50")
    if feature.sma_200 is None:
        rejection_reasons.append("missing_sma200")
    if feature.volume_ratio_20 is None:
        rejection_reasons.append("missing_volume_ratio20")
    if feature.rs_63 is None:
        rejection_reasons.append("missing_rs63")
    if _atr_percent(feature) is None:
        rejection_reasons.append("missing_atr_percent")


def _select_breakout(
    *,
    feature: FeatureRow,
    strategy_config: StrategyConfig,
    mode: StrategyMode,
    prior_high_20: float | None,
    prior_high_55: float | None,
    breakout_lookback: BreakoutLookback | None,
) -> tuple[BreakoutLookback, float] | None:
    variants: tuple[int, ...]
    if breakout_lookback is not None:
        variants = (breakout_lookback,)
    elif mode == "live":
        variants = (strategy_config.breakout_lookback_primary,)
    else:
        variants = strategy_config.breakout_lookback_research_variants

    for variant in variants:
        if variant not in (20, 55):
            continue
        prior_high = prior_high_20 if variant == 20 else prior_high_55
        if prior_high is not None and feature.close > prior_high:
            return (cast(BreakoutLookback, variant), prior_high)
    return None


def _atr_percent(feature: FeatureRow) -> float | None:
    if feature.atr_percent is not None:
        return feature.atr_percent
    if feature.atr_14 is None:
        return None
    return feature.atr_14 / feature.close
