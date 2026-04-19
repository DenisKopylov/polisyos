"""Tests for individual evidence gatherers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.ir.analytics.literature import EnvironmentAuditReport, LiteratureCausalPrior
from polisyos.scientist.cross_graph.gatherers.academic import AcademicGatherer, _serialize_value
from polisyos.scientist.cross_graph.gatherers.dataset import DatasetGatherer
from polisyos.scientist.cross_graph.gatherers.legal import LegalGatherer
from polisyos.scientist.cross_graph.gatherers.transport import TransportGatherer


def _need() -> MagicMock:
    n = MagicMock()
    n.need_id = "n1"
    n.need_type.value = "metric"
    return n


class TestAcademicGatherer:
    def test_dimension(self):
        assert AcademicGatherer().dimension == "academic"

    def test_no_query_returns_insufficient(self):
        g = AcademicGatherer()
        result = g.assess(_need(), concepts=[], context={})
        assert result.status == "insufficient"
        assert result.confidence < 0.5

    def test_with_compiler_fn(self):
        mock_result = MagicMock()
        mock_result.evidence_status.value = "supported"
        mock_result.transport_confidence = 0.9
        mock_result.diagnostics = []
        mock_result.provenance_refs = ["ref1"]
        mock_result.transport_reasons = ["reason1"]

        g = AcademicGatherer()
        result = g.assess(
            _need(), concepts=[], context={
                "academic_query": MagicMock(),
                "_assess_academic_need": lambda *a, **kw: mock_result,
            },
        )
        assert result.status == "supported"
        assert result.confidence == 0.9
        assert result.metadata["transport_reasons"] == ["reason1"]

    def test_environment_audit_metadata_passthrough_and_advisory_diagnostic(self):
        mock_result = MagicMock()
        mock_result.evidence_status.value = "supported"
        mock_result.transport_confidence = 0.9
        mock_result.diagnostics = []
        mock_result.provenance_refs = ["ref1"]
        mock_result.transport_reasons = []

        audit = EnvironmentAuditReport(
            status="warning",
            n_environments=2,
            ks_passed=False,
            ks_rejected_variables=[0],
            icp_run=True,
            icp_passed=False,
            variant_features=[1],
            warnings=["ks_detected_distribution_shift"],
        )
        g = AcademicGatherer()
        result = g.assess(
            _need(),
            concepts=[],
            context={
                "academic_query": MagicMock(),
                "_assess_academic_need": lambda *a, **kw: mock_result,
                "literature_prior": LiteratureCausalPrior(),
                "literature_prior_ref": "artifact://prior-1",
                "environment_audit": audit,
                "environment_audit_summary": {
                    "status": "warning",
                    "ks_passed": False,
                    "ks_rejected_variables": [0],
                    "variant_features": [1],
                },
            },
        )

        assert result.status == "supported"
        assert result.metadata["literature_prior_ref"] == "artifact://prior-1"
        assert result.metadata["environment_audit_summary"]["status"] == "warning"
        assert result.diagnostics
        assert (
            result.diagnostics[0].code
            == "cross_graph.academic.environment_audit_advisory"
        )

    def test_serialize_value_assertion_is_not_swallowed(self):
        class _BrokenPayload:
            def model_dump_json(self):
                return "{}"

            def model_dump(self, *, mode):
                del mode
                raise AssertionError("serialization invariant failed")

        with pytest.raises(AssertionError, match="serialization invariant failed"):
            _serialize_value(_BrokenPayload())


class TestDatasetGatherer:
    def test_dimension(self):
        assert DatasetGatherer().dimension == "dataset"

    def test_no_registry_returns_unknown(self):
        g = DatasetGatherer()
        result = g.assess(_need(), concepts=[], context={})
        assert "unknown" in result.status.lower()


class TestLegalGatherer:
    def test_dimension(self):
        assert LegalGatherer().dimension == "legal"

    def test_no_adapter_returns_unknown(self):
        g = LegalGatherer()
        result = g.assess(_need(), concepts=[], context={})
        assert "unknown" in result.status.lower()


class TestTransportGatherer:
    def test_dimension(self):
        assert TransportGatherer().dimension == "transport"

    def test_no_fn_returns_unsupported(self):
        g = TransportGatherer()
        result = g.assess(_need(), concepts=[], context={})
        assert "unsupported" in result.status.lower()
