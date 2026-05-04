# Codex Prompt - Create Milestone Prompt Pack

You are Codex working inside this repository (/home/peppasmich/AI_Trading_Bot).

Your task is **NOT** to implement the trading bot yet.

Your task is to inspect the repository, read the project governance file, read the latest versioned specification, and then create a clean milestone-based prompt pack under a new `prompts/` folder.

---

## Required First Steps

1. Inspect the full repository structure.
2. Read `AGENTS.md` from the project root.
3. Identify and read the latest versioned autonomous trading bot specification file.
   - Prefer the newest file matching something like:
     - `*SPEC*.md`
     - `Autonomous_AI_Trading_Bot_SPEC_v*.md`
   - If multiple versions exist, use the highest version number.
4. Do not make assumptions that conflict with `AGENTS.md` or the latest spec.
5. Do not implement application code.
6. Do not create migrations, services, workers, dashboards, APIs, or trading logic yet.
7. Only create milestone prompt documents.

---

## Goal

Create a `prompts/` directory containing a set of ready-to-use Codex prompt files.

Each prompt file should correspond to one semantic project milestone and should be usable later as a standalone Codex prompt.

The purpose is to break the project into safe, incremental, spec-aligned implementation phases.

---

## Important Governance Rules

Follow these rules from `AGENTS.md`:

- The latest spec is the source of truth.
- The repository structure and content may evolve.
- If implementation would deviate from the latest spec, Codex must ask for permission and wait before implementing.
- If a deviation is approved later, the latest spec must also be updated.
- AI must not have broker write permissions.
- Execution authority belongs to the deterministic execution pipeline.
- Every live order requires a valid `ExecutionIntent`.
- Temporal is part of the v0.1 architecture.
- Vercel is dashboard/control-plane only.
- No code implementation should happen during this prompt-generation task.

---

## What to Create

Create the following folder:

```text
prompts/
```

Inside it, create these Markdown files:

```text
prompts/README.md
prompts/00_REPO_INSPECTION_AND_PLAN.md
prompts/01_PROJECT_FOUNDATION.md
prompts/02_DATA_AND_BACKTEST_CORE.md
prompts/03_TEMPORAL_WORKFLOWS.md
prompts/04_STRATEGY_REGIME_AND_SIGNALS.md
prompts/05_RISK_AND_EXECUTION_CORE.md
prompts/06_BROKER_RECONCILIATION.md
prompts/07_AI_INTELLIGENCE_LAYER.md
prompts/08_DASHBOARD_AND_CONTROL_PLANE.md
prompts/09_VALIDATION_AND_TESTING.md
prompts/10_PAPER_TRADING_RUNBOOK.md
prompts/11_LEVEL4_MICRO_LIVE_READINESS.md
```

If the inspected repository or latest spec suggests a better naming or ordering, you may adjust the exact file list, but only if you explain why in the final summary.

---

## Content Requirements for Each Prompt File

Each milestone prompt must be written as a ready-to-paste Codex prompt.

Each file must include:

1. **Title**
2. **Context**
   - mention that Codex must read `AGENTS.md`;
   - mention that Codex must read the latest versioned spec;
   - mention that implementation must remain spec-aligned.
3. **Goal**
   - one clear milestone objective.
4. **Scope**
   - what this milestone is allowed to change or create.
5. **Out of Scope**
   - what must not be implemented in this milestone.
6. **Required Inspection**
   - files/folders Codex should inspect before editing.
7. **Implementation Tasks**
   - concrete tasks for that milestone.
8. **Spec Alignment Checks**
   - specific checks against the latest spec.
9. **Tests / Validation**
   - tests or validation expected for that milestone.
10. **Documentation Updates**

- docs or spec updates required if approved changes deviate from the spec.

1. **Approval Gate**

- explicit instruction to stop and ask before implementing any spec deviation.

1. **Expected Final Response**

- a concise reporting format Codex should use after completing that milestone.

---

## Requirements for the Milestone Prompt Set

The milestone set must be incremental.

Earlier milestones must not depend on later milestones.

The sequence should generally follow this build order:

```text
0. Repo inspection and plan
1. Project foundation
2. Data and backtest core
3. Temporal workflows
4. Strategy, regime, and signal logic
5. Risk and execution core
6. Broker reconciliation
7. AI intelligence layer
8. Dashboard and control plane
9. Validation and testing
10. Paper trading runbook
11. Level 4 micro-live readiness
```

However, after inspecting the repo and latest spec, adjust the milestone descriptions if needed.

---

## Specific Milestone Expectations

### 00_REPO_INSPECTION_AND_PLAN

This prompt should instruct Codex to:

- inspect the repo;
- read `AGENTS.md`;
- read the latest spec;
- identify current implemented vs missing parts;
- produce a repo-aware implementation plan;
- not implement code unless separately asked.

### 01_PROJECT_FOUNDATION

Should cover:

- base repository structure;
- Python project configuration;
- environment template;
- config loading;
- logging;
- basic package/module layout;
- placeholder docs if needed;
- no trading logic yet.

