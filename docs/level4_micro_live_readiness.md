# Level 4 Micro-Live Readiness

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 22 adds provider-first news retrieval, OpenAI structured-analysis boundaries,
disabled-by-default OpenAI web fallback, and autonomous AI feedback/calibration safety downgrades
while preserving the readiness boundary. It does not enable live trading, autonomous live
execution, live credentials, real Alpaca calls in default tests, real alert delivery, actual paper
trading operations, live orders, production schedules, expanded Level 4, or Level 5.

## Purpose And Scope

Level 4 micro-live is the first live autonomous target. It allows live orders only after explicit
configuration, very small capital caps, deterministic risk checks, valid execution intents,
broker reconciliation, active kill switch, protective stops, logging, alerts, and complete evidence
review.

This document defines the evidence required before a future go/no-go decision. It is not a go-live
authorization.

## Non-Goals

- Do not enable live trading.
- Do not enable autonomous live execution.
- Do not add paper or live credentials.
- Do not call live Alpaca, AI/news providers, unmanaged databases, or production services. Opt-in
  read-only Alpaca paper smoke checks remain connectivity validation only. The paper
  order-lifecycle smoke harness may call paper write endpoints only in a separate operator-gated
  run, and refuses by default.
- Do not submit broker orders.
- Do not change risk limits, autonomy level, execution policy, stop policy, kill-switch behavior,
  allowed assets, strategy defaults, or AI authority boundaries.
- Do not promote to expanded Level 4 or Level 5.
- Do not claim Level 4 readiness until every gate below has evidence.

## Current Readiness Status

Current conclusion: **Not ready for Level 4 micro-live**.

Known status:

- Milestones 00-22 are complete as local/offline code, opt-in validation scaffolding, local
  Temporal SDK test-server/replay coverage, opt-in Alpaca paper read-only smoke tooling, and a
  default-refusing gated paper order-lifecycle smoke harness, plus provider/OpenAI/calibration
  boundaries with offline default tests.
- Paper trading operations have not started.
- Frozen paper evidence is not available.
- Database/audit-ledger foundation and local/fake Temporal ledger activities exist; managed
  Postgres/Supabase migration/check helpers and opt-in repository CRUD validation exist.
- Paper-only Alpaca adapter, fake broker activity boundaries, passing opt-in read-only paper smoke
  evidence, and a gated order-lifecycle smoke harness exist. The latest 21B write-smoke attempt
  reached gated paper preflight and refused before writes because the Alpaca paper clock was closed;
  retained real paper order lifecycle write evidence is still absent.
- Fake/local paper dry-run orchestration exists and produces local ledger/report/dashboard evidence,
  but it is not actual paper trading evidence.
- Local Temporal SDK test-server/replay coverage exists; production Temporal query/signal backend
  integration is deferred.
- Provider-first Marketaux/Alpha Vantage and OpenAI structured-analysis support exists with opt-in
  smoke gates; real provider/OpenAI smoke evidence is required if not separately run and retained.
- Real dashboard deployment is deferred.
- Alerting contracts and fake adapters exist; real alert delivery evidence is absent.
- Live trading remains disabled.
- Autonomous live execution remains disabled.

Hard blockers:

- No production managed database activity wiring evidence.
- No production Temporal backend/live worker evidence.
- No retained real Alpaca paper order lifecycle write evidence or paper execution evidence.
- No controlled real paper operations evidence.
- No retained real provider/OpenAI smoke evidence unless separately gated and run.
- No production Temporal query/signal backend evidence.
- No real alert delivery evidence.
- No frozen paper run evidence.
- No Level 4 go/no-go report.

## Acceptance Gates Before Level 4 Micro-Live

These gates are required by the latest spec. They are not current achievements.

- At least 8 weeks frozen paper.
- At least 30 closed paper trades or 2 quarters of forward paper, whichever comes later.
- OOS Profit Factor >= 1.10.
- OOS Sharpe >= 0.75 or OOS Sortino >= 1.00.
- Max drawdown <= 10%.
- 100% protective stop placement success.
- Broker/internal mismatch rate < 0.1%.
- AI valid-schema rate >= 99%.
- Zero Sev-1 control incidents in the last 20 sessions.
- Zero missing-stop incidents.
- Zero duplicate-order incidents.

