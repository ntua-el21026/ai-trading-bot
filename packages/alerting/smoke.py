"""Gated Telegram alert-delivery smoke harness."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.alerting.adapters import TelegramAlertAdapter, TelegramClient, TelegramDeliveryConfig
from packages.alerting.models import AlertDispatchRequest, AlertMessage
from packages.alerting.templates import (
    TradeOutcomeSummary,
    build_daily_report_alert,
    build_generic_incident_alert,
    build_test_alert,
    build_trade_outcome_alert,
)
from packages.reporting.generators import generate_daily_report
from packages.reporting.models import DailyReport, ReportInputSnapshot


class TelegramSmokeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    refused: bool
    gates_loaded: bool
    real_delivery_enabled: bool
    token_present: bool
    chat_id_present: bool
    messages_attempted: int = Field(ge=0)
    messages_sent: int = Field(ge=0)
    message_limit_respected: bool
    raw_response_printed: bool = False
    secrets_printed: bool = False
    external_calls_performed: bool = False
    failure_codes: tuple[str, ...] = ()
    refusal_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.messages_sent > self.messages_attempted:
            raise ValueError("messages_sent cannot exceed messages_attempted")
        if self.messages_attempted > 3:
            raise ValueError("Telegram smoke cannot attempt more than 3 messages")
        return self


def run_telegram_alert_smoke(
    *,
    env: Mapping[str, str | None] | None = None,
    client: TelegramClient | None = None,
    now: datetime | None = None,
) -> TelegramSmokeSummary:
    env_mapping = env or os.environ
    config = TelegramDeliveryConfig.from_mapping(env_mapping)
    refusal_reasons = config.refusal_reasons()
    if refusal_reasons:
        return TelegramSmokeSummary(
            refused=True,
            gates_loaded=False,
            real_delivery_enabled=config.real_delivery_enabled,
            token_present=config.token_present,
            chat_id_present=config.chat_id_present,
            messages_attempted=0,
            messages_sent=0,
            message_limit_respected=True,
            refusal_reasons=refusal_reasons,
        )

    smoke_now = now or datetime.now(UTC)
    messages = _smoke_messages(env_mapping, created_at=smoke_now)
    selected_messages = messages[: config.smoke_max_messages]
    adapter = TelegramAlertAdapter(config=config, client=client)
    attempted = 0
    sent = 0
    failure_codes: list[str] = []
    external_calls = False
    for message in selected_messages:
        attempted += 1
        result = adapter.dispatch(AlertDispatchRequest(message=message, channels=("telegram",)))
        external_calls = external_calls or result.external_calls_performed
        if result.status == "sent":
            sent += 1
            continue
        failure_codes.append(result.failure_code or "telegram_delivery_failed")

    return TelegramSmokeSummary(
        refused=sent == 0 and bool(failure_codes),
        gates_loaded=True,
        real_delivery_enabled=config.real_delivery_enabled,
        token_present=config.token_present,
        chat_id_present=config.chat_id_present,
        messages_attempted=attempted,
        messages_sent=sent,
        message_limit_respected=attempted <= config.smoke_max_messages <= 3,
        external_calls_performed=external_calls,
        failure_codes=tuple(failure_codes),
    )


def _smoke_messages(
    env: Mapping[str, str | None],
    *,
    created_at: datetime,
) -> tuple[AlertMessage, ...]:
    messages: list[AlertMessage] = [build_test_alert(created_at=created_at)]
    if _env_bool(env.get("TELEGRAM_ALERT_SMOKE_INCLUDE_REPORT_SAMPLE")):
        report = generate_daily_report(
            report_date=date(2026, 5, 8),
            snapshot=ReportInputSnapshot(
                generated_at=created_at,
                environment="paper",
                dry_run=True,
                live_trading_enabled=False,
                autonomous_execution_enabled=False,
                candidates=(
                    {"symbol": "SPY", "candidate_status": "accepted"},
                    {"symbol": "AAPL", "candidate_status": "rejected"},
                ),
                decisions=(
                    {"symbol": "SPY", "decision_status": "approved"},
                    {"symbol": "AAPL", "decision_status": "rejected"},
                ),
                positions=(),
                reconciliations=({"status": "clean", "mismatches": []},),
                incidents=(),
            ),
        )
        messages.append(
            build_daily_report_alert(cast(DailyReport, report.report), created_at=created_at)
        )
    if _env_bool(env.get("TELEGRAM_ALERT_SMOKE_INCLUDE_TRADE_SAMPLE")):
        messages.append(
            build_trade_outcome_alert(
                TradeOutcomeSummary(
                    symbol="SPY",
                    result="WIN",
                    entry_price=500.00,
                    exit_price=505.00,
                    pnl_pct=1.00,
                    r_multiple=0.50,
                    exit_reason="smoke sample",
                ),
                created_at=created_at,
            )
        )
    if _env_bool(env.get("TELEGRAM_ALERT_SMOKE_INCLUDE_CRITICAL_SAMPLE")):
        messages.append(
            build_generic_incident_alert(
                title="Telegram critical smoke sample",
                body="Critical sample only. No trading action is requested.",
                severity="critical",
                created_at=created_at,
            )
        )
    return tuple(messages)


def _env_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
