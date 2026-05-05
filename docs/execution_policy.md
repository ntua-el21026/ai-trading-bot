# Execution Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 06 implements passive execution-core and broker-reconciliation contracts:
`ExecutionIntent`, client-order idempotency helpers, order lifecycle transition validation,
structured rejection models, broker adapter protocols, normalized broker state models, Alpaca
`trade_updates` mapping, and pure reconciliation comparison. It does not implement executable broker
order submission, database persistence, live trading, or real Temporal order execution behavior.

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

The helper also provides duplicate active-intent detection. Broker and database lookup before retry
remain deferred to broker reconciliation and execution milestones.

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

`packages/broker/alpaca.py` currently provides a safe Alpaca paper adapter skeleton and fixture
mapping for Alpaca `trade_updates`. The adapter refuses live-mode configuration and raises
`BrokerAdapterNotConfigured` for all network/order methods until a later milestone wires an explicit
paper client inside Temporal activities.

## Stream And REST Fallback

Alpaca `trade_updates` fixture payloads are mapped to normalized `BrokerStreamEvent`,
`BrokerOrder`, and `BrokerFill` contracts. REST fallback is represented by
`BrokerRestFallbackSnapshot`, which uses the latest-spec 30-second fallback interval. Tests use
fixtures only; no websocket, REST, or broker credential access occurs.

## Level 4 Readiness Status

`docs/level4_micro_live_readiness.md` documents the execution evidence required before Level 4
micro-live: valid `ExecutionIntent`, broker reconciliation, idempotent `client_order_id`,
protective-stop verification, partial-fill handling, duplicate-order prevention, alerts, and
manual-control evidence. Current implementation remains passive and does not submit paper or live
broker orders.
