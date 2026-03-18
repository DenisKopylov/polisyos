"""Tests for QueryValidationReport IR schema."""
import pytest
from pydantic import ValidationError

from polisyos.ir.analytics.query_validation_report import (
    QueryValidationReport,
    ValidationError as VError,
    ValidationIssue,
    ValidationSeverity,
    ValidationWarning,
)


# ---------------------------------------------------------------------------
# ValidationSeverity
# ---------------------------------------------------------------------------


class TestValidationSeverity:
    def test_all_values_are_str(self):
        for s in ValidationSeverity:
            assert isinstance(s.value, str)

    def test_expected_values_exist(self):
        values = {s.value for s in ValidationSeverity}
        assert {"error", "warning", "info"} == values


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------


class TestValidationError:
    def test_basic_creation(self):
        err = VError(code="GRAPH_CYCLE", message="Graph contains a cycle")
        assert err.code == "GRAPH_CYCLE"
        assert err.message == "Graph contains a cycle"
        assert err.severity == ValidationSeverity.ERROR
        assert err.context == {}

    def test_with_context(self):
        err = VError(
            code="MISSING_TREATMENT",
            message="Treatment 'T' not in graph nodes",
            context={"treatment": "T", "available_nodes": ["X", "Y"]},
        )
        assert err.context["treatment"] == "T"

    def test_frozen_rejects_mutation(self):
        err = VError(code="X", message="x")
        with pytest.raises((TypeError, Exception)):
            err.code = "Y"

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            VError(code="X", message="x", surprise="oops")

    def test_round_trip_json(self):
        err = VError(code="S_NODE_DANGLING", message="S-node references unknown variable 'Z'")
        data = err.model_dump(mode="json")
        restored = VError.model_validate(data)
        assert restored.code == "S_NODE_DANGLING"
        assert restored.severity == ValidationSeverity.ERROR


# ---------------------------------------------------------------------------
# ValidationWarning
# ---------------------------------------------------------------------------


class TestValidationWarning:
    def test_basic_creation(self):
        w = ValidationWarning(code="LOW_SAMPLE_SIZE", message="n_obs < 100 may affect reliability")
        assert w.severity == ValidationSeverity.WARNING
        assert w.code == "LOW_SAMPLE_SIZE"

    def test_frozen_rejects_mutation(self):
        w = ValidationWarning(code="X", message="x")
        with pytest.raises((TypeError, Exception)):
            w.message = "changed"

    def test_round_trip_json(self):
        w = ValidationWarning(code="DOMAIN_LABEL_MISMATCH", message="Domain labels differ")
        data = w.model_dump(mode="json")
        restored = ValidationWarning.model_validate(data)
        assert restored.code == "DOMAIN_LABEL_MISMATCH"
        assert restored.severity == ValidationSeverity.WARNING


# ---------------------------------------------------------------------------
# QueryValidationReport
# ---------------------------------------------------------------------------


class TestQueryValidationReport:
    def test_valid_empty_report(self):
        report = QueryValidationReport(is_valid=True)
        assert report.is_valid is True
        assert report.errors == ()
        assert report.warnings == ()
        assert report.query_str == ""
        assert report.checked_at == ""

    def test_invalid_report_with_errors(self):
        err = VError(code="MISSING_OUTCOME", message="Outcome 'Y' not in graph")
        report = QueryValidationReport(is_valid=False, errors=(err,))
        assert report.is_valid is False
        assert report.has_errors() is True
        assert report.has_warnings() is False

    def test_valid_report_with_warnings(self):
        w = ValidationWarning(code="PROXY_USED", message="Proxy variable substituted")
        report = QueryValidationReport(is_valid=True, warnings=(w,))
        assert report.has_errors() is False
        assert report.has_warnings() is True

    def test_has_errors_false_when_no_errors(self):
        report = QueryValidationReport(is_valid=True)
        assert report.has_errors() is False

    def test_has_warnings_false_when_no_warnings(self):
        report = QueryValidationReport(is_valid=True)
        assert report.has_warnings() is False

    def test_to_summary_valid(self):
        report = QueryValidationReport(is_valid=True)
        summary = report.to_summary()
        assert "VALID" in summary

    def test_to_summary_invalid_with_error(self):
        err = VError(code="GRAPH_CYCLE", message="cycle detected")
        report = QueryValidationReport(is_valid=False, errors=(err,))
        summary = report.to_summary()
        assert "INVALID" in summary
        assert "GRAPH_CYCLE" in summary
        assert "1 error" in summary

    def test_to_summary_valid_with_warnings(self):
        w1 = ValidationWarning(code="WARN_A", message="a")
        w2 = ValidationWarning(code="WARN_B", message="b")
        report = QueryValidationReport(is_valid=True, warnings=(w1, w2))
        summary = report.to_summary()
        assert "VALID" in summary
        assert "2 warning" in summary
        assert "WARN_A" in summary

    def test_full_creation(self):
        err = VError(code="MISSING_TREATMENT", message="T not in graph")
        w = ValidationWarning(code="LOW_N", message="Small sample", context={"n": 50})
        report = QueryValidationReport(
            is_valid=False,
            errors=(err,),
            warnings=(w,),
            query_str="P(Y|do(T))",
            checked_at="2026-03-16T12:00:00Z",
        )
        assert report.query_str == "P(Y|do(T))"
        assert report.checked_at == "2026-03-16T12:00:00Z"
        assert len(report.errors) == 1
        assert len(report.warnings) == 1

    def test_frozen_rejects_mutation(self):
        report = QueryValidationReport(is_valid=True)
        with pytest.raises((TypeError, Exception)):
            report.is_valid = False

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            QueryValidationReport(is_valid=True, mystery_field="oops")

    def test_round_trip_json(self):
        err = VError(code="E1", message="error one", context={"var": "X"})
        w = ValidationWarning(code="W1", message="warning one")
        report = QueryValidationReport(
            is_valid=False,
            errors=(err,),
            warnings=(w,),
            query_str="Q",
            checked_at="2026-03-16T00:00:00Z",
        )
        data = report.model_dump(mode="json")
        restored = QueryValidationReport.model_validate(data)
        assert restored.is_valid is False
        assert len(restored.errors) == 1
        assert restored.errors[0].code == "E1"
        assert restored.errors[0].context == {"var": "X"}
        assert len(restored.warnings) == 1
        assert restored.warnings[0].severity == ValidationSeverity.WARNING
