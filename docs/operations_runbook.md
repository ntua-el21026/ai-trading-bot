# Operations Runbook

This document is a foundation placeholder for operations.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.4.md`. Milestone 27 does
not implement production services, active schedules, actual paper trading runs, real AI/news
provider/API calls by default, production schedule activation, dashboard deployment, Level 4 live
readiness evidence, or live trading. It does
define passive broker/reconciliation, fake-tested paper Alpaca boundaries, opt-in read-only Alpaca
paper smoke tooling, a default-refusing gated Alpaca paper order-lifecycle smoke harness, AI/news, reporting,
alerting, dashboard/control-plane, validation/testing contracts, fake/local paper dry-run
orchestration, explicit Postgres/Supabase runtime migration/check helpers with second opt-in gates,
opt-in managed repository CRUD validation, local Temporal SDK test-server/replay coverage, paper
trading operations documentation, Level 4 readiness documentation with incident/fallback
recommendations, Marketaux/Alpha Vantage provider-first news boundaries, OpenAI structured-analysis
and disabled web-fallback boundaries, AI feedback/calibration safety downgrades, a local
database/audit-ledger foundation, and safe Temporal activity boundaries backed by local/fake
repositories. It also adds a Telegram-only real alert delivery harness behind explicit gates while
keeping Email/Resend deferred, plus a Temporal Cloud dev smoke harness that refuses by default and
uses fake/local activities only. Milestone 25 adds dashboard/control-plane dev runtime wiring with
fake/local read models, safe control validation, fake/default dispatch, and a smoke harness that
does not deploy or perform external side effects.
Milestone 26 adds a dashboard-only Vercel preview harness with static output and no workers,
execution services, schedules, secrets, broker calls, AI/news calls, or alerts.
Milestone 27 adds a controlled paper operations readiness harness that aggregates existing local
status and documented smoke evidence only. It does not start paper trading, activate schedules,
submit broker orders, call providers, send real alerts, or deploy anything.
Milestone 43 adds deterministic scale-in policy support with fake/stub tests only. Operators must
not run a real scale-in order, submit an add-on stop, cancel/replace stops, activate schedules, or
start the frozen validation clock as part of M43.

## Current Foundation Operations

1. Install dependencies with `uv sync --dev`.
2. Validate configuration with `uv run pytest tests/unit/test_config.py`.
3. Keep `.env` files local and uncommitted.
4. Treat `.env.example` as variable names only.

## Current Reconciliation Operations

Broker reconciliation is currently a pure comparison contract:

1. Build a normalized broker snapshot from fixture, stream, or future REST activity output.
2. Build a passive internal ledger snapshot from fixture or future database activity output.
3. Compare snapshots with `compare_broker_and_internal`.
4. Treat critical incidents as pause-new-risk recommendations.
5. Treat missing protective stops according to the configured warning, critical, and flatten
   thresholds.
6. For scale-in validation, treat summed verified protective-stop quantity below open position
   quantity as a critical mismatch that blocks new risk.

Milestone 14 includes fake-client submit/cancel/protective-stop boundaries, but no current operation
submits, cancels, or flattens real broker orders. Flattening is represented only as a
`flatten_if_safe` recommendation for later execution workflow handling.

## Current Broker Operations

Paper broker behavior is currently fake-client and contract based:

1. Use `FakeAlpacaClient` for local account, order, fill, position, stream, and REST fallback tests.
2. Use `AlpacaPaperAdapter` only with `system.environment="paper"` and live-order flags disabled.
3. Runtime adapter construction requires explicit paper credentials and an injected client.
4. Broker activities under `apps/workers/app/activities/broker.py` default to the fake adapter.
5. Optional read-only Alpaca paper smoke requires explicit gates and calls only read-only endpoints.
6. Optional Alpaca paper order-lifecycle smoke harness refuses by default and requires separate
   explicit write-smoke gates before any paper write-capable call.

Default tests do not call Alpaca, do not require credentials, and do not submit real paper or live
orders.

## Current Alpaca Read-Only Smoke Operations

The read-only paper smoke validates only account, open-order, position, and clock/status reads:

```bash
RUN_ALPACA_PAPER_SMOKE=1 \
ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT \
ALPACA_BASE_URL=https://paper-api.alpaca.markets \
  uv run python scripts/check_alpaca_paper_readonly.py
```

The command must be run only after loading local paper credentials outside the repository. It
requires `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, the exact paper base URL, live trading disabled,
autonomous execution disabled, live orders disabled, and adapter live-mode refusal. It prints
sanitized status fields only and no raw broker payloads or credentials.

Latest Milestone 20 audit status: the read-only smoke passed after corrected local paper credentials
were loaded. The sanitized summary confirmed the paper base URL, reachable and mapped account,
open-order, position, and clock/status reads, and no write operations attempted.

Forbidden operations for this smoke:

- submit order;
- cancel order;
- replace order;
- place protective stop;
- close or liquidate position;
- use any live endpoint;
- call any POST, PATCH, or DELETE broker endpoint.

## Current Alpaca Paper Order-Lifecycle Smoke Operations

Milestone 21A adds a harness for one controlled paper order lifecycle, but it refuses by default:

```bash
uv run python scripts/check_alpaca_paper_order_lifecycle.py
```

Expected default result: sanitized refusal, no order submitted, no cancellation, no protective stop,
no cleanup exit, and no broker write endpoint called.

The controlled Milestone 21B real paper write smoke has completed successfully through the gated
harness with final target-symbol state clean/flat. A repeat real paper write smoke still requires
all explicit gates loaded before the command starts:

- `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1`
- `ALPACA_PAPER_ORDER_LIFECYCLE_CONFIRM=SUBMIT_AND_CLEAN_UP_TINY_PAPER_ORDER`
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_PAPER_ORDER_SMOKE_SYMBOL`
- `ALPACA_PAPER_ORDER_SMOKE_MAX_QTY`
- `ALPACA_PAPER_ORDER_SMOKE_MAX_NOTIONAL_USD`
- `ALPACA_PAPER_ORDER_SMOKE_TIMEOUT_SECONDS`

The harness also validates paper environment config, live trading disabled, autonomous execution
disabled, live orders disabled, execution-intent/risk/reconciliation/stop requirements, approved
live-universe equity/ETF scope, quantity `<= 1`, notional `<= 1000`, timeout `<= 180` seconds, and
absence of pre-existing target-symbol broker orders or positions.

This harness is not paper trading. It is not frozen paper evidence, does not activate Temporal
schedules, does not route through autonomous strategy execution, does not call AI/news providers,
does not send alerts, does not deploy the dashboard, does not use live Alpaca, and does not satisfy
Level 4 readiness.

## Current Controlled Paper Operations Readiness

Milestone 27 provides a read-only readiness aggregation command:

```bash
uv run python scripts/check_paper_operations_readiness.py
```

The command checks local config safety invariants and aggregates evidence for managed database
validation, Temporal local/Cloud dev status, Alpaca read-only and controlled lifecycle smokes,
AI/news provider and OpenAI smokes, Telegram alert smoke, dashboard/control-plane smoke, and Vercel
dashboard deployment audit status. It may call only local/fake read-model helpers by default. It
does not invoke the Alpaca order-lifecycle smoke, AI/news external smokes, Telegram delivery smoke,
schedule activation, paper trading workflows, or deployment.

The readiness result distinguishes readiness for a future first controlled paper session from
actual paper operations. Actual paper trading remains not started, frozen paper evidence remains
absent, and Level 4 remains not ready.

## Current AI And News Operations

AI/news intelligence is server-side and explicitly gated for real external calls:

1. Request ticker-tagged news only for deterministic shortlist symbols.
2. Use Marketaux as primary provider and Alpha Vantage as fallback/cross-check provider.
3. Enforce daily request budgets before real provider requests.
4. Normalize and deduplicate articles and persist/hash raw payloads through ledger boundaries where
   feasible.
5. Build a versioned prompt and validate strict OpenAI structured JSON output.
6. Keep OpenAI web fallback disabled by default and exception-only when explicitly allowed.
7. Generate AI calibration reports and safety-state downgrade recommendations.

Default tests and default activity implementations use fixtures/fakes or refuse safely. Real
provider/OpenAI smoke tests require explicit gates:

- `RUN_NEWS_PROVIDER_SMOKE=1`
- `NEWS_PROVIDER_SMOKE_CONFIRM=FETCH_SHORTLIST_NEWS_ONLY`
- `RUN_OPENAI_MODEL_LIST_SMOKE=1`
- `OPENAI_MODEL_LIST_CONFIRM=LIST_AVAILABLE_MODELS_ONLY`
- `RUN_OPENAI_AI_SMOKE=1`
- `OPENAI_AI_SMOKE_CONFIRM=STRUCTURED_OUTPUT_SHORTLIST_NEWS_ONLY`
- `RUN_OPENAI_WEB_FALLBACK_SMOKE=1`
- `OPENAI_WEB_FALLBACK_CONFIRM=AUDITED_EXCEPTION_ONLY_WEB_SEARCH`

AI may:

- classify catalysts and adverse risks;
- produce `ai_score`, `hard_block`, and `size_multiplier <= 1.0`;
- produce reports, warnings, and escalation recommendations;
- reduce or neutralize AI influence when calibration quality degrades.

AI may not:

- create or modify orders;
- change stops;
- mutate strategy, risk, execution, universe, or kill-switch rules;
- increase position size above deterministic caps;
- access broker credentials;
- call broker APIs.

AI/news operations do not send real alerts, deploy the dashboard, activate schedules, start paper
trading operations, or complete Level 4 readiness.

## Current Ledger Operations

Database/audit-ledger behavior is currently a local persistence foundation:

1. Review Postgres-target DDL in `db/migrations/0001_initial_audit_ledger.sql`.
2. Use `packages.ledger.connect_in_memory_sqlite()` only for local deterministic tests.
3. Use `SQLiteLedgerRepository` against an explicit SQLite connection; it does not read
   `DATABASE_URL`.
4. Preserve raw provider payloads, raw AI prompt/output hashes, execution intent IDs, client order
   IDs, broker snapshots, system events, and report payloads when exercising repository tests.

No default operation opens a managed Postgres/Supabase connection, runs production migrations, or
requires real database credentials.

## Current Managed Database Runtime Operations

Managed Postgres/Supabase support is prepared but opt-in:

1. Store `DATABASE_URL` outside the repository.
2. Dry-run migration target validation:

```bash
DATABASE_URL="postgresql://..." uv run python scripts/apply_ledger_migrations.py
```

3. Apply the migration only after confirming the redacted target:

```bash
RUN_MANAGED_DB_TESTS=1 \
LEDGER_MIGRATION_CONFIRM=APPLY_TO_DEV_DATABASE \
DATABASE_URL="postgresql://..." \
  uv run python scripts/apply_ledger_migrations.py --apply
