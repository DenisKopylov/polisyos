from __future__ import annotations

from types import SimpleNamespace

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
from polisyos.ir.analytics.causal import (
    ProofBundle,
    build_data_readiness_report,
    load_data_readiness_report,
    load_proof_bundle,
    persist_data_readiness_report,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
    proof_bundle_from_proximal_certificate,
)
from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.frontier import (
    PHASE1_CLOSURE_MANIFEST,
    load_frontier_sketch,
    materialize_phase1_frontier_sketch,
    persist_frontier_sketch,
)
from polisyos.ir.analytics.invariance import RegimeShiftIdentificationCertificate
from polisyos.ir.analytics.proximal import (
    BridgeFailureMode,
    BridgeFunctionSpec,
    BridgePlausibilityReport,
    BridgePlausibilitySeverity,
    BridgeFallbackDisposition,
    IdentifiedFunctional,
    ProximalGraphCheck,
    ProximalIdentificationCertificate,
    ProximalQuerySpec,
    ProxyAnnotation,
    SpatialProxySpec,
    load_bridge_plausibility_report,
    persist_bridge_plausibility_report,
    load_proximal_identification_certificate,
    persist_proximal_identification_certificate,
)
from polisyos.ir.analytics.recoverability import (
    JointDecisionCertificate,
    JointDecisionStatus,
    MinimalRepairSet,
    RecoverabilityCertificate,
    RecoverabilityCertificateStatus,
    RecoveryScope,
    RepairSetTestability,
    RepairSetType,
    load_joint_decision_certificate,
    load_recoverability_certificate,
    persist_joint_decision_certificate,
    persist_recoverability_certificate,
)


def _proximal_certificate() -> ProximalIdentificationCertificate:
    return ProximalIdentificationCertificate(
        query=ProximalQuerySpec(
            estimand="ATE",
            treatment=("A",),
            outcome=("Y",),
            covariates=("X",),
        ),
        proxies=ProxyAnnotation(
            treatment_inducing=("Z",),
            outcome_inducing=("W",),
            covariates=("X",),
        ),
        graph_checks=(
            ProximalGraphCheck(
                check="pci_core",
                status="pass",
                source="A",
                target="Y",
            ),
        ),
        bridge_functions=(
            BridgeFunctionSpec(
                name="h",
                role="outcome_bridge",
                domain=("W", "A", "X"),
                equation_type="conditional_expectation",
                equation="E[Y - h(W, A, X) | Z, A, X] = 0",
            ),
        ),
        identified_functionals=(
            IdentifiedFunctional(
                target="ATE",
                expression="E[h(W, 1, X) - h(W, 0, X)]",
                preferred=True,
                bridge_role="outcome_bridge",
            ),
        ),
        assumptions=("proximal_bridge_consistency",),
        proof_trace=("pci_core", "bridge_identified"),
    )


def _recoverability_certificate() -> RecoverabilityCertificate:
    return RecoverabilityCertificate(
        target_query="P(Y|do(X))",
        mgraph_fingerprint="sha256:test",
        status=RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS,
        recovery_scope=RecoveryScope.CAUSAL_QUERY,
        blocking_r_nodes=("R_X",),
        minimal_repair_sets=(
            MinimalRepairSet(
                repair_type=RepairSetType.ASSUMPTION,
                items=("remove_edge(X -> R_X)",),
                testability=RepairSetTestability.NOT_TESTABLE,
            ),
        ),
        warnings=("assumption_dependent_missingness_recovery",),
        theorem_family="mgraph_recoverability_v1",
    )


def test_phase1_manifest_declares_all_phase1_stages_and_backbone_subset() -> None:
    expected_stage_ids = {
        "2.1",
        "3.1",
        "4.4",
        "5.3",
        "8.1",
        "11.1",
        "11.2",
        "12.1",
        "13.1",
        "15.1",
        "16.1",
    }
    expected_backbone_ids = {"2.1", "3.1", "4.4", "5.3", "11.1", "12.1", "13.1", "15.1", "16.1"}
    actual_stage_ids = {stage.stage_id for stage in PHASE1_CLOSURE_MANIFEST.stages}
    actual_backbone_ids = {
        stage.stage_id for stage in PHASE1_CLOSURE_MANIFEST.stages if stage.backbone
    }

    assert actual_stage_ids == expected_stage_ids
    assert actual_backbone_ids == expected_backbone_ids
    for stage in PHASE1_CLOSURE_MANIFEST.stages:
        assert stage.benchmark_proxy
        assert stage.typed_integration_target
        assert stage.required_for_promotion
        assert stage.canonical_contract_surface


def test_phase1_closure_summary_has_machine_checkable_consumer_paths() -> None:
    closure_summary = {
        stage.stage_id: {
            "typed_target": stage.typed_integration_target,
            "surface": stage.canonical_contract_surface,
            "backbone": stage.backbone,
        }
        for stage in PHASE1_CLOSURE_MANIFEST.stages
    }

    assert len(closure_summary) == 11
    assert closure_summary["8.1"]["typed_target"] == "CausalDiscoveryReport.algebraic_constraints"
    assert closure_summary["11.2"]["typed_target"] == "ProofBundle.bridge_plausibility_report_ref"
    assert closure_summary["16.1"]["typed_target"] == "RegimeShiftIdentificationCertificateRef"
    assert "algebraic_constraints" in CausalDiscoveryReport.model_fields
    assert "bridge_plausibility_report_ref" in ProofBundle.model_fields
    assert "identifiability_witness" in RegimeShiftIdentificationCertificate.model_fields


def test_frontier_sketch_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    sketch = materialize_phase1_frontier_sketch(
        stage_id="4.4",
        family="cyclic_sigma_certificate",
        sketch_type="scope_split",
        hypothesis="Validated cyclic reductions require exact linear-unique witnesses.",
        known_limitations=("sigma_separation_failed",),
        metadata={"benchmark_case": "sigma_fail"},
    )

    sketch_ref = persist_frontier_sketch(store, sketch)
    loaded = load_frontier_sketch(store, sketch_ref)

    assert loaded == sketch
    assert loaded.max_readiness == "PROOF_ONLY"
    assert loaded.typed_integration_target == "ProofBundle.dynamic_semantics"


