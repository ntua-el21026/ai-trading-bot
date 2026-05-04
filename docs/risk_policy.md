# Risk Policy

This document is a foundation placeholder for risk policy.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 01 only records safe configuration defaults and typed validation. It does not implement risk checks, position sizing, execution gating, stop management, or kill-switch behavior.

## Foundation Defaults

- Paper environment by default.
- Dry-run behavior by default.
- Live trading disabled.
- Autonomous execution disabled.
- Margin disabled.
- Shorting disabled.
- Options, futures, crypto, leveraged ETFs, and prediction markets disabled.
- Protective stops required in configuration.

## Future Work

Later milestones must implement deterministic and non-bypassable risk checks before any new-risk order path. Any change to risk limits or risk semantics requires explicit approval and a corresponding spec update.
