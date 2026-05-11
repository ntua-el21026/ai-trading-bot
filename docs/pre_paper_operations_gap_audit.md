# Pre-Paper Operations Gap Audit

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

## 1. Purpose

Milestone 28 locks the pre-paper operations gap audit and the protocol for a future first
controlled paper session.

This milestone is documentation, audit, and protocol only:

- Actual paper trading has not started.
- This milestone does not start paper trading.
- This milestone does not perform broker writes.
- This milestone does not call Alpaca, OpenAI, Marketaux, Alpha Vantage, Telegram, Temporal Cloud,
  Supabase/Postgres, or Vercel.
- This milestone does not activate schedules.
- This milestone does not implement runtime execution code.
- This milestone does not enable live trading or autonomous live execution.

Milestone 28 is a spec-aligned clarification of the latest spec and existing runbooks. It does not
change trading behavior, risk policy, execution policy, autonomy level, broker authority, or
deployment architecture.

Milestone 29 implements the fake/local first-session wiring harness described in
`docs/first_controlled_paper_session_wiring.md`. That harness is offline only and still does not
start actual paper trading.

Milestone 30 wires the real first-session gate boundary described in
`docs/first_controlled_paper_session_real_gate_wiring.md`. That path still refuses by default,
submits no real broker orders, and does not run the actual controlled paper session.

Milestone 31 adds the read-only preflight and launch authorization packet documented in
`docs/first_controlled_paper_session_preflight.md`. It is still no-real-session and
no-broker-write only.

Milestone 32 extends that same preflight document with real-read-only completion/signoff behavior
and a sanitized launch packet artifact. It still cannot submit, cancel, replace, or flatten orders.

Milestone 33 retries the operator-reviewed real-read-only preflight after isolating the M32
write-smoke blocker to a local `.env` safety flag. The retry remains read-only, no-session,
no-broker-write, and no-schedule only.

Milestone 35B attempted the operator-selected AAPL first-session launch only through the allowed
read-only gates. It remained NO-GO because the refreshed Alpaca clock reported the regular session
closed. No write-capable real-paper command was run, and no broker writes occurred.

Milestone 35C retried during an open market session. One AAPL paper entry order was submitted and
filled, then a fill-mapping defect interrupted the normal stop path. A recovery protective stop was
submitted and verified. The run is a safety incident and repeated controlled paper sessions are
blocked pending post-session audit.

Milestone 35D performed that post-session audit with read-only broker verification only. It verified
the AAPL paper position remains open and protected by the expected open stop, hardened the fill
metadata handling path, recommended `HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW`, and kept repeated
controlled paper sessions NO-GO. No broker writes, cleanup, flatten, schedule activation, live
trading, autonomous live execution, or leverage changes occurred in M35D.

Milestone 35E records the operator decision to hold the protected AAPL paper position until the
next review. It verified the position and stop through read-only broker calls only, performed no
broker writes or cleanup actions, and kept repeated controlled paper sessions blocked.

Milestone 35F attempted operator-approved risk-reducing incident closure. The command verified the
protected AAPL state, attempted one cleanup sell for the current long quantity, and Alpaca paper
rejected that sell with sanitized status `failed:invalid_order_request`. The protective stop was not
canceled because AAPL was not flat. The incident remains open, AAPL remains protected, and repeated
controlled paper sessions remain blocked.

## 2. Source-Of-Truth Files Reviewed

Source-of-truth hierarchy confirmed:

1. Latest versioned `SPEC*.md` file.
2. `AGENTS.md`.
3. Other docs explicitly referenced by the latest spec.
4. Existing implementation.
5. Current user prompt.
6. Engineering judgment.

Primary governance, spec, docs, config, and implementation areas reviewed:

- `AGENTS.md`
- `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`
- `README.md`
- `.env.example`
- `pyproject.toml`
- `uv.lock`
- `package.json`
- `package-lock.json`
- `vercel.json`
- `.vercelignore`
- `config/`
- `db/migrations/`
- `docs/ai_intelligence.md`
- `docs/alerting.md`
- `docs/architecture.md`
- `docs/broker_integration.md`
- `docs/dashboard_control_plane.md`
- `docs/database_audit_ledger.md`
- `docs/database_runtime.md`
- `docs/execution_policy.md`
- `docs/level4_micro_live_readiness.md`
- `docs/operations_runbook.md`
- `docs/paper_dry_run_orchestration.md`
- `docs/paper_trading_runbook.md`
- `docs/reporting.md`
- `docs/risk_policy.md`
- `docs/temporal_workflows.md`
- `docs/validation_plan.md`
- `docs/project_structure/project_struct.txt`
- `docs/project_analytics/project_analytics.txt`
- `apps/api/`
- `apps/dashboard/`
- `apps/workers/`
- `packages/ai/`
- `packages/alerting/`
- `packages/backtesting/`
- `packages/broker/`
- `packages/control_plane/`
- `packages/core/`
- `packages/data/`
- `packages/execution/`
- `packages/ledger/`
- `packages/paper/`
- `packages/reconciliation/`
- `packages/reporting/`
- `packages/risk/`
- `packages/strategy/`
- `packages/validation/`
- `scripts/`
- `tests/unit/`
- `tests/integration/`
- `tests/temporal/`

## 3. Current State Summary

The repository remains ready to proceed to a future first controlled paper session implementation
and wiring milestone according to Milestone 27 readiness aggregation.

Current state:

- Milestone 21B controlled Alpaca paper order lifecycle smoke completed successfully and ended
  clean/flat for the target symbol.
- Milestone 22 news/provider/OpenAI smoke evidence exists.
- Milestone 23 Telegram alert smoke evidence exists.
- Milestone 24 Temporal Cloud dev smoke evidence exists.
- Milestone 25 dashboard/control-plane runtime smoke evidence exists.
- Milestone 26 static Vercel dashboard preview evidence exists.
- Milestone 27 controlled paper operations readiness aggregation exists and reports readiness for a
  future first controlled paper session.
- Actual controlled paper trading session is pending.
- Frozen paper evidence is absent.
- Live trading remains disabled.
- Autonomous live execution remains disabled.
- Level 4 micro-live is not ready.

Evidence boundary distinctions:

- Readiness evidence means prior components, gates, docs, and local-safe checks indicate the repo can
  proceed to a future first controlled paper session milestone. It is not trading evidence.
- Controlled paper lifecycle smoke evidence means one operator-gated broker lifecycle smoke exercised
  a tiny paper order, protective stop, cleanup, and final clean/flat state. It is not a strategy-led
  paper session.
- First actual controlled paper session means one manually approved, tightly bounded session through
  the future paper operation path, with real evidence persisted and audited.
- Repeated controlled paper sessions mean multiple operator-approved sessions after a post-session
  audit confirms the first session was clean enough to repeat.
- Scheduled paper sessions mean Temporal schedules are explicitly reviewed, created, and activated
  for paper operation after repeated controlled sessions justify the change.
- Unattended scheduled paper operation means paper sessions may run without session-by-session
  manual launch under documented schedule, alerting, incident, and operator-monitoring gates.
- Frozen paper validation period means strategy, risk, execution, AI prompt/schema, and config
  versions are frozen and paper evidence is collected against the latest spec acceptance criteria.
- Level 4 micro-live readiness means frozen paper evidence and every spec gate support a separate
  live go/no-go review. It is not satisfied now.

## 4. Evidence Already Available

Existing evidence is readiness and smoke evidence only:

- Managed DB readiness: migration/schema/runtime helpers and opt-in managed repository CRUD
  validation paths are documented and tested; default tests remain local/fake.
- Alpaca paper read-only smoke: account, open-order, position, and clock/status reads passed against
  the paper endpoint through explicit gates.
- Controlled Alpaca paper order lifecycle smoke: Milestone 21B completed one tiny gated lifecycle
  smoke, including acknowledgement/fill handling, protective stop verification, cleanup, and final
  clean/flat state.
- AI/news provider/OpenAI smoke: Marketaux/Alpha Vantage provider-first and OpenAI structured
  analysis support exists with explicit smoke gates and offline defaults.
- Telegram smoke: Telegram delivery harness and prior smoke evidence exist behind explicit gates;
  default alerting uses fake/fail-closed behavior.
- Temporal Cloud dev smoke: a harmless dev-namespace smoke path exists behind explicit gates and
  creates no schedules.
- Dashboard/control-plane smoke: server-side read-only snapshot and safe control validation exists
  with fake/default dispatch.
