# Level 4 Micro-Live Readiness Checklist

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

This checklist is documentation-only. It does not enable live trading or submit broker orders.

## Current Status

- [ ] Milestones 00-10 complete.
- [ ] Paper trading operations completed.
- [ ] Frozen paper evidence available.
- [ ] Database/audit persistence implemented.
- [ ] Real Temporal query/signal backend integrated.
- [ ] Real Alpaca paper client integrated and validated.
- [ ] Real AI/news providers integrated and validated.
- [ ] Dashboard deployed and validated.
- [ ] Alerting implemented and validated.
- [ ] Level 4 go/no-go report completed.

## Acceptance Gates

- [ ] At least 8 weeks frozen paper.
- [ ] At least 30 closed paper trades or 2 quarters of forward paper, whichever comes later.
- [ ] OOS Profit Factor >= 1.10.
- [ ] OOS Sharpe >= 0.75 or OOS Sortino >= 1.00.
- [ ] Max drawdown <= 10%.
- [ ] 100% protective stop placement success.
- [ ] Broker/internal mismatch rate < 0.1%.
- [ ] AI valid-schema rate >= 99%.
- [ ] Zero Sev-1 control incidents in last 20 sessions.
- [ ] Zero missing-stop incidents.
- [ ] Zero duplicate-order incidents.

## Safety Gates

- [ ] Live trading disabled until final approval.
- [ ] Autonomous live execution disabled until final approval.
- [ ] Kill switch enabled.
- [ ] Broker reconciliation required.
- [ ] Protective stops required.
- [ ] Unsupported assets disabled.
- [ ] AI has no broker access.
- [ ] Dashboard/frontend has no provider secrets.
- [ ] Alert delivery verified.
- [ ] Rollback and kill-switch plan verified.

## Evidence Gates

- [ ] Pre-execution reconciliation evidence.
- [ ] Active-window reconciliation evidence.
- [ ] EOD reconciliation evidence.
- [ ] BOD reconciliation evidence.
- [ ] Missing-stop threshold evidence.
- [ ] Partial-fill stop quantity evidence.
- [ ] Duplicate order/idempotency evidence.
- [ ] AI schema/fallback evidence.
- [ ] Slippage/fill diagnostics evidence.
- [ ] Dashboard/control-plane evidence.
- [ ] Manual re-arm evidence.

## Sign-Off

- Operator:
- Reviewer:
- Date:
- Candidate commit:
- Decision: go/no-go
- Notes:
