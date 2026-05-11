# Paper Trading Runbook

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 27 adds a controlled paper operations readiness harness while paper trading remains disabled. The
repository still does not implement actual paper trading operations, production dashboard
deployment, frozen paper evidence, Level 4 readiness, or live trading.

## Purpose And Constraints

Paper trading is operational rehearsal. It validates whether the system can operate safely through
orchestration, broker integration, order lifecycle handling, protective stop placement, broker
reconciliation, logging, kill switches, reporting, and AI schema behavior.

Paper trading does not prove:

- live fill quality;
- market impact;
- queue position;
- price improvement;
- live slippage;
- live profitability.

Backtests are also validation tools, not proof of profitability. Paper-first validation is required
before any Level 4 micro-live approval, but paper results are acceptance evidence only when they are
frozen, versioned, reproducible, and operationally clean.

## Current Implementation Status

This runbook is target/runbook readiness documentation. Current code provides contracts and fixtures
for broker reconciliation, fake Alpaca paper adapter boundaries, AI/news validation, control-plane
actions, report generation, fake alert dispatch, dashboard read models, failure simulation, paper
dry-run checks, fake/local end-to-end dry-run orchestration, local ledger repository tests, opt-in
managed repository CRUD validation, safe local/fake Temporal activity tests, and fake broker
activity tests. It also provides an opt-in read-only Alpaca paper smoke command, a separate gated
order-lifecycle smoke harness that refuses by default, and a Telegram alert delivery smoke harness
that refuses by default. Milestone 24 adds a Temporal Cloud dev smoke harness that refuses by
default and uses fake/local activities only when gated. Milestone 25 adds a dashboard/control-plane
dev runtime smoke that builds fake/local read-only snapshots and validates safe controls through a
fake dispatcher by default. Milestone 26 adds a static dashboard-only Vercel preview harness with
no workers, no order-entry controls, no secrets, and no browser-side privileged service calls.
Milestone 27 adds `scripts/check_paper_operations_readiness.py`, a read-only readiness aggregator
for existing database, Temporal, broker, AI/news, alerting, dashboard, and paper-status evidence. It
does not connect those contracts to autonomous order-writing paper
execution, production managed database activity wiring, production schedule activation, production
dashboard deployment, or actual paper execution orchestration yet. Milestone 22 provider/OpenAI
smoke tests remain opt-in and skipped/refused unless explicit gates and local secrets are present.

The safe local dry-run command is:

```bash
uv run python scripts/run_paper_dry_run.py
```

It prints `This is a fake/local dry run. No broker orders are submitted.`, uses in-memory SQLite
and fake adapters, and does not call external services.

The controlled paper operations readiness command is:

```bash
uv run python scripts/check_paper_operations_readiness.py
```

It aggregates readiness evidence only. It does not start paper trading, activate schedules, submit
or cancel broker orders, run strategy-generated paper trading, call AI/news providers, send real
alerts, or deploy anything.

Milestone 28 locks the pre-paper operations gap audit and future first controlled paper session
protocol in `docs/pre_paper_operations_gap_audit.md`.

Milestone 29 adds the fake/local first controlled paper-session wiring harness documented in
`docs/first_controlled_paper_session_wiring.md`. It is an offline rehearsal path only; it does not
submit paper orders or start actual paper trading.

Milestone 30 adds the real-gated first-session wiring boundary documented in
`docs/first_controlled_paper_session_real_gate_wiring.md`. It refuses by default and still does
not submit paper orders or run the actual controlled paper session.

Milestone 31 adds the read-only first-session preflight and launch authorization packet documented
in `docs/first_controlled_paper_session_preflight.md`. It may run only fake/stub checks by default
or explicitly gated Alpaca paper read-only checks; it performs no broker writes and does not start
the actual session.

Milestone 32 extends that preflight path with `MILESTONE_32_READ_ONLY_PREFLIGHT`, safe `.env` gate
loading for real-read-only mode, and sanitized launch packet artifact generation. It still performs
only account, clock, open-order, and position reads when all read-only gates pass.

