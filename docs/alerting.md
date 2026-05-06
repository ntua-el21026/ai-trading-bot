# Alerting

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 15 adds alerting contracts and fake/fail-closed adapters. Default tests and default
activity wiring do not send Telegram, email, broker, AI/news, or other network messages.

Milestone 16 uses `FakeAlertAdapter` inside the fake/local paper dry-run path to capture order,
fill, incident, and report-generated alerts. No real alert delivery is enabled.

## Implemented

- `packages/alerting/models.py` defines alert severity, channels, categories, messages, dispatch
  requests, and dispatch results.
- `packages/alerting/routing.py` maps severity/category to channels and escalates critical
  categories such as missing protective stops, reconciliation mismatch, duplicate orders/intents,
  kill-switch activation, worker unavailability, and broker ambiguity.
- `packages/alerting/adapters.py` defines an adapter protocol, `FakeAlertAdapter`, and fail-closed
  Telegram/email adapter skeletons.
- `apps/workers/app/activities/reporting.py` exposes alert dispatch, incident-alert, and
  report-alert Temporal activity boundaries.
- `packages/paper/dry_run.py` captures fake dry-run alerts through `AlertRouter` and
  `FakeAlertAdapter`.

## Adapter Policy

- `FakeAlertAdapter` captures messages in memory and performs no external calls.
- Telegram and email skeletons fail closed when secrets/config are absent.
- Telegram and email skeletons also fail closed when config is supplied because network delivery is
  intentionally disabled in this milestone.
- No alert credentials are committed or required by default tests.
- Real alert delivery must be added in a later milestone with explicit configuration gates,
  delivery tests, and evidence capture.

## Safety Boundary

Alerting does not:

- enable live trading;
- enable autonomous execution;
- submit broker orders;
- call broker APIs;
- call AI/news providers;
- expose frontend secrets;
- start paper trading operations.
- call external alert services during dry-run orchestration.

## Tests

Current alerting tests:

```bash
uv run --group dev pytest tests/unit/test_alerting.py tests/unit/test_reporting_activities.py
```

These tests validate routing and fake/fail-closed behavior only. They are not real alert-delivery
evidence.
