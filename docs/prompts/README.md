# Milestone Prompt Pack

This directory contains ready-to-use Codex milestone prompts for the autonomous AI trading bot repository.

These prompts are intended to be run sequentially unless the user explicitly decides otherwise. Each prompt requires Codex to read `AGENTS.md`, identify and read the latest versioned specification file, inspect relevant repository files, and stop for approval before any spec deviation.

As of this prompt pack, the latest identified spec is:

```text
docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md
```

Future Codex runs must still re-identify the latest versioned spec before editing.

## Milestones

1. `00_REPO_INSPECTION_AND_PLAN.md` - Inspect the repository and produce a spec-aligned implementation plan without code changes.
2. `01_PROJECT_FOUNDATION.md` - Establish base repository structure, Python project configuration, config loading, logging, environment templates, and foundational docs.
3. `02_DATA_AND_BACKTEST_CORE.md` - Build market data abstractions, raw payload persistence design, OHLCV models, feature scaffolding, and backtest skeletons.
4. `03_TEMPORAL_WORKFLOWS.md` - Add Temporal worker setup, task queues, workflow/activity boundaries, deterministic workflow skeletons, and Temporal docs/tests.
5. `04_STRATEGY_REGIME_AND_SIGNALS.md` - Implement deterministic regime, breakout, relative strength, ATR, earnings blackout, and signal logic without live execution.
6. `05_RISK_AND_EXECUTION_CORE.md` - Implement deterministic risk checks, position sizing, `ExecutionIntent`, idempotency design, and order lifecycle abstractions without live trading enablement.
7. `06_BROKER_RECONCILIATION.md` - Implement Alpaca paper adapter boundaries, broker stream/REST fallback abstractions, reconciliation, and mismatch incidents without live trading.
8. `07_AI_INTELLIGENCE_LAYER.md` - Implement bounded shortlist-only AI/news intelligence with schema validation, prompt versioning, persistence, and neutral fallback behavior.
9. `08_DASHBOARD_AND_CONTROL_PLANE.md` - Implement dashboard/control-plane views and kill-switch control flow while keeping Vercel dashboard-only and broker secrets out of frontend code.
10. `09_VALIDATION_AND_TESTING.md` - Add the validation harness, unit/integration/Temporal/failure tests, backtest checks, and paper dry-run verification.
11. `10_PAPER_TRADING_RUNBOOK.md` - Create paper-trading operations procedures, monitoring, reporting, incident response, and paper-to-live acceptance checklist.
12. `11_LEVEL4_MICRO_LIVE_READINESS.md` - Prepare Level 4 micro-live readiness documentation and gates without enabling live trading unless explicitly requested.

## Usage

Start with `00_REPO_INSPECTION_AND_PLAN.md`. Later milestones should use the previous milestone outputs as context, but must still independently verify current repository state and latest spec alignment.
