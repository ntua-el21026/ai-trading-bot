# Autonomous AI Trading Bot - Execution-First Specification

**Document version:** v0.2  
**Date:** 2026-05-04  
**Target system:** Autonomous AI-assisted trading bot with broker-level autonomous trade execution  
**Primary objective:** Build a production-grade autonomous trading system that can independently generate, validate, execute, manage, and close trades using deterministic strategy logic, AI-assisted news/catalyst analysis, hard risk controls, broker reconciliation, and complete auditability.

---

## 1. Executive Summary

This specification defines a trading-bot MVP whose central capability is **autonomous trade execution**.

The system is designed to operate at **Autonomy Level 4 first** and later support **Autonomy Level 5** after validation. In both levels, the system can place and manage live broker orders automatically, but only inside deterministic constraints.

The system will autonomously:

- collect market data,
- detect market regime,
- generate trade candidates,
- fetch news and catalyst context,
- score candidates using deterministic and AI-assisted signals,
- validate every trade through hard risk gates,
- place live or paper broker orders,
- attach protective stops,
- monitor open orders and positions,
- modify or cancel orders when required,
- close positions based on deterministic exit rules,
- reconcile broker state against internal state,
- pause itself on abnormal conditions,
- log every input, decision, order, fill, exit, rejection, and error,
- generate daily and weekly reports.

The key principle is:

```text
The system may execute autonomously.
The AI model may not execute directly.
Execution authority belongs to the deterministic execution pipeline.
```

This means the AI layer can contribute to:

- catalyst scoring,
- risk flagging,
- ranking,
- trade explanations,
- blocking trades,
- reducing confidence,
- producing reports.

But the AI layer cannot:

- directly submit orders,
- override risk limits,
- change position sizing caps,
- disable kill switches,
- trade unapproved symbols,
- modify live strategy rules automatically,
- bypass broker reconciliation.

The first production target is:

```text
US equities and ETFs
Daily/swing timeframe
Alpaca paper first
Alpaca live after validation
Long-only
No leverage
No options
No shorting
No low-latency scalping
```

---

## 2. Core Philosophy

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
5. AI-assisted news and catalyst filtering,
6. systematic logging and review,
7. disciplined validation.

The AI layer is a research and decision-support component. The final execution path is deterministic and auditable.

---

## 3. Goals and Non-Goals

### 3.1 Goals

The MVP must:

1. Run autonomously on a schedule.
2. Support paper trading and live trading.
3. Support **autonomous live order submission** after explicit configuration.
4. Support **autonomous position management** after order fill.
5. Support **autonomous exits** using deterministic exit logic.
6. Trade a limited approved universe of liquid equities/ETFs.
7. Use a deterministic strategy engine as the primary signal source.
8. Use AI for news/catalyst analysis, risk flagging, ranking, journaling, and reports.
9. Enforce hard risk constraints before every order.
10. Attach protective stops to every live position.
11. Reconcile broker state before and after execution.
12. Maintain a full audit trail of all inputs, decisions, scores, risk checks, orders, fills, stops, exits, rejections, and AI outputs.
13. Provide a dashboard for monitoring system state, trades, risk, and performance.
14. Provide emergency shutdown through a kill switch.
15. Support autonomous safety-pausing when abnormal conditions occur.
16. Support staged validation:
    - backtest,
    - simulated dry run,
    - paper autonomous trading,
    - Level 4 capped live autonomous trading,
    - Level 5 expanded autonomous trading.

### 3.2 Non-Goals

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
14. Selling signals to third parties.
15. Guaranteeing profitability.

---

## 4. Autonomy Model

The system supports explicit autonomy levels.

| Level | Name | Execution Behavior |
|---:|---|---|
| 0 | Research Only | AI summarizes markets. No signals. No orders. |
| 1 | Signal Only | Strategy generates signals. No broker orders. |
| 2 | Paper Autonomous | Bot executes automatically in paper account. |
| 3 | Live Approval | Bot proposes live orders, user approves manually. |
| 4 | Live Autonomous Capped | Bot executes live orders automatically under strict caps. |
| 5 | Live Autonomous Expanded | Bot executes live orders automatically with larger but still constrained capital. |

### 4.1 Target Level

The desired target is:

```text
Build toward Level 4 as the first real live version.
Design the architecture so Level 5 can be enabled later.
```

### 4.2 Level 4 Definition

Level 4 means:

- live trades can be placed automatically,
- manual approval is not required per trade,
- capital is small and capped,
- open positions are capped,
- risk per trade is capped,
- daily/weekly/monthly loss limits are enforced,
- every trade must pass deterministic risk checks,
- every position must have an exit plan,
- every position must have a protective stop,
- all execution actions are logged,
- every order/fill/exit triggers an alert,
- kill switch is active,
- system self-pauses on critical failures.

### 4.3 Level 5 Definition

Level 5 means:

- the system can run end-to-end without manual intervention during normal conditions,
- live capital may be increased,
- the universe may be expanded,
- position count may be increased,
- multiple strategies may be enabled,
- automated rebalancing/exit management may be active,
- automated reporting and review are mandatory.

Level 5 still requires:

- hard risk gates,
- deterministic execution rules,
- broker reconciliation,
- kill switches,
- complete logging,
- no direct AI order submission.

Level 5 does not mean:

```text
The AI can trade anything it wants.
```

Level 5 means:

```text
The autonomous execution pipeline can operate continuously within pre-approved deterministic boundaries.
```

---

## 5. Autonomous Execution Authority

### 5.1 Execution Authority Hierarchy

The system has strict authority boundaries.

| Component | May propose trades | May score trades | May block trades | May submit orders |
|---|---:|---:|---:|---:|
| AI research layer | Yes | Yes | Yes | No |
| Strategy engine | Yes | Yes | No | No |
| Decision arbiter | Yes | Yes | Yes | No |
| Risk engine | No | No | Yes | No |
| Execution engine | No | No | No | Yes |
| Broker adapter | No | No | No | Yes, only when called by execution engine |

