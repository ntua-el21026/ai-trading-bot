# Milestone 44E Scale-In Repair Rehearsal

Milestone 44E repairs the M44D long scale-in add-on rejection and reruns exactly one bounded real
Alpaca paper long scale-in rehearsal. It does not rerun the short rehearsal, start M45, start the
8-week validation clock, activate schedules, enable live trading, enable autonomous live execution,
enable leverage, or claim Level 4 readiness.

## Accepted Prior Evidence

- Latest spec remains `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md`.
- M44D short proof remains accepted from `docs/evidence/activation_rehearsal_m44d.json`.
- M44D final broker baseline was flat with zero open orders and zero positions.
- M44C Tiingo EOD primary signal data gate remains the accepted primary signal-data proof.

## Root Cause

M44D failed at the add-on entry with sanitized
`scale_in_entry_submit_failed:invalid_order_request`. The likely cause is Alpaca's wash-trade
protection: a plain same-symbol `buy limit` may be rejected while an existing protective `sell stop`
is open. The repair preserves the initial stop and changes only the add-on order shape.

## Repair

The M44E scale-in repair submits the add-on as a broker-native OTO order with an attached
stop-loss child. The add-on parent is the second long entry; the OTO child is the additive
protective sell stop for the added quantity. The existing initial protective stop remains open
during add-on submission.

Safety boundaries:

- approved symbols are `XLK`, then fallback `XLF`;
- maximum initial quantity is 1 share;
- maximum add-on quantity is 1 share;
- maximum total symbol quantity is 2 shares;
- no short orders are used;
- no existing stop may be cancelled before the add-on entry;
- aggregate verified sell-stop quantity must cover total long quantity;
- cleanup cancels only session-created stops for the rehearsal symbol;
- cleanup sell quantity may not exceed the current long quantity;
- final broker baseline must be zero open orders and zero positions.

## Command

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
  --mode scale-in-repair \
  --operator-approval MILESTONE_44E_SCALE_IN_REPAIR_AND_REHEARSAL \
  --scale-primary-symbol XLK \
  --scale-fallback-symbol XLF \
  --scale-initial-max-qty 1 \
  --scale-addon-max-qty 1 \
  --confirm-paper-endpoint \
  --confirm-scale-in-rehearsal-only \
  --confirm-additive-sell-stop-required \
  --confirm-cleanup-to-flat \
  --confirm-no-live-trading \
  --confirm-no-autonomous-live \
  --confirm-no-schedules \
  --confirm-no-leverage \
  --confirm-no-frozen-validation-start \
  --confirm-level4-not-ready
```

## Evidence

M44E writes:

- `docs/evidence/scale_in_rehearsal_m44e.json`
- `docs/evidence/frozen_readiness_m44e.json`

M45 long+short+scale-in readiness is `GO` only if M44D short proof is accepted, M44E scale-in proof
succeeds, Tiingo EOD remains verified, final broker baseline is flat, scale-ins are enabled in the
v0.6 validation-start policy, no schedules are active, frozen validation has not started, and no
blockers remain.

## M44E Result

The real M44E repair rehearsal selected `XLK`; fallback was not used.

- Initial long entry filled one paper share.
- Initial protective sell stop was verified for one share.
- The repaired add-on used Alpaca OTO with an attached stop-loss child.
- Add-on entry filled one paper share.
- Additive protective sell stop was verified for one share.
- Aggregate sell-stop protection was verified for total long quantity two.
- Cleanup sell filled the total two-share long quantity.
- A transient session-created orphan emergency stop was canceled after read-only flat-position
  verification.
- Final broker baseline is flat: open orders `0`, positions `0`, clean reconciliation.
- M45 long+short+scale-in readiness is `GO`, with explicit M45 operator approval still required.
