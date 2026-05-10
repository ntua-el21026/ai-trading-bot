# First Controlled Paper Session Execution

Milestone 34 adds the explicitly gated execution boundary for the first controlled Alpaca paper
session. This is the first milestone where real Alpaca paper broker writes may occur, but only
after every launch-packet, endpoint, reconciliation, risk, `ExecutionIntent`, protective-stop, and
cleanup-policy gate passes.

This milestone still refuses safely when the operator has not supplied a target symbol and order
envelope. The Milestone 34 repository run recorded a NO-GO result because no operator-selected
target symbol, maximum quantity, or maximum notional was provided.

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

The target symbol must be approved by the configured universe, long-only, and clean of existing
target-symbol open orders and positions before execution. The first-session envelope is intentionally
small; the default policy requires one share and a limit DAY entry order.

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

## Evidence

Milestone 34 writes a sanitized result packet to:

```text
docs/evidence/first_controlled_paper_session_result.json
```

The packet records:

- launch packet reference;
- operator approval marker;
- target symbol and order envelope if provided;
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