Only the **execution engine** may submit broker orders, and only after receiving:

```text
approved_trade_decision
AND passed_risk_check
AND valid_broker_reconciliation
AND active_autonomy_permission
AND kill_switch_off
```

### 5.2 Autonomous Execution Permission

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

The system must reject live autonomous orders if any flag is missing or false.

### 5.3 Explicit Execution Contract

A trade can be executed only when the system produces an `ExecutionIntent`.

Required `ExecutionIntent` fields:

```json
{
  "decision_id": "uuid",
  "symbol": "AAPL",
  "side": "buy",
  "asset_class": "equity",
  "quantity": 10,
  "entry_order_type": "limit",
  "limit_price": 180.50,
  "stop_loss_price": 174.20,
  "time_in_force": "day",
  "strategy_version": "regime_filtered_breakout_v0_1",
  "risk_config_version": "risk_v0_1",
  "autonomy_level": 4,
  "requires_protective_stop": true,
  "max_acceptable_slippage_pct": 0.0025,
  "expires_at": "2026-05-04T15:30:00Z"
}
```

No broker order may be submitted without a valid `ExecutionIntent`.

---

## 6. Trading Scope

### 6.1 Asset Class

Initial target:

```text
US equities and ETFs
```

### 6.2 Broker

Initial broker:

```text
Alpaca
```

Required environments:

- paper trading,
- live trading.

### 6.3 Timeframe

Initial timeframe:

```text
Daily / swing trading
```

The bot evaluates:

- pre-market,
- after market open,
- midday,
- pre-close,
- after close.

No high-frequency operation is required.

### 6.4 Initial Trading Universe

Recommended v0.1 universe:

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

### 6.5 Excluded Instruments

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

## 7. High-Level Architecture

```text
Market Data Provider
        |
        v
Data Ingestion Layer
        |
        v
Feature Engineering Layer
        |
        v
Regime Classifier
        |
        v
Deterministic Strategy Engine
        |
        v
Trade Candidate Generator
        |
        +----------------------+
        |                      |
        v                      v
News/Catalyst Fetcher     AI Research Layer
        |                      |
        +----------+-----------+
                   |
                   v
Decision Arbiter
                   |
                   v
Risk Engine
                   |
                   v
Execution Intent Builder
                   |
                   v
Autonomous Execution Engine
                   |
                   v
Broker Adapter
                   |
                   v
Broker Orders / Fills / Positions
                   |
                   v
Reconciliation Engine
                   |
                   v
Database + Audit Log + Dashboard + Reports
```

Final execution condition:

```text
deterministic_setup_valid = true
AND decision = approved
AND risk_gate = pass
AND execution_intent_valid = true
AND broker_reconciliation_status = clean
AND kill_switch = off
AND autonomous_execution_enabled = true
```

---

## 8. Trade Lifecycle

The autonomous trade lifecycle is:

```text
1. Ingest market data.
2. Compute features.
3. Detect regime.
4. Generate deterministic candidates.
5. Fetch news/catalysts for candidates.
6. Generate AI research JSON.
7. Score candidate in decision arbiter.
8. Run risk checks.
9. Build ExecutionIntent.
10. Reconcile broker state.
11. Submit entry order.
12. Confirm order accepted.
13. Track order until filled/canceled/expired.
14. Attach or verify protective stop.
15. Monitor position.
16. Apply exit rules.
17. Submit exit order when required.
18. Reconcile closed position.
19. Generate trade journal entry.
20. Include trade in daily/weekly reports.
```

Every step must be logged.

---

## 9. Module Specification

### 9.1 Data Ingestion Module

Responsibilities:

- Fetch OHLCV data.
- Fetch latest prices.
- Fetch account data.
- Fetch open orders.
- Fetch broker positions.
- Store normalized raw data.
- Detect missing/corrupt data.
- Maintain data freshness metadata.

Required checks:

- missing candles,
- duplicate candles,
- stale data,
- split/dividend adjustment consistency,
- timezone consistency,
- symbol validity.

### 9.2 Feature Engineering Module

Initial features:

- daily return,
- rolling volatility,
- ATR,
- 10-day moving average,
- 20-day moving average,
- 50-day moving average,
- 200-day moving average,
- 20-day high,
- 20-day low,
- relative strength vs SPY,
- volume ratio vs 20-day average,
- gap percentage,
- distance from 50-day moving average,
- distance from 200-day moving average.

### 9.3 Regime Classifier

Initial deterministic model:

```text
Bullish regime:
    SPY close > SPY 50DMA
    AND SPY close > SPY 200DMA
    AND QQQ close > QQQ 50DMA

Defensive regime:
    SPY close < SPY 200DMA
    OR realized volatility percentile > threshold

Choppy regime:
    SPY between 50DMA and 200DMA
    OR trend strength below threshold

Risk-off regime:
    SPY below 200DMA
    AND volatility elevated
```

Output schema:

```json
{
  "date": "2026-05-04",
  "regime": "bullish|neutral|choppy|defensive|risk_off",
  "risk_multiplier": 0.5,
  "long_trading_allowed": true,
  "new_entries_allowed": true,
  "max_position_count": 5,
  "max_gross_exposure_pct": 0.20,
  "reason_codes": [
    "SPY_ABOVE_50DMA",
    "SPY_ABOVE_200DMA",
    "VOL_NORMAL"
  ]
}
```

Later upgrade:

- Hidden Markov Model regime classification.
- Regime transition probabilities.
- Hysteresis.
- Cooldowns after regime changes.

### 9.4 Deterministic Strategy Engine

Initial strategy:

```text
Regime-filtered long-only breakout/momentum swing strategy
```

Entry conditions:

```text
New long candidate is valid if:

1. Market regime allows new long entries.
2. Symbol is in approved universe.
3. Symbol close > 50DMA.
4. Symbol close > 200DMA.
5. Symbol breaks above 20-day high.
6. Volume > 20-day average * volume_threshold.
7. Relative strength vs SPY over 20 days is positive.
8. ATR is within allowed range.
9. Symbol is not already held.
10. No earnings/event blackout if configured.
```

Exit conditions:

```text
Exit position if any condition is true:

1. Hard stop hit.
2. Trailing stop hit.
3. Close below 10DMA.
4. Regime flips to risk_off.
5. Time stop reached.
6. AI risk flag escalates to block.
7. Max portfolio loss threshold reached.
8. Broker/state reconciliation detects unsafe mismatch.
```

Initial parameters:

```yaml
strategy:
  breakout_lookback_days: 20
  volume_average_days: 20
  volume_threshold: 1.1
  relative_strength_lookback_days: 20
  atr_period_days: 14
  initial_stop_atr_multiplier: 2.0
  trailing_stop_atr_multiplier: 2.5
  time_stop_days: 15
  min_price: 20
  min_average_dollar_volume: 50000000
```

### 9.5 AI News / Catalyst Layer

Responsibilities:

- Fetch news for candidate symbols.
- Summarize catalysts.
- Identify material risks.
- Score catalyst strength.
- Detect negative news that should block a trade.
- Produce strict JSON.
- Generate human-readable explanations.
- Store all prompts, raw outputs, parsed outputs, and citations.

AI outputs are advisory.

AI can:

- support a trade,
- remain neutral,
- reduce size,
- block a trade,
- flag risk,
- generate reports.

AI cannot:

- submit orders,
- increase size above risk limits,
- bypass stop requirements,
- modify live strategy rules,
- disable kill switches.

### 9.6 AI Decision Schema

All AI outputs must be strict JSON.

```json
{
  "symbol": "NVDA",
  "as_of": "2026-05-04T13:00:00Z",
  "news_window_hours": 48,
  "summary": "Recent news is broadly positive, led by analyst upgrades and strong AI demand commentary.",
  "catalyst_type": "analyst_upgrade|earnings|guidance|macro|sector_momentum|product|legal|none|unknown",
  "sentiment": "positive|neutral|negative|mixed|unknown",
  "catalyst_strength": 0.72,
  "risk_level": "low|medium|high|critical",
  "risk_flags": [
    "high_valuation",
    "sector_concentration"
  ],
  "trade_bias": "support_long|neutral|block_long|reduce_size",
  "confidence": 0.68,
  "blocking_reason": null,
  "evidence_quality": "strong|medium|weak|insufficient",
  "citations": [
    {
      "title": "Source title",
      "url": "https://example.com",
      "published_at": "2026-05-04T08:00:00Z"
    }
  ]
}
```

### 9.7 Decision Arbiter

The arbiter combines deterministic and AI scores.

Initial scoring model:

```text
final_score =
    0.40 * technical_score
  + 0.25 * regime_score
  + 0.20 * ai_catalyst_score
  + 0.10 * relative_strength_score
  + 0.05 * portfolio_fit_score
```

Candidate can proceed to risk engine if:

```text
deterministic_setup_valid = true
AND final_score >= min_final_score
AND ai_trade_bias != "block_long"
AND ai_risk_level != "critical"
```

Initial config:

```yaml
decision:
  min_final_score: 0.70
  block_on_ai_critical_risk: true
  reduce_size_on_ai_high_risk: true
  require_recent_news_check: true
```

### 9.8 Risk Engine

The risk engine is deterministic and non-bypassable.

Initial Level 4 limits:

```yaml
risk:
  max_account_allocation_pct: 0.20
  max_position_size_pct: 0.04
  max_risk_per_trade_pct: 0.005
  max_open_positions: 5
  max_daily_loss_pct: 0.01
  max_weekly_loss_pct: 0.03
  max_monthly_loss_pct: 0.06
  max_sector_exposure_pct: 0.12
  max_single_symbol_exposure_pct: 0.04
  allow_margin: false
  allow_shorting: false
  allow_options: false
  allow_leveraged_etfs: false
  min_cash_buffer_pct: 0.50
  require_stop_order: true
  cancel_on_missing_stop: true
  pause_on_stop_failure: true
  kill_switch_enabled: true
```

Pre-order risk checks:

```text
1. Is live trading enabled?
2. Is autonomous execution enabled?
3. Is symbol approved?
4. Is asset class approved?
5. Is market open?
6. Is data fresh?
7. Is account synced?
8. Is max daily loss breached?
9. Is max weekly loss breached?
10. Is max monthly loss breached?
11. Would position exceed max size?
12. Would sector exposure exceed cap?
13. Would open position count exceed cap?
14. Is stop loss defined?
15. Is estimated risk within max risk per trade?
16. Is cash buffer preserved?
17. Is order duplicate?
18. Is broker account in expected mode?
19. Has system health check passed?
20. Is kill switch off?
```

If any critical check fails:

```text
Reject order.
Log rejection.
Notify user.
```

### 9.9 Position Sizing

Initial sizing:

```text
risk_amount = account_equity * max_risk_per_trade_pct
stop_distance = entry_price - stop_price
raw_shares = floor(risk_amount / stop_distance)
max_value_shares = floor((account_equity * max_position_size_pct) / entry_price)
shares = min(raw_shares, max_value_shares)
```

Adjustments:

```text
If AI risk level is high:
    shares = shares * 0.5

If regime is neutral/choppy:
    shares = shares * regime_risk_multiplier

If shares < 1:
    skip trade
```

### 9.10 Execution Intent Builder

The execution intent builder converts an approved decision into a broker-ready intent.

It must verify:

- decision approved,
- risk check passed,
- symbol approved,
- quantity > 0,
- stop price exists,
- order type allowed,
- time-in-force allowed,
- intent expiration set,
- autonomy level allowed,
- strategy/risk config versions attached.