```

4. Validate expected tables:

```bash
RUN_MANAGED_DB_TESTS=1 DATABASE_URL="postgresql://..." \
  uv run python scripts/check_ledger_database.py --list-tables
```

5. Run managed repository CRUD validation only against a development target after migration:

```bash
RUN_MANAGED_DB_TESTS=1 DATABASE_URL="postgresql://..." \
  uv run --group dev pytest tests/integration/test_managed_ledger_crud.py
```

The scripts require explicit `DATABASE_URL`, reject obvious placeholders, enforce the opt-in gates,
and never print credentials. The CRUD test writes isolated fixture records inside rollback
transactions and never truncates or deletes arbitrary rows. These commands do not call brokers,
AI/news providers, alert services, Temporal schedules, dashboard deployment, or trading code.

## Current Temporal Ledger Activity Operations

Temporal ledger activities are currently local/fake-safe boundaries:

1. Workflow skeletons call stable ledger activity names such as `persist_execution_intent`,
   `persist_order_event`, `persist_broker_reconciliation`, `persist_system_event`, and
   `persist_report`.
2. Activity implementations use `LedgerActivityService` and `SQLiteLedgerRepository` by default.
3. Tests may inject a fake/local service through `build_fake_ledger_activity_service`.
4. Activity results report `external_calls_performed=false`.

These activities persist to local SQLite during tests. They do not call broker APIs, AI/news
providers, managed databases, alerts, or frontend code.

## Current Temporal Test Environment Operations

Temporal SDK test-environment coverage is available for local validation:

```bash
uv run --group dev pytest tests/temporal -vv
```

The tests start Temporal's local SDK test server, register workers on the configured task queues,
execute every workflow skeleton with fake/local activities, exercise kill-switch, reconciliation,
and reporting signal-query contracts, and replay a generated kill-switch workflow history. They do
not connect to Temporal Cloud, do not activate production schedules, do not require managed database
credentials, and do not call broker, AI/news, market-data, alert, dashboard, or trading services.

## Current Temporal Cloud Dev Runtime Operations

Temporal Cloud runtime wiring is explicitly gated and safe by default:

```bash
uv run python scripts/check_temporal_cloud_runtime.py
```

With no gates loaded, the command refuses before connecting to Temporal Cloud. A real dev-namespace
smoke requires `RUN_TEMPORAL_CLOUD_SMOKE=1`,
`TEMPORAL_CLOUD_SMOKE_CONFIRM=CONNECT_DEV_NAMESPACE_ONLY`, `TEMPORAL_ADDRESS`,
`TEMPORAL_NAMESPACE`, and `TEMPORAL_API_KEY`. Optional selectors are
`TEMPORAL_CLOUD_SMOKE_TASK_QUEUE` and `TEMPORAL_CLOUD_SMOKE_WORKFLOW`; the only supported smoke
workflow is `KillSwitchWorkflow`.

When gated, the smoke connects to the configured Temporal Cloud dev namespace using API-key/TLS
client construction, starts temporary workers with a fake smoke-only activity, runs a harmless
kill-switch workflow, checks signal/query behavior when feasible, prints sanitized evidence only,
and creates or activates no schedules. It does not call broker APIs, AI/news providers, alert
adapters, managed databases, dashboard services, or paper trading code.

## Current Temporal Broker Activity Operations

Temporal broker activities are currently fake-safe boundaries:

1. Activity names are registered for broker snapshots, broker lookups, paper entry submit, paper
   cancel, paper protective-stop submit/verify, and trade-update mapping.
2. The default service uses `build_fake_alpaca_paper_adapter`.
3. Activity results report `external_calls_performed=false` in default tests.
4. Workflow modules do not import broker SDKs or clients directly.

These activities are not yet connected to a real order lifecycle workflow that can submit paper
orders.

## Current Paper Dry-Run Operations

The current executable dry-run is fake/local only:

1. Run `uv run python scripts/run_paper_dry_run.py`.
2. Confirm the output warning: `This is a fake/local dry run. No broker orders are submitted.`
3. Review the returned `DryRunResult` for fake broker mode, no external calls, report ID, dashboard
   snapshot status, reconciliation status, and captured fake alerts.

The dry run uses `packages/paper/`, in-memory SQLite, fixture data, neutral/fake AI output,
`FakeAlpacaClient`, `FakeAlertAdapter`, daily report generation, and ledger-backed dashboard read
models. It does not call Alpaca, AI/news, market-data, Telegram/email, managed Postgres/Supabase, or
Temporal services, and it does not submit real paper or live broker orders.

## Current Reporting And Alerting Operations

Reporting and alerting are local/fake-safe by default, with a gated Telegram real-delivery harness:

1. Generate daily or weekly reports from supplied ledger/read-model snapshots through
   `packages.reporting`.
2. Render deterministic Markdown and persist report payloads through the ledger repository.
3. Dispatch alerts through `AlertRouter` with `FakeAlertAdapter` by default.
4. Use `TelegramAlertAdapter` only server-side and only when the explicit real-delivery gates are
   loaded.
5. Treat Email/Resend as deferred optional future secondary delivery.
6. Use `apps/workers/app/activities/reporting.py` for Temporal activity boundaries that report
   `external_calls_performed=false` in default tests.

The Telegram smoke command is:

```bash
uv run python scripts/check_telegram_alert_delivery.py
```

With no gates loaded, it refuses safely. Real Telegram smoke delivery requires
`ALERT_PROVIDER_PRIMARY=telegram`, `ALERT_ENABLE_REAL_DELIVERY=true`, Telegram token/chat presence,
`RUN_TELEGRAM_ALERT_SMOKE=1`,
`TELEGRAM_ALERT_SMOKE_CONFIRM=SEND_TEST_ALERT_TO_OPERATOR`, and
`TELEGRAM_ALERT_SMOKE_MAX_MESSAGES<=3`. It prints sanitized summary fields only.

No current alert operation starts paper trading, modifies risk/execution/stops, acts on Telegram
commands, deploys anything, or satisfies Level 4 readiness.

## Current Dashboard Operations

Dashboard/control-plane behavior is server-side and safe by default:

1. Read dashboard snapshots from fixture providers or the local ledger-backed read-model provider.
2. Represent safe manual controls as auditable command objects.
3. Map safe controls to existing Temporal signal names through server-side contracts.
4. Expose only explicitly safe public dashboard environment values.
5. Validate dev runtime behavior with `scripts/check_dashboard_control_plane_runtime.py`.

No current dashboard operation submits broker orders, calls broker APIs, calls AI/news providers,
calls Temporal from browser code, sends alerts, exposes broker/AI provider secrets, or changes
risk/autonomy configuration.

Default dashboard smoke behavior:

```bash
uv run python scripts/check_dashboard_control_plane_runtime.py
```

This builds a fake/local snapshot, validates required dashboard sections, validates safe control
requests, dispatches through the fake dispatcher, and prints sanitized status only. Real Temporal
control signals are disabled by default. Managed DB dashboard runtime and Vercel preview deployment
are refused by this dev runtime smoke; Vercel preview uses the separate Milestone 26 harness.

Dashboard preview behavior:

```bash
npm run build
uv run python scripts/check_vercel_dashboard_preview.py
```

The preview check validates that Vercel is dashboard-only, workers and backend packages are
excluded, only safe public environment values are used, no frontend secrets are referenced, no
order-entry UI exists, and no browser-side broker, Temporal, AI/news, database, or alert calls are
present. A Vercel preview may be created only after the explicit preview gates are loaded. Do not
run `vercel --prod`; the generated preview URL is sufficient and no custom domain is required.

Milestone 26B deployment evidence:

- Preview deployment: `https://ai-trading-cy85e5pf1-michael-peppas-projects.vercel.app`.
- Accidental production deployment:
  `https://ai-trading-qxid0g5t8-michael-peppas-projects.vercel.app`.
- Accidental production alias: `https://ai-trading-bot-silk.vercel.app`.
- Audit result: the production alias served the static/read-only dashboard. The deployment-specific
  preview and production URLs were Vercel-ready but anonymously protected with HTTP 401.
- No workers, execution services, backend runtime, frontend secrets, order-entry controls, or
  browser-side broker/AI/news/Temporal/database/Telegram privileged calls were verified in the
  dashboard artifact.

Future production deployments require explicit approval/gates. Preview-only milestones must not run
`vercel --prod`.

## Current Validation Operations

Validation is currently fixture and contract based:

1. Use `build_default_validation_harness_config` to inspect the spec-defined historical split,
   benchmark, fee/slippage, ablation, and Monte Carlo placeholder assumptions.
2. Use `default_failure_simulation_scenarios` to verify that required failure cases are represented
   without external calls.
3. Use `evaluate_paper_dry_run` to validate paper dry-run safety inputs without broker submission.
4. Run validation-focused tests with:

```bash
uv run --group dev pytest tests/unit/test_validation_harness.py tests/unit/test_failure_simulations.py tests/unit/test_paper_dry_run.py tests/temporal/test_workflow_contracts.py
```

These checks are operational rehearsal and contract validation only. They are not backtest,
paper-trading, or live-profitability evidence.