## Current Config Review

### System And Execution Safety

| Setting | Current value | Required readiness posture | Status |
| --- | --- | --- | --- |
| `system.environment` | `paper` | Paper until approved live milestone | OK |
| `system.dry_run` | `true` | Dry-run by default | OK |
| `system.live_trading_enabled` | `false` | Disabled until approved go-live | OK |
| `system.autonomous_execution_enabled` | `false` | Disabled until approved go-live | OK |
| `system.autonomy_level` | `2` | Not Level 4 live | OK |
| `system.kill_switch_enabled` | `true` | Enabled | OK |
| `system.require_broker_reconciliation` | `true` | Required | OK |
| `execution.allow_live_orders` | `false` | Disabled | OK |
| `execution.autonomous_execution_enabled` | `false` | Disabled | OK |
| `execution.require_execution_intent` | `true` | Required | OK |
| `execution.require_passed_risk_check` | `true` | Required | OK |
| `execution.require_broker_reconciliation_before_order` | `true` | Required | OK |
| `execution.require_protective_stop` | `true` | Required | OK |

### Level 4 Micro-Live Risk Limits

`config/risk.yaml` matches the latest-spec `risk_level_4_micro_live` values:

| Limit | Current value | Latest-spec value | Status |
| --- | --- | --- | --- |
| `max_gross_exposure_pct` | `0.20` | `0.20` | Match |
| `max_deployable_capital_pct` | `0.20` | `0.20` | Match |
| `max_position_size_pct` | `0.04` | `0.04` | Match |
| `max_risk_per_trade_pct` | `0.0035` | `0.0035` | Match |
| `max_open_positions` | `5` | `5` | Match |
| `max_sector_exposure_pct` | `0.10` | `0.10` | Match |
| `min_cash_buffer_pct` | `0.75` | `0.75` | Match |
| `max_daily_loss_pct` | `0.01` | `0.01` | Match |
| `max_weekly_loss_pct` | `0.025` | `0.025` | Match |
| `max_monthly_loss_pct` | `0.05` | `0.05` | Match |
| `allow_margin` | `false` | `false` | Match |
| `allow_shorting` | `false` | `false` | Match |
| `allow_options` | `false` | `false` | Match |
| `allow_leveraged_etfs` | `false` | `false` | Match |
| `require_protective_stop` | `true` | `true` | Match |

The config also keeps futures, crypto, and prediction markets disabled.

### Universe And AI Safety

- `config/universe.yaml` allows only approved equities/ETFs and disables options, shorting,
  leveraged ETFs, inverse ETFs, futures, crypto, and prediction markets.
- `config/ai.yaml` keeps `allow_ai_to_create_orders: false`.
- `config/ai.yaml` keeps `allow_ai_to_modify_strategy: false`.
- `config/ai.yaml` keeps `allow_ai_to_modify_risk_limits: false`.
- `config/ai.yaml` keeps `analyze_full_universe: false`.
- `config/ai.yaml` keeps `analyze_deterministic_shortlist_only: true`.
- `config/ai.yaml` keeps Marketaux as primary news provider and Alpha Vantage as fallback.
- `config/ai.yaml` keeps OpenAI web fallback disabled by default.
- `config/ai.yaml` permits AI feedback/calibration only for safety downgrade/reporting behavior.

## Credential Separation And Secret Manager Requirements

Credential readiness requires evidence for:

- Alpaca paper credentials are separate from Alpaca live credentials.
- Paper and live environment variable sets are separate.
- `.env.example` contains variable names only.
- No `.env` file is committed.
- Broker credentials are never exposed to frontend code.
- AI/news provider keys are never exposed to frontend code.
- Temporal API keys and privileged database URLs are never exposed to frontend code.
- Production secrets are stored in a secret manager.
- Live credentials require explicit operator approval after a complete go/no-go report.