Milestone 33 adds `MILESTONE_33_READ_ONLY_PREFLIGHT` and retries the real-read-only launch packet
path after diagnosing the Milestone 32 `write_smoke_flag_must_be_disabled` NO-GO. The blocker is
cleared only by running the read-only command with the write-smoke flag explicitly non-truthy for
that process; `.env` remains untracked and must not be printed.

Milestone 34 adds the explicitly gated first controlled Alpaca paper execution path documented in
`docs/first_controlled_paper_session_execution.md`. The recorded Milestone 34 run refused before
broker writes because no operator-selected target symbol or order envelope was supplied. The result
packet is written to `docs/evidence/first_controlled_paper_session_result.json`.

Milestone 35A corrects the pre-execution symbol/envelope model before real execution. The first
session now requires an explicit limit price, validates `quantity * limit_price <= max_notional`,
enforces `first_session_max_qty=1`, and enforces a config-backed
`first_session_absolute_max_notional_usd=500.0`. The local universe audit command is:

```bash
uv run python scripts/run_first_controlled_paper_session.py --mode audit-symbol-universe
```

It performs no external calls and no broker writes.

Milestone 35B attempted the operator-selected first controlled paper session only up to the
allowed read-only gates. The target/envelope was `AAPL`, quantity `1`, max notional `350`, limit
price `330`, and estimated notional `330`. The real read-only Alpaca paper preflight completed
cleanly, but the refreshed clock showed the market/session closed, so the write-capable
real-paper command was not run. The result packet records `market_clock_not_open`, no broker
writes, no actual paper trading, no schedules, no leverage, and no Level 4 readiness.

Milestone 35C retried the same AAPL envelope after a refreshed read-only preflight reported the
market open and AAPL clean. One Alpaca paper entry order was submitted and filled for one share.
The process then hit a fill-mapping defect before the normal stop path completed. A recovery
protective stop was submitted for the filled AAPL quantity and verified by read-back. This is a
safety incident and blocks repeated controlled paper sessions until the post-session audit accepts
the incident handling and result packet.

The read-only Alpaca paper smoke command is opt-in and must not be treated as paper trading:

```bash
RUN_ALPACA_PAPER_SMOKE=1 \
ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT \
ALPACA_BASE_URL=https://paper-api.alpaca.markets \
  uv run python scripts/check_alpaca_paper_readonly.py
```

It validates account, open-order, position, and clock/status reads only. It must not submit,
cancel, replace, close, liquidate, or place protective-stop orders.

Milestone 20 read-only smoke status: passed after corrected local paper credentials were loaded.
This proves paper account connectivity and normalized read-only mapping only. It is not actual paper
trading and it does not validate the paper order lifecycle.

Milestone 21B status: the real paper order-lifecycle smoke completed through the gated harness. It
used the paper endpoint, submitted and acknowledged one tiny smoke entry, verified the protective
stop after fill, performed cleanup, cancelled smoke-created orders after cleanup, verified final
target-symbol state clean/flat, and printed sanitized evidence only. It was a controlled smoke, not
actual paper trading operations, not frozen paper evidence, and not Level 4 readiness.

The Alpaca paper order-lifecycle smoke harness is also opt-in and must not be treated as paper
trading:

```bash
uv run python scripts/check_alpaca_paper_order_lifecycle.py
```

With no write-smoke gates loaded, the expected result is sanitized refusal before broker write
calls. A later real paper write smoke requires the explicit gates listed below, uses only one tiny
paper `DAY` limit entry order, places a protective stop only for filled quantity, cleans up
smoke-created orders/positions, and prints sanitized evidence only. It is not frozen paper
evidence, not actual paper trading operations, and not Level 4 readiness.

Do not treat any procedure below as operationally complete until the deferred integrations listed in
the paper-to-live handoff section are implemented and validated.

## Environment Setup Checklist

Required services by name:

- Temporal service or Temporal Cloud namespace.
- Worker process for each required task queue.
- Alpaca paper account.
- Database/audit-ledger foundation and gated managed runtime validation.
- Dashboard/control plane when deployed.
- Alert channels when implemented.
- AI/news provider configuration when implemented.

Required environment variable names only:

- `DATABASE_URL`
- `RUN_MANAGED_DB_TESTS`
- `LEDGER_MIGRATION_CONFIRM`
- `TEMPORAL_ADDRESS`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_API_KEY`
- `TEMPORAL_TLS_CERT`
- `TEMPORAL_TLS_KEY`
- `RUN_TEMPORAL_CLOUD_SMOKE`
- `TEMPORAL_CLOUD_SMOKE_CONFIRM`
- `TEMPORAL_CLOUD_SMOKE_TASK_QUEUE`
- `TEMPORAL_CLOUD_SMOKE_WORKFLOW`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_BASE_URL`
- `RUN_ALPACA_PAPER_SMOKE`
- `ALPACA_PAPER_SMOKE_CONFIRM`
- `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE`
- `ALPACA_PAPER_ORDER_LIFECYCLE_CONFIRM`
- `ALPACA_PAPER_ORDER_SMOKE_SYMBOL`
- `ALPACA_PAPER_ORDER_SMOKE_MAX_QTY`
- `ALPACA_PAPER_ORDER_SMOKE_MAX_NOTIONAL_USD`
- `ALPACA_PAPER_ORDER_SMOKE_TIMEOUT_SECONDS`
- `RUN_FIRST_CONTROLLED_PAPER_SESSION`
- `RUN_FIRST_CONTROLLED_PAPER_SESSION_EXECUTION`
- `AI_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_ESCALATION_MODEL`
- `OPENAI_FALLBACK_MODEL`
- `MARKETAUX_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `NEWS_PROVIDER_PRIMARY`
- `NEWS_PROVIDER_FALLBACK`
- `NEWS_MARKETAUX_DAILY_REQUEST_LIMIT`
- `NEWS_ALPHA_VANTAGE_DAILY_REQUEST_LIMIT`
- `NEWS_MAX_SYMBOLS_PER_RUN`
- `NEWS_MAX_ARTICLES_PER_SYMBOL`
- `NEWS_DEFAULT_LOOKBACK_DAYS`
- `NEWS_EXTENDED_LOOKBACK_DAYS`
- `NEWS_ENABLE_OPENAI_WEB_FALLBACK`
- `NEWS_OPENAI_WEB_DAILY_REQUEST_LIMIT`
- `AI_DAILY_REQUEST_LIMIT`
- `AI_MAX_SYMBOLS_PER_RUN`
- `AI_MAX_ARTICLES_PER_SYMBOL`
- `AI_REQUIRE_STRUCTURED_OUTPUT`
- `AI_NEUTRAL_FALLBACK_ON_ERROR`
- `AI_ENABLE_ESCALATION`
- `RUN_NEWS_PROVIDER_SMOKE`
- `NEWS_PROVIDER_SMOKE_CONFIRM`
- `NEWS_PROVIDER_SMOKE_SYMBOLS`
- `RUN_OPENAI_MODEL_LIST_SMOKE`
- `OPENAI_MODEL_LIST_CONFIRM`
- `RUN_OPENAI_AI_SMOKE`
- `OPENAI_AI_SMOKE_CONFIRM`
- `RUN_OPENAI_WEB_FALLBACK_SMOKE`
- `OPENAI_WEB_FALLBACK_CONFIRM`
- `ANTHROPIC_API_KEY`
- `POLYGON_API_KEY`
- `FINNHUB_API_KEY`
- `FMP_API_KEY`
- `TIINGO_API_KEY`
- `TAVILY_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `APP_ENV`
- `NEXT_PUBLIC_APP_ENV`
- `NEXT_PUBLIC_DASHBOARD_ENV`
- `LIVE_TRADING_ENABLED`
- `AUTONOMOUS_EXECUTION_ENABLED`
- `AUTONOMY_LEVEL`
- `KILL_SWITCH_ENABLED`
- `RUN_DASHBOARD_CONTROL_PLANE_SMOKE`
- `DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM`
- `DASHBOARD_CONTROL_PLANE_USE_TEMPORAL_DEV`
- `DASHBOARD_CONTROL_PLANE_USE_MANAGED_DB`
- `DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS`
- `RUN_VERCEL_DASHBOARD_PREVIEW`
- `VERCEL_DASHBOARD_PREVIEW_CONFIRM`
- `ALERT_PROVIDER_PRIMARY`
- `ALERT_PROVIDER_SECONDARY`
- `ALERT_ENABLE_REAL_DELIVERY`
- `ALERT_DAILY_MESSAGE_LIMIT`
- `ALERT_CRITICAL_BYPASS_DAILY_LIMIT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `RUN_TELEGRAM_ALERT_SMOKE`
- `TELEGRAM_ALERT_SMOKE_CONFIRM`
- `TELEGRAM_ALERT_SMOKE_MAX_MESSAGES`
- `TELEGRAM_ALERT_SMOKE_INCLUDE_REPORT_SAMPLE`
- `TELEGRAM_ALERT_SMOKE_INCLUDE_TRADE_SAMPLE`
- `TELEGRAM_ALERT_SMOKE_INCLUDE_CRITICAL_SAMPLE`

Environment rules:

- Keep secrets outside the repository.
- Use secret-manager storage for real deployments.
- Keep paper and live broker credentials separated.
- Do not use live broker credentials during paper runs.
- Do not expose broker, AI/news, Temporal, or privileged database secrets to frontend code.
- Confirm `APP_ENV`/system config points to paper mode before any paper run.
- Confirm live trading remains disabled unless a future approved milestone changes the spec and
  config.

## Pre-Run Safety Checklist

Complete this checklist before every paper session:

- Confirm the latest spec version: `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.
- Confirm `git status --short` is clean or every dirty file is known and documented.
- Confirm required tests pass:
  `uv run --group dev pytest tests/unit tests/temporal`.
- Confirm `uv run --group dev ruff check .` passes.
- Confirm `uv run --group dev mypy packages apps tests` passes.
- Confirm `config/system.yaml` remains `environment: "paper"`.
- Confirm `config/system.yaml` remains `dry_run: true` until an approved paper execution milestone
  explicitly changes it.
- Confirm `live_trading_enabled: false`.
- Confirm autonomous live execution is disabled.
- Confirm broker account mode is paper through the explicitly gated read-only smoke command before
  any future paper order lifecycle smoke test is approved.
- Confirm the order-lifecycle smoke harness refuses by default unless every explicit write-smoke
  gate is loaded before the command starts.
- Confirm the paper operations readiness harness reports readiness evidence only and still reports
  actual paper trading started as false, frozen paper evidence as absent, and Level 4 as not ready.
- Confirm kill switch is enabled.
- Confirm broker reconciliation is required before new-risk orders.
- Confirm protective stops are required.
- Confirm no unsupported assets are enabled: no shorting, margin, options, futures, crypto,
  leveraged ETFs, inverse ETFs, or prediction markets.
- Confirm AI has no broker credentials and no broker API access.
- Confirm AI/news real calls are gated; default tests and dry runs use fakes or refuse safely.
- Confirm OpenAI web fallback is disabled by default and exception-only.
- Confirm AI feedback/calibration cannot mutate strategy, risk, execution, stop, universe, or
  kill-switch rules.
- Confirm dashboard/frontend code has no broker or AI/news provider secrets.
- Confirm dashboard/control-plane runtime uses fake dispatch by default and has no order-entry,
  live-enable, autonomous-enable, strategy/risk/execution mutation, or natural-language trading
  controls.
- Confirm Telegram alert delivery gates are configured only for an intentional smoke, or record
  that default fake/fail-closed alert behavior is active.
- Confirm Temporal Cloud dev smoke gates are configured only for an intentional dev-namespace
  smoke, or record that default local/fake Temporal behavior is active.
- Confirm operator knows the manual kill-switch and pause-new-risk control paths.

## Startup Procedure

This procedure is target-state documentation until real services are wired.

1. Confirm the pre-run safety checklist.
2. Start or verify Temporal service availability.
   - Use `uv run python scripts/check_temporal_cloud_runtime.py` for the explicitly gated Temporal
     Cloud dev smoke only; it does not create schedules or call real broker/AI/news/alert services.
3. Start workers on required task queues:
   - `market-data-task-queue`
   - `strategy-task-queue`
   - `ai-research-task-queue`
   - `execution-task-queue`
   - `reconciliation-task-queue`
   - `reporting-task-queue`
4. Confirm worker registration and task queue polling.
5. Confirm dashboard/control-plane read models load from safe backend contracts.
   - Use `uv run python scripts/check_dashboard_control_plane_runtime.py` for the dev runtime
     smoke. It does not deploy, activate schedules, call broker/AI/news/alert services, or send real
     Temporal control signals by default.
6. Confirm broker paper account mode through server-side broker activity once implemented.
7. Confirm managed database/audit-ledger connectivity once implemented.
8. Confirm Telegram alert delivery through the explicit smoke harness before relying on real alerts.
9. Run forced reconciliation before allowing new paper risk once real broker state is connected.
10. Record config version, code commit, spec version, and operator.

## Shutdown Procedure

1. Cancel unfilled entry orders if safe and applicable.
2. Verify every open position has a confirmed protective stop.
3. Run broker/internal reconciliation.
4. Generate or request EOD report.
5. Record unresolved incidents and follow-ups.
6. Stop workers only after active execution workflows are completed, paused, or intentionally handed
   off.
7. Preserve logs, reports, reconciliation snapshots, and incident evidence.

## Daily Procedure

All times are US Eastern Time. Until real services are implemented, these steps describe runbook
readiness and expected future operations, not active trading capability.

### Pre-Market / BOD

- Review prior EOD report and open incidents.
- Confirm Temporal service, workers, task queues, dashboard, and alert channels.
- Confirm broker stream and REST fallback readiness once broker integration exists.
- Confirm data-provider freshness and expected market session.
- Confirm kill-switch state is `RUNNING` before any new-risk paper entries.
- Run BOD reconciliation when broker/internal persistence is available.
- Keep new risk paused if any critical incident is unresolved.

### 08:25-08:45 - DailyDataRefreshWorkflow

- Refresh adjusted bars, latest quotes, asset/reference data, corporate actions, and earnings
  calendar.
- Verify raw payload hashes and normalized data freshness once persistence exists.
- Mark stale bars or stale quotes as incidents and block new risk.

### 08:45-09:10 - AIShortlistResearchWorkflow Refresh

- Fetch ticker-tagged news only for deterministic shortlist candidates.
- Use Marketaux primary and Alpha Vantage fallback/cross-check when explicit provider gates and
  credentials are present; otherwise use fixtures/refusal in default tests.
- Enforce provider request budgets, max symbols, max articles, and lookback windows.
- Normalize and deduplicate articles and preserve raw payload hashes.
- Run schema-validated OpenAI research only through explicit server-side activity boundaries and
  optional smoke gates.
- Keep OpenAI web fallback disabled by default and exception-only.
- Generate calibration reports/warnings that can only reduce, neutralize, or escalate AI influence.
- Apply neutral fallback for no news, invalid JSON, schema violations, provider outage, or
  insufficient data.
- Track invalid AI payload rate.

### 09:45-10:30 - OrderLifecycleWorkflow Entry Window

- Confirm pre-submit risk checks pass.
- Confirm pre-submit broker reconciliation is clean.
- Confirm `ExecutionIntent` and idempotent `client_order_id` are present.
- Submit only through Temporal activity boundaries once broker paper execution exists.
- Do not use market orders for new-risk entries.
- Do not use extended-hours entries.
- Monitor acknowledgement, fills, partial fills, stop placement, and incidents.

### 10:30-16:00 - PositionLifecycleWorkflow Monitoring

- Monitor open orders until expiry/cancel.
- Keep REST fallback active every 30 seconds during active windows when orders are open.
- Verify protective stops after every fill or partial fill.
- Permit risk-reducing exits according to kill-switch state.
- Keep or verify protective exits during any pause-new-risk state.
- Escalate stale quotes, stream disconnects without REST fallback, broker ambiguity, and workflow
  failures.

### 16:10-16:30 - EODSignalWorkflow

- Finalize EOD bars.
- Compute features, regime, deterministic candidates, and rejection reasons.
- Persist signal/candidate artifacts through local/fake ledger activity boundaries now; require
  managed database runtime integration before operational paper trading.
- Record optimism warnings if point-in-time universe membership is unavailable.

### 16:30-17:00 - AIShortlistResearchWorkflow

- Refresh AI/news research for EOD shortlist only.
- Validate strict schema output.
- Record fallback reasons and AI schema validity metrics.
- Keep AI advisory only; it cannot create or modify orders, stops, strategy rules, or risk limits.

### 17:00-17:15 - DecisionWorkflow

- Combine deterministic signals and validated AI outputs.
- Apply regime gate, hard blocks, and deterministic ranking.
- Create decisions or rejections for next-session planning only.
- Do not bypass risk checks or broker reconciliation.

### 20:00 - ReconciliationWorkflow And ReportingWorkflow

- Reconcile broker account, orders, fills, positions, and protective stops against internal ledger.
- Create incidents for mismatches.
- Generate daily report with workflow, execution, AI, risk, reconciliation, and incident sections.
- Current report generation can render and persist local/fake reports; operational paper evidence
  still requires real run data and managed runtime persistence.
- Keep unresolved critical incidents paused for manual review.

## Weekly Procedure

- Review all daily reports.
- Review closed paper trades and open positions.
- Review stop placement success rate.
- Review broker/internal mismatch rate.
- Review AI valid-schema rate and invalid payload clusters.
- Review duplicate order/intent incidents.
- Review stale data and provider outage incidents.
- Review dashboard/control-plane command audit records.
- Confirm strategy/config/prompt/schema versions were frozen for the paper window.
- Record unresolved operational gaps and decide whether the paper clock remains valid.

## Monitoring Checklist

Monitor these items during active paper sessions:

- Temporal service health.
- Worker availability by task queue.
- Workflow status and retry state.
- Activity retry state.
- Data freshness for bars and quotes.
- Broker stream status.
- REST fallback status and 30-second active-window cadence.
- Open entry orders.
- Order acknowledgements.
- Fills and partial fills.
- Open positions.
- Protective stop confirmation and quantity matching filled quantity.
- Reconciliation status and last successful reconciliation timestamp.
- Incidents by severity and state.
- Kill-switch state.
- Risk status, exposure, cash buffer, and loss-limit proximity.
- AI schema validity.
- Invalid AI payload rate.
- AI fallback reasons.
- Dashboard/control-plane health.
- Report generation status.

## Incident Response

Default incident rules:

- Pause new risk for critical reconciliation, execution, stop, stale-data, or worker-control
  incidents.
- Preserve or verify protective exits.
- Keep risk-reducing exits allowed unless the state is `PAUSED_ALL_AUTONOMOUS_ACTIONS`.
- Require manual review for unresolved broker ambiguity, missing stop, unexpected position, or
  control-plane uncertainty.
- Capture evidence before clearing or re-arming.

| Incident | Immediate action | Pause new risk | Risk-reducing exits | Manual review | Evidence and report update |
| --- | --- | --- | --- | --- | --- |
| Missing protective stop | Verify stream and REST state, create incident, retry stop through approved future activity path only. | Yes if unconfirmed beyond threshold. | Allowed. | Required if unresolved. | Position, fill, expected stop, broker stop lookup, timestamps, workflow history. |
| Stop not confirmed after 5 seconds | Create warning incident and verify via REST fallback. | No unless other critical issue exists. | Allowed. | Required if uncertainty persists. | Fill timestamp, stop request, stream event state, REST snapshot. |
| Stop not confirmed after 30 seconds | Create critical incident and pause new entries. | Yes. | Allowed. | Required. | All 5-second evidence plus retry history and kill-switch state. |
| Stop not confirmed after 60 seconds | Recommend flatten-if-safe through approved execution workflow path. | Yes. | Allowed. | Required. | Safety assessment, quote freshness, position quantity, attempted stop verification. |
| Duplicate order or duplicate active intent | Block new duplicate risk, cancel pending duplicate if safe, reconcile. | Yes for critical duplicate ambiguity. | Allowed. | Required if broker state is ambiguous. | Client order IDs, broker order IDs, intent records, workflow IDs. |
| Broker/internal mismatch | Run reconciliation, create incident, preserve exits. | Yes for critical mismatch. | Allowed. | Required if unresolved. | Broker snapshot, internal snapshot, mismatch list, timestamps. |
| Unexpected broker position | Pause new entries, verify protective stop, reconcile source. | Yes. | Allowed. | Required. | Broker position, internal ledger absence, stop state, stream events. |
| Unexpected short position | Pause new entries, escalate critical incident, assess flatten-if-safe. | Yes. | Allowed if risk-reducing. | Required. | Position side/quantity, order trail, broker account snapshot, quote freshness. |
| Stale market data | Reject new-risk decisions and refresh data. | Yes until fresh data is confirmed. | Allowed. | Required if repeated. | Data timestamp, provider status, workflow history. |
| Stale quote data | Pause new-risk execution and verify quote provider status. | Yes during active execution. | Allowed when quotes are fresh enough for safe exit. | Required if active orders exist. | Quote timestamp, provider status, open orders/positions. |
| Invalid AI payload | Use neutral fallback and record warning. | No by itself. | Allowed. | Required if repeated or blocking data absent. | Raw output hash, parse error, schema version, prompt version. |
| Repeated AI invalid payloads | Escalate incident and keep AI neutral. | Yes if multiple invalid payloads in the same run create a system-level safety condition. | Allowed. | Required. | Invalid count, symbols, provider/model version, fallback records. |
| AI provider outage | Use neutral fallback and record outage. | No by itself. | Allowed. | Required if repeated or required checks cannot complete. | Provider status, symbols affected, fallback records. |
| Broker API timeout or ambiguous state | Stop retrying submit path, run idempotency lookup/reconciliation, create incident. | Yes. | Allowed. | Required. | Request ID, client order ID, broker lookup result, workflow history. |
| Trade update stream disconnected | Switch to REST fallback every 30 seconds during active windows. | Yes if no REST fallback during active execution. | Allowed. | Required if active orders/positions exist. | Disconnect time, fallback health, open state. |
| REST fallback unavailable | Pause new entries and resolve broker visibility. | Yes. | Allowed if state is clear enough to reduce risk safely. | Required. | REST errors, stream state, open broker/internal state. |
| Temporal worker unavailable | Pause execution-critical starts, restore worker, inspect stuck workflows. | Yes for execution/reconciliation queues. | Allowed after orchestration state is clear. | Required. | Worker logs, task queue status, workflow IDs. |
| Execution workflow failure | Pause new entries, inspect workflow history, run reconciliation. | Yes. | Allowed if safe. | Required. | Workflow history, activity failures, broker/internal state. |
| Dashboard/control-plane failure | Use backend/Temporal operator path only, avoid browser actions. | No by itself unless controls are unavailable during active risk. | Allowed. | Required if incident controls are unavailable. | Error logs, affected views/actions, alternative control path. |
| Database/audit ledger outage placeholder | Stop new-risk execution because audit persistence is unavailable. | Yes. | Allowed if broker state and workflow state are clear. | Required. | DB error, last persisted record, broker snapshot, workflow state. |
| Daily/weekly/monthly loss breach | Activate kill-switch behavior and block new risk. | Yes. | Allowed unless stronger pause selected. | Required before re-arm. | PnL records, exposure, open positions, risk checks. |
| Manual kill-switch activation | Transition to pause/kill state, cancel pending entries if safe, reconcile. | Yes. | Allowed unless `PAUSED_ALL_AUTONOMOUS_ACTIONS`. | Required before resume. | Operator, reason, timestamp, state snapshot. |
| Manual pause-new-risk activation | Block new entries and preserve/verify exits. | Yes. | Allowed. | Required for resume-after-review. | Operator, reason, open orders/positions, reconciliation status. |
| Manual resume-after-review | Verify checklist, reconcile, confirm unresolved incident count is zero. | Clear only after approval. | Allowed. | Required. | Review notes, approvals, config/version snapshot, evidence links. |

