# Paper Dry-Run Orchestration

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.4.md`.

Milestone 16 adds a fake/local end-to-end paper dry-run path. It is operational rehearsal only. It
does not start actual paper trading, submit broker orders, call external services, or provide Level
4 readiness evidence. Milestone 21A's gated Alpaca paper order-lifecycle smoke harness is separate
from this fake/local dry-run path and refuses by default unless explicit write-smoke gates are
loaded.

## Implemented

- `packages/paper/models.py` defines typed dry-run scenario, config, input, result, evidence,
  safety-flag, step-result, and failure-mode models.
- `packages/paper/fixtures.py` defines deterministic fixture scenarios.
- `packages/paper/dry_run.py` coordinates the fake/local dry-run service.
- `scripts/run_paper_dry_run.py` runs the safe default happy-path scenario.

The service exercises this shape:

1. Initialize local in-memory SQLite ledger repository.
2. Persist fixture raw provider payload.
3. Persist deterministic strategy candidate.
4. Persist neutral or fake-invalid AI fallback output.
5. Persist deterministic trade decision.
6. Run deterministic risk gate using safe simulated paper permission for the risk check only.
7. Persist risk check and execution intent when risk passes.
8. Submit fake paper entry through `FakeAlpacaClient`.
9. Persist fake order, fill, and position records.
10. Submit and verify fake protective stop when required.
11. Compare fake broker and internal snapshots through reconciliation logic.
12. Persist reconciliation and incidents/system events.
13. Capture fake alerts through `FakeAlertAdapter`.
14. Generate and persist a daily report.
15. Build a ledger-backed dashboard/read-model snapshot.

## Scenarios

Implemented scenarios include:

- `happy_path`
- `risk_rejection`
- `invalid_ai_output_neutral`
- `duplicate_active_intent`
- `broker_ambiguity`
- `partial_fill`
- `missing_protective_stop`
- `reconciliation_mismatch`
- `kill_switch_pause_new_risk`
- `stale_data`

The default command runs `happy_path`:

```bash
uv run python scripts/run_paper_dry_run.py
```

Failure scenarios can be invoked explicitly, for example:

```bash
uv run python scripts/run_paper_dry_run.py --scenario broker_ambiguity
```

Failure scenarios may return a nonzero exit code because the dry-run result is expected to fail.

## Safety Boundary

The dry-run path uses:

- in-memory SQLite;
- fixture data only;
- neutral/fake AI outputs only;
- `FakeAlpacaClient` only;
- `FakeAlertAdapter` only;
- local report and dashboard read-model generation only.

The dry-run path does not:

- enable live trading;
- enable autonomous live execution;
- add secrets;
- require `DATABASE_URL`;
- call Alpaca;
- call AI/news providers;
- call market-data providers;
- send Telegram/email alerts;
- call managed Postgres/Supabase;
- submit real paper or live broker orders;
- activate Temporal schedules;
- deploy a dashboard.

## Validation

Dry-run-specific tests:

```bash
uv run --group dev pytest tests/unit/test_paper_dry_run*.py tests/unit/test_dry_run*.py
```

Full local validation remains:

```bash
uv run --group dev pytest tests/unit tests/temporal
uv run --group dev ruff check .
uv run --group dev mypy packages apps tests
uv run --group dev python -m compileall -q packages apps tests
```

## Remaining Gaps

The following are still deferred:

- retained real Alpaca paper order-lifecycle smoke evidence;
- production managed Postgres/Supabase activity wiring;
- production Temporal query/signal backend integration;
- real AI/news provider integration;
- real alert delivery;
- real dashboard deployment;
- actual paper trading operations;
- frozen paper evidence;
- Level 4 micro-live readiness.

Milestones 17-18 add opt-in Postgres/Supabase migration, schema-check, and repository CRUD
validation helpers, but the dry-run path continues to default to in-memory SQLite and does not
require or call managed Postgres/Supabase.
