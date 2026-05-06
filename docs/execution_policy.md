# Execution Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 06 implements passive execution-core and broker-reconciliation contracts:
`ExecutionIntent`, client-order idempotency helpers, order lifecycle transition validation,
structured rejection models, broker adapter protocols, normalized broker state models, Alpaca
`trade_updates` mapping, and pure reconciliation comparison. It does not implement executable broker
order submission, live trading, or real Temporal order execution behavior. Milestone 12 adds
database/audit-ledger schema and local repository foundations for later execution persistence.
Milestone 13 adds local/fake Temporal ledger activity boundaries for execution intent, order, fill,
and position audit persistence without submitting broker orders. Milestone 14 adds paper-only
Alpaca adapter and broker activity boundaries behind explicit gates, using fake clients in default
tests and without starting paper trading operations. Milestone 16 adds fake/local dry-run
orchestration that creates and persists an `ExecutionIntent`, fake order/fill/position records, and
protective-stop verification evidence without real broker orders.

## Foundation Defaults

- `allow_live_orders: false`
- `autonomous_execution_enabled: false`
- `require_execution_intent: true`
- `require_passed_risk_check: true`
- `require_broker_reconciliation_before_order: true`
- `require_protective_stop: true`

## ExecutionIntent

`packages/execution/models.py` defines `ExecutionIntent` with the latest-spec fields:

- decision ID;
- symbol;
- side;
- asset class;
- quantity;
- entry order type;
- limit price;
- stop loss price;
- time in force;
- strategy version;
- risk config version;
- autonomy level;
- protective-stop requirement;
- max acceptable slippage in basis points;
- expiration timestamp;
- client order ID root;
- status;
- optional Temporal workflow ID.

`packages/execution/execution_intent.py` only creates an intent after an approved risk assessment.

## Idempotency

`packages/execution/idempotency.py` builds deterministic client order ID roots in the spec format:

```text
{strategy}-{symbol}-{side}-{trade_date}-{intent_seq}-{short_hash}
```

The helper also provides duplicate active-intent detection. The ledger foundation enforces
`execution_intents.client_order_id_root` uniqueness locally and in the Postgres-target schema.
Broker lookup before retry and managed database runtime evidence remain deferred to broker
reconciliation and execution milestones.

Milestone 14 adds fake-tested broker lookup by `client_order_id` before paper submit retry. This is
not yet wired into an end-to-end execution workflow and does not submit real broker orders in
default tests.

Milestone 16 exercises this idempotent client-order path through `FakeAlpacaClient` in the
fake/local dry run only. It is not actual paper broker execution.

## Order Lifecycle Abstractions

`packages/execution/order_lifecycle.py` validates local lifecycle transitions only. It does not call
a broker or submit orders. Invalid transitions return structured rejections for future audit logging.

## Required Future Boundary

Future broker order submission must happen only through the deterministic Temporal execution workflow path, after valid decisions, risk checks, reconciliation, active autonomy permission, and kill-switch checks.

AI/news intelligence is not an execution path. AI output cannot create orders, modify orders, change
stops, modify strategy rules, modify risk limits, access broker credentials, or call broker APIs.

Dashboard/control-plane actions are also not an execution path. The Milestone 08 contracts expose no
order-entry action, no natural-language trading input, and no broker adapter access. Safe controls
are auditable requests mapped to server-side Temporal signal names only.

## Broker Adapter Boundary

`packages/broker/adapters.py` defines the broker operations required by later execution activities:

- account snapshot retrieval;
- open order retrieval and lookup by broker/client order ID;
- recent fill retrieval;
- current position retrieval;
- protective stop lookup;
- REST fallback snapshot retrieval;
- order submission, cancellation, protective-stop submission, and stream event consumption.

`packages/broker/alpaca.py` provides a paper-only Alpaca adapter that depends on an injectable client
protocol. It refuses non-paper environments, live-trading flags, autonomous-execution flags, and
`allow_live_orders=true`. Runtime mode requires explicit paper credentials and an injected client.
Default tests use `FakeAlpacaClient` and do not call Alpaca.

Implemented fake-tested paper boundaries:

- account, open-order, fill, and position snapshots;
- lookup by broker order ID and `client_order_id`;
- DAY limit entry-order request construction;
- paper order cancellation;
- protective-stop submission for filled quantity;
- protective-stop verification;
- structured ambiguous/failed results for timeouts, duplicate client IDs, rejected orders, missing
  stops, stream disconnects, and REST fallback unavailability.

## Stream And REST Fallback

Alpaca `trade_updates` fixture payloads are mapped to normalized `BrokerStreamEvent`,
`BrokerOrder`, and `BrokerFill` contracts. REST fallback is represented by
`BrokerRestFallbackSnapshot`, which uses the latest-spec 30-second fallback interval. Tests use
fakes and fixtures only; no websocket, REST, real Alpaca, or broker credential access occurs.

## Level 4 Readiness Status

`docs/level4_micro_live_readiness.md` documents the execution evidence required before Level 4
micro-live: valid `ExecutionIntent`, broker reconciliation, idempotent `client_order_id`,
protective-stop verification, partial-fill handling, duplicate-order prevention, alerts, and
manual-control evidence. Current implementation has paper-only broker boundaries, but no end-to-end
paper operations, frozen paper evidence, or live trading approval. The fake/local dry-run path is
local validation evidence only.
