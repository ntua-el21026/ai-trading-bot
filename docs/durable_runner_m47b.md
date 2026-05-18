# Milestone 47B Durable Off-PC Frozen Runner

Latest source of truth: `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md`.

## Result

- Off-PC operation result: `NO_GO`
- Preparation result: `GO`
- Selected durable path: `cloud_vps_docker_runner`
- Durable runner status: `deployment_ready_not_active`
- Runner command: `docker compose -f docker-compose.paper-runner.yml up -d --build frozen-paper-runner`
- Health check command: `docker compose -f docker-compose.paper-runner.yml exec -T frozen-paper-runner uv run python scripts/check_frozen_paper_runner_health.py --heartbeat .runtime/frozen_validation_runner/heartbeat.json --max-age-seconds 900`
- Heartbeat status: `missing`
- Heartbeat age seconds: `None`

## Validation Clock

- Status: `active`
- Start UTC: `2026-05-18T16:51:09.038248Z`
- Target end UTC: `2026-07-13T16:51:09.038248Z`
- Current UTC: `2026-05-18T21:52:58.395024Z`
- Day index: `1`
- Window active: `true`

## Deployment Package

Deployment artifacts:
- `Dockerfile.paper-runner`
- `.dockerignore`
- `docker-compose.paper-runner.yml`
- `deploy/systemd/frozen-paper-runner.service`
- `scripts/run_frozen_paper_validation_runner.py`
- `scripts/check_frozen_paper_runner_health.py`

The package is intended for a small VPS or cloud VM using Docker Compose or systemd.
It is not a Vercel execution worker and exposes no frontend secrets.

## Environment Matrix

Required server-side variables for the off-PC host:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_BASE_URL`
- `TIINGO_API_KEY`
- `DATABASE_URL`, only if the managed ledger runtime is enabled for the host
- `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, and `TEMPORAL_API_KEY`, only if the host is later
  upgraded to a Temporal Cloud schedule/worker path

Required safety flags:

- `LIVE_TRADING_ENABLED=false`
- `AUTONOMOUS_EXECUTION_ENABLED=false`
- `AUTONOMOUS_LIVE_EXECUTION_ENABLED=false`
- `LEVERAGE_ENABLED=false`
- `LIVE_SHORTING_ENABLED=false`
- `FROZEN_VALIDATION_ENABLED=true`
- `FROZEN_VALIDATION_SPEC_VERSION=v0.6`
- `ALERT_ENABLE_REAL_DELIVERY=false`
- `AI_ENABLE_ESCALATION=false`
- `NEWS_ENABLE_OPENAI_WEB_FALLBACK=false`
- `DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS=false`
- `RUN_VERCEL_DASHBOARD_PREVIEW=`

Do not put broker, data, database, Temporal, OpenAI, Telegram, or Vercel credentials in frontend
environment variables, docs, evidence, images, or logs.

## Off-PC Setup

1. Provision a small server or VM with Docker and Docker Compose.
2. Clone the repository to `/opt/ai-trading-bot`.
3. Create `/opt/ai-trading-bot/.env` on the server using `.env.example` variable names only.
4. Set only paper broker/data credentials and the safety flags above.
5. Start the runner:

```bash
docker compose -f docker-compose.paper-runner.yml up -d --build frozen-paper-runner
```

6. Verify health:

```bash
docker compose -f docker-compose.paper-runner.yml exec -T frozen-paper-runner uv run python scripts/check_frozen_paper_runner_health.py --heartbeat .runtime/frozen_validation_runner/heartbeat.json --max-age-seconds 900
```

7. Re-run the M47B audit from the deployed host or against a copied durable heartbeat. Off-PC
   operation is not GO until a durable heartbeat or Temporal worker registration is confirmed.

For systemd-managed hosts, install `deploy/systemd/frozen-paper-runner.service`, set
`WorkingDirectory` to the checked-out repo path if needed, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frozen-paper-runner.service
sudo systemctl status frozen-paper-runner.service
```

## Failure Recovery

- If heartbeat is stale or missing, inspect container logs and restart the Docker Compose service.
- If broker reconciliation fails, pause new risk and investigate open orders/positions before
  restarting.
- If Tiingo verification fails, treat the validation as operationally blocked until data access is
  restored.
- If any live/autonomy/leverage/live-shorting flag drifts true, stop the runner and rotate or fix
  the server environment before restart.
- Do not change frozen strategy, risk, universe, data provider, or validation timestamps during
  recovery.

## Broker / Data / Safety

- Broker open orders: `0`
- Broker positions: `0`
- Reconciliation: `flat_zero_positions_zero_open_orders`
- Market data: `tiingo` `eod` `verified`
- Live trading enabled: `false`
- Autonomous live execution enabled: `false`
- Leverage enabled: `false`
- Live shorting enabled: `false`
- AI broker authority: `false`
- Level 4 ready: `false`

## Blockers

- `durable_off_pc_runner_not_active`

## Setup Commands

Build and start on the off-PC host:

```bash
docker compose -f docker-compose.paper-runner.yml up -d --build frozen-paper-runner
```

Health check:

```bash
docker compose -f docker-compose.paper-runner.yml exec -T frozen-paper-runner uv run python scripts/check_frozen_paper_runner_health.py --heartbeat .runtime/frozen_validation_runner/heartbeat.json --max-age-seconds 900
```

Stop:

```bash
docker compose -f docker-compose.paper-runner.yml down
```

Monitor heartbeat, broker reconciliation, Tiingo status, frozen hash drift, cycle evidence, incidents, and daily reports each trading day.
