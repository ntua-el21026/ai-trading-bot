# Kill-Switch And Manual Re-Arm Checklist

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.4.md`.

This checklist is documentation-only. It does not send Temporal signals or broker orders.

## Trigger Review

- [ ] Incident identified.
- [ ] Current state captured.
- [ ] Kill-switch state recorded.
- [ ] Open orders recorded.
- [ ] Open positions recorded.
- [ ] Protective stop status recorded.
- [ ] Last reconciliation status recorded.

## Immediate Safety Actions

- [ ] New risk paused.
- [ ] Pending entry orders cancelled if safe.
- [ ] Protective exits preserved or verified.
- [ ] Risk-reducing exits confirmed allowed unless `PAUSED_ALL_AUTONOMOUS_ACTIONS`.
- [ ] Full reconciliation requested.
- [ ] Incident snapshot created.
- [ ] Alert delivery confirmed.

## Re-Arm Preconditions

- [ ] Root cause documented.
- [ ] Broker/internal state reconciled.
- [ ] Protective stops confirmed.
- [ ] Duplicate orders ruled out.
- [ ] Stale data resolved.
- [ ] Execution workflow state consistent.
- [ ] Dashboard/control-plane state consistent.
- [ ] No unresolved critical incidents remain.
- [ ] Operator approval recorded.

## Resume After Review

- [ ] `manual_resume_after_review` request is auditable.
- [ ] Review reference attached.
- [ ] Reconciliation was run immediately before resume.
- [ ] Kill-switch state after resume recorded.
- [ ] Report updated.

## Sign-Off

- Operator:
- Reviewer:
- Date:
- Incident ID:
- Resume approved: yes/no
