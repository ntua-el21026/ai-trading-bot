# Autonomous AI Trading Bot - Execution-First Specification v0.4

**Document version:** v0.4
**Date:** 2026-05-13
**Target system:** Temporal-orchestrated autonomous AI-assisted trading bot with broker-level autonomous trade execution
**Primary objective:** Build a production-grade autonomous trading system that can independently generate, validate, execute, manage, reconcile, and report trades using deterministic strategy logic, bounded AI-assisted news/catalyst analysis, hard risk controls, Temporal durable workflows, broker reconciliation, and complete auditability.

**v0.4 policy extension:** deterministic paper-mode scale-in / pyramiding support before the
8-week frozen paper validation. This version permits one initial entry plus at most one
deterministic scale-in entry per symbol under strict paper-validation caps. It does not start
frozen validation, activate schedules, enable live trading, enable autonomous live execution,
permit leverage, or grant AI broker authority.

---

## 1. Executive Summary

This specification defines a trading-bot MVP whose central capability is **autonomous trade execution** under deterministic constraints.

The system is designed to operate at **Autonomy Level 4 first** and later support **Autonomy Level 5** after validation. In both levels, the system can place and manage live broker orders automatically, but only inside deterministic strategy, execution, reconciliation, and risk boundaries.

The defining architectural decision retained from v0.3 is:

```text
Temporal is part of the v0.1 architecture from the start.
```

Temporal is used as the durable workflow orchestration layer for execution-critical workflows. It coordinates scheduled workflows, retries, stateful order lifecycles, fill/stop handling, reconciliation, kill-switch behavior, and reporting pipelines.

The core safety principle remains:

```text
The system may execute autonomously.
The AI model may not execute directly.
Execution authority belongs to the deterministic execution pipeline.
```

The first production target is:

```text
US equities and ETFs
Daily / swing timeframe
Alpaca paper first
Alpaca live only after validation
Long-only
No leverage
No options
No shorting
No low-latency scalping
```

---

## 2. Locked Design Decisions

```text
1. Level 4 autonomous execution is the target.
2. v0.1 live mode is long-only, unleveraged, and conservative.
3. AI has no broker write permissions.
4. AI cannot submit trades, modify orders, override stops, or change risk limits.
5. Deterministic strategy/risk/execution/reconciliation is the authority.
6. Regime is a gate and risk multiplier, not an AI opinion.
7. AI is used only as a bounded news/catalyst/risk intelligence layer.
8. AI runs only on deterministic shortlist candidates, not on the full universe.
9. Vercel is dashboard/control-plane only.
10. Execution workers run outside Vercel.
11. Temporal is used from v0.1 for durable orchestration.
12. Paper trading is operational rehearsal, not proof of live profitability.
13. First live launch uses micro-live limits.
14. Expanded Level 4 and Level 5 require evidence from stable paper and micro-live runs.
15. Shorts, leverage, options, futures, crypto, and prediction markets are excluded from v0.1.
```

---

## 3. Core Philosophy

The system must be autonomous, but not unconstrained.

The desired behavior is:

```text
Autonomous execution inside deterministic boundaries.
```

Not:

```text
LLM chooses anything and sends broker orders.
```

The trading edge, if any, must come from a robust combination of:

1. deterministic market-regime filtering,
2. deterministic technical setup detection,
3. controlled position sizing,
4. strict risk management,
5. AI-assisted adverse-news and catalyst filtering,
6. systematic logging and review,
7. disciplined validation,
8. broker-safe execution,
9. durable orchestration.

The AI layer is an evidence-backed intelligence layer. It can analyze, score, explain, block, or reduce size within deterministic rules.

It cannot:

- call broker APIs,
- access broker credentials,
- create orders,
- modify orders,
- increase size,
- disable stops,
- disable kill switches,
- modify risk limits,
- mutate live strategy rules.

---

## 4. Goals and Non-Goals

### 4.1 Goals

The MVP must:

1. Run autonomously on scheduled workflows.
2. Use Temporal for execution-critical durable workflows.
3. Support paper trading and live trading environments.
4. Support autonomous live order submission after explicit configuration.
5. Support autonomous position management after order fill.
6. Support autonomous exits using deterministic exit logic.
7. Trade a limited approved universe of liquid US equities/ETFs.
8. Maintain a broader research universe for backtesting and candidate discovery.
9. Use a deterministic strategy engine as the primary signal source.
10. Use AI only for news/catalyst analysis, risk flagging, ranking assistance, journaling, explanations, and reports.
11. Enforce hard risk constraints before every order.
12. Attach and verify protective stops on every live position.
13. Reconcile broker state before and after execution.
14. Maintain a complete audit trail.
15. Provide a dashboard for monitoring and control.
16. Provide emergency shutdown through a kill switch.
17. Support autonomous safety-pausing on abnormal conditions.
18. Support staged validation:
    - historical backtest,
    - walk-forward validation,
    - simulated dry run,
    - autonomous paper trading,
    - Level 4 micro-live autonomous trading,
    - expanded Level 4,
    - Level 5 autonomous trading.

### 4.2 Non-Goals

The MVP will not initially support:

1. High-frequency trading.
2. Sub-second execution.
3. Market making.
4. Options.
5. Futures.
6. Margin/leverage.
7. Short selling.
8. Crypto perpetuals.
9. Prediction markets.
10. Low-float penny stocks.
11. Illiquid securities.
12. Automatic AI strategy mutation.
13. Unrestricted LLM-driven execution.
14. Natural-language broker order placement in production.
15. Alpaca MCP or natural-language trading interfaces in production execution path.
16. Selling signals to third parties.
17. Guaranteeing profitability.

---

## 5. Autonomy Model

| Level | Name                     | Execution Behavior                                                                |
| ----: | ------------------------ | --------------------------------------------------------------------------------- |
|     0 | Research Only            | AI summarizes markets. No signals. No orders.                                     |
|     1 | Signal Only              | Strategy generates signals. No broker orders.                                     |
|     2 | Paper Autonomous         | Bot executes automatically in paper account.                                      |
|     3 | Live Approval            | Bot proposes live orders, user approves manually.                                 |
|     4 | Live Autonomous Capped   | Bot executes live orders automatically under strict caps.                         |
|     5 | Live Autonomous Expanded | Bot executes live orders automatically with larger but still constrained capital. |

### 5.1 Target Level

```text
Build toward Level 4 as the first real live version.
Design the architecture so Level 5 can be enabled later after evidence.
```

### 5.2 Level 4 Micro-Live Definition

Level 4 micro-live means:

- live trades can be placed automatically,
- manual approval is not required per trade,
- capital is very small and capped,
- gross exposure is capped,
- position count is capped,
- sector exposure is capped,
- risk per trade is capped,
- daily/weekly/monthly loss limits are enforced,
- every trade must pass deterministic risk checks,
- every position must have an exit plan,
- every position must have a protective stop,
- all execution actions are logged,
- every order/fill/exit triggers an alert,
- kill switch is active,
- system self-pauses on critical failures.

### 5.3 Expanded Level 4 Definition

Expanded Level 4 may increase deployable capital and position count only after:

- stable paper operation,
- stable micro-live operation,
- no missing-stop incidents,
- no duplicate-order incidents,
- no unresolved reconciliation incidents,
- live slippage within expected envelope,
- no Sev-1 control incidents.

### 5.4 Level 5 Definition

Level 5 means:

- the system can run end-to-end without manual intervention during normal conditions,
- live capital may be increased,
- the universe may be expanded,
- position count may be increased,
- multiple strategies may be enabled,
- automated rebalancing/exit management may be active,
- automated reporting and review are mandatory.

Level 5 still requires hard risk gates, deterministic execution rules, broker reconciliation, kill switches, Temporal workflow auditability, complete logging, and no direct AI order submission.

---

## 6. Temporal Workflow Orchestration

### 6.1 Why Temporal Is Included From v0.1

Temporal is included from the start because autonomous trading workflows are stateful, failure-sensitive, and must survive partial execution failures.

The system must avoid fragile flows like:

```text
Submit order
API timeout
Process crashes
State unknown
Retry creates duplicate order
```

Temporal provides durable workflow execution so order lifecycles, retries, waits, timeouts, and incident transitions can be explicitly modeled and persisted.

### 6.2 Temporal Responsibilities

Temporal will orchestrate:

1. scheduled market workflows,
2. data-refresh workflows,
3. EOD signal-generation workflows,
4. AI catalyst-analysis workflows,
5. execution-intent workflows,
6. order-submission workflows,
7. fill-monitoring workflows,
8. protective-stop workflows,
9. partial-fill workflows,
10. cancel/replace workflows,
11. reconciliation workflows,
12. kill-switch workflows,
13. report-generation workflows.

### 6.3 Temporal Components