- Vercel static dashboard preview: static read-only dashboard preview evidence exists; it is not an
  execution worker, production control plane, or paper evidence.
- Paper operations readiness harness: Milestone 27 aggregates existing evidence and local-safe
  checks while explicitly preserving `paper_operations_started=false`, frozen paper evidence absent,
  and `level4_ready=false`.

## 5. Remaining Gaps Before First Controlled Paper Session

The items below must be closed, satisfied, or explicitly deferred before or during the future first
actual controlled paper session.

| Gap | Current assessment | Classification |
| --- | --- | --- |
| Managed ledger runtime wiring for actual session evidence | Local/fake repositories and explicit Postgres/Supabase helpers exist; the actual session still needs managed runtime persistence evidence under an explicit gate. | Blocking before first session |
| Temporal runtime workflow wiring for paper operation | Workflow skeletons and activity boundaries exist; actual paper operation workflow wiring is not implemented. | Blocking before first session |
| Worker deployment/startup model | Local worker bootstrap exists; first-session worker start model and task queues must be explicitly defined and verified. | Blocking before first session |
| Explicit first-session launch command or workflow path | No approved first-session launch command or workflow invocation exists yet. | Blocking before first session |
| Broker write gate semantics for first session | Smoke-specific write gates exist; first-session gates must be separate, explicit, session-scoped, and non-live. | Blocking before first session |
| Paper endpoint enforcement | Existing Alpaca paper adapter and smoke harness refuse live endpoints; first-session path must prove the same before writes. | Blocking before first session |
| Live endpoint rejection | Existing smoke/readiness paths reject live endpoints; future session must record live endpoint was not touched. | Blocking before first session |
| No leverage | Config disables margin/leverage; future session must record gross exposure remains `<= 1.00x` equity and no margin borrowing is intentionally used. | Blocking before first session |
| No schedules active | Schedule seeding remains dry-run only; future first session must stay manual and prove schedules are not active. | Blocking before first session |
| Pre-run broker reconciliation | Reconciliation contracts exist; future session must run and persist clean pre-run reconciliation before new risk. | Required during first session |
| Post-run broker reconciliation | Reconciliation contracts exist; future session must run and persist final broker/internal reconciliation. | Post-session audit item |
| Protective stop verification | Fake and smoke evidence exists; future session must verify stop for any filled quantity and persist timing/status. | Required during first session |
| Cleanup/flatten procedure | Smoke cleanup exists; first-session cleanup/flatten policy must be explicitly chosen before launch and applied only if applicable. | Blocking before first session |
| Incident handling | Incident contracts and runbooks exist; first-session incidents must be persisted, reviewed, and block repetition if unresolved. | Required during first session |
| Telegram alert mode | Telegram smoke evidence exists; first-session must choose fake delivery or real delivery before launch and record the choice. | Blocking before first session |
| Dashboard read-model visibility | Dashboard read models exist; first-session must prove relevant status is visible from persisted session evidence. | Post-session audit item |
| Report generation | Local report generation exists; first-session must generate and persist a final session report from real session records. | Post-session audit item |
| Session ID / commit hash / config snapshot evidence | Required evidence format is not yet produced by an actual paper session. | Blocking before first session |
| Repeated controlled paper sessions | Not allowed until the first session is audited. | Future scheduled/autonomous paper item |
| Scheduled paper sessions | Not allowed for the first session. | Future scheduled/autonomous paper item |
| Unattended scheduled paper operation | Not allowed until repeated controlled sessions and schedule gates are accepted. | Future scheduled/autonomous paper item |
| Frozen paper validation | Not started; no frozen validation clock exists. | Future Level 4 item |
| Level 4 micro-live readiness | Not ready; requires frozen paper evidence and all latest-spec gates. | Future Level 4 item |

## 6. First Controlled Paper Session Protocol

The future first controlled paper session must follow this protocol. A later implementation/wiring
milestone must provide the concrete launch command or Temporal workflow path before this protocol
can be executed.

Required operating boundaries:

- Explicit operator approval is required before launch.
- Paper endpoint only.
- Live endpoint forbidden.
- No schedules.
- Manual launch only.
- One session only.
- One small controlled position or a tightly limited trade envelope.
- Long-only.
- No leverage and no margin borrowing.
- No shorts.
- No options, futures, crypto, leveraged ETFs, inverse ETFs, or prediction markets.
- Deterministic strategy, risk, and execution authority only.
- AI/news may be used only as bounded risk/catalyst intelligence over deterministic shortlist
  candidates.
