from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts.manifest import ArtifactAuthorityInfo, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.analytics.causal import ProofBundle, load_proof_bundle, persist_proof_bundle
from polisyos.ir.analytics.simulation_proof_bridge import (
    SimulationCalibrationReceipt,
    SimulationCertificationStatus,
    SimulationProofBridge,
    SimulationProofBridgeArtifacts,
    build_simulation_proof_bridge_artifacts,
    load_simulation_calibration_receipt,
    load_simulation_proof_bridge,
    persist_simulation_calibration_receipt,
    persist_simulation_proof_bridge,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    EvidenceBundleRef,
    InterfaceMappingRef,
    ProofBundleRef,
    SimulationCalibrationReceiptRef,
    SimulationProofBridgeRef,
)
from polisyos.ir.trinity import TrinityBundle


def _produce_real_foundry_simulation(store: FileSystemCAS):
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=policy.schema_version),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert compile_result.ok and compile_result.exec_plan_ref is not None
    snapshot_ref = put_state_snapshot(
        store,
        state=GlobalState.empty(n_agents=2, n_firms=1),
        step=0,
    )
    state_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)
    data_ref = store.put_json(
        DataSnapshot(data_ref=state_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_ref,
            registry_bundle_ref=bundle.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings_ref.artifact_id),
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert result.ok and result.simulation_result_ref is not None
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(result.simulation_result_ref.artifact_id))
    )
    return result.simulation_result_ref, simulation.metrics_ref


def _authority_surface_payload(surface: str) -> dict[str, object]:
    def artifact_id(char: str) -> str:
        return f"sha256:{char * 64}"

    simulation_ref = ArtifactRefModel(
        artifact_id=artifact_id("1"),
        kind="foundry.simulation_result",
        media_type="application/json",
    )
    calibration_ref = SimulationCalibrationReceiptRef(artifact_id=artifact_id("2"))
    evidence_ref = EvidenceBundleRef(artifact_id=artifact_id("3"))
    proof_ref = ProofBundleRef(artifact_id=artifact_id("4"))
    if surface == "calibration":
        return {
            "simulation_result_ref": simulation_ref,
            "source": "default_unverified",
            "truthfulness_receipt": TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
            ),
            "accepted": False,
            "degradation_reasons": ("truthfulness_producer_missing",),
        }
    if surface == "bridge":
        return {
            "run_id": "R_authority_surface",
            "simulation_result_ref": simulation_ref,
            "evidence_bundle_ref": evidence_ref,
            "proof_bundle_ref": proof_ref,
            "calibration_receipt_ref": calibration_ref,
            "certification_status": SimulationCertificationStatus.SCENARIO,
            "proof_status": "identified",
            "calibration_status": "unverified",
            "composability_status": "reusable",
        }
    return {
        "bridge_ref": SimulationProofBridgeRef(artifact_id=artifact_id("5")),
        "calibration_receipt_ref": calibration_ref,
        "evidence_bundle_ref": evidence_ref,
        "proof_bundle_ref": proof_ref,
        "witness_index_ref": ArtifactRefModel(
            artifact_id=artifact_id("6"),
            kind="ir.proof_witness_index",
            media_type="application/json",
        ),
        "composability_certificate_ref": ArtifactRefModel(
            artifact_id=artifact_id("7"),
            kind="ir.proof_composability_certificate",
            media_type="application/json",
        ),
        "certification_status": SimulationCertificationStatus.SCENARIO,
    }


def _mutate_authority_surface(
    surface: str,
    mutation: str,
) -> dict[str, object]:
    payload = _authority_surface_payload(surface)
    if mutation == "accepted":
        payload["accepted"] = True
    elif mutation == "source":
        payload["source"] = "explicit"
    elif mutation == "tier":
        payload["truthfulness_receipt"] = TruthfulnessReceipt(
            runtime_truthfulness_tier=TruthfulnessTier.APPROXIMATE_CALIBRATED,
            truthfulness_scope=TruthfulnessScope.POSTERIOR,
        )
    elif mutation == "calibration_status":
        payload["calibration_status"] = "accepted"
    else:
        payload["certification_status"] = SimulationCertificationStatus.IDENTIFIED
    return payload


