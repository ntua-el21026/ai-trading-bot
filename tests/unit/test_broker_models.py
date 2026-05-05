from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.broker.alpaca import AlpacaPaperAdapter
from packages.broker.models import (
    REST_FALLBACK_INTERVAL_SECONDS,
    BrokerAccountSnapshot,
    BrokerPosition,
    BrokerRestFallbackSnapshot,
)
from packages.core.config import SystemConfig, load_app_config


def test_rest_fallback_snapshot_uses_spec_polling_interval() -> None:
    as_of = datetime(2026, 5, 4, 14, 0, tzinfo=UTC)
    account = BrokerAccountSnapshot(
        account_id="paper-account",
        environment="paper",
        equity=100_000.0,
        cash=90_000.0,
        as_of=as_of,
    )

    snapshot = BrokerRestFallbackSnapshot(account=account, as_of=as_of)

    assert snapshot.source == "rest_fallback"
    assert snapshot.poll_interval_seconds == REST_FALLBACK_INTERVAL_SECONDS


def test_broker_models_reject_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        BrokerAccountSnapshot(
            account_id="paper-account",
            environment="paper",
            equity=100_000.0,
            cash=90_000.0,
            as_of=datetime(2026, 5, 4, 14, 0),
        )


def test_broker_position_can_represent_unexpected_short_for_reconciliation() -> None:
    position = BrokerPosition(
        symbol="AAPL",
        asset_class="equity",
        quantity=-5.0,
        avg_entry_price=100.0,
    )

    assert position.quantity == -5.0


def test_alpaca_paper_adapter_refuses_live_mode_and_unconfigured_calls() -> None:
    config = load_app_config()
    live_system = SystemConfig.model_validate(config.system.model_dump() | {"environment": "live"})

    with pytest.raises(RuntimeError, match="only supports paper mode"):
        AlpacaPaperAdapter(system_config=live_system, execution_config=config.execution)

    adapter = AlpacaPaperAdapter(system_config=config.system, execution_config=config.execution)
    with pytest.raises(RuntimeError, match="not configured"):
        adapter.account_snapshot()
