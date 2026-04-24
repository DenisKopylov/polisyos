"""FalsificationReport — unified container for causal falsification tests.

Aggregates the results of placebo, refutation, independence, and invariance
tests into a single machine-readable object.  Used by the DiagnosticDashboard
and the QualityScoreAggregator.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class FalsificationTestKind(str, Enum):
    """Category of falsification / refutation test."""

    PLACEBO_TREATMENT = "placebo_treatment"
    """Replaces treatment with a random placebo and checks that estimated effect ≈ 0."""

    RANDOM_COMMON_CAUSE = "random_common_cause"
    """Adds a random covariate as a common cause; estimate should not change significantly."""

    DATA_SUBSET = "data_subset"
    """Re-estimates on a random subset; checks stability of the point estimate."""

    BOOTSTRAP_REFUTATION = "bootstrap_refutation"
    """Bootstraps the dataset and checks that the estimate is stable across resamples."""

    INDEPENDENCE_TEST = "independence_test"
    """Tests conditional independence assumptions (HSIC, KCI, partial correlation)."""

    INVARIANCE_TEST = "invariance_test"
    """Tests invariance of causal coefficients across environments (ICP, KS)."""

    PARALLEL_TRENDS = "parallel_trends"
    """Pre-treatment slope equality test for DiD identification."""

    EXCLUSION_RESTRICTION = "exclusion_restriction"
    """Over-identification / Sargan test for IV exclusion restriction."""


class FalsificationTest(BaseModel):
    """Result of a single falsification / refutation test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_name: str
    """Human-readable name of the test (e.g. 'placebo_treatment_X')."""

    test_kind: FalsificationTestKind
    """Category of the test."""

    passed: bool
    """True when the test did NOT find evidence against the null (identification holds)."""

    statistic: float | None = None
    """Test statistic value (e.g. t-statistic, Hausman statistic)."""

    p_value: float | None = None
    """p-value of the test (high p-value = no evidence of violation)."""

    effect_ratio: float | None = None
    """For placebo tests: placebo_effect / original_effect.  Should be near 0."""

    interpretation: str = ""
    """Human-readable interpretation of the test result."""

    is_critical: bool = False
    """True when failure of this test blocks reliable estimation."""


class FalsificationReport(BaseModel):
    """Aggregated results of all falsification tests run for a causal analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tests: tuple[FalsificationTest, ...] = ()
    """All falsification tests that were executed."""

    n_passed: int = 0
    """Number of tests that passed."""

    n_failed: int = 0
    """Number of tests that failed."""

    overall_passed: bool = True
    """True when no *critical* tests failed."""

    critical_failures: tuple[str, ...] = ()
    """Names of critical tests that failed (blocks downstream quality score)."""

    @classmethod
    def from_tests(cls, tests: list[FalsificationTest]) -> FalsificationReport:
        """Build a FalsificationReport from a list of FalsificationTest results."""
        n_passed = sum(1 for t in tests if t.passed)
        n_failed = sum(1 for t in tests if not t.passed)
        failures = tuple(t.test_name for t in tests if not t.passed and t.is_critical)
        return cls(
            tests=tuple(tests),
            n_passed=n_passed,
            n_failed=n_failed,
            overall_passed=(len(failures) == 0),
            critical_failures=failures,
        )

    @classmethod
    def from_dowhy_refute_outputs(
        cls,
        node_outputs: dict[str, dict],
        *,
        alpha: float = 0.05,
    ) -> FalsificationReport:
        """Build from CausalEngine node_outputs that contain DoWhyRefute results.

        Looks for any node output that has a 'refutation_result' key.
        """
        tests: list[FalsificationTest] = []
        for node_id, outputs in node_outputs.items():
            if not isinstance(outputs, dict):
                continue
            refute = outputs.get("refutation_result")
            if not isinstance(refute, dict):
                continue
            test_name = refute.get("test_name", node_id)
            p_val: float | None = refute.get("p_value")
            stat: float | None = refute.get("statistic")
            passed = bool(refute.get("passed", True))
            kind_str = refute.get("test_kind", "data_subset")
            try:
                kind = FalsificationTestKind(kind_str)
            except ValueError:
                kind = FalsificationTestKind.DATA_SUBSET
            tests.append(
                FalsificationTest(
                    test_name=test_name,
                    test_kind=kind,
                    passed=passed,
                    statistic=stat,
                    p_value=p_val,
                    interpretation=refute.get("interpretation", ""),
                    is_critical=kind
                    in {
                        FalsificationTestKind.PLACEBO_TREATMENT,
                        FalsificationTestKind.INDEPENDENCE_TEST,
                    },
                )
            )
        return cls.from_tests(tests)

    @classmethod
    def from_parallel_trends(cls, result: dict) -> FalsificationReport:
        """Build a single-test FalsificationReport from a ParallelTrendsCheck result dict."""
        passed = bool(result.get("passed", True))
        test = FalsificationTest(
            test_name="parallel_trends_check",
            test_kind=FalsificationTestKind.PARALLEL_TRENDS,
            passed=passed,
            statistic=result.get("statistic"),
            p_value=result.get("p_value"),
            interpretation=("Pre-treatment slope equality: " + ("passed" if passed else "FAILED")),
            is_critical=True,
        )
        return cls.from_tests([test])


__all__ = [
    "FalsificationReport",
    "FalsificationTest",
    "FalsificationTestKind",
]
