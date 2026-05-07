#!/usr/bin/env python
"""Run the explicitly gated Alpaca paper order-lifecycle smoke harness."""

from __future__ import annotations

import json

from pydantic import ValidationError

from packages.broker.alpaca import AlpacaClientError
from packages.broker.order_lifecycle_smoke import (
    run_alpaca_paper_order_lifecycle_smoke,
)


def main() -> int:
    try:
        summary = run_alpaca_paper_order_lifecycle_smoke()
    except AlpacaClientError as exc:
        print("Alpaca paper order-lifecycle smoke failed with a sanitized broker error.")
        print(f"- broker_error_code: {exc.code}")
        print(f"- retryable: {str(exc.retryable).lower()}")
        print(f"- ambiguous: {str(exc.ambiguous).lower()}")
        return 1
    except ValidationError:
        print("Alpaca paper order-lifecycle smoke failed while normalizing a sanitized payload.")
        return 1
    except Exception as exc:
        print("Alpaca paper order-lifecycle smoke failed unexpectedly.")
        print(f"- error_type: {type(exc).__name__}")
        return 1

    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    if summary.refused and not summary.write_operations_attempted:
        return 0
    if summary.broker_ambiguity_detected:
        return 1
    if summary.refused and summary.write_operations_attempted:
        return 1
    return 0 if summary.broker_reconciliation_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
