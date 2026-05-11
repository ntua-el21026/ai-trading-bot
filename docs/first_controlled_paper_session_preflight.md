# First Controlled Paper Session Preflight

Milestone 31 adds a read-only preflight and launch authorization packet for the future first
controlled Alpaca paper session. It does not run the real session, submit orders, cancel orders,
replace orders, flatten positions, activate schedules, deploy services, enable live trading,
enable autonomous live execution, or add leverage.

Milestone 32 completes the operator-reviewed real-read-only preflight path and final launch packet
signoff behavior. The outcome may be GO if all read-only checks and launch gates pass, or NO-GO
with precise blockers. It remains no-real-session and no-broker-write only.

Milestone 33 retries the real-read-only preflight after diagnosing the Milestone 32 NO-GO blocker
`write_smoke_flag_must_be_disabled`. That blocker was caused by a local `.env` write-smoke flag
for `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE`, not by the read-only preflight code path. Milestone
33 does not edit `.env`; it clears the blocker only for the retry process by explicitly overriding
the write-smoke flag to a non-truthy value while preserving refusal when the flag is `1`.

This document extends:

- `docs/pre_paper_operations_gap_audit.md`
- `docs/first_controlled_paper_session_wiring.md`
- `docs/first_controlled_paper_session_real_gate_wiring.md`
- `docs/paper_trading_runbook.md`

## Scope

The milestone implements:

- typed preflight request and gate models;
- fake/stub read-only broker preflight;
- strictly gated real-read-only Alpaca paper preflight boundary;
- endpoint validation evidence;
- account, clock/session, open-order, position, target-symbol, and exposure summaries;
- cleanup/flatten policy decision;
- evidence persistence decision;
- alert mode decision;
- dashboard/report visibility decision;
- launch authorization packet generation;
- deterministic go/no-go result.

No broker write method is reachable from the preflight path.

## Modes

`fake` mode is local-only and uses stubbed account, clock, open-order, and position summaries. It
requires the fake operator marker `MILESTONE_31_FAKE_PREFLIGHT` for a passing fake preflight.

`real-read-only` mode may call Alpaca paper read-only endpoints only after all explicit gates pass.
It safely loads process environment plus local `.env` and `.env.local` values without printing raw
values. It requires:

- operator marker `MILESTONE_31_READ_ONLY_PREFLIGHT`, `MILESTONE_32_READ_ONLY_PREFLIGHT`, or
  `MILESTONE_33_READ_ONLY_PREFLIGHT`;
- `--confirm-paper-endpoint`;
- `--confirm-no-broker-writes`;
- `--confirm-no-live-trading`;
- `--confirm-no-autonomous-live`;
- `--confirm-no-schedules`;
- `--confirm-no-leverage`;
- existing Alpaca paper read-only smoke environment gates, including the exact paper endpoint.
- no write-smoke flag such as `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1`;
- no first-session execution flag such as `RUN_FIRST_CONTROLLED_PAPER_SESSION=1`.

If any gate fails, the command refuses before broker calls.

## Manual Command

Fake success:

```bash
uv run python scripts/check_first_controlled_paper_session_preflight.py \
  --mode fake \
  --scenario happy_path \
  --operator-approval MILESTONE_31_FAKE_PREFLIGHT
```

Fake live-endpoint refusal:

```bash
uv run python scripts/check_first_controlled_paper_session_preflight.py \
  --mode fake \
  --scenario live_endpoint_rejected \
  --operator-approval MILESTONE_31_FAKE_PREFLIGHT
```

Fake dirty-symbol no-go:

```bash
uv run python scripts/check_first_controlled_paper_session_preflight.py \
  --mode fake \
  --scenario dirty_target_symbol \
  --operator-approval MILESTONE_31_FAKE_PREFLIGHT
```

Milestone 33 real read-only preflight retry, only when local paper credentials and explicit gates
are already present. The leading environment override disables only the write-smoke flag for this
read-only process and does not edit `.env`:

```bash
RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE= \
uv run python scripts/check_first_controlled_paper_session_preflight.py \
  --mode real-read-only \
  --operator-approval MILESTONE_33_READ_ONLY_PREFLIGHT \
  --confirm-paper-endpoint \
  --confirm-no-broker-writes \
  --confirm-no-live-trading \
  --confirm-no-autonomous-live \
  --confirm-no-schedules \
  --confirm-no-leverage \
  --packet-output docs/evidence/first_controlled_paper_session_launch_packet.json
```

That real-read-only path may read only account, clock, open orders, and positions. It must not
submit, cancel, replace, or flatten orders.

If the local `.env` gates or credentials are absent, the command returns NO-GO before broker calls
and still writes a sanitized packet when `--packet-output` is supplied.

If `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1` remains active after process overrides are applied,
the preflight must return NO-GO before broker calls with `write_smoke_flag_must_be_disabled`.

## Launch Authorization Packet

The packet contains:

- authorization packet ID;
- timestamp;
- operator approval marker, if supplied;
- commit hash or unavailable marker;
- latest spec path and version;
- Milestone 28, 29, 30, and runbook references;
- preflight mode;
- broker endpoint mode;
- paper endpoint proof;
- live endpoint rejection proof;
- account status summary;
- clock/session summary;
- open-order summary;
- position summary;
- target-symbol clean/allowed result;
- kill-switch expected state;
- prior incident review marker;
- no-schedule assertion;
- no-live assertion;
- no-autonomous-live assertion;
- no-leverage assertion;
- max gross exposure assertion;
- target symbol allowlist;
- max quantity and notional envelope;
- cleanup/flatten policy decision;
- alert mode decision;
- evidence persistence decision;
- dashboard/report visibility decision;
- required first-session gate checklist;
- go/no-go decision;
- blockers when no-go;
- explicit statement that actual paper trading has not started;
- explicit statement that no real broker writes were attempted.

Secret values are not inspected or printed. The packet records sensitive variable names only as
redacted markers.

The recommended final packet artifact path is:

```text
docs/evidence/first_controlled_paper_session_launch_packet.json
```

The artifact is sanitized JSON containing the packet plus result safety flags.

## Cleanup And Evidence Decisions

The default cleanup policy is verify-only. Future cleanup/flatten may be allowed only for
risk-reducing cleanup, must not create new risk, must preserve paper endpoint enforcement, and
remains out of scope for this milestone.

The default evidence decision is local authorization packet plus future managed DB persistence and
post-session audit. Managed Supabase/Postgres is not required by default and is not connected by
the fake path.

## Go/No-Go

`go` means the selected preflight mode passed its gates and produced an authorization packet. A
fake `go` is not proof that the real Alpaca read-only preflight passed.

`no_go` means one or more blockers must be cleared before the future real first controlled paper
session. Common blockers include missing operator approval, live endpoint detection, paper endpoint
not proven, existing target-symbol open orders, existing target-symbol position, leverage exposure,
missing cleanup policy, or missing evidence persistence decision.

## Remaining Before Real Session

Before the actual first controlled paper session can run:

- real read-only preflight must be completed or explicitly accepted as current enough;
- final launch authorization must be reviewed by the operator;
- real session execution must remain behind the Milestone 30 gates;
- managed evidence persistence must be chosen;
- cleanup/flatten policy must be confirmed;
- post-session audit procedure must be ready.

Schedules, unattended operation, frozen validation, and Level 4 remain out of scope.

## Milestone 32/33 Result Boundary

Milestones 32 and 33 can only complete read-only preflight. They do not authorize actual paper
session execution by themselves. A GO packet means the operator may proceed to a separate explicit
launch milestone. A NO-GO packet lists blockers that must be cleared before launch.

Milestone 33 approval of the launch packet, if achieved, remains launch authorization only. It does
not submit, cancel, replace, flatten, or place protective stops.

## Milestone 33 Result

Milestone 33 diagnosed the Milestone 32 NO-GO as a local `.env` write-smoke flag:
`RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1`. The retry did not edit `.env`; it cleared that blocker
only for the read-only process with `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=`.

The gated real-read-only retry completed account, clock/status, open-order, and position reads
against the Alpaca paper endpoint and regenerated
`docs/evidence/first_controlled_paper_session_launch_packet.json` as GO. The sanitized summary
reported no open orders, no positions, no broker writes, no actual paper trading, no schedules, and
no Level 4 readiness claim.

## Level 4 And Leverage Exclusion

Milestones 31, 32, and 33 do not make the system Level 4 ready. Level 4 still requires frozen
paper evidence and all latest-spec gates.

Leverage remains out of scope. Gross exposure must remain <= 1.00x equity, and margin borrowing
must not be intentionally used.

## Milestone 34 Link

The Milestone 34 execution boundary is documented in
`docs/first_controlled_paper_session_execution.md`. It consumes the Milestone 33 GO launch packet
but still refuses before broker writes unless the operator supplies the separate real-session write
gates plus a target symbol and order envelope. The recorded Milestone 34 result remained NO-GO for
missing target and envelope inputs.

Milestone 35A extends the pre-execution command model so a future launch packet can be generated
for an operator-selected target symbol, and the execution command can validate explicit max
quantity, max notional, and limit price locally. The preflight remains read-only and no-broker-write
only.

Milestone 35B reran the real-read-only preflight for operator-selected `AAPL` with process-local
safety overrides. The packet remained GO for read-only launch prerequisites, but the refreshed
clock showed the regular session closed, so the write-capable execution command was not run and the
session remained NO-GO before broker writes.

Milestone 35C reran the real-read-only preflight during an open market session. It returned GO for
the AAPL launch prerequisites before the real-paper command was attempted. Post-execution read-only
state is no longer clean because the session created an AAPL paper position protected by an open
stop; repeated controlled sessions must wait for post-session audit.
