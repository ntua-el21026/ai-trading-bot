# Temporal Workflows

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Through Milestone 26, the repository includes Temporal SDK scaffolding, worker bootstrap, workflow skeletons,
ledger-backed activity contracts using safe local/fake repositories, paper-only broker activity
contracts using fake Alpaca clients by default, reporting/alerting/dashboard read-model activity
contracts using local ledger repositories and fake alert adapters by default, fake/local paper
dry-run orchestration, managed Postgres/Supabase runtime helpers, provider placeholder activity
boundaries, Milestone 22 AI/news activity boundary names, Telegram alert delivery activity
boundaries behind explicit gates, Temporal Cloud dev client/runtime helpers, a default-refusing
Temporal Cloud smoke harness, signal names, query names, dashboard/control-plane signal mapping
contracts, a dashboard/control-plane dev runtime smoke harness, local Temporal SDK
test-environment coverage, and replay coverage for a generated
workflow history. It does not implement actual paper trading orchestration, default AI/provider
external calls, production schedule activation, browser-side Temporal calls, actual paper trading
operations, or live trading.

Milestone 43 scale-in support is currently a deterministic policy/helper boundary. A future
Temporal execution path may call it before add-on paper entries, but workflow code must still only
orchestrate deterministic state and call activities for side effects. M43 itself activates no
schedules and performs no broker writes.

## Configuration

