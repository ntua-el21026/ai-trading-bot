# First Controlled Paper Session Wiring Harness

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

## Purpose

Milestone 29 implements a fake/local wiring harness for the future first controlled paper session.
It prepares the runtime path, manual launch command, typed session/evidence models, refusal
semantics, local ledger evidence boundary, Temporal-compatible service shape, and report/evidence
package generation.

This milestone is fake/local only:

- Actual paper trading has not started.
- No Alpaca paper orders are submitted, cancelled, replaced, or flattened.
- No Alpaca, OpenAI, Marketaux, Alpha Vantage, Telegram, Temporal Cloud, Supabase/Postgres, or
  Vercel calls are made.
- No schedules are activated.
- Live trading remains disabled.
- Autonomous live execution remains disabled.
- Leverage remains disabled and out of scope.

## Relationship To Milestone 28

Milestone 28, documented in `docs/pre_paper_operations_gap_audit.md`, locked the pre-paper gap
audit and the future first controlled paper session protocol. Milestone 29 implements only the
offline rehearsal path for that protocol. It does not authorize real paper broker writes.

Milestone 30, documented in `docs/first_controlled_paper_session_real_gate_wiring.md`, extends
this fake/local rehearsal with a real-session gate boundary. It remains no-real-session and
no-real-broker-write only.

Milestone 31, documented in `docs/first_controlled_paper_session_preflight.md`, adds a read-only
preflight and launch authorization packet. It still does not authorize broker writes or actual
paper session execution.

Milestone 32 uses the same preflight path for real-read-only completion/signoff and sanitized
packet generation. It still remains outside the broker-write execution path.

Milestone 33 retries that read-only preflight after safely clearing the M32 write-smoke blocker for
the retry process only. It remains outside the broker-write execution path.

The harness proves the shape of the future session:

1. Session context and safety snapshot are built with secret values redacted and not inspected.
2. Paper endpoint evidence is represented as fake/local proof only.
3. Live endpoint use is represented as refused proof.
4. Pre-run reconciliation is simulated and must be clean before fake order simulation.
5. Candidate, neutral AI/news fallback, decision, risk check, and ExecutionIntent evidence are
   persisted or represented.
6. Fake entry acknowledgement, fill, protective stop, stop verification, final reconciliation,
   report generation, fake alert summary, and dashboard read-model visibility are exercised.
7. Unsafe scenarios refuse before fake submit or produce a critical local incident.

## Manual Command

Run the safe happy-path rehearsal:

```bash
uv run python scripts/check_first_controlled_paper_session.py --scenario happy_path
```

Run refusal or incident rehearsals:

```bash
uv run python scripts/check_first_controlled_paper_session.py --scenario kill_switch_blocks
uv run python scripts/check_first_controlled_paper_session.py --scenario dirty_reconciliation_blocks
uv run python scripts/check_first_controlled_paper_session.py --scenario missing_stop_incident
```

The script supports only `--mode fake-local`. Any other mode is refused. The script prints a concise
JSON summary and exits `0` only when the fake/local scenario succeeds. Refusal and unsafe incident
scenarios exit non-zero.

Supported scenarios:

- `happy_path`
- `kill_switch_blocks`
- `dirty_reconciliation_blocks`
- `missing_stop_incident`
- `duplicate_intent_blocks`
- `leverage_rejected`
- `short_rejected`
- `missing_operator_approval`
- `live_endpoint_rejected`
- `missing_execution_intent`
- `unsupported_asset_rejected`
- `partial_fill`

## Evidence Package

The harness returns a typed evidence package containing:

- session ID and timestamp;
- fake/local operator approval marker;
- commit hash or unavailable marker;
- spec version;
- config/safety snapshot with secret values redacted and not inspected;
- paper endpoint proof and live endpoint rejection proof;
- no-schedule and no-leverage assertions;
- pre-run reconciliation result;
- candidate, AI/news fallback, decision, risk-check, and ExecutionIntent IDs when reached;
- fake order, client order, fill, protective stop, and stop verification IDs/results when reached;
- post-run reconciliation result;
- final open-order and position status;
- report ID/path;
- dashboard snapshot status;
- fake alert delivery summary;
- incident IDs when any refusal or unsafe condition occurs.

## Safety Refusals

The harness refuses before any fake order simulation when:

- operator approval marker is missing;
- a live endpoint or live mode is requested;
- pre-run reconciliation is dirty;
- ExecutionIntent is missing;
- duplicate active intent is present;
- kill switch blocks new risk;
- side is short;
- asset class is unsupported;
- gross exposure would exceed 1.00x equity or otherwise require leverage.

If a fill is simulated but the protective stop is missing or not verified, the harness records a
critical local incident and returns an unsafe result. It still does not make real broker calls.

## Temporal And Ledger Boundary

The Milestone 29 service is a Temporal-compatible local service boundary. It can be called by a
future workflow milestone, but it does not connect to Temporal Cloud or activate schedules.

Evidence is persisted through the local SQLite ledger used by the existing fake paper dry-run tests.
The harness does not require `DATABASE_URL` and does not connect to managed Supabase/Postgres.

## Remaining Before Real First Session

Before the real first controlled paper session can run, a later milestone must explicitly add and
review:

- real paper broker write gates;
- paper endpoint enforcement against runtime configuration;
- managed ledger persistence for actual session evidence;
- Temporal workflow/activity wiring for real paper operation;
- worker startup/manual launch procedure;
- real alert mode selection;
- cleanup/flatten procedure under explicit gates;
- final operator go/no-go checklist execution.

The next appropriate milestone is real first-session implementation/wiring under explicit gates,
not schedules, unattended operation, frozen validation, or Level 4.

## Level 4 And Leverage Exclusion

Milestone 29 does not make the system Level 4 ready. Level 4 still requires frozen paper evidence
and all spec gates.

Leverage remains out of scope for v0.1 active validation. Gross exposure must remain `<= 1.00x`
equity, margin borrowing must not be intentionally used, and active leverage would require a future
spec change plus a separate validation track.
