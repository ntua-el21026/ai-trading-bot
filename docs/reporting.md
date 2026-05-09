# Reporting

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 15 adds local/fake-safe reporting foundations. Reports are generated from supplied
ledger/read-model snapshots, rendered deterministically, and persisted through the ledger repository.
Report generation does not call broker APIs, AI/news providers, market-data providers, alert
services, or managed databases by default.

Milestone 16 uses the daily report generator inside the fake/local paper dry-run path. Those reports
are generated from local ledger records created during the dry run and are not production paper
trading evidence.

Milestone 22 adds AI calibration report payloads and AI quality warning/event payloads. These are
reporting and safety-degradation artifacts only: they may recommend reduced influence, neutral-only
behavior, or escalation, but they cannot mutate strategy, risk, execution, stop policy, universe
membership, kill switches, or broker state.

Milestone 23 adds Telegram-safe daily and weekly report summaries plus trade win/loss summaries for
operator-facing alerts. These summaries are generated from report/trade outcome payloads and do not
send real Telegram messages unless the explicit Telegram delivery gates are loaded.

Milestone 25 surfaces report summaries through the dashboard/control-plane read model and smoke
harness. Dashboard report sections are read-only and may be empty or unavailable-safe when no local
ledger records exist; they do not generate new reports, send alerts, deploy a dashboard, or start
paper trading.

## Implemented

- `packages/reporting/models.py` defines daily/weekly report, section, metric, issue, snapshot, and
  generation-result models.
- `packages/reporting/generators.py` builds daily and weekly reports from typed snapshots.
- `packages/reporting/renderers.py` renders deterministic Markdown suitable for tests and audit
  storage plus concise Telegram-safe daily/weekly summaries.
- `packages/reporting/ledger.py` builds report snapshots from ledger repository reads and persists
  report records.
- `apps/workers/app/activities/reporting.py` exposes Temporal activity boundaries for daily/weekly
  report generation and dashboard snapshot reads.
- `packages/paper/dry_run.py` generates and persists a daily report as part of the fake/local
  end-to-end dry run.
- `packages/ai/feedback.py` builds AI calibration report payloads and AI quality event payloads
  that can be persisted through existing report/system-event ledger boundaries.
- `packages/alerting/templates.py` converts daily reports, weekly reports, and trade outcomes into
  concise Telegram alert messages.
- `packages/control_plane/runtime.py` validates that dashboard report summary sections are present
  in the dev runtime snapshot without calling report generation or alert delivery services.

Daily reports include workflow summary, candidates/signals, AI stats, decisions/rejections,
execution intents, orders/fills/positions, protective stops, reconciliation status, incidents,
risk/exposure, slippage diagnostics, and follow-ups.

Weekly reports include paper-trade summary, closed/open trade counts, execution diagnostics, stop
placement, mismatch rate, AI schema validity, incidents by severity, failed checks/rejections,
operational issues, and unresolved gaps.

## Safety Boundary

- Default reporting uses in-memory SQLite or caller-supplied local repositories in tests.
- Reports explicitly label missing evidence and do not claim profitability.
- Report activities return `external_calls_performed=false` by default.
- Report alert dispatch uses `FakeAlertAdapter` by default and does not call Telegram in default
  tests.
- Real operational reports still require managed database runtime integration and real paper run
  data.
- Real Telegram report delivery requires the explicit Telegram smoke/delivery gates and remains
  operator-facing only.
- Provider/OpenAI smoke results and AI calibration reports are not actual paper trading evidence,
  frozen paper evidence, or Level 4 readiness evidence by themselves.
- Live trading and autonomous execution remain disabled.

## Tests

Current reporting tests:

```bash
uv run --group dev pytest tests/unit/test_reporting.py tests/unit/test_reporting_activities.py
```

Dry-run report coverage is included in:

```bash
uv run --group dev pytest tests/unit/test_paper_dry_run_orchestration.py
```

These tests are fixture/local tests only. They are not paper trading evidence.
