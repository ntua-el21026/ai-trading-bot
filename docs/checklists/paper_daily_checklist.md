# Paper Daily Checklist

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Use this checklist with `docs/paper_trading_runbook.md`. It is documentation-only and does not
execute broker, AI/news, database, or Temporal actions.

## Pre-Run

- [ ] Latest spec version confirmed.
- [ ] `git status --short` clean or known.
- [ ] Required tests passed.
- [ ] Config is paper mode.
- [ ] Live trading disabled.
- [ ] Autonomous live execution disabled.
- [ ] Broker account mode is paper.
- [ ] Kill switch enabled.
- [ ] Broker reconciliation required.
- [ ] Protective stops required.
- [ ] Unsupported assets disabled.
- [ ] AI has no broker access.
- [ ] Dashboard has no broker or AI/news provider secrets.
- [ ] Alerts configured, or alerting gap documented.

## Pre-Market / BOD

- [ ] Prior report reviewed.
- [ ] Open incidents reviewed.
- [ ] Temporal service checked.
- [ ] Workers/task queues checked.
- [ ] Dashboard/control-plane checked.
- [ ] Broker stream and REST fallback readiness checked when implemented.
- [ ] BOD reconciliation completed when implemented.
- [ ] New risk remains paused if critical incidents are unresolved.

## Data And AI Windows

- [ ] 08:25-08:45 ET data refresh status reviewed.
- [ ] Bar/quote freshness reviewed.
- [ ] Corporate action/earnings data status reviewed.
- [ ] 08:45-09:10 ET AI shortlist refresh status reviewed.
- [ ] AI schema validity reviewed.
- [ ] AI fallbacks reviewed.

## Entry And Intraday

- [ ] 09:45-10:30 ET entry window monitored.
- [ ] Execution intents reviewed.
- [ ] Risk checks reviewed.
- [ ] Pre-submit reconciliation reviewed.
- [ ] Orders/fills/partial fills monitored.
- [ ] Protective stops confirmed for filled quantity.
- [ ] REST fallback status checked every active window.
- [ ] Incidents monitored and escalated.

## EOD / Post-Market

- [ ] 16:10-16:30 ET EOD signals reviewed.
- [ ] 16:30-17:00 ET AI refresh reviewed.
- [ ] 17:00-17:15 ET decisions reviewed.
- [ ] 20:00 ET reconciliation reviewed.
- [ ] Daily report generated or gap documented.
- [ ] Open follow-ups assigned.

## Sign-Off

- Operator:
- Date:
- Commit/config snapshot:
- Critical incidents:
- Resume/pause state:
