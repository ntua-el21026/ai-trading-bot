"""Dry-run helper for future Temporal schedule seeding.

Milestone 03 intentionally does not create or activate production schedules. This script prints
the configured schedule contracts so a later milestone can replace the dry run with explicit,
reviewed Temporal schedule creation.
"""

from __future__ import annotations

from packages.core.config import load_app_config


def main() -> None:
    config = load_app_config().temporal
    schedules = config.schedules.model_dump()
    print("Temporal schedule seeding is dry-run only in Milestone 03.")
    print(f"namespace={config.namespace}")
    for name, cron in schedules.items():
        print(f"{name}={cron}")


if __name__ == "__main__":
    main()
