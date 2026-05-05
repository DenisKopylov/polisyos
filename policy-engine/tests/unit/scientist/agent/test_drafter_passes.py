"""Tests for polisyos.scientist.agent._drafter_passes — deterministic checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from polisyos.scientist.agent._drafter_passes import _DrafterPassesMixin
from polisyos.scientist.agent.drafter_models import (
    FindingCategory,
    FindingSeverity,
    MultiPassConfig,
    PassExecution,
)
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class _PassesHarness(_DrafterPassesMixin):
    def __init__(self, *, config=None, code_verifier=None, memory=None):
        self._config = config or MultiPassConfig()
        self._code_verifier = code_verifier
        self._memory = memory

    def _parse_category(self, raw: str):
        from polisyos.scientist.agent.drafter_models import FindingCategory

        try:
            return FindingCategory(raw.strip().lower())
        except ValueError:
            return FindingCategory.OTHER

    def _parse_severity(self, raw: str):
        from polisyos.scientist.agent.drafter_models import FindingSeverity

        try:
            return FindingSeverity(raw.strip().lower())
        except ValueError:
            return FindingSeverity.MEDIUM


@pytest.fixture
def harness():
    return _PassesHarness()


def _make_draft(**overrides) -> DraftResult:
    defaults = dict(
        draft_id="d1",
        problem_frame_ref="pf1",
        narrative="policy",
        interventions=[],
        rationale="reason",
        confidence=0.8,
    )
    defaults.update(overrides)
    return DraftResult(**defaults)


def _make_frame(**overrides) -> ProblemFrame:
    defaults = dict(frame_id="f1", domain="d", problem_statement="p")
    defaults.update(overrides)
    return ProblemFrame(**defaults)


# ---------------------------------------------------------------------------
# _check_parameter_ranges
# ---------------------------------------------------------------------------


class TestCheckParameterRanges:
    def test_no_interventions(self, harness):
        draft = _make_draft(interventions=[])
        assert harness._check_parameter_ranges(draft) == []

    def test_valid_rate(self, harness):
        draft = _make_draft(interventions=[{"params": {"rate": 0.5}}])
        assert harness._check_parameter_ranges(draft) == []

    def test_rate_boundary_zero(self, harness):
        draft = _make_draft(interventions=[{"params": {"rate": 0.0}}])
        assert harness._check_parameter_ranges(draft) == []

    def test_rate_boundary_one(self, harness):
        draft = _make_draft(interventions=[{"params": {"rate": 1.0}}])
        assert harness._check_parameter_ranges(draft) == []

    def test_rate_out_of_range_high(self, harness):
        draft = _make_draft(interventions=[{"params": {"tax_rate": 1.5}}])
        findings = harness._check_parameter_ranges(draft)
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.HIGH
        assert findings[0].category == FindingCategory.PARAMETER_ERROR
        assert "1.5" in findings[0].description

    def test_rate_out_of_range_negative(self, harness):
        draft = _make_draft(interventions=[{"params": {"rate": -0.1}}])
        findings = harness._check_parameter_ranges(draft)
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.HIGH

    def test_non_numeric_rate(self, harness):
        draft = _make_draft(interventions=[{"params": {"rate": "abc"}}])
        findings = harness._check_parameter_ranges(draft)
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.MEDIUM
        assert "non-numeric" in findings[0].description

    def test_non_rate_param_ignored(self, harness):
        draft = _make_draft(interventions=[{"params": {"name": "test"}}])
        assert harness._check_parameter_ranges(draft) == []

    def test_parameters_key_alias(self, harness):
        draft = _make_draft(interventions=[{"parameters": {"rate": 1.5}}])
        findings = harness._check_parameter_ranges(draft)
        assert len(findings) == 1

    def test_no_params_key(self, harness):
        draft = _make_draft(interventions=[{"name": "test"}])
        assert harness._check_parameter_ranges(draft) == []


# ---------------------------------------------------------------------------
# _check_target_overlaps
# ---------------------------------------------------------------------------


class TestCheckTargetOverlaps:
    def test_no_overlap(self, harness):
        draft = _make_draft(
            interventions=[
                {"target_population": "group_a"},
                {"target_population": "group_b"},
            ]
        )
        assert harness._check_target_overlaps(draft) == []

    def test_overlap_detected(self, harness):
        draft = _make_draft(
            interventions=[
                {"target_population": "youth"},
                {"target_population": "Youth"},
            ]
        )
        findings = harness._check_target_overlaps(draft)
        assert len(findings) == 1
        assert findings[0].category == FindingCategory.TARGET_OVERLAP

    def test_dict_target_overlap(self, harness):
        draft = _make_draft(
            interventions=[
                {"target": {"age": 18, "gender": "male"}},
                {"target": {"gender": "male", "age": 18}},
            ]
        )
        findings = harness._check_target_overlaps(draft)
        assert len(findings) == 1

    def test_empty_interventions(self, harness):
        draft = _make_draft(interventions=[])
        assert harness._check_target_overlaps(draft) == []

    def test_no_target_fields(self, harness):
        draft = _make_draft(interventions=[{"name": "a"}, {"name": "b"}])
        assert harness._check_target_overlaps(draft) == []


# ---------------------------------------------------------------------------
# _execute_deterministic_checks
# ---------------------------------------------------------------------------


class TestExecuteDeterministicChecks:
    def test_clean_draft(self, harness):
        draft = _make_draft(interventions=[{"params": {"rate": 0.5}}])
        result = harness._execute_deterministic_checks(draft)
        assert result.executed is True
        assert result.pass_name == "deterministic_checks"
        assert result.findings == []

    def test_findings_aggregated(self, harness):
        draft = _make_draft(
            interventions=[
                {"params": {"rate": 1.5}, "target_population": "youth"},
                {"target_population": "Youth"},
            ]
        )
        result = harness._execute_deterministic_checks(draft)
        assert len(result.findings) >= 2  # 1 range + 1 overlap

    def test_uses_injected_tracer(self, monkeypatch):
        class _Span:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return None

        class _Tracer:
            def __init__(self) -> None:
                self.names: list[str] = []

            def start_as_current_span(self, name: str, attributes=None):
                del attributes
                self.names.append(name)
                return _Span()

        tracer = _Tracer()
        h = _PassesHarness()
        h._tracer = tracer
        monkeypatch.setattr(
            "polisyos.scientist.agent._drafter_passes._default_tracer",
            lambda: (_ for _ in ()).throw(
                AssertionError("global tracer lookup should not run when tracer is injected")
            ),
        )

        result = h._execute_deterministic_checks(_make_draft(interventions=[]))

        assert result.executed is True
        assert tracer.names == ["drafter.pass.deterministic_checks"]


# ---------------------------------------------------------------------------
# _augment_pass3_with_code_verification
# ---------------------------------------------------------------------------


class TestAugmentPass3:
    def test_no_verifier_passthrough(self, harness):
        pass3 = PassExecution(pass_name="p3", pass_number=3, executed=True)
        result = harness._augment_pass3_with_code_verification(
            pass3,
            draft=_make_draft(),
            problem_frame=_make_frame(),
        )
        assert result is pass3

    def test_not_executed_passthrough(self):
        h = _PassesHarness(code_verifier=MagicMock())
        pass3 = PassExecution(pass_name="p3", pass_number=3, executed=False)
        result = h._augment_pass3_with_code_verification(
            pass3,
            draft=_make_draft(),
            problem_frame=_make_frame(),
        )
        assert result is pass3

    def test_no_verification_code_passthrough(self):
        verifier = MagicMock()
        h = _PassesHarness(code_verifier=verifier)
        pass3 = PassExecution(
            pass_name="p3",
            pass_number=3,
            executed=True,
            verification_code=None,
            raw_llm_response=None,
        )
        with patch(
            "polisyos.scientist.agent._drafter_passes.VerificationCodeExtractor"
        ) as mock_extractor:
            mock_extractor.extract_from_llm_response.return_value = None
            result = h._augment_pass3_with_code_verification(
                pass3,
                draft=_make_draft(),
                problem_frame=_make_frame(),
            )
        assert result is pass3

    def test_passed_verification_passthrough(self):
        from polisyos.scientist.agent.code_verifier import VerificationStatus

        verifier = MagicMock()
        verification_result = MagicMock()
        verification_result.status = VerificationStatus.PASSED
        verification_result.passed = True
        verifier.execute.return_value = verification_result

        h = _PassesHarness(code_verifier=verifier)
        pass3 = PassExecution(
            pass_name="p3",
            pass_number=3,
            executed=True,
            verification_code="assert True",
        )
        result = h._augment_pass3_with_code_verification(
            pass3,
            draft=_make_draft(),
            problem_frame=_make_frame(),
        )
        assert result is pass3

    def test_failed_verification_adds_findings(self):
        from polisyos.scientist.agent.code_verifier import VerificationStatus

        verifier = MagicMock()
        verification_result = MagicMock()
        verification_result.status = VerificationStatus.FAILED
        verification_result.passed = False
        verification_result.execution_time_ms = 100
        verification_result.to_findings.return_value = [
            {"category": "parameter_error", "severity": "high", "description": "assertion failed"},
        ]
        verifier.execute.return_value = verification_result

        h = _PassesHarness(code_verifier=verifier)
        pass3 = PassExecution(
            pass_name="p3",
            pass_number=3,
            executed=True,
            verification_code="assert False",
            findings=[],
            confidence_adjustment=None,
        )
        result = h._augment_pass3_with_code_verification(
            pass3,
            draft=_make_draft(),
            problem_frame=_make_frame(),
        )
        assert len(result.findings) == 1
        assert result.findings[0].source_pass == "code_verification"
        assert result.confidence_adjustment == -0.03
