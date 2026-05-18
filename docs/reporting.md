# Reporting

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md`.

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

Milestone 43 requires scale-in evidence and future frozen validation reports to distinguish
`initial_entry`, `scale_in_entry`, `initial_protective_stop`, `add_on_protective_stop`, `exit`,
`cleanup`, and `incident_repair`. Reports must be able to record scale-in count, success/failure,
total symbol quantity, protected quantity, scale-in incidents, and attribution notes when partial
scale-in exists.

Milestone 44 extends frozen-readiness reporting for v0.5. Frozen validation reports must include
validation-clock fields, flat-start baseline reference, signed quantity/position side, gross/net
long and short exposure, active exits, negative-only AI/news status, scale-in stage-gate status,
shorts-enabled status, and M45 blocker status. Carry-in fields may exist for historical reporting,
but the v0.5 validation start requires zero carry-in positions and zero open orders.

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

## Milestone 44D Reporting Expectations

v0.6 frozen paper reports must show whether long, short, and scale-in paths are active for the
validation window. Daily and weekly evidence should distinguish:

- long entries and protective sell stops;
- paper-only short entries, signed negative quantities, and protective buy stops;
- long scale-in add-on entries and additive protective sell stops;
- aggregate protected quantity versus open position quantity;
- final flat baseline evidence before M45 start;
- any emergency re-protection or cleanup incident.

Reports must continue to state that live trading, autonomous live execution, leverage, schedules,
frozen validation start, and Level 4 readiness are disabled until explicitly approved.

M44E reporting must additionally record the repaired scale-in add-on order shape, including that the
add-on used a broker-native OTO parent with an attached stop-loss child, the initial stop remained
open during add-on submission, aggregate protection passed, cleanup restored flat state, and M45
readiness remained gated by explicit operator approval.

## Milestone 45 Reporting Requirements

Frozen paper reports during the M45 window must include validation clock status, active spec
version, local schedule registry status, Tiingo EOD data gate status, full long universe, short
universe, paper-short enablement, live-shorting disabled status, long scale-in enablement, short
scale-in disabled status, AI negative-only status, broker baseline/reconciliation status, open
orders, positions, protective stop coverage, buy-stop coverage for shorts, additive stop coverage
for scale-ins, incidents, operator interventions, and blockers.

Daily and weekly reports must not claim Level 4 readiness, profitability proof, or live-readiness
until future milestones approve those claims.
