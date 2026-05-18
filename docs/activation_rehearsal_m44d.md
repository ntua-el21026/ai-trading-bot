# Milestone 44D Activation Rehearsal

Milestone 44D updates the M45 target from long-only, scale-in-disabled frozen paper validation to
long plus paper-only broad-ETF shorts plus deterministic long scale-ins. M44D does not start M45,
does not start the 8-week clock, and does not activate schedules.

## Source Of Truth

- Latest spec: `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md`.
- Prior Tiingo data gate: `docs/evidence/primary_signal_data_gate_m44c.json`.
- Rehearsal evidence: `docs/evidence/activation_rehearsal_m44d.json`.
- Refreshed readiness: `docs/evidence/frozen_readiness_m44d.json`.

## Short Rehearsal Policy

The short rehearsal is paper-only and restricted to one share in `IWM`, with `SPY` as fallback.
No individual-stock shorts, sector-ETF shorts, leveraged ETFs, inverse ETFs, live shorting, or
short scale-ins are allowed.

Required lifecycle:

- verify flat broker baseline and open paper session;
- verify asset tradable, marginable, shortable, and easy-to-borrow;
- submit one short entry using broker side `sell`;
- verify signed position quantity is negative;
- submit and verify one protective `buy` stop for the filled short quantity;
- cancel only the session-created buy stop before cleanup;
- submit a risk-reducing buy-to-cover for current short quantity only;
- verify final open orders `0`, positions `0`, and clean flat reconciliation.

If cleanup fails after stop cancellation and the short remains open, M44D must submit an emergency
replacement buy stop, produce a safe-incident result, and block M45 readiness.

## Long Scale-In Rehearsal Policy

The scale-in rehearsal is long-only and restricted to `XLK`, with `XLF` as fallback. It proves one
initial entry plus one add-on entry in the same symbol. No short scale-ins are enabled at M45 T0.

Required lifecycle:

- verify flat broker baseline after the short rehearsal cleanup;
- submit one initial long entry using broker side `buy`;
- submit and verify one initial protective `sell` stop for the initial filled quantity;
- submit one add-on long entry using broker side `buy`;
- submit and verify one additive protective `sell` stop for the add-on filled quantity;
- verify aggregate sell-stop quantity covers total open long quantity;
- cancel only session-created protective stops before cleanup;
- submit risk-reducing sell cleanup for current long quantity only;
- verify final open orders `0`, positions `0`, and clean flat reconciliation.

If cleanup fails after stop cancellation and the long remains open, M44D must submit an emergency
replacement sell stop, produce a safe-incident result, and block M45 readiness.

## Command Shape

```bash
RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE= \
ALERT_ENABLE_REAL_DELIVERY=false \
AI_ENABLE_ESCALATION=false \
NEWS_ENABLE_OPENAI_WEB_FALLBACK=false \
DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS=false \
RUN_FIRST_CONTROLLED_PAPER_SESSION= \
RUN_FIRST_CONTROLLED_PAPER_SESSION_EXECUTION= \
RUN_TEMPORAL_CLOUD_SMOKE= \
RUN_DASHBOARD_CONTROL_PLANE_SMOKE= \
RUN_VERCEL_DASHBOARD_PREVIEW= \
RUN_TELEGRAM_ALERT_SMOKE= \
uv run python scripts/run_activation_rehearsal_m44d.py \
  --mode full \
  --operator-approval MILESTONE_44D_SHORT_AND_SCALE_IN_REHEARSAL_AND_LONG_SHORT_SCALEIN_READINESS \
  --short-primary-symbol IWM \
  --short-fallback-symbol SPY \
  --scale-primary-symbol XLK \
  --scale-fallback-symbol XLF \
  --short-max-qty 1 \
  --scale-initial-max-qty 1 \
  --scale-addon-max-qty 1 \
  --confirm-paper-endpoint \
  --confirm-short-rehearsal-only \
  --confirm-scale-in-rehearsal-only \
  --confirm-protective-buy-stop-required \
  --confirm-additive-sell-stop-required \
  --confirm-cleanup-to-flat \
  --confirm-no-live-trading \
  --confirm-no-autonomous-live \
  --confirm-no-schedules \
  --confirm-no-leverage \
  --confirm-no-frozen-validation-start \
  --confirm-level4-not-ready
```

The script defaults to real paper mode. Tests and local fake rehearsals may pass
`--broker-mode fake`; fake mode is not broker evidence.

## M45 Readiness Rule

M45 long+short+scale-in readiness is `GO` only if:

- v0.6 is the latest source-of-truth spec;
- Tiingo EOD primary signal data remains verified;
- the real paper short lifecycle succeeds and cleans to flat;
- the real paper long scale-in lifecycle succeeds and cleans to flat;
- final broker baseline is zero open orders and zero positions;
- no schedules are active;
- frozen validation has not started;
- no unresolved blockers exist.

M45 still requires a separate explicit operator approval milestone.

## M44D Result

The M44D real-paper run was attempted under the approved envelope.

- Short rehearsal selected `IWM`.
- Short entry filled one paper share.
- Signed short position reconciliation passed.
- Protective buy stop was submitted and verified for one share.
- The session-created buy stop was cancelled before cleanup.
- Buy-to-cover cleanup filled one share.
- Short rehearsal final state was flat with zero open orders and zero positions.

The long scale-in rehearsal selected `XLK`.

- Initial long entry filled one paper share.
- Initial protective sell stop was submitted and verified for one share.
- The add-on/scale-in entry was rejected by Alpaca with sanitized
  `invalid_order_request`.
- The session-created initial stop was cancelled before cleanup.
- Risk-reducing sell cleanup filled one share.
- Final broker state was flat with zero open orders and zero positions.

Because the real scale-in add-on did not fill and the additive-stop lifecycle was not proven, M45
long+short+scale-in readiness is `NO-GO`. Frozen validation has not started, and no schedule was
activated.
