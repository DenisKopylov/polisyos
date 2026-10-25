"""Decision-packet consumer tests for EvidenceBundle owner admission."""

from dataclasses import replace
from types import SimpleNamespace

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics import evidence_bundle as evidence_bundle_module
from polisyos.ir.analytics.evidence_bundle import (
    EvidenceBundle,
    persist_causal_evidence_bundle,
)
from polisyos.ir.artifacts.io import put_json_artifact
from polisyos.ir.registry.refs import EvidenceBundleRef, ProofBundleRef
from polisyos.scientist.nodes.builtins.decide.decision_packet import causal_sections


def _bundle_with_proof(run_id: str) -> EvidenceBundle:
    return EvidenceBundle(
        run_id=run_id,
        query_str="P(Y|do(X))",
        proof_bundle_ref=ProofBundleRef(artifact_id="sha256:" + "b" * 64),
    )


def test_decision_packet_projects_proof_ref_from_fresh_owned_bundle(tmp_path):
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    bundle = _bundle_with_proof("owned-positive")
    ref = persist_causal_evidence_bundle(store, bundle)

    projected: dict[str, object] = {}
    packet_payload: dict[str, object] = {}
    causal_sections._populate_causal_evidence(
        SimpleNamespace(store=store),
        ref,
        projected,
        packet_payload,
    )

    assert projected["proof_bundle_ref"] == "sha256:" + "b" * 64
    assert not packet_payload.get("degraded_paths")


def test_decision_packet_refuses_projection_when_actual_shared_admission_is_removed(
    tmp_path, monkeypatch
):
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    bundle = _bundle_with_proof("admission-removal")
    ref = persist_causal_evidence_bundle(store, bundle)
    admitted = evidence_bundle_module.load_causal_evidence_bundle_with_admission(store, ref)

    # The DTO and every owner marker remain intact; only the resolved admission is removed.
    # This drives the actual internal loader and actual decision-packet consumer.
    unadmitted = replace(admitted, admission=None)
    assert unadmitted.value.proof_bundle_ref == bundle.proof_bundle_ref
    assert unadmitted.contract_id == admitted.contract_id
    assert unadmitted.dto_fqn == admitted.dto_fqn
    assert unadmitted.abi_key == admitted.abi_key
    assert unadmitted.registry_key == admitted.registry_key
    assert unadmitted.purpose == admitted.purpose
    assert unadmitted.raw_bytes == admitted.raw_bytes
    assert unadmitted.manifest_profile_sha256 == admitted.manifest_profile_sha256
    monkeypatch.setattr(
        evidence_bundle_module,
        "_get_owned_json_artifact_with_bytes",
        lambda *_args, **_kwargs: unadmitted,
    )

    projected: dict[str, object] = {}
    packet_payload: dict[str, object] = {}
    causal_sections._populate_causal_evidence(
        SimpleNamespace(store=store),
        ref,
        projected,
        packet_payload,
    )

    assert "proof_bundle_ref" not in projected
    degraded = packet_payload["degraded_paths"]
    assert isinstance(degraded, list)
    assert any(
        item.get("reason") == "causal_method_evidence_load_failed"
        for item in degraded
        if isinstance(item, dict)
    )


def test_decision_packet_degrades_legacy_payload_with_noncanonical_profile(tmp_path):
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    bundle = _bundle_with_proof("legacy-profile-mismatch")
    payload = bundle.model_dump(mode="json")
    payload["twin_network_result_ref"] = None
    raw_ref = put_json_artifact(
        store,
        payload,
        kind="fabric.evidence_bundle",
        schema_name="ir.causal_evidence_bundle",
        schema_version="1.0",
        canon_spec=evidence_bundle_module.CanonSpec(
            forbid_floats=False,
            exclude_none=False,
        ),
    )
    ref = EvidenceBundleRef.model_validate(raw_ref)

    # Plain DTO parsing alone exposes the proof ref; the consumer must use owner admission.
    assert EvidenceBundle.model_validate(payload).proof_bundle_ref == bundle.proof_bundle_ref
    projected: dict[str, object] = {}
    packet_payload: dict[str, object] = {}
    causal_sections._populate_causal_evidence(
        SimpleNamespace(store=store),
        ref,
        projected,
        packet_payload,
    )

    assert "proof_bundle_ref" not in projected
    degraded = packet_payload["degraded_paths"]
    assert isinstance(degraded, list)
    assert any(
        item.get("reason") == "causal_method_evidence_load_failed"
        for item in degraded
        if isinstance(item, dict)
    )
