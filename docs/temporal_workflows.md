# Temporal Workflows

This document is a foundation placeholder for Temporal workflow design.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Temporal is required from v0.1, but Milestone 01 does not implement workers, workflows, schedules, activities, signals, or queries.

## Foundation Configuration

`config/temporal.yaml` defines the initial namespace, task queue names, schedule names, and retry defaults from the latest spec so later milestones can build workers and workflow skeletons against stable names.

## Required Boundary

Future workflow code must remain deterministic and call activities for side effects. Broker APIs, database writes, AI APIs, news APIs, alert sending, random values, and direct wall-clock reads belong in activities, not workflows.

## Current Milestone Status

- No Temporal SDK dependency is installed.
- No Temporal client is implemented.
- No worker process is implemented.
- No workflow code is implemented.