- AI has no broker credentials, broker API path, order authority, stop authority, strategy mutation
  authority, risk mutation authority, or kill-switch override authority.

Required pre-order gates:

- Latest spec version recorded.
- Session ID assigned.
- Operator approval marker recorded.
- Commit hash recorded.
- Config and safety flag snapshot recorded with secrets redacted.
- Local `.env` may exist but must remain untracked and must not be printed.
- Paper endpoint proof recorded.
- Live endpoint rejection recorded.
- Market/session status checked.
- Existing broker open orders checked.
- Existing broker positions checked.
- Target symbol clean or explicitly allowed.
- Kill switch allows new risk.
- Broker reconciliation is clean before new-risk execution.
- Valid deterministic decision exists.
- Passed deterministic risk check exists.
- Valid `ExecutionIntent` exists before any paper order.
- Idempotency key and `client_order_id` root exist.

Required in-order behavior:

- Entry order submitted only after all gates pass.
- New-risk entry must be a `DAY` limit or approved marketable-limit paper order according to the
  latest execution policy.
- No market order for new-risk entry.
- No extended-hours entry.
- Order acknowledgement persisted.
- Fill or partial-fill state persisted.
- Protective stop submitted for filled quantity only.
- Protective stop verification required through stream and/or REST fallback evidence.
- Partial-fill stop quantity must match filled quantity.
- Ambiguous broker state pauses the session and triggers reconciliation.
- Incidents must be persisted and reviewed.
- Telegram alerts are emitted or faked according to the preselected alert mode.
- Dashboard visibility must be checked against persisted read models.

Required closeout:

- Final broker/internal reconciliation required.
- Final open orders checked.
- Final positions checked.
- Protective stop status checked.
- Cleanup/flatten policy checked if applicable.
- Final report required.
- Alert/report summary checked if enabled.
- Post-session audit required before repeated sessions.

## 7. Go/No-Go Checklist

### A. Pre-Run Go/No-Go

- [ ] Correct branch and commit recorded.
- [ ] Latest spec identified as `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`, unless a newer
  versioned spec exists.
- [ ] `.env` present locally if needed, untracked, and not printed.
- [ ] Secrets not printed.
- [ ] Database reachable under explicit gate.
- [ ] Temporal Cloud reachable under explicit gate, if the approved first-session path uses it.
- [ ] Alpaca paper read reachable under explicit gate.
- [ ] Alpaca endpoint is paper.
- [ ] Live endpoint rejected.
- [ ] Account status valid.
- [ ] Market/session status checked.
- [ ] Existing open orders checked.
- [ ] Existing positions checked.
- [ ] Target symbol clean or explicitly allowed.
- [ ] Kill switch allows new risk.
- [ ] Prior incidents reviewed.
- [ ] Real alert delivery mode explicitly chosen: fake, real Telegram, or disabled-fail-closed.
- [ ] Dashboard status available.
- [ ] Config snapshot recorded with secrets redacted.
- [ ] No schedules active; schedules are not expected for the first session.
- [ ] Paper endpoint, no-live, no-leverage, long-only, and no-unsupported-asset flags verified.

### B. In-Run Requirements

- [ ] Candidate generated and persisted.
- [ ] AI/news output persisted, or neutral fallback persisted.
- [ ] Deterministic decision persisted.
- [ ] Risk check persisted.
- [ ] `ExecutionIntent` persisted.
- [ ] Broker reconciliation clean before order.
- [ ] Entry order submitted only after all gates.
- [ ] Order acknowledgement persisted.
- [ ] Fill or partial-fill handling persisted.
- [ ] Protective stop submitted for filled quantity.
- [ ] Protective stop verified.
- [ ] Alerts emitted or faked according to config.
- [ ] Incidents persisted if any.

### C. Post-Run Requirements

- [ ] Final broker/internal reconciliation completed and persisted.
- [ ] Open orders checked.
- [ ] Positions checked.
- [ ] Protective stop status checked.
- [ ] Cleanup/flatten policy checked if applicable.
- [ ] Report generated and persisted.
- [ ] Dashboard read model checked.
- [ ] Telegram/report summary checked if enabled.
- [ ] No live endpoint touched.
- [ ] No secrets printed.
- [ ] No schedule activated.
- [ ] Post-session audit completed before repeated sessions.