@pytest.mark.parametrize(
    ("surface", "model_type", "mutation"),
    [
        ("calibration", SimulationCalibrationReceipt, "accepted"),
        ("calibration", SimulationCalibrationReceipt, "source"),
        ("calibration", SimulationCalibrationReceipt, "tier"),
        ("bridge", SimulationProofBridge, "calibration_status"),
        ("bridge", SimulationProofBridge, "identified"),
        ("artifacts", SimulationProofBridgeArtifacts, "identified"),
    ],
)
def test_authority_surface_constructors_reject_every_unsupported_positive(
    surface,
    model_type,
    mutation,
) -> None:
    with pytest.raises(ValueError, match="producer/verifier"):
        model_type.model_validate(_mutate_authority_surface(surface, mutation))


def test_calibration_receipt_preserves_declared_candidate_while_runtime_stays_unverified() -> None:
    payload = _authority_surface_payload("calibration")
    payload["truthfulness_receipt"] = TruthfulnessReceipt(
        declared_truthfulness_tier=TruthfulnessTier.EXACT,
        runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
        truthfulness_scope=TruthfulnessScope.POSTERIOR,
    )

    receipt = SimulationCalibrationReceipt.model_validate(payload)

    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert (
        receipt.truthfulness_receipt.declared_truthfulness_tier
        is TruthfulnessTier.EXACT
    )
    assert (
        receipt.truthfulness_receipt.runtime_truthfulness_tier
        is TruthfulnessTier.UNVERIFIED
    )
    assert (
        receipt.truthfulness_receipt.effective_truthfulness_tier
        is TruthfulnessTier.UNVERIFIED
    )


