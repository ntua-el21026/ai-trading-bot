"""Run a fake/local paper dry-run scenario.

This script intentionally never calls broker, AI/news, alert, market-data, Temporal, or managed
database services. It uses in-memory SQLite and fake adapters only.
"""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper import default_dry_run_input, run_paper_dry_run

SAFE_MODE = "fake-local"
WARNING = "This is a fake/local dry run. No broker orders are submitted."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a fake/local paper dry-run scenario.")
    parser.add_argument("--scenario", default="happy_path", help="Dry-run scenario ID.")
    parser.add_argument(
        "--mode",
        default=SAFE_MODE,
        help="Only fake-local mode is supported.",
    )
    args = parser.parse_args(argv)

    if args.mode != SAFE_MODE:
        print("Refusing non-fake paper dry-run mode.", file=sys.stderr)
        return 2

    print(WARNING)
    result = run_paper_dry_run(default_dry_run_input(args.scenario))
    print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
