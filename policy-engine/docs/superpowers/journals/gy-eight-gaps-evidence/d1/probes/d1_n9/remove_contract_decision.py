"""Discard the consulted full contract decision while retaining its real identity."""
from __future__ import annotations

import pytest

from polisyos.fabric.connectors.registry import ConnectorRegistry


def main() -> int:
    original = ConnectorRegistry.validate_fetch_result

    def ignore_contract_errors(self, **kwargs):
        measured = original(self, **kwargs)
        print(f"REMOVAL: keeping current contract {measured.contract_content_hash}, discarding errors {measured.errors!r}")
        return measured.model_copy(update={"errors": ()})

    ConnectorRegistry.validate_fetch_result = ignore_contract_errors
    return pytest.main([
        "-q", "-s",
        "tests/unit/runtime/quality/test_promotion_sequence.py::"
        "test_n9_measurement_refuses_out_of_contract_observations",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