`config/temporal.yaml` defines the namespace, task queue names, schedule names, and default retry
values from the latest spec. The typed config loader supports a Temporal service address and
defaults it to `localhost:7233` for local development. Temporal Cloud dev connections are built only
by explicit runtime helpers that require `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, and
`TEMPORAL_API_KEY`; the API key is never printed.

Task queues:

- `market-data-task-queue`
- `strategy-task-queue`
- `ai-research-task-queue`
- `execution-task-queue`
- `reconciliation-task-queue`
- `reporting-task-queue`

Execution-critical skeletons are registered on `execution-task-queue`; reconciliation skeletons are
registered on `reconciliation-task-queue`.

## Workflow Skeletons

- `DailyDataRefreshWorkflow`
- `EODSignalWorkflow`
- `AIShortlistResearchWorkflow`
- `DecisionWorkflow`
- `ExecutionIntentWorkflow`
- `OrderLifecycleWorkflow`
- `PositionLifecycleWorkflow`
- `ReconciliationWorkflow`
- `KillSwitchWorkflow`
- `ReportingWorkflow`

Workflow code is limited to deterministic orchestration state, Temporal signals, Temporal queries,
and Temporal activity calls. The skeletons call ledger activity boundaries by name and return status
objects. They do not import ledger repositories or database sessions directly.

## Activity Boundary

Current activity contracts are registered from `apps/workers/app/activities/contracts.py`.
Ledger-backed activity implementations live in `apps/workers/app/activities/ledger.py`; typed
ledger request/response models live in `apps/workers/app/activities/models.py`; fake/local service
helpers live in `apps/workers/app/activities/fakes.py`. Paper broker activity contracts live in
`apps/workers/app/activities/broker.py` and default to `FakeAlpacaClient`. Reporting, alerting, and
dashboard read-model activity contracts live in `apps/workers/app/activities/reporting.py` and
default to local SQLite ledger repositories plus fake alert adapters.

Milestone 13 adds safe ledger activity boundaries for:

- raw provider payload persistence;
- data-refresh persistence checkpoints;
- trade candidate persistence;
- AI research output persistence;
- trade decision persistence;
- risk-check persistence;
- execution intent persistence;
- order/fill/position audit persistence;
- broker reconciliation snapshot persistence;
- system event/incident persistence;
- report persistence;
- read helpers for latest reconciliation status, active execution intents, open positions, and
  recent incidents.

The default activity service uses in-memory SQLite through `packages/ledger` and requires no
`DATABASE_URL`. This is local/fake-safe integration, not managed Postgres/Supabase runtime wiring.
All activity results keep `external_calls_performed=false`.

Milestone 14 adds fake-safe paper broker activity boundaries for:

- broker account snapshots;
- broker order, position, and fill snapshots;
- broker order lookup by broker ID and `client_order_id`;
- paper entry-order submit boundary;
- paper order cancel boundary;
- paper protective-stop submit/verify boundaries;
- Alpaca trade-update mapping.

These activities are registered with the worker but default to a fake adapter. They are not wired
into a live/paper order-submission workflow path and do not call Alpaca in default tests.

Milestone 15 adds fake/local reporting and alerting activity boundaries for:

- daily report generation and ledger persistence;
- weekly report generation and ledger persistence;
- alert dispatch through fake/fail-closed adapters;
- incident alert dispatch;
- report-generated alert dispatch;
- dashboard snapshot construction from ledger read models.

The `ReportingWorkflow` now calls the `generate_daily_report` activity by stable name while keeping
workflow code deterministic and free of database, alert, broker, AI/news, network, wall-clock, and
random imports. The activity performs local ledger reads/writes and returns
`external_calls_performed=false` by default.

Milestone 23 extends the alerting activity boundary with a server-side, gated Telegram adapter and
Telegram-safe report/trade/incident summaries. Default activity wiring still uses
`FakeAlertAdapter`, so local tests perform no Telegram calls. Real Telegram delivery can occur only
through activity/adapter code when explicit delivery gates are loaded; workflow modules still do not
import Telegram clients, network libraries, alert adapters, environment variables, or secrets.

Milestone 16 adds `packages/paper/` as a fake/local dry-run orchestration service. It may call
existing activity-adjacent package boundaries directly for local validation, but it does not require
a live Temporal server and does not activate schedules. Workflow code remains deterministic and
continues to avoid direct database, broker, AI/news, provider, network, clock, or random side
effects.

Milestone 19 adds local Temporal SDK test-environment coverage under `tests/temporal/`. The tests
start the SDK test server, register workers on configured task queues, execute every registered
workflow skeleton with fake/local activities, exercise signal/query contracts for kill switch,
reconciliation, and reporting workflows, and replay a generated `KillSwitchWorkflow` history with
Temporal's replayer. These tests do not connect to Temporal Cloud, do not activate production
schedules, do not require managed database credentials, and do not call broker, AI/news, market-data,
alert, or dashboard services.

Milestone 24 adds Temporal Cloud dev runtime helpers and `scripts/check_temporal_cloud_runtime.py`.
The smoke refuses by default. A real dev-namespace connection requires:

- `RUN_TEMPORAL_CLOUD_SMOKE=1`
- `TEMPORAL_CLOUD_SMOKE_CONFIRM=CONNECT_DEV_NAMESPACE_ONLY`
- `TEMPORAL_ADDRESS`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_API_KEY`

Optional smoke selectors are `TEMPORAL_CLOUD_SMOKE_TASK_QUEUE` and
`TEMPORAL_CLOUD_SMOKE_WORKFLOW`. The only supported workflow for this smoke is
`KillSwitchWorkflow`; activity execution uses a smoke-only fake `persist_system_event` activity.
The smoke creates no schedules, activates no schedules, calls no brokers, calls no AI/news
providers, sends no alerts, and starts no paper trading operations.

Milestone 06 adds placeholder boundaries for:

- broker reconciliation snapshot retrieval;
- internal ledger snapshot retrieval;
- reconciliation snapshot comparison.

Milestone 07 adds placeholder boundaries for:

- deterministic-shortlist candidate news retrieval;
- AI trade-research execution;
- AI output validation;
- AI research payload storage.

Milestone 22 adds explicit AI/news activity boundary names for:

- shortlist news retrieval;
- Marketaux news retrieval;
- Alpha Vantage news retrieval;
- OpenAI web fallback;
- news payload persistence;
- AI research output persistence;
- AI calibration report generation.

Provider-facing activities remain fake/refuse placeholders by default. Real Marketaux, Alpha
Vantage, OpenAI structured-output, or OpenAI web-search calls must be injected only through activity
implementations after explicit smoke gates are present. Workflow code still calls activities by name
and performs no broker API, AI API, news API, database, websocket, or REST calls directly.

