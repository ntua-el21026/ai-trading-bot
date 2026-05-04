# 11 - Level 4 Micro-Live Readiness

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Level 4 micro-live is the first live autonomous target, but live trading must not be enabled unless explicitly asked and all spec-defined gates are satisfied.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Prepare Level 4 micro-live readiness documentation and validation gates, including pre-live checklist, credential separation requirements, micro-live risk configuration review, kill-switch/manual re-arm testing, and final go/no-go evidence requirements.

## Scope

- Readiness checklist documentation.
- Evidence checklist for paper validation and operational safety gates.
- Credential separation procedure using variable names only.
- Micro-live risk config review against latest-spec limits.
- Manual re-arm and kill-switch test procedures.
- Incident, reconciliation, missing-stop, duplicate-order, AI schema, and slippage acceptance checks.
- Final go/no-go report template.

## Out of Scope

- Do not enable live trading.
- Do not add real live credentials.
- Do not change risk limits, autonomy level, execution policy, stop policy, kill-switch behavior, or allowed assets unless explicitly approved and spec-updated.
- Do not run live broker orders.
- Do not promote to expanded Level 4 or Level 5.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on autonomy model, Level 4 micro-live definition, risk limits, execution, reconciliation, kill switch, validation acceptance criteria, environment variables, and roadmap
- Existing `config/system.yaml`, `config/risk.yaml`, `config/execution.yaml`, `.env.example`, `docs/operations_runbook.md`, `docs/validation_plan.md`, `docs/risk_policy.md`, `docs/execution_policy.md`, reports, and tests if present
- Evidence artifacts from paper trading if available

## Implementation Tasks

1. Create or update Level 4 micro-live readiness documentation.
2. Document the exact acceptance gates required before micro-live, including frozen paper duration/trade count, OOS metrics, drawdown, protective stops, mismatch rate, AI schema validity, Sev-1 incidents, missing-stop incidents, and duplicate-order incidents.
3. Document credential separation and secret-manager requirements without exposing or creating secrets.
4. Review micro-live risk config values against latest-spec `risk_level_4_micro_live` limits and document discrepancies without silently changing them.
5. Document kill-switch, pause-new-risk, force reconciliation, manual re-arm, and alert tests required before go-live.
6. Add a go/no-go report template that records evidence, unresolved risks, operator approval, and config versions.
7. If any config changes are needed to prepare but not enable micro-live, stop and ask for approval before changing them.

## Spec Alignment Checks

- Level 4 micro-live must remain capped and conservative.
- Live trading must remain disabled unless the user explicitly requests enablement and all gates are satisfied.
- Required risk limits must match latest spec unless approved and spec-updated.
- AI must still have no broker write permissions.
- Vercel must remain dashboard/control-plane only.
- Expanded Level 4 and Level 5 must require evidence after micro-live and must not be enabled here.

## Tests / Validation

- Validate documentation links and referenced commands where possible.
- Run config validation if config files exist and are read.
- Run tests for kill-switch/manual re-arm procedures only if they are dry-run/simulated and configured.
- Do not run live broker orders.
- Report any missing evidence or unverified gates clearly.

## Documentation Updates

- Update operations, validation, risk, and execution docs with Level 4 readiness gates and go/no-go template.
- Do not update the latest spec unless an approved deviation requires it.
- Do not document live enablement as complete unless the user explicitly requested and approved that separate action.

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
