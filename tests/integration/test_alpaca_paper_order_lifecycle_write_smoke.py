from __future__ import annotations

import json
import os

import pytest

from packages.broker.alpaca import AlpacaClientError
from packages.broker.models import BrokerErrorCode
from packages.broker.order_lifecycle_smoke import (
    AlpacaPaperOrderLifecycleSmokeSummary,
    failed_alpaca_paper_order_lifecycle_smoke_gates,
    run_alpaca_paper_order_lifecycle_smoke,
)
from packages.core.config import load_app_config


@pytest.mark.integration
def test_alpaca_paper_order_lifecycle_smoke() -> None:
    app_config = load_app_config()
    failed_gates = failed_alpaca_paper_order_lifecycle_smoke_gates(
        environ=os.environ,
        app_config=app_config,
    )
    if failed_gates:
        pytest.skip(f"Alpaca paper order-lifecycle smoke gates not satisfied: {failed_gates}")

    summary, smoke_error = _run_smoke_sanitized()
    if smoke_error is not None:
        code, retryable, ambiguous = smoke_error
        pytest.fail(
            "Alpaca paper order-lifecycle smoke failed: "
            f"code={code}, retryable={str(retryable).lower()}, "
            f"ambiguous={str(ambiguous).lower()}",
            pytrace=False,
        )
    assert summary is not None

    serialized = json.dumps(summary.model_dump(mode="json"))
    assert "ALPACA_SECRET_KEY" not in serialized
    assert "APCA-API-SECRET-KEY" not in serialized
    assert "raw_broker_payload" not in serialized
    assert summary.paper_endpoint_used is True or summary.refused is True
    assert summary.live_endpoint_used is False
    assert summary.secrets_printed is False
    assert summary.raw_payloads_printed is False
    assert summary.actual_paper_trading_started is False
    assert summary.live_trading_enabled is False
    assert summary.autonomous_execution_enabled is False
    assert summary.level4_ready is False


def _run_smoke_sanitized() -> (
    tuple[AlpacaPaperOrderLifecycleSmokeSummary | None, tuple[BrokerErrorCode, bool, bool] | None]
):
    try:
        return run_alpaca_paper_order_lifecycle_smoke(), None
    except AlpacaClientError as exc:
        return None, (exc.code, exc.retryable, exc.ambiguous)
