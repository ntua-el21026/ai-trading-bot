# Operations Runbook

This document is a foundation placeholder for operations.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 09 does not implement production services, active schedules, real broker clients, real AI/news provider clients, real Temporal query/signal backend integration, alerts, reports, paper trading runs, or live trading. It does define passive broker/reconciliation, AI/news, dashboard/control-plane, and validation/testing contracts with incident/fallback recommendations.

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

No current operation submits, cancels, or flattens broker orders. Flattening is represented only as a
`flatten_if_safe` recommendation for later execution workflow handling.

## Current AI Operations

AI/news intelligence is currently a fixture-safe contract:

1. Request ticker-tagged news only for deterministic shortlist symbols.
2. Normalize and deduplicate articles.
3. Build a versioned prompt and validate strict AI JSON output.
4. Fall back to neutral behavior for no news, invalid JSON, schema violations, provider outages, or
   insufficient data.
5. Persist only payload contracts for future database integration.

No current operation calls AI providers, news providers, broker APIs, or databases. AI has no broker
credentials and cannot create or modify orders, stops, strategy rules, risk limits, or kill switches.

## Current Dashboard Operations

Dashboard/control-plane behavior is currently contract-only:

1. Read dashboard snapshots from fixture or future database/Temporal read-model providers.
2. Represent safe manual controls as auditable command objects.
3. Map safe controls to existing Temporal signal names through server-side contracts.
4. Expose only explicitly safe public dashboard environment values.

No current dashboard operation submits broker orders, calls broker APIs, calls AI/news providers,
calls Temporal from browser code, exposes broker/AI provider secrets, or changes risk/autonomy
configuration.

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

## Future Operations Scope

Later milestones must document real worker startup, Temporal schedules, paper trading procedures,
real broker credential setup, real AI/news provider setup, database-backed reconciliation and AI
research persistence, real Temporal query/signal backend integration, dashboard deployment,
incident response, kill-switch behavior, reporting, and Level 4 micro-live readiness gates.
