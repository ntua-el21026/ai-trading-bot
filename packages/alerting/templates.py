"""Deterministic Telegram-safe alert message templates."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.alerting.models import AlertMessage
from packages.reporting.models import DailyReport, WeeklyReport
from packages.reporting.renderers import (
    render_daily_report_telegram_summary,
    render_weekly_report_telegram_summary,
)


class AlertTemplateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TradeOutcomeSummary(AlertTemplateModel):
    symbol: str
    result: Literal["WIN", "LOSS"]
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    pnl_pct: float
    r_multiple: float
    exit_reason: str

    @model_validator(mode="after")
    def validate_symbol(self) -> TradeOutcomeSummary:
        if self.symbol != self.symbol.upper():
            raise ValueError("trade outcome symbol must be uppercase")
        if not self.exit_reason.strip():
            raise ValueError("trade outcome exit_reason cannot be blank")
        return self


def build_test_alert(*, created_at: datetime) -> AlertMessage:
    return AlertMessage(
        category="routine_status",
        severity="info",
        title="Telegram alert smoke test",
        body="Operator-facing Telegram delivery harness test. No trading action is requested.",
        source_component="telegram_alert_smoke",
        created_at=created_at,
        payload={"smoke": True},
    )


def build_order_submitted_alert(
    *,
    symbol: str,
    quantity: float,
    order_type: str,
    created_at: datetime,
) -> AlertMessage:
    return AlertMessage(
        category="order_submitted",
        severity="info",
        title=f"Order Submitted: {symbol}",
        body=f"Submitted {quantity:g} share(s) using {order_type.upper()} order type.",
        source_component="execution",
        created_at=created_at,
        related_entity_type="order",
        payload={"symbol": symbol, "quantity": quantity, "order_type": order_type},
    )


def build_fill_alert(
    *,
    symbol: str,
    filled_quantity: float,
    average_price: float,
    partial: bool,
    created_at: datetime,
) -> AlertMessage:
    category: Literal["partial_fill", "order_filled"] = (
        "partial_fill" if partial else "order_filled"
    )
    title = f"{'Partial Fill' if partial else 'Order Filled'}: {symbol}"
    return AlertMessage(
        category=category,
        severity="info",
        title=title,
        body=f"Filled quantity: {filled_quantity:g}. Average price: {average_price:.2f}.",
        source_component="execution",
        created_at=created_at,
        related_entity_type="fill",
        payload={"symbol": symbol, "filled_quantity": filled_quantity, "partial": partial},
    )


def build_protective_stop_confirmed_alert(
    *,
    symbol: str,
    quantity: float,
    stop_price: float,
    created_at: datetime,
) -> AlertMessage:
    return AlertMessage(
        category="protective_stop_verified",
        severity="info",
        title=f"Protective Stop Confirmed: {symbol}",
        body=f"Stop verified for {quantity:g} share(s) at {stop_price:.2f}.",
        source_component="execution",
        created_at=created_at,
        related_entity_type="protective_stop",
        payload={"symbol": symbol, "quantity": quantity, "stop_price": stop_price},
    )


def build_protective_stop_missing_alert(*, symbol: str, created_at: datetime) -> AlertMessage:
    return AlertMessage(
        category="missing_protective_stop",
        severity="critical",
        title=f"Missing Protective Stop: {symbol}",
        body="Position lacks a confirmed protective stop. New risk must remain paused.",
        source_component="reconciliation",
        created_at=created_at,
        related_entity_type="position",
        payload={"symbol": symbol},
    )


def build_trade_outcome_alert(
    outcome: TradeOutcomeSummary,
    *,
    created_at: datetime,
) -> AlertMessage:
    body = "\n".join(
        (
            f"Trade Closed: {outcome.symbol}",
            f"Result: {outcome.result}",
            f"Entry: {outcome.entry_price:.2f}",
            f"Exit: {outcome.exit_price:.2f}",
            f"PnL: {_signed_pct(outcome.pnl_pct)}",
            f"R: {_signed_r(outcome.r_multiple)}",
            f"Reason: {outcome.exit_reason}",
        )
    )
    return AlertMessage(
        category="trade_closed_win" if outcome.result == "WIN" else "trade_closed_loss",
        severity="info" if outcome.result == "WIN" else "warning",
        title=f"Trade Closed: {outcome.symbol} {outcome.result}",
        body=body,
        source_component="reporting",
        created_at=created_at,
        related_entity_type="trade",
        payload=outcome.model_dump(mode="json"),
    )


def build_daily_report_alert(report: DailyReport, *, created_at: datetime) -> AlertMessage:
    return AlertMessage(
        category="daily_report_generated",
        severity="info",
        title=f"Daily Report - {report.status.replace('_', ' ').title()}",
        body=render_daily_report_telegram_summary(report),
        source_component="reporting",
        created_at=created_at,
        related_entity_type="report",
        payload={"report_type": "daily", "status": report.status},
    )


def build_weekly_report_alert(report: WeeklyReport, *, created_at: datetime) -> AlertMessage:
    return AlertMessage(
        category="weekly_report_generated",
        severity="info",
        title=f"Weekly Report - {report.status.replace('_', ' ').title()}",
        body=render_weekly_report_telegram_summary(report),
        source_component="reporting",
        created_at=created_at,
        related_entity_type="report",
        payload={"report_type": "weekly", "status": report.status},
    )


def build_ai_news_warning_alert(
    *,
    symbol: str,
    reason: str,
    created_at: datetime,
) -> AlertMessage:
    return AlertMessage(
        category="ai_news_warning",
        severity="warning",
        title=f"AI/News Warning: {symbol}",
        body=f"{symbol}: {reason}. AI influence must remain bounded by deterministic rules.",
        source_component="ai_intelligence",
        created_at=created_at,
        related_entity_type="ai_research",
        payload={"symbol": symbol, "reason": reason},
    )


def build_reconciliation_mismatch_alert(
    *,
    summary: str,
    critical: bool,
    created_at: datetime,
) -> AlertMessage:
    return AlertMessage(
        category="reconciliation_mismatch" if critical else "noncritical_reconciliation_issue",
        severity="critical" if critical else "warning",
        title="Broker Reconciliation Mismatch",
        body=summary,
        source_component="reconciliation",
        created_at=created_at,
        related_entity_type="broker_reconciliation",
        payload={"critical": critical},
    )


def build_kill_switch_alert(*, reason: str, created_at: datetime) -> AlertMessage:
    return AlertMessage(
        category="kill_switch_activation",
        severity="critical",
        title="Kill Switch Activated",
        body=f"New risk is paused. Reason: {reason}. Manual review is required before re-arm.",
        source_component="kill_switch",
        created_at=created_at,
        related_entity_type="kill_switch",
        payload={"reason": reason},
    )


def build_generic_incident_alert(
    *,
    title: str,
    body: str,
    severity: Literal["warning", "critical"],
    created_at: datetime,
) -> AlertMessage:
    return AlertMessage(
        category="generic_incident",
        severity=severity,
        title=title,
        body=body,
        source_component="incident_service",
        created_at=created_at,
        related_entity_type="incident",
        payload={"severity": severity},
    )


def _signed_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _signed_r(value: float) -> str:
    return f"{value:+.2f}R"
