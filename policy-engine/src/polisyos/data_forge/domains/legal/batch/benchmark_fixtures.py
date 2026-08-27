"""Authority-neutral legal benchmark query fixtures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LegalSearchBenchmarkCase:
    """Authority-neutral query fixture supplied by Data Forge."""

    case_id: str
    query: str
    expected_actions: tuple[str, ...] = ()
    expected_norm_types: tuple[str, ...] = ()
    domain: str | None = None


_DEFAULT_SEARCH_CASES: tuple[LegalSearchBenchmarkCase, ...] = (
    LegalSearchBenchmarkCase(
        case_id="licensing_approvals",
        query="ліцензія дозвіл погодження",
        expected_actions=("requires", "grants", "approves"),
        expected_norm_types=("obligation", "permission", "procedure"),
    ),
    LegalSearchBenchmarkCase(
        case_id="reporting_compliance",
        query="подати звіт повідомити орган",
        expected_actions=("requires", "delegates"),
        expected_norm_types=("obligation", "procedure"),
    ),
    LegalSearchBenchmarkCase(
        case_id="entry_force_amendment",
        query="набирає чинності внесення змін",
        expected_actions=("enters_into_force", "amends", "repeals"),
        expected_norm_types=("entry_into_force", "amendment", "repeal"),
    ),
    LegalSearchBenchmarkCase(
        case_id="thresholds",
        query="відсоток грн мінімальний розмір",
        expected_actions=("sets_threshold",),
        expected_norm_types=("obligation", "procedure"),
    ),
)


def legal_search_benchmark_cases() -> tuple[LegalSearchBenchmarkCase, ...]:
    """Return the complete frozen query-fixture denominator."""
    return _DEFAULT_SEARCH_CASES


__all__ = ["LegalSearchBenchmarkCase", "legal_search_benchmark_cases"]
