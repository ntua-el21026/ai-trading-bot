from datetime import date, timedelta

from packages.core.config import load_app_config
from packages.data.models import FeatureRow, UniverseMember
from packages.strategy.models import (
    EarningsBlackoutEvaluation,
    RegimeClassification,
    RegimeState,
    StrategyMode,
)
from packages.strategy.signals import evaluate_candidate, evaluate_earnings_blackout


def _feature(symbol: str = "AAPL") -> FeatureRow:
    return FeatureRow(
        symbol=symbol,
        date=date(2024, 1, 31),
        close=180.0,
        sma_50=170.0,
        sma_200=150.0,
        ema_10=176.0,
        atr_14=5.0,
        atr_percent=5.0 / 180.0,
        volume_sma_20=500_000.0,
        volume_ratio_20=1.5,
        high_20=181.0,
        high_55=181.0,
        dollar_volume=90_000_000.0,
        rs_63=0.08,
    )


def _member(
    symbol: str = "AAPL",
    universe: StrategyMode = "live",
    included: bool = True,
) -> UniverseMember:
    return UniverseMember(
        symbol=symbol,
        universe=universe,
        as_of=date(2024, 1, 31),
        included=included,
        exclusion_reasons=() if included else ("not_in_approved_live_symbols",),
        point_in_time_available=True,
        optimistic_backtest_warning=False,
    )


def _regime(
    state: RegimeState = "RISK_ON",
    new_entries_allowed: bool = True,
) -> RegimeClassification:
    return RegimeClassification(
        state=state,
        as_of=date(2024, 1, 31),
        proxy="SPY",
        new_entries_allowed=new_entries_allowed,
        size_multiplier=1.0 if new_entries_allowed else 0.0,
        risk_on_confirmed=state == "RISK_ON",
        risk_off_confirmed=state == "RISK_OFF",
        cooldown_days_remaining=0,
        reason_codes=(f"regime_{state.lower()}",),
    )


def _clear_earnings() -> EarningsBlackoutEvaluation:
    calendar = tuple(date(2024, 1, 1) + timedelta(days=index) for index in range(40))
    return evaluate_earnings_blackout(
        as_of=date(2024, 1, 31),
        earnings_date=date(2024, 2, 9),
        trading_calendar=calendar,
    )


def test_evaluate_candidate_accepts_spec_aligned_live_breakout() -> None:
    config = load_app_config()

    candidate = evaluate_candidate(
        _feature(),
        universe_member=_member(),
        strategy_config=config.strategy,
        live_universe_config=config.live_universe,
        regime=_regime(),
        earnings=_clear_earnings(),
        prior_high_20=179.0,
        prior_high_55=181.0,
    )

    assert candidate.accepted is True
    assert candidate.side == "long"
    assert candidate.breakout_lookback == 20
    assert candidate.breakout_level == 179.0
    assert candidate.rejection_reasons == ()
    assert "rs63_filter_passed" in candidate.reason_codes


def test_evaluate_candidate_rejects_risk_off_and_duplicate_intent() -> None:
    config = load_app_config()

    candidate = evaluate_candidate(
        _feature(),
        universe_member=_member(),
        strategy_config=config.strategy,
        live_universe_config=config.live_universe,
        regime=_regime("RISK_OFF", new_entries_allowed=False),
        earnings=_clear_earnings(),
        prior_high_20=179.0,
        active_intent_symbols=("AAPL",),
    )

    assert candidate.accepted is False
    assert "regime_risk_off" in candidate.rejection_reasons
    assert "active_duplicate_intent" in candidate.rejection_reasons


def test_research_candidate_supports_55_day_breakout_variant() -> None:
    config = load_app_config()

    candidate = evaluate_candidate(
        _feature("MSFT"),
        universe_member=_member("MSFT", universe="research"),
        strategy_config=config.strategy,
        research_universe_config=config.research_universe,
        regime=_regime(),
        earnings=_clear_earnings(),
        prior_high_20=181.0,
        prior_high_55=179.0,
        rs_percentile=75.0,
    )

    assert candidate.accepted is True
    assert candidate.breakout_lookback == 55
    assert "rs_percentile_filter_passed" in candidate.reason_codes


def test_earnings_unknown_is_conservative_and_blocks_entries() -> None:
    config = load_app_config()
    earnings = evaluate_earnings_blackout(
        as_of=date(2024, 1, 31),
        earnings_date=None,
        trading_calendar=(),
    )

    candidate = evaluate_candidate(
        _feature(),
        universe_member=_member(),
        strategy_config=config.strategy,
        live_universe_config=config.live_universe,
        regime=_regime(),
        earnings=earnings,
        prior_high_20=179.0,
    )

    assert earnings.status == "unknown"
    assert earnings.allow_entries is False
    assert earnings.allow_exits is True
    assert candidate.accepted is False
    assert "earnings_unknown" in candidate.rejection_reasons


def test_earnings_blackout_blocks_entries_around_event_date() -> None:
    calendar = tuple(date(2024, 1, 29) + timedelta(days=index) for index in range(8))

    evaluation = evaluate_earnings_blackout(
        as_of=date(2024, 1, 31),
        earnings_date=date(2024, 2, 2),
        trading_calendar=calendar,
    )

    assert evaluation.status == "blackout"
    assert evaluation.allow_entries is False
    assert evaluation.allow_exits is True
