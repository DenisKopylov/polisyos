from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
from polisyos.ir.analytics.causal import (
    ProofBundle,
    load_proof_bundle,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
)
from polisyos.ir.analytics.proof_composability import (
    ProofComposabilityStatus,
    ProofGraphWitness,
    ProofObligationKind,
    ProofReplayStepStatus,
    ProofWitnessIndex,
    attach_proof_composability_to_proof_bundle,
    build_proof_composability_certificate,
    infer_proof_composability_status,
    load_proof_composability_certificate,
    load_proof_witness_index,
    persist_proof_composability_certificate,
    persist_proof_witness_index,
)
from polisyos.ir.refs import (
    EvidenceBundleRef,
    ProofComposabilityCertificateRef,
    ProofWitnessIndexRef,
)


def _sha(char: str) -> str:
    return f"sha256:{char * 64}"


def _evidence_ref() -> EvidenceBundleRef:
    return EvidenceBundleRef.model_validate(
        {
            "artifact_id": _sha("1"),
            "kind": "fabric.evidence_bundle",
            "media_type": "application/json",
        }
    )


def _proof_bundle() -> ProofBundle:
    return ProofBundle(
        proof_status="identified",
        proof_stratum="A0_trusted",
        theorem_family="id_v1",
        completeness_regime="complete",
        implementation_coverage="declared-scope:id_v1",
        proof_trace=["rule1", "rule2"],
    )


def test_infer_proof_composability_status_distinguishes_reuse_modes() -> None:
    assert (
        infer_proof_composability_status(
            step_statuses={"s1": ProofReplayStepStatus.VALID},
            projection_preservation_passed=True,
        )
        is ProofComposabilityStatus.REUSABLE
    )
    assert (
        infer_proof_composability_status(
            step_statuses={"s1": ProofReplayStepStatus.UNKNOWN},
            projection_preservation_passed=False,
        )
        is ProofComposabilityStatus.REVALIDATE
    )
    assert (
        infer_proof_composability_status(
            step_statuses={"s1": ProofReplayStepStatus.INVALID},
            broken_witness_ids=("w1",),
        )
        is ProofComposabilityStatus.REDERIVE
    )


def test_proof_witness_index_rejects_unknown_witness_links() -> None:
    witness = ProofGraphWitness(
        witness_id="w1",
        obligation_kind=ProofObligationKind.M_SEPARATION,
        support_vars=("X", "Y"),
        projection_hash="proj-1",
    )

    with pytest.raises(ValueError, match="unknown witness ids"):
        ProofWitnessIndex(
            witnesses=(witness,),
            step_to_witness_ids={"s1": ("missing",)},
        )


def test_proof_composability_artifacts_round_trip_and_attach_to_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    witness = ProofGraphWitness(
        witness_id="w_backdoor",
        obligation_kind=ProofObligationKind.M_SEPARATION,
        support_vars=("X", "Y", "Z"),
        mutilation="remove_in(X)",
        projection_hash="proj-backdoor",
        separation_statement="Y ⟂ Z | X in G_barX",
    )
    witness_index = ProofWitnessIndex(
        witnesses=(witness,),
        step_to_witness_ids={"s1": ("w_backdoor",)},
        proof_support_projection_hash="proj-backdoor",
    )
    witness_ref = persist_proof_witness_index(store, witness_index)
    certificate = build_proof_composability_certificate(
        source_fragment_id="fragment_a",
        checked_query="P(Y|do(X))",
        composed_graph_ref="artifact:graph:composed",
        proof_trace_ref=_evidence_ref(),
        witness_index_ref=witness_ref,
        preserved_witness_ids=("w_backdoor",),
        step_statuses={"s1": ProofReplayStepStatus.VALID},
        projection_preservation_passed=True,
        proof_support_projection_hash="proj-backdoor",
    )
    certificate_ref = persist_proof_composability_certificate(store, certificate)
    loaded_index = load_proof_witness_index(store, witness_ref)
    loaded_certificate = load_proof_composability_certificate(store, certificate_ref)
    attached_bundle = attach_proof_composability_to_proof_bundle(
        _proof_bundle(),
        certificate_ref,
        loaded_certificate,
    )
    proof_ref = persist_proof_bundle(store, attached_bundle)
    loaded_bundle = load_proof_bundle(store, proof_ref)

    assert loaded_index == witness_index
    assert loaded_certificate.status is ProofComposabilityStatus.REUSABLE
    assert loaded_bundle.proof_trace_ref == _evidence_ref()
    assert loaded_bundle.composability_status == "reusable"
    assert loaded_bundle.composability_certificate_ref == certificate_ref
    assert loaded_bundle.witness_index_ref == witness_ref
    assert loaded_bundle.proof_support_projection_hash == "proj-backdoor"
    assert loaded_bundle.metadata["proof_composability"]["status"] == "reusable"


def test_proof_bundle_translation_reads_composability_metadata() -> None:
    trace_ref = _evidence_ref()
    composability_ref = ProofComposabilityCertificateRef.model_validate(
        {
            "artifact_id": _sha("2"),
            "kind": "ir.proof_composability_certificate",
            "media_type": "application/json",
        }
    )
    witness_ref = ProofWitnessIndexRef.model_validate(
        {
            "artifact_id": _sha("3"),
            "kind": "ir.proof_witness_index",
            "media_type": "application/json",
        }
    )
    result = SimpleNamespace(
        status=IdentificationStatus.IDENTIFIED,
        algorithm_version="id_v1",
        estimand_ast=None,
        trace=["rule1", "rule2"],
        query_str="P(Y|do(X))",
        required_distributions=[],
        metadata={
            "proof_trace_ref": trace_ref.model_dump(mode="json"),
            "composability_status": "revalidate",
            "composability_certificate_ref": composability_ref.model_dump(mode="json"),
            "witness_index_ref": witness_ref.model_dump(mode="json"),
            "proof_support_projection_hash": "proj-2",
            "invalidated_by_graph_hashes": ["graph-a", "graph-b"],
        },
    )

    bundle = proof_bundle_from_identification_result(result)

    assert bundle.proof_trace_ref == trace_ref
    assert bundle.composability_status == "revalidate"
    assert bundle.composability_certificate_ref == composability_ref
    assert bundle.witness_index_ref == witness_ref
    assert bundle.proof_support_projection_hash == "proj-2"
    assert bundle.invalidated_by_graph_hashes == ["graph-a", "graph-b"]


def test_proof_bundle_translation_reads_operator_lift_metadata() -> None:
    result = SimpleNamespace(
        status=IdentificationStatus.IDENTIFIED,
        algorithm_version="id_v1",
        estimand_ast=None,
        trace=["rule1"],
        query_str="operator query",
        required_distributions=[],
        metadata={
            "uniform_probe_class_ref": "rkhs://outcome/unit-ball",
            "operator_lift_allowed": True,
            "operator_lift_scope": "whole_probe_space",
            "operator_lift_reason": "counterfactual_distribution_identified_via_backdoor_for_all_g_in_HY",
        },
    )

    bundle = proof_bundle_from_identification_result(result)

    assert bundle.uniform_probe_class_ref == "rkhs://outcome/unit-ball"
    assert bundle.operator_lift_allowed is True
    assert bundle.operator_lift_scope == "whole_probe_space"
    assert (
        bundle.operator_lift_reason
        == "counterfactual_distribution_identified_via_backdoor_for_all_g_in_HY"
    )
