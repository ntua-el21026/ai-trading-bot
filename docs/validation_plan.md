# Validation Plan

This document describes the current validation scaffold.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`. Milestones 17-27
add managed Postgres/Supabase runtime preparation with explicit `DATABASE_URL` validation,
migration dry-run/apply scripts, schema-check helpers, second opt-in gates, opt-in managed DB
repository CRUD tests skipped by default, local Temporal SDK test-environment/replay coverage,
opt-in Alpaca paper read-only smoke tooling, and a default-refusing gated Alpaca paper
order-lifecycle smoke harness. Milestone 22 adds Marketaux/Alpha Vantage provider-first news
retrieval, OpenAI structured analysis, disabled-by-default OpenAI web fallback, and autonomous AI
feedback/calibration using offline default tests. Milestone 23 adds Telegram-only alert delivery
contracts, templates, routing, report/trade summaries, fake-default behavior, and an explicitly
gated Telegram smoke harness. Milestone 24 adds Temporal Cloud dev runtime helpers and a
default-refusing Cloud smoke harness for harmless workflow execution with fake/local activities.
Milestone 25 adds dashboard/control-plane dev runtime smoke coverage for read-only snapshots,
runtime status sections, safe control schemas, fake/default dispatch, and frontend secret
guardrails. Milestone 26 adds static dashboard preview build/config checks for Vercel
dashboard-only preview deployment. Milestone 26B records Vercel deployment evidence for preview URL
`https://ai-trading-cy85e5pf1-michael-peppas-projects.vercel.app` and documents an accidental
production deployment/alias as non-operational static dashboard-only after audit. This does not
validate actual paper trading operations, production operational dashboard integration, production
schedule activation, live trading, or profitability.
Milestone 27 adds controlled paper operations readiness tests and a read-only readiness script that
aggregate existing evidence only; they do not start paper trading, activate schedules, submit broker
orders, call providers, send alerts, or deploy.
Milestone 43 adds deterministic scale-in policy coverage with fake/stub clients only. It does not
start frozen validation, activate schedules, perform broker writes, call providers, or claim Level 4
readiness. Milestone 44 creates the v0.5 frozen-validation spec, adds dormant paper-only short-side
architecture, disables scale-ins at validation T0, requires a flat broker baseline before M45, and
keeps M45 blocked until the non-IEX primary signal-data gate is verified or explicitly waived by
governance.

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
- Runtime database URL validation, redaction, migration dry-run scripts, managed DB operation gates,
  schema uniqueness/index checks, and default-skipped managed DB schema/CRUD checks are
  fixture-tested without connecting to managed Postgres/Supabase.
- Ledger-backed activity persistence and read helpers are fixture-tested with in-memory SQLite and
  no managed database credentials.
- Regime classification is fixture-tested for `RISK_ON`, `CAUTION`, and `RISK_OFF`.
- Strategy candidate evaluation is fixture-tested for long-only accepted/rejected candidates, 20D and 55D breakout variants, RS63, ATR percent, earnings blackout, held-symbol, and duplicate-intent gates.
- Strategy candidate evaluation can explicitly evaluate held symbols as scale-in candidates while
  still refusing held symbols by default.
- Exit helpers are fixture-tested for initial stops, trailing stops, technical exits, time stops, and fail-fast exits without submitting orders.
- Risk checks are fixture-tested for accepted and rejected new-risk paths, stale data, kill switch, duplicate intent, exposure, and loss-limit failures.
- Position sizing is fixture-tested for configured caps, multipliers, invalid stop distance, and below-one-share rejection.
- Execution intent and idempotency helpers are fixture-tested for approved-risk intent creation, protective-stop validation, expiration checks, deterministic client order IDs, duplicate detection, and passive lifecycle transition rejection.
- Scale-in policy helpers are fixture-tested for config defaults, disabled policy refusal, protected
  existing positions, missing-stop refusal, open-order role blockers, unresolved incidents, symbol
  and portfolio caps, missing add-on signals, distinct scale-in intent metadata, additive stop
  requirements, aggregate protection, failed stop incidents, duplicate active intents, reporting
  roles, full-universe eligibility, and AAPL/MSFT/XLK protected-hold candidate handling.
- Broker model validation is fixture-tested without credentials.
- Alpaca `trade_updates` mapping is fixture-tested without websocket connections.
- Paper-only Alpaca adapter gates, fake-client mapping, idempotency lookup, paper entry/cancel,
  protective-stop submit/verify, partial-fill stop-quantity handling, ambiguity handling, and
  broker activity contracts are fixture-tested without real Alpaca calls.
