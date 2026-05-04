from datetime import date

from packages.core.config import load_app_config
from packages.data.models import AssetMetadata, FeatureRow
from packages.data.universe import build_live_universe, build_research_universe


def _feature(symbol: str, close: float, adv20_usd: float) -> FeatureRow:
    volume_sma_20 = adv20_usd / close
    return FeatureRow(
        symbol=symbol,
        date=date(2024, 1, 31),
        close=close,
        volume_sma_20=volume_sma_20,
        dollar_volume=adv20_usd,
    )


def test_live_universe_filters_to_approved_liquid_equities_and_etfs() -> None:
    config = load_app_config()
    assets = (
        AssetMetadata(symbol="SPY", asset_class="etf", point_in_time_available=True),
        AssetMetadata(symbol="AAPL", asset_class="equity", point_in_time_available=True),
        AssetMetadata(symbol="BTCUSD", asset_class="crypto", point_in_time_available=True),
        AssetMetadata(symbol="TQQQ", asset_class="etf", is_leveraged_etf=True),
        AssetMetadata(symbol="XYZ", asset_class="equity", point_in_time_available=True),
    )
    features = {
        "SPY": _feature("SPY", 500.0, 100_000_000.0),
        "AAPL": _feature("AAPL", 180.0, 80_000_000.0),
        "BTCUSD": _feature("BTCUSD", 50_000.0, 100_000_000.0),
        "TQQQ": _feature("TQQQ", 60.0, 100_000_000.0),
        "XYZ": _feature("XYZ", 30.0, 100_000_000.0),
    }

    result = build_live_universe(
        assets=assets,
        latest_features=features,
        config=config.live_universe,
        as_of=date(2024, 1, 31),
    )

    assert result.included_symbols == ("AAPL", "SPY")
    excluded = {member.symbol: member.exclusion_reasons for member in result.members}
    assert "disallowed_asset_class:crypto" in excluded["BTCUSD"]
    assert "leveraged_etf_excluded" in excluded["TQQQ"]
    assert "not_in_approved_live_symbols" in excluded["XYZ"]


def test_research_universe_marks_optimistic_when_point_in_time_data_is_missing() -> None:
    config = load_app_config()
    assets = (
        AssetMetadata(symbol="SPY", asset_class="etf", point_in_time_available=False),
    )
    features = {"SPY": _feature("SPY", 500.0, 100_000_000.0)}

    result = build_research_universe(
        assets=assets,
        latest_features=features,
        config=config.research_universe,
        as_of=date(2024, 1, 31),
    )

    assert result.included_symbols == ("SPY",)
    assert result.optimistic_backtest_warning is True
    assert result.members[0].optimistic_backtest_warning is True

