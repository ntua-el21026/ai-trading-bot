"""Alert adapter protocols and fake/default-safe Telegram delivery."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib import error, parse, request

from packages.alerting.models import (
    AlertChannel,
    AlertDispatchRequest,
    AlertDispatchResult,
    AlertMessage,
    AlertSeverity,
)

TELEGRAM_PROVIDER = "telegram"
TELEGRAM_SMOKE_CONFIRM = "SEND_TEST_ALERT_TO_OPERATOR"
DEFAULT_TELEGRAM_TIMEOUT_SECONDS = 10
MAX_TELEGRAM_MESSAGE_LENGTH = 3800

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|database_url|chat_id)\s*[:=]\s*[^\s,;]+"
        ),
        r"\1=<redacted>",
    ),
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"), "<redacted-telegram-token>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "<redacted-openai-key>"),
    (re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"), "<redacted-openai-key>"),
    (
        re.compile(r"postgres(?:ql)?://[^\s/@:]+:[^\s/@]+@[^\s]+", re.IGNORECASE),
        "postgres://<redacted>@<redacted>",
    ),
)


class AlertAdapter(Protocol):
    channel: AlertChannel

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        """Dispatch an alert message through a channel boundary."""


class FakeAlertAdapter:
    channel: AlertChannel = "fake"

    def __init__(self) -> None:
        self.messages: list[AlertMessage] = []

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        self.messages.append(request.message)
        return AlertDispatchResult(
            status="captured",
            channel=self.channel,
            message=request.message,
            external_calls_performed=False,
        )


class TelegramAlertAdapter:
    channel: AlertChannel = "telegram"

    def __init__(
        self,
        *,
        config: TelegramDeliveryConfig | None = None,
        bot_token: str | None = None,
        chat_id: str | None = None,
        client: TelegramClient | None = None,
    ) -> None:
        self._config = config or TelegramDeliveryConfig.from_mapping(
            {
                "TELEGRAM_BOT_TOKEN": bot_token or "",
                "TELEGRAM_CHAT_ID": chat_id or "",
            }
        )
        self._client = client or UrllibTelegramClient()
        self._daily_sent = 0
        self._smoke_sent = 0

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        refusal_reasons = self._config.refusal_reasons()
        if refusal_reasons:
            return _failed_closed(
                channel=self.channel,
                message=request.message,
                error_message="Telegram delivery gates are not loaded.",
                failure_code="telegram_gates_missing",
            )
        if self._smoke_sent >= self._config.smoke_max_messages:
            return _failed_closed(
                channel=self.channel,
                message=request.message,
                error_message="Telegram smoke message limit exceeded.",
                failure_code="telegram_smoke_limit_exceeded",
            )
        if (
            self._daily_sent >= self._config.daily_message_limit
            and not _critical_bypasses_limit(
                request.message.severity,
                self._config.critical_bypass_daily_limit,
            )
        ):
            return _failed_closed(
                channel=self.channel,
                message=request.message,
                error_message="Telegram daily message limit exceeded.",
                failure_code="telegram_daily_limit_exceeded",
            )

        text = render_telegram_message(request.message)
        try:
            send_result = self._client.send_message(
                bot_token=self._config.bot_token or "",
                chat_id=self._config.chat_id or "",
                text=text,
                timeout_seconds=DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
            )
        except TelegramDeliveryError as exc:
            return AlertDispatchResult(
                status="failed_closed",
                channel=self.channel,
                message=request.message,
                external_calls_performed=True,
                failure_code=exc.code,
                error_message=exc.sanitized_message,
            )
        self._daily_sent += 1
        self._smoke_sent += 1
        return AlertDispatchResult(
            status="sent",
            channel=self.channel,
            message=request.message,
            external_calls_performed=True,
            provider_message_id=send_result.provider_message_id,
        )


class EmailAlertAdapter:
    channel: AlertChannel = "email"

    def __init__(self, *, smtp_url: str | None = None, from_address: str | None = None) -> None:
        self._configured = bool(smtp_url and from_address)

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        if not self._configured:
            return _failed_closed(
                channel=self.channel,
                message=request.message,
                error_message="Email alert adapter is not configured with required secrets.",
            )
        return _failed_closed(
            channel=self.channel,
            message=request.message,
            error_message="Email network delivery is disabled in this milestone.",
        )


def _failed_closed(
    *,
    channel: AlertChannel,
    message: AlertMessage,
    error_message: str,
    failure_code: str | None = None,
) -> AlertDispatchResult:
    return AlertDispatchResult(
        status="failed_closed",
        channel=channel,
        message=message,
        external_calls_performed=False,
        failure_code=failure_code,
        error_message=error_message,
    )


@dataclass(frozen=True)
class TelegramDeliveryConfig:
    provider_primary: str = TELEGRAM_PROVIDER
    real_delivery_enabled: bool = False
    bot_token: str | None = None
    chat_id: str | None = None
    run_smoke: str | None = None
    smoke_confirm: str | None = None
    smoke_max_messages_raw: str | None = None
    daily_message_limit: int = 50
    critical_bypass_daily_limit: bool = True

    @classmethod
    def from_mapping(cls, env: Mapping[str, str | None]) -> TelegramDeliveryConfig:
        return cls(
            provider_primary=(env.get("ALERT_PROVIDER_PRIMARY") or TELEGRAM_PROVIDER).strip(),
            real_delivery_enabled=_env_bool(env.get("ALERT_ENABLE_REAL_DELIVERY")),
            bot_token=_blank_to_none(env.get("TELEGRAM_BOT_TOKEN")),
            chat_id=_blank_to_none(env.get("TELEGRAM_CHAT_ID")),
            run_smoke=_blank_to_none(env.get("RUN_TELEGRAM_ALERT_SMOKE")),
            smoke_confirm=_blank_to_none(env.get("TELEGRAM_ALERT_SMOKE_CONFIRM")),
            smoke_max_messages_raw=_blank_to_none(env.get("TELEGRAM_ALERT_SMOKE_MAX_MESSAGES")),
            daily_message_limit=_parse_int(env.get("ALERT_DAILY_MESSAGE_LIMIT"), default=50),
            critical_bypass_daily_limit=_env_bool(
                env.get("ALERT_CRITICAL_BYPASS_DAILY_LIMIT"),
                default=True,
            ),
        )

    @property
    def token_present(self) -> bool:
        return bool(self.bot_token)

    @property
    def chat_id_present(self) -> bool:
        return bool(self.chat_id)

    @property
    def smoke_max_messages(self) -> int:
        return _parse_int(self.smoke_max_messages_raw, default=0)

    @property
    def gates_loaded(self) -> bool:
        return not self.refusal_reasons()

    def refusal_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.provider_primary != TELEGRAM_PROVIDER:
            reasons.append("ALERT_PROVIDER_PRIMARY=telegram")
        if not self.real_delivery_enabled:
            reasons.append("ALERT_ENABLE_REAL_DELIVERY=true")
        if not self.token_present:
            reasons.append("TELEGRAM_BOT_TOKEN present")
        if not self.chat_id_present:
            reasons.append("TELEGRAM_CHAT_ID present")
        if self.run_smoke != "1":
            reasons.append("RUN_TELEGRAM_ALERT_SMOKE=1")
        if self.smoke_confirm != TELEGRAM_SMOKE_CONFIRM:
            reasons.append(f"TELEGRAM_ALERT_SMOKE_CONFIRM={TELEGRAM_SMOKE_CONFIRM}")
        if self.smoke_max_messages_raw is None:
            reasons.append("TELEGRAM_ALERT_SMOKE_MAX_MESSAGES present")
        elif self.smoke_max_messages < 1 or self.smoke_max_messages > 3:
            reasons.append("TELEGRAM_ALERT_SMOKE_MAX_MESSAGES<=3")
        if self.daily_message_limit < 0:
            reasons.append("ALERT_DAILY_MESSAGE_LIMIT>=0")
        return tuple(reasons)


@dataclass(frozen=True)
class TelegramSendResult:
    provider_message_id: str | None = None


class TelegramClient(Protocol):
    def send_message(
        self,
        *,
        bot_token: str,
        chat_id: str,
        text: str,
        timeout_seconds: int,
    ) -> TelegramSendResult:
        """Send a message through Telegram's Bot API."""