| Component                         | Role                                                                                  |
| --------------------------------- | ------------------------------------------------------------------------------------- |
| Temporal Service / Temporal Cloud | Durable workflow backend                                                              |
| Task Queues                       | Separate workflow/activity queues                                                     |
| Workers                           | Python workers executing workflows and activities                                     |
| Workflows                         | Deterministic orchestration logic                                                     |
| Activities                        | Side-effecting operations such as Alpaca API calls, DB writes, news fetches, AI calls |
| Signals                           | External events such as manual kill switch, approval, resume                          |
| Queries                           | Read workflow state for dashboard/control plane                                       |
| Schedules                         | Durable scheduled workflow triggers                                                   |

### 6.4 Task Queues

Recommended task queues:

```text
market-data-task-queue
strategy-task-queue
ai-research-task-queue
execution-task-queue
reconciliation-task-queue
reporting-task-queue
```

Execution-critical workflows must run on dedicated workers:

```text
execution-task-queue
reconciliation-task-queue
```

### 6.5 Workflow Determinism Rule

Temporal workflows must remain deterministic.

```text
Workflow code:
    orchestrates decisions,
    stores workflow state,
    waits for timers/signals,
    calls activities.

Activity code:
    calls Alpaca,
    calls database,
    calls AI APIs,
    fetches news,
    sends alerts,
    reads current time,
    performs non-deterministic I/O.
```

No broker API, AI API, news API, random generation, database query, or direct clock call should occur inside workflow code.

### 6.6 Core Workflows

#### 6.6.1 DailyDataRefreshWorkflow

Purpose:

- refresh adjusted bars,
- refresh latest quotes,
- refresh asset/reference data,
- refresh corporate actions,
- refresh earnings calendar,
- persist raw and normalized data,
- emit data freshness status.

#### 6.6.2 EODSignalWorkflow

Purpose:

- finalize EOD bars,
- compute features,
- compute regime,
- run deterministic strategy engine,
- build shortlist,
- persist candidates,
- create next-session trade plan draft.

#### 6.6.3 AIShortlistResearchWorkflow

Purpose:

- fetch normalized news only for deterministic shortlist,
- deduplicate articles,
- run AI structured-output analysis,
- validate schema,
- persist raw prompts, raw outputs, parsed outputs, model version, schema version, citations, and audit hashes,
- assign neutral fallback if invalid.

#### 6.6.4 DecisionWorkflow

Purpose:

- combine deterministic signals and validated AI outputs,
- apply regime gate,
- calculate final scores,
- rank candidates,
- apply hard blocks,
- create trade decisions.

#### 6.6.5 ExecutionIntentWorkflow

Purpose:

- transform approved decisions into execution intents,
- run final pre-risk checks,
- create idempotent intent records,
- create client order ID roots,
- hand off to OrderLifecycleWorkflow.

#### 6.6.6 OrderLifecycleWorkflow

Purpose:

- submit entry order,
- monitor broker acknowledgement,
- monitor fills,
- handle partial fills,
- place protective stop,
- verify stop via stream and REST,
- mark position as protected,
- handle unfilled order expiry,
- handle order rejection,
- emit alerts,
- transition to PositionLifecycleWorkflow after fill.

#### 6.6.7 PositionLifecycleWorkflow

Purpose:

- monitor open position,
- enforce stop status,
- manage app-level trailing stop updates,
- evaluate scheduled exits,
- submit risk-reducing exit orders,
- close and reconcile position,
- persist realized slippage/fill metrics.

#### 6.6.8 ReconciliationWorkflow

Purpose:

- reconcile internal ledger with broker account, orders, fills, and positions,
- detect mismatches,
- create incidents,
- trigger pause/kill-switch if required,
- update dashboard state.

#### 6.6.9 KillSwitchWorkflow

Purpose:

- transition system to `PAUSED_NEW_RISK` or stronger state,
- cancel pending entry orders if safe,
- preserve/verify protective exits,
- allow risk-reducing exits,
- emit critical alerts,
- require manual re-arm checklist.

#### 6.6.10 ReportingWorkflow

Purpose:

- generate daily report,
- generate weekly report,
- include decisions, rejections, fills, slippage, risk, AI summaries, incidents, and performance metrics.

### 6.7 Temporal Signals

Required signals:

```text
manual_kill_switch
manual_pause_new_risk
manual_resume_after_review
force_reconciliation
force_report
approve_level_change
acknowledge_incident
```

### 6.8 Temporal Queries

Required dashboard queries:

```text
get_current_system_state
get_active_workflows
get_active_execution_intents
get_open_order_lifecycles
get_open_position_lifecycles
get_recent_incidents
get_last_reconciliation_status
get_kill_switch_state
```

### 6.9 Retry Policies

Default non-critical activities:

```yaml
retry:
  initial_interval_seconds: 5
  backoff_coefficient: 2.0
  maximum_interval_seconds: 60
  maximum_attempts: 3
```

Broker order submission:

```yaml
broker_order_submit_retry:
  maximum_attempts: 1
  retry_only_after_idempotency_lookup: true
```

Protective stop:

```yaml
protective_stop_retry:
  maximum_attempts: 3
  initial_interval_seconds: 2
  maximum_interval_seconds: 10
```

AI activity:

```yaml
ai_retry:
  maximum_attempts: 2
  fallback_on_failure: "neutral"
```

### 6.10 Temporal and Database State

Temporal stores workflow state. Postgres stores durable business/audit state.

```text
Temporal:
    orchestration state,
    timers,
    retries,
    workflow history,
    workflow status.

Postgres:
    trading ledger,
    candidates,
    decisions,
    execution intents,
    orders,
    fills,
    positions,
    AI outputs,
    reports,
    incidents.
```

The database remains the business audit ledger.

---

## 7. Autonomous Execution Authority

### 7.1 Execution Authority Hierarchy

| Component                   |         May propose trades | May score trades | May block trades |                           May submit orders |
| --------------------------- | -------------------------: | ---------------: | ---------------: | ------------------------------------------: |
| AI intelligence service     | No direct trade generation |              Yes |              Yes |                                          No |
| Strategy engine             |                        Yes |              Yes |               No |                                          No |
| Decision arbiter            |                        Yes |              Yes |              Yes |                                          No |
| Risk engine                 |                         No |               No |              Yes |                                          No |
| Execution intent builder    |                         No |               No |               No |                                          No |
| Temporal execution workflow |                         No |               No |               No |                      Orchestrates execution |
| Broker adapter activity     |                         No |               No |               No | Yes, only when called by execution workflow |

Only the deterministic execution pipeline may submit broker orders, and only after receiving:

```text
approved_trade_decision
AND passed_risk_check
AND valid_execution_intent
AND valid_broker_reconciliation
AND active_autonomy_permission
AND kill_switch_off
```

### 7.2 Autonomous Execution Permission

Live autonomous execution requires all of these flags:

```yaml
execution:
  environment: "live"
  live_trading_enabled: true
  autonomous_execution_enabled: true
  autonomy_level: 4
  kill_switch_enabled: true
  allow_manual_approval_bypass: true
```

### 7.3 Explicit Execution Contract

No broker order may be submitted without a valid `ExecutionIntent`.

Required `ExecutionIntent` fields:

```json
{
  "decision_id": "uuid",
  "symbol": "AAPL",
  "side": "buy",
  "asset_class": "equity",
  "quantity": 10,
  "entry_order_type": "limit",
  "limit_price": 180.5,
  "stop_loss_price": 174.2,
  "time_in_force": "day",
  "strategy_version": "regime_filtered_breakout_v0_3",
  "risk_config_version": "risk_v0_3",
  "autonomy_level": 4,
  "requires_protective_stop": true,
  "max_acceptable_slippage_bps": 25,
  "expires_at": "2026-05-04T15:00:00Z"
}
```

---

## 8. Trading Scope

### 8.1 Asset Class

Initial target:

```text
US equities and ETFs
```

### 8.2 Broker

Initial broker:

```text
Alpaca
```

Required environments:

- paper trading,
- live trading.

### 8.3 Timeframe

Initial timeframe:

```text
Daily / swing trading
```

### 8.4 Live Universe

Initial approved live symbols:

```text
SPY
QQQ
DIA
IWM
XLK
XLF
XLE
XLV
AAPL
MSFT
NVDA
AMZN
META
GOOGL
```

Live universe requirements:

```yaml
live_universe:
  min_price: 20
  min_adv20_usd: 50000000
  allow_etfs: true
  allow_common_stocks: true
  allow_leveraged_etfs: false
  allow_inverse_etfs: false
```

### 8.5 Research Universe

The research universe is broader and rules-based.

```yaml
research_universe:
  min_price: 10
  min_adv20_usd: 20000000
  include_us_common_stocks: true
  include_major_etfs: true
  survivorship_bias_warning_required: true
  point_in_time_universe_preferred: true
```

