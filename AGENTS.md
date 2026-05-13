# AGENTS.md

## Project Context

This repository contains an autonomous AI-assisted trading-bot system.

The current intended product is a **Temporal-orchestrated, broker-reconciled, long-only US equities/ETF swing-trading bot** with:

- deterministic strategy, risk, execution, and reconciliation logic;
- AI used only as a bounded news/catalyst/risk-intelligence layer;
- autonomous execution through deterministic gates;
- paper-first validation;
- conservative Level 4 micro-live deployment before any expanded autonomy;
- complete auditability through database logs, Temporal workflow history, raw data persistence, and reports.

The latest specification file is the source of truth for product behavior, system architecture, constraints, and acceptance criteria.

At the time of writing, the latest expected spec is:

```text
Autonomous_AI_Trading_Bot_SPEC_v0.4.md
```

If a newer spec exists, use the newest versioned spec file instead.

---

## Core Rule

Do not treat this repository as a generic trading-bot project.

Always treat it as a **spec-governed autonomous trading system** where correctness, safety, determinism, auditability, validation, and risk control are more important than speed of implementation or feature breadth.

---

## Source of Truth Priority

When deciding what to implement, follow this priority order:

1. The latest versioned `SPEC*.md` file.
2. Other project documentation explicitly referenced by the latest spec.
3. Existing implementation in the repository.
4. The current user prompt.
5. Reasonable engineering judgment.

If these conflict, do **not** silently choose one.

Instead:

1. identify the conflict;
2. explain the options;
3. ask for permission or inspection;
4. wait for the user's answer before implementing.

---

## Repository Structure May Evolve

The repository structure, module boundaries, filenames, package layout, configuration files, database schema, and documentation organization may change over time.

Do not assume that the current structure is final.

Before making non-trivial structural changes:

1. inspect the current repository;
2. compare the current structure against the latest spec;
3. explain the proposed change;
4. identify files affected;
5. ask for approval if the change deviates from the latest spec or affects architecture.

Minor additions that directly follow the latest spec may be implemented without asking, unless the user requested planning only.

---

## Spec Alignment Requirement

Every implementation change must be checked against the latest spec.

Before modifying code, configuration, migrations, workflows, execution logic, risk logic, AI logic, or deployment files, determine whether the requested change is:

```text
A. already allowed by the latest spec;
B. a clarification of the latest spec;
C. a deviation from the latest spec;
D. an unspecified new behavior;
E. a contradiction of the latest spec.
```

Rules:

- If A: proceed normally.
- If B: proceed, and update documentation if useful.
- If C, D, or E: do not implement immediately.
- For C, D, or E, ask for permission and/or inspection first.
- Wait for the user's answer before making the implementation change.

---

## Spec Update Rule

If the user approves a deviation, new behavior, architecture change, risk-parameter change, execution-policy change, AI-policy change, workflow change, database-schema change, or deployment-policy change, the latest spec must also be updated.

The code and the spec must not diverge.

When a change is approved, update the latest versioned spec file or create a new versioned spec file, depending on the size and importance of the change.

Use this policy:

```text
Small clarification:
    update the latest spec file in place if the user explicitly allows it.

Material behavioral/architectural change:
    create a new versioned spec file, e.g. SPEC_v0.4.md.

Risk/execution/autonomy/security change:
    create a new versioned spec file.

Trading strategy/risk parameter change:
    update the spec and config together.

Temporary experiment:
    document it as an experiment and keep it out of production defaults unless approved.
```

If the user asks for code only but the code changes behavior relative to the spec, stop and ask whether the spec should be updated first.

---

## Approval Gate for Spec Deviations

If a requested task would deviate from the latest spec, respond with a short blocking note like:

```text
This deviates from the latest spec because: <reason>.

Proposed options:
1. Keep the spec unchanged and implement only the compliant part.
2. Update the spec first, then implement.
3. Treat this as an experimental branch/config disabled by default.

Please confirm which option you want.
```

Do not implement the deviation until the user confirms.

---

## Prohibited Silent Changes

Do not silently change any of the following:

- autonomy level;
- live-trading enablement;
- broker execution behavior;
- risk limits;
- position sizing;
- stop-loss policy;
- trailing-stop policy;
- kill-switch behavior;
- allowed asset classes;
- margin/leverage permissions;
- short-selling permissions;
- options/futures/crypto/prediction-market support;
- AI authority boundaries;
- Temporal workflow semantics;
- order idempotency behavior;
- broker reconciliation behavior;
- database ledger semantics;
- validation acceptance criteria;
- production deployment architecture.

Any change to these requires explicit approval and a corresponding spec update.

---

## Trading Safety Invariants

The following invariants must hold unless the user explicitly updates the spec:

```text
AI has no broker write permissions.
AI cannot directly submit trades.
AI cannot modify live orders.
AI cannot override risk limits.
AI cannot increase position size above deterministic caps.
AI cannot disable kill switches.
AI cannot mutate live strategy rules.
```

```text
Execution authority belongs to the deterministic execution pipeline.
Every live order requires a valid ExecutionIntent.
Every new-risk order requires passed risk checks.
Every live position requires a protective stop.
Broker state must be reconciled before new-risk execution.
Kill switch blocks new risk.
Protective/risk-reducing exits may remain allowed.
```

```text
v0.1 is long-only.
v0.1 uses no leverage.
v0.1 does not short.
v0.1 does not trade options, futures, crypto, or prediction markets.
v0.1 does not perform high-frequency trading or scalping.
```

---

## Temporal Requirements

Temporal is part of the v0.1 architecture.

Use Temporal for execution-critical orchestration, including:

- scheduled workflows;
- order lifecycle workflows;
- fill monitoring;
- stop placement;
- partial-fill handling;
- reconciliation workflows;
- kill-switch workflows;
- reporting workflows.

Respect Temporal workflow determinism.

Workflow code should orchestrate deterministic workflow state and call activities.

Activity code should perform side effects, including:

- broker API calls;
- database writes;
- AI API calls;
- news/data API calls;
- alert sending;
- reading wall-clock time;
- random or non-deterministic operations.

Do not call external APIs directly from workflow code.

Do not place broker orders outside the approved Temporal execution workflow path.

---

## AI Layer Rules

The AI layer is bounded and advisory.

Allowed AI responsibilities:

- summarize candidate-specific news;
- extract catalysts;
- classify risk events;
- generate structured JSON;
- provide explanations;
- produce daily and weekly reports;
- suggest hypotheses for manual review.

Forbidden AI responsibilities:

- scanning the full universe for direct trade ideas in v0.1;
- direct broker access;
- order submission;
- order modification;
- risk-limit changes;
- live strategy mutation;
- changing stop levels except through deterministic approved logic;
- generating unstructured outputs for execution-critical paths.

AI outputs must be schema-validated.

Invalid AI output must fall back to neutral behavior unless the latest spec says otherwise.

AI failure alone should not trigger a global kill switch unless repeated failures or missing required checks create a system-level safety issue defined by the spec.

---

## Risk Engine Rules

Risk logic is deterministic and non-bypassable.

Before any new-risk order, enforce:

- environment validity;
- live/paper mode correctness;
- autonomous execution flag;
- approved symbol;
- approved asset class;
- fresh market data;
- broker reconciliation;
- kill-switch state;
- max gross exposure;
- max deployable capital;
- max position size;
- max risk per trade;
- max open positions;
- max sector exposure;
- min cash buffer;
- daily/weekly/monthly loss limits;
- protective stop availability;
- duplicate-intent prevention;
- Temporal workflow consistency.

If any critical risk check fails, reject the order, log the rejection, and notify according to severity.

---

## Execution Rules

Execution must be idempotent, auditable, and broker-reconciled.

Required concepts:

- `ExecutionIntent`;
- `client_order_id`;
- pre-submit reconciliation;
- post-submit acknowledgement;
- fill monitoring;
- protective stop placement;
- stop verification through stream and REST fallback;
- partial-fill handling;
- unfilled-order expiry;
- order/fill/position persistence;
- slippage/fill diagnostics;
- incident creation on ambiguity.

Do not create naked live positions intentionally.

If a position exists without a confirmed protective stop beyond the configured threshold, follow the latest spec's stop-failure policy.

---

## Data and Validation Rules

Backtests must not be treated as proof of profitability.

Paper trading must not be treated as proof of live profitability.

Paper trading validates:

- orchestration;
- broker integration;
- order lifecycle;
- stop placement;
- reconciliation;
- logging;
- kill switches;
- reporting;
- AI schema behavior.

Paper trading does not fully validate:

- live fill quality;
- market impact;
- queue position;
- price improvement;
- live slippage;
- live profitability.

Preserve raw data and audit records wherever required by the spec.

If point-in-time universe data is unavailable, label stock-universe backtests as optimistic.

---

## Documentation Update Expectations

When implementing meaningful changes, update relevant documentation.

Possible documentation files include:

- latest versioned spec file;
- `README.md`;
- `docs/architecture.md`;
- `docs/temporal_workflows.md`;
- `docs/risk_policy.md`;
- `docs/execution_policy.md`;
- `docs/validation_plan.md`;
- `docs/operations_runbook.md`;
- `.env.example`;
- config files under `config/`.

Do not update documentation with claims that are not implemented or validated.

Do not claim profitability.

---

## Coding Standards

Use clean, typed, production-oriented code.

Preferred backend stack:

```text
Python 3.12+
FastAPI
Temporal Python SDK
Postgres / Supabase
SQLAlchemy or SQLModel
Pydantic
pandas / NumPy
```

Guidelines:

- prefer explicit types;
- prefer pure functions for strategy/risk calculations;
- isolate side effects in adapters/activities;
- keep broker-specific logic inside broker adapters;
- keep Temporal workflow code deterministic;
- keep AI prompts and schemas versioned;
- keep config-driven parameters;
- avoid hidden constants;
- avoid global mutable state;
- avoid silent exception swallowing;
- log structured events;
- write tests for risk, execution, reconciliation, and workflow failure paths.

---

## Testing Requirements

For non-trivial changes, add or update tests.

Important test categories:

- unit tests for feature calculations;
- unit tests for regime logic;
- unit tests for strategy signals;
- unit tests for risk checks;
- unit tests for position sizing;
- unit tests for AI schema parsing;
- unit tests for execution-intent construction;
- Temporal workflow replay/determinism tests;
- integration tests for broker paper adapter;
- integration tests for reconciliation;
- failure tests for stop placement, duplicate orders, stale data, invalid AI output, and kill-switch transitions.

Do not reduce or bypass tests unless explicitly approved.

---

## Environment and Secrets

Never commit secrets.

Never expose broker credentials to frontend code.

Use `.env.example` for variable names only.

Separate paper and live credentials.

Use deployment-provider secret management for production.

If a change touches secrets, broker credentials, deployment configuration, live trading flags, or production environment variables, ask for confirmation before implementation unless the user explicitly requested the exact change.

---

## Prompt Handling Rules for Codex

When receiving a user prompt:

1. Read the prompt carefully.
2. Inspect the relevant files before editing.
3. Identify the latest versioned spec.
4. Check whether the prompt is compliant with the spec.
5. If compliant, implement cleanly.
6. If not compliant, stop and ask for approval.
7. If approved, update the spec as well as the implementation.
8. Summarize exactly what changed.
9. Mention any files that still need follow-up work.

Do not over-implement beyond the prompt.

Do not introduce new architecture unless requested or required by the latest spec.

Do not make speculative improvements to risk/execution behavior without approval.

---

## Response Style for Codex

When reporting back, include:

```text
Summary:
- What changed.

Files changed:
- path/to/file.py
- path/to/config.yaml

Spec impact:
- Compliant with latest spec, or
- Spec updated, or
- Spec deviation requires approval.

Tests:
- Tests run.
- Tests added.
- Tests not run and why.

Risks / follow-ups:
- Any remaining issues.
```

Be precise and concise.

---

## Final Governance Rule

If implementation and specification disagree, the project is in an invalid state.

Resolve the disagreement before continuing.

The latest spec and the codebase must evolve together.
