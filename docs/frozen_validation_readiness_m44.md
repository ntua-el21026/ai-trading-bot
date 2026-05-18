# Frozen Validation Readiness M44

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Milestone 44 prepares the repository for M45, but it does not start the 8-week frozen paper
validation clock. It does not activate schedules, enable unattended operation, enable live trading,
enable autonomous live execution, enable leverage, submit real short orders, or claim Level 4
readiness.

## Spec And Configuration

v0.5 supersedes v0.4 for freeze readiness. It introduces paper-only short-side architecture while
keeping shorts disabled by default and keeping M45 validation start long-only.

Validation-start defaults:

- `flat_start_required: true`
- `carry_in_positions_allowed: false`
- `validation_clock_started: false`
- `frozen_validation_enabled: false`
- `frozen_validation_start_allowed: false`
- `shorts.enabled: false`
- `scale_in_policy.enabled_at_validation_start: false`
- `ai_policy.negative_only: true`
- `level4_ready: false`

The full configured universe remains eligible for long candidates. The dormant short-capable subset
is limited to SPY, QQQ, DIA, and IWM for a future separately approved paper-only rehearsal.

## Flat-Start Cleanup

M44 ran the operator-approved cleanup marker
`MILESTONE_44_FLAT_START_CLEANUP_AND_BASELINE`.

Cleanup was limited to AAPL, MSFT, and XLK:

- pre-cleanup state verified open long quantity `1` with verified protective stop quantity `1` for
  each symbol;
- the expected protective stop for each symbol was cancelled before selling that symbol;
- one risk-reducing sell for the current long quantity was submitted for each symbol;
- all cleanup sells filled;
- no emergency re-protection was required;
- final open orders count is `0`;
- final positions count is `0`;
- final reconciliation is `flat_zero_positions_zero_open_orders`.

Flat cleanup evidence: `docs/evidence/flat_start_cleanup_m44.json`.

## Dormant Short Architecture

M44 adds signed-position and side-aware semantics:

- `signed_qty > 0` means long;
- `signed_qty < 0` means short;
- `signed_qty = 0` means flat;
- long entry maps to broker buy;
- long protective stop maps to broker sell stop;
- short entry maps to broker sell;
- short protective stop maps to broker buy stop;
- short cover maps to broker buy.

Existing long positions block short entries in the same symbol, existing short positions block long
entries in the same symbol, and no same-symbol reversal path exists in v0.5. Any future reversal
requires flat reconciliation first.

Shorts remain disabled at validation start. Real short broker writes were not performed in M44.

## Scale-In Stage Gate

Scale-in implementation remains present, but scale-ins are disabled at validation T0. A later stage
may consider scale-ins only after:

- at least 10 clean scheduled runs;
- real broker additive-stop proof;
- no missing-stop incident;
- no duplicate-order incident;
- no unresolved broker/internal mismatch incident.

AI/news output cannot authorize scale-ins.

## AI/News Policy

AI/news is negative-only during the first frozen window. AI may:

- hard-block;
- reduce size;
- explain or report risk.

AI may not:

- positively increase ranking;
- increase size;
- authorize an entry;
- authorize a scale-in;
- authorize a short;
- create, cancel, replace, or modify broker orders.

## Active Frozen Exits

The v0.5 frozen start uses:

- broker protective stop;
- fail-fast exit;
- EMA10 technical exit;
- time stop.

App-level trailing stops are disabled initially. Stop-limit orders are not the primary downside
protection. Same-day re-entry is forbidden after stop, exit, or cleanup.

## M45 Go/No-Go

Current M44 result: M45 is NO-GO.

Ready gates already satisfied:

- v0.5 exists and is the latest source of truth;
- flat broker baseline achieved;
- open orders count is `0`;
- positions count is `0`;
- reconciliation is clean;
- shorts implementation is present and disabled;
- scale-in implementation is present and disabled at validation start;
- AI/news negative-only policy is configured;
- schedules are not activated;
- frozen validation has not started.

Blocking gate:

- `non_iex_primary_signal_data_not_verified`

M45 still requires explicit operator approval. If the non-IEX gate is verified or explicitly waived
by governance, M45 should regenerate readiness evidence immediately before starting the frozen
clock.

Frozen readiness evidence: `docs/evidence/frozen_readiness_m44.json`.

## Milestone 44B Primary Signal Data Gate

M44B adds the dedicated primary-signal data gate evidence path. It does not start M45, activate
schedules, perform broker writes, enable live/autonomous execution, enable leverage, or enable
shorts.

Configured market-data policy:

- primary signal provider: `alpaca`;
- primary signal feed: `sip`;
- non-IEX primary signal data required: `true`;
- IEX-only frozen validation allowed by config: `false`;
- waiver enabled by config: `false`.

M44B verify mode requested Alpaca SIP data with read-only market-data access. The check reached the
data endpoint but returned sanitized `unauthorized`, so non-IEX primary signal data is still not
verified. M45 remains NO-GO.

M44B evidence:

- signal data gate: `docs/evidence/primary_signal_data_gate_m44b.json`;
- refreshed readiness: `docs/evidence/frozen_readiness_m44b.json`.

Remaining ways to clear the gate:

- verify the approved Tiingo EOD primary signal feed with read-only historical completed daily
  bars for the frozen universe;
- enable/confirm Alpaca SIP or another approved non-IEX primary signal feed and rerun verify mode;
- or provide the explicit `MILESTONE_44B_NON_IEX_DATA_GATE_WAIVER` governance marker with a waiver
  reason. Waiver mode makes M45 an operational paper validation with market-data limitations, not a
  clean strategy-performance proof.

## Milestone 44C Tiingo EOD Primary Signal Data Gate

M44C changes the configured M45 primary signal data source from Alpaca SIP to Tiingo EOD historical
completed daily bars. Alpaca remains the paper broker and execution integration, but Alpaca IEX is
not allowed for frozen-validation signal generation.

Configured market-data policy:

- primary signal provider: `tiingo`;
- primary signal feed: `eod`;
- primary signal mode: `historical_completed_daily_bars`;
- Tiingo token environment variable name: `TIINGO_API_KEY`;
- minimum history required per sample symbol: `260` completed bars;
- sample symbols: `SPY`, `QQQ`, `AAPL`, `MSFT`, `XLK`;
- IEX-only frozen validation allowed by config: `false`.

M44C verify mode performs read-only Tiingo EOD requests only. It validates completed daily OHLCV and
adjusted-price fields and sufficient history for SMA200, RS63, ATR, 20D breakout, and volume
filters. It performs no broker writes, schedule activation, or frozen-validation start.

M44C evidence:

- signal data gate: `docs/evidence/primary_signal_data_gate_m44c.json`;
- refreshed readiness: `docs/evidence/frozen_readiness_m44c.json`.

M44C result: the real read-only Tiingo EOD check verified `SPY`, `QQQ`, `AAPL`, `MSFT`, and
`XLK` with sufficient completed daily history and no missing core fields. The refreshed readiness
packet records M45 readiness `GO`, with frozen validation still not started and explicit M45
operator approval still required.
