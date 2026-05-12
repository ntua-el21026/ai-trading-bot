# First Controlled Paper Session Execution

Milestone 34 adds the explicitly gated execution boundary for the first controlled Alpaca paper
session. This is the first milestone where real Alpaca paper broker writes may occur, but only
after every launch-packet, endpoint, reconciliation, risk, `ExecutionIntent`, protective-stop, and
cleanup-policy gate passes.

This milestone still refuses safely when the operator has not supplied a target symbol and order
envelope. The Milestone 34 repository run recorded a NO-GO result because no operator-selected
target symbol, maximum quantity, or maximum notional was provided.

Milestone 35A corrects the first-session symbol and envelope model before real execution. The
earlier universal `25.0` USD max-notional cap was too low for the configured approved universe and
could force a far-below-market limit price if the system derived price from notional. The corrected
model requires an explicit operator-supplied limit price and validates the resulting estimated
notional locally before any broker access.

## Scope

The execution path supports:

- default refusal with no external calls and no broker writes;
- existing Milestone 30 fake/local real-gate checks;
- `fake-real-paper` rehearsal of one entry order, fill handling, protective stop verification, and
  result packet generation with fake adapters only;
- `real-paper` mode that can reach Alpaca paper writes only after all explicit gates pass.

The path does not call OpenAI, Marketaux, Alpha Vantage, Telegram real delivery, Temporal Cloud,
Supabase/Postgres, or Vercel. It does not activate schedules, enable unattended operation, enable
live trading, enable autonomous live execution, add leverage, allow shorts, or grant AI broker
authority.

## Required Real-Paper Gates

The real-paper path must refuse before broker writes unless all of these are present:

- operator marker `MILESTONE_34_FIRST_CONTROLLED_PAPER_SESSION`;
- GO launch packet at `docs/evidence/first_controlled_paper_session_launch_packet.json`;
- `--confirm-paper-endpoint`;
- `--confirm-real-paper-writes`;
- `--confirm-no-live-trading`;
- `--confirm-no-autonomous-live`;
- `--confirm-no-schedules`;
- `--confirm-no-leverage`;
- `--confirm-first-session-only`;
- `--confirm-protective-stop-required`;
- `--confirm-cleanup-policy`;
- operator-provided `--target-symbol`;
- operator-provided `--max-qty`;
- operator-provided `--max-notional`.
- operator-provided `--limit-price`.

The target symbol must be approved by the configured universe, long-only, and clean of existing
target-symbol open orders and positions before execution. The first-session envelope is intentionally
small; the default policy requires one share and a limit DAY entry order.

## Milestone 35A Envelope Policy

The first-session envelope is now validated as:

- `first_session_max_qty = 1`;
- `first_session_absolute_max_notional_usd = 500.0`;
- `estimated_entry_notional_usd = max_qty * limit_price`;
- `max_qty <= first_session_max_qty`;
- `max_notional <= first_session_absolute_max_notional_usd`;
- `estimated_entry_notional_usd <= max_notional`;
- `limit_price` must be explicit, positive, and finite;
- target symbol must be in the configured live universe;
- leveraged and inverse ETFs remain forbidden.

The configured live universe currently contains:

```text
SPY, QQQ, DIA, IWM, XLK, XLF, XLE, XLV, AAPL, MSFT, NVDA, AMZN, META, GOOGL
```

Milestone 35A adds a local-only universe audit mode:

```bash
uv run python scripts/run_first_controlled_paper_session.py --mode audit-symbol-universe
```

This audit performs no external calls and no broker writes. It verifies that each configured symbol
is structurally eligible for the first-session path when the operator supplies a valid quantity,
max notional, and limit price.

## Commands

Default refusal:

```bash
uv run python scripts/run_first_controlled_paper_session.py
```

Real-paper refusal when target and envelope are missing:

```bash
uv run python scripts/run_first_controlled_paper_session.py \
  --mode real-paper \
  --operator-approval MILESTONE_34_FIRST_CONTROLLED_PAPER_SESSION \
  --confirm-paper-endpoint \
  --confirm-real-paper-writes \
  --confirm-no-live-trading \
  --confirm-no-autonomous-live \
  --confirm-no-schedules \
  --confirm-no-leverage \
  --confirm-first-session-only \
  --confirm-protective-stop-required \
  --confirm-cleanup-policy
```

Fake real-paper rehearsal:

```bash
uv run python scripts/run_first_controlled_paper_session.py \
  --mode fake-real-paper \
  --scenario happy_path \
  --operator-approval MILESTONE_34_FAKE_REAL_PAPER
```