- Alpaca paper read-only smoke gates, sanitized summary output, GET-only HTTP client behavior,
  live-endpoint refusal, account/open-order/position/clock mapping, and write-operation refusal are
  fixture-tested without real Alpaca calls.
- Alpaca paper order-lifecycle smoke gates, default refusal, live-endpoint refusal, unsafe config
  refusal, live-universe scope checks, quantity/notional/timeout caps, existing broker-state
  refusal, smoke-only client order IDs, fake-client filled/unfilled/partial/ambiguous lifecycle
  behavior, cleanup, reconciliation summaries, and sanitized output are fixture-tested without real
  Alpaca calls.
- Daily/weekly report generation, stable Markdown rendering, Telegram-safe report summaries,
  report persistence, alert routing, fake alert capture, gated Telegram adapter behavior,
  fail-closed deferred email skeletons, dashboard read models, and reporting activities are
  fixture-tested without external alert delivery or managed database credentials.
- Fake/local end-to-end paper dry-run orchestration is tested for happy path, risk rejection,
  duplicate active intent, broker ambiguity, missing protective stops, reconciliation mismatches,
  partial fills, invalid-AI neutral fallback, report/dashboard output, and CLI safety behavior.
- REST fallback snapshot construction is fixture-tested with the 30-second spec interval.
- Reconciliation comparison is fixture-tested for clean state, missing/extra positions, missing protective stops, duplicate open entry orders, unexpected short positions, unsupported broker asset classes, unknown open broker orders, missing fills, quantity mismatch, average-price mismatch, account-equity mismatch, stale snapshots, and Temporal workflow inconsistency.
- Incident severity, pause-new-risk recommendations, and flatten-if-safe recommendations are fixture-tested.
- AI article validation, normalization, deduplication, and deterministic-shortlist provider boundaries are fixture-tested.
- Marketaux and Alpha Vantage payload normalization, provider-first fallback/cross-check behavior,
  per-provider request budgets, per-run symbol/article caps, provider outage/no-news behavior,
  malformed payload handling, deduplication, raw payload hashes, and no full-universe scanning are
  fixture-tested without external calls.
- OpenAI structured-output analysis, strict Responses-API schema generation, optional model-list
  validation through fake clients, invalid JSON/schema fallback, no-news/provider-outage/budget
  fallback, prompt/model/schema version recording, raw prompt/output hashes, hard-block policy, and
  no execution-intent/order authority are fixture-tested without OpenAI calls.
- OpenAI web fallback disabled-by-default behavior, runtime policy requirement, exception-only
  trigger rules, separate budget refusal, and provider-covered skip behavior are fixture-tested
  without OpenAI web-search calls.
- AI feedback/calibration metrics, report generation, AI quality warning/event payloads, safety
  downgrades to reduced/neutral/escalation states, and no strategy/risk/execution/broker mutation
  are fixture-tested.
- AI prompt loading, strict JSON parsing, invalid JSON fallback, schema-violation fallback, no-news fallback, provider-outage fallback, and conflicting-source fallback are fixture-tested.
- AI recency decay, source quality weighting, score clipping, hard-block confidence threshold, and non-increasing size-multiplier behavior are fixture-tested.
- AI persistence payload hashes are fixture-tested without database writes.
- AI/news provider activity contracts remain fixture-tested as placeholders with no external calls.
- Workflow skeletons are fixture-tested to call ledger activity boundaries by stable names while
  avoiding direct side-effect imports.
- Dashboard/control-plane read models, safe control action shapes, Temporal signal mapping, no
  order-entry controls, runtime status sections, fixture dispatch behavior, fake/local runtime
  smoke behavior, deployment refusal, managed-DB runtime refusal, and frontend secret guardrails are
  fixture-tested.
- Controlled paper operations readiness evidence aggregation is fixture-tested for success, missing
  evidence, hard-failure safety flags, default no-external-call behavior, and sanitized output.
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
- Temporal SDK test-environment tests execute every registered workflow skeleton with fake/local
  activities, validate selected signal/query contracts, verify configured worker task-queue
  registration, and replay a generated kill-switch workflow history without Temporal Cloud,
  production schedules, managed database credentials, broker APIs, AI/news providers, alert
  delivery, or broker orders.