Backtests without point-in-time universe data must be labeled optimistic.

### 8.6 Excluded Instruments

The MVP excludes:

- options,
- futures,
- crypto,
- penny stocks,
- illiquid stocks,
- leveraged ETFs,
- inverse ETFs,
- margin,
- short selling.

---

## 9. High-Level Architecture

```text
Temporal Schedules
        |
        v
Temporal Workflows
        |
        +--------------------------------------------------+
        |                                                  |
        v                                                  v
Market Data / News Activities                  Broker / Execution Activities
        |                                                  |
        v                                                  v
Postgres Ledger + Raw Data Store + Audit Trail + Workflow Metadata
        |
        v
Feature Engine
        |
        v
Regime Engine
        |
        v
Strategy Engine
        |
        v
Deterministic Shortlist
        |
        v
AI Intelligence Service
        |
        v
Validated AI JSON
        |
        v
Decision Arbiter
        |
        v
Risk Engine
        |
        v
ExecutionIntent
        |
        v
Temporal OrderLifecycleWorkflow
        |
        v
Alpaca Broker Adapter
        |
        v
Reconciliation Workflow
        |
        v
Reports / Alerts / Dashboard / Kill Switch
```

Final execution condition:

```text
deterministic_setup_valid = true
AND regime_allows_new_entries = true
AND decision = approved
AND risk_gate = pass
AND execution_intent_valid = true
AND broker_reconciliation_status = clean
AND kill_switch = off
AND autonomous_execution_enabled = true
```

---

## 10. EOD-First Daily Cadence

The system is EOD-first with a morning refresh. It does not mine new intraday alpha in v0.1.

All times are in `America/New_York`.

|        Time | Workflow                                       | Purpose                                                    |
| ----------: | ---------------------------------------------- | ---------------------------------------------------------- |
| 08:25-08:45 | `DailyDataRefreshWorkflow`                     | Refresh asset master, corporate actions, earnings calendar |
| 08:45-09:10 | `AIShortlistResearchWorkflow` refresh          | Refresh overnight news for shortlisted names               |
| 09:45-10:30 | `OrderLifecycleWorkflow`                       | New-entry execution window                                 |
| 10:30-16:00 | `PositionLifecycleWorkflow`                    | Monitoring and risk-reducing actions only                  |
| 16:10-16:30 | `EODSignalWorkflow`                            | Finalize EOD bars, features, regime, shortlist             |
| 16:30-17:00 | `AIShortlistResearchWorkflow`                  | AI catalyst scoring on deterministic shortlist             |
| 17:00-17:15 | `DecisionWorkflow`                             | Create next-session trade plan snapshot                    |
|       20:00 | `ReconciliationWorkflow` + `ReportingWorkflow` | Sanity reconciliation and report build                     |

Rules:

```text
No autonomous new-risk entries outside 09:45-10:30 ET.
No autonomous extended-hours entries in v0.1.
Risk-reducing exits may occur when allowed by configuration and broker/session rules.
```

---

## 11. Module Specification

### 11.1 Market Data Service

Responsibilities:

- ingest adjusted daily OHLCV,
- ingest latest quotes for execution,
- ingest corporate actions,
- ingest asset metadata,
- ingest earnings calendar,
- ingest ticker-tagged news,
- persist raw provider payloads,
- normalize provider-specific formats,
- compute data freshness status.

### 11.2 Universe Builder

Responsibilities:

- build research universe,
- build approved live universe,
- apply price filters,
- apply liquidity filters,
- exclude disallowed assets,
- detect symbol validity,
- detect asset metadata staleness,
- handle corporate-action blocks.

### 11.3 Feature Engine

Initial features:

- daily return,
- rolling volatility,
- ATR,
- SMA50,
- SMA200,
- EMA10,
- SMA20 volume,
- 20-day high,
- 55-day high,
- relative strength vs SPY,
- ATR percent,
- gap percent,
- distance from SMA50,
- distance from SMA200,
- dollar volume.

### 11.4 Regime Engine

The v0.1 regime engine is deterministic, rule-based, and auditable.

States:

```text
RISK_ON
CAUTION
RISK_OFF
```

Primary proxy:

```text
SPY
```

Formula:

```text
RV20 = sqrt(252) * std(log(Close_t / Close_{t-1}), 20)
```

Risk-on if:

```text
SPY close > 1.01 * SPY SMA200
AND condition holds for 3 consecutive closes
AND RV20 < 25%
AND SPY SMA50 > SPY SMA200
```

Risk-off if:

```text
SPY close < 0.99 * SPY SMA200 for 2 consecutive closes
OR RV20 > 35%
```

Caution:

```text
not risk-on
AND not risk-off
```

Hysteresis:

```text
After risk-off, require 3 trading-day cooldown before new entries.
To return to risk-on, require 3 closes above SMA200 and SMA50 > SMA200.
```

Regime effects:

| Regime   |                    New Entries | Size Multiplier |  Max Gross Exposure | Exit Behavior                        |
| -------- | -----------------------------: | --------------: | ------------------: | ------------------------------------ |
| RISK_ON  |                        Allowed |             1.0 | live mode dependent | Normal                               |
| CAUTION  | Allowed only with higher score |             0.5 |       half live cap | Normal, tighter selectivity          |
| RISK_OFF |                      Forbidden |             0.0 |         0% new risk | Block entries; flatten if persistent |

Persistent risk-off rule:

```text
If RISK_OFF persists for 3 consecutive trading days,
flatten remaining long exposure in the next liquid session using risk-reducing orders.
```

Future upgrade:

```text
HMM may be added in v0.2 as a shadow regime overlay only.
It must not control live gating until it beats the rule-based model in OOS and paper validation.
```

### 11.5 Deterministic Strategy Engine

Initial strategy family:

```text
Long-only trend-breakout continuation with relative-strength ranking.
```

The engine must support two research variants:

```yaml
breakout_variants:
  - 20
  - 55
```

The live default is selected after walk-forward validation.

Baseline candidate rule:

```text
New long candidate is valid if:

1. Regime is not RISK_OFF.
2. Symbol is in approved universe for live, or research universe for backtest.
3. Close > SMA50.
4. SMA50 > SMA200.
5. Price breaks above configured prior high:
       Close > HH20_prev
   or
       Close > HH55_prev
6. VolumeRatio20 >= threshold.
7. RS63 > 0.
8. RS63 percentile >= configured floor if using broad universe.
9. ATR14 / Close is inside allowed volatility band.
10. Price >= min_price.
11. ADV20 >= min_adv20_usd.
12. No earnings blackout.
13. Symbol is not already held, unless it is being evaluated as an explicit deterministic
    paper-validation scale-in candidate under section 15.8.
14. No active duplicate intent exists.
```

Baseline live parameters:

```yaml
strategy:
  trend_fast_ma: 50
  trend_slow_ma: 200
  breakout_lookback_primary: 20
  breakout_lookback_research_variants: [20, 55]
  volume_lookback_days: 20
  volume_ratio_min: 1.20
  relative_strength_lookback_days: 63
  relative_strength_min: 0.0
  relative_strength_percentile_floor_research: 70
  atr_period: 14
  atr_pct_min: 0.015
  atr_pct_max: 0.060
  min_live_price: 20
  min_live_adv20_usd: 50000000
  min_research_price: 10
  min_research_adv20_usd: 20000000
```

### 11.6 Exit Engine

Initial stop:

```text
initial_stop = entry_price - 2.0 * ATR14_at_entry
```

Research variant:

```text
initial_stop = entry_price - 2.5 * ATR14_at_entry
```

Trailing stop:

```text
app-level trailing stop = max(old_stop, highest_close_since_entry - 2.5 * ATR14)
```

Research variant:

```text
highest_close_since_entry - 3.0 * ATR14
```

Technical exit:

```text
Exit after 2 consecutive closes below EMA10.
```

Time stop:

```text
Exit after 20 trading days if unrealized PnL < +0.5R.
```

Fail-fast exit:

```text
If position closes back below breakout level within first 5 bars, exit.
```

No fixed take-profit is enabled by default in v0.1.

### 11.7 Earnings Blackout

Earnings blackout is deterministic.

```yaml
earnings_blackout:
  enabled: true
  block_entries_before_trading_sessions: 2
  block_entries_after_trading_sessions: 1
  allow_exits_during_blackout: true
```

---

## 12. AI Intelligence Service

### 12.1 Role

AI is used only on deterministic shortlist candidates.

AI responsibilities:

- summarize symbol-level catalyst context,
- extract events,
- classify event direction,
- identify adverse-news risks,
- detect blocking risks,
- produce bounded AI score,
- explain trade context,
- generate daily/weekly reports.

AI does not scan the full universe for trades in v0.1.