## Paper Trading Runbook

Paper operations are documented in `docs/paper_trading_runbook.md`.

Supporting documentation-only artifacts:

- `docs/checklists/paper_daily_checklist.md`
- `docs/checklists/paper_weekly_review.md`
- `docs/templates/paper_daily_report_template.md`
- `docs/templates/paper_incident_report_template.md`

The runbook covers paper setup constraints, daily/weekly procedures, monitoring, incident response,
reporting expectations, frozen paper acceptance criteria, and paper-to-Level-4 handoff gates. It is
target-state readiness documentation only. It does not start paper trading operations, call real
broker APIs by default, start provider integrations, enable live trading, or prove profitability.

## Level 4 Micro-Live Readiness

Level 4 readiness documentation is in `docs/level4_micro_live_readiness.md`.

Supporting documentation-only artifacts:

- `docs/checklists/level4_micro_live_readiness_checklist.md`
- `docs/checklists/credential_separation_checklist.md`
- `docs/checklists/kill_switch_rearm_checklist.md`
- `docs/templates/level4_micro_live_go_no_go_template.md`

Current conclusion: Level 4 micro-live is not ready. The readiness documents define evidence gates,
config review, credential separation, kill-switch/manual re-arm tests, reconciliation evidence,
protective-stop evidence, slippage/fill-quality evidence, dashboard evidence, and final go/no-go
records. They do not enable live trading or autonomous live execution.

## Future Operations Scope

Later milestones must implement real worker startup for actual paper operations, explicitly gated
Temporal schedule activation, actual paper trading orchestration, production managed database
activity wiring, production dashboard deployment, evidence collection, frozen paper acceptance, and
Level 4 micro-live readiness gates.
