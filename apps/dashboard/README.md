# Dashboard Contract

This directory is a minimal dashboard scaffold. No frontend framework is installed.

The dashboard is read-only monitoring plus safe control-plane actions routed through backend
contracts. It must not contain broker credentials, AI provider credentials, order-entry forms,
natural-language trading inputs, direct broker calls, direct AI/news provider calls, or autonomous
execution workers.

Milestone 25 dashboard/control-plane runtime smoke is implemented server-side in
`packages/control_plane/runtime.py` and `scripts/check_dashboard_control_plane_runtime.py`. It builds
fake/local read-only snapshots and validates safe controls through fake dispatch by default. It does
not deploy, activate schedules, send Telegram alerts, call broker APIs, call AI/news providers, or
send real Temporal control signals by default.

Allowed public environment names are defined in `public_env.py`.
