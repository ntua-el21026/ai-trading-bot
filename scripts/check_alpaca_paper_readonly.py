#!/usr/bin/env python
"""Run the opt-in Alpaca paper read-only smoke check with sanitized output."""

from __future__ import annotations

import json

from pydantic import ValidationError

from packages.broker.alpaca import AlpacaClientError
from packages.broker.smoke import (
    AlpacaPaperReadOnlySmokeGateError,
    run_alpaca_paper_readonly_smoke,
)


def main() -> int:
    try:
        summary = run_alpaca_paper_readonly_smoke()
    except AlpacaPaperReadOnlySmokeGateError as exc:
        print("Alpaca paper read-only smoke gates are not satisfied.")
        for gate in exc.failed_gates:
            print(f"- {gate}")
        return 2
    except AlpacaClientError as exc:
        print("Alpaca paper read-only smoke failed before all read-only checks completed.")
        print(f"- broker_error_code: {exc.code}")
        print(f"- retryable: {str(exc.retryable).lower()}")
        print(f"- ambiguous: {str(exc.ambiguous).lower()}")
        return 1
    except ValidationError:
        print("Alpaca paper read-only smoke failed while normalizing a read-only payload.")
        return 1
    except Exception as exc:
        print("Alpaca paper read-only smoke failed unexpectedly.")
        print(f"- error_type: {type(exc).__name__}")
        return 1

    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
