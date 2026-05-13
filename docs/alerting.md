# Alerting

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Milestone 23 adds Telegram as the only real alert delivery channel for now. Email/Resend is
intentionally deferred and is not required for this stage. Default tests and default activity wiring
still use fake/fail-closed adapters and do not send Telegram, email, broker, AI/news, or other
network messages.

Milestone 25 surfaces alerting status in the dashboard/control-plane read model. The dashboard
status is read-only; it does not send Telegram messages, expose Telegram tokens/chat IDs, implement
Telegram commands, or use alerts as a control path.

Milestone 27 readiness aggregation records Telegram harness and prior smoke evidence as local
status only. It does not send Telegram messages or use alerts as a control path.

Milestone 43 scale-in incidents, including an unverified add-on protective stop, must be alertable
as critical missing-stop or broker-ambiguity style incidents in future runtime wiring. M43 itself
uses fake/stub tests only and sends no real Telegram messages.

## Implemented

- `packages/alerting/models.py` defines alert severity, channels, categories, messages, dispatch
  requests, and dispatch results.
- `packages/alerting/routing.py` maps severity/category to channels and escalates critical
  categories such as missing protective stops, reconciliation mismatch, duplicate orders/intents,
  kill-switch activation, worker unavailability, broker ambiguity, and degraded AI quality.
- `packages/alerting/templates.py` renders deterministic alert messages for test alerts,
  order/fill/stop events, trade win/loss outcomes, daily/weekly report summaries, AI/news warnings,
  reconciliation mismatches, kill-switch activation, and generic incidents.
- `packages/alerting/adapters.py` defines `FakeAlertAdapter`, a gated server-side
  `TelegramAlertAdapter`, and a fail-closed future email skeleton.
- `packages/alerting/smoke.py` and `scripts/check_telegram_alert_delivery.py` provide the explicit
  Telegram delivery smoke harness with sanitized summary output.
- `apps/workers/app/activities/reporting.py` exposes alert dispatch, incident-alert, and
  report-alert Temporal activity boundaries. They use fake adapters by default.
- `packages/paper/dry_run.py` captures fake dry-run alerts for order, fill, protective stop,
  incident, and report-generated events.
- `packages/control_plane/models.py` and `packages/control_plane/runtime.py` expose a read-only
  alerting status section for dashboard smoke validation without calling real alert adapters.

## Telegram Real Delivery Gates

Real Telegram delivery may occur only when all gates are loaded before the process starts:

- `ALERT_PROVIDER_PRIMARY=telegram`
- `ALERT_ENABLE_REAL_DELIVERY=true`
- `TELEGRAM_BOT_TOKEN` present
- `TELEGRAM_CHAT_ID` present
- `RUN_TELEGRAM_ALERT_SMOKE=1`
- `TELEGRAM_ALERT_SMOKE_CONFIRM=SEND_TEST_ALERT_TO_OPERATOR`
- `TELEGRAM_ALERT_SMOKE_MAX_MESSAGES` present and `<= 3`

The smoke command is:

```bash
uv run python scripts/check_telegram_alert_delivery.py
```

With no gates loaded, the expected result is a sanitized refusal and no Telegram call. When gates are
loaded, the smoke sends at most the configured message count. Optional smoke samples are controlled
by:

- `TELEGRAM_ALERT_SMOKE_INCLUDE_REPORT_SAMPLE`
- `TELEGRAM_ALERT_SMOKE_INCLUDE_TRADE_SAMPLE`
- `TELEGRAM_ALERT_SMOKE_INCLUDE_CRITICAL_SAMPLE`

The script prints no `.env`, tokens, chat IDs, raw Telegram responses, broker secrets, database URLs,
Temporal keys, or AI/news provider keys.

## Routing Policy

- INFO: routine status, daily report generated, weekly report generated.
- WARNING: AI/news fallback, provider budget exceeded, stale data, unconfirmed stop warning,
  non-critical reconciliation issue, trade loss summary.
- CRITICAL: missing protective stop, broker/internal mismatch, duplicate order/intent, unexpected
  broker position, unexpected short position, kill-switch activation, execution worker unavailable,
  broker ambiguity, database/audit persistence unavailable, and AI quality degraded to
  `AI_NEUTRAL_ONLY` or `AI_ESCALATION_REQUIRED`.
- ORDER/FILL/STOP: order submitted, order acknowledged, order filled, partial fill, protective stop
  submitted, protective stop verified, cleanup completed.
- REPORT: daily and weekly report summaries.
- TRADE OUTCOME: trade closed win/loss, R-multiple, percent result, and exit reason.

## Rate And Message Limits

- `ALERT_DAILY_MESSAGE_LIMIT` limits normal real Telegram messages.
- `ALERT_CRITICAL_BYPASS_DAILY_LIMIT=true` allows critical alerts to bypass the normal daily limit.
- `TELEGRAM_ALERT_SMOKE_MAX_MESSAGES` limits the gated smoke to at most three messages.

The implementation is in-memory and side-effect-limited. It does not add Redis or new
infrastructure.

## Safety Boundary

Alerting is operator-facing only. Telegram does not:

- enable live trading;
- enable autonomous execution;
- submit, cancel, replace, or modify broker orders;
- place or change stops;
- mutate strategy, risk, execution, universe, or kill-switch rules;
- call broker APIs;
- call AI/news providers;
- expose frontend secrets;
- implement Telegram commands or natural-language trading;
- start paper trading operations.

## Email/Resend Status

Email/Resend is deferred. It remains a possible future secondary channel for daily/weekly reports
and critical backup alerts only after paper evidence and/or profitability justification. Email
variables are not required for Milestone 23, and no real email delivery is implemented.

## Tests

Current alerting tests:

```bash
uv run --group dev pytest tests/unit/test_alerting.py tests/unit/test_telegram_alerting.py
uv run --group dev pytest tests/integration/test_telegram_alert_delivery_smoke.py
```

The integration smoke is skipped unless explicit real-delivery gates are present. Unit tests use
fake clients and do not call Telegram.