A future real execution retry must add an operator-selected target and envelope:

```bash
uv run python scripts/run_first_controlled_paper_session.py \
  --mode real-paper \
  --operator-approval MILESTONE_34_FIRST_CONTROLLED_PAPER_SESSION \
  --target-symbol <OPERATOR_SELECTED_SYMBOL> \
  --max-qty 1 \
  --max-notional <OPERATOR_SELECTED_MAX_NOTIONAL> \
  --limit-price <OPERATOR_SELECTED_LIMIT_PRICE> \
  --confirm-paper-endpoint \
  --confirm-real-paper-writes \
  --confirm-no-live-trading \
  --confirm-no-autonomous-live \
  --confirm-no-schedules \
  --confirm-no-leverage \
  --confirm-first-session-only \
  --confirm-protective-stop-required \
  --confirm-cleanup-policy
```

Do not choose the symbol automatically. Do not increase quantity or notional beyond the approved
operator envelope.

The following are examples only and do not claim current market prices:

```bash
uv run python scripts/run_first_controlled_paper_session.py \
  --mode fake-real-paper \
  --scenario happy_path \
  --operator-approval MILESTONE_34_FAKE_REAL_PAPER \
  --target-symbol AAPL \
  --max-qty 1 \
  --max-notional 350 \
  --limit-price 330

uv run python scripts/run_first_controlled_paper_session.py \
  --mode fake-real-paper \
  --scenario happy_path \
  --operator-approval MILESTONE_34_FAKE_REAL_PAPER \
  --target-symbol SPY \
  --max-qty 1 \
  --max-notional 500 \
  --limit-price 490

uv run python scripts/run_first_controlled_paper_session.py \
  --mode fake-real-paper \
  --scenario happy_path \
  --operator-approval MILESTONE_34_FAKE_REAL_PAPER \
  --target-symbol QQQ \
  --max-qty 1 \
  --max-notional 500 \
  --limit-price 490
```

The future real M35 command must use the operator-selected target symbol and envelope, plus a
milestone-scoped operator marker. Milestone 35A used
`MILESTONE_35_OPERATOR_SELECTED_FIRST_CONTROLLED_PAPER_SESSION` for local gate validation only and
did not run the real command. Milestone 35B uses
`MILESTONE_35B_OPERATOR_SELECTED_FIRST_CONTROLLED_PAPER_SESSION` for the operator-selected AAPL
execution attempt.

Milestone 35B command shape, with process-local safety overrides because local `.env` may still
contain unrelated smoke/control flags:

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
uv run python scripts/run_first_controlled_paper_session.py \
  --mode real-paper \
  --operator-approval MILESTONE_35B_OPERATOR_SELECTED_FIRST_CONTROLLED_PAPER_SESSION \
  --target-symbol AAPL \
  --max-qty 1 \
  --max-notional 350 \
  --limit-price 330 \
  --confirm-paper-endpoint \
  --confirm-real-paper-writes \
  --confirm-no-live-trading \
  --confirm-no-autonomous-live \
  --confirm-no-schedules \
  --confirm-no-leverage \
  --confirm-first-session-only \
  --confirm-protective-stop-required \
  --confirm-cleanup-policy
