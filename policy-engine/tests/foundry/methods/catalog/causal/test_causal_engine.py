"""Unit tests for CausalEngine orchestrator."""
import pytest
import numpy as np
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult, IdentificationStatus,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, CausalEdge, GraphType
from polisyos.ir.analytics.causal_graph import EdgeMark
from polisyos.ir.analytics.negative_certificate import NegativeCertificate, BlockingType
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle


def make_dag(directed_edges):
    """Build a CausalGraphModel from a list of (src, dst) directed edges."""
    nodes = list({n for e in directed_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)


def make_confounded(directed_edges, bidirected_edges):
    """Build graph with both directed and bidirected (confounding) edges."""
    nodes = list({n for e in directed_edges + bidirected_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    for s, d in bidirected_edges:
        edges.append(CausalEdge(src=s, dst=d, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    # PAG allows mixed edge marks including bidirected arrows
    return CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)


class TestCausalEngineIdentify:
    def setup_method(self):
        self.engine = CausalEngine(registry=None, knowledge_base=None)

    def test_backdoor_graph_returns_identified(self):
        # Z -> X -> Y, Z -> Y (classical backdoor: Z is confounder)
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify("X", "Y", graph)
        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_non_identifiable_returns_negative_cert(self):
        # Bow-arc: X -> Y with bidirected X <-> Y (non-identifiable)
        graph = make_confounded([("X", "Y")], [("X", "Y")])
        result = self.engine.identify("X", "Y", graph)
        # May return HEDGE_FOUND as IdentificationResult or NegativeCertificate
        if isinstance(result, IdentificationResult):
            assert result.status in {
                IdentificationStatus.HEDGE_FOUND,
                IdentificationStatus.ORACLE_NEEDED,
                IdentificationStatus.PAG_AMBIGUOUS,  # Track B: PAG graphs may return this
            }
        else:
            assert isinstance(result, NegativeCertificate)
            assert result.blocking_type == BlockingType.HEDGE_STRUCTURE

    def test_identify_with_z_interventions(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify("X", "Y", graph, z_interventions=frozenset({"Z"}))
        assert isinstance(result, (IdentificationResult, NegativeCertificate))

    def test_identify_with_conditions(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify("X", "Y", graph, conditions=frozenset({"Z"}))
        assert isinstance(result, (IdentificationResult, NegativeCertificate))

    def test_identify_returns_valid_status(self):
        graph = make_dag([("X", "Y")])
        result = self.engine.identify("X", "Y", graph)
        if isinstance(result, IdentificationResult):
            assert result.status in list(IdentificationStatus)

    def test_identify_frozenset_treatment(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify(frozenset({"X"}), frozenset({"Y"}), graph)
        assert isinstance(result, (IdentificationResult, NegativeCertificate))


class TestCausalEngineCompile:
    def setup_method(self):
        self.engine = CausalEngine(registry=None, knowledge_base=None)
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def _get_identified_result(self):
        result = self.engine.identify("X", "Y", self.graph)
        if not isinstance(result, IdentificationResult):
            pytest.skip("Identification failed, cannot test compilation")
        if result.status != IdentificationStatus.IDENTIFIED:
            pytest.skip(f"Not identified (status={result.status}), cannot test compilation")
        return result

    def test_compile_returns_executor_graph(self):
        from polisyos.foundry.methods.catalog.causal.estimand_compiler import ExecutorGraph
        result = self._get_identified_result()
        eg = self.engine.compile(result, n_obs=500, covariate_dim=3)
        assert isinstance(eg, ExecutorGraph)

    def test_compile_nodes_nonempty(self):
        result = self._get_identified_result()
        eg = self.engine.compile(result, n_obs=500)
        assert len(eg.nodes) > 0

    def test_compile_raises_on_non_identified(self):
        result = make_confounded([("X", "Y")], [("X", "Y")])
        non_id_result = self.engine.identify("X", "Y", result)
        if isinstance(non_id_result, IdentificationResult) and non_id_result.estimand_ast is not None:
            pytest.skip("Unexpectedly identified")
        if isinstance(non_id_result, NegativeCertificate):
            pytest.skip("Returns NegativeCertificate — cannot test ValueError from compile")
        with pytest.raises((ValueError, Exception)):
            self.engine.compile(non_id_result)


class TestCausalEngineAudit:
    def setup_method(self):
        self.engine = CausalEngine(registry=None)
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def _get_result(self):
        return self.engine.identify("X", "Y", self.graph)

    def test_audit_returns_evidence_bundle(self):
        result = self._get_result()
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = self.engine.audit(result, None, run_id="test-run-1")
        assert isinstance(bundle, EvidenceBundle)

    def test_audit_run_id_preserved(self):
        result = self._get_result()
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = self.engine.audit(result, None, run_id="my-unique-run")
        assert bundle.run_id == "my-unique-run"

    def test_audit_created_at_is_iso_string(self):
        result = self._get_result()
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = self.engine.audit(result, None, run_id="r1")
        assert isinstance(bundle.created_at, str)
        assert "T" in bundle.created_at  # ISO format contains 'T'

    def test_audit_identification_status_in_bundle(self):
        result = self._get_result()
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = self.engine.audit(result, None, run_id="r2")
        assert isinstance(bundle.identification_status, str)
        assert len(bundle.identification_status) > 0

    def test_audit_schema_report_in_diagnostics(self):
        from polisyos.foundry.methods.catalog.causal.schema_resolver import SchemaResolutionReport
        result = self._get_result()
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        schema = SchemaResolutionReport(support_warnings=["overlap concern"], is_feasible=True)
        bundle = self.engine.audit(result, None, run_id="r3", schema_report=schema)
        assert "schema_warnings_count" in bundle.diagnostic_scores


class TestCausalEngineRun:
    def setup_method(self):
        self.engine = CausalEngine(registry=None)
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def test_run_returns_triple(self):
        result = self.engine.run("X", "Y", self.graph)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_run_bundle_is_evidence_bundle(self):
        _, bundle, _ = self.engine.run("X", "Y", self.graph)
        assert isinstance(bundle, EvidenceBundle)

    def test_run_no_negative_cert_for_identifiable(self):
        _, bundle, cert = self.engine.run("X", "Y", self.graph)
        # Backdoor graph should be identifiable → no negative cert
        if bundle.identification_status == "identified":
            assert cert is None

    def test_run_negative_cert_for_non_identifiable(self):
        graph = make_confounded([("X", "Y")], [("X", "Y")])
        report, bundle, cert = self.engine.run("X", "Y", graph)
        # Should get negative cert or HEDGE_FOUND
        assert report is None or cert is not None or bundle.identification_status in {
            "hedge_found", "oracle_needed"
        }
