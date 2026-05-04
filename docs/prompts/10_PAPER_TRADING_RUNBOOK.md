# 10 - Paper Trading Runbook

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Paper trading is operational rehearsal: it validates orchestration, broker integration, stop placement, reconciliation, logging, kill switches, reporting, and AI schema behavior, but it does not prove live profitability.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Create the paper trading operations runbook, checklist, monitoring procedure, report expectations, incident response flow, and paper-to-live acceptance criteria.

## Scope

- Paper trading runbook documentation.
- Daily/weekly operating checklists.
- Startup, shutdown, monitoring, and reconciliation procedures.
- Incident response and escalation workflow.
- Paper reporting requirements.
- Frozen paper validation criteria.
- Paper-to-Level-4 micro-live readiness checklist.
- Optional scripts/checklists only if they are non-trading documentation helpers and do not execute broker orders.

## Out of Scope

- No live trading enablement.
- No actual broker API calls unless explicitly requested and safe.
- No application code unless needed for documentation generation and approved by the user.
- No changes to execution policy, risk limits, autonomy level, or live credentials.
- No claims of profitability from paper results.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on paper trading policy, validation plan, acceptance before Level 4 micro-live, operations, reports, kill switch, reconciliation, and incidents
- Existing `docs/operations_runbook.md`, `docs/validation_plan.md`, `docs/execution_policy.md`, `docs/risk_policy.md`, `docs/temporal_workflows.md`, README, and scripts if present
- Existing paper tests, reports, and dry-run commands if present

## Implementation Tasks

1. Document paper environment setup using variable names only, without secrets.
2. Define pre-market, entry-window, intraday, EOD, and weekly paper procedures.
3. Document required monitoring signals: Temporal workflows, broker stream/REST reconciliation, orders, fills, positions, protective stops, incidents, AI schema validity, and reports.
4. Define incident response for missing stop, duplicate order, broker/internal mismatch, stale data, invalid AI payload, worker outage, and kill-switch activation.
5. Document daily and weekly report contents.
6. Document frozen paper acceptance criteria, including duration/trade-count requirements and control-incident thresholds from the latest spec.
7. Document explicit paper-to-live handoff requirements and unresolved gaps.

## Spec Alignment Checks

- Paper trading must remain operational rehearsal, not proof of profitability.
- Acceptance before Level 4 micro-live must match the latest spec.
- Protective stop placement success, mismatch thresholds, AI valid-schema rate, missing-stop incidents, duplicate-order incidents, and Sev-1 incident criteria must be included.
- No live credentials or live enablement steps may be added as executable defaults.
- Kill switch and manual re-arm requirements must match the latest spec.

## Tests / Validation

- Validate documentation links and referenced commands where possible.
- Run documentation lint if configured.
- If no doc validation exists, manually inspect the created docs for completeness against latest-spec acceptance criteria.
- Do not run broker APIs for this documentation milestone.

## Documentation Updates

- Update `docs/operations_runbook.md` or create the appropriate runbook doc.
- Update validation docs if paper acceptance criteria are not already documented.
- Do not update the latest spec unless an approved deviation requires it.

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
