# Temporal Workflows

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 09 includes Temporal SDK scaffolding, worker bootstrap, workflow skeletons, activity
contracts, signal names, query names, broker-reconciliation activity boundaries, AI/news activity
boundaries, dashboard/control-plane signal mapping contracts, validation-oriented workflow boundary
tests, and contract tests. It does not
implement broker execution, database writes, AI calls, market/news provider calls, production
schedule activation, browser-side Temporal calls, or live trading.

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
and Temporal activity calls. The skeletons call placeholder activities by name and return placeholder
status objects.

## Activity Boundary

Current activity contracts are placeholders under `apps/workers/app/activities/contracts.py`.
They intentionally perform no external calls and return `external_calls_performed=false`.

Milestone 06 adds placeholder boundaries for:

- broker reconciliation snapshot retrieval;
- internal ledger snapshot retrieval;
- reconciliation snapshot comparison.

Milestone 07 adds placeholder boundaries for:

- deterministic-shortlist candidate news retrieval;
- AI trade-research execution;
- AI output validation;
- AI research payload storage.

These are activity contracts only. Workflow code still calls activities by name and performs no
broker API, AI API, news API, database, websocket, or REST calls directly.

Future side effects must stay in activities:

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
idempotency lookup behavior through broker and database activities. AI activity retry is represented
as a contract with neutral fallback on failure.

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

Milestone 09 also statically checks that workflow modules do not directly import broker, AI/news, or
network-provider code. Side effects remain activity responsibilities.

Full Temporal replay or local test-server execution is deferred until workflow behavior and mocked
activities are added. A future command should use Temporal's testing environment, for example:

```bash
uv run --group dev pytest tests/temporal --run-temporal-server
```
