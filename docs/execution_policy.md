# Execution Policy

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 05 implements passive execution-core contracts: `ExecutionIntent`, client-order
idempotency helpers, order lifecycle transition validation, and structured rejection models. It does
not implement broker adapters, broker order submission, database persistence, live trading, or real
Temporal order execution behavior.

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