Future real side effects must stay in activities:

- broker API calls;
- database writes;
- AI API calls;
- news/data provider calls;
- alert delivery;
- wall-clock reads;
- non-deterministic I/O.

Workflow code must not perform those side effects directly.

## Signals

Required signal contract names are defined in `apps/workers/app/signals.py`:

- `manual_kill_switch`
- `manual_pause_new_risk`
- `manual_resume_after_review`
- `force_reconciliation`
- `force_report`
- `approve_level_change`
- `acknowledge_incident`

The kill-switch skeleton records deterministic state transitions that block new risk while
preserving risk-reducing exits.

Dashboard/control-plane actions map only to safe signal names through server-side contracts under
`apps/api/app/control_plane.py`. The Milestone 25 dev runtime smoke validates these mappings through
a fake dispatcher by default; browser/dashboard code must not call Temporal directly.
Milestone 26 keeps Vercel dashboard-only: the static preview does not run workers, connect to
Temporal from browser code, activate schedules, or expose Temporal credentials. Milestone 27
readiness aggregation checks Temporal local/Cloud evidence and schedule status as read-only
evidence; it does not connect to Temporal Cloud, create schedules, activate schedules, or run paper
operation workflows by default.

## Queries

Required query contract names are defined in `apps/workers/app/queries.py`:

- `get_current_system_state`
- `get_active_workflows`
- `get_active_execution_intents`
- `get_open_order_lifecycles`
- `get_open_position_lifecycles`
- `get_recent_incidents`
- `get_last_reconciliation_status`
- `get_kill_switch_state`

## Retry Contracts

Retry policy contracts are defined in `apps/workers/app/retry_policies.py`:

- default non-critical activity retry from config;
- broker order submit placeholder with `maximum_attempts=1` and an idempotency lookup flag;
- protective stop retry placeholder;
- AI retry placeholder with neutral fallback metadata.

These are contracts only. Broker order submission retry remains capped at one attempt; Milestone 14
adds fake-tested idempotency lookup by `client_order_id`, but end-to-end retry orchestration through
Temporal remains deferred. AI activity retry is represented as a contract with neutral fallback on
failure.

## Local Worker Bootstrap

Start one worker for a configured queue after a local Temporal service is available:

```bash
uv run python scripts/start_worker.py --task-queue execution-task-queue
```

Schedule creation remains dry-run only in the current implementation:

```bash
uv run python scripts/seed_temporal_schedules.py
```

## Temporal Cloud Dev Smoke

Default refusal:

```bash
uv run python scripts/check_temporal_cloud_runtime.py
```

When the explicit dev smoke gates are loaded in a local child process, the same script connects to
the configured Temporal Cloud dev namespace, starts a temporary worker with fake/local activity
behavior, runs a harmless `KillSwitchWorkflow`, checks signal/query behavior when feasible, and
returns sanitized evidence only. It is not production schedule activation, not actual paper trading,
not frozen paper evidence, and not Level 4 readiness.

## Testing

Current tests include import/static contracts, local Temporal SDK test-environment execution, and
workflow replay coverage:

```bash
uv run --group dev pytest tests/unit tests/temporal
```

Milestone 14 statically checks that workflow modules do not directly import broker clients,
broker SDKs, AI/news, ledger/database, network-provider, wall-clock, or random side-effect code.
Side effects remain activity responsibilities.

Milestone 15 adds fixture tests for report activities, alert dispatch activities, dashboard snapshot
activity output, and workflow activity-name alignment.

Milestone 16 adds fake/local dry-run orchestration tests and CLI safety tests.

Milestone 19 adds the real SDK test-server and replay tests:

```bash
uv run --group dev pytest tests/temporal -vv
```

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires real Temporal query/signal backend evidence before
Level 4 micro-live. Current workflow tests include local SDK test-server signal/query coverage and
replay evidence, and the Milestone 24 harness has gathered dev-namespace Cloud smoke evidence
through explicit gates. Production schedule activation, actual paper operations, and Level 4
readiness remain deferred.
