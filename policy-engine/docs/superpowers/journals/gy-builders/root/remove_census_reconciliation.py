"""Remove the executed reconciliation property while keeping its public markers."""

from __future__ import annotations

import pytest

from tools.quality.validation import check_multilingual_locale_census as gate


def removed(first: object, second: object) -> None:
    """Intentionally deleted decisive comparison for this isolated removal probe."""


gate.reconcile_catalogues = removed
raise SystemExit(pytest.main([
    "tests/repo_quality/tools/test_multilingual_locale_census.py::"
    "test_corrupting_one_actual_parser_result_fails_independent_comparison[a]",
    "-o", "addopts=", "-q",
]))
