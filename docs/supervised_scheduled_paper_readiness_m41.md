# Supervised Scheduled Paper Readiness M41

Milestone 41 is a readiness review only. It does not create Temporal schedules, activate
schedules, start unattended operation, start frozen validation, enable live trading, enable
autonomous live execution, enable leverage, or perform broker writes.

## Current Broker State Under Review

M41 starts from the accepted M40 result:

- AAPL paper position is open for quantity `1`.
- AAPL protective stop is verified for quantity `1`.
- MSFT paper position is open for quantity `1`.
- MSFT protective stop is verified for quantity `1`.
- M40 final reconciliation was `clean_protected_hold`.
- M40 used the normal protective-stop path without recovery handling.
- M40 reported no unresolved incidents and no schedule activation.

M41 must re-verify the current broker state with Alpaca paper read-only calls before any
readiness recommendation is accepted.

The M41 read-only verification accepted this state and produced:

- open orders summary: `expected_aapl_msft_protective_stops_only`;
- positions summary: `expected_aapl_msft_positions_only`;
- reconciliation summary: `clean_protected_holds`;
- readiness recommendation: `M42_SUPERVISED_SCHEDULED_PAPER_RUN_MAY_BE_CONSIDERED`;
- broker writes in M41: `false`;
- schedules created or activated: `false`.

## Schedule Activation Boundary

No schedule activation is allowed in M41.

A future supervised scheduled paper milestone must keep schedules disabled by default and require
an explicit operator approval marker before any schedule is created or activated. The future
approval must specify the run window, target universe, max attempts, max fills, operator monitoring
requirements, cleanup policy, and stop handling policy.

## Required Future Schedule Gates

Every future supervised scheduled paper run must pass these gates before any broker write:

- Paper endpoint confirmed and live endpoint rejected.
- Read-only broker preflight completed in the same run.
- Broker account, clock, open orders, positions, and protective stops reconciled.
- Existing protected holds accounted for before new target selection.
- Duplicate symbol entries refused when a symbol has an open position or open order.
- Unexpected open orders or positions refused.
- Kill switch and manual pause state checked before new risk.
- Target symbol must be operator approved and in the configured allowed universe.
- Order envelope must be explicit, bounded, and within configured quantity and notional caps.
- ExecutionIntent must exist before any order.
- Protective stop plan must exist before any entry.
- Protective stop must be verified after every fill.
- Broker/API ambiguity produces NO-GO.

## Market Session Rules

Market-closed days or unacceptable session windows produce no broker writes.

If a scheduled run starts while the market is closed, it must write a sanitized no-write evidence
packet and exit. It must not queue delayed broker writes, retry unattended, or bypass the configured
entry window.

## Protected-Hold Handling

The scheduler must treat existing protected holds as active exposure. It must not submit duplicate
entries for AAPL or MSFT while those positions remain open. It must verify their protective stops
before any future new-risk attempt and must refuse on a missing or mismatched stop.

## Pause And Kill-Switch Behavior

The kill switch blocks all new-risk execution. Protective and explicitly approved risk reducing
actions may remain available only when documented by the active milestone and execution policy.

Manual pause blocks scheduled new-risk execution until the operator explicitly clears the pause in
a later approved milestone.

## Operator Monitoring

The first supervised scheduled paper run must be monitored by the operator. The operator should
review:

- pre-run read-only broker state;
- selected target and order envelope;
- order acknowledgement and fill state;
- protective stop verification;
- final reconciliation;
- alerts and dashboard read models;
- incident and blocker lists.

## Cleanup And Repair Boundaries

Scheduled paper cleanup must be explicitly bounded. A future scheduled run may not flatten,
cancel, replace, or repair positions unless the approved policy for that milestone allows the
specific action. Cleanup is limited to risk reducing or protective actions for session-created
quantity and must be audited in the run packet.

## Evidence, Reporting, Dashboard, And Alerts

Each future supervised scheduled paper run must generate a sanitized evidence packet with:

- schedule approval marker;
- preflight result;
- broker state before broker writes;
- selected candidate and risk decision;
- ExecutionIntent ID;
- entry order result;
- fill result;
- protective stop result;
- final broker state;
- final reconciliation;
- incidents and blockers;
- confirmation that schedules, live trading, autonomous live execution, leverage, and Level 4
  readiness were not enabled unless a later milestone explicitly approves them.

Dashboard and report views must show paper-only status, open protected holds, stop verification,
pauses, blockers, and latest reconciliation. Real alert delivery remains disabled unless separately
approved.

## Frozen Validation Boundary

Frozen paper validation has not started. It remains blocked until after a supervised scheduled
paper run produces accepted evidence and a later freeze milestone explicitly freezes strategy,
risk, execution, AI prompt/schema, config versions, and evidence collection rules.

## M41 Recommendation Boundary

If M41 verifies both AAPL and MSFT protected holds, finds no unexpected orders or positions, and
accepts the M40 evidence, the next milestone may consider a supervised scheduled paper run. M41
itself does not authorize or activate that run.
