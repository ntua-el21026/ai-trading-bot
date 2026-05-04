# 01 - Project Foundation

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. The foundation must support a Temporal-orchestrated, broker-reconciled, long-only US equities/ETF swing-trading system with deterministic safety controls and full auditability.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Create the minimal project foundation required by the latest spec: repository layout, Python project configuration, config loading, logging, environment template, and baseline documentation, without implementing trading behavior.

## Scope

- Base Python project setup using the stack allowed by the latest spec.
- Minimal package/module layout consistent with the latest spec.
- Configuration files and typed config loading scaffolding.
- Structured logging setup.
- `.env.example` with variable names only.
- Placeholder documentation for architecture, Temporal, risk, execution, validation, and operations if the spec expects them.
- Narrow tests for config loading and foundational utilities.

## Out of Scope

- No strategy, regime, signal, risk, execution, broker, AI, dashboard, or backtest logic beyond placeholders needed for structure.
- No database migrations unless the user explicitly approves them for this milestone.
- No live trading enablement.
- No secrets or real credentials.
- No dependency changes that are not required for the foundation.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec
- `README.md`
- `docs/`
- Existing `pyproject.toml`, `requirements*.txt`, `uv.lock`, `poetry.lock`, or equivalent dependency files
- Existing `config/`, `.env.example`, `apps/`, `packages/`, `tests/`, and `scripts/` folders
- `.gitignore` and `.gitattributes`

## Implementation Tasks

1. Confirm the latest spec's expected repository structure and preferred backend stack.
2. Create or adjust the minimal directory layout required for later milestones.
3. Add Python project configuration if absent, using Python 3.12+ unless the repo already specifies otherwise.
4. Add config files aligned with the latest spec defaults, keeping live trading disabled and dry-run/paper defaults safe.
5. Add typed config-loading scaffolding with validation and no hidden constants.
6. Add structured logging setup suitable for worker/API use.
7. Add `.env.example` with variable names only and no secret values.
8. Add placeholder docs only where the latest spec expects documentation.
9. Add focused tests for config loading and logging initialization if implementation files are created.

## Spec Alignment Checks

- Defaults must keep `live_trading_enabled: false`, `autonomous_execution_enabled: false`, and safe paper/dry-run behavior.
- Config must not allow margin, shorting, options, futures, crypto, or prediction markets.
- AI config must keep AI unable to create orders, modify strategy, or modify risk limits.
- Vercel/dashboard configuration must not expose broker credentials.
- Temporal must be included as an architectural dependency or placeholder per spec, but workflows are not implemented in this milestone.

## Tests / Validation

- Run the narrowest relevant test command for created foundation code.
- Run formatting or type checks only if configured.
- If no test framework exists yet, add minimal tests for foundation utilities or state exactly why tests were not run.

## Documentation Updates

- Update `README.md` only with accurate setup/project-structure information.
- Add or update docs that describe structure and foundation only.
- Do not claim trading functionality exists.
- If any foundation decision deviates from the latest spec, stop for approval before editing and update the spec if approved.

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
