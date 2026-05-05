# Paper Trading Runbook

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 10 defines paper trading operating procedures and acceptance gates only. The repository
still does not implement actual paper trading operations, real Alpaca paper client integration,
database persistence, real AI/news provider calls, production dashboard deployment, or live trading.

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
for broker reconciliation, AI/news validation, control-plane actions, failure simulation, and paper
dry-run checks. It does not connect those contracts to real provider clients or durable database
persistence yet.

Do not treat any procedure below as operationally complete until the deferred integrations listed in
the paper-to-live handoff section are implemented and validated.

## Environment Setup Checklist

Required services by name:

- Temporal service or Temporal Cloud namespace.
- Worker process for each required task queue.
- Alpaca paper account.
- Database/audit ledger when implemented.
- Dashboard/control plane when deployed.
- Alert channels when implemented.
- AI/news provider configuration when implemented.

Required environment variable names only:

- `DATABASE_URL`
- `TEMPORAL_ADDRESS`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_API_KEY`
- `TEMPORAL_TLS_CERT`
- `TEMPORAL_TLS_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_BASE_URL`
- `AI_PROVIDER`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `POLYGON_API_KEY`
- `FINNHUB_API_KEY`
- `FMP_API_KEY`
- `TIINGO_API_KEY`
- `TAVILY_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `APP_ENV`
- `LIVE_TRADING_ENABLED`
- `AUTONOMOUS_EXECUTION_ENABLED`
- `AUTONOMY_LEVEL`
- `KILL_SWITCH_ENABLED`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

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
- Confirm broker account mode is paper.
- Confirm kill switch is enabled.
- Confirm broker reconciliation is required before new-risk orders.
- Confirm protective stops are required.
- Confirm no unsupported assets are enabled: no shorting, margin, options, futures, crypto,
  leveraged ETFs, inverse ETFs, or prediction markets.
- Confirm AI has no broker credentials and no broker API access.
- Confirm dashboard/frontend code has no broker or AI/news provider secrets.
- Confirm alert channels are configured, or record that alerting is not yet implemented.
- Confirm operator knows the manual kill-switch and pause-new-risk control paths.

## Startup Procedure

This procedure is target-state documentation until real services are wired.

1. Confirm the pre-run safety checklist.
2. Start or verify Temporal service availability.
3. Start workers on required task queues:
   - `market-data-task-queue`
   - `strategy-task-queue`
   - `ai-research-task-queue`
   - `execution-task-queue`
   - `reconciliation-task-queue`
   - `reporting-task-queue`
4. Confirm worker registration and task queue polling.
5. Confirm dashboard/control-plane read models load from safe backend contracts.
6. Confirm broker paper account mode through server-side broker activity once implemented.
7. Confirm database/audit ledger connectivity once implemented.
8. Confirm alert channel delivery once implemented.
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
- Normalize and deduplicate articles.
- Run schema-validated AI research once provider integration exists.
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
- Persist signal/candidate artifacts once database persistence exists.
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

- real database/audit persistence implementation and migration evidence;
- real Temporal query/signal backend integration;
- real Alpaca paper client integration and broker paper evidence;
- real AI/news provider integration and schema-validity evidence;
- real dashboard deployment evidence;
- alerting implementation and delivery evidence;
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