Variable names only:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_BASE_URL`
- `RUN_ALPACA_PAPER_SMOKE`
- `ALPACA_PAPER_SMOKE_CONFIRM`
- `RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE`
- `ALPACA_PAPER_ORDER_LIFECYCLE_CONFIRM`
- `ALPACA_PAPER_ORDER_SMOKE_SYMBOL`
- `ALPACA_PAPER_ORDER_SMOKE_MAX_QTY`
- `ALPACA_PAPER_ORDER_SMOKE_MAX_NOTIONAL_USD`
- `ALPACA_PAPER_ORDER_SMOKE_TIMEOUT_SECONDS`
- `DATABASE_URL`
- `RUN_MANAGED_DB_TESTS`
- `LEDGER_MIGRATION_CONFIRM`
- `TEMPORAL_ADDRESS`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_API_KEY`
- `AI_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_ESCALATION_MODEL`
- `OPENAI_FALLBACK_MODEL`
- `MARKETAUX_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `NEWS_PROVIDER_PRIMARY`
- `NEWS_PROVIDER_FALLBACK`
- `NEWS_MARKETAUX_DAILY_REQUEST_LIMIT`
- `NEWS_ALPHA_VANTAGE_DAILY_REQUEST_LIMIT`
- `NEWS_ENABLE_OPENAI_WEB_FALLBACK`
- `RUN_NEWS_PROVIDER_SMOKE`
- `NEWS_PROVIDER_SMOKE_CONFIRM`
- `RUN_OPENAI_MODEL_LIST_SMOKE`
- `OPENAI_MODEL_LIST_CONFIRM`
- `RUN_OPENAI_AI_SMOKE`
- `OPENAI_AI_SMOKE_CONFIRM`
- `RUN_OPENAI_WEB_FALLBACK_SMOKE`
- `OPENAI_WEB_FALLBACK_CONFIRM`
- `ANTHROPIC_API_KEY`
- `POLYGON_API_KEY`
- `FINNHUB_API_KEY`
- `FMP_API_KEY`
- `TIINGO_API_KEY`
- `TAVILY_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `LIVE_TRADING_ENABLED`
- `AUTONOMOUS_EXECUTION_ENABLED`
- `AUTONOMY_LEVEL`
- `KILL_SWITCH_ENABLED`

## Required Control And Re-Arm Evidence

Before Level 4 micro-live, dry-run or controlled-paper evidence must demonstrate:

- `manual_kill_switch` transitions to a new-risk-blocking state.
- `manual_pause_new_risk` blocks new entries.
- `manual_resume_after_review` requires documented manual review.
- `force_reconciliation` routes through backend/Temporal boundaries.
- `force_report` routes through backend/Temporal boundaries.
- `acknowledge_incident` is auditable.
- Pause-new-risk preserves or verifies protective exits.
- Risk-reducing exits remain allowed where permitted by kill-switch state.
- Manual re-arm checklist is completed before resuming.
- Alert delivery works for orders, fills, exits, kill switch, reconciliation mismatches, missing
  stops, worker failure, and provider outage.

Current status: contract tests exist for signal names and safe control models, local Temporal SDK
signal/query tests cover selected workflows, and fake alert routing is fixture-tested. Production
Temporal signal/query backend integration and real alert delivery evidence are pending.

## Broker And Reconciliation Evidence

Required evidence:

- Pre-execution reconciliation before every new-risk order.
- Active-window reconciliation every 30 seconds while orders are open.
- EOD reconciliation after market close.
- BOD reconciliation before next market open.
- Alpaca `trade_updates` stream plus REST fallback.
- Broker position without internal position detection.
- Internal position without broker position detection.
- Missing protective stop detection.
- Duplicate open entry order detection.
- Unexpected short position detection.
- Account equity mismatch detection above threshold.
- Order fill not recorded internally detection.
- Temporal workflow state inconsistent with DB/order state detection.