## 8. Required Evidence Package

The future first controlled paper session must produce an evidence package containing:

- Session ID.
- Timestamp.
- Operator approval marker.
- Commit hash.
- Spec version.
- Config and safety flag snapshot with secrets redacted.
- Broker endpoint proof as paper-only.
- Live endpoint rejection proof.
- Pre-run reconciliation result.
- Candidate IDs.
- AI/news output IDs if applicable.
- Decision IDs.
- Risk-check IDs.
- `ExecutionIntent` IDs.
- Broker order IDs and `client_order_id` values.
- Fill IDs.
- Protective stop order ID.
- Protective stop verification result.
- Incident IDs if any.
- Post-run reconciliation result.
- Final open orders status.
- Final positions status.
- Report ID or report path.
- Dashboard snapshot.
- Alert delivery or fake-delivery summary.

The evidence package must not contain raw secrets, raw `.env` values, API keys, Telegram tokens,
chat IDs, raw privileged provider responses, or unredacted database URLs.

## 9. Autonomy Staging

The approved staging path remains:

1. First manual controlled paper session.
2. Post-session audit.
3. Repeated controlled paper sessions.
4. Scheduled paper sessions.
5. Unattended scheduled paper operation.
6. Frozen paper validation period.
7. Level 4 go/no-go review.

The frozen validation clock must not start until:

- the system is stable;
- paper execution is proven;
- schedules and autonomy level are explicitly chosen;
- strategy, risk, execution, AI prompt/schema, and config rules are frozen;
- the frozen-period evidence capture format is approved.

## 10. Level 4 Exclusion

Milestone 28 does not make the system Level 4 ready.

Level 4 micro-live remains no-go until the latest spec gates are satisfied, including frozen paper
evidence, protective stop success, broker/internal mismatch limits, AI schema validity, absence of
Sev-1 control incidents, absence of missing-stop incidents, absence of duplicate-order incidents,
credential separation, alerting evidence, dashboard/control-plane evidence, kill-switch evidence,
and an explicit Level 4 go/no-go review.

No live trading or autonomous live execution may be enabled by this milestone.

## 11. Leverage Exclusion

Leverage remains out of scope for v0.1 active validation:

- Gross exposure must remain `<= 1.00x` equity.
- Margin borrowing must not be intentionally used.
- `allow_margin` remains `false`.
- Shorting remains disabled.
- Optional future leverage-aware accounting may be added later as a passive accounting extension
  only if approved.
- Active leverage requires a future spec change and a separate validation track.

## 12. Final Conclusion

Milestone 28 is documentation, audit, and protocol only.

No blocking spec contradiction was found during this audit. The repository remains aligned with
`docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md` and remains ready to proceed to a future
implementation/wiring milestone for the first controlled paper session.

At Milestone 28, actual paper trading had not started. Current M35C evidence records that actual
paper trading has now started through one controlled AAPL paper entry and verified protective stop.

Frozen paper validation still has not started.

Level 4 micro-live remains not ready.

## Milestone 34 Execution Boundary

Milestone 34 is documented in `docs/first_controlled_paper_session_execution.md`. It adds the
explicitly gated first Alpaca paper execution path and a sanitized post-session result packet, but
the repository run refused before broker writes because no operator-selected target symbol or order
envelope was supplied. No live trading, autonomous live execution, schedules, leverage, or Level 4
readiness were enabled.

Milestone 35A updates that execution boundary to correct the first-session symbol/envelope model.
The path no longer uses a universal `25.0` USD notional cap or derives limit price from max
notional for real-paper mode. A future real execution requires explicit target symbol, max quantity,
max notional, and limit price, with local validation before broker access.

Milestone 35E records the operator decision to hold the protected AAPL paper position until the
next review. The verification path is read-only only, confirms the expected open position and
protective stop when broker state permits, performs no cleanup/flatten/cancel/replace actions, and
keeps repeated controlled paper sessions blocked.

Milestone 35F attempted risk-reducing cleanup and incident closure. The cleanup sell was rejected
by Alpaca paper before a broker order ID was created, final state remained protected hold, and M36
must remain a protected-position monitoring or separately approved cleanup milestone.
