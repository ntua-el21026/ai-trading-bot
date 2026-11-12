# AI Trading Bot

A paper-trading research framework with deterministic strategy, risk, execution
and reconciliation components, Temporal orchestration and a bounded advisory
AI/news layer. AI has no broker-write authority and cannot override risk limits.

## Recorded state

The v0.6 paper-validation clock started on 18 May 2026 with a 13 July target.
The latest committed May observations do **not** establish completion of that
56-day run. The [durable-runner evidence](docs/evidence/durable_runner_m47b.json)
records deployment_ready_not_active, no accepted heartbeat and off-PC NO_GO.
Elapsed calendar time is not validation evidence. Live trading, profitability
and completed autonomous operation are not supported claims.

The source contains controlled paper-operation tooling as well as fake/local
adapters. Those operator-gated paths are distinct from the offline entry point
below. Earlier milestone descriptions and detailed validation commands remain in
the [historical README](docs/history/readme-before-portfolio-preparation.md).

## Architecture

- Data models normalize supplied market/broker observations and retain provenance.
- Deterministic strategy and risk modules construct bounded execution intents.
- Temporal workflows coordinate activities; external effects belong in activities.
- Broker adapters reconcile order/fill/stop state behind explicit paper gates.
- SQLite supports local tests; managed PostgreSQL requires separate configuration.
- News/AI components return schema-checked advisory results and neutral fallbacks.
- Reporting and a read-only dashboard project retained operational state.

The backtest consumes explicit supplied signals under its declared fee/slippage
and timing convention. It does not establish a predictive model or causal signal
generator. Any future strategy result needs independent data/split/execution
qualification.

## Offline setup and tests

Python 3.12 or later and uv are required. Install dependencies in an isolated
environment, keep credentials unset and retain fake/local defaults.

~~~bash
uv sync --dev
uv run --group dev pytest tests/unit -m "not integration"
uv run python scripts/run_paper_dry_run.py
~~~

The dry run uses fake adapters and in-memory SQLite. It does not call broker,
AI/news, alert, market-data, Temporal or managed database services. Do not substitute
paper-operation or credentialed smoke commands for this demonstration.

Temporal server/replay tests, managed-database integration, provider smoke tests,
long-duration paper acceptance and deployment qualification are separate gates.
A unit pass or dashboard build does not satisfy them.

## Technical documentation

Start with the [v0.6 specification](docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md)
and the source modules under packages and apps. Configuration under config
defines strategy, execution, risk, regime, universe, Temporal and AI boundaries.
Keep their acceptance criteria and financial parameters unchanged during
presentation work. The historical README links runbooks and milestone-specific
checks, including intentionally gated commands.

## Attribution, limitations and release

Maintained by Michail-Athanasios Peppas, with AI-assisted implementation/review
records retained for provenance. The [MIT license](LICENSE) covers material for
which that grant applies; provider data, imported components and third-party
services retain their own terms.

Use synthetic fixtures for public demonstrations. Review paper-session identifiers,
private operations records and provider/data terms before publication. Code
accessibility, reuse licensing, long-run research acceptance and authorization to
operate a broker-connected system are separate decisions.
