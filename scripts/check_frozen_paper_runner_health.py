#!/usr/bin/env python3
"""Check frozen paper runner heartbeat freshness without printing secrets."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--heartbeat",
        default=".runtime/frozen_validation_runner/heartbeat.json",
    )
    parser.add_argument("--max-age-seconds", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.heartbeat)
    status = "missing"
    age_seconds: float | None = None
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_timestamp = payload.get("timestamp")
            if isinstance(raw_timestamp, str):
                timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                age_seconds = max(
                    0.0,
                    (datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds(),
                )
                status = "fresh" if age_seconds <= args.max_age_seconds else "stale"
            else:
                status = "stale"
        except (json.JSONDecodeError, ValueError):
            status = "stale"
    print(
        json.dumps(
            {
                "heartbeat": str(path),
                "status": status,
                "age_seconds": age_seconds,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "fresh" else 1


if __name__ == "__main__":
    sys.exit(main())