Example intent:

```json
{
  "decision_id": "uuid",
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 10,
  "entry_order_type": "limit",
  "limit_price": 180.50,
  "stop_loss_price": 174.20,
  "time_in_force": "day",
  "strategy_version": "regime_filtered_breakout_v0_1",
  "risk_config_version": "risk_v0_1",
  "autonomy_level": 4,
  "requires_protective_stop": true,
  "max_acceptable_slippage_pct": 0.0025,
  "expires_at": "2026-05-04T15:30:00Z"
}
```

### 9.11 Autonomous Execution Engine

The autonomous execution engine is the only component that may submit broker orders.

Responsibilities:

- validate execution intent,
- verify environment and autonomy flags,
- reconcile broker state before execution,
- submit entry order,
- track order status,
- handle partial fills,
- attach/verify protective stop,
- update internal order state,
- emit alerts,
- pause system on critical execution failure.

Allowed actions:

- submit entry order,
- cancel stale entry order,
- submit protective stop,
- replace protective stop when allowed,
- submit exit order,
- close position on deterministic exit,
- pause new entries.

Disallowed actions:

- trade unapproved symbols,
- trade disallowed asset classes,
- increase size beyond risk engine output,
- ignore missing stop,
- submit order without risk check,
- submit order without execution intent,
- trade while kill switch is active.

### 9.12 Order Manager

Responsibilities:

- Convert valid execution intents into broker orders.
- Prevent duplicate orders.
- Enforce idempotency keys.
- Attach stop-loss or bracket order.
- Track order status.
- Handle partial fills.
- Reconcile orders with broker state.
- Retry safe failures.
- Cancel stale orders.
- Notify on every execution event.

Supported order types v0.1:

- limit buy order,
- market sell order for exits,
- stop-loss order,
- trailing stop order if broker behavior is verified.

Recommended entry behavior:

```text
Use limit orders for entries.
Expire unfilled entry orders by configured time.
Require protective stop after fill.
If stop placement fails, pause new entries and notify immediately.
```

### 9.13 Broker Adapter

Initial broker:

```text
Alpaca
```

Broker adapter interface:

```python
get_account()
get_clock()
get_positions()
get_open_orders()
submit_order()
cancel_order()
replace_order()
close_position()
get_order()
get_latest_trade()
```

The rest of the application must not call Alpaca directly.

### 9.14 Reconciliation Engine

Every scheduled run must reconcile:

- internal positions,
- broker positions,
- open broker orders,
- recent fills,
- cash/equity,
- stop orders,
- expected vs actual quantities,
- expected vs actual average entry prices.

If mismatch is detected:

```text
1. Pause new entries.
2. Notify user.
3. Attempt safe reconciliation.
4. Require manual review if unresolved.
```

Critical mismatches:

- broker position exists but internal position does not,
- internal position exists but broker position does not,
- position exists without protective stop,
- duplicate open entry orders,
- unexpected short position,
- account equity mismatch above threshold,
- order fill not recorded internally.

---

## 10. Autonomous Exit Management

The system must autonomously manage exits.

### 10.1 Exit Triggers

Exit triggers:

```text
1. Stop-loss hit.
2. Trailing stop hit.
3. Close below 10DMA.
4. Regime flips to risk_off.
5. Time stop reached.
6. AI risk flag changes to critical.
7. Max daily/weekly/monthly loss breached.
8. Missing stop cannot be repaired.
9. Broker reconciliation mismatch requires de-risking.
```

### 10.2 Exit Authority

The system may autonomously exit a position if:

```text
position_is_known = true
AND exit_trigger_valid = true
AND broker_reconciliation_status != critical_unresolved
AND kill_switch_allows_exits = true
```

Important:

```text
Kill switch disables new entries.
Kill switch should not necessarily disable protective exits.
```

The system must distinguish between:

- blocking new risk,
- reducing existing risk.

### 10.3 Protective Stop Policy

Every live position must have:

- initial stop,
- stop order submitted or broker-native bracket,
- stop status verified,
- internal stop price recorded,
- alert sent if missing.

If stop placement fails:

```text
1. Retry once if safe.
2. If still failed, pause new entries.
3. Notify user.
4. Depending on config, close position or require manual intervention.
```

---

## 11. Scheduler

Initial scheduled jobs:

| Job | Market Time | Purpose |
|---|---:|---|
| Pre-market scan | before open | Fetch data/news, generate candidates |
| Market-open execution | after open | Validate and place entries |
| Midday risk check | midday | Reconcile, manage stops, detect risk |
| Pre-close execution/risk check | before close | Exit/time stop/risk review |
| End-of-day report | after close | Summarize activity |
| Weekly review | Friday after close | Performance and rule review |

Time zone rules:

```text
America/New_York for market schedule.
Europe/Athens only for user-facing display.
```

The scheduler must avoid:

- running entry jobs outside market hours,
- submitting duplicate orders on retry,
- submitting orders if previous reconciliation failed.

---

## 12. Reporting Module

Daily report must include:

- account equity,
- daily PnL,
- open positions,
- new trades,
- closed trades,
- rejected trades,
- submitted orders,
- canceled orders,
- failed orders,
- stop status,
- risk status,
- AI summaries,
- errors/anomalies,
- next-day watchlist.

Weekly report must include:

- weekly return,
- benchmark comparison,
- max drawdown,
- win rate,
- average win/loss,
- profit factor,
- rule violations,
- AI usefulness review,
- execution quality review,
- slippage review,
- strategy drift warnings,
- recommended hypotheses for manual review.

---

## 13. Dashboard

Initial pages:

1. Overview
2. Portfolio
3. Signals
4. Decisions
5. Execution Intents
6. Orders
7. Trades
8. Stops
9. Risk
10. AI Research
11. Backtests
12. Reports
13. Settings
14. Kill Switch

Dashboard actions:

- enable/disable paper trading,
- enable/disable live trading,
- enable/disable autonomous execution,
- trigger kill switch,
- reset kill switch after review,
- view execution logs,
- view rejected trades,
- view broker reconciliation state.

Dashboard must not expose broker secrets.

---

## 14. Database Specification

Recommended database:

```text
Postgres / Supabase
```

### 14.1 Core Tables

#### symbols

```sql
CREATE TABLE symbols (
    id UUID PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT,
    asset_class TEXT NOT NULL,
    sector TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### ohlcv_daily

```sql
CREATE TABLE ohlcv_daily (
    id UUID PRIMARY KEY,
    symbol_id UUID NOT NULL REFERENCES symbols(id),
    date DATE NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    adjusted_close NUMERIC,
    volume BIGINT NOT NULL,
    provider TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(symbol_id, date, provider)
);
```

#### features_daily

```sql
CREATE TABLE features_daily (
    id UUID PRIMARY KEY,
    symbol_id UUID NOT NULL REFERENCES symbols(id),
    date DATE NOT NULL,
    sma_10 NUMERIC,
    sma_20 NUMERIC,
    sma_50 NUMERIC,
    sma_200 NUMERIC,
    atr_14 NUMERIC,
    rolling_vol_20 NUMERIC,
    high_20 NUMERIC,
    low_20 NUMERIC,
    volume_avg_20 NUMERIC,
    volume_ratio_20 NUMERIC,
    relative_strength_20 NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(symbol_id, date)
);
```

#### regimes

```sql
CREATE TABLE regimes (
    id UUID PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    regime TEXT NOT NULL,
    risk_multiplier NUMERIC NOT NULL,
    long_trading_allowed BOOLEAN NOT NULL,
    new_entries_allowed BOOLEAN NOT NULL,
    reason_codes JSONB NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### trade_candidates

```sql
CREATE TABLE trade_candidates (
    id UUID PRIMARY KEY,
    symbol_id UUID NOT NULL REFERENCES symbols(id),
    date DATE NOT NULL,
    direction TEXT NOT NULL,
    deterministic_setup_valid BOOLEAN NOT NULL,
    technical_score NUMERIC NOT NULL,
    regime_score NUMERIC NOT NULL,
    relative_strength_score NUMERIC NOT NULL,
    reason_codes JSONB NOT NULL,
    strategy_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### ai_research_outputs

```sql
CREATE TABLE ai_research_outputs (
    id UUID PRIMARY KEY,
    candidate_id UUID REFERENCES trade_candidates(id),
    symbol_id UUID REFERENCES symbols(id),
    as_of TIMESTAMPTZ NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    news_window_hours INTEGER NOT NULL,
    raw_output JSONB NOT NULL,
    parsed_output JSONB NOT NULL,
    sentiment TEXT,
    catalyst_type TEXT,
    catalyst_strength NUMERIC,
    risk_level TEXT,
    trade_bias TEXT,
    confidence NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### trade_decisions

```sql
CREATE TABLE trade_decisions (
    id UUID PRIMARY KEY,
    candidate_id UUID NOT NULL REFERENCES trade_candidates(id),
    ai_research_id UUID REFERENCES ai_research_outputs(id),
    date DATE NOT NULL,
    final_score NUMERIC NOT NULL,
    decision TEXT NOT NULL,
    decision_reason_codes JSONB NOT NULL,
    blocked_reason TEXT,
    strategy_version TEXT NOT NULL,
    arbiter_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### risk_checks

```sql
CREATE TABLE risk_checks (
    id UUID PRIMARY KEY,
    decision_id UUID REFERENCES trade_decisions(id),
    checked_at TIMESTAMPTZ NOT NULL,
    passed BOOLEAN NOT NULL,
    checks JSONB NOT NULL,
    rejection_reason TEXT,
    risk_config_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### execution_intents

```sql
CREATE TABLE execution_intents (
    id UUID PRIMARY KEY,
    decision_id UUID NOT NULL REFERENCES trade_decisions(id),
    risk_check_id UUID NOT NULL REFERENCES risk_checks(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    entry_order_type TEXT NOT NULL,
    limit_price NUMERIC,
    stop_loss_price NUMERIC NOT NULL,
    time_in_force TEXT NOT NULL,
    autonomy_level INTEGER NOT NULL,
    status TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### orders

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    execution_intent_id UUID REFERENCES execution_intents(id),
    broker TEXT NOT NULL,
    broker_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    limit_price NUMERIC,
    stop_price NUMERIC,
    status TEXT NOT NULL,
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    filled_avg_price NUMERIC,
    raw_broker_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### fills

```sql
CREATE TABLE fills (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    broker_fill_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    filled_at TIMESTAMPTZ NOT NULL,
    raw_broker_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### positions

```sql
CREATE TABLE positions (
    id UUID PRIMARY KEY,
    broker TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    avg_entry_price NUMERIC NOT NULL,
    current_price NUMERIC,
    market_value NUMERIC,
    unrealized_pnl NUMERIC,
    unrealized_pnl_pct NUMERIC,
    stop_price NUMERIC,
    trailing_stop_price NUMERIC,
    status TEXT NOT NULL,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### broker_reconciliations

```sql
CREATE TABLE broker_reconciliations (
    id UUID PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    account_snapshot JSONB NOT NULL,
    broker_positions JSONB NOT NULL,
    internal_positions JSONB NOT NULL,
    broker_orders JSONB NOT NULL,
    internal_orders JSONB NOT NULL,
    mismatches JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### system_events

```sql
CREATE TABLE system_events (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### reports

```sql
CREATE TABLE reports (
    id UUID PRIMARY KEY,
    report_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    content_markdown TEXT NOT NULL,
    metrics JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 15. Configuration Files

### 15.1 config/system.yaml

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

### 15.2 config/execution.yaml

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
  max_acceptable_slippage_pct: 0.0025
  cancel_unfilled_entries_after_minutes: 60
  pause_on_order_submit_failure: true
  pause_on_stop_failure: true
  notify_on_every_order: true
```

### 15.3 config/universe.yaml

```yaml
universe:
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
  excluded:
    allow_options: false
    allow_shorting: false
    allow_leveraged_etfs: false
```

### 15.4 config/strategy.yaml

```yaml
strategy:
  name: "regime_filtered_breakout_v0_1"
  breakout_lookback_days: 20
  volume_average_days: 20
  volume_threshold: 1.1
  relative_strength_lookback_days: 20
  atr_period_days: 14
  initial_stop_atr_multiplier: 2.0
  trailing_stop_atr_multiplier: 2.5
  time_stop_days: 15
  min_price: 20
  min_average_dollar_volume: 50000000
  require_close_above_sma_50: true
  require_close_above_sma_200: true
```

### 15.5 config/risk.yaml

```yaml
risk:
  max_account_allocation_pct: 0.20
  max_position_size_pct: 0.04
  max_risk_per_trade_pct: 0.005
  max_open_positions: 5
  max_daily_loss_pct: 0.01
  max_weekly_loss_pct: 0.03
  max_monthly_loss_pct: 0.06
  max_sector_exposure_pct: 0.12
  max_single_symbol_exposure_pct: 0.04
  allow_margin: false
  allow_shorting: false
  allow_options: false
  allow_leveraged_etfs: false
  min_cash_buffer_pct: 0.50
  require_stop_order: true
  cancel_on_missing_stop: true
  pause_on_stop_failure: true
```

### 15.6 config/ai.yaml

```yaml
ai:
  enabled: true
  provider: "openai_or_anthropic"
  model: "configured_in_env"
  require_json_schema: true
  max_news_window_hours: 72
  block_on_critical_risk: true
  reduce_size_on_high_risk: true
  allow_ai_to_create_orders: false
  allow_ai_to_modify_strategy: false
  allow_ai_to_modify_risk_limits: false
  prompt_version: "ai_trade_research_v0_1"
```

---

## 16. Environment Variables

```bash
DATABASE_URL=
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=
AI_PROVIDER=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
NEWS_API_KEY=
APP_ENV=
LIVE_TRADING_ENABLED=
AUTONOMOUS_EXECUTION_ENABLED=
AUTONOMY_LEVEL=
KILL_SWITCH_ENABLED=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Security requirements:

- never commit `.env`,
- use separate paper/live credentials,
- never expose broker keys to frontend,
- store secrets in deployment secret manager,
- rotate keys after suspicious behavior,
- keep production and paper environments physically separated where practical.

---

## 17. AI Prompting Requirements

All prompts must:

1. Request strict JSON.
2. Include schema.
3. Include candidate facts.
4. Include source snippets or citations.
5. Forbid invented news.
6. Require `unknown` when evidence is insufficient.
7. Include blocking risk detection.
8. Include confidence.
9. Store prompt version.
10. Store raw and parsed outputs.

### 17.1 AI Trade Research Prompt Template

```text
You are an AI trading research assistant.

Your role is to analyze recent news and risk context for a proposed trade candidate.
You do not place trades.
You do not override risk rules.
You must return strict JSON only.

Candidate:
- Symbol: {{symbol}}
- Direction: {{direction}}
- Date: {{date}}
- Deterministic setup reason codes: {{reason_codes}}
- Technical score: {{technical_score}}
- Regime: {{regime}}
- Current portfolio exposure: {{portfolio_context}}

News/context snippets:
{{news_snippets}}

Return this JSON schema exactly:
{
  "symbol": string,
  "as_of": string,
  "news_window_hours": number,
  "summary": string,
  "catalyst_type": "analyst_upgrade|earnings|guidance|macro|sector_momentum|product|legal|none|unknown",
  "sentiment": "positive|neutral|negative|mixed|unknown",
  "catalyst_strength": number,
  "risk_level": "low|medium|high|critical",
  "risk_flags": string[],
  "trade_bias": "support_long|neutral|block_long|reduce_size",
  "confidence": number,
  "blocking_reason": string|null,
  "evidence_quality": "strong|medium|weak|insufficient",
  "citations": [
    {
      "title": string,
      "url": string,
      "published_at": string
    }
  ]
}

Rules:
- Do not invent facts.
- If news is insufficient, set evidence_quality to "insufficient".
- If there is a severe unresolved risk, set trade_bias to "block_long".
- If risk is material but not fatal, set trade_bias to "reduce_size".
- catalyst_strength must be between 0 and 1.
- confidence must be between 0 and 1.
- Return JSON only.
```

---

## 18. Backtesting Requirements

Backtesting validates the deterministic core before live autonomy.

Required metrics:

- CAGR,
- total return,
- benchmark return,
- max drawdown,
- Sharpe ratio,
- Sortino ratio,
- win rate,
- average win,
- average loss,
- profit factor,
- number of trades,
- exposure percentage,
- turnover,
- average holding period,
- monthly returns,
- best trade,
- worst trade,
- fees/slippage assumptions.

Required validation:

1. In-sample backtest.
2. Out-of-sample backtest.
3. Walk-forward validation.
4. Parameter sensitivity.
5. Slippage sensitivity.
6. Fees sensitivity.
7. Trade-sequence Monte Carlo.
8. Benchmark comparison vs SPY and QQQ.
9. Ablation tests:
    - without AI filter,
    - with AI filter,
    - without regime filter,
    - with regime filter.

Do not proceed to autonomous paper trading unless:

```text
1. Strategy behavior is logical.
2. Drawdown is acceptable.
3. Fees/slippage do not destroy results.
4. Trade count is sufficient.
5. Performance is not dependent on one or two trades.
6. Parameter changes do not completely break performance.
7. Crash/risk-off behavior is safe.
```

---

## 19. Paper Trading Requirements

Paper trading must run before live autonomy.

Minimum duration:

```text
4-6 weeks
```

Recommended duration:

```text
8-12 weeks
```

Autonomous paper mode must validate:

- scheduling,
- broker integration,
- autonomous order submission,
- order lifecycle,
- stop placement,
- exit management,
- reconciliation,
- risk gates,
- duplicate prevention,
- dashboard,
- reports,
- AI JSON parsing,
- kill switch behavior,
- failure handling.

Paper trading does not fully validate live fill quality, real liquidity, market impact, slippage, or live profitability.

---

## 20. Live Trading Requirements

### 20.1 Level 4 Live Autonomous Mode

Initial constraints:

```yaml
live_mode_level_4:
  autonomous_execution_enabled: true
  manual_approval_required: false
  max_account_allocation_pct: 0.20
  max_position_size_pct: 0.04
  max_risk_per_trade_pct: 0.005
  max_open_positions: 5
  max_daily_loss_pct: 0.01
  max_weekly_loss_pct: 0.03
  allow_margin: false
  allow_shorting: false
  allow_options: false
  allow_leveraged_etfs: false
  require_stop_order: true
  notify_on_every_order: true
```

Level 4 may autonomously:

- open positions,
- attach stops,
- cancel stale orders,
- close positions,
- pause new entries,
- generate reports.

Level 4 may not:

- change strategy rules,
- increase risk limits,
- trade unapproved assets,
- trade outside configured hours,
- continue after critical mismatch.

### 20.2 Level 5 Live Autonomous Mode

Level 5 can only be enabled after:

- at least 3 months stable Level 4 operation,
- no critical unresolved reconciliation errors,
- no unresolved stop failures,
- no major AI hallucination incidents affecting decisions,
- live drawdown within acceptable bounds,
- strategy reviewed against benchmark,
- logs complete,
- kill switch tested,
- live performance and execution reviewed.

Level 5 may increase:

- capital allocation,
- max open positions,
- approved universe,
- number of enabled strategies.

Level 5 must not enable:

- unrestricted AI trading,
- leverage,
- options,
- shorts,
- unknown symbols,
- automatic strategy mutation.

---

## 21. Safety and Kill Switches

Kill switches:

1. Manual kill switch.
2. Daily loss kill switch.
3. Weekly loss kill switch.
4. Monthly loss kill switch.
5. Broker reconciliation kill switch.
6. Missing stop kill switch.
7. Data stale kill switch.
8. AI output invalid kill switch.
9. Duplicate order kill switch.
10. Deployment health kill switch.
11. Excessive slippage kill switch.
12. Unexpected live order kill switch.

When triggered:

```text
1. Disable new entries.
2. Cancel pending entry orders if safe.
3. Preserve or validate protective exits.
4. Notify user immediately.
5. Write critical system event.
6. Require explicit reset.
```

Important distinction:

```text
Kill switch blocks new risk.
Protective exits may remain allowed to reduce risk.
```

---

## 22. Monitoring and Alerts

Critical alerts:

- live order submitted,
- order filled,
- stop placement failed,
- stop missing,
- broker mismatch,
- risk limit breached,
- kill switch triggered,
- API error,
- AI output parse failure,
- stale market data,
- unexpected position,
- daily loss limit reached,
- duplicate order attempt,
- autonomous execution disabled/enabled.

Non-critical alerts:

- daily report,
- weekly report,
- candidate generated,
- candidate rejected,
- AI news summary generated.

---

## 23. Deployment Architecture

Recommended:

```text
Frontend:
    Next.js on Vercel

Backend API:
    FastAPI on Cloud Run / Railway / Render / VPS

Workers:
    Cloud Run Jobs / Celery workers / APScheduler on VPS

Database:
    Supabase Postgres

Secrets:
    Deployment provider secret manager

Broker:
    Alpaca paper/live

AI:
    OpenAI/Anthropic API

Notifications:
    Telegram/email
```

Critical rule:

```text
Do not run autonomous live order execution as a Vercel serverless function.
```

Use Vercel for dashboard only.

Autonomous execution should run in:

- Cloud Run jobs,
- long-running worker,
- VPS service,
- or another controlled backend worker environment.

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
│   ├── execution.yaml
│   ├── universe.yaml
│   ├── strategy.yaml
│   ├── risk.yaml
│   └── ai.yaml
├── apps/
│   ├── api/
│   │   └── app/
│   │       ├── main.py
│   │       ├── routes/
│   │       └── dependencies.py
│   ├── worker/
│   │   └── app/
│   │       ├── jobs/
│   │       └── scheduler.py
│   └── dashboard/
│       └── nextjs_app/
├── packages/
│   ├── core/
│   │   ├── config/
│   │   ├── logging/
│   │   ├── time/
│   │   └── types/
│   ├── data/
│   │   ├── ingestion/
│   │   ├── providers/
│   │   └── features/
│   ├── strategy/
│   │   ├── regime.py
│   │   ├── signals.py
│   │   ├── scoring.py
│   │   └── exits.py
│   ├── ai/
│   │   ├── prompts/
│   │   ├── schemas/
│   │   ├── research.py
│   │   └── parser.py
│   ├── risk/
│   │   ├── checks.py
│   │   ├── sizing.py
│   │   └── kill_switch.py
│   ├── execution/
│   │   ├── execution_intent.py
│   │   ├── autonomous_executor.py
│   │   ├── broker_adapter.py
│   │   ├── alpaca_adapter.py
│   │   ├── order_manager.py
│   │   └── reconciliation.py
│   ├── reporting/
│   │   ├── daily.py
│   │   └── weekly.py
│   └── backtesting/
│       ├── engine.py
│       ├── metrics.py
│       └── walk_forward.py
├── db/
│   ├── migrations/
│   └── seed/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── paper/
├── scripts/
│   ├── run_backtest.py
│   ├── run_paper_cycle.py
│   ├── run_autonomous_cycle.py
│   ├── reconcile_broker.py
│   └── generate_report.py
└── docs/
    ├── architecture.md
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
- autonomous executor validation,
- order request builder,
- kill switch logic,
- config loading.

### 25.2 Integration Tests

Required:

- database write/read,
- Alpaca paper account connection,
- order submit/cancel in paper mode,
- protective stop creation,
- position reconciliation,
- AI JSON parsing,
- scheduled job dry run,
- autonomous execution dry run.

### 25.3 Failure Tests

Simulate:

- stale market data,
- invalid AI JSON,
- missing stop order,
- broker API timeout,
- duplicate order attempt,
- partial fill,
- unexpected broker position,
- database outage,
- kill switch activation,
- order submitted but not recorded,
- internal position without broker position,
- broker position without internal position.

---

## 26. Validation Roadmap

### Phase 0 - Specification

Deliverables:

- SPEC.md
- architecture diagram
- risk policy
- execution policy
- validation plan
- Codex implementation prompt

### Phase 1 - Deterministic Research Engine

Deliverables:

- data loader,
- feature engine,
- regime classifier,
- deterministic signal generator,
- backtest report.

### Phase 2 - Backtesting and Robustness

Deliverables:

- walk-forward testing,
- fees/slippage modeling,
- Monte Carlo trade sequence testing,
- benchmark comparison,
- parameter sensitivity.

### Phase 3 - AI Research Layer

Deliverables:

- news fetcher,
- AI summary prompt,
- AI decision JSON schema,
- AI output storage,
- candidate scoring integration.

### Phase 4 - Autonomous Paper Execution

Deliverables:

- Alpaca paper integration,
- execution intent builder,
- autonomous executor,
- order manager,
- stop-loss handling,
- broker reconciliation,
- alerts,
- daily report.

### Phase 5 - Level 4 Live Autonomous Execution

Deliverables:

- tiny live capital,
- autonomous live entries,
- autonomous exits,
- protective stops,
- strict caps,
- live kill switch,
- live reports,
- post-trade audit.

### Phase 6 - Level 5 Live Autonomous Execution

Deliverables:

- expanded capital only after validation,
- reduced manual oversight,
- stricter monitoring,
- formal operations runbook,
- periodic performance and risk reviews.

---

## 27. Acceptance Criteria

### 27.1 MVP v0.1 Acceptance

Complete when:

- deterministic backtest runs end-to-end,
- strategy produces trade logs,
- metrics report is generated,
- config files control behavior,
- unit tests pass.

### 27.2 MVP v0.2 Acceptance

Complete when:

- AI analyzes trade candidates,
- AI JSON outputs are validated,
- AI cannot create orders,
- AI outputs are logged,
- arbiter combines deterministic and AI scores.

### 27.3 MVP v0.3 Acceptance

Complete when:

- execution intents are generated,
- risk checks are enforced,
- Alpaca paper connects,
- paper orders can be placed autonomously,
- stops are managed,
- broker state is reconciled,
- reports are generated.

### 27.4 MVP v0.4 Acceptance

Complete when:

- autonomous paper mode runs for 4-6 weeks,
- no critical unresolved errors occur,
- all decisions are logged,
- all orders are reconciled,
- all positions have stops,
- kill switch is tested.

### 27.5 MVP v0.5 Acceptance

Complete when:

- Level 4 live mode runs with tiny capital,
- autonomous live execution works,
- strict risk caps are enforced,
- system can pause itself,
- reports are accurate,
- no unauthorized trade is possible.

### 27.6 Level 5 Acceptance

Complete only after:

- Level 4 has been stable for at least 3 months,
- live execution logs are complete,
- no critical safety gaps remain,
- strategy performance is reviewed,
- risk limits remain enforced,
- capital expansion is explicitly configured.

---

## 28. Profitability View

This system can be profitable, but profitability is not guaranteed and must be proven.

The system’s edge may come from:

1. deterministic strategy quality,
2. market-regime filtering,
3. strict risk control,
4. AI-assisted catalyst filtering,
5. better discipline,
6. better journaling,
7. automated execution consistency.

Major failure modes:

1. overfitting,
2. weak alpha,
3. slippage,
4. live fill differences,
5. AI hallucination,
6. data quality errors,
7. broker/API failures,
8. strategy decay,
9. excessive autonomy too early.

Therefore, autonomous execution must be enabled only after paper validation and must start with small live capital.

---

## 29. Immediate Next Steps

Before implementation, generate these files:

1. `SPEC.md`
2. `ARCHITECTURE.md`
3. `EXECUTION_POLICY.md`
4. `RISK_POLICY.md`
5. `VALIDATION_PLAN.md`
6. `OPERATIONS_RUNBOOK.md`
7. `CODEX_IMPLEMENTATION_PROMPT.md`
8. `CODEX_CONFIG.toml`
9. `.env.example`

First implementation target:

```text
Build MVP v0.1:
- config loading
- data ingestion abstraction
- feature engineering
- regime classifier
- deterministic strategy engine
- risk module skeleton
- backtest runner
- metrics report
```

Second implementation target:

```text
Build autonomous execution foundation:
- execution intent builder
- autonomous executor
- Alpaca paper adapter
- order manager
- stop handling
- broker reconciliation
- kill switch
```

---

## 30. Final Recommendation

Build the system as an **autonomous execution bot**, but keep its autonomy bounded.

Target:

```text
Level 4 first:
    live autonomous entries and exits,
    tiny capital,
    strict deterministic risk gates,
    AI-assisted news/catalyst scoring,
    broker execution,
    protective stops,
    full logs,
    daily reports,
    kill switch.

Level 5 later:
    only after long paper/live validation,
    expanded but still deterministic constraints,
    no unrestricted AI trading.
```

The best first real build is:

```text
A regime-filtered autonomous equities/ETF swing bot
with AI news/catalyst scoring,
deterministic order execution,
strict risk management,
broker reconciliation,
protective stops,
and complete auditability.
```
