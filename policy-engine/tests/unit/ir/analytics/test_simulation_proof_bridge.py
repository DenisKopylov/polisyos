from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import artifact_ref_for_manifest
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
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
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.analytics import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
from polisyos.ir.analytics.causal import ProofBundle, load_proof_bundle, persist_proof_bundle
from polisyos.ir.analytics.evidence_bundle import load_causal_evidence_bundle
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


class _StrictSimulationResultV13(BaseModel):
    """Independent strict reader for the pre-1.4 SimulationResult wire shape."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.3"]
    exec_plan_ref: dict[str, object]
    metrics_ref: dict[str, object]
    metric_observation_bundle_ref: dict[str, object] | None = None
    state_snapshot_ref: dict[str, object] | None = None
    environment_ref: dict[str, object] | None = None
    environment_fingerprint: str | None = None
    trace_slice_ref: dict[str, object] | None = None
    uncertainty_envelopes: dict[str, object] | None = None
    distributional_report_ref: dict[str, object] | None = None
    welfare_bundle_ref: dict[str, object] | None = None
    welfare_bound_refs: dict[str, object] | None = None
    metric_validation_report_ref: dict[str, object] | None = None
    fairness_audit_report_ref: dict[str, object] | None = None
    propagation_config_ref: dict[str, object] | None = None
    propagation_report_ref: dict[str, object] | None = None
    feedback_result_ref: dict[str, object] | None = None
    identifiability_diagnostic_ref: dict[str, object] | None = None
    notes: list[str] = Field(default_factory=list)


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
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_ref,
            registry_bundle_ref=bundle.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_ref,
        ),
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
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


def test_real_foundry_legacy_artifact_remains_readable_and_limited_in_ir_bridge(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref, metrics_ref = _produce_real_foundry_simulation(store)

    manifest = store.get_manifest(simulation_ref)
    payload = from_canonical_bytes(store.get_bytes(simulation_ref.artifact_id))
    legacy_reader = _StrictSimulationResultV13.model_validate(payload)

    assert manifest.artifact_schema.version == "1.3"
    assert legacy_reader.schema_version == "1.3"
    assert "execution_input_basis_ref" not in payload
    assert "execution_source_status" not in payload

    selected_simulation_ref = artifact_ref_for_manifest(store.get_manifest(simulation_ref))
    selected_metrics_ref = artifact_ref_for_manifest(store.get_manifest(metrics_ref))
    profileless_simulation_ref = type(simulation_ref)(artifact_id=simulation_ref.artifact_id)
    profileless_metrics_ref = type(metrics_ref)(artifact_id=metrics_ref.artifact_id)

    output = build_simulation_proof_bridge_artifacts(
        _ensure_ir_artifact_store(store),
        run_id="R_real_foundry_legacy_projection",
        simulation_result_ref=selected_simulation_ref,
        metrics_ref=selected_metrics_ref,
    )
    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )

    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "simulation_truthfulness_producer_missing" in receipt.degradation_reasons

    receipt_manifest = store.get_manifest(output.calibration_receipt_ref)
    receipt_input_profiles = {
        item.role: item.manifest_profile_sha256 for item in receipt_manifest.inputs
    }
    assert receipt_input_profiles["simulation_result"] == (
        selected_simulation_ref.manifest_profile_sha256
    )
    assert receipt_input_profiles["metrics"] == selected_metrics_ref.manifest_profile_sha256

    profileless_output = build_simulation_proof_bridge_artifacts(
        _ensure_ir_artifact_store(store),
        run_id="R_real_foundry_legacy_profileless_control",
        simulation_result_ref=profileless_simulation_ref,
        metrics_ref=profileless_metrics_ref,
    )
    profileless_manifest = store.get_manifest(profileless_output.calibration_receipt_ref)
    profileless_input_profiles = {
        item.role: item.manifest_profile_sha256 for item in profileless_manifest.inputs
    }
    assert profileless_input_profiles["simulation_result"] is None
    assert profileless_input_profiles["metrics"] is None


def test_simulation_proof_bridge_rejects_forged_new_status_in_legacy_bytes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref, metrics_ref = _produce_real_foundry_simulation(store)
    payload = dict(from_canonical_bytes(store.get_bytes(simulation_ref.artifact_id)))
    payload["execution_source_status"] = "single_step_basis"

    forged_ref = store.put_json(
        payload,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
        ),
    )
    output = build_simulation_proof_bridge_artifacts(
        _ensure_ir_artifact_store(store),
        run_id="R_forged_legacy_basis_status",
        simulation_result_ref=forged_ref,
        metrics_ref=metrics_ref,
    )
    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )

    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert "simulation_owner_payload_invalid" in receipt.degradation_reasons


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
    assert receipt.truthfulness_receipt.declared_truthfulness_tier is TruthfulnessTier.EXACT
    assert receipt.truthfulness_receipt.runtime_truthfulness_tier is TruthfulnessTier.UNVERIFIED
    assert receipt.truthfulness_receipt.effective_truthfulness_tier is TruthfulnessTier.UNVERIFIED


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
        loader(_ensure_ir_artifact_store(store), ref)


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
        _ensure_ir_artifact_store(store),
        run_id="R_bridge",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
    )

    assert isinstance(output.bridge_ref, SimulationProofBridgeRef)
    assert isinstance(output.calibration_receipt_ref, SimulationCalibrationReceiptRef)
    bridge = load_simulation_proof_bridge(_ensure_ir_artifact_store(store), output.bridge_ref)
    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
    proof = load_proof_bundle(_ensure_ir_artifact_store(store), output.proof_bundle_ref)

    assert bridge.certification_status is SimulationCertificationStatus.SCENARIO
    assert bridge.proof_status == "non_identified"
    assert bridge.calibration_status == "unverified"
    assert receipt.accepted is False
    assert proof.metadata["simulation_certification_status"] == "SCENARIO"
    assert "identification_proof_missing" in bridge.degradation_reasons
    assert bridge.evidence_bundle_ref is not None
    evidence = load_causal_evidence_bundle(
        _ensure_ir_artifact_store(store), bridge.evidence_bundle_ref
    )
    evidence_manifest = _ensure_ir_artifact_store(store).get_manifest(bridge.evidence_bundle_ref)
    assert evidence_manifest.artifact_schema.version == "1.0"
    assert evidence.twin_network_result_ref is None


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
            _ensure_ir_artifact_store(store),
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
        _ensure_ir_artifact_store(store),
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
        _ensure_ir_artifact_store(store),
        run_id="R_identified",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        interface_mapping_ref=interface_mapping_ref,
        causal_query="P(Y|do(X))",
        base_proof_bundle_ref=base_proof_ref,
    )

    bridge = load_simulation_proof_bridge(_ensure_ir_artifact_store(store), output.bridge_ref)
    calibration = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
    proof = load_proof_bundle(
        _ensure_ir_artifact_store(store), ProofBundleRef.model_validate(bridge.proof_bundle_ref)
    )

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
        _ensure_ir_artifact_store(store),
        run_id="R_wrong_kind",
        simulation_result_ref=simulation_ref,
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
        _ensure_ir_artifact_store(store),
        run_id="R_unprovenanced_kind",
        simulation_result_ref=simulation_ref,
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
        _ensure_ir_artifact_store(store),
        run_id="R_impossible_receipt",
        simulation_result_ref=simulation_ref,
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
        _ensure_ir_artifact_store(store),
        run_id="R_metrics_wrong_kind",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
        _ensure_ir_artifact_store(store),
        run_id="R_forged_payload",
        simulation_result_ref=simulation_ref,
        simulation_payload=forged_payload,
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
        _ensure_ir_artifact_store(store),
        run_id="R_forged_metrics_payload",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        metrics_payload={"values": {"loss": "forged"}},
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
        _ensure_ir_artifact_store(store),
        run_id="R_explicit_mismatch",
        simulation_result_ref=simulation_ref,
        calibration_receipt=self_attested,
    )

    receipt = load_simulation_calibration_receipt(
        _ensure_ir_artifact_store(store), output.calibration_receipt_ref
    )
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
            _ensure_ir_artifact_store(store),
            run_id="R_malformed_explicit",
            simulation_result_ref=simulation_ref,
            calibration_receipt={"runtime_truthfulness_tier": "forged-tier"},
        )


def test_selected_optional_bridge_report_refuses_unreadable_profile(monkeypatch) -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.ir.analytics import simulation_proof_bridge as bridge_module

    selector = ArtifactRefModel(
        artifact_id="sha256:" + "f" * 64,
        kind="ir.constraint_report",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    store = object()

    monkeypatch.setattr(
        bridge_module, "get_json_artifact", lambda _store, _ref: {"hard_fail": True}
    )
    assert bridge_module._load_selected_report_payload(
        store, selector, role="constraint_report"
    ) == {"hard_fail": True}
    assert (
        bridge_module._load_selected_report_payload(store, None, role="constraint_report") is None
    )

    def refuse(_store, _ref):
        raise CanonicalProfileRefusalError("canon_profile_not_verified")

    monkeypatch.setattr(bridge_module, "get_json_artifact", refuse)
    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        bridge_module._load_selected_report_payload(store, selector, role="constraint_report")
    assert refusal.value.code == "canon_profile_not_verified"


def test_selected_report_refusal_persists_blocked_bridge(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    selected_report = store.put_json(
        {"hard_fail": False},
        PutOptions(kind="ir.constraint_report", media_type="application/json"),
    )
    malformed_selected_ref = ArtifactRefModel.model_validate(
        selected_report.model_dump(mode="json")
    ).model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    output = build_simulation_proof_bridge_artifacts(
        _ensure_ir_artifact_store(store),
        run_id="R_selected_constraint_refusal",
        simulation_result_ref=simulation_ref,
        constraint_report_ref=malformed_selected_ref,
    )

    assert output.certification_status is SimulationCertificationStatus.BLOCKED
    refusal_reason = (
        "constraint_report_selected_refused:simulation_bridge_constraint_report_selected_unreadable"
    )
    assert refusal_reason in output.degradation_reasons
    bridge = load_simulation_proof_bridge(_ensure_ir_artifact_store(store), output.bridge_ref)
    assert bridge.certification_status is SimulationCertificationStatus.BLOCKED
    assert refusal_reason in bridge.degradation_reasons


def test_valid_selected_hard_fail_constraint_blocks_bridge(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    constraint_ref = store.put_json(
        {"hard_fail": True},
        PutOptions(kind="ir.constraint_report", media_type="application/json"),
    )

    output = build_simulation_proof_bridge_artifacts(
        _ensure_ir_artifact_store(store),
        run_id="R_selected_constraint_hard_fail",
        simulation_result_ref=simulation_ref,
        constraint_report_ref=constraint_ref,
    )

    assert output.certification_status is SimulationCertificationStatus.BLOCKED
    assert "constraint_report_hard_fail" in output.degradation_reasons


def test_selected_readiness_report_refusal_blocks_and_absence_stays_optional(tmp_path) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
    from polisyos.ir.observation.causal_readiness import (
        CausalReadinessBundle,
        TransportabilityCheckEntry,
        persist_causal_readiness_bundle,
    )

    store = FileSystemCAS(tmp_path / "cas")
    ir_store = _ensure_ir_artifact_store(store)
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    readiness_ref = persist_causal_readiness_bundle(
        ir_store,
        CausalReadinessBundle(
            transport_results=[TransportabilityCheckEntry(check_id="transport", status="blocked")]
        ),
    )

    valid = build_simulation_proof_bridge_artifacts(
        ir_store,
        run_id="R_selected_readiness_valid",
        simulation_result_ref=simulation_ref,
        causal_readiness_bundle_ref=readiness_ref,
    )
    assert valid.certification_status is SimulationCertificationStatus.BLOCKED
    assert "causal_readiness_blocked" in valid.degradation_reasons

    malformed_ref = CoreArtifactRef.model_validate(
        readiness_ref.model_dump(mode="json")
    ).model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    refused = build_simulation_proof_bridge_artifacts(
        ir_store,
        run_id="R_selected_readiness_refused",
        simulation_result_ref=simulation_ref,
        causal_readiness_bundle_ref=malformed_ref,
    )
    refusal_reason = (
        "causal_readiness_bundle_selected_refused:"
        "simulation_bridge_causal_readiness_bundle_selected_unreadable"
    )
    assert refused.certification_status is SimulationCertificationStatus.BLOCKED
    assert refusal_reason in refused.degradation_reasons

    absent = build_simulation_proof_bridge_artifacts(
        ir_store,
        run_id="R_selected_readiness_absent",
        simulation_result_ref=simulation_ref,
    )
    assert absent.certification_status is SimulationCertificationStatus.SCENARIO
    assert not any(
        reason.startswith("causal_readiness_bundle_selected_refused:")
        for reason in absent.degradation_reasons
    )
