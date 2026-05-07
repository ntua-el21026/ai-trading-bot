from __future__ import annotations

import os

import pytest

from packages.broker.alpaca import AlpacaClientError
from packages.broker.models import BrokerErrorCode
from packages.broker.smoke import (
    AlpacaPaperReadOnlySmokeSummary,
    failed_alpaca_paper_readonly_smoke_gates,
    run_alpaca_paper_readonly_smoke,
)
from packages.core.config import load_app_config


@pytest.mark.integration
def test_alpaca_paper_readonly_smoke() -> None:
    app_config = load_app_config()
    failed_gates = failed_alpaca_paper_readonly_smoke_gates(
        environ=os.environ,
        app_config=app_config,
    )
    if failed_gates:
        pytest.skip(f"Alpaca paper read-only smoke gates not satisfied: {failed_gates}")

    summary, smoke_error = _run_smoke_sanitized()
    if smoke_error is not None:
        code, retryable, ambiguous = smoke_error
        pytest.fail(
            "Alpaca paper read-only smoke failed: "
            f"code={code}, retryable={str(retryable).lower()}, "
            f"ambiguous={str(ambiguous).lower()}",
            pytrace=False,
        )
    assert summary is not None

    assert summary.base_url == "https://paper-api.alpaca.markets"
    assert summary.credentials_loaded is True
    assert summary.account_snapshot_reachable is True
    assert summary.account_snapshot_mapped is True
    assert summary.open_orders_reachable is True
    assert summary.open_orders_mapped is True
    assert summary.positions_reachable is True
    assert summary.positions_mapped is True
    assert summary.clock_reachable is True
    assert summary.clock_mapped is True
    assert summary.live_endpoint_used is False
    assert summary.write_operations_attempted is False
    assert summary.order_write_endpoints_called is False
    assert summary.orders_submitted is False
    assert summary.orders_cancelled is False
    assert summary.orders_replaced is False
    assert summary.stops_submitted is False


def _run_smoke_sanitized() -> (
    tuple[AlpacaPaperReadOnlySmokeSummary | None, tuple[BrokerErrorCode, bool, bool] | None]
):
    try:
        return run_alpaca_paper_readonly_smoke(), None
    except AlpacaClientError as exc:
        return None, (exc.code, exc.retryable, exc.ambiguous)