def test_recoverability_and_joint_refs_flow_into_proof_and_readiness(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    recoverability = _recoverability_certificate()
    joint = JointDecisionCertificate(
        verdict=JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE,
        target_query="P(Y|do(X))",
        id_status="identified",
        recoverability=recoverability,
        computable_functionals=("P(Y|do(X))",),
    )
    recoverability_ref = persist_recoverability_certificate(store, recoverability)
    joint_ref = persist_joint_decision_certificate(
        store,
        joint,
    )
    proof = proof_bundle_from_identification_result(
        SimpleNamespace(
            status=IdentificationStatus.IDENTIFIED,
            algorithm_version="id_v1",
            estimand_ast=None,
            trace=[],
            query_str="P(Y|do(X))",
            required_distributions=[],
            metadata={"joint_decision": joint.model_dump(mode="json")},
        ),
        recoverability_certificate=recoverability,
        recoverability_certificate_ref=recoverability_ref,
        joint_decision_ref=joint_ref,
    )
    readiness = build_data_readiness_report(
        recoverability_certificate=recoverability,
        recoverability_certificate_ref=recoverability_ref,
        joint_decision=joint,
        joint_decision_ref=joint_ref,
        fallback_data_available=True,
    )

    proof_ref = persist_proof_bundle(store, proof)
    readiness_ref = persist_data_readiness_report(store, readiness)
    loaded_proof = load_proof_bundle(store, proof_ref)
    loaded_readiness = load_data_readiness_report(store, readiness_ref)

    assert loaded_proof.recoverability_certificate_ref == recoverability_ref
    assert loaded_proof.joint_decision_ref == joint_ref
    assert loaded_proof.metadata["recoverability_certificate_ref"]["artifact_id"] == str(
        recoverability_ref.artifact_id
    )
    assert loaded_readiness.recoverability_certificate_ref == recoverability_ref
    assert loaded_readiness.joint_decision_ref == joint_ref
    assert loaded_readiness.recoverability is not None


def test_proximal_certificate_ref_attaches_to_proof_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = _proximal_certificate()
    certificate_ref = persist_proximal_identification_certificate(store, certificate)
    sketch = materialize_phase1_frontier_sketch(
        stage_id="11.1",
        family="proximal_bridge",
        sketch_type="benchmark_proxy",
        hypothesis="PCI-Core proximal certificates are sound but intentionally incomplete.",
        primary_ref=certificate_ref,
        known_limitations=("sound_incomplete",),
    )
    sketch_ref = persist_frontier_sketch(store, sketch)

    bundle = proof_bundle_from_proximal_certificate(
        certificate,
        graph_ref="graph:demo",
        query_ref="query:demo",
        certificate_ref=certificate_ref,
        frontier_sketch_ref=sketch_ref,
    )
    proof_ref = persist_proof_bundle(store, bundle)
    loaded_bundle = load_proof_bundle(store, proof_ref)

    assert load_proximal_identification_certificate(store, certificate_ref) == certificate
    assert loaded_bundle.proximal_certificate_ref == certificate_ref
    assert loaded_bundle.frontier_sketch_ref == sketch_ref
    assert loaded_bundle.metadata["proximal_certificate_ref"]["artifact_id"] == str(
        certificate_ref.artifact_id
    )
    assert load_frontier_sketch(store, sketch_ref).stage_id == "11.1"
    joint_ref = persist_joint_decision_certificate(
        store,
        JointDecisionCertificate(
            verdict=JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE,
            target_query="P(Y|do(X))",
            id_status="identified",
            recoverability=_recoverability_certificate(),
        ),
    )
    recoverability_ref = persist_recoverability_certificate(store, _recoverability_certificate())
    assert load_joint_decision_certificate(store, joint_ref).verdict is (
        JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE
    )
    assert load_recoverability_certificate(store, recoverability_ref).status is (
        RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS
    )


def test_bridge_plausibility_ref_attaches_to_proof_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = BridgePlausibilityReport(
        equation_type="outcome_bridge",
        residual_r=0.42,
        effective_rank=1.0,
        sigma_min=0.002,
        ill_posedness_index=140.0,
        proxy_association_score=0.08,
        bridge_existence_supported=True,
        completeness_plausible=False,
        functional_invariant_to_nonuniqueness=True,
        suspected_failure_mode=BridgeFailureMode.WEAK_COMPLETENESS,
        severity=BridgePlausibilitySeverity.YELLOW,
        fallback_disposition=BridgeFallbackDisposition.REQUIRE_BOUNDS,
        reasons=("proxy_association_or_effective_rank_weak",),
    )
    report_ref = persist_bridge_plausibility_report(store, report)

    bundle = proof_bundle_from_identification_result(
        SimpleNamespace(
            status=IdentificationStatus.IDENTIFIED,
            algorithm_version="proximal_id_pci_core",
            estimand_ast=None,
            trace=["proximal bridge diagnostics available"],
            query_str="P(Y|do(A))",
            required_distributions=[],
            metadata={
                "bridge_plausibility_report": report.model_dump(mode="json"),
                "bridge_plausibility_report_ref": report_ref.model_dump(mode="json"),
            },
        )
    )
    proof_ref = persist_proof_bundle(store, bundle)
    loaded_bundle = load_proof_bundle(store, proof_ref)

    assert load_bridge_plausibility_report(store, report_ref) == report
    assert loaded_bundle.bridge_plausibility_report_ref == report_ref
    assert loaded_bundle.metadata["bridge_plausibility_report_ref"]["artifact_id"] == str(
        report_ref.artifact_id
    )


def test_spatial_proxy_specs_round_trip_in_proximal_certificate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = _proximal_certificate().model_copy(
        update={
            "proxies": ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
                spatial_proxy_specs=(
                    SpatialProxySpec(
                        proxy_variables=("Z",),
                        weight_matrix_ref="artifact://weights/W",
                        proxy_construction="buffered_ring_lag",
                        lag_orders=(2,),
                        buffer_radius=2,
                        allowed_roles=("treatment_inducing",),
                        spillover_radius_claim=1,
                    ),
                    SpatialProxySpec(
                        proxy_variables=("W",),
                        weight_matrix_ref="artifact://weights/W",
                        proxy_construction="buffered_ring_lag",
                        lag_orders=(3,),
                        buffer_radius=3,
                        allowed_roles=("outcome_inducing",),
                        spillover_radius_claim=1,
                    ),
                ),
            ),
            "metadata": {
                "theorem_family": "proximal_spatial_id_v1",
                "method": "spatial_proximal_bridge",
                "implementation_coverage": "spatial_proximal_bridge_v1",
            },
        }
    )
    certificate_ref = persist_proximal_identification_certificate(store, certificate)
    loaded = load_proximal_identification_certificate(store, certificate_ref)
    bundle = proof_bundle_from_proximal_certificate(certificate, certificate_ref=certificate_ref)

    assert len(loaded.proxies.spatial_proxy_specs) == 2
    assert loaded.proxies.spatial_proxy_specs[1].lag_orders == (3,)
    assert bundle.theorem_family == "proximal_spatial_id_v1"
    assert bundle.metadata["method"] == "spatial_proximal_bridge"
