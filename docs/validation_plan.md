# Validation Plan

This document describes the current validation scaffold.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 15 adds
report generation, alerting contracts, fake alert adapters, and ledger-backed dashboard read models
using fixture/local data by default. It does not validate real Alpaca paper credentials, real
AI/news provider credentials, managed Postgres/Supabase runtime connectivity, real alert delivery,
production dashboard deployment, live Temporal replay behavior, paper trading operations, live
trading, or profitability.

## Foundation Checks

- Config files load from `config/`.
- Safe defaults remain disabled for live trading and autonomous execution.
- Forbidden v0.1 instruments and authorities remain disabled in config.
- Structured logging can be initialized.
- Raw provider payload hashes are stable for canonical JSON payloads.
- Adjusted daily OHLCV model validation rejects invalid price ranges.
- Daily feature utilities are deterministic and fixture-based.
- Live universe filters preserve the approved US equities/ETF scope.
- Research universe output marks optimistic warnings when point-in-time membership is unavailable.
- Backtest metrics and explicit-signal engine behavior are fixture-tested without broker calls.
- Audit-ledger schema and repository round trips are fixture-tested with in-memory SQLite and no
  managed database credentials.
- Ledger-backed activity persistence and read helpers are fixture-tested with in-memory SQLite and
  no managed database credentials.
- Regime classification is fixture-tested for `RISK_ON`, `CAUTION`, and `RISK_OFF`.
- Strategy candidate evaluation is fixture-tested for long-only accepted/rejected candidates, 20D and 55D breakout variants, RS63, ATR percent, earnings blackout, held-symbol, and duplicate-intent gates.
- Exit helpers are fixture-tested for initial stops, trailing stops, technical exits, time stops, and fail-fast exits without submitting orders.
- Risk checks are fixture-tested for accepted and rejected new-risk paths, stale data, kill switch, duplicate intent, exposure, and loss-limit failures.
- Position sizing is fixture-tested for configured caps, multipliers, invalid stop distance, and below-one-share rejection.
- Execution intent and idempotency helpers are fixture-tested for approved-risk intent creation, protective-stop validation, expiration checks, deterministic client order IDs, duplicate detection, and passive lifecycle transition rejection.
- Broker model validation is fixture-tested without credentials.
- Alpaca `trade_updates` mapping is fixture-tested without websocket connections.
- Paper-only Alpaca adapter gates, fake-client mapping, idempotency lookup, paper entry/cancel,
  protective-stop submit/verify, partial-fill stop-quantity handling, ambiguity handling, and
  broker activity contracts are fixture-tested without real Alpaca calls.
- Daily/weekly report generation, stable Markdown rendering, report persistence, alert routing,
  fake alert capture, fail-closed Telegram/email skeletons, dashboard read models, and reporting
  activities are fixture-tested without external alert delivery or managed database credentials.
- REST fallback snapshot construction is fixture-tested with the 30-second spec interval.
- Reconciliation comparison is fixture-tested for clean state, missing/extra positions, missing protective stops, duplicate open entry orders, unexpected short positions, unsupported broker asset classes, unknown open broker orders, missing fills, quantity mismatch, average-price mismatch, account-equity mismatch, stale snapshots, and Temporal workflow inconsistency.
- Incident severity, pause-new-risk recommendations, and flatten-if-safe recommendations are fixture-tested.
- AI article validation, normalization, deduplication, and deterministic-shortlist provider boundaries are fixture-tested.
- AI prompt loading, strict JSON parsing, invalid JSON fallback, schema-violation fallback, no-news fallback, provider-outage fallback, and conflicting-source fallback are fixture-tested.
- AI recency decay, source quality weighting, score clipping, hard-block confidence threshold, and non-increasing size-multiplier behavior are fixture-tested.
- AI persistence payload hashes are fixture-tested without database writes.
- AI/news provider activity contracts remain fixture-tested as placeholders with no external calls.
- Workflow skeletons are fixture-tested to call ledger activity boundaries by stable names while
  avoiding direct side-effect imports.
- Dashboard/control-plane read models, safe control action shapes, Temporal signal mapping, no
  order-entry controls, fixture dispatch behavior, and frontend secret guardrails are fixture-tested.
- Validation harness assumptions are fixture-tested for historical splits, benchmarks, fee/slippage
  assumptions, required ablations, Monte Carlo placeholders, point-in-time universe optimism
  warnings, and explicit no-profitability-proof language.
- Failure-simulation contracts are fixture-tested for stale market data, invalid AI JSON, AI
  provider outage, broker ambiguity, duplicate order attempts, partial fills, missing protective
  stops, reconciliation mismatches, database/worker outage placeholders, kill-switch activation, and
  submitted-but-not-recorded placeholders.
- Paper dry-run contracts are fixture-tested to reject broker submissions, external calls, live
  trading flags, and autonomous execution flags.
- Workflow modules are statically checked for direct broker, AI/news, provider SDK, network, random,
  environment, and wall-clock side-effect imports.
- Paper trading runbook documentation cross-links the frozen paper acceptance gates and operating
  evidence requirements without claiming paper operations have started.
- Level 4 readiness documentation cross-links acceptance gates, current blockers, config review,
  credential separation, kill-switch/manual re-arm evidence, reconciliation evidence, protective
  stop evidence, slippage/fill-quality evidence, and go/no-go records.

## Coverage Inventory

| Spec category | Current coverage |
| --- | --- |
| Config loading | `tests/unit/test_config.py`, `tests/unit/test_temporal_config.py` |
| Data models and raw payload hashing | `tests/unit/test_data_models.py` |
| Feature computation | `tests/unit/test_features.py` |
| Universe filtering | `tests/unit/test_universe.py` |
| Backtesting metrics and explicit-signal engine | `tests/unit/test_backtesting_metrics.py` |
| Database/audit-ledger foundation | `tests/unit/test_ledger_schema.py`, `tests/unit/test_ledger_repositories.py` |
| Temporal ledger activities | `tests/unit/test_ledger_activities.py`, `tests/temporal/test_workflow_contracts.py` |
| Regime logic | `tests/unit/test_regime.py` |
| Strategy signals and candidates | `tests/unit/test_strategy_signals.py` |
| Exit helpers | `tests/unit/test_strategy_exits.py` |
| Risk checks | `tests/unit/test_risk_checks.py` |
| Position sizing | `tests/unit/test_position_sizing.py` |
| Kill switch | `tests/unit/test_kill_switch.py`, `tests/temporal/test_workflow_contracts.py` |
| Execution intent | `tests/unit/test_execution_intent.py` |
| Idempotency | `tests/unit/test_idempotency.py` |
| Order lifecycle contracts | `tests/unit/test_execution_intent.py`, `tests/unit/test_failure_simulations.py` |
| Broker models and stream mapping | `tests/unit/test_broker_models.py`, `tests/unit/test_alpaca_mapping.py` |
| Paper broker adapter and activities | `tests/unit/test_alpaca_paper_adapter.py`, `tests/unit/test_broker_activities.py` |
| Reconciliation | `tests/unit/test_reconciliation.py`, `tests/unit/test_failure_simulations.py` |
| AI schema, fallback, scoring, persistence | `tests/unit/test_ai_news.py`, `tests/unit/test_ai_parser.py`, `tests/unit/test_ai_scoring.py`, `tests/unit/test_ai_persistence.py`, `tests/unit/test_failure_simulations.py` |
| Reporting and alerting | `tests/unit/test_reporting.py`, `tests/unit/test_reporting_activities.py`, `tests/unit/test_alerting.py` |
| Control plane and dashboard env/read models | `tests/unit/test_control_plane_models.py`, `tests/unit/test_control_plane_api.py`, `tests/unit/test_dashboard_read_models.py`, `tests/unit/test_dashboard_env_security.py` |
| Temporal workflow and activity contracts | `tests/temporal/test_workflow_contracts.py` |
| Validation harness assumptions | `tests/unit/test_validation_harness.py` |
| Failure simulations | `tests/unit/test_failure_simulations.py` |
| Paper dry-run contracts | `tests/unit/test_paper_dry_run.py` |

Remaining gaps are explicit: real Alpaca paper smoke tests, managed Postgres/Supabase runtime
integration, real provider integrations, real alert delivery, real Temporal test-server/replay
coverage, production dashboard deployment, paper trading operations, and Level 4 micro-live
readiness evidence are not implemented.

## Validation Harness Contracts

`packages/validation/models.py` defines the current validation-harness contract:

- historical period begins on 2012-01-01 and ends at latest available data;
- design / parameter selection split: 2012-2018;
- rolling OOS development split: 2019-2023;
- final untouched lockbox split: 2024-latest;
- benchmarks: SPY total return, exposure-adjusted SPY, and equal-weight approved universe;
- fee/slippage assumptions: zero commission, 1 bps fee proxy per side, 10 bps baseline entry,
  10 bps routine exit, 20 bps stop exit, 25 bps stress entry, and 40 bps stress stop exit;
- required ablations: regime on/off, relative strength on/off, volume filter on/off, AI forced
  neutral vs enabled, fail-fast exit on/off, time stop on/off, 20D vs 55D breakout, 2.0 ATR vs 2.5
  ATR stop, and 2.5 ATR vs 3.0 ATR trailing;
