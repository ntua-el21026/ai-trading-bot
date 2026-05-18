# Milestone 45 Frozen Paper Validation Start

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md`.

M45 is the freeze/start milestone for the official 8-week long+short+scale-in frozen paper
validation. It may start only after the explicit operator marker
`MILESTONE_45_START_8_WEEK_LONG_SHORT_SCALEIN_FROZEN_PAPER_VALIDATION` and all final gates pass.

## M45 Result

M45 started successfully.

- validation status: `active`;
- validation start timestamp UTC: `2026-05-18T16:51:09.038248Z`;
- validation target end timestamp UTC: `2026-07-13T16:51:09.038248Z`;
- validation window: 56 days;
- schedule state: `active_local_paper_validation_registry`;
- schedule ID/name: `frozen-paper-validation-v0.6-long-short-scalein`;
- current broker baseline at start: zero open orders, zero positions, clean flat reconciliation;
- broker writes during M45 start: none;
- Temporal Cloud schedule created: false;
- blockers: none.

## Start Scope

M45 starts the validation clock and registers the paper-only validation schedule locally. It does
not submit any immediate broker order. Future broker writes may occur only inside scheduled paper
workflow runs after that run's Tiingo data, strategy, risk, broker, reconciliation, shortability,
scale-in, and protective-stop gates pass.

The current implementation records a local paper-validation schedule registry entry in the M45
evidence packet. It does not create a Temporal Cloud schedule. Temporal schedule activation remains
deferred until a separately gated implementation exists.

Milestone 47 resolved the M46 `local_registry_has_no_active_runner` blocker by activating the
paper-only local runner `frozen-validation-runner-v0.6-local`. The M45 validation clock and frozen
hashes were not reset. The runner does not force trades; it wakes on frozen schedule points and
executes only read-only gate checks unless a natural due cycle later produces a valid frozen-policy
paper execution path.

Milestone 47B adds deployment-ready off-PC runner packaging for a cloud VM/VPS. The M45 validation
clock remains unchanged. Off-PC operation is GO only after a durable runner heartbeat or Temporal
schedule plus worker registration is confirmed.

## Frozen Policy

- active spec: `v0.6`;
- duration: 56 days;
- mode: paper;
- broker: Alpaca paper;
- primary signal data: Tiingo EOD historical completed daily bars;
- live trading: disabled;
- autonomous live execution: disabled;
- leverage: disabled;
- live shorting: disabled;
- paper shorts: enabled;
- long scale-ins: enabled;
- short scale-ins: disabled;
- AI/news: negative-only risk overlay;
- forced trades: disabled;
- flat start: required and verified;
- Level 4: not ready.

Full long universe:

- `SPY`, `QQQ`, `DIA`, `IWM`, `XLK`, `XLF`, `XLE`, `XLV`, `AAPL`, `MSFT`, `NVDA`,
  `AMZN`, `META`, `GOOGL`.

Short universe:

- `SPY`, `QQQ`, `DIA`, `IWM`.

## Final Gates

M45 refuses unless:

- v0.6 is the latest spec;
- M44C Tiingo EOD gate is verified and `GO`;
- M44D short proof is accepted;
- M44E scale-in proof is accepted;
- current Alpaca paper read-only baseline is flat with zero open orders and zero positions;
- no unresolved critical incidents or blockers remain;
- paper shorts are enabled and live shorting is disabled;
- long scale-ins are enabled and short scale-ins are disabled;
- AI/news remains negative-only;
- risk, execution, reporting, intervention, and incident policies are frozen;
- the operator approval marker is present.

## Operator Interventions

Allowed during the window:

- pause/kill switch;
- manual review;
- stop repair;
- risk-reducing cleanup;
- disable schedule after incident;
- restart only after documented incident review;
- rotate credentials if compromised;
- fix non-strategy operational bugs with evidence.

Forbidden unless the validation is restarted or marked contaminated:

- optimize strategy parameters;
- change universe;
- change risk caps;
- enable live trading;
- enable leverage;
- enable live shorting;
- change short universe;
- change scale-in caps;
- switch primary data provider;
- change signal rules;
- manually force trades;
- manually override rejected trades;
- let AI authorize trades;
- claim Level 4 readiness.

## Evidence

M45 writes `docs/evidence/frozen_paper_validation_start_m45.json`.

The packet records start result, validation status, start/end timestamps, current flat broker
baseline, Tiingo gate status, short readiness, scale-in readiness, frozen policy hashes, local
schedule registry status, operator intervention policy, incident rules, reporting requirements, and
blockers.

Secrets, raw broker account identifiers, API keys, database URLs, Telegram tokens, provider tokens,
and Temporal credentials must not be included.
