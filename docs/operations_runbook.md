# Operations Runbook

This document is a foundation placeholder for operations.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 22 does
not implement production services, active schedules, actual paper trading runs, real AI/news
provider/API smoke evidence by default, production Temporal query/signal backend integration, real
alert delivery, dashboard deployment, Level 4 live readiness evidence, or live trading. It does
define passive broker/reconciliation, fake-tested paper Alpaca boundaries, opt-in read-only Alpaca
paper smoke tooling, a default-refusing gated Alpaca paper order-lifecycle smoke harness, AI/news, reporting,
alerting, dashboard/control-plane, validation/testing contracts, fake/local paper dry-run
orchestration, explicit Postgres/Supabase runtime migration/check helpers with second opt-in gates,
opt-in managed repository CRUD validation, local Temporal SDK test-server/replay coverage, paper
trading operations documentation, Level 4 readiness documentation with incident/fallback
recommendations, Marketaux/Alpha Vantage provider-first news boundaries, OpenAI structured-analysis
and disabled web-fallback boundaries, AI feedback/calibration safety downgrades, a local
database/audit-ledger foundation, and safe Temporal activity boundaries backed by local/fake
repositories.

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

A future real paper write smoke requires all explicit gates loaded before the command starts:

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

No current operation sends real alerts, deploys the dashboard, activates schedules, starts paper
trading operations, or completes Level 4 readiness.

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

Reporting and alerting are currently local/fake-safe boundaries:

1. Generate daily or weekly reports from supplied ledger/read-model snapshots through
   `packages.reporting`.
2. Render deterministic Markdown and persist report payloads through the ledger repository.
3. Dispatch alerts through `AlertRouter` with `FakeAlertAdapter` by default.
4. Treat Telegram/email adapters as fail-closed skeletons until a future approved milestone adds
   real delivery configuration and tests.
5. Use `apps/workers/app/activities/reporting.py` for Temporal activity boundaries that report
   `external_calls_performed=false` in default tests.

No current operation sends Telegram/email messages, calls external alert services, claims production
reporting evidence, or starts paper trading operations.

## Current Dashboard Operations

Dashboard/control-plane behavior is currently contract-only:

1. Read dashboard snapshots from fixture providers or the local ledger-backed read-model provider.
2. Represent safe manual controls as auditable command objects.
3. Map safe controls to existing Temporal signal names through server-side contracts.
4. Expose only explicitly safe public dashboard environment values.

No current dashboard operation submits broker orders, calls broker APIs, calls AI/news providers,
calls Temporal from browser code, sends alerts, exposes broker/AI provider secrets, or changes
risk/autonomy configuration.

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

Later milestones must implement real worker startup, Temporal schedules, an explicitly gated real
Alpaca paper order-lifecycle smoke run if not already captured, actual paper trading orchestration,
real AI/news provider setup, production
managed database activity wiring, production Temporal query/signal backend integration, dashboard
deployment, real alert delivery, evidence collection, and Level 4 micro-live readiness gates.
