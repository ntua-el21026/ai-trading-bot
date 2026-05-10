# First Controlled Paper Session Preflight

Milestone 31 adds a read-only preflight and launch authorization packet for the future first
controlled Alpaca paper session. It does not run the real session, submit orders, cancel orders,
replace orders, flatten positions, activate schedules, deploy services, enable live trading,
enable autonomous live execution, or add leverage.

Milestone 32 completes the operator-reviewed real-read-only preflight path and final launch packet
signoff behavior. The outcome may be GO if all read-only checks and launch gates pass, or NO-GO
with precise blockers. It remains no-real-session and no-broker-write only.

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

- operator marker `MILESTONE_31_READ_ONLY_PREFLIGHT` or `MILESTONE_32_READ_ONLY_PREFLIGHT`;
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

Real read-only preflight, only when local paper credentials and explicit gates are already present:

```bash
uv run python scripts/check_first_controlled_paper_session_preflight.py \
  --mode real-read-only \
  --operator-approval MILESTONE_32_READ_ONLY_PREFLIGHT \
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

## Milestone 32 Result Boundary

Milestone 32 can only complete read-only preflight. It does not authorize actual paper session
execution by itself. A GO packet means the operator may proceed to a separate explicit launch
milestone. A NO-GO packet lists blockers that must be cleared before launch.

## Level 4 And Leverage Exclusion

Milestones 31 and 32 do not make the system Level 4 ready. Level 4 still requires frozen paper
evidence and all latest-spec gates.

Leverage remains out of scope. Gross exposure must remain <= 1.00x equity, and margin borrowing
must not be intentionally used.