### 12.2 Data Sources

Milestone 22 provider-first news policy:

```text
Primary ticker-tagged news:
    Marketaux

Fallback / cross-check ticker-tagged news:
    Alpha Vantage

Structured AI analysis:
    OpenAI structured output over provider-fetched deterministic shortlist news only

Sparse-case web fallback:
    OpenAI web search, disabled by default and allowed only as audited exception behavior
```

Raw news payloads, normalized articles, AI prompt/output hashes, parsed outputs, provider budget
events, and calibration reports must be persisted or made available through ledger/reporting
boundaries where feasible.

### 12.3 Retrieval Policy

```yaml
ai_news:
  default_lookback_calendar_days: 7
  extended_event_lookback_calendar_days: 14
  max_articles_per_symbol: 12
  provider_primary: "marketaux"
  provider_fallback: "alpha_vantage"
  marketaux_daily_request_limit: 90
  alpha_vantage_daily_request_limit: 20
  max_symbols_per_run: 5
  openai_web_fallback_enabled: false
  openai_web_daily_request_limit: 5
  no_social_media: true
  no_forum_scraping: true
  persist_raw_payloads: true
  persist_canonical_urls: true
```

Provider retrieval rules:

- never scan the full universe,
- accept only explicit deterministic shortlist symbols,
- enforce max symbols and max articles per run,
- enforce daily request budgets before each real provider request,
- use 7 calendar days by default and 14 days for extended event/risk lookups,
- normalize provider-specific payloads into a provider-independent article model,
- deduplicate by canonical URL, provider ID, and title/source/timestamp heuristics,
- use neutral/no-news behavior when no articles are found,
- never allow provider data to create broker orders directly.

### 12.4 Event Taxonomy

Initial event taxonomy:

| Event Type                                   | Base Direction                |
| -------------------------------------------- | ----------------------------- |
| earnings surprise / guidance revision        | positive or negative          |
| offering / dilution / shelf / convert        | negative                      |
| M&A / strategic deal                         | positive or mixed             |
| lawsuit / SEC / FDA / halt / accounting risk | negative                      |
| analyst upgrade / downgrade                  | moderate positive or negative |
| product / contract / management change       | moderate                      |
| dividend / split / calendar-only             | weak                          |
| generic macro mention                        | weak                          |

The AI extracts events. Deterministic code maps events to scores.

### 12.5 AI Score

Recency decay:

```text
w_time = exp(-hours_since_publication / 72)
```

Source-quality weight:

```text
regulatory filing / company PR / premier financial publisher: 1.0
secondary aggregation: 0.7
low-substance rewrite: 0.4
```

Raw catalyst score:

```text
AI_raw = clip(sum(direction_sign * event_weight * w_time * w_source), -5, 5)
```

Mapped score:

```text
AI_score = clip(50 + 8 * AI_raw, 10, 90)
```

Interpretation:

```text
AI_score >= 65: supportive
45 <= AI_score < 65: neutral / mixed
AI_score < 45: adverse
hard_block = true: block
```

### 12.6 Fallbacks

```text
No news found:
    state = insufficient_data
    ai_score = 50
    hard_block = false

Invalid schema:
    retry once
    if still invalid:
        ai_score = 50
        hard_block = false
        incident severity = warning

AI provider outage:
    neutral fallback
    no global kill-switch
    alert if repeated

Conflicting sources:
    mixed state
    size multiplier <= 0.75
    no hard block unless high-severity risk exists
```

AI failure does not trigger a global trading kill switch by itself.

### 12.7 OpenAI Model And Web Fallback Controls

Configured OpenAI model names must be read from environment/config and must not be assumed valid.
Default tests must not require OpenAI credentials or valid remote model IDs. If an OpenAI model-list
smoke is explicitly requested, the model list may be checked only with:

```text
RUN_OPENAI_MODEL_LIST_SMOKE=1
OPENAI_MODEL_LIST_CONFIRM=LIST_AVAILABLE_MODELS_ONLY
```

If the configured model is unavailable, the AI path fails closed with sanitized status and neutral
behavior. Raw API keys and raw provider responses must not be printed.

OpenAI web fallback is disabled by default and exception-only. It may run only when enabled by
policy, explicitly allowed at runtime, within its daily request budget, and one of these conditions
holds:

- Marketaux and Alpha Vantage return no articles for a shortlisted symbol,
- providers conflict on high-severity news,
- legal/regulatory/accounting/FDA-style risk is suspected but provider context is incomplete,
- AI confidence is low and the trade would otherwise pass,
- a hard-block decision depends on missing context.

Web fallback output is advisory only. It cannot create orders, modify orders, change stops, change
strategy rules, change risk limits, expand the universe, or access broker credentials.

### 12.8 AI Feedback And Calibration

Autonomous AI feedback/calibration is approved only as evaluation, reporting, warning, escalation,
and safety-degradation behavior.

Allowed behavior:

- evaluate historical AI outputs against later outcomes,
- compute schema-validity, provider-coverage, no-news, fallback, hard-block, missed-risk,
  confidence-bucket, score-bucket, drawdown/outcome proxy, and version-breakdown metrics,
- generate calibration reports,
- produce AI quality warnings or incident recommendations,
- recommend or set internal AI safety states:
  - `AI_NORMAL`,
  - `AI_REDUCED_INFLUENCE`,
  - `AI_NEUTRAL_ONLY`,
  - `AI_ESCALATION_REQUIRED`.

AI safety states may only reduce, neutralize, or escalate AI influence. They must never increase
position size, mutate strategy rules, change risk limits, change execution rules, change stop
policy, expand the universe, enable live trading, override deterministic risk checks, override kill
switches, or call broker APIs.

---

## 13. Decision Arbiter

### 13.1 Regime Is Outside The Main Score

Regime is a gate and size multiplier.

```text
if regime == RISK_OFF:
    block new entries

if regime == CAUTION:
    require FinalScore >= 80
    size *= 0.5

if regime == RISK_ON:
    require FinalScore >= 72
```

### 13.2 Final Score

```text
FinalScore =
    0.60 * TechnicalScore
  + 0.20 * RelativeStrengthScore
  + 0.10 * AIScore
  + 0.10 * PortfolioFitScore
```

Initial thresholds:

```yaml
decision:
  final_score_min_risk_on: 72
  final_score_min_caution: 80
  risk_off_blocks_new_entries: true
```

### 13.3 Technical Score

```text
TechnicalScore =
    0.35 * TrendScore
  + 0.35 * BreakoutScore
  + 0.15 * VolumeScore
  + 0.15 * VolatilityScore
```

### 13.4 Hard Blocks

Hard blocks outside the weighted score:

- regime = `RISK_OFF`,
- price/liquidity filter failure,
- protective stop unavailable,
- stale market data,
- duplicate order intent,
- unresolved broker mismatch,
- earnings within blackout window,
- corporate-action ambiguity,
- AI high-severity blocking risk with confidence >= 0.70,
- kill switch active,
- live autonomous execution disabled.

### 13.5 Size Reductions

```text
CAUTION regime:
    size *= 0.5

AI adverse / uncertain with confidence 0.55-0.70:
    size *= 0.75

AI high risk:
    size *= 0.5

Execution spread above warning threshold:
    size *= 0.5 or skip, depending on severity
```

---

## 14. Risk Engine

### 14.1 Level 4 Micro-Live Limits

The first live autonomous version is deliberately under-deployed.

```yaml
risk_level_4_micro_live:
  max_gross_exposure_pct: 0.20
  max_deployable_capital_pct: 0.20
  max_position_size_pct: 0.04
  max_risk_per_trade_pct: 0.0035
  max_open_positions: 5
  max_sector_exposure_pct: 0.10
  min_cash_buffer_pct: 0.75
  max_daily_loss_pct: 0.01
  max_weekly_loss_pct: 0.025
  max_monthly_loss_pct: 0.05
  allow_margin: false
  allow_shorting: false
  allow_options: false
  allow_leveraged_etfs: false
  require_protective_stop: true
```

### 14.2 Expanded Level 4 Limits

Allowed only after stability.

```yaml
risk_level_4_expanded:
  max_gross_exposure_pct: 0.60
  max_deployable_capital_pct: 0.60
  max_position_size_pct: 0.10
  max_risk_per_trade_pct: 0.0035
  max_open_positions: 6
  max_sector_exposure_pct: 0.20
  min_cash_buffer_pct: 0.35
  max_daily_loss_pct: 0.0125
  max_weekly_loss_pct: 0.03
  max_monthly_loss_pct: 0.06
```

### 14.3 Risk Checks Before New Entry

```text
1. Is live/paper mode valid?
2. Is autonomous execution enabled?
3. Is symbol approved?
4. Is asset class approved?
5. Is market/session valid?
6. Is data fresh?
7. Is broker account synced?
8. Is kill switch off?
9. Is max daily loss breached?
10. Is max weekly loss breached?
11. Is max monthly loss breached?
12. Would position exceed max size?
13. Would gross exposure exceed cap?
14. Would sector exposure exceed cap?
15. Would open position count exceed cap?
16. Is stop loss defined?
17. Is estimated risk within max risk per trade?
18. Is cash buffer preserved?
19. Is order duplicate?
20. Is broker account in expected mode?
21. Has system health check passed?
22. Is Temporal workflow state consistent?
```

For a paper-validation scale-in entry, the same new-risk checks apply plus the additional
section 15.8 scale-in gates. A protected existing long position does not by itself block scale-in
evaluation. An unprotected position, pending entry order, ambiguous open order, unresolved symbol
incident, reconciliation mismatch, missing deterministic add-on signal, or exceeded
symbol/portfolio/risk cap must block new risk.

### 14.4 Position Sizing

```text
risk_amount = account_equity * max_risk_per_trade_pct
stop_distance = entry_price - stop_price
raw_shares = floor(risk_amount / stop_distance)
max_value_shares = floor((account_equity * max_position_size_pct) / entry_price)
shares = min(raw_shares, max_value_shares)
```

Then apply multipliers:

```text
shares *= regime_size_multiplier
shares *= ai_size_multiplier
shares *= execution_quality_multiplier
```

If shares < 1:

```text
skip trade
```

---

## 15. Execution Engine

### 15.1 Order Types

For new-risk entries:

```text
Use DAY limit or marketable limit orders.
Do not use market orders for new entries.
Do not use extended-hours entries.
```

For risk-reducing exits:

```text
Use marketable limit for scheduled exits.
Use broker protective stops for downside protection.
Use market exits only for kill-switch / control-failure cases.
```

### 15.2 Entry Window

```yaml
execution:
  entry_window_start_et: "09:45"
  entry_window_end_et: "10:30"
  unfilled_entry_cancel_time_et: "11:00"
```

### 15.3 Protective Stop Policy

Every filled position must have a protective stop.

```yaml
protective_stop:
  warning_after_seconds: 5
  critical_after_seconds: 30
  flatten_after_seconds: 60
  max_retries: 3

scale_in:
  enabled_for_paper_validation: true
  max_entries_per_symbol: 2
  max_add_entries_per_symbol: 1
  max_new_entry_qty: 1
  max_scale_in_qty: 1
  max_total_symbol_qty: 2
  max_pending_entry_orders_per_symbol: 0
  max_unresolved_incidents_per_symbol: 0
  require_existing_stop_verified: true
  require_add_on_signal: true
  require_no_pending_entry_order: true
  require_no_unresolved_symbol_incident: true
  protective_stop_required_before_scale_in: true
  protective_stop_required_after_scale_in: true
  stop_policy: "additive_stop_for_added_quantity"
  allow_stop_replacement: false
  allow_stop_cancel_before_scale_in: false
  block_if_protected_quantity_below_position_quantity: true
```

Behavior:

```text
If stop is not confirmed after 5 seconds:
    warning incident

If stop is not confirmed after 30 seconds:
    critical incident
    pause new entries

If stop is not confirmed after 60 seconds:
    flatten position if safe
```

### 15.4 App-Level Trailing Stop

The primary trailing logic is application-level.

```text
Do not rely on broker-native trailing stop as the primary exit engine in v0.1.
```

The system may cancel/replace stop orders only when the new stop is tighter and risk-reducing.

### 15.5 Partial Fills

Partial-fill handling:

```text
If partial fill occurs:
    protective stop quantity must match filled quantity.
    remaining unfilled entry quantity remains active only until expiry.
    after expiry, cancel remainder.
    never leave filled quantity unprotected.
```

### 15.6 Idempotency

Use broker `client_order_id` plus DB uniqueness constraints.

Recommended format:

```text
{strategy}-{symbol}-{side}-{trade_date}-{intent_seq}-{short_hash}
```

Before retrying order submission:

```text
1. Query broker by client_order_id.
2. Query internal DB by execution_intent_id.
3. If broker already accepted order, do not resubmit.
4. If state ambiguous, pause workflow and trigger reconciliation.
```

### 15.7 Order Lifecycle

Temporal `OrderLifecycleWorkflow`:

```text
1. Receive ExecutionIntent.
2. Validate Temporal workflow state.
3. Run pre-submit risk checks.
4. Run pre-submit broker reconciliation.
5. Submit entry order via activity.
6. Await broker acknowledgement.
7. Monitor fill via stream and REST fallback.
8. If unfilled by expiry, cancel.
9. If filled or partially filled, submit protective stop.
10. Verify stop via stream and REST.
11. Mark position PROTECTED.
12. Emit alerts.
13. Start PositionLifecycleWorkflow.
```

### 15.8 Deterministic Paper Scale-In Policy

v0.4 adds a conservative paper-mode scale-in policy before the 8-week frozen paper validation.
This policy does not start frozen validation, activate schedules, enable live trading, enable
autonomous live execution, permit leverage, permit shorts, or grant AI broker authority.

Scale-in is limited to the configured paper validation universe. The strategy may evaluate the
full configured allowed universe, but no symbol is forced to trade. Symbols with existing
protected paper holdings may be evaluated as scale-in candidates only through deterministic
strategy, risk, execution, reconciliation, and duplicate-intent gates.

Required paper-validation caps:

```yaml
scale_in:
  enabled_for_paper_validation: true
  max_entries_per_symbol: 2
  max_add_entries_per_symbol: 1
  max_new_entry_qty: 1
  max_scale_in_qty: 1
  max_total_symbol_qty: 2
  max_pending_entry_orders_per_symbol: 0
  max_unresolved_incidents_per_symbol: 0
  require_existing_stop_verified: true
  require_add_on_signal: true
  require_no_pending_entry_order: true
  require_no_unresolved_symbol_incident: true
  protective_stop_required_before_scale_in: true
  protective_stop_required_after_scale_in: true
  stop_policy: "additive_stop_for_added_quantity"
  allow_stop_replacement: false
  allow_stop_cancel_before_scale_in: false
  block_if_protected_quantity_below_position_quantity: true
```

Existing position rule:

```text
An existing long position may be considered for scale-in only when:
  - position quantity is > 0 and < max_total_symbol_qty,
  - verified protective stop coverage exists for the current position,
  - protected quantity is reconciled as sufficient,
  - no unresolved incident exists for that symbol,
  - no pending entry order exists for that symbol,
  - no ambiguous or stale open order exists for that symbol,
  - broker reconciliation is clean,
  - a deterministic add-on signal permits the add,
  - aggregate symbol quantity after add remains <= max_total_symbol_qty,
  - symbol notional, portfolio exposure, and aggregate risk-at-stop remain within caps,
  - a valid ExecutionIntent exists before order submission.
```

Open order classification is deterministic:

| Role | Scale-in behavior |
| ---- | ----------------- |
| `protective_stop` | Allowed and required when verified. It does not block scale-in by itself. |
| `pending_entry` | Blocks scale-in. |
| `pending_exit` | Blocks new risk. |
| `stale_session_order` | Blocks scale-in until resolved. |
| `unknown_or_ambiguous` | Blocks scale-in until resolved. |

Add-on signal rule:

```text
Scale-in requires a fresh deterministic add-on signal. Existing profit, a prior entry, or AI/news
output cannot authorize scale-in. If no deterministic add-on signal exists, the scale-in decision
must refuse new risk.
```

Stop handling after scale-in:

```text
Do not cancel or replace existing protective stops in the scale-in path.
Keep the existing protective stop intact.
After an add-on entry fill, submit a separate protective stop only for the newly filled quantity.
Verify the add-on stop through broker read-back.
If add-on stop verification fails, classify a SAFE INCIDENT, block further new risk, and use only
the already approved emergency cleanup path when that path explicitly permits it.
```

Aggregate protection rule:

```text
protected_quantity_sum >= open_position_quantity
```

After a scale-in fill, reconciliation must prove the summed verified protective-stop quantity is at
least the open symbol position quantity. Under-protected positions are incidents and block new risk.

Duplicate execution prevention:

```text
No duplicate active ExecutionIntent for the same symbol/side/signal.
No second scale-in for the same signal.
No concurrent scale-in for the same symbol.
No scale-in while an entry order is pending.
No scale-in while a previous add-on stop is unverified.
```

Reporting must distinguish:

- `initial_entry`,
- `scale_in_entry`,
- `initial_protective_stop`,
- `add_on_protective_stop`,
- `exit`,
- `cleanup`,
- `incident_repair`.

Frozen paper validation reports must record initial-entry count, scale-in-entry count, scale-in
success/failure, total symbol quantity after scale-in, protected quantity after scale-in, scale-in
incidents, and PnL attribution notes when partial scale-in exists.

---

## 16. Broker Reconciliation

### 16.1 Broker Truth Model

The broker is the external executable truth. The database is the intended/audit truth.

### 16.2 Channels

```text
Primary:
    Alpaca trade_updates stream

Fallback:
    REST polling every 30 seconds during active windows
```

### 16.3 Reconciliation Schedule

```text
Pre-execution reconciliation:
    before every new-risk order

Active-window reconciliation:
    every 30 seconds while orders are open

EOD reconciliation:
    after market close

BOD reconciliation:
    before next market open
```

### 16.4 Critical Mismatches

Critical mismatches:

- broker position exists but internal position does not,
- internal position exists but broker position does not,
- position exists without protective stop,
- position exists where summed verified protective-stop quantity is below open position quantity,
- duplicate open entry orders,
- unexpected short position,
- account equity mismatch above threshold,
- order fill not recorded internally,
- symbol/corporate-action mismatch,
- avg entry price drift not explained by broker adjustment,
- Temporal workflow state inconsistent with DB order state.

### 16.5 Mismatch Behavior

```text
1. Pause new entries.
2. Create incident.
3. Notify user.
4. Attempt safe reconciliation.
5. Keep or verify protective exits.
6. Require manual review if unresolved.
```

---

## 17. Kill Switch

### 17.1 Kill Switch States

```text
RUNNING
PAUSED_NEW_RISK
PAUSED_ALL_AUTONOMOUS_ACTIONS
FORCE_FLAT_REQUESTED
MANUAL_REVIEW_REQUIRED
```

### 17.2 Kill Switch Triggers

Kill-switch triggers:

- daily loss breach,
- weekly loss breach,
- monthly loss breach,
- protective stop not confirmed,
- unresolved broker/internal mismatch,
- repeated order rejections,
- stale quotes,
- stale daily bars,
- unexpected corporate action,
- duplicate active entry intent,
- unexpected position,
- multiple invalid AI payloads in same run,
- Temporal workflow failure in execution path,
- execution worker unavailable,
- websocket disconnected with no REST fallback during active execution window.

### 17.3 Behavior After Kill Switch

```text
1. Disable new entries.
2. Cancel pending entry orders if safe.
3. Preserve or verify protective exits.
4. Allow risk-reducing exits unless explicitly disabled.
5. Run full reconciliation.
6. Create incident snapshot.
7. Notify user.
8. Require manual re-arm checklist.
```

Important:

```text
Kill switch blocks new risk.
Protective exits may remain allowed to reduce existing risk.
```

---

## 18. Data and Infrastructure Stack

### 18.1 Recommended Stack

```text
Workflow orchestration:
    Temporal Cloud or self-hosted Temporal

Broker / execution:
    Alpaca

Historical daily bars:
    Tiingo or Polygon / Massive

Ticker-tagged news:
    Polygon / Massive News

Calendar / transcripts fallback:
    Finnhub + Financial Modeling Prep

Backend:
    FastAPI

Database / ledger:
    Supabase PostgreSQL or managed Postgres

Workers:
    Python Temporal workers deployed on Cloud Run services or another long-running worker environment

Scheduler:
    Temporal Schedules

Secrets:
    Google Secret Manager or deployment-provider secret manager

Frontend / dashboard:
    Next.js on Vercel

Alerts:
    Telegram initially
    Email/Resend optional future secondary channel after evidence review

Logging:
    structured JSON logs + Postgres audit tables + cloud logs
```

### 18.2 Vercel Policy

```text
Vercel is dashboard-only.
No autonomous order execution runs on Vercel.
No broker credentials are exposed to Vercel frontend.
```

Milestone 26 may use a minimal static Vercel preview harness as an interim dashboard-only
validation artifact when no frontend framework has been introduced yet. This preview must expose
only approved public environment values, include no order-entry controls, run no workers or
execution services, and make no broker, AI/news, database, Temporal, or alert-provider calls from
browser code. The static preview does not replace the final dashboard target, does not constitute
production deployment evidence, and does not satisfy paper trading or Level 4 readiness.

### 18.3 Production Data Policy

```text
Production signals must not rely solely on Alpaca free IEX feed.
Use SIP-quality or consolidated data where possible.
```

### 18.4 Alert Delivery Policy

Telegram is the initial v0.1 real alert delivery channel.

Email/Resend is intentionally deferred and is not required before the initial Telegram alert harness
validation. Email may be reconsidered later as an optional secondary channel for daily/weekly
reports and critical backup alerts only after paper evidence and/or profitability justification.

Deferring email does not weaken the current execution/risk safety boundary because Telegram
critical alerts remain required for this stage and alerting remains operator-facing only.

Alerting cannot:

- create or modify orders,
- change stops,
- mutate strategy, risk, execution, universe, or kill-switch rules,
- enable live trading,
- enable autonomous live execution,
- access broker credentials,
- act as a Telegram command/control trading interface.

Before Level 4 micro-live, the final readiness review must either verify Telegram-only alert
sufficiency or explicitly approve a secondary alert delivery channel.

### 18.5 Paper Trading Policy

Paper trading is operational rehearsal.

It validates:

- workflow orchestration,
- broker integration,
- stop placement,
- reconciliation,
- logging,
- kill switches,
- reports.

It does not prove:

- live fill quality,
- market impact,
- queue position,
- price improvement,
- live slippage,
- live profitability.

---

## 19. Database Specification

Recommended database:

```text
Postgres / Supabase
```

Core business tables:

```text
symbols
raw_provider_payloads
ohlcv_daily
features_daily
regimes
trade_candidates
ai_research_outputs
trade_decisions
risk_checks
execution_intents
orders
fills
positions
broker_reconciliations
system_events
reports
```

The database must store:

- raw provider payloads,
- payload hashes,
- adjusted OHLCV,
- computed features,
- regime states,
- trade candidates,
- AI prompts,
- AI raw outputs,
- parsed AI outputs,
- prompt/model/schema versions,
- decisions,
- risk checks,
- execution intents,
- orders,
- fills,
- positions,
- reconciliation snapshots,
- incidents,
- reports.

The `execution_intents` table must include:

```text
temporal_workflow_id
client_order_id_root
status
payload
expires_at
```

The `orders` table must include:

```text
broker_order_id
client_order_id
raw_broker_payload
```

The `broker_reconciliations` table must include:

```text
temporal_workflow_id
account_snapshot
broker_positions
internal_positions
broker_orders
internal_orders
mismatches
```

---

## 20. Configuration Files

### 20.1 config/system.yaml

```yaml
system:
  environment: "paper"
  timezone_market: "America/New_York"
  timezone_user: "Europe/Athens"
  dry_run: true
  live_trading_enabled: false
  autonomous_execution_enabled: false
  autonomy_level: 2
  kill_switch_enabled: true
  require_broker_reconciliation: true
  pause_on_reconciliation_error: true
```

### 20.2 config/temporal.yaml

```yaml
temporal:
  namespace: "autonomous-trading"
  task_queues:
    market_data: "market-data-task-queue"
    strategy: "strategy-task-queue"
    ai_research: "ai-research-task-queue"
    execution: "execution-task-queue"
    reconciliation: "reconciliation-task-queue"
    reporting: "reporting-task-queue"

  schedules:
    daily_data_refresh: "25 8 * * 1-5"
    eod_signal_generation: "10 16 * * 1-5"
    ai_shortlist_research: "30 16 * * 1-5"
    trade_plan_snapshot: "0 17 * * 1-5"
    sanity_reconciliation: "0 20 * * 1-5"

  retry_defaults:
    initial_interval_seconds: 5
    backoff_coefficient: 2.0
    maximum_interval_seconds: 60
    maximum_attempts: 3
```

### 20.3 config/execution.yaml

```yaml
execution:
  autonomous_execution_enabled: false
  allow_live_orders: false
  require_execution_intent: true
  require_passed_risk_check: true
  require_broker_reconciliation_before_order: true
  require_protective_stop: true
  entry_order_type: "limit"
  entry_time_in_force: "day"
  entry_window_start_et: "09:45"
  entry_window_end_et: "10:30"
  unfilled_entry_cancel_time_et: "11:00"
  max_acceptable_slippage_bps: 25
  pause_on_order_submit_failure: true
  pause_on_stop_failure: true
  notify_on_every_order: true

protective_stop:
  warning_after_seconds: 5
  critical_after_seconds: 30
  flatten_after_seconds: 60
  max_retries: 3
```

### 20.4 config/universe.yaml

```yaml
live_universe:
  symbols:
    - SPY
    - QQQ
    - DIA
    - IWM
    - XLK
    - XLF
    - XLE
    - XLV
    - AAPL
    - MSFT
    - NVDA
    - AMZN
    - META
    - GOOGL
  min_price: 20
  min_adv20_usd: 50000000
  allow_options: false
  allow_shorting: false
  allow_leveraged_etfs: false
  allow_inverse_etfs: false

research_universe:
  min_price: 10
  min_adv20_usd: 20000000
  include_us_common_stocks: true
  include_major_etfs: true
  point_in_time_universe_preferred: true
```

### 20.5 config/strategy.yaml

```yaml
strategy:
  name: "regime_filtered_breakout_v0_3"
  trend_fast_ma: 50
  trend_slow_ma: 200
  breakout_lookback_primary: 20
  breakout_lookback_research_variants:
    - 20
    - 55
  volume_lookback_days: 20
  volume_ratio_min: 1.20
  relative_strength_lookback_days: 63
  relative_strength_min: 0.0
  relative_strength_percentile_floor_research: 70
  atr_period: 14
  atr_pct_min: 0.015
  atr_pct_max: 0.060
  initial_stop_atr_multiplier: 2.0
  initial_stop_atr_multiplier_research_variants:
    - 2.0
    - 2.5
  trailing_stop_atr_multiplier: 2.5
  trailing_stop_atr_multiplier_research_variants:
    - 2.5
    - 3.0
  technical_exit_ema: 10
  technical_exit_confirm_closes: 2
  time_stop_days: 20
  fail_fast_exit_days: 5
```

### 20.6 config/regime.yaml

```yaml
regime:
  model_version: "rule_based_regime_v0_3"
  states:
    - RISK_ON
    - CAUTION
    - RISK_OFF
  proxy: "SPY"
  sma_slow: 200
  sma_fast: 50
  risk_on_above_sma200_multiplier: 1.01
  risk_off_below_sma200_multiplier: 0.99
  risk_on_confirm_closes: 3
  risk_off_confirm_closes: 2
  rv20_risk_on_max: 0.25
  rv20_risk_off_min: 0.35
  risk_off_cooldown_days: 3
```

### 20.7 config/risk.yaml

```yaml
risk_level_4_micro_live:
  max_gross_exposure_pct: 0.20
  max_deployable_capital_pct: 0.20
  max_position_size_pct: 0.04
  max_risk_per_trade_pct: 0.0035
  max_open_positions: 5
  max_sector_exposure_pct: 0.10
  min_cash_buffer_pct: 0.75
  max_daily_loss_pct: 0.01
  max_weekly_loss_pct: 0.025
  max_monthly_loss_pct: 0.05
  allow_margin: false
  allow_shorting: false
  allow_options: false
  allow_leveraged_etfs: false
  require_protective_stop: true

risk_level_4_expanded:
  max_gross_exposure_pct: 0.60
  max_deployable_capital_pct: 0.60
  max_position_size_pct: 0.10
  max_risk_per_trade_pct: 0.0035
  max_open_positions: 6
  max_sector_exposure_pct: 0.20
  min_cash_buffer_pct: 0.35
  max_daily_loss_pct: 0.0125
  max_weekly_loss_pct: 0.03
  max_monthly_loss_pct: 0.06
```

### 20.8 config/ai.yaml

```yaml
ai:
  enabled: true
  provider: "openai"
  model: "configured_in_env"
  require_json_schema: true
  allow_ai_to_create_orders: false
  allow_ai_to_modify_strategy: false
  allow_ai_to_modify_risk_limits: false
  analyze_full_universe: false
  analyze_deterministic_shortlist_only: true
  default_news_lookback_calendar_days: 7
  extended_event_lookback_calendar_days: 14
  max_articles_per_symbol: 12
  batch_size_symbols: 5
  max_batch_size_symbols: 8
  missing_news_fallback_score: 50
  invalid_output_fallback_score: 50
  hard_block_confidence_min: 0.70
  prompt_version: "ai_trade_research_v0_3"
  schema_version: "ai_trade_research_schema_v0_3"
  news_provider_primary: "marketaux"
  news_provider_fallback: "alpha_vantage"
  marketaux_daily_request_limit: 90
  alpha_vantage_daily_request_limit: 20
  news_max_symbols_per_run: 5
  news_max_articles_per_symbol: 3
  news_enable_openai_web_fallback: false
  news_openai_web_daily_request_limit: 5
  openai_model: "gpt-5.2"
  openai_escalation_model: "gpt-5.2-pro"
  openai_fallback_model: "gpt-5-mini"
  ai_daily_request_limit: 25
  ai_max_symbols_per_run: 5
  ai_max_articles_per_symbol: 3
  ai_require_structured_output: true
  ai_neutral_fallback_on_error: true
  ai_enable_escalation: false
  ai_feedback_enabled: true
  ai_feedback_min_schema_validity_rate: 0.99
  ai_feedback_min_provider_coverage_rate: 0.60
  ai_feedback_max_fallback_rate: 0.35
  ai_feedback_max_missed_risk_false_negative_proxy_rate: 0.15
```

---

## 21. Environment Variables

```bash
DATABASE_URL=
TEMPORAL_ADDRESS=
TEMPORAL_NAMESPACE=
TEMPORAL_API_KEY=
TEMPORAL_TLS_CERT=
TEMPORAL_TLS_KEY=
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=
AI_PROVIDER=
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_ESCALATION_MODEL=
OPENAI_FALLBACK_MODEL=
MARKETAUX_API_KEY=
ALPHA_VANTAGE_API_KEY=
NEWS_PROVIDER_PRIMARY=
NEWS_PROVIDER_FALLBACK=
NEWS_MARKETAUX_DAILY_REQUEST_LIMIT=
NEWS_ALPHA_VANTAGE_DAILY_REQUEST_LIMIT=
NEWS_MAX_SYMBOLS_PER_RUN=
NEWS_MAX_ARTICLES_PER_SYMBOL=
NEWS_DEFAULT_LOOKBACK_DAYS=
NEWS_EXTENDED_LOOKBACK_DAYS=
NEWS_ENABLE_OPENAI_WEB_FALLBACK=
NEWS_OPENAI_WEB_DAILY_REQUEST_LIMIT=
AI_DAILY_REQUEST_LIMIT=
AI_MAX_SYMBOLS_PER_RUN=
AI_MAX_ARTICLES_PER_SYMBOL=
AI_REQUIRE_STRUCTURED_OUTPUT=
AI_NEUTRAL_FALLBACK_ON_ERROR=
AI_ENABLE_ESCALATION=
RUN_NEWS_PROVIDER_SMOKE=
NEWS_PROVIDER_SMOKE_CONFIRM=
NEWS_PROVIDER_SMOKE_SYMBOLS=
RUN_OPENAI_MODEL_LIST_SMOKE=
OPENAI_MODEL_LIST_CONFIRM=
RUN_OPENAI_AI_SMOKE=
OPENAI_AI_SMOKE_CONFIRM=
RUN_OPENAI_WEB_FALLBACK_SMOKE=
OPENAI_WEB_FALLBACK_CONFIRM=
APP_ENV=
LIVE_TRADING_ENABLED=
AUTONOMOUS_EXECUTION_ENABLED=
AUTONOMY_LEVEL=
KILL_SWITCH_ENABLED=
ALERT_PROVIDER_PRIMARY=
ALERT_PROVIDER_SECONDARY=
ALERT_ENABLE_REAL_DELIVERY=
ALERT_DAILY_MESSAGE_LIMIT=
ALERT_CRITICAL_BYPASS_DAILY_LIMIT=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
RUN_TELEGRAM_ALERT_SMOKE=
TELEGRAM_ALERT_SMOKE_CONFIRM=
TELEGRAM_ALERT_SMOKE_MAX_MESSAGES=
TELEGRAM_ALERT_SMOKE_INCLUDE_REPORT_SAMPLE=
TELEGRAM_ALERT_SMOKE_INCLUDE_TRADE_SAMPLE=
TELEGRAM_ALERT_SMOKE_INCLUDE_CRITICAL_SAMPLE=
```

Security requirements:

- never commit `.env`,
- use separate paper/live credentials,
- never expose broker keys to frontend,
- store secrets in secret manager,
- rotate keys after suspicious behavior,
- keep production and paper environments separated,
- AI service must not receive broker credentials.

---

## 22. Validation Plan

### 22.1 Historical Period

Preferred:

```text
2012-01-01 to latest available
```

Include multiple regimes:

- long bull market,
- COVID crash,
- 2022 bear market,
- post-2022 high-rate environment.

### 22.2 Benchmarks

Primary:

```text
SPY total return
```

Secondary:

```text
exposure-adjusted SPY benchmark
equal-weight approved universe benchmark
```

### 22.3 Split Design

```text
Design / parameter selection:
    2012-2018

Rolling OOS development:
    2019-2023

Final untouched lockbox:
    2024-latest
```

