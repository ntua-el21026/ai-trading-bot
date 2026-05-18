# Risk Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md`.

Milestone 06 implements deterministic risk-check contracts, position sizing, kill-switch state
models, and passive broker reconciliation inputs. The implementation is passive: it approves or
rejects proposed new-risk entries, compares broker/internal snapshots, and returns structured reason
codes and incident recommendations. It does not submit orders, call a broker, write from Temporal to
managed database runtime, or enable live trading. Milestone 13 adds local/fake Temporal ledger
activities for risk-check and incident persistence. Milestone 14 adds fake-tested paper broker
boundaries for snapshots, idempotency lookup, protective-stop submit/verify, and ambiguity handling
without starting paper operations. Milestone 16 exercises deterministic risk checks in fake/local
dry-run scenarios, including risk rejection, duplicate active intent, stale data, and
kill-switch/pause-new-risk inputs, without enabling autonomous execution in config. Milestone 21A
adds a default-refusing Alpaca paper order-lifecycle smoke harness that must pass the same paper,
live-disabled, autonomy-disabled, reconciliation-required, and protective-stop-required config
invariants before any broker write-capable path can be reached. Milestone 43 adds deterministic
paper-validation scale-in caps and eligibility checks without weakening initial-entry safety or
performing broker writes.

Milestone 44 adds v0.5 frozen-validation risk defaults. Frozen validation starts long-only and flat,
with scale-ins disabled at validation T0. Dormant short-side paper architecture exists, but
`shorts.enabled=false` and real short broker writes remain forbidden in M44 and M45 start config.
M45 readiness is blocked until non-IEX primary signal data is verified or explicitly waived by
governance.

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

## Scale-In Risk Gates

M43 scale-in is treated as new risk and must pass the normal risk checks plus scale-in-specific
caps:

- `max_entries_per_symbol: 2`;
- `max_add_entries_per_symbol: 1`;
- `max_new_entry_qty: 1`;
- `max_scale_in_qty: 1`;
- `max_total_symbol_qty: 2`;
- `max_pending_entry_orders_per_symbol: 0`;
- `max_unresolved_incidents_per_symbol: 0`.

An existing long paper position may be considered only when current protective-stop coverage is
verified and sufficient. The add-on is refused if total symbol quantity, symbol notional, portfolio
exposure, aggregate risk-at-stop, or portfolio risk-at-stop would exceed configured caps.

Scale-in also refuses when no deterministic add-on signal exists. AI/news output cannot authorize
scale-in and cannot increase position size, alter stops, mutate risk limits, or bypass any gate.

Under v0.5, scale-in implementation remains present but frozen validation starts with scale-ins
disabled. Enabling scale-ins in a later paper stage requires at least 10 clean scheduled runs, real
broker additive-stop proof, and no missing-stop, duplicate-order, or unresolved reconciliation
incident.

## Dormant Short-Side Risk Gates

Short-side support is architecture-only at v0.5 validation start. A future short rehearsal must be
paper-only, explicitly approved, and limited to the configured broad ETF subset: SPY, QQQ, DIA, and
IWM. Individual-stock shorts, sector ETF shorts, leveraged ETF shorts, inverse ETF shorts, live
shorting, leverage, and margin borrowing remain disabled.

If shorts are enabled by a future milestone, every short candidate must pass side-aware gates:
paper mode, eligible symbol, tradable/marginable/shortable/easy-to-borrow asset status, account
shorting permission, whole-share quantity, no same-symbol long or pending entry, no ambiguous
broker state, deterministic bearish signal, valid `ExecutionIntent`, and a protective buy-stop plan.
An open short without aggregate verified buy-stop coverage is a critical incident.

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

Milestone 14 fake broker snapshots can feed the reconciliation comparison service. These tests are
contract validation only; they are not broker paper evidence and do not prove live readiness.
Milestone 16 fake/local dry-run scenarios persist reconciliation mismatches and missing-stop
incidents through the local ledger, still without real broker calls.

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

Later milestones must connect these contracts to end-to-end Temporal execution workflows, explicit
Alpaca paper smoke evidence, and managed database audit persistence. The ledger foundation now
provides schema, local repository support, local/fake Temporal activity boundaries, fake/local
dry-run evidence for risk-check and incident persistence, and a gated order-lifecycle smoke harness
that refuses by default. Any change to risk limits or risk semantics requires explicit approval and
a corresponding spec update.

## Level 4 Readiness Status

`docs/level4_micro_live_readiness.md` documents the current Level 4 micro-live risk config review.
The current `risk_level_4_micro_live` values match the latest spec, while live trading and
autonomous live execution remain disabled. Level 4 readiness is not satisfied because frozen paper,
real broker/provider, managed database runtime, dashboard, alerting, and go/no-go evidence are still
absent. The Milestone 21A harness is not actual paper trading and does not satisfy frozen paper or
Level 4 evidence gates.

## Milestone 44D v0.6 Risk Policy

v0.6 makes shorts eligible for M45 paper validation only after the M44D real paper rehearsal
succeeds. Short risk remains paper-only:

- live shorting is disabled;
- short universe is `SPY`, `QQQ`, `DIA`, `IWM`;
- individual-stock shorts, sector-ETF shorts, leveraged ETFs, and inverse ETFs are rejected;
- maximum total short symbol quantity is one share;
- only one open short symbol is allowed;
- every filled short quantity requires a verified protective buy stop;
- short scale-ins remain disabled at validation start.

v0.6 also makes long scale-ins eligible for M45 paper validation only after the M44D or M44E
additive-stop rehearsal succeeds:

- one initial entry plus one add-on entry per symbol;
- maximum total symbol quantity is two shares;
- an existing verified stop is required before add-on entry;
- the add-on fill requires an additive sell stop for the added quantity;
- if a plain add-on buy is rejected by Alpaca wash-trade protection while the initial sell stop is
  open, a broker-native OTO add-on with an attached stop-loss child may satisfy the additive-stop
  proof;
- aggregate verified stop quantity must cover total open long quantity;
- no stop cancel/replace is allowed during the scale-in entry path.

The final M44E and M45 start baseline must be flat with zero open orders, zero positions, and clean
reconciliation. Live trading, autonomous live execution, leverage, and Level 4 readiness remain out
of scope.

## Milestone 45 Frozen Risk Boundary

M45 freezes v0.6 risk for the 56-day paper window: maximum gross exposure 20%, maximum net exposure
20%, maximum open positions 4, maximum two new entries per day, maximum one long scale-in per day,
maximum one open short symbol, no short scale-ins, no live shorting, no leverage, no forced trades,
and zero unresolved critical incidents. Broker reconciliation and protective-stop verification
remain mandatory before and after any scheduled paper execution.
