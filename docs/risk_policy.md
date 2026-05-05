# Risk Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 06 implements deterministic risk-check contracts, position sizing, kill-switch state
models, and passive broker reconciliation inputs. The implementation is passive: it approves or
rejects proposed new-risk entries, compares broker/internal snapshots, and returns structured reason
codes and incident recommendations. It does not submit orders, call a broker, write a database, or
enable live trading.

## Foundation Defaults

- Paper environment by default.
- Dry-run behavior by default.
- Live trading disabled.
- Autonomous execution disabled.
- Margin disabled.
- Shorting disabled.
- Options, futures, crypto, leveraged ETFs, and prediction markets disabled.
- Protective stops required in configuration.

## Implemented Risk Checks

`packages/risk/checks.py` evaluates a `NewRiskOrderInput` against typed config and current state.
Checks include:

- environment validity and paper/live mode consistency;
- autonomous execution flags;
- approved live symbol and equity/ETF asset-class scope;
- market-session validity placeholder supplied by the caller;
- data freshness;
- broker reconciliation cleanliness placeholder supplied by the caller;
- kill-switch state;
- daily, weekly, and monthly loss limits;
- max position size, gross exposure, deployable capital, open positions, and sector exposure;
- minimum cash buffer;
- protective stop availability and stop distance;
- max risk per trade;
- duplicate active intent;
- broker account mode consistency;
- system health placeholder;
- Temporal workflow state consistency placeholder.

Any failed check rejects the new-risk order.

## Broker Reconciliation Input

`packages/reconciliation/service.py` compares normalized broker snapshots against passive internal
ledger snapshots. Its `ReconciliationResult.broker_reconciliation_clean` property is designed to feed
the existing `broker_reconciliation_clean` risk-check input.

Critical reconciliation mismatches recommend `PAUSED_NEW_RISK` behavior while preserving
risk-reducing exits. Missing protective stops follow the latest-spec thresholds:

- warning/investigate after the warning threshold;
- critical pause-new-risk after the critical threshold;
- flatten-if-safe recommendation after the flatten threshold.

The implementation emits recommendations only. It does not cancel orders, submit flattening orders,
or mutate kill-switch state directly.

## AI Risk Intelligence Input

`packages/ai/scoring.py` maps schema-validated AI news events into deterministic AI scores,
hard-block flags, and non-increasing size multipliers. AI output is advisory only and does not
override risk checks, broker reconciliation, kill-switch state, protective-stop requirements, or
execution gates.

Invalid AI output, no news, or provider outages fall back to neutral behavior and do not trigger a
global kill switch by themselves.

## Dashboard Control Input

`packages/control_plane/models.py` represents manual kill-switch, pause-new-risk, resume-after-review,
force reconciliation/report, and acknowledge-incident requests as auditable control commands. These
commands do not modify risk limits, autonomy level, stop policy, or broker state directly.

## Position Sizing

`packages/risk/sizing.py` implements the latest-spec sizing formula:

```text
risk_amount = account_equity * max_risk_per_trade_pct
stop_distance = entry_price - stop_price
raw_shares = floor(risk_amount / stop_distance)
max_value_shares = floor((account_equity * max_position_size_pct) / entry_price)
shares = min(raw_shares, max_value_shares)
```

Regime, AI, and execution-quality multipliers may reduce size when supplied. Multipliers are capped
at `1.0` and cannot increase size above deterministic caps. Invalid stop distance or fewer than one
share rejects sizing.

## Kill Switch

`packages/risk/kill_switch.py` models:

- `RUNNING`
- `PAUSED_NEW_RISK`
- `PAUSED_ALL_AUTONOMOUS_ACTIONS`
- `FORCE_FLAT_REQUESTED`
- `MANUAL_REVIEW_REQUIRED`

Only `RUNNING` allows new risk. Risk-reducing exits remain allowed in pause/force-flat/review states
unless the state is `PAUSED_ALL_AUTONOMOUS_ACTIONS`.

## Future Work

Later milestones must connect these contracts to Temporal execution workflows, real Alpaca paper
adapters, and database audit persistence. Any change to risk limits or risk semantics requires
explicit approval and a corresponding spec update.

## Level 4 Readiness Status

`docs/level4_micro_live_readiness.md` documents the current Level 4 micro-live risk config review.
The current `risk_level_4_micro_live` values match the latest spec, while live trading and
autonomous live execution remain disabled. Level 4 readiness is not satisfied because frozen paper,
real broker/provider, database, dashboard, alerting, and go/no-go evidence are still absent.