Current status: deterministic reconciliation contracts and fixture tests exist, local ledger
schema/repository/activity foundations exist, opt-in managed DB CRUD validation is available, and
local Temporal SDK signal/query tests cover the reconciliation workflow. Read-only paper smoke
evidence validates account/open-order/position/clock reads through explicit gates. The Milestone 21A
order-lifecycle harness can produce sanitized smoke evidence only when separately write-gated; by
default it refuses before broker write calls. The latest 21B attempt refused safely before writes
because the paper clock was closed. Real broker stream, retained order-lifecycle write evidence,
REST fallback during active orders, production managed database activity wiring, and Temporal/DB
consistency evidence are pending.

## Protective Stop Evidence

Required evidence:

- Stop placement success rate is 100%.
- Warning incident is created after 5 seconds without confirmation.
- Critical incident is created and new entries pause after 30 seconds without confirmation.
- Flatten-if-safe recommendation or approved behavior occurs after 60 seconds without confirmation.
- Partial-fill stop quantity matches filled quantity.
- No naked live positions exist.
- Unresolved missing-stop cases require manual review.

Current status: missing-stop policy contracts and tests exist, and the gated smoke harness can
exercise filled-quantity stop submission with a fake client. Real stop placement, broker
verification, and paper evidence are pending unless separately write-gated and retained.

## Duplicate Order And Idempotency Evidence

Required evidence:

- Every new-risk order uses a valid `ExecutionIntent`.
- Every broker order uses deterministic `client_order_id`.
- Broker lookup by `client_order_id` occurs before retry.
- Internal execution-intent lookup occurs before retry.
- Ambiguous state pauses workflow and triggers reconciliation.
- Duplicate active intent is rejected.
- Zero duplicate-order incidents during frozen paper.

Current status: passive idempotency helpers, duplicate-intent checks, lifecycle contracts, and local
ledger uniqueness constraints exist. Real broker and managed database idempotency evidence is
pending.

## AI Schema Evidence

Required evidence:

- AI analyzes deterministic shortlist candidates only.
- AI has no broker credentials or broker API access.
- AI output is strict schema-validated JSON.
- Invalid JSON falls back neutral.
- Schema violations fall back neutral.
- Provider outages fall back neutral.
- AI valid-schema rate is >= 99% during frozen paper.
- Multiple invalid payloads in the same run trigger the configured incident path.

Current status: schema, parser, fallback, scoring, and fixture tests exist. Real provider evidence is
pending.

## Dashboard And Control-Plane Evidence

Required evidence:

- Dashboard displays system state, workflows, execution intents, orders, positions, incidents,
  reconciliation, kill switch, signals, AI outputs, reports, and risk status.
- Frontend does not reference broker, AI/news, Temporal, or privileged database secrets.
- Browser/client code does not call Temporal, broker APIs, or AI/news providers directly.
- Control actions route through backend/Temporal boundaries.
- No order-entry or natural-language trading control exists.
- Operator can use kill switch, pause new risk, force reconciliation, force report, acknowledge
  incidents, and resume after review through approved server-side paths.

Current status: read models, ledger-backed dashboard snapshots, safe control contracts, fixture
dispatch, frontend env guardrails, and local Temporal SDK signal/query tests exist. Real dashboard
deployment and production Temporal backend evidence are pending.

## Slippage And Fill-Quality Evidence

Required evidence:

- Paper fill and slippage diagnostics are captured and reviewed.
- Paper trading is not represented as proof of live fill quality.
- Live/micro-live has not started in this repository.
- Before expanded Level 4, median live slippage must not be worse than model by more than 10 bps.
- Live fill quality, market impact, queue position, price improvement, and live slippage require
  micro-live evidence after Level 4 starts.

## Final Go/No-Go Rule

Level 4 micro-live remains **no-go** until:

- every acceptance gate has evidence;
- every hard blocker is resolved;
- required tests/checks pass on the candidate commit;
- live and paper credentials are separated in a secret manager;
- alerting is verified;
- rollback and kill-switch paths are verified;
- operator approvals are recorded in `docs/templates/level4_micro_live_go_no_go_template.md` or an
  equivalent signed record.

Expanded Level 4 and Level 5 remain out of scope until after stable Level 4 evidence is available.
