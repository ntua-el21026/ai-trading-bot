# First Controlled Paper Session Real-Gate Wiring

Milestone 30 wires the real first controlled paper-session path behind explicit gates. It does
not run the real session, submit Alpaca paper orders, call external providers, activate schedules,
deploy services, enable live trading, enable autonomous live execution, or add leverage.

This document extends the Milestone 28 protocol in
`docs/pre_paper_operations_gap_audit.md` and the Milestone 29 fake/local harness in
`docs/first_controlled_paper_session_wiring.md`.

Milestone 31 adds the read-only preflight and launch authorization packet in
`docs/first_controlled_paper_session_preflight.md`. It keeps the real-gated execution path
deferred and performs no broker writes.

Milestone 32 completes or fails closed the real-read-only preflight/signoff path and can generate a
sanitized launch packet artifact. The real-gated execution path remains deferred.

Milestone 33 retries the real-read-only preflight after clearing the M32 write-smoke blocker for
the read-only process only. The real-gated execution path remains deferred and no broker writes are
authorized.

## What Is Wired

- A typed real-session gate configuration and preflight evidence model in `packages/paper/real_gate.py`.
- A real-gated service boundary that can later sit in front of the broker, reconciliation, risk,
  ledger, reporting, alerting, and dashboard/read-model path.
- A default refusal path for missing operator approval or missing real-write gates.
- A fake/stub mode that delegates to the Milestone 29 fake/local harness after all real-session
  gates are represented as satisfied.
- A manual CLI at `scripts/run_first_controlled_paper_session.py`.
- Tests proving real-gated refusals occur before any broker-write simulation and that fake/stub
  mode performs no external calls or real broker writes.

## Safety Boundary

Default behavior is refusal. Running the script with no arguments exits non-zero and records that:

- actual paper trading has not started;
- real broker orders were not submitted, cancelled, replaced, or flattened;
- real broker writes were not attempted;
- external calls were not attempted;
- schedules were not activated;
- live trading remains disabled;
- autonomous live execution remains disabled;
- leverage remains disabled;
- AI has no broker write authority.

Milestone 30 includes no code path that Codex should run to submit real orders. The future
real-session path remains deferred even if all real gates are represented as passing.

## Modes

`real-gated` is the default mode. It represents the future real-session path and refuses unless
explicit gates are supplied. In Milestone 30, even a fully gated `real-gated` run stops with
`real_session_execution_deferred_milestone_30`.

`fake` mode uses stubbed preflight evidence and the Milestone 29 local harness. It is the only
mode expected to return success in this milestone.

## Required Real-Session Gates

A future real first controlled paper session must prove all of these before broker writes:

- operator approval marker;
- expected spec version and recorded commit marker;
- explicit allow-real-Alpaca-paper-writes gate;
- paper endpoint proof;
- live endpoint rejection;
- no live trading;
- no autonomous live execution;
- no schedules active or expected;
- no leverage and gross exposure <= 1.00x equity;
- target symbol allowlist;
- first-session quantity and notional caps;
- supported long-only side;
- supported equity/ETF asset class;
- supported limit order type;
- clean pre-run reconciliation;
- kill switch permits new risk;
- no unresolved blocking incident;
- no duplicate active intent;
- valid `ExecutionIntent`;
- idempotency key;
- protective stop plan;
- cleanup/flatten policy decision;
- evidence persistence target;
- unambiguous broker state;
- AI has no broker write authority.

Any missing or failed gate refuses before broker write logic.

## Manual Script

Default refusal:

```bash
uv run python scripts/run_first_controlled_paper_session.py
```

Fake/stub success path:

```bash
uv run python scripts/run_first_controlled_paper_session.py \
  --mode fake \
  --scenario happy_path \
  --operator-approval MILESTONE_30_FAKE_ONLY
```

Fake/stub refusal path:

```bash
uv run python scripts/run_first_controlled_paper_session.py \
  --mode fake \
  --scenario live_endpoint_rejected \
  --operator-approval MILESTONE_30_FAKE_ONLY
```

The script prints structured JSON with redaction-safe identifiers and safety flags. It does not
read or print secrets and does not call Alpaca, OpenAI, Marketaux, Alpha Vantage, Telegram,
Temporal Cloud, Supabase/Postgres, or Vercel.

## Evidence Extension

The Milestone 30 result includes real-session readiness fields:

- real write gates evaluated;
- real write gates passed or failed;
- broker adapter mode;
- broker endpoint mode;
- preflight evidence ID;
- reconciliation evidence ID;
- protective stop plan ID;
- cleanup policy ID;
- refusal reason IDs;
- alert mode;
- ledger persistence mode;
- external calls attempted false;
- real broker writes attempted false;
- real broker orders submitted false;
- AI broker write authority false.

In fake/stub success mode, the result also includes the Milestone 29 first-session evidence package.

## Supported Scenarios

The real-gate harness supports happy path, missing operator approval, missing real-write gate,
live endpoint rejection, paper endpoint not proven, live trading enabled, autonomous live execution
enabled, schedules active, leverage rejected, gross exposure rejected, short rejected, unsupported
asset rejected, unsupported order type rejected, dirty reconciliation, active kill switch, blocking
incident, duplicate intent, missing `ExecutionIntent`, missing idempotency key, missing protective
stop plan, missing cleanup policy, missing evidence persistence, ambiguous broker state, missing
stop incident, and AI broker-write request rejection.

All scenarios are fake/stubbed in this milestone.

## Remaining Before Real First Session

Before the actual controlled Alpaca paper session can run, a later milestone must explicitly
approve and verify:

- real read-only preflight against Alpaca paper under operator control;
- managed ledger persistence target and evidence retention;
- exact real broker adapter injection point;
- operator launch procedure and evidence capture;
- final cleanup/flatten policy for real paper state;
- post-session audit workflow.

That future milestone must still avoid live endpoints, schedules, unattended operation, frozen
validation claims, and Level 4 claims unless separately approved by the spec gates.

## Level 4 And Leverage Exclusion

This milestone does not make the system Level 4 ready. Level 4 still requires frozen paper evidence
and all spec gates.

Leverage remains out of scope for v0.1 active validation. Gross exposure must remain <= 1.00x
equity, and margin borrowing must not be intentionally used.

## Milestone 34 Link

Milestone 34 builds on this real-gated boundary in
`docs/first_controlled_paper_session_execution.md`. The real-paper path now requires a GO launch
packet, first-session write gates, an operator-selected target symbol, an explicit tiny order
envelope, clean pre-run reconciliation, a valid `ExecutionIntent`, and a protective stop plan before
any broker write can occur.
