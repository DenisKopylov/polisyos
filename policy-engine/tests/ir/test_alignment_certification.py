from __future__ import annotations

import pytest

from polisyos.ir.analytics.alignment_certification import (
    AlignmentCertificate,
    AlignmentCertificateType,
    AlignmentCertificationPolicy,
    OuterObjectiveResult,
    compute_outer_objective,
    run_outer_search,
)


def _cert(
    cert_type: AlignmentCertificateType = AlignmentCertificateType.EXACT,
    confidence: float = 0.8,
) -> AlignmentCertificate:
    return AlignmentCertificate(
        cert_type=cert_type,
        source_variable="src",
        target_variable="tgt",
        confidence=confidence,
    )


class TestAlignmentCertificationPolicy:
    def test_tau_min_lower_bound(self) -> None:
        with pytest.raises(ValueError, match="tau_min"):
            AlignmentCertificationPolicy(tau_min=0.50)

    def test_tau_min_upper_bound(self) -> None:
        with pytest.raises(ValueError, match="tau_min"):
            AlignmentCertificationPolicy(tau_min=0.99)

    def test_tau_min_at_bounds(self) -> None:
        AlignmentCertificationPolicy(tau_min=0.55)
        AlignmentCertificationPolicy(tau_min=0.95)

    def test_validate_chain_passes_above_tau(self) -> None:
        policy = AlignmentCertificationPolicy(tau_min=0.60)
        chain = [_cert(confidence=0.9), _cert(confidence=0.85)]
        result = policy.validate_chain(chain)
        assert result.passed
        assert result.effective_confidence > 0.6

    def test_validate_chain_fails_below_tau(self) -> None:
        policy = AlignmentCertificationPolicy(tau_min=0.90)
        chain = [_cert(confidence=0.5), _cert(confidence=0.4)]
        result = policy.validate_chain(chain)
        assert not result.passed

    def test_validate_chain_rejects_disallowed_type(self) -> None:
        policy = AlignmentCertificationPolicy(
            allowed_types=(AlignmentCertificateType.EXACT,),
            tau_min=0.55,
        )
        chain = [_cert(cert_type=AlignmentCertificateType.PROXY_BUNDLE, confidence=0.99)]
        result = policy.validate_chain(chain)
        assert not result.passed
        assert any("not allowed" in v for v in result.violations)

    def test_validate_chain_max_length(self) -> None:
        policy = AlignmentCertificationPolicy(max_chain_length=2, tau_min=0.55)
        chain = [_cert(confidence=0.9) for _ in range(4)]
        result = policy.validate_chain(chain)
        assert not result.passed
        assert any("exceeds" in v for v in result.violations)
        assert result.long_chain_warning is not None

    def test_validate_empty_chain(self) -> None:
        policy = AlignmentCertificationPolicy(tau_min=0.55)
        result = policy.validate_chain([])
        assert not result.passed
        assert result.effective_confidence == 0.0

    def test_harmonic_composition(self) -> None:
        policy = AlignmentCertificationPolicy(
            composition_rule="harmonic", tau_min=0.55
        )
        chain = [_cert(confidence=0.8), _cert(confidence=0.6)]
        result = policy.validate_chain(chain)
        expected = 2 * 0.8 * 0.6 / (0.8 + 0.6)
        assert result.effective_confidence == pytest.approx(expected, abs=0.01)

    def test_multiplicative_composition(self) -> None:
        policy = AlignmentCertificationPolicy(
            composition_rule="multiplicative", tau_min=0.55
        )
        chain = [_cert(confidence=0.8), _cert(confidence=0.7)]
        result = policy.validate_chain(chain)
        assert result.effective_confidence == pytest.approx(0.56, abs=0.01)


class TestOuterObjective:
    def test_perfect_coverage_zero_conflict(self) -> None:
        assert compute_outer_objective(1.0, 0.0, 1.0) == 1.0

    def test_conflict_reduces_score(self) -> None:
        assert compute_outer_objective(0.8, 0.3, 1.0) < 0.8

    def test_lambda_amplifies_conflict(self) -> None:
        s1 = compute_outer_objective(0.8, 0.3, 1.0)
        s2 = compute_outer_objective(0.8, 0.3, 2.0)
        assert s2 < s1


class TestOuterSearch:
    def test_search_returns_best(self) -> None:
        def evaluator(policy: AlignmentCertificationPolicy) -> OuterObjectiveResult:
            score = 1.0 - abs(policy.tau_min - 0.70)
            return OuterObjectiveResult(
                score=score,
                coverage=0.9,
                conflict_norm=0.1,
                lambda_conflict=1.0,
                config=policy,
                is_feasible=True,
            )

        result = run_outer_search(evaluator)
        assert result.configs_evaluated > 0
        assert result.best_config.tau_min == pytest.approx(0.70)

    def test_search_respects_max_solves(self) -> None:
        call_count = 0

        def evaluator(policy: AlignmentCertificationPolicy) -> OuterObjectiveResult:
            nonlocal call_count
            call_count += 1
            return OuterObjectiveResult(
                score=0.5,
                coverage=0.5,
                conflict_norm=0.0,
                lambda_conflict=1.0,
                config=policy,
                is_feasible=True,
            )

        result = run_outer_search(evaluator)
        assert result.configs_evaluated <= 48
        assert result.truncated or result.configs_evaluated <= 48