class TelegramDeliveryError(RuntimeError):
    def __init__(self, *, code: str, sanitized_message: str) -> None:
        super().__init__(sanitized_message)
        self.code = code
        self.sanitized_message = sanitized_message


class UrllibTelegramClient:
    def send_message(
        self,
        *,
        bot_token: str,
        chat_id: str,
        text: str,
        timeout_seconds: int,
    ) -> TelegramSendResult:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = parse.urlencode(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        telegram_request = request.Request(
            url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with request.urlopen(telegram_request, timeout=timeout_seconds) as response:
                response_body = response.read(4096)
                status_code = response.status
        except error.HTTPError as exc:
            raise TelegramDeliveryError(
                code="telegram_http_error",
                sanitized_message=f"Telegram API returned HTTP {exc.code}.",
            ) from exc
        except error.URLError as exc:
            raise TelegramDeliveryError(
                code="telegram_network_error",
                sanitized_message="Telegram API network request failed.",
            ) from exc
        if status_code >= 400:
            raise TelegramDeliveryError(
                code="telegram_http_error",
                sanitized_message=f"Telegram API returned HTTP {status_code}.",
            )
        return _parse_telegram_response(response_body)


def render_telegram_message(message: AlertMessage) -> str:
    related = ""
    if message.related_entity_type and message.related_entity_id:
        related = f"\nRelated: {sanitize_alert_text(message.related_entity_type)}"
    text = (
        f"{message.severity.upper()}: {sanitize_alert_text(message.title)}\n"
        f"Category: {message.category}\n"
        f"Source: {sanitize_alert_text(message.source_component)}"
        f"{related}\n\n"
        f"{sanitize_alert_text(message.body)}"
    )
    if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
        return text[: MAX_TELEGRAM_MESSAGE_LENGTH - 20].rstrip() + "\n<message truncated>"
    return text


def sanitize_alert_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _parse_telegram_response(response_body: bytes) -> TelegramSendResult:
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TelegramDeliveryError(
            code="telegram_malformed_response",
            sanitized_message="Telegram API returned an unreadable response.",
        ) from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise TelegramDeliveryError(
            code="telegram_api_rejected",
            sanitized_message="Telegram API rejected the message.",
        )
    result = payload.get("result")
    message_id: str | None = None
    if isinstance(result, dict) and result.get("message_id") is not None:
        message_id = str(result["message_id"])
    return TelegramSendResult(provider_message_id=message_id)


def _critical_bypasses_limit(
    severity: AlertSeverity,
    critical_bypass_daily_limit: bool,
) -> bool:
    return severity == "critical" and critical_bypass_daily_limit


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _env_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return -1