### 22.4 Walk-Forward

```text
Anchored expanding window.
Yearly re-evaluation.
No daily/weekly retuning.
```

### 22.5 Fees and Slippage

```yaml
validation_costs:
  commission: 0
  fee_proxy_bps_per_side: 1
  baseline_entry_slippage_bps: 10
  baseline_routine_exit_slippage_bps: 10
  baseline_stop_exit_slippage_bps: 20
  stress_entry_slippage_bps: 25
  stress_stop_exit_slippage_bps: 40
```

### 22.6 Monte Carlo

```text
10,000 trade-sequence bootstraps
monthly block-bootstrap returns
random 5% missed fills
randomized slippage multiplier in [0.5x, 1.5x]
```

### 22.7 Required Ablations

- regime on/off,
- relative strength on/off,
- volume filter on/off,
- AI forced neutral vs AI enabled,
- fail-fast exit on/off,
- time stop on/off,
- 20D breakout vs 55D breakout,
- 2.0 ATR stop vs 2.5 ATR stop,
- 2.5 ATR trailing vs 3.0 ATR trailing.

### 22.8 Acceptance Before Level 4 Micro-Live

Required:

```text
At least 8 weeks frozen paper.
At least 30 closed paper trades or 2 quarters of forward paper, whichever comes later.
OOS Profit Factor >= 1.10.
OOS Sharpe >= 0.75 or OOS Sortino >= 1.00.
Max drawdown <= 10%.
100% protective stop placement success.
Broker/internal mismatch rate < 0.1%.
AI valid-schema rate >= 99%.
Zero Sev-1 control incidents in last 20 sessions.
Zero missing-stop incidents.
Zero duplicate-order incidents.
```

### 22.9 Acceptance Before Expanded Level 4

Required:

```text
At least 12 weeks micro-live.
No Sev-1 incidents.
No unexplained broker mismatches.
Median live slippage not worse than model by more than 10 bps.
Live max drawdown <= 6%.
All strategy/config changes versioned.
```

### 22.10 Acceptance Before Level 5

Required:

```text
At least 3 months stable expanded Level 4 operation.
No critical kill-switch event from execution ambiguity.
No unresolved reconciliation incidents.
No missing-stop incidents.
No duplicate-order incidents.
Live results inside predefined confidence envelope.
Formal operations runbook completed.
Temporal workflow replay and incident recovery tested.
```

---

## 23. ML Scope

### 23.1 v0.1 ML Policy

```text
No predictive ML in execution path.
No HMM live gating.
No gradient boosting live scoring.
No neural networks.
No reinforcement learning.
No LLM-only decision-making.
```

### 23.2 Allowed v0.1 AI

```text
Structured-output LLM for news/catalyst/risk extraction only.
```

### 23.3 Future ML

| Model                  | Stage                | Role                         |
| ---------------------- | -------------------- | ---------------------------- |
| HMM                    | v0.2 shadow          | Regime confirmation only     |
| Gradient boosting      | later                | Offline ranking overlay      |
| Neural networks        | later or never       | Research only                |
| Reinforcement learning | not recommended soon | Forbidden for execution path |
| LLM-only trading       | never in core path   | Forbidden                    |

---

## 24. Repository Structure

```text
autonomous-ai-trading-bot/
├── README.md
├── SPEC.md
├── .env.example
├── pyproject.toml
├── docker-compose.yml
├── config/
│   ├── system.yaml
│   ├── temporal.yaml
│   ├── execution.yaml
│   ├── universe.yaml
│   ├── strategy.yaml
│   ├── regime.yaml
│   ├── risk.yaml
│   └── ai.yaml
├── apps/
│   ├── api/
│   │   └── app/
│   │       ├── main.py
│   │       ├── routes/
│   │       └── dependencies.py
│   ├── workers/
│   │   └── app/
│   │       ├── temporal_client.py
│   │       ├── worker.py
│   │       ├── workflows/
│   │       └── activities/
│   └── dashboard/
│       └── nextjs_app/
├── packages/
│   ├── core/
│   ├── data/
│   ├── strategy/
│   ├── ai/
│   ├── risk/
│   ├── execution/
│   ├── reporting/
│   └── backtesting/
├── db/
│   ├── migrations/
│   └── seed/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── temporal/
│   └── paper/
├── scripts/
│   ├── run_backtest.py
│   ├── start_worker.py
│   ├── seed_temporal_schedules.py
│   ├── run_paper_cycle.py
│   ├── reconcile_broker.py
│   └── generate_report.py
└── docs/
    ├── architecture.md
    ├── temporal_workflows.md
    ├── risk_policy.md
    ├── execution_policy.md
    ├── validation_plan.md
    └── operations_runbook.md
```

---

## 25. Testing Requirements

### 25.1 Unit Tests

Required:

- regime classifier,
- signal engine,
- feature computation,
- position sizing,
- risk checks,
- AI output parser,
- execution intent builder,
- order request builder,
- kill switch logic,
- config loading.

### 25.2 Temporal Tests

Required:

- workflow replay determinism,
- activity retry behavior,
- order lifecycle happy path,
- partial-fill workflow,
- stop-placement failure workflow,
- reconciliation mismatch workflow,
- kill-switch signal workflow,
- manual resume signal workflow.

### 25.3 Integration Tests

Required:

- database write/read,
- Temporal worker startup,
- Temporal schedule creation,
- Alpaca paper account connection,
- order submit/cancel in paper mode,
- protective stop creation,
- position reconciliation,
- AI JSON parsing,
- scheduled job dry run,
- autonomous execution dry run.

### 25.4 Failure Tests

Simulate:

- stale market data,
- invalid AI JSON,
- AI outage,
- missing stop order,
- broker API timeout,
- duplicate order attempt,
- partial fill,
- unexpected broker position,
- database outage,
- Temporal worker crash,
- Temporal activity retry,
- kill switch activation,
- order submitted but not recorded,
- internal position without broker position,
- broker position without internal position.

---

## 26. Implementation Roadmap

### Phase A - Foundation

Deliverables:

- repo structure,
- config system,
- Postgres schema,
- Temporal connection,
- Temporal worker skeleton,
- basic schedules,
- logging,
- `.env.example`.

### Phase B - Data and Backtest Core

Deliverables:

- market data ingest,
- raw payload persistence,
- universe builder,
- feature engine,
- deterministic regime engine,
- deterministic strategy engine,
- backtester,
- metrics report.

### Phase C - Risk and Execution Core

Deliverables:

- risk checks,
- position sizing,
- execution intent builder,
- Alpaca adapter,
- broker idempotency,
- order manager,
- protective stop logic,
- reconciliation engine.

### Phase D - Temporal Execution Workflows

Deliverables:

- `OrderLifecycleWorkflow`,
- `PositionLifecycleWorkflow`,
- `ReconciliationWorkflow`,
- `KillSwitchWorkflow`,
- replay tests,
- failure tests.

### Phase E - Paper Trading Orchestration

Deliverables:

- autonomous paper workflows,
- alerts,
- daily report,
- weekly report,
- dashboard state,
- incident logging.

### Phase F - AI Intelligence Layer

Deliverables:

- news fetch,
- article dedupe,
- structured-output prompt,
- schema validation,
- fallback logic,
- raw/parsed output persistence,
- AI score integration.

### Phase G - Frozen Paper Validation

Deliverables:

- 8-12 weeks frozen paper run,
- paper reports,
- execution diagnostics,
- ablation results,
- validation summary.

Before Phase G starts, M43 scale-in policy may be frozen for paper validation only. Starting the
validation clock requires a separate M44 freeze/start decision; v0.4 itself does not activate
schedules or begin unattended operation.

### Phase H - Level 4 Micro-Live

Deliverables:

- live credentials separated,
- micro-live risk config,
- live kill-switch test,
- live daily reports,
- incident runbook,
- post-trade audit.

### Phase I - Expanded Level 4 / Level 5

Deliverables:

- expanded risk profile only after evidence,
- HMM shadow regime optional,
- strategy variant selection,
- formal operations runbook,
- stability review.

---

## 27. Final Recommendation

Build the system as:

```text
Temporal-orchestrated autonomous Level 4 trading bot.
Deterministic strategy/risk/execution core.
AI only as bounded news/catalyst/risk intelligence.
Paper-first.
Micro-live first.
Expanded autonomy only after evidence.
```

The best v0.1 build is:

```text
A Temporal-backed, broker-reconciled, long-only US equities/ETF swing bot
using rule-based regime gating,
20D/55D breakout research variants,
63D relative strength,
ATR-based exits,
AI adverse-news filtering,
strict risk limits,
protective stops,
idempotent order workflows,
and complete auditability.
```

The first live system should be autonomous, but deliberately conservative.

```text
Autonomy is allowed.
Unbounded discretion is not.
```
