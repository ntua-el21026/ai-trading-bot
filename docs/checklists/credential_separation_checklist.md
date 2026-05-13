# Credential Separation Checklist

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.4.md`.

This checklist is documentation-only. Do not write secret values into this file.

## Repository Hygiene

- [ ] `.env.example` contains variable names only.
- [ ] No `.env` file is committed.
- [ ] No broker credentials appear in frontend/dashboard code.
- [ ] No AI/news provider credentials appear in frontend/dashboard code.
- [ ] No Temporal API key appears in frontend/dashboard code.
- [ ] No privileged database URL appears in frontend/dashboard code.

## Paper Credentials

- [ ] Paper broker credentials are stored outside the repo.
- [ ] Paper broker credentials are separate from live credentials.
- [ ] Paper broker base URL is clearly paper-only.
- [ ] Paper environment variables are scoped to paper runs.
- [ ] Paper credentials have been rotated if exposed or copied into unsafe tooling.

## Live Credentials

- [ ] Live broker credentials are not present in the repo.
- [ ] Live broker credentials are not loaded by paper or dry-run environments.
- [ ] Live broker credentials are stored in a secret manager.
- [ ] Live credential access requires explicit operator approval.
- [ ] Live credential activation requires completed go/no-go evidence.

## Provider And Platform Secrets

- [ ] `DATABASE_URL` stored in secret manager when implemented.
- [ ] `TEMPORAL_API_KEY` stored in secret manager when implemented.
- [ ] AI/news provider keys stored in secret manager when implemented.
- [ ] Alert channel tokens stored in secret manager when implemented.
- [ ] Secret rotation procedure documented.

## Sign-Off

- Operator:
- Reviewer:
- Date:
- Evidence location:
