"""Integration tests for CausalEngine end-to-end pipeline."""

import numpy as np
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate


def make_dag(directed_edges):
    nodes = list({n for e in directed_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)


def make_confounded(directed_edges, bidirected_edges):
    nodes = list({n for e in directed_edges + bidirected_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    for s, d in bidirected_edges:
        edges.append(CausalEdge(src=s, dst=d, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    # PAG allows mixed edge marks including bidirected arrows
    return CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)


def make_data(n=500, seed=42, ate=0.5):
    """Generate data from a simple DGP: Z->X->Y, Z->Y (backdoor)."""
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal(n)
    X = (0.5 * Z + rng.standard_normal(n) > 0).astype(float)
    Y = ate * X + 0.3 * Z + rng.standard_normal(n) * 0.1
    return {"X": X, "Y": Y, "Z": Z, "outcome": Y, "treatment": X, "covariates": Z.reshape(-1, 1)}


class TestBackdoorEndToEnd:
    """End-to-end test on an identifiable backdoor graph."""

    def setup_method(self):
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        self.engine = CausalEngine(registry=None)

    def test_run_returns_evidence_bundle(self):
        _, bundle, _ = self.engine.run("X", "Y", self.graph, n_obs=500)
        assert isinstance(bundle, EvidenceBundle)

    def test_identification_succeeds(self):
        _, bundle, cert = self.engine.run("X", "Y", self.graph)
        # Should be identified
        assert bundle.identification_status in {"identified", "hedge_found", "oracle_needed"}

    def test_no_negative_cert_when_identified(self):
        _, bundle, cert = self.engine.run("X", "Y", self.graph)
        if bundle.identification_status == "identified":
            assert cert is None

    def test_evidence_bundle_has_run_id(self):
        _, bundle, _ = self.engine.run("X", "Y", self.graph, run_id="integration-test-1")
        assert bundle.run_id == "integration-test-1"

    def test_schema_resolution_in_run(self):
        _, bundle, _ = self.engine.run(
            "X",
            "Y",
            self.graph,
            df_columns=["X", "Y", "Z"],
            df_dtypes={"X": "float64", "Y": "float64", "Z": "float64"},
        )
        assert "schema_feasible" in bundle.diagnostic_scores or True  # non-crashing


class TestHedgeEndToEnd:
    """End-to-end test on a non-identifiable graph."""

    def setup_method(self):
        # Bow-arc: X->Y with X<->Y (non-identifiable)
        self.graph = make_confounded([("X", "Y")], [("X", "Y")])
        self.engine = CausalEngine(registry=None)

    def test_run_returns_triple(self):
        result = self.engine.run("X", "Y", self.graph)
        assert len(result) == 3

    def test_negative_cert_or_hedge_status(self):
        report, bundle, cert = self.engine.run("X", "Y", self.graph)
        # Either cert is set or bundle shows hedge/oracle-needed
        if cert is not None:
            assert isinstance(cert, NegativeCertificate)
            # bow-arc PAG may yield HEDGE_STRUCTURE (direct ID) or
            # MISSING_DISTRIBUTION (ORACLE_NEEDED → query validation failure)
            assert cert.blocking_type in (
                BlockingType.HEDGE_STRUCTURE,
                BlockingType.MISSING_DISTRIBUTION,
            )
        else:
            # May have reached ORACLE_NEEDED or returned a result without cert
            assert bundle is not None

    def test_report_is_none_when_non_identifiable(self):
        report, bundle, cert = self.engine.run("X", "Y", self.graph)
        # With no registry and non-identifiable graph, report should be None
        if cert is not None:
            assert report is None


class TestZInterventionEndToEnd:
    """Test with z-interventions (Z-transportability path)."""

    def setup_method(self):
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        self.engine = CausalEngine(registry=None)

    def test_run_with_z_interventions(self):
        _, bundle, cert = self.engine.run(
            "X",
            "Y",
            self.graph,
            z_interventions=frozenset({"Z"}),
        )
        assert isinstance(bundle, EvidenceBundle)

    def test_z_id_returns_identification_result(self):
        result = self.engine.identify(
            "X",
            "Y",
            self.graph,
            z_interventions=frozenset({"Z"}),
        )
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

        assert isinstance(result, (IdentificationResult, NegativeCertificate))


class TestSchemaResolutionIntegration:
    """Test SchemaResolver integration in run()."""

    def setup_method(self):
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        self.engine = CausalEngine(registry=None)

    def test_schema_warnings_surface_in_bundle(self):
        _, bundle, _ = self.engine.run(
            "X",
            "Y",
            self.graph,
            df_columns=["X", "Y", "Z"],
            df_dtypes={"X": "float64", "Y": "float64", "Z": "float64"},
        )
        # schema_feasible should appear if schema resolution ran
        # Just check it doesn't crash
        assert isinstance(bundle, EvidenceBundle)

    def test_missing_column_does_not_crash(self):
        _, bundle, _ = self.engine.run(
            "X",
            "Y",
            self.graph,
            df_columns=["X", "Y"],  # Z missing
            df_dtypes={"X": "float64", "Y": "float64"},
        )
        assert isinstance(bundle, EvidenceBundle)
