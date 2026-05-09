#!/usr/bin/env python
"""Run the dashboard/control-plane dev runtime smoke harness."""

from __future__ import annotations

import json

from packages.control_plane.runtime import run_dashboard_control_plane_smoke


def main() -> int:
    summary = run_dashboard_control_plane_smoke()
    print(json.dumps(summary.to_sanitized_dict(), indent=2, sort_keys=True))
    if summary.refused or summary.failure_codes:
        return 1
    if not summary.snapshot_built or not summary.safe_controls_validated:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
