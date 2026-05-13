# Paper Weekly Review Checklist

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Use this checklist with `docs/paper_trading_runbook.md`. It is documentation-only and does not
execute broker, AI/news, database, or Temporal actions.

## Evidence Review

- [ ] All daily reports reviewed.
- [ ] Closed paper trade count reviewed.
- [ ] Open positions reviewed.
- [ ] Stop placement success rate reviewed.
- [ ] Broker/internal mismatch rate reviewed.
- [ ] AI valid-schema rate reviewed.
- [ ] Sev-1/control incidents reviewed.
- [ ] Missing-stop incidents reviewed.
- [ ] Duplicate-order incidents reviewed.
- [ ] Stale data/provider outage incidents reviewed.
- [ ] Dashboard/control-plane action audit reviewed.
- [ ] Alert delivery reviewed when implemented.

## Frozen Paper Window

- [ ] Strategy version unchanged or change impact documented.
- [ ] Risk config unchanged or change impact documented.
- [ ] Execution policy unchanged or change impact documented.
- [ ] AI prompt/schema versions unchanged or change impact documented.
- [ ] Data/backtest assumptions unchanged or change impact documented.
- [ ] Paper/live credential separation confirmed.
- [ ] No live trading occurred.
- [ ] No paper result is represented as proof of live profitability.

## Acceptance Progress

- [ ] Weeks of frozen paper counted.
- [ ] Closed paper trades counted.
- [ ] OOS Profit Factor tracked.
- [ ] OOS Sharpe or Sortino tracked.
- [ ] Max drawdown tracked.
- [ ] Protective stop placement success tracked.
- [ ] Broker/internal mismatch rate tracked.
- [ ] AI valid-schema rate tracked.
- [ ] Last 20 sessions control incident status tracked.

## Sign-Off

- Reviewer:
- Week ending:
- Frozen paper clock remains valid: yes/no
- Gaps:
- Next actions:
