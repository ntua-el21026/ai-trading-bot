# Reporting

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 15 adds local/fake-safe reporting foundations. Reports are generated from supplied
ledger/read-model snapshots, rendered deterministically, and persisted through the ledger repository.
Report generation does not call broker APIs, AI/news providers, market-data providers, alert
services, or managed databases by default.

Milestone 16 uses the daily report generator inside the fake/local paper dry-run path. Those reports
are generated from local ledger records created during the dry run and are not production paper
trading evidence.

## Implemented

- `packages/reporting/models.py` defines daily/weekly report, section, metric, issue, snapshot, and
  generation-result models.
- `packages/reporting/generators.py` builds daily and weekly reports from typed snapshots.
- `packages/reporting/renderers.py` renders deterministic Markdown suitable for tests and audit
  storage.
- `packages/reporting/ledger.py` builds report snapshots from ledger repository reads and persists
  report records.
- `apps/workers/app/activities/reporting.py` exposes Temporal activity boundaries for daily/weekly
  report generation and dashboard snapshot reads.
- `packages/paper/dry_run.py` generates and persists a daily report as part of the fake/local
  end-to-end dry run.

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
- Real operational reports still require managed database runtime integration and real paper run
  data.
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
