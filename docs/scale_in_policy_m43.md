# Milestone 43 Scale-In Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.4.md`.

Milestone 43 adds deterministic paper-validation scale-in support before the 8-week frozen paper
validation starts. It does not start frozen validation, activate schedules, enable live trading,
enable autonomous live execution, enable leverage, or grant AI broker authority.

## Scope

Scale-in is allowed only as a deterministic execution/risk policy extension for paper validation.
The strategy may evaluate the full configured allowed universe:

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

No symbol is forced to trade. Symbols with existing protected positions are no longer
automatically skipped; they are routed through the scale-in eligibility gates and are refused
unless every deterministic gate passes.

## Configuration

The frozen M43 policy values live in `config/execution.yaml`:

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

## Eligibility Rules

A scale-in candidate must already have a long paper position with quantity greater than zero and
less than `max_total_symbol_qty`. Existing verified protective-stop coverage is required before a
scale-in can be considered.

Scale-in is refused when any of these are true:

- scale-in is disabled;
- the position is flat, short, or already at the total-symbol quantity cap;
- verified protective-stop coverage is missing or insufficient;
- a pending entry order exists;
- an unknown, ambiguous, stale, or pending-exit order exists;
- an unresolved symbol incident exists;
- broker reconciliation is not clean;
- no deterministic add-on signal is present;
- symbol notional, portfolio exposure, or aggregate risk-at-stop would exceed caps;
- an active duplicate scale-in intent exists for the symbol, side, or signal;
- a previous scale-in stop remains unverified.

AI/news output cannot authorize scale-in. AI remains advisory only and cannot create orders, modify
orders, modify stops, change strategy rules, change risk limits, or access broker credentials.

## Open Order Roles

Open orders are classified deterministically:

| Role | Effect |
| --- | --- |
| `protective_stop` | Allowed and required when verified. Does not block scale-in by itself. |
| `pending_entry` | Blocks scale-in. |
| `pending_exit` | Blocks new risk. |
| `stale_session_order` | Blocks scale-in until resolved. |
| `unknown_or_ambiguous` | Blocks scale-in until resolved. |

## Stop Policy

The M43 scale-in path uses additive stops only:

- keep existing protective stops intact;
- do not cancel or replace stops before scaling in;
- after an add-on fill, submit a new protective stop only for the newly filled quantity;
- verify the add-on stop through broker read-back;
- require final summed protected quantity to cover the total open symbol position.

The aggregate protection rule is:

```text
protected_quantity_sum >= open_position_quantity
```

If the added quantity does not receive a verified protective stop, the system must produce a
structured safe incident, block further new risk, and use only the already approved emergency
cleanup path when that path explicitly permits it.

## Reporting

Evidence and reports must distinguish these action roles:

- `initial_entry`
- `scale_in_entry`
- `initial_protective_stop`
- `add_on_protective_stop`
- `exit`
- `cleanup`
- `incident_repair`

Frozen validation reporting must record initial entries, scale-in entries, scale-in success/failure,
total symbol quantity after scale-in, protected quantity after scale-in, scale-in incidents, and PnL
attribution notes when partial scale-in exists.

## Current Paper Holds

The accepted M39-M42 evidence leaves these expected protected paper holds:

- AAPL quantity 1 with verified protective stop quantity 1;
- MSFT quantity 1 with verified protective stop quantity 1;
- XLK quantity 1 with verified protective stop quantity 1.

Under M43, those symbols are potential scale-in candidates only if a fresh deterministic add-on
signal and all risk/execution/reconciliation gates pass. They are not automatically scaled in.

## Safety Status

M43 performed no real broker writes and does not authorize a real scale-in run. It does not submit,
cancel, replace, or flatten broker orders. It does not call OpenAI, Marketaux, Alpha Vantage,
Telegram delivery, Vercel deployment, or Temporal schedule activation. M44 must separately freeze
versions and explicitly start the 8-week validation clock if the operator accepts the readiness
state.
