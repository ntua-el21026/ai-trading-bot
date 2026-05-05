# Architecture

This document describes the current foundation, data/backtest, Temporal skeleton, deterministic strategy, risk/execution-core, broker-reconciliation, AI/news intelligence, dashboard/control-plane, validation/testing, and paper-operations documentation boundary architecture.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Current repository implementation is limited to Milestone 10 scaffolding: project metadata, safe configuration defaults, typed config loading, structured logging helpers, offline data contracts, deterministic feature utilities, universe filters, explicit-signal backtest utilities, Temporal workflow/worker skeletons, deterministic strategy/regime/signal helpers, passive risk/execution-core contracts, broker adapter contracts, normalized broker models, pure reconciliation comparison, bounded AI/news intelligence contracts, dashboard/control-plane read/action contracts, validation/testing contracts, and paper trading runbook documentation.

## Target Shape

- Temporal orchestrates execution-critical workflows.
- Postgres or Supabase Postgres is the durable business and audit ledger.
- Deterministic strategy, risk, execution, and reconciliation code owns trading authority.
- AI is bounded to shortlist news/catalyst/risk intelligence and has no broker write path.
- Vercel is dashboard/control-plane only.

## Current Milestone Status

- Data models exist for adjusted daily OHLCV bars, quotes, asset metadata, raw provider payload metadata, feature rows, and universe membership.
- Raw provider payload hashing helpers and repository protocol contracts exist.
- Provider interfaces exist as protocols only and make no live network calls.
- Feature utilities calculate daily returns, SMA, EMA, ATR14, ATR percent, volume averages, volume ratios, highs, dollar volume, and RS63 inputs.
- Universe filters support live and research universe scaffolding with point-in-time optimism warnings.
- Backtesting utilities support explicit fixture signals, basic mark-to-market equity, and validation metrics.
- Temporal SDK dependency, typed client bootstrap, task queue mapping, workflow skeletons, placeholder activity contracts, signal names, query names, and retry-policy contracts exist.
- Regime classification implements deterministic `RISK_ON`, `CAUTION`, and `RISK_OFF` states from SPY SMA/realized-volatility rules.
- Strategy candidate evaluation implements long-only trend, breakout, volume, RS63, ATR percent, universe, price, ADV, earnings, held-symbol, and duplicate-intent gates.
- Exit helpers calculate stop levels and exit trigger reason codes only; they do not submit or modify orders.
- Risk checks evaluate new-risk eligibility from config and caller-supplied system, session, reconciliation, Temporal, exposure, loss, cash, duplicate-intent, and kill-switch state.
- Position sizing implements the configured risk-per-trade and max-position-size formula with non-increasing multipliers.
- Execution-core contracts define `ExecutionIntent`, deterministic client order ID roots, duplicate-intent helpers, passive order lifecycle transitions, and structured rejection models.
- Broker contracts define account, order, fill, position, protective-stop, REST fallback, and stream event models.
- The Alpaca paper adapter is a dependency-free safety skeleton. It refuses live-mode configuration and raises until an explicitly configured paper client is added in a later milestone.
- Alpaca `trade_updates` fixture payloads can be mapped into internal broker stream events without credentials or websocket connections.
- Reconciliation contracts compare broker snapshots against passive internal ledger snapshots and classify mismatches into structured incidents with pause-new-risk or flatten-if-safe recommendations.
- AI/news contracts define deterministic-shortlist-only news requests, provider protocols, article normalization/deduplication, strict AI output schemas, neutral fallbacks, deterministic AI event scoring, hard-block classification, and persistence payload contracts.
- The AI prompt template is versioned under `packages/ai/prompts/` and explicitly forbids broker actions, order creation/modification, stop changes, strategy mutation, risk-limit changes, and full-universe scanning.
- AI/news Temporal activity boundaries are placeholders only and perform no external provider, AI, database, broker, or network calls.
- Control-plane contracts define read-only dashboard views and auditable safe control requests.
- `apps/api/app/control_plane.py` maps safe backend control requests to existing Temporal signal names. It does not call Temporal, broker adapters, AI/news providers, or databases yet.
- `apps/dashboard/` is a minimal dashboard scaffold with safe public environment selection only. No frontend framework or deployment files are added.
- Validation contracts under `packages/validation/` define the spec-required backtest split, benchmark,
  fee/slippage, ablation, Monte Carlo placeholder, failure-simulation, and paper dry-run check
  assumptions. They are deterministic contracts only and do not run live or paper broker orders.
- `docs/paper_trading_runbook.md` and related checklist/report templates define paper operations,
  monitoring, incident response, frozen paper acceptance criteria, and paper-to-Level-4 handoff
  gates. They are documentation only and do not activate paper or live trading.
- No production API service is implemented.
- No production worker deployment is implemented.
- No production dashboard UI is implemented.
- No broker-executable order submission is implemented.
- No real Alpaca SDK/client integration is implemented.
- No database schema or migration is implemented.
- No real AI/news provider integration is implemented.
- No real Temporal query/signal backend integration is implemented.
- Temporal schedules are not activated.
- Earnings blackout evaluation requires caller-supplied earnings dates and trading calendars. Missing earnings data is treated as unknown and blocks entries conservatively.

Future milestones must keep implementation aligned with the latest spec before adding behavior.