## Daily Report Requirements

Daily paper reports must include:

- workflow summary;
- data freshness summary;
- candidates and signals;
- AI summary and schema validity stats;
- decisions and deterministic rejection reasons;
- execution intents;
- orders, fills, partial fills, and open orders;
- open and closed positions;
- protective stop status and placement timing;
- reconciliation status and mismatch details;
- incidents by severity and state;
- kill-switch state and manual controls used;
- risk, exposure, cash buffer, and loss-limit status;
- slippage and fill diagnostics where available;
- dashboard/control-plane status;
- open follow-ups and owner.

## Weekly Report Requirements

Weekly paper reports must include:

- paper trades summary;
- closed trade count;
- open positions;
- execution diagnostics;
- stop placement success rate;
- broker/internal mismatch rate;
- AI schema validity rate;
- incidents by severity;
- failed checks and rejections;
- stale data/provider outage summary;
- dashboard/control-plane command audit summary;
- operational issues and unresolved gaps;
- whether the frozen paper clock remains valid.

## Milestone 35D Post-Session Audit

Milestone 35D audited the first controlled Alpaca paper session incident without broker writes. The
real-read-only audit verified one AAPL paper position and one open verified AAPL protective stop.
No cancel, replace, flatten, new entry, new stop, schedule activation, live trading, autonomous live
execution, leverage, provider call, or real alert delivery occurred in M35D.

The incident root cause was fill metadata normalization: Alpaca account activity fill data omitted
`client_order_id`, and the M35C execution path tried to map recent fills before the normal stop
submission path. The code now falls back to `order_id` for fills without `client_order_id` and
records malformed fill metadata as a structured incident while continuing to protective-stop
submission from the known entry-order context.

Current operational decision:

- recommendation: `HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW`;
- cleanup/flatten performed: no;
- repeated controlled paper sessions: NO-GO;
- next allowed step: explicit post-session audit acceptance or a separately approved
  risk-reducing cleanup/flatten decision.

Frozen paper validation has not started. Level 4 remains not ready.

## Frozen Paper Acceptance Criteria

These are gates before Level 4 micro-live consideration, not current achievements:

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

The paper window must use frozen strategy, risk, execution, AI prompt, AI schema, and config
versions. Material changes reset or explicitly invalidate the affected acceptance window unless a
future approved validation policy says otherwise.

## Paper-To-Level-4 Handoff Gates

Before micro-live readiness review, collect and approve:

- managed database/audit persistence implementation and migration execution evidence;
- real Temporal test-server/replay evidence;
- real Temporal query/signal backend integration;
- retained Alpaca read-only smoke evidence and separately gated paper order lifecycle broker
  evidence;
- real AI/news provider integration and schema-validity evidence;
- real dashboard deployment evidence;
- retained Telegram alert delivery evidence;
- frozen paper evidence satisfying every acceptance criterion;
- incident-free control history for the required sessions;
- documented resolution of all Sev-1/critical incidents;
- operator go/no-go approval;
- config, strategy, risk, execution, prompt, schema, and code version snapshot;
- secret-manager setup;
- verified paper/live credential separation;
- rollback and manual control paths;
- Level 4 micro-live readiness review under the next milestone.

Live enablement is not complete in this milestone. Do not document or execute live trading activation
until a future approved milestone updates the implementation and, if required, the spec.

Level 4 readiness evidence and go/no-go requirements are tracked in
`docs/level4_micro_live_readiness.md` and
`docs/templates/level4_micro_live_go_no_go_template.md`.