@pytest.mark.parametrize(
    ("surface", "model_type", "persist", "mutation"),
    [
        (
            "calibration",
            SimulationCalibrationReceipt,
            persist_simulation_calibration_receipt,
            "accepted",
        ),
        (
            "calibration",
            SimulationCalibrationReceipt,
            persist_simulation_calibration_receipt,
            "source",
        ),
        (
            "calibration",
            SimulationCalibrationReceipt,
            persist_simulation_calibration_receipt,
            "tier",
        ),
        (
            "bridge",
            SimulationProofBridge,
            persist_simulation_proof_bridge,
            "calibration_status",
        ),
        (
            "bridge",
            SimulationProofBridge,
            persist_simulation_proof_bridge,
            "identified",
        ),
    ],
)
def test_authority_surface_persistence_revalidates_model_construct_bypasses(
    tmp_path,
    surface,
    model_type,
    persist,
    mutation,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    forged = model_type.model_construct(**_mutate_authority_surface(surface, mutation))

    with pytest.raises(ValueError, match="producer/verifier"):
        persist(store, forged)


@pytest.mark.parametrize(
    ("surface", "ref_type", "loader", "kind", "mutation"),
    [
        (
            "calibration",
            SimulationCalibrationReceiptRef,
            load_simulation_calibration_receipt,
            "ir.simulation_calibration_receipt",
            "accepted",
        ),
        (
            "calibration",
            SimulationCalibrationReceiptRef,
            load_simulation_calibration_receipt,
            "ir.simulation_calibration_receipt",
            "source",
        ),
        (
            "calibration",
            SimulationCalibrationReceiptRef,
            load_simulation_calibration_receipt,
            "ir.simulation_calibration_receipt",
            "tier",
        ),
        (
            "bridge",
            SimulationProofBridgeRef,
            load_simulation_proof_bridge,
            "ir.simulation_proof_bridge",
            "calibration_status",
        ),
        (
            "bridge",
            SimulationProofBridgeRef,
            load_simulation_proof_bridge,
            "ir.simulation_proof_bridge",
            "identified",
        ),
    ],
)
def test_authority_surface_loaders_reject_forged_persisted_payloads(
    tmp_path,
    surface,
    ref_type,
    loader,
    kind,
    mutation,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    raw_ref = store.put_json(
        _mutate_authority_surface(surface, mutation),
        PutOptions(kind=kind, media_type="application/json"),
    )
    ref = ref_type.model_validate(raw_ref.model_dump(mode="json"))

    with pytest.raises(ValueError, match="producer/verifier"):
        loader(store, ref)


def test_simulation_proof_bridge_defaults_to_scenario_without_causal_context(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": {"loss": "1.0"}},
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_bridge",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
    )

    assert isinstance(output.bridge_ref, SimulationProofBridgeRef)
    assert isinstance(output.calibration_receipt_ref, SimulationCalibrationReceiptRef)
    bridge = load_simulation_proof_bridge(store, output.bridge_ref)
    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    proof = load_proof_bundle(store, output.proof_bundle_ref)

    assert bridge.certification_status is SimulationCertificationStatus.SCENARIO
    assert bridge.proof_status == "non_identified"
    assert bridge.calibration_status == "unverified"
    assert receipt.accepted is False
    assert proof.metadata["simulation_certification_status"] == "SCENARIO"
    assert "identification_proof_missing" in bridge.degradation_reasons


def test_simulation_proof_bridge_rejects_method_execution_as_validity_evidence(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    method_evidence_ref = store.put_json(
        {
            "authority_purpose": "method_execution",
            "authoritative_for": ["execution_reproducibility"],
            "may_not_use_for": ["governance_admissibility", "method_validity"],
        },
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.MethodExecutionEvidence",
                version="0.1.0",
            ),
        ),
    )

    with pytest.raises(ValueError, match="causal_validity_bundle_ref"):
        build_simulation_proof_bridge_artifacts(
            store,
            run_id="R_execution_is_not_validity",
            simulation_result_ref=simulation_ref,
            causal_validity_bundle_ref=method_evidence_ref,
        )


def test_simulation_proof_bridge_preserves_proof_but_does_not_inflate_real_foundry_output(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref, metrics_ref = _produce_real_foundry_simulation(store)
    interface_mapping_ref = InterfaceMappingRef.model_validate(
        store.put_json(
            {"fragment_ids": ["sim"], "entries": []},
            PutOptions(kind="ir.interface_mapping", media_type="application/json"),
        ).model_dump(mode="json")
    )
    base_proof_ref = persist_proof_bundle(
        store,
        ProofBundle(
            proof_status="identified",
            proof_stratum="A0_trusted",
            theorem_family="id_v1",
            completeness_regime="complete",
            implementation_coverage="declared-scope:id_v1",
            composability_status="reusable",
        ),
    )
    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_identified",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        interface_mapping_ref=interface_mapping_ref,
        causal_query="P(Y|do(X))",
        base_proof_bundle_ref=base_proof_ref,
    )

    bridge = load_simulation_proof_bridge(store, output.bridge_ref)
    calibration = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    proof = load_proof_bundle(store, ProofBundleRef.model_validate(bridge.proof_bundle_ref))

    assert bridge.certification_status is SimulationCertificationStatus.SCENARIO
    assert bridge.calibration_status == "unverified"
    assert calibration.accepted is False
    assert calibration.source == "default_unverified"
    assert "simulation_truthfulness_producer_missing" in calibration.degradation_reasons
    assert "metrics_truthfulness_producer_missing" in calibration.degradation_reasons
    assert "simulation_manifest_schema_mismatch" not in calibration.degradation_reasons
    assert "simulation_owner_payload_invalid" not in calibration.degradation_reasons
    assert "metrics_manifest_schema_mismatch" not in calibration.degradation_reasons
    assert "metrics_owner_payload_invalid" not in calibration.degradation_reasons
    assert bridge.base_proof_bundle_ref == base_proof_ref
    assert proof.proof_status == "identified"
    assert proof.metadata["base_proof_ref"] == base_proof_ref.model_dump(mode="json")


def test_simulation_proof_bridge_rejects_wrong_kind_receipt_blob(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {
            "truthfulness_receipt": TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
            ).model_dump(mode="json")
        },
        PutOptions(
            kind="attacker.unverified_blob",
            media_type="application/json",
            schema=SchemaInfo(name="attacker.Blob", version="1.0"),
            producer=ProducerInfo(component="attacker", version="1.0"),
        ),
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_wrong_kind",
        simulation_result_ref=simulation_ref,
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "simulation_manifest_kind_mismatch" in receipt.degradation_reasons


def test_simulation_proof_bridge_rejects_unprovenanced_owner_kind(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {
            "schema_version": "1.3",
            "truthfulness_receipt": TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
            ).model_dump(mode="json"),
        },
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_unprovenanced_kind",
        simulation_result_ref=simulation_ref,
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "simulation_manifest_schema_mismatch" in receipt.degradation_reasons
    assert "simulation_truthfulness_producer_missing" in receipt.degradation_reasons


def test_simulation_proof_bridge_rejects_impossible_receipt_in_typed_owner_payload(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {
            "schema_version": "1.3",
            "exec_plan_ref": {
                "artifact_id": "sha256:" + "1" * 64,
                "kind": "foundry.exec_plan",
                "media_type": "application/json",
            },
            "metrics_ref": {
                "artifact_id": "sha256:" + "2" * 64,
                "kind": "foundry.metrics",
                "media_type": "application/json",
            },
            "truthfulness_receipt": TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
            ).model_dump(mode="json"),
        },
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
            producer=ProducerInfo(component="foundry.fake", version="1.0"),
            authority=ArtifactAuthorityInfo(
                authority_envelope_ref="sha256:" + "3" * 64,
                diagnostic_event_ref="sha256:" + "4" * 64,
                manifest_ref="cas-manifest://sha256:" + "5" * 64,
                payload_sha256="6" * 64,
            ),
        ),
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_impossible_receipt",
        simulation_result_ref=simulation_ref,
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "simulation_owner_payload_invalid" in receipt.degradation_reasons
    assert "simulation_truthfulness_producer_not_admitted" in receipt.degradation_reasons
    assert "simulation_truthfulness_verifier_not_admitted" in receipt.degradation_reasons


def test_simulation_proof_bridge_rejects_sibling_metrics_receipt_blob(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {
            "truthfulness_receipt": TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
            ).model_dump(mode="json")
        },
        PutOptions(kind="attacker.unverified_blob", media_type="application/json"),
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_metrics_wrong_kind",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "metrics_manifest_kind_mismatch" in receipt.degradation_reasons


def test_simulation_proof_bridge_rejects_forged_caller_payload_receipt(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    forged_payload = {
        "schema_version": "1.3",
        "notes": [],
        "truthfulness_receipt": TruthfulnessReceipt(
            runtime_truthfulness_tier=TruthfulnessTier.EXACT,
            truthfulness_scope=TruthfulnessScope.POSTERIOR,
        ).model_dump(mode="json"),
    }

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_forged_payload",
        simulation_result_ref=simulation_ref,
        simulation_payload=forged_payload,
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "simulation_payload_content_mismatch" in receipt.degradation_reasons


def test_simulation_proof_bridge_rejects_forged_caller_metrics_payload(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": {"loss": "1.0"}},
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_forged_metrics_payload",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        metrics_payload={"values": {"loss": "forged"}},
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "metrics_payload_content_mismatch" in receipt.degradation_reasons


def test_simulation_proof_bridge_keeps_explicit_receipt_non_authorizing(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bound_receipt = TruthfulnessReceipt(
        runtime_truthfulness_tier=TruthfulnessTier.APPROXIMATE_CALIBRATED,
        truthfulness_scope=TruthfulnessScope.POSTERIOR,
        diagnostics={"source": "bound-runtime"},
    )
    simulation_ref = store.put_json(
        {
            "schema_version": "1.3",
            "truthfulness_receipt": bound_receipt.model_dump(mode="json"),
        },
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    self_attested = TruthfulnessReceipt(
        runtime_truthfulness_tier=TruthfulnessTier.EXACT,
        truthfulness_scope=TruthfulnessScope.POSTERIOR,
        diagnostics={"source": "caller"},
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_explicit_mismatch",
        simulation_result_ref=simulation_ref,
        calibration_receipt=self_attested,
    )

    receipt = load_simulation_calibration_receipt(store, output.calibration_receipt_ref)
    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "explicit_truthfulness_receipt_unverified" in receipt.degradation_reasons


def test_simulation_proof_bridge_rejects_malformed_explicit_receipt(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    with pytest.raises(ValueError, match="runtime_truthfulness_tier"):
        build_simulation_proof_bridge_artifacts(
            store,
            run_id="R_malformed_explicit",
            simulation_result_ref=simulation_ref,
            calibration_receipt={"runtime_truthfulness_tier": "forged-tier"},
        )
