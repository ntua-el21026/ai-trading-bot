# Temporal Workflows

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 13 includes Temporal SDK scaffolding, worker bootstrap, workflow skeletons, ledger-backed
activity contracts using safe local/fake repositories, provider placeholder activity boundaries,
signal names, query names, dashboard/control-plane signal mapping contracts, validation-oriented
workflow boundary tests, and contract tests. It does not implement broker execution, managed
Postgres/Supabase runtime wiring, AI calls, market/news provider calls, production schedule
activation, browser-side Temporal calls, paper orders, or live trading.

## Configuration

`config/temporal.yaml` defines the namespace, task queue names, schedule names, and default retry
values from the latest spec. The typed config loader also supports a Temporal service address and
defaults it to `localhost:7233` for local development.

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
request/response models live in `apps/workers/app/activities/models.py`; fake/local service helpers
live in `apps/workers/app/activities/fakes.py`.

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

Milestone 06 adds placeholder boundaries for:

- broker reconciliation snapshot retrieval;
- internal ledger snapshot retrieval;
- reconciliation snapshot comparison.

Milestone 07 adds placeholder boundaries for:

- deterministic-shortlist candidate news retrieval;
- AI trade-research execution;
- AI output validation;
- AI research payload storage.

Provider-facing activities remain placeholders only. Workflow code still calls activities by name
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
`apps/api/app/control_plane.py`. Browser/dashboard code must not call Temporal directly.

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

These are contracts only. They do not implement broker, stop, or provider-backed AI behavior. Broker
order submission retry remains capped at one attempt until a later milestone adds explicit
idempotency lookup behavior through broker and managed database activities. AI activity retry is
represented as a contract with neutral fallback on failure.

## Local Worker Bootstrap

Start one worker for a configured queue after a local Temporal service is available:

```bash
uv run python scripts/start_worker.py --task-queue execution-task-queue
```

Schedule creation remains dry-run only in the current implementation:

```bash
uv run python scripts/seed_temporal_schedules.py
```

## Testing

Current tests are import and contract tests:

```bash
uv run --group dev pytest tests/unit tests/temporal
```

Milestone 13 also statically checks that workflow modules do not directly import broker, AI/news,
ledger/database, network-provider, wall-clock, or random side-effect code. Side effects remain
activity responsibilities.

Full Temporal replay or local test-server execution is deferred. A future command should use
Temporal's testing environment, for example:

```bash
uv run --group dev pytest tests/temporal --run-temporal-server
```

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires real Temporal query/signal backend evidence before
Level 4 micro-live. Current workflow tests are import/static contract tests only; real test-server
or replay evidence, live worker evidence, and production schedule activation remain deferred.
