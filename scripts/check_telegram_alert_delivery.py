"""Run the gated Telegram alert-delivery smoke harness.

The script prints sanitized summary fields only. It never prints `.env`, bot tokens, chat IDs, raw
Telegram responses, broker secrets, database URLs, Temporal keys, or AI/news provider keys.
"""

from __future__ import annotations

import json

from packages.alerting.smoke import run_telegram_alert_smoke


def main() -> int:
    summary = run_telegram_alert_smoke()
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    if not summary.gates_loaded:
        return 0
    return 0 if summary.failure_codes == () else 1


if __name__ == "__main__":
    raise SystemExit(main())
