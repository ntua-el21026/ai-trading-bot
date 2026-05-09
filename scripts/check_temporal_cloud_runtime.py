#!/usr/bin/env python
"""Run the gated Temporal Cloud dev runtime smoke harness."""

from __future__ import annotations

import json

from apps.workers.app.temporal_cloud_smoke import run_temporal_cloud_smoke


def main() -> int:
    summary = run_temporal_cloud_smoke()
    print(json.dumps(summary.to_sanitized_dict(), indent=2, sort_keys=True))
    if summary.refused and not summary.gates_loaded:
        return 0
    if summary.failure_codes:
        return 1
    return 0 if summary.workflow_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
