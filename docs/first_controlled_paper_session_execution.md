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
