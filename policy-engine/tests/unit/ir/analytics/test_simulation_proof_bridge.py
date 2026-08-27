from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
from polisyos.ir.analytics.causal import ProofBundle, load_proof_bundle, persist_proof_bundle
from polisyos.ir.analytics.simulation_proof_bridge import (
    SimulationCertificationStatus,
    build_simulation_proof_bridge_artifacts,
    load_simulation_calibration_receipt,
    load_simulation_proof_bridge,
)
from polisyos.ir.registry.refs import (
    InterfaceMappingRef,
    ProofBundleRef,
    SimulationCalibrationReceiptRef,
    SimulationProofBridgeRef,
)


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


def test_simulation_proof_bridge_preserves_identified_base_proof_when_receipts_pass(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref = store.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": {"loss": "1.0"}},
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
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
    receipt = TruthfulnessReceipt(
        runtime_truthfulness_tier=TruthfulnessTier.APPROXIMATE_CALIBRATED,
        truthfulness_scope=TruthfulnessScope.POSTERIOR,
    )

    output = build_simulation_proof_bridge_artifacts(
        store,
        run_id="R_identified",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        interface_mapping_ref=interface_mapping_ref,
        causal_query="P(Y|do(X))",
        base_proof_bundle_ref=base_proof_ref,
        calibration_receipt=receipt,
    )

    bridge = load_simulation_proof_bridge(store, output.bridge_ref)
    proof = load_proof_bundle(store, ProofBundleRef.model_validate(bridge.proof_bundle_ref))

    assert bridge.certification_status is SimulationCertificationStatus.IDENTIFIED
    assert bridge.base_proof_bundle_ref == base_proof_ref
    assert proof.proof_status == "identified"
    assert proof.metadata["base_proof_ref"] == base_proof_ref.model_dump(mode="json")
