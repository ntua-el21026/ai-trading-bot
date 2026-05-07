# Broker Integration

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 14 adds paper-only Alpaca broker boundaries. Milestone 16 uses those boundaries through
`FakeAlpacaClient` in a fake/local dry-run path. Milestone 20 adds an opt-in read-only Alpaca paper
smoke path. The repository does not start paper trading operations, does not activate Temporal
schedules, does not add real credentials, and does not enable live trading.

## Current Implementation

- `packages/broker/alpaca.py` defines `AlpacaClientProtocol`, `AlpacaPaperClient`,
  `AlpacaPaperReadOnlyHttpClient`, `AlpacaPaperCredentials`, `AlpacaPaperAdapter`, Alpaca-like
  payload mappers, paper entry-order request builders, protective-stop request builders,
  structured broker results, and stream/REST status helpers.
- `packages/broker/smoke.py` defines the explicit-gate read-only paper smoke runner and sanitized
  summary model.
- `scripts/check_alpaca_paper_readonly.py` runs the opt-in read-only smoke check with sanitized
  output only.
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
- read-only account, open-order, position, and clock/status smoke mapping;
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

Paper order lifecycle smoke tests remain deferred. A future milestone must separately gate and
approve any paper submit/cancel/protective-stop test before it can run.

## Current Non-Claims

- No paper trading operations have started.
- No live trading is enabled.
- No autonomous execution is enabled.
- No real Alpaca calls occur in default tests.
- No broker orders are submitted in default tests.
- The successful read-only paper smoke is connectivity evidence only; it is not actual paper
  trading.
- Protective-stop and reconciliation behavior are fake-client contract tests, not production paper
  evidence.
- Level 4 micro-live readiness remains unsatisfied.
