# Broker Integration

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Milestone 14 adds paper-only Alpaca broker boundaries. Milestone 16 uses those boundaries through
`FakeAlpacaClient` in a fake/local dry-run path. Milestone 20 adds an opt-in read-only Alpaca paper
smoke path. Milestone 21A adds an explicitly gated Alpaca paper order-lifecycle smoke harness. The
repository does not start paper trading operations, does not activate Temporal schedules, does not
add real credentials, and does not enable live trading.
Milestone 43 adds scale-in broker-state classification and additive-stop policy helpers with
fake/stub tests only. It does not run a real scale-in order or perform real broker writes.
Milestone 44 adds v0.5 side-aware broker semantics and flat-start cleanup evidence. Real M44 broker
writes were limited to cancelling verified AAPL/MSFT/XLK protective stops and submitting
risk-reducing sells for the current long quantities. No real short broker orders were submitted.
Final M44 broker baseline is flat with zero open orders and zero positions.

## Current Implementation

- `packages/broker/alpaca.py` defines `AlpacaClientProtocol`, `AlpacaPaperClient`,
  `AlpacaPaperReadOnlyHttpClient`, `AlpacaPaperCredentials`, `AlpacaPaperAdapter`, Alpaca-like
  payload mappers, paper entry-order request builders, protective-stop request builders,
  structured broker results, and stream/REST status helpers.
- `packages/broker/smoke.py` defines the explicit-gate read-only paper smoke runner and sanitized
  summary model.
- `packages/broker/order_lifecycle_smoke.py` defines the explicit-gate paper order-lifecycle smoke
  runner, future write-capable paper HTTP client, smoke-only intent construction, cleanup logic,
  and sanitized summary model.
- `scripts/check_alpaca_paper_readonly.py` runs the opt-in read-only smoke check with sanitized
  output only.
- `scripts/check_alpaca_paper_order_lifecycle.py` runs the opt-in paper order-lifecycle smoke
  harness with sanitized output only. It returns a safe refusal summary by default.
- `packages/broker/fakes.py` defines `FakeAlpacaClient` and fake adapter builders for local tests.
- `apps/workers/app/activities/broker.py` defines broker activity request/response contracts and
  activity functions for paper account/order/fill/position snapshots, idempotency lookups, paper
  entry submit, paper cancel, protective-stop submit/verify, and trade-update mapping.

The adapter depends on an injected client protocol. The repository does not add the Alpaca SDK in
this milestone, and default tests never instantiate an SDK-backed client.

## Paper-Only Gates

`AlpacaPaperAdapter` refuses:

- non-paper system environments;
- `live_trading_enabled=true`;
- `autonomous_execution_enabled=true`;
- `execution.allow_live_orders=true`;
- runtime mode without explicit paper credentials;
- runtime mode without an injected client.

Default tests use `run_mode="test"` with `FakeAlpacaClient`, so no credentials or external network
calls are required.

The read-only smoke path additionally requires:

- `ALPACA_API_KEY` present;
- `ALPACA_SECRET_KEY` present;
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`;
- `RUN_ALPACA_PAPER_SMOKE=1`;
- `ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT`;
- `config/system.yaml` live/autonomous flags disabled;
- `config/execution.yaml` live/autonomous order flags disabled;
- `AlpacaPaperAdapter` live-mode refusal check passing.

The paper order-lifecycle smoke path separately requires:

- `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1`;
- `ALPACA_PAPER_ORDER_LIFECYCLE_CONFIRM=SUBMIT_AND_CLEAN_UP_TINY_PAPER_ORDER`;
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`;
- `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` present;
- `ALPACA_PAPER_ORDER_SMOKE_SYMBOL` present and approved in `config/universe.yaml`;
- `ALPACA_PAPER_ORDER_SMOKE_MAX_QTY` present and `<= 1`;
- `ALPACA_PAPER_ORDER_SMOKE_MAX_NOTIONAL_USD` present and `<= 1000`;
- `ALPACA_PAPER_ORDER_SMOKE_TIMEOUT_SECONDS` present and `<= 180`;
- paper/dry-run config with live trading, autonomous execution, and live orders disabled;
- execution-intent, risk-check, broker-reconciliation, and protective-stop requirements enabled.

If any gate fails, the harness refuses before write-capable broker calls.

## Supported Boundaries

Implemented fake-tested boundaries:

- account snapshot mapping;
- open-order, fill, and position snapshots;
- lookup by broker order ID;
- lookup by `client_order_id`;
- paper DAY limit entry-order request construction;
- paper order cancellation;
- paper protective-stop submission for filled quantity;
- protective-stop verification against open fake broker orders;
- deterministic open-order role classification for `protective_stop`, `pending_entry`,
  `pending_exit`, `stale_session_order`, and `unknown_or_ambiguous`;
- additive protective-stop representation for scale-in filled quantity without canceling or
  replacing existing stops;
- signed quantity and position-side interpretation for long, flat, and dormant short positions;
- buy-stop protective semantics for future paper-only short positions;
- orphan stop, oversubscribed stop, unexpected short position, signed-quantity, and stream-vs-REST
  divergence mismatch classes;
- Alpaca `trade_updates` mapping;
- read-only account, open-order, position, and clock/status smoke mapping;
- explicitly gated smoke-only DAY limit entry submission, acknowledgement/fill observation,
  partial/unfilled handling, protective-stop submission for filled quantity, smoke-created order
  cancellation, cleanup exit submission, and sanitized final reconciliation through fake-client
  tests;
- REST fallback snapshot/status with the spec's 30-second active-window interval;
- structured ambiguity and safety errors for duplicate client IDs, timeouts, rejected orders,
  missing stops, stream disconnects, and REST fallback unavailability.

New-risk paper entries remain DAY limit orders only. Market entries and extended-hours entries are
not supported.

## Activity Boundary

Broker activity functions are registered with the worker activity registry, but the default broker
activity service uses a fake Alpaca adapter. Real Alpaca paper runtime wiring must be explicit and
server-side. Workflow modules still do not import broker clients, SDKs, credentials, or network
libraries directly.

These activity contracts are not end-to-end paper orchestration. They are side-effect boundaries for
later Temporal order lifecycle integration.

## Fake/Local Dry-Run Use

`packages/paper/` uses `FakeAlpacaClient` and the paper adapter gate behavior to exercise entry
acknowledgement, fill persistence, partial-fill stop quantity, protective-stop verification, broker
ambiguity, missing-stop incidents, and reconciliation mismatches. This is not a real Alpaca paper
smoke test and it does not submit broker orders.

## Optional Read-Only Paper Smoke

The read-only paper smoke command is opt-in and server-side only:

```bash
RUN_ALPACA_PAPER_SMOKE=1 \
ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT \
ALPACA_BASE_URL=https://paper-api.alpaca.markets \
  uv run python scripts/check_alpaca_paper_readonly.py
```

Allowed real calls are GET/read-only account, orders, positions, and clock/status calls. The smoke
path prints no secrets and does not print raw broker payloads. It does not submit, cancel, replace,
close, liquidate, or place protective-stop orders. The matching integration test is skipped by
default unless the same explicit gates are present.

Milestone 20 read-only smoke status: passed after corrected local paper credentials were loaded.
The sanitized result confirmed account, open-order, position, and clock/status reads mapped
successfully against `https://paper-api.alpaca.markets`, with zero submitted, cancelled, replaced,
or stop orders and no live endpoint use.

Milestone 21B controlled order-lifecycle smoke status: passed through the gated harness with final
target-symbol state clean/flat. This remains smoke evidence only; it is not actual paper trading or
frozen paper evidence.

## Optional Paper Order-Lifecycle Smoke Harness

The order-lifecycle smoke command is opt-in and server-side only:

```bash
uv run python scripts/check_alpaca_paper_order_lifecycle.py
```

With no write-smoke gates, this command refuses safely, prints a sanitized summary, and performs no
broker writes. When all write-smoke gates are explicitly loaded, it is designed to submit one tiny
paper `DAY` limit buy order with a smoke-only `client_order_id`, observe acknowledgement/fill
status, place a protective stop only for filled quantity, cancel unfilled or smoke-created orders,
submit a risk-reducing paper cleanup exit if a smoke-created position exists, and reconcile final
state as far as available.

This is not actual paper trading, not frozen paper evidence, and not Level 4 readiness. It is a
single operator-invoked broker lifecycle smoke harness.

## Current Non-Claims

- No paper trading operations have started.
- No live trading is enabled.
- No autonomous execution is enabled.
- No real Alpaca calls occur in default tests.
- No broker orders are submitted in default tests.
- The order-lifecycle smoke harness refuses by default.
- The successful read-only paper smoke is connectivity evidence only; it is not actual paper
  trading.
- Future successful order-lifecycle smoke output is broker lifecycle evidence only; it is not actual
  paper trading or frozen paper evidence.
- Protective-stop and reconciliation behavior are fake-client contract tests, not production paper
  evidence.
- Milestone 27 readiness aggregation does not invoke broker write smokes or touch broker state; it
  records existing broker evidence only.
- Level 4 micro-live readiness remains unsatisfied.