- Monte Carlo placeholders: 10,000 trade-sequence bootstraps, monthly block-bootstrap returns,
  random 5% missed fills, and randomized slippage multiplier in `[0.5x, 1.5x]`;
- stock-universe validation without point-in-time universe membership requires an optimism warning.

These are contracts and assumptions only. They do not run historical provider jobs or claim strategy
profitability.

## Failure Simulation Contracts

`packages/validation/failures.py` defines fixture-safe failure simulation scenarios for stale data,
invalid AI output, AI outage, broker ambiguity, duplicate order attempts, partial fills, missing
stops, broker/internal reconciliation mismatches, database outage placeholders, Temporal worker
unavailability placeholders, kill-switch activation, and submitted-but-not-recorded placeholders.

The scenarios describe expected outcomes and reason codes. They do not call external services,
submit orders, or mutate runtime state.

## Paper Dry-Run Contracts

`packages/validation/paper.py` defines paper dry-run check contracts for execution-intent lifecycle,
fixture broker snapshots, reconciliation cleanliness, missing-stop policy, duplicate-order
rejection, invalid-AI neutral fallback, control-plane kill-switch signal mapping, absence of broker
submissions, absence of external calls, and safe live/autonomous runtime flags.

Paper dry-run checks are operational contract validation, not proof of profitability or live
readiness.

## Paper Operations Evidence

`docs/paper_trading_runbook.md` defines the target paper operating procedure, monitoring checklist,
incident response flow, report expectations, frozen paper acceptance criteria, and paper-to-Level-4
handoff gates.

Current paper operations evidence is absent. The repository has fake-tested paper broker boundaries,
but still needs explicit real Alpaca paper smoke tests, managed database runtime connectivity, real
Temporal query/signal backend integration, real Temporal test-server/replay evidence, real AI/news
provider integration, real dashboard deployment, real alert delivery, and controlled paper runs
before these gates can be satisfied.

Frozen paper acceptance gates before Level 4 micro-live consideration:

- At least 8 weeks frozen paper.
- At least 30 closed paper trades or 2 quarters of forward paper, whichever comes later.
- OOS Profit Factor >= 1.10.
- OOS Sharpe >= 0.75 or OOS Sortino >= 1.00.
- Max drawdown <= 10%.
- 100% protective stop placement success.
- Broker/internal mismatch rate < 0.1%.
- AI valid-schema rate >= 99%.
- Zero Sev-1 control incidents in the last 20 sessions.
- Zero missing-stop incidents.
- Zero duplicate-order incidents.

These are gates, not current achievements.

## Level 4 Micro-Live Evidence

`docs/level4_micro_live_readiness.md` defines the current Level 4 readiness evidence checklist and
states the current conclusion: not ready.

Required supporting artifacts:

- `docs/checklists/level4_micro_live_readiness_checklist.md`
- `docs/checklists/credential_separation_checklist.md`
- `docs/checklists/kill_switch_rearm_checklist.md`
- `docs/templates/level4_micro_live_go_no_go_template.md`

Current blockers:

- Frozen paper evidence is unavailable.
- Actual paper trading operations have not started.
- Database/audit-ledger foundation and local/fake Temporal activity persistence exist; managed
  runtime connectivity is absent.
- Real Temporal query/signal backend integration is deferred.
- Real Alpaca paper smoke-test evidence and real AI/news provider integrations are deferred.
- Real dashboard deployment is deferred.
- Alerting contracts and fake adapters exist; real alert delivery evidence is absent.
- Live trading remains disabled.

These blockers must be resolved before a Level 4 go/no-go report can approve micro-live.

## Backtest Policy

Backtests are validation tools. They are not proof of live profitability. They can help validate data plumbing, feature calculations, assumptions, metrics, and later strategy behavior.

If point-in-time universe membership is unavailable, stock-universe backtests must be labeled optimistic. The current research universe scaffolding exposes an `optimistic_backtest_warning` flag for this purpose.

## Future Validation Scope

Later milestones must add managed database-backed integration tests, real provider mock/replay
integration, Temporal test-server/replay coverage, controlled paper trading execution, paper trading
evidence, and Level 4 readiness review required by the latest spec. Backtests and paper trading must
not be represented as proof of live profitability.

## Current Assumptions

Earnings blackout logic requires a caller-supplied trading calendar and earnings date. If earnings
data or the relevant trading session is unavailable, the status is `unknown` and candidate entries
are blocked conservatively. Exits remain allowed during blackout according to the latest spec.
