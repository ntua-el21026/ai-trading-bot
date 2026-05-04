# Risk Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 05 implements deterministic risk-check contracts, position sizing, and kill-switch state
models. The implementation is passive: it approves or rejects proposed new-risk entries and returns
structured reason codes. It does not submit orders, call a broker, write a database, or enable live
trading.

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

Milestone 06 must provide real broker reconciliation inputs. Later milestones must connect these
contracts to Temporal execution workflows and database audit persistence. Any change to risk limits
or risk semantics requires explicit approval and a corresponding spec update.
