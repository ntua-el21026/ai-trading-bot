from __future__ import annotations

import os

import pytest

from packages.alerting.adapters import TELEGRAM_SMOKE_CONFIRM, TelegramDeliveryConfig
from packages.alerting.smoke import run_telegram_alert_smoke


@pytest.mark.integration
def test_telegram_alert_delivery_smoke_is_explicitly_gated() -> None:
    config = TelegramDeliveryConfig.from_mapping(os.environ)
    if not config.gates_loaded:
        pytest.skip("Telegram alert smoke requires explicit real-delivery gates")

    summary = run_telegram_alert_smoke()

    assert summary.gates_loaded is True
    assert summary.real_delivery_enabled is True
    assert summary.token_present is True
    assert summary.chat_id_present is True
    assert summary.messages_attempted <= 3
    assert summary.messages_sent <= summary.messages_attempted
    assert summary.message_limit_respected is True
    assert summary.raw_response_printed is False
    assert summary.secrets_printed is False
    assert os.environ.get("TELEGRAM_ALERT_SMOKE_CONFIRM") == TELEGRAM_SMOKE_CONFIRM
