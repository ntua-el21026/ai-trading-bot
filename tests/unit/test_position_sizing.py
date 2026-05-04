from packages.core.config import load_app_config
from packages.risk.models import PositionSizingInput
from packages.risk.sizing import calculate_position_size


def test_position_sizing_uses_risk_and_max_position_caps() -> None:
    config = load_app_config()

    result = calculate_position_size(
        PositionSizingInput(
            account_equity=100_000.0,
            entry_price=100.0,
            stop_price=98.0,
            regime_size_multiplier=0.5,
        ),
        config.risk_level_4_micro_live,
    )

    assert result.accepted is True
    assert result.risk_amount == 350.0
    assert result.stop_distance == 2.0
    assert result.raw_shares == 175
    assert result.max_value_shares == 40
    assert result.shares == 20


def test_position_sizing_rejects_invalid_stop_distance() -> None:
    config = load_app_config()

    result = calculate_position_size(
        PositionSizingInput(account_equity=100_000.0, entry_price=100.0, stop_price=101.0),
        config.risk_level_4_micro_live,
    )

    assert result.accepted is False
    assert result.shares == 0
    assert result.rejection_reasons == ("invalid_stop_distance",)


def test_position_sizing_rejects_when_multipliers_reduce_below_one_share() -> None:
    config = load_app_config()

    result = calculate_position_size(
        PositionSizingInput(
            account_equity=1_000.0,
            entry_price=100.0,
            stop_price=99.0,
            regime_size_multiplier=0.1,
        ),
        config.risk_level_4_micro_live,
    )

    assert result.accepted is False
    assert result.rejection_reasons == ("position_size_below_one_share",)