### 02_DATA_AND_BACKTEST_CORE

Should cover:

- market data abstractions;
- raw provider payload persistence;
- OHLCV models;
- feature calculation scaffolding;
- backtest engine skeleton;
- metrics skeleton;
- no broker execution.

### 03_TEMPORAL_WORKFLOWS

Should cover:

- Temporal worker setup;
- task queues;
- workflow/activity boundary;
- workflow skeletons;
- deterministic workflow rules;
- no real broker orders yet.

### 04_STRATEGY_REGIME_AND_SIGNALS

Should cover:

- deterministic regime engine;
- strategy signal rules;
- 20D/55D breakout variants;
- RS63;
- ATR filters;
- earnings blackout placeholders;
- no live execution.

### 05_RISK_AND_EXECUTION_CORE

Should cover:

- risk checks;
- position sizing;
- execution-intent object;
- idempotency design;
- order lifecycle abstractions;
- no live broker credentials or live trading.

### 06_BROKER_RECONCILIATION

Should cover:

- Alpaca adapter interface;
- paper-mode adapter implementation;
- `trade_updates` stream handling or abstraction;
- REST fallback;
- broker/internal state reconciliation;
- mismatch incident handling;
- no live trading enablement.

### 07_AI_INTELLIGENCE_LAYER

Should cover:

- deterministic shortlist-only AI analysis;
- news source abstractions;
- AI schema;
- prompt versioning;
- raw/parsed output persistence;
- fallback behavior;
- no broker access from AI.

### 08_DASHBOARD_AND_CONTROL_PLANE

Should cover:

- dashboard structure;
- read-only portfolio/signal/order/risk/report views;
- kill-switch control flow;
- no broker secrets in frontend;
- Vercel dashboard-only assumption.

### 09_VALIDATION_AND_TESTING

Should cover:

- unit tests;
- integration tests;
- Temporal workflow tests;
- backtest validation;
- paper execution dry-run checks;
- failure simulations.

### 10_PAPER_TRADING_RUNBOOK

Should cover:

- paper trading operating procedure;
- checklist;
- monitoring;
- reports;
- incident response;
- paper-to-live acceptance criteria.

### 11_LEVEL4_MICRO_LIVE_READINESS

Should cover:

- pre-live checklist;
- required validation gates;
- live credential separation;
- micro-live risk config;
- manual re-arm and kill-switch testing;
- no actual enabling of live trading unless explicitly asked.

---

## File Format Expectations

Each prompt file should start with:

```md
# <Milestone Number> - <Milestone Title>

You are Codex working inside this repository.
```

Each prompt file should include a section:

```md
## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.
```

Each prompt file should include an approval gate similar to:

```md
## Approval Gate

If any requested implementation would deviate from the latest spec, do not implement it.
Explain the deviation, propose options, and wait for user approval.
If the user approves a deviation, update the latest spec as part of the same milestone or create a new versioned spec file, depending on the size of the change.
```

Each prompt file should include final reporting format:

```md
## Expected Final Response

Summary:

- ...

Files changed:

- ...

Spec impact:

- ...

Tests:

- ...

Risks / follow-ups:

- ...
```

---

## Root Index File

Also create:

```text
prompts/README.md
```

This file should list all milestone prompt files in order, with a short description of each.

It should state that prompts are intended to be run sequentially unless the user explicitly decides otherwise.

---

## Do Not Do the Following

Do not implement the bot.

Do not create actual application modules unless they are only part of the prompt-pack task and not implementation.

Do not run broker APIs.

Do not configure live trading.

Do not add secrets.

Do not change risk limits.

Do not change the latest spec unless the prompt-pack task itself discovers that the prompt files need to reference a newer spec filename or there is a documentation-only correction. If a true spec change is needed, report it instead of making it.

---

## Final Response After Completing This Task

After creating the prompt files, respond with:

```text
Summary:
- Created prompts/ milestone prompt pack.
- Identified latest spec: <filename>.
- No implementation code was changed.

Files created:
- prompts/README.md
- prompts/00_REPO_INSPECTION_AND_PLAN.md
- prompts/01_PROJECT_FOUNDATION.md
- prompts/02_DATA_AND_BACKTEST_CORE.md
- prompts/03_TEMPORAL_WORKFLOWS.md
- prompts/04_STRATEGY_REGIME_AND_SIGNALS.md
- prompts/05_RISK_AND_EXECUTION_CORE.md
- prompts/06_BROKER_RECONCILIATION.md
- prompts/07_AI_INTELLIGENCE_LAYER.md
- prompts/08_DASHBOARD_AND_CONTROL_PLANE.md
- prompts/09_VALIDATION_AND_TESTING.md
- prompts/10_PAPER_TRADING_RUNBOOK.md
- prompts/11_LEVEL4_MICRO_LIVE_READINESS.md

Spec impact:
- No spec behavior changed.
- Any noted spec/doc concerns: <list or none>.

Recommended next step:
- Run prompts/00_REPO_INSPECTION_AND_PLAN.md as the first implementation-planning Codex prompt.
```
