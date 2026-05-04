# 07 - AI Intelligence Layer

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. The AI layer is bounded and advisory: it may analyze deterministic shortlist candidates, classify news/catalyst risk, return schema-validated JSON, and produce explanations/reports. It must not have broker write permissions.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Implement bounded shortlist-only AI/news intelligence with prompt versioning, schema validation, raw/parsed output persistence contracts, and neutral fallback behavior.

## Scope

- News source abstractions for ticker-tagged candidate news.
- Article normalization and deduplication.
- AI prompt template/version files.
- AI structured-output schema and parser.
- Raw prompt/output persistence contracts with prompt/model/schema versions and audit hashes.
- Validated parsed output models.
- Neutral fallback behavior for missing news, invalid output, and AI outage.
- Unit tests for schema parsing and fallback behavior.

## Out of Scope

- No AI full-universe scanning for direct trade ideas.
- No broker credentials or broker API access in AI code.
- No AI order submission, order modification, stop changes, risk-limit changes, live strategy mutation, or kill-switch override.
- No unstructured AI output in execution-critical paths.
- No live provider/API calls unless behind explicit dry-run or mocked test boundaries.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on AI intelligence service, decision arbiter, ML scope, database specification, config/ai, environment variables, and testing
- Existing `packages/ai`, `packages/strategy`, `packages/data`, `config/ai.yaml`, `apps/workers/activities`, and tests
- Existing candidate/decision models and persistence boundaries

## Implementation Tasks

1. Define news provider interfaces for deterministic shortlist candidates only.
2. Add article normalization, ticker association, deduplication, and source metadata models.
3. Create versioned AI prompt template files aligned with the latest spec.
4. Implement a strict JSON schema or Pydantic model for AI trade research output.
5. Implement parser/validator behavior that rejects invalid output and returns configured neutral fallback.
6. Define persistence payloads for raw prompt, raw AI output, parsed output, prompt version, schema version, model version, citations, and audit hashes.
7. Add AI activity boundaries for Temporal use without calling AI from workflow code.
8. Add tests for valid output, invalid JSON, schema violations, missing news fallback, hard-block confidence, and audit metadata.

## Spec Alignment Checks

- AI must analyze deterministic shortlist candidates only.
- AI must not create orders, modify strategy, modify risk limits, submit trades, modify orders, change stops, or access broker credentials.
- AI outputs must be schema-validated.
- Invalid AI output must fall back to neutral behavior unless the latest spec says otherwise.
- AI failure alone must not trigger a global kill switch unless repeated failures or required checks create a spec-defined system-level safety issue.

## Tests / Validation

- Run unit tests for prompt/schema parsing, fallback behavior, event taxonomy, and persistence payloads.
- Use mocked AI/news responses by default.
- Run type checks or lint if configured.
- Document any external-provider tests not run and exact commands for later.

## Documentation Updates

- Update AI documentation with prompt/schema versions, allowed responsibilities, forbidden responsibilities, fallback behavior, and persistence requirements.
- Update `.env.example` only with variable names if required.
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
