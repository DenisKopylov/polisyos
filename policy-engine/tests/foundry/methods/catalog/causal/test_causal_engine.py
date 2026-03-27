"""Unit tests for CausalEngine orchestrator."""
import pytest
import numpy as np
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import (
    CausalEngine,
    DataReadinessBlockedError,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData, PanelObservationalData
from polisyos.foundry.methods.catalog.causal.estimand_compiler import ExecutorGraph
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult, IdentificationStatus,
)
from polisyos.ir.analytics.causal import build_data_readiness_report
from polisyos.ir.analytics.causal import load_data_readiness_report, load_proof_bundle
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    InterventionInterpolationPolicy,
    RegimeRule,
    TemporalInterventionTrajectory,
    TemporalQueryMode,
    load_dynamic_treatment_regime,
    load_effect_trajectory_bundle,
    load_temporal_intervention_trajectory,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, CausalEdge, GraphType
from polisyos.ir.analytics.causal_graph import EdgeMark
from polisyos.ir.analytics.negative_certificate import load_negative_certificate
from polisyos.ir.analytics.negative_certificate import NegativeCertificate, BlockingType
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle
from polisyos.ir.refs import ArtifactRefModel, DynamicTreatmentRegimeRef, EffectTrajectoryBundleRef, TemporalInterventionTrajectoryRef


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


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


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
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def _get_result(self, engine: CausalEngine):
        return engine.identify("X", "Y", self.graph)

    def test_audit_returns_evidence_bundle(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="test-run-1")
        assert isinstance(bundle, EvidenceBundle)

    def test_audit_run_id_preserved(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="my-unique-run")
        assert bundle.run_id == "my-unique-run"

    def test_audit_created_at_is_iso_string(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="r1")
        assert isinstance(bundle.created_at, str)
        assert "T" in bundle.created_at  # ISO format contains 'T'

    def test_audit_identification_status_in_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="r2")
        assert isinstance(bundle.identification_status, str)
        assert len(bundle.identification_status) > 0
        assert bundle.proof_bundle_ref is not None
        assert load_proof_bundle(store, bundle.proof_bundle_ref).proof_status == "identified"

    def test_audit_schema_report_in_diagnostics(self, tmp_path):
        from polisyos.foundry.methods.catalog.causal.schema_resolver import SchemaResolutionReport
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import _make_dummy_identification_result
            result = _make_dummy_identification_result("X", "Y")
        schema = SchemaResolutionReport(support_warnings=["overlap concern"], is_feasible=True)
        bundle = engine.audit(result, None, run_id="r3", schema_report=schema)
        assert "schema_warnings_count" in bundle.diagnostic_scores