```

This command may submit real Alpaca paper orders only when the launch packet is GO, the paper
endpoint is proven, AAPL is clean, the market/session is acceptable, reconciliation is clean, the
ExecutionIntent is valid, and the protective-stop plan is present. If any gate fails, it must refuse
before broker writes or stop in a documented safe incident state.

Milestone 35C retries the same AAPL envelope during an acceptable regular market session with
`MILESTONE_35C_OPERATOR_SELECTED_FIRST_CONTROLLED_PAPER_SESSION`. It must first rerun the
real-read-only preflight with process-local safety overrides and may run the write-capable
real-paper command only if that refreshed packet is GO and the market/session is open.

## Evidence

Milestone 34 writes a sanitized result packet to:

```text
docs/evidence/first_controlled_paper_session_result.json
```

The packet records:

- launch packet reference;
- operator approval marker;
- target symbol and order envelope if provided;
- explicit limit price;
- estimated entry notional;
- first-session quantity and notional ceilings;
- symbol allowlist decision;
- order-envelope validation result and rejection reasons;
- paper endpoint proof and live endpoint not-used proof;
- pre-run broker state and reconciliation result;
- candidate, decision, risk-check, `ExecutionIntent`, order, fill, and stop identifiers when
  reached;
- cleanup policy and cleanup actions when reached;
- post-run reconciliation when reached;
- incidents and blockers;
- fake alert summary;
- actual-paper-trading, broker-write, schedule, live, autonomous-live, leverage, Level 4, and AI
  broker-authority safety flags.

The packet must not contain raw secrets, raw `.env` values, API keys, Telegram tokens, raw database
URLs, or unredacted privileged provider responses.

## Milestone 34 Result

The Milestone 34 real-paper command refused before broker reads or writes because the required
operator-selected target symbol and order envelope were absent. The sanitized result blockers were:

- `target_symbol_required`;
- `max_qty_required`;
- `max_notional_required`.

No actual paper trading started. No real broker orders were submitted, cancelled, replaced, or
flattened. No protective stop was placed because no entry order was submitted.

## Milestone 35A Result

Milestone 35A is code, tests, docs, and fake/local rehearsal only. It does not run the real first
controlled paper session and does not perform broker writes. The old universal `25.0` USD cap is
replaced by the config-backed first-session ceiling. The future M35 execution path still requires
operator approval, a fresh target/envelope decision, paper endpoint proof, clean reconciliation, a
valid `ExecutionIntent`, and protective-stop enforcement.

## Milestone 35B Result

Milestone 35B used the operator-selected target and envelope:

- target symbol: `AAPL`;
- max quantity: `1`;
- max notional: `350`;
- limit price: `330`;
- estimated notional: `330`.

The gated real read-only preflight was rerun with process-local safety overrides because local
`.env` may still contain unrelated smoke/control flags. The preflight completed against the Alpaca
paper endpoint with account, clock, open-order, and position reads only. It reported clean AAPL
open orders and positions, no broker writes, no actual paper trading, no schedules, no leverage,
and no Level 4 readiness claim.

The real-paper write-capable execution command was not run because the refreshed Alpaca clock
reported the regular session closed. The local sanitized result packet records `market_clock_not_open`
as the M35B NO-GO blocker. No entry order, cancel, replacement, flatten, or protective stop was
submitted.

## Milestone 35C Result

Milestone 35C retried the same operator-selected AAPL envelope during an open Alpaca paper market
session:

- target symbol: `AAPL`;
- max quantity: `1`;
- max notional: `350`;
- limit price: `330`;
- estimated notional: `330`.

The refreshed real-read-only preflight returned GO before execution: paper endpoint proven, account
and clock readable, AAPL open orders clean, AAPL positions clean, no broker writes attempted, no
actual paper trading started, no schedules, no leverage, and no Level 4 readiness claim.

The real-paper command submitted one AAPL paper entry order. The order filled for one share, then
the execution process hit an implementation defect while mapping an Alpaca fill activity payload
that omitted `client_order_id`. This happened after the entry fill and before the normal protective
stop submission path completed.

The run was treated as a safety incident. A recovery protective stop was submitted for the filled
AAPL quantity through the paper endpoint and verified by read-back. The result packet records:

- actual paper trading started;
- real broker writes attempted;
- entry status `filled`;
- fill status `filled`;
- filled quantity `1`;
- protective stop verification `verified`;
- post-run state `protective_stop_open` and `protected_position_open`;
- post-session recommendation `do_not_repeat_until_blockers_cleared`.

The fill-mapping defect was fixed so future fill activity payloads that omit `client_order_id` fall
back to `order_id` and do not crash the evidence path. Repeated controlled paper sessions remain
blocked until the M35C incident and result packet are audited.

## Milestone 35D Post-Session Audit

Milestone 35D is post-session audit and incident review only. It does not start another session,
submit a new entry, submit a new stop, cancel, replace, flatten, activate schedules, enable live
trading, enable autonomous live execution, or add leverage.

The M35C incident root cause was confined to Alpaca fill activity normalization and fill-id lookup:
the account activity fill payload omitted `client_order_id`, and the first-session execution path
queried recent fills before submitting the normal protective stop. Code hardening now handles this
case in two layers:

- fill mapping falls back to `order_id` when `client_order_id` is absent;
- fill-id lookup records malformed fill metadata as a structured incident and continues to the
  protective-stop path using the known entry-order context.

The M35D real-read-only post-session audit used process-local safety overrides and performed only
Alpaca paper reads. The audit verified:

- AAPL paper position quantity remains `1`;
- the expected AAPL protective stop is open and verified;
- open orders consist of the expected protective stop;
- positions consist of the expected AAPL paper position;
- reconciliation is clean enough to hold the protected position for incident review;
- no broker writes occurred in M35D.

The cleanup/hold recommendation is `HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW`. No flatten or
cleanup was performed. Repeated controlled paper sessions remain NO-GO until the post-session audit
is accepted and any later cleanup/flatten decision is explicitly approved.

The sanitized M35D audit packet is:

```text
docs/evidence/first_controlled_paper_session_post_session_audit.json
```

## Milestone 35E Hold Decision

Milestone 35E records the operator decision
`HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW`. It is read-only only: no new session, entry order,
stop order, cancel, replace, flatten, schedule activation, live trading, autonomous live execution,
or leverage is allowed.

The M35E read-only hold verification confirmed the protected hold state:

- AAPL paper position remains open for the filled first-session quantity;
- the expected AAPL protective stop remains open and verified;
- stop quantity matches the protected AAPL position quantity;
- open orders contain no unexpected orders outside the expected protective stop;
- positions contain no unexpected positions outside the expected AAPL paper position;
- reconciliation is consistent with `protected_position_reconciled_for_hold`.

The recorded recommendation is `CONTINUE_HOLD_UNTIL_NEXT_REVIEW`. Cleanup, flatten, cancel, and
stop replacement were not performed in Milestone 35E. Repeated controlled paper sessions remain
NO-GO, frozen validation has not started, and Level 4 remains not ready.

The sanitized M35E hold decision packet is:

```text
docs/evidence/first_controlled_paper_session_hold_decision.json
```

## Milestone 35F Cleanup And Incident Closure Attempt

Milestone 35F changed the operator decision to
`OPERATOR_APPROVED_RISK_REDUCING_CLEANUP_AND_INCIDENT_CLOSURE` with cleanup approval marker
`MILESTONE_35F_RISK_REDUCING_CLEANUP`. It did not start a new session and did not submit a buy or
new-risk entry order.

The real M35F command first verified broker state through Alpaca paper reads:

- AAPL paper position remained open for quantity `1`;
- the expected AAPL protective stop remained open and verified for quantity `1`;
- no unexpected open orders were present outside the expected protective stop;
- no unexpected positions were present outside the expected AAPL position;
- reconciliation remained `protected_position_reconciled_for_hold`.

The approved cleanup path then attempted one risk-reducing AAPL sell for the current long quantity.
Alpaca paper rejected that cleanup sell with sanitized status `failed:invalid_order_request`. No
broker order ID was created for the cleanup sell. Because the AAPL position was not verified flat,
the session-created protective stop was not canceled. No unrelated order was canceled, replaced, or
modified.

Final M35F state:

- AAPL position remains open for quantity `1`;
- the expected AAPL protective stop remains open and verified for quantity `1`;
- open orders consist of the expected protective stop;
- positions consist of the expected AAPL position;
- incident closure status is `protected_hold_continues`;
- repeated controlled paper sessions remain NO-GO;
- M36 recommendation is protected-position monitoring or a separately approved cleanup approach,
  not a second controlled paper session;
- frozen validation has not started;
- Level 4 remains not ready.

The sanitized M35F incident closure packet is:

```text
docs/evidence/first_controlled_paper_session_incident_closure.json
```

## Milestone 36 Protected Position Monitoring

Milestone 36 monitored the protected AAPL paper position and analyzed the M35F cleanup rejection.
It was read-only only: no new session, entry order, buy order, sell order, cancel, replace,
flatten, stop change, schedule activation, live trading, autonomous live execution, provider call,
real alert delivery, or leverage change occurred.

The M36 read-only Alpaca paper monitoring result verified:

- AAPL paper position remains open for quantity `1`;
- the expected AAPL protective stop remains open and verified for quantity `1`;
- the protective stop status is `new`;
- open orders consist of the expected protective stop;
- positions consist of the expected AAPL position;
- reconciliation remains `protected_position_reconciled_for_hold`;
- broker writes performed in M36: `false`.

The M35F cleanup rejection classification is `LIKELY_EXISTING_STOP_BLOCKED_SELL`. Sanitized
evidence shows the M35F cleanup attempted a separate DAY market sell for the current long AAPL
quantity while the session-created GTC sell stop was already open for the same quantity. Alpaca
paper rejected the separate sell with `failed:invalid_order_request` and did not create a cleanup
broker order ID. The likely cause is that the open stop was already reserving the held sellable
quantity, so the additional sell would over-sell the protected long position. The sanitized evidence
is sufficient for a likely classification, but not a definitive broker-rule diagnosis because raw
broker error text is intentionally not recorded.

M36 recommendation:

- continue the protected hold while no separate cleanup approval exists;
- request an operator-approved corrected cleanup milestone if the operator wants closure;
- that future cleanup may need an explicitly approved ordered sequence: verify position and
  session-created stop, cancel only that stop, verify cancellation, submit a risk reducing sell for
  the current long quantity, verify flat state, then verify no stale orders;
- request manual broker review if the stop becomes missing/unverified, the position quantity
  changes unexpectedly, or any unexpected order or position appears.

Repeated controlled paper sessions remain NO-GO. Frozen validation has not started. Level 4 remains
not ready.

The sanitized M36 monitoring packet is:

```text
docs/evidence/protected_position_monitoring_m36.json
```

## Milestone 37 Corrected Cleanup Attempt

Milestone 37 was explicitly approved for corrected AAPL cleanup with operator marker
`OPERATOR_APPROVED_CORRECTED_AAPL_CLEANUP_AND_INCIDENT_CLOSURE` and cleanup approval marker
`MILESTONE_37_CORRECTED_AAPL_CLEANUP`. It did not start a new session, submit a new entry, submit
a buy, trade another symbol, use a live endpoint, activate schedules, call providers, or enable
live/autonomous execution or leverage.

The M37 command first verified the current Alpaca paper state:

- AAPL paper position remains open for quantity `1`;
- the expected AAPL protective stop remains open and verified for quantity `1`;
- open orders consist of the expected protective stop;
- positions consist of the expected AAPL position;
- reconciliation remains `protected_position_reconciled_for_hold`.

The corrected cleanup write sequence did not run because the Alpaca paper clock was not open. M37
therefore did not cancel the protective stop, did not submit the cleanup sell, and did not perform
emergency re-protection. Broker writes performed in M37: `false`.

Final M37 state:

- AAPL remains open for quantity `1`;
- the expected protective stop remains open and verified;
- incident closure status is `protected_hold_continues`;
- repeated controlled paper sessions remain NO-GO;
- next recommendation is `M38_RETRY_CORRECTED_CLEANUP_WHEN_MARKET_OPEN`;
- frozen validation has not started;
- Level 4 remains not ready.

The sanitized M37 corrected cleanup packet is:

```text
docs/evidence/corrected_cleanup_m37.json
```

## Milestone 38 Corrected Cleanup Retry

Milestone 38 retried the corrected AAPL cleanup during an acceptable Alpaca paper market/session
window with operator marker `OPERATOR_APPROVED_M38_CORRECTED_AAPL_CLEANUP_RETRY` and cleanup
approval marker `MILESTONE_38_CORRECTED_AAPL_CLEANUP_RETRY`. It did not start a new session,
submit a new entry, submit a buy, trade another symbol, use a live endpoint, activate schedules,
call providers, or enable live/autonomous execution or leverage.

The M38 command verified pre-cleanup state before any write:

- market/session status was `open_acceptable_for_cleanup`;
- AAPL paper position was open for quantity `1`;
- the expected AAPL protective stop was open and verified for quantity `1`;
- open orders consisted of the expected protective stop;
- positions consisted of the expected AAPL position.

The corrected cleanup sequence then cancelled only the expected session-created AAPL protective
stop, verified cancellation, submitted one risk-reducing AAPL sell for the current long quantity,
and verified the sell as `filled`. Emergency re-protection was not needed.

Final M38 state:

- AAPL position is flat;
- final open orders total is `0`;
- final positions total is `0`;
- final reconciliation is `flat_no_open_position`;
- incident closure status is `closed`;
- broker writes performed in M38: `true`, limited to stop cancellation and risk-reducing AAPL
  cleanup sell;
- repeated controlled paper sessions may be considered in compact M39, but were not started in
  M38;
- frozen validation has not started;
- Level 4 remains not ready.

The sanitized M38 corrected cleanup retry packet is:

```text
docs/evidence/corrected_cleanup_m38.json
```

## Post-Session Policy

If a future retry executes a real paper entry, protective stop verification is mandatory for any
filled quantity. Cleanup/flatten actions must be risk-reducing only, must use the paper endpoint,
and must not create new risk.

After any real broker write, the next allowed step is post-session audit only. Repeated controlled
paper sessions must not begin until the post-session audit is accepted. Frozen validation,
schedules, unattended operation, and Level 4 remain out of scope until separately approved by the
latest spec gates.

## Related Documents

- `docs/pre_paper_operations_gap_audit.md`
- `docs/first_controlled_paper_session_wiring.md`
- `docs/first_controlled_paper_session_real_gate_wiring.md`
- `docs/first_controlled_paper_session_preflight.md`
- `docs/paper_trading_runbook.md`
