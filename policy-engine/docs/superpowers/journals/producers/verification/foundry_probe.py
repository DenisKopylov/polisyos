"""Remove diagnostic non-decisiveness in memory and run the unchanged negative."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path.cwd()))

from tools.quality.validation import check_layer3_gy_value_gate_contract as owner


def main() -> int:
    """Keep real recomputation and markers while giving diagnostics governing effect."""
    original = owner._validate_foundry_dependency_discriminant

    def remove_separation(**kwargs: object) -> owner.ValueGateValidationResult:
        result = original(**kwargs)
        return replace(
            result,
            governing_issues=result.governing_issues + result.ambient_findings,
        )

    owner._validate_foundry_dependency_discriminant = remove_separation
    return int(
        pytest.main(
            [
                "tests/unit/runtime/quality/test_value_gate.py::"
                "test_n8_dependency_discriminant_matching_supplied_fail_is_ambient_only",
                "-q",
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