class TestCausalEngineRun:
    def setup_method(self):
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def test_run_returns_triple(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = engine.run("X", "Y", self.graph)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_run_bundle_is_evidence_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        _, bundle, _ = engine.run("X", "Y", self.graph)
        assert isinstance(bundle, EvidenceBundle)
        assert bundle.proof_bundle_ref is not None
        assert bundle.data_readiness_report_ref is not None
        assert load_proof_bundle(store, bundle.proof_bundle_ref).proof_status == "identified"
        assert load_data_readiness_report(store, bundle.data_readiness_report_ref).decision in {
            "pass",
            "warn",
            "unknown",
        }

    def test_run_no_negative_cert_for_identifiable(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        _, bundle, cert = engine.run("X", "Y", self.graph)
        # Backdoor graph should be identifiable → no negative cert
        if bundle.identification_status == "identified":
            assert cert is None

    def test_run_negative_cert_for_non_identifiable(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_confounded([("X", "Y")], [("X", "Y")])
        report, bundle, cert = engine.run("X", "Y", graph)
        # Should get negative cert or HEDGE_FOUND
        assert report is None or cert is not None or bundle.identification_status in {
            "hedge_found", "oracle_needed"
        }
        if cert is not None:
            assert cert.recovery_plan is not None
            assert bundle.proof_bundle_ref is not None
            assert bundle.negative_certificate_ref is not None
            restored_cert = load_negative_certificate(store, bundle.negative_certificate_ref)
            assert restored_cert.blocking_type == cert.blocking_type
            if cert.bounds_bundle is None:
                assert bundle.data_readiness_report_ref is not None
            else:
                assert bundle.bounds_bundle_ref is not None
                restored_bounds = load_bounds_bundle(store, bundle.bounds_bundle_ref)
                assert restored_bounds.lower_bound == cert.bounds_bundle.lower_bound

    def test_run_skips_estimator_execution_when_preflight_blocks(self, tmp_path, monkeypatch):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=object(), artifact_store=store)
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

        identified = engine.identify("X", "Y", graph)
        if not isinstance(identified, IdentificationResult):
            pytest.skip("Identification unexpectedly returned a NegativeCertificate.")
        if identified.status != IdentificationStatus.IDENTIFIED:
            pytest.skip(f"Expected identified query, got {identified.status}.")

        block_report = build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
            support_mismatch={"passes_support_check": False},
        )
        monkeypatch.setattr(
            engine,
            "compile",
            lambda *args, **kwargs: ExecutorGraph(nodes=(), edges=(), nuisance_schedule=(), run_id="run"),
        )
        monkeypatch.setattr(
            engine,
            "_run_readiness_preflight",
            lambda **kwargs: (block_report, {}),
        )

        def _unexpected_estimate(*args, **kwargs):
            raise AssertionError("estimate() should not run when readiness preflight blocks execution")

        monkeypatch.setattr(engine, "estimate", _unexpected_estimate)

        report, bundle, cert = engine.run(
            "X",
            "Y",
            graph,
            data_dict={
                "X": np.array([0.0, 1.0, 0.0, 1.0]),
                "Y": np.array([1.0, 2.0, 1.5, 2.5]),
                "Z": np.array([0.0, 0.0, 1.0, 1.0]),
            },
        )

        assert report is None
        assert cert is None
        assert bundle.data_readiness_report_ref is not None
        readiness = load_data_readiness_report(store, bundle.data_readiness_report_ref)
        assert readiness.decision == "block"
        assert readiness.can_run_estimation is False


class TestCausalEngineTemporal:
    @staticmethod
    def _panel_data() -> PanelObservationalData:
        outcome = np.array(
            [
                [0.0, 0.2, 0.4, 1.6],
                [0.0, 0.2, 0.4, 0.5],
                [0.1, 0.1, 0.3, 0.4],
            ],
            dtype=float,
        )
        return PanelObservationalData(
            outcome=outcome,
            treatment=np.array([1, 0, 0], dtype=int),
            time_treatment=3,
            time_index=np.array([0.0, 1.0, 2.0, 3.0], dtype=float),
        )

    @staticmethod
    def _intervention() -> TemporalInterventionTrajectory:
        return TemporalInterventionTrajectory(
            time_points=(0.0, 1.0, 2.0, 3.0),
            values=(0.0, 0.0, 0.0, 1.0),
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        )

    @classmethod
    def _query(
        cls,
        intervention_ref: ArtifactRefModel | None = None,
        *,
        query_mode: TemporalQueryMode = TemporalQueryMode.FIXED_INTERVENTION,
        outcome_process: str = "treated_outcome",
        horizon_end: float = 3.0,
    ) -> ContinuousTimeQuery:
        return ContinuousTimeQuery(
            intervention_trajectory_ref=(
                intervention_ref
                if intervention_ref is not None or query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
                else _artifact_ref("a", kind="ir.temporal_intervention_trajectory")
            ),
            query_mode=query_mode,
            outcome_process=outcome_process,
            horizon_start=0.0,
            horizon_end=horizon_end,
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        )

    @staticmethod
    def _dynamic_data() -> DynamicTreatmentData:
        rng = np.random.default_rng(123)
        n_units, n_periods = 220, 3
        state = np.zeros((n_units, n_periods), dtype=float)
        treatment = np.zeros((n_units, n_periods), dtype=int)
        state[:, 0] = rng.normal(0.0, 1.0, size=n_units)
        for t in range(n_periods):
            probs = 1.0 / (1.0 + np.exp(-(0.2 + 0.2 * state[:, t])))
            treatment[:, t] = rng.binomial(1, probs)
            if t < n_periods - 1:
                state[:, t + 1] = (
                    0.55 * state[:, t]
                    + 0.45 * treatment[:, t] * (state[:, t] > 0.0)
                    - 0.20 * treatment[:, t] * (state[:, t] <= 0.0)
                    + rng.normal(0.0, 0.25, size=n_units)
                )
        reward = (
            1.4 * treatment * (state > 0.0)
            - 0.7 * treatment * (state <= 0.0)
        ).sum(axis=1)
        outcome = reward + 0.25 * state[:, 0] + rng.normal(0.0, 0.30, size=n_units)
        return DynamicTreatmentData(
            outcome=outcome,
            treatment_sequence=treatment,
            covariate_sequence=state[:, :, np.newaxis],
            time_ids=np.arange(n_periods, dtype=float),
            variable_names=["state"],
        )

    def test_temporal_causal_effect_persists_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        intervention_ref = persist_temporal_intervention_trajectory(store, self._intervention())

        trajectory = engine.temporal_causal_effect(
            self._panel_data(),
            self._query(intervention_ref),
            method="linear_sde",
        )

        assert trajectory.effect_bundle is not None
        assert "effect_bundle_artifact_id" in trajectory.metadata
        bundle_ref = EffectTrajectoryBundleRef(
            artifact_id=trajectory.metadata["effect_bundle_artifact_id"]
        )
        restored = load_effect_trajectory_bundle(store, bundle_ref)
        assert restored.query_ref.kind == "ir.continuous_time_query"
        assert restored.trajectory_ref.kind == "ir.temporal_trajectory"
        assert restored.confidence_band_ref.kind == "ir.temporal_confidence_band"
        assert restored.solver_diagnostics_ref.kind == "ir.temporal_solver_diagnostics"
        assert restored.metadata["intervention_contract_status"] == "resolved_artifact"
        assert restored.continuous_time_degraded is False

    def test_temporal_causal_effect_requires_intervention_source(self):
        engine = CausalEngine(registry=None, knowledge_base=None)

        with pytest.raises(Exception, match="intervention"):
            engine.temporal_causal_effect(
                self._panel_data(),
                self._query(),
                method="linear_sde",
            )

    def test_temporal_causal_effect_optimal_policy_discovery_persists_policy_lineage(
        self,
        tmp_path,
    ):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)

        trajectory = engine.temporal_causal_effect(
            self._dynamic_data(),
            self._query(
                intervention_ref=None,
                query_mode=TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
                outcome_process="state",
                horizon_end=2.0,
            ),
            method="linear_sde",
        )

        assert trajectory.effect_bundle is not None
        bundle = trajectory.effect_bundle
        assert bundle.metadata["execution_contract_kind"] == "optimal_policy_discovery"
        assert bundle.metadata["policy_artifact_ref"] is not None
        assert bundle.metadata["derived_schedule_ref"] is not None

        policy_ref = DynamicTreatmentRegimeRef.model_validate(bundle.metadata["policy_artifact_ref"])
        derived_ref = TemporalInterventionTrajectoryRef.model_validate(
            bundle.metadata["derived_schedule_ref"]
        )
        restored_policy = load_dynamic_treatment_regime(store, policy_ref)
        restored_schedule = load_temporal_intervention_trajectory(store, derived_ref)

        assert isinstance(restored_policy, DynamicTreatmentRegime)
        assert restored_policy.rule in {RegimeRule.THRESHOLD, RegimeRule.ALWAYS_TREAT}
        assert len(restored_schedule.values) == 3


@pytest.mark.parametrize(
    ("label", "callable_factory"),
    [
        (
            "dynamic_causal_effect",
            lambda engine: lambda: engine.dynamic_causal_effect(data={}, method="ice_g"),
        ),
        (
            "mediation_analysis",
            lambda engine: lambda: engine.mediation_analysis(
                data={},
                treatment="X",
                outcome="Y",
                mediators=["M"],
                method="linear",
            ),
        ),
        (
            "interference_effect",
            lambda engine: lambda: engine.interference_effect(
                data={},
                treatment="T",
                outcome="Y",
                method="network_aipw",
            ),
        ),
        (
            "fairness_audit",
            lambda engine: lambda: engine.fairness_audit(
                data={},
                protected="A",
                outcome="Y",
                method="tv_decomposition",
            ),
        ),
    ],
)
def test_direct_estimation_wrappers_block_on_missing_readiness(label, callable_factory):
    engine = CausalEngine(registry=None, knowledge_base=None)
    wrapped_call = callable_factory(engine)

    with pytest.raises(DataReadinessBlockedError) as exc_info:
        wrapped_call()

    assert exc_info.value.report.decision == "unknown", label
    assert exc_info.value.report.can_run_estimation is False, label