- Temporal Cloud runtime smoke settings, required gate parsing, API-key/TLS connection kwargs,
  selected task queue handling, sanitized output, no-schedule behavior, and default refusal are
  fixture-tested without connecting to Temporal Cloud.
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
| Database runtime preparation | `tests/unit/test_database_runtime.py`, `tests/unit/test_ledger_connection_runtime.py`, `tests/unit/test_migration_runtime.py`, `tests/integration/test_managed_ledger_crud.py` |
| Temporal ledger activities | `tests/unit/test_ledger_activities.py`, `tests/temporal/test_workflow_contracts.py` |
| Regime logic | `tests/unit/test_regime.py` |
| Strategy signals and candidates | `tests/unit/test_strategy_signals.py` |
| Exit helpers | `tests/unit/test_strategy_exits.py` |
| Risk checks | `tests/unit/test_risk_checks.py` |
| Position sizing | `tests/unit/test_position_sizing.py` |
| Kill switch | `tests/unit/test_kill_switch.py`, `tests/temporal/test_workflow_contracts.py` |
| Execution intent | `tests/unit/test_execution_intent.py` |
| Scale-in policy | `tests/unit/test_scale_in_policy.py` |
| Idempotency | `tests/unit/test_idempotency.py` |
| Order lifecycle contracts | `tests/unit/test_execution_intent.py`, `tests/unit/test_failure_simulations.py` |
| Broker models and stream mapping | `tests/unit/test_broker_models.py`, `tests/unit/test_alpaca_mapping.py` |
| Paper broker adapter and activities | `tests/unit/test_alpaca_paper_adapter.py`, `tests/unit/test_broker_activities.py` |
| Alpaca paper read-only smoke | `tests/unit/test_alpaca_paper_readonly.py`, `tests/integration/test_alpaca_paper_readonly_smoke.py` |
| Alpaca paper order-lifecycle smoke harness | `tests/unit/test_alpaca_paper_order_lifecycle_smoke.py`, `tests/integration/test_alpaca_paper_order_lifecycle_write_smoke.py` |
| Reconciliation | `tests/unit/test_reconciliation.py`, `tests/unit/test_failure_simulations.py` |
| AI schema, fallback, scoring, persistence | `tests/unit/test_ai_news.py`, `tests/unit/test_ai_parser.py`, `tests/unit/test_ai_scoring.py`, `tests/unit/test_ai_persistence.py`, `tests/unit/test_failure_simulations.py` |
| Provider-first news | `tests/unit/test_news_provider_integration.py`, `tests/integration/test_news_provider_external_smoke.py` |
| OpenAI structured analysis and web fallback | `tests/unit/test_openai_structured_analysis.py`, `tests/unit/test_openai_web_fallback.py`, `tests/integration/test_openai_external_smoke.py` |
| AI feedback/calibration | `tests/unit/test_ai_feedback_calibration.py` |
| Reporting and alerting | `tests/unit/test_reporting.py`, `tests/unit/test_reporting_activities.py`, `tests/unit/test_alerting.py`, `tests/unit/test_telegram_alerting.py`, `tests/integration/test_telegram_alert_delivery_smoke.py` |
| Fake/local paper dry-run orchestration | `tests/unit/test_paper_dry_run_orchestration.py`, `tests/unit/test_dry_run_cli.py` |
| Control plane and dashboard env/read models | `tests/unit/test_control_plane_models.py`, `tests/unit/test_control_plane_api.py`, `tests/unit/test_dashboard_read_models.py`, `tests/unit/test_dashboard_env_security.py`, `tests/unit/test_dashboard_control_plane_runtime.py` |
| Controlled paper operations readiness | `tests/unit/test_paper_operations_readiness.py` |
| Temporal workflow and activity contracts | `tests/temporal/test_workflow_contracts.py`, `tests/temporal/test_temporal_sdk_environment.py` |
| Temporal Cloud dev runtime smoke | `tests/unit/test_temporal_cloud_runtime.py` |
| Validation harness assumptions | `tests/unit/test_validation_harness.py` |
| Failure simulations | `tests/unit/test_failure_simulations.py` |
| Paper dry-run contracts | `tests/unit/test_paper_dry_run.py` |

Remaining gaps are explicit: production managed Postgres/Supabase activity wiring, production
operational dashboard/backend integration, production schedule activation, actual paper trading
operations, frozen paper evidence, and Level 4 micro-live readiness evidence are not complete.
Milestone 27 reports readiness for a future first controlled paper session only; it is not the
session itself and is not frozen paper evidence. Milestone 25 dashboard/control-plane
runtime smoke is dev-only and not a production deployment. Milestone 20 read-only Alpaca paper
smoke evidence has passed for account, open-order, position, and clock/status reads only. Milestone
21B controlled paper order-lifecycle smoke evidence has passed, but it is not actual paper trading
operations or frozen paper evidence. Milestone 22 provider/OpenAI/calibration support and Milestone
23 Telegram delivery evidence are also not actual paper trading evidence.

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

`packages/paper/` now provides an executable fake/local dry-run service that persists ledger
evidence, uses `FakeAlpacaClient`, captures fake alerts, generates a daily report, and builds a
dashboard snapshot. `scripts/run_paper_dry_run.py` runs this path in fake/local mode only and does
not submit broker orders or call external services.

## Paper Operations Evidence

`docs/paper_trading_runbook.md` defines the target paper operating procedure, monitoring checklist,
incident response flow, report expectations, frozen paper acceptance criteria, and paper-to-Level-4
handoff gates.

Current paper operations evidence is absent. The repository has fake-tested paper broker boundaries,
fake/local paper dry-run orchestration, local ledger evidence, a successful gated paper
order-lifecycle smoke, provider/OpenAI smoke evidence, Telegram smoke evidence, and a gated
Temporal Cloud dev smoke harness. It still needs production managed database activity wiring,
production Temporal/live-worker evidence, real dashboard deployment, and controlled paper runs
before frozen paper gates can be satisfied.

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
- Database/audit-ledger foundation, local/fake Temporal activity persistence, explicit
  Postgres/Supabase runtime helpers, and opt-in managed CRUD validation exist.
- Local Temporal SDK test-server/replay coverage exists; the Temporal Cloud dev smoke harness has
  completed through explicit gates. Production schedule activation and actual paper-operation worker
  evidence are deferred.
- Alpaca paper read-only smoke evidence exists for account/open-order/position/clock reads; the
  controlled paper order-lifecycle smoke has passed through the gated harness. This is smoke
  evidence only, not actual paper trading operations or frozen paper evidence.
- Dashboard/control-plane dev runtime smoke exists and uses fake/default dispatch. Dashboard-only
  Vercel preview harness/build guardrails exist. Preview deployment evidence exists, and the
  accidental production deployment/alias has been documented as static/read-only and
  non-operational, but production operational dashboard integration is deferred.
- Alerting contracts, fake adapters, Telegram routing/templates, and a gated Telegram smoke harness
  exist. Real Telegram smoke evidence has run through gated paths.
- Live trading remains disabled.

These blockers must be resolved before a Level 4 go/no-go report can approve micro-live.

## Backtest Policy

Backtests are validation tools. They are not proof of live profitability. They can help validate data plumbing, feature calculations, assumptions, metrics, and later strategy behavior.

If point-in-time universe membership is unavailable, stock-universe backtests must be labeled optimistic. The current research universe scaffolding exposes an `optimistic_backtest_warning` flag for this purpose.

## Future Validation Scope

Later milestones must add production managed database activity wiring, real provider mock/replay
integration, controlled paper trading execution, paper trading evidence, and Level 4 readiness
review required by the latest spec. Backtests and paper trading must not be represented as proof of
live profitability.

## Milestone 44 Frozen Readiness

M44 prepares the frozen validation configuration but does not start the validation clock. The M44
baseline packet records zero open positions, zero open orders, and clean reconciliation after
approved risk-reducing cleanup of AAPL, MSFT, and XLK paper holds.

Frozen validation under v0.5 starts long-only. The full configured long universe remains eligible,
short-side architecture is present but disabled, and the short-eligible paper subset is limited to
SPY, QQQ, DIA, and IWM for any future separately approved rehearsal. Scale-ins are implemented but
disabled at validation start until the stage gate records at least 10 clean scheduled runs and real
broker additive-stop proof.

M45 remains NO-GO until the non-IEX primary signal-data gate is verified or explicitly waived. M44
also freezes negative-only AI/news behavior for the first window: AI may block, reduce, and report,
but may not authorize trades, shorts, scale-ins, or larger sizing.

M44B implements this gate as a separate readiness check. Verify mode must prove the configured
primary signal feed is non-IEX through read-only market-data access. Waiver mode requires the
explicit `MILESTONE_44B_NON_IEX_DATA_GATE_WAIVER` marker and records that the paper window is
operational validation with market-data limitations.

M44C sets Tiingo EOD historical completed daily bars as the primary M45 signal feed. The check uses
`TIINGO_API_KEY` from local environment, fetches read-only daily bars for `SPY`, `QQQ`, `AAPL`,
`MSFT`, and `XLK`, and requires at least 260 completed bars with valid OHLCV and adjusted-price
fields. Alpaca remains the paper broker; Alpaca IEX is not allowed for signal generation. M45
remains NO-GO unless the Tiingo EOD gate verifies or an explicit governance waiver is recorded.
The M44C real read-only check verified Tiingo EOD access and refreshed readiness to M45 `GO`;
starting the frozen window still requires the separate M45 operator approval milestone.

## Current Assumptions

Earnings blackout logic requires a caller-supplied trading calendar and earnings date. If earnings
data or the relevant trading session is unavailable, the status is `unknown` and candidate entries
are blocked conservatively. Exits remain allowed during blackout according to the latest spec.
