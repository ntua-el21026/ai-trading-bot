"""Start one Temporal worker for a configured task queue."""

from __future__ import annotations

import argparse

from apps.workers.app.worker import run_worker_sync, task_queue_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a Temporal worker for one task queue.")
    parser.add_argument(
        "--task-queue",
        required=True,
        choices=task_queue_names(),
        help="Configured Temporal task queue to poll.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_worker_sync(args.task_queue)


if __name__ == "__main__":
    main()
