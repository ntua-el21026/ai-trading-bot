from datetime import UTC, date, datetime
from uuid import uuid4

from packages.execution.idempotency import (
    build_client_order_id_root,
    duplicate_intent_key,
    has_duplicate_intent,
    short_hash,
)
from packages.execution.models import ExecutionIntent, ExecutionIntentStatus


def _intent(status: ExecutionIntentStatus = "risk_approved") -> ExecutionIntent:
    return ExecutionIntent(
        decision_id=uuid4(),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=10,
        entry_order_type="limit",
        limit_price=100.0,
        stop_loss_price=98.0,
        time_in_force="day",
        strategy_version="regime_filtered_breakout_v0_3",
        risk_config_version="risk_v0_3",
        autonomy_level=4,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=25,
        expires_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
        client_order_id_root="root",
        status=status,
    )


def test_client_order_id_root_is_deterministic_and_sequence_sensitive() -> None:
    decision_id = str(uuid4())

    first = build_client_order_id_root(
        strategy_version="regime_filtered_breakout_v0_3",
        symbol="AAPL",
        side="buy",
        trade_date=date(2026, 5, 4),
        intent_sequence=1,
        decision_id=decision_id,
    )
    second = build_client_order_id_root(
        strategy_version="regime_filtered_breakout_v0_3",
        symbol="AAPL",
        side="buy",
        trade_date=date(2026, 5, 4),
        intent_sequence=1,
        decision_id=decision_id,
    )
    different_sequence = build_client_order_id_root(
        strategy_version="regime_filtered_breakout_v0_3",
        symbol="AAPL",
        side="buy",
        trade_date=date(2026, 5, 4),
        intent_sequence=2,
        decision_id=decision_id,
    )

    assert first == second
    assert first != different_sequence
    assert first.startswith("regime_filtered_breakout_v0_3-AAPL-buy-20260504-1-")


def test_short_hash_is_stable() -> None:
    assert short_hash("same-input") == short_hash("same-input")
    assert len(short_hash("same-input")) == 10


def test_duplicate_intent_detection_ignores_terminal_statuses() -> None:
    intent = _intent()
    key = duplicate_intent_key(intent, date(2026, 5, 4))

    assert has_duplicate_intent(key, (intent,)) is True
    assert has_duplicate_intent(key, (_intent("cancelled"),)) is False
