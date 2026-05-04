# 00 - Repo Inspection And Plan

You are Codex working inside this repository.

## Context

This repository is a spec-governed autonomous trading system, not a generic trading-bot project. Before planning any work, read `AGENTS.md`, identify and read the latest versioned autonomous trading bot specification, and treat the latest spec as the source of truth. Implementation must remain spec-aligned.

This milestone is planning-only. Do not implement application code.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Produce a repository-aware, spec-aligned implementation plan that identifies what exists, what is missing, and the safest incremental build sequence.

## Scope

- Inspect repository structure, documentation, spec files, configuration, tests, and any existing source code.
- Identify the latest spec file by version number.
- Compare the repository against the latest spec's architecture, roadmap, repository structure, and acceptance criteria.
- Produce an implementation plan broken into small milestones.
- Identify risks, blockers, missing decisions, and likely approval gates.

## Out of Scope

- Do not create application modules.
- Do not create migrations.
- Do not implement services, workers, dashboards, APIs, broker adapters, trading logic, or tests.
- Do not change risk limits, execution policy, autonomy settings, or the latest spec.
- Do not add secrets or environment-specific credentials.

## Required Inspection

- `AGENTS.md`
- Latest file matching `*SPEC*.md` or `Autonomous_AI_Trading_Bot_SPEC_v*.md`
- `README.md`
- `docs/`
- Existing `config/`, `apps/`, `packages/`, `db/`, `tests/`, and `scripts/` folders if present
- Project configuration files such as `pyproject.toml`, `requirements*.txt`, `package.json`, `docker-compose.yml`, and `.env.example` if present
- Git status, if available

## Implementation Tasks

1. Inspect the full repository tree, excluding only generated/cache folders when needed for readability.
2. Identify all versioned spec files and select the highest version.
3. Summarize the latest spec's governing constraints relevant to implementation order.
4. Compare current repository contents to the latest spec's expected structure.
5. Classify existing implementation areas as present, partial, missing, or unclear.
6. Produce a safe milestone plan for project foundation, data/backtest, Temporal, strategy, risk/execution, broker reconciliation, AI, dashboard, validation, paper trading, and micro-live readiness.
7. List explicit approval gates for any likely spec deviation or architecture decision.
8. List immediate next files to create in Milestone 01 if the user approves implementation.

## Spec Alignment Checks

- Confirm the plan preserves Temporal as part of the v0.1 architecture.
- Confirm no AI direct broker access is proposed.
- Confirm execution authority remains in deterministic execution workflows.
- Confirm every future live order path requires a valid `ExecutionIntent`.
- Confirm Vercel is treated as dashboard/control-plane only.
- Confirm paper-first validation and Level 4 micro-live gates remain intact.
- Confirm no unsupported asset class, leverage, shorting, options, futures, crypto, or prediction-market support is introduced.

## Tests / Validation

- No code tests are expected because this milestone is inspection/planning-only.
- Validate that the selected latest spec is the highest available version.
- Validate that the final plan maps each proposed milestone to relevant latest-spec sections.

## Documentation Updates

- Documentation changes are not required for this planning-only milestone.
- If you create or update a planning document, keep it clearly labeled as a plan and do not present unimplemented behavior as complete.
- Do not update the latest spec unless the user explicitly approves a documentation-only correction.

## Approval Gate

If any requested implementation would deviate from the latest spec, do not implement it.
Explain the deviation, propose options, and wait for user approval.
If the user approves a deviation, update the latest spec as part of the same milestone or create a new versioned spec file, depending on the size of the change.

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
