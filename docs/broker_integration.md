# Broker Integration

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 14 adds paper-only Alpaca broker boundaries. It does not start paper trading operations,
does not activate Temporal schedules, does not add real credentials, and does not enable live
trading.

## Current Implementation

- `packages/broker/alpaca.py` defines `AlpacaClientProtocol`, `AlpacaPaperClient`,
  `AlpacaPaperCredentials`, `AlpacaPaperAdapter`, Alpaca-like payload mappers, paper entry-order
  request builders, protective-stop request builders, structured broker results, and stream/REST
  status helpers.
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
- Alpaca `trade_updates` mapping;
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

## Optional Paper Smoke Tests

Real Alpaca paper smoke tests are deferred. When added, they must:

- require explicit paper credentials from environment or secret manager;
- use a marker such as `--run-alpaca-paper`;
- be excluded from the default test suite;
- submit only explicitly approved paper orders;
- verify idempotency lookup, cancel behavior, protective stop placement, and reconciliation evidence;
- never accept live endpoints or live credentials.

## Current Non-Claims

- No paper trading operations have started.
- No live trading is enabled.
- No autonomous execution is enabled.
- No real Alpaca calls occur in default tests.
- No broker orders are submitted in default tests.
- Protective-stop and reconciliation behavior are fake-client contract tests, not production paper
  evidence.
- Level 4 micro-live readiness remains unsatisfied.
