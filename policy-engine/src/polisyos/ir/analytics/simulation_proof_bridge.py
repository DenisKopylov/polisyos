"""Bridge simulation outputs into causal proof and calibration artifact surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
    extract_truthfulness_receipt,
    truthfulness_depth,
    validate_truthfulness_receipt,
)
from polisyos.ir.analytics.causal import ProofBundle, load_proof_bundle, persist_proof_bundle
from polisyos.ir.analytics.evidence_bundle import (
    DataProvenance,
    EvidenceBundle,
    persist_causal_evidence_bundle,
)
from polisyos.ir.analytics.proof_composability import (
    ProofComposabilityStatus,
    ProofWitnessIndex,
    attach_proof_composability_to_proof_bundle,
    build_proof_composability_certificate,
    persist_proof_composability_certificate,
    persist_proof_witness_index,
)
from polisyos.ir.artifacts import (
    ArtifactID,
    ArtifactStore,
    InputRef,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    EvidenceBundleRef,
    InterfaceMappingRef,
    ProofBundleRef,
    SimulationCalibrationReceiptRef,
    SimulationProofBridgeRef,
)

_SCHEMA_VERSION = "1.0"
_UNSPECIFIED_ASSUMPTIONS = {
    "cost_model": "unspecified",
    "noise_model": "unspecified",
    "allowed_adaptive_designs": "unspecified",
}
_CALIBRATED_TIERS = (
    TruthfulnessTier.APPROXIMATE_CALIBRATED,
    TruthfulnessTier.ASYMPTOTIC,
    TruthfulnessTier.EXACT,
)


class SimulationCertificationStatus(str, Enum):
    """Decision-facing causal status for a quantitative simulation output."""

    IDENTIFIED = "IDENTIFIED"
    BOUNDED = "BOUNDED"
    SCENARIO = "SCENARIO"
    BLOCKED = "BLOCKED"


class SimulationCalibrationReceipt(BaseModel):
    """Persist the runtime calibration/truthfulness receipt for one simulation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    simulation_result_ref: ArtifactRefModel
    metrics_ref: ArtifactRefModel | None = None
    source: Literal["explicit", "simulation_result", "metrics", "default_unverified"]
    truthfulness_receipt: TruthfulnessReceipt
    accepted: bool
    degradation_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationProofBridge(BaseModel):
    """CAS-backed bridge from a simulation result to evidence, proof, and calibration refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    run_id: str
    simulation_result_ref: ArtifactRefModel
    metrics_ref: ArtifactRefModel | None = None
    state_snapshot_ref: ArtifactRefModel | None = None
    constraint_report_ref: ArtifactRefModel | None = None
    environment_manifest_ref: ArtifactRefModel | None = None
    tee_attestation_ref: ArtifactRefModel | None = None
    sbom_ref: ArtifactRefModel | None = None
    evidence_bundle_ref: EvidenceBundleRef
    proof_bundle_ref: ProofBundleRef
    calibration_receipt_ref: SimulationCalibrationReceiptRef
    base_proof_bundle_ref: ProofBundleRef | None = None
    interface_mapping_ref: InterfaceMappingRef | None = None
    causal_readiness_bundle_ref: ArtifactRefModel | None = None
    causal_validity_bundle_ref: ArtifactRefModel | None = None
    causal_query_ref: ArtifactRefModel | None = None
    certification_status: SimulationCertificationStatus
    proof_status: Literal["identified", "non_identified", "oracle_needed"]
    calibration_status: Literal["accepted", "unverified"]
    composability_status: Literal["reusable", "revalidate", "rederive", "unknown"]
    degradation_reasons: tuple[str, ...] = ()
    unspecified_assumptions: dict[str, Literal["unspecified"]] = Field(
        default_factory=lambda: dict(_UNSPECIFIED_ASSUMPTIONS)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationProofBridgeArtifacts(BaseModel):
    """Return all refs materialized by the simulation proof bridge stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bridge_ref: SimulationProofBridgeRef
    calibration_receipt_ref: SimulationCalibrationReceiptRef
    evidence_bundle_ref: EvidenceBundleRef
    proof_bundle_ref: ProofBundleRef
    witness_index_ref: ArtifactRefModel
    composability_certificate_ref: ArtifactRefModel
    certification_status: SimulationCertificationStatus
    degradation_reasons: tuple[str, ...] = ()


def persist_simulation_calibration_receipt(
    store: ArtifactStore,
    receipt: SimulationCalibrationReceipt,
    *,
    inputs: Sequence[Any] | None = None,
    schema_name: str = "ir.simulation_calibration_receipt",
    schema_version: str = _SCHEMA_VERSION,
) -> SimulationCalibrationReceiptRef:
    """Persist a simulation calibration receipt and return its typed ref."""

    ref = put_json_artifact(
        store,
        receipt.model_dump(mode="json"),
        kind="ir.simulation_calibration_receipt",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SimulationCalibrationReceiptRef.model_validate(ref)


def load_simulation_calibration_receipt(
    store: ArtifactStore,
    ref: SimulationCalibrationReceiptRef,
) -> SimulationCalibrationReceipt:
    """Load a persisted simulation calibration receipt."""

    payload = get_json_artifact(store, ref.artifact_id)
    return SimulationCalibrationReceipt.model_validate(payload)


def persist_simulation_proof_bridge(
    store: ArtifactStore,
    bridge: SimulationProofBridge,
    *,
    inputs: Sequence[Any] | None = None,
    schema_name: str = "ir.simulation_proof_bridge",
    schema_version: str = _SCHEMA_VERSION,
) -> SimulationProofBridgeRef:
    """Persist a simulation-proof bridge and return its typed ref."""

    ref = put_json_artifact(
        store,
        bridge.model_dump(mode="json"),
        kind="ir.simulation_proof_bridge",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SimulationProofBridgeRef.model_validate(ref)


def load_simulation_proof_bridge(
    store: ArtifactStore,
    ref: SimulationProofBridgeRef,
) -> SimulationProofBridge:
    """Load a persisted simulation-proof bridge."""

    payload = get_json_artifact(store, ref.artifact_id)
    return SimulationProofBridge.model_validate(payload)


def build_simulation_proof_bridge_artifacts(
    store: ArtifactStore,
    *,
    run_id: str,
    simulation_result_ref: Any,
    metrics_ref: Any | None = None,
    state_snapshot_ref: Any | None = None,
    constraint_report_ref: Any | None = None,
    environment_manifest_ref: Any | None = None,
    tee_attestation_ref: Any | None = None,
    sbom_ref: Any | None = None,
    interface_mapping_ref: Any | None = None,
    causal_readiness_bundle_ref: Any | None = None,
    causal_validity_bundle_ref: Any | None = None,
    causal_query_ref: Any | None = None,
    base_proof_bundle_ref: Any | None = None,
    simulation_payload: Mapping[str, Any] | None = None,
    metrics_payload: Mapping[str, Any] | None = None,
    causal_query: str | None = None,
    calibration_receipt: TruthfulnessReceipt | Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SimulationProofBridgeArtifacts:
    """Materialize EvidenceBundle, ProofBundle, calibration receipt, and bridge refs."""

    sim_ref = _coerce_ref(simulation_result_ref)
    metric_ref = _coerce_optional_ref(metrics_ref)
    state_ref = _coerce_optional_ref(state_snapshot_ref)
    constraint_ref = _coerce_optional_ref(constraint_report_ref)
    environment_ref = _coerce_optional_ref(environment_manifest_ref)
    tee_ref = _coerce_optional_ref(tee_attestation_ref)
    software_ref = _coerce_optional_ref(sbom_ref)
    mapping_ref = _coerce_typed_optional_ref(interface_mapping_ref, InterfaceMappingRef)
    readiness_ref = _coerce_optional_ref(causal_readiness_bundle_ref)
    validity_ref = _coerce_optional_ref(causal_validity_bundle_ref)
    query_ref = _coerce_optional_ref(causal_query_ref)
    base_proof_ref = _coerce_typed_optional_ref(base_proof_bundle_ref, ProofBundleRef)

    if simulation_payload is None:
        simulation_payload = _load_payload(store, sim_ref)
    if metrics_payload is None and metric_ref is not None:
        metrics_payload = _load_payload(store, metric_ref)

    lineage_inputs = _lineage_inputs(
        (
            ("simulation_result", sim_ref),
            ("metrics", metric_ref),
            ("state_snapshot", state_ref),
            ("constraint_report", constraint_ref),
            ("environment_manifest", environment_ref),
            ("tee_attestation", tee_ref),
            ("sbom", software_ref),
            ("interface_mapping", mapping_ref),
            ("causal_readiness_bundle", readiness_ref),
            ("causal_validity_bundle", validity_ref),
            ("causal_query", query_ref),
            ("base_proof_bundle", base_proof_ref),
        )
    )

    receipt, receipt_source = _resolve_truthfulness_receipt(
        explicit=calibration_receipt,
        simulation_payload=simulation_payload,
        metrics_payload=metrics_payload,
    )
    calibration_accepted = _receipt_is_calibrated(receipt)
    calibration_model = SimulationCalibrationReceipt(
        simulation_result_ref=sim_ref,
        metrics_ref=metric_ref,
        source=receipt_source,
        truthfulness_receipt=receipt,
        accepted=calibration_accepted,
        degradation_reasons=tuple(receipt.degradation_reasons),
        metadata={
            "truthfulness_scope": (
                receipt.truthfulness_scope.value if receipt.truthfulness_scope is not None else None
            ),
            "effective_truthfulness_tier": (
                receipt.effective_truthfulness_tier.value
                if receipt.effective_truthfulness_tier is not None
                else None
            ),
        },
    )
    calibration_ref = persist_simulation_calibration_receipt(
        store,
        calibration_model,
        inputs=lineage_inputs,
    )

    query_text = _query_text(causal_query=causal_query, causal_query_ref=query_ref)
    evidence = EvidenceBundle(
        run_id=run_id,
        query_str=query_text,
        data_provenance=_data_provenance(
            (
                ("simulation_result", sim_ref),
                ("metrics", metric_ref),
                ("state_snapshot", state_ref),
                ("constraint_report", constraint_ref),
                ("environment_manifest", environment_ref),
                ("tee_attestation", tee_ref),
                ("sbom", software_ref),
            )
        ),
        diagnostic_scores=_diagnostic_scores(receipt=receipt, calibration_accepted=calibration_accepted),
        method_config={
            "bridge": "simulation_proof_bridge",
            "bridge_version": _SCHEMA_VERSION,
            "unspecified_assumptions": dict(_UNSPECIFIED_ASSUMPTIONS),
        },
        identification_status="pending_proof_bridge",
        algorithm_version="simulation_proof_bridge.v1",
        created_at=_utc_now(),
    )
    evidence_ref = persist_causal_evidence_bundle(store, evidence, inputs=lineage_inputs)

    proof, proof_status = _build_or_extend_proof_bundle(
        store=store,
        evidence_ref=evidence_ref,
        base_proof_ref=base_proof_ref,
        query_text=query_text,
        query_ref=query_ref,
        graph_ref=metadata.get("graph_ref") if isinstance(metadata, Mapping) else None,
        lineage={
            "simulation_result_ref": sim_ref.model_dump(mode="json"),
            "metrics_ref": metric_ref.model_dump(mode="json") if metric_ref is not None else None,
            "calibration_receipt_ref": calibration_ref.model_dump(mode="json"),
            "evidence_bundle_ref": evidence_ref.model_dump(mode="json"),
        },
    )
    witness_index = ProofWitnessIndex(
        proof_support_projection_hash=proof.proof_support_projection_hash,
        metadata={"source": "simulation_proof_bridge", "run_id": run_id},
    )
    witness_ref = persist_proof_witness_index(store, witness_index, inputs=lineage_inputs)
    composability_status = _resolve_composability_status(proof)
    certificate = build_proof_composability_certificate(
        source_fragment_id="simulation_proof_bridge",
        checked_query=query_text,
        proof_trace_ref=evidence_ref,
        witness_index_ref=witness_ref,
        projection_preservation_passed=None,
        metadata={"reason": "simulation_bridge_does_not_replay_graphical_witnesses"},
        status=composability_status,
    )
    certificate_ref = persist_proof_composability_certificate(
        store,
        certificate,
        inputs=lineage_inputs,
    )
    proof = attach_proof_composability_to_proof_bundle(proof, certificate_ref, certificate)

    reasons = _degradation_reasons(
        has_causal_query=causal_query is not None or query_ref is not None,
        has_interface_mapping=mapping_ref is not None,
        base_proof_ref=base_proof_ref,
        calibration_receipt=receipt,
        calibration_accepted=calibration_accepted,
        composability_status=composability_status.value,
        constraint_payload=_load_payload(store, constraint_ref) if constraint_ref is not None else None,
        readiness_payload=_load_payload(store, readiness_ref) if readiness_ref is not None else None,
        validity_payload=_load_payload(store, validity_ref) if validity_ref is not None else None,
    )
    certification_status = _certification_status(
        proof=proof,
        calibration_accepted=calibration_accepted,
        composability_status=composability_status.value,
        has_causal_query=causal_query is not None or query_ref is not None,
        has_interface_mapping=mapping_ref is not None,
        blocked=_has_blocking_reason(reasons),
    )
    proof_metadata = dict(proof.metadata)
    proof_metadata["simulation_certification_status"] = certification_status.value
    proof_metadata["simulation_degradation_reasons"] = list(reasons)
    proof_metadata["unspecified_assumptions"] = dict(_UNSPECIFIED_ASSUMPTIONS)
    proof = proof.model_copy(update={"metadata": proof_metadata})
    proof_ref = persist_proof_bundle(
        store,
        proof,
        inputs=[*lineage_inputs, _input_ref(evidence_ref, "proof_trace")],
    )

    bridge = SimulationProofBridge(
        run_id=run_id,
        simulation_result_ref=sim_ref,
        metrics_ref=metric_ref,
        state_snapshot_ref=state_ref,
        constraint_report_ref=constraint_ref,
        environment_manifest_ref=environment_ref,
        tee_attestation_ref=tee_ref,
        sbom_ref=software_ref,
        evidence_bundle_ref=evidence_ref,
        proof_bundle_ref=proof_ref,
        calibration_receipt_ref=calibration_ref,
        base_proof_bundle_ref=base_proof_ref,
        interface_mapping_ref=mapping_ref,
        causal_readiness_bundle_ref=readiness_ref,
        causal_validity_bundle_ref=validity_ref,
        causal_query_ref=query_ref,
        certification_status=certification_status,
        proof_status=proof_status,
        calibration_status="accepted" if calibration_accepted else "unverified",
        composability_status=composability_status.value,
        degradation_reasons=reasons,
        metadata={
            **dict(metadata or {}),
            "bridge_version": _SCHEMA_VERSION,
            "calibration_receipt_source": receipt_source,
        },
    )
    bridge_ref = persist_simulation_proof_bridge(
        store,
        bridge,
        inputs=[
            *lineage_inputs,
            _input_ref(evidence_ref, "evidence_bundle"),
            _input_ref(proof_ref, "proof_bundle"),
            _input_ref(calibration_ref, "calibration_receipt"),
        ],
    )
    return SimulationProofBridgeArtifacts(
        bridge_ref=bridge_ref,
        calibration_receipt_ref=calibration_ref,
        evidence_bundle_ref=evidence_ref,
        proof_bundle_ref=proof_ref,
        witness_index_ref=ArtifactRefModel.model_validate(witness_ref.model_dump(mode="json")),
        composability_certificate_ref=ArtifactRefModel.model_validate(
            certificate_ref.model_dump(mode="json")
        ),
        certification_status=certification_status,
        degradation_reasons=reasons,
    )


def _coerce_ref(value: Any) -> ArtifactRefModel:
    if isinstance(value, ArtifactRefModel):
        return value
    if hasattr(value, "model_dump"):
        return ArtifactRefModel.model_validate(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return ArtifactRefModel.model_validate(dict(value))
    raise TypeError("artifact ref must be a mapping or model with model_dump()")


def _coerce_optional_ref(value: Any | None) -> ArtifactRefModel | None:
    if value is None:
        return None
    return _coerce_ref(value)


def _coerce_typed_optional_ref(model: Any | None, ref_type: type[BaseModel]) -> Any | None:
    if model is None:
        return None
    ref = _coerce_ref(model)
    return ref_type.model_validate(ref.model_dump(mode="json"))


def _input_ref(ref: Any, role: str) -> InputRef:
    normalized = _coerce_ref(ref)
    return InputRef(artifact_id=ArtifactID.model_validate(str(normalized.artifact_id)), role=role)


def _lineage_inputs(items: Sequence[tuple[str, Any | None]]) -> list[InputRef]:
    inputs: list[InputRef] = []
    for role, ref in items:
        if ref is not None:
            inputs.append(_input_ref(ref, role))
    return inputs


def _load_payload(store: ArtifactStore, ref: ArtifactRefModel | None) -> dict[str, Any] | None:
    if ref is None:
        return None
    try:
        payload = get_json_artifact(store, ref.artifact_id)
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def _resolve_truthfulness_receipt(
    *,
    explicit: TruthfulnessReceipt | Mapping[str, Any] | None,
    simulation_payload: Mapping[str, Any] | None,
    metrics_payload: Mapping[str, Any] | None,
) -> tuple[TruthfulnessReceipt, Literal["explicit", "simulation_result", "metrics", "default_unverified"]]:
    if explicit is not None:
        receipt = validate_truthfulness_receipt(explicit)
        if receipt is not None:
            return receipt, "explicit"
    for source, payload in (
        ("simulation_result", simulation_payload),
        ("metrics", metrics_payload),
    ):
        receipt = extract_truthfulness_receipt(payload)
        if receipt is not None:
            return receipt, source
    return (
        TruthfulnessReceipt(
            runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
            truthfulness_scope=TruthfulnessScope.POSTERIOR,
            diagnostics={"source": "simulation_proof_bridge"},
            degradation_reasons=("runtime_calibration_receipt_missing",),
        ),
        "default_unverified",
    )


def _receipt_is_calibrated(receipt: TruthfulnessReceipt) -> bool:
    tier = receipt.effective_truthfulness_tier or receipt.runtime_truthfulness_tier
    return any(truthfulness_depth(tier) >= truthfulness_depth(candidate) for candidate in _CALIBRATED_TIERS)


def _diagnostic_scores(
    *,
    receipt: TruthfulnessReceipt,
    calibration_accepted: bool,
) -> dict[str, float]:
    tier_depth = truthfulness_depth(
        receipt.effective_truthfulness_tier or receipt.runtime_truthfulness_tier
    )
    return {
        "calibration_accepted": 1.0 if calibration_accepted else 0.0,
        "truthfulness_depth": float(tier_depth),
    }


def _data_provenance(items: Sequence[tuple[str, ArtifactRefModel | None]]) -> tuple[DataProvenance, ...]:
    provenance: list[DataProvenance] = []
    for role, ref in items:
        if ref is None:
            continue
        provenance.append(
            DataProvenance(
                dataset_ref=str(ref.artifact_id),
                domain=role,
                availability_status="available",
            )
        )
    return tuple(provenance)


def _build_or_extend_proof_bundle(
    *,
    store: ArtifactStore,
    evidence_ref: EvidenceBundleRef,
    base_proof_ref: ProofBundleRef | None,
    query_text: str,
    query_ref: ArtifactRefModel | None,
    graph_ref: Any | None,
    lineage: Mapping[str, Any],
) -> tuple[ProofBundle, Literal["identified", "non_identified", "oracle_needed"]]:
    if base_proof_ref is not None:
        base = load_proof_bundle(store, base_proof_ref)
        metadata = {
            **dict(base.metadata),
            "base_proof_ref": base_proof_ref.model_dump(mode="json"),
            "simulation_bridge_lineage": dict(lineage),
        }
        query_ref_text = str(query_ref.artifact_id) if query_ref is not None else base.query_ref
        graph_ref_text = str(graph_ref) if graph_ref is not None else base.graph_ref
        return (
            base.model_copy(
                update={
                    "proof_trace_ref": evidence_ref,
                    "query_ref": query_ref_text,
                    "graph_ref": graph_ref_text,
                    "metadata": metadata,
                }
            ),
            base.proof_status,
        )

    proof = ProofBundle(
        proof_status="non_identified",
        proof_stratum="A1_extended",
        theorem_family="simulation_proof_bridge.v1",
        completeness_regime="heuristic_backed",
        implementation_coverage="bridge_created_without_identification_trace",
        graph_ref=str(graph_ref) if graph_ref is not None else None,
        query_ref=str(query_ref.artifact_id) if query_ref is not None else None,
        proof_trace_ref=evidence_ref,
        proof_trace=[
            "Simulation output persisted.",
            "No reusable causal identification proof was supplied to the bridge.",
        ],
        composability_status="unknown",
        assumptions=["simulator_validity_assumptions_declared_or_unspecified"],
        metadata={
            "query_text": query_text,
            "simulation_bridge_lineage": dict(lineage),
            "unspecified_assumptions": dict(_UNSPECIFIED_ASSUMPTIONS),
        },
    )
    return proof, "non_identified"


def _resolve_composability_status(proof: ProofBundle) -> ProofComposabilityStatus:
    try:
        return ProofComposabilityStatus(proof.composability_status)
    except ValueError:
        return ProofComposabilityStatus.UNKNOWN


def _degradation_reasons(
    *,
    has_causal_query: bool,
    has_interface_mapping: bool,
    base_proof_ref: ProofBundleRef | None,
    calibration_receipt: TruthfulnessReceipt,
    calibration_accepted: bool,
    composability_status: str,
    constraint_payload: Mapping[str, Any] | None,
    readiness_payload: Mapping[str, Any] | None,
    validity_payload: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not has_causal_query:
        reasons.append("causal_query_unspecified")
    if not has_interface_mapping:
        reasons.append("interface_mapping_missing")
    if base_proof_ref is None:
        reasons.append("identification_proof_missing")
    if not calibration_accepted:
        reasons.extend(calibration_receipt.degradation_reasons or ("calibration_unverified",))
    if composability_status not in {"reusable", "revalidate"}:
        reasons.append(f"proof_composability_{composability_status}")
    if _constraint_blocked(constraint_payload):
        reasons.append("constraint_report_hard_fail")
    if _readiness_blocked(readiness_payload):
        reasons.append("causal_readiness_blocked")
    if _validity_failed(validity_payload):
        reasons.append("causal_validity_failed")
    return tuple(dict.fromkeys(reason for reason in reasons if reason))


def _certification_status(
    *,
    proof: ProofBundle,
    calibration_accepted: bool,
    composability_status: str,
    has_causal_query: bool,
    has_interface_mapping: bool,
    blocked: bool,
) -> SimulationCertificationStatus:
    if blocked:
        return SimulationCertificationStatus.BLOCKED
    if proof.proof_status == "oracle_needed":
        return SimulationCertificationStatus.BLOCKED
    if proof.proof_status == "identified":
        if (
            calibration_accepted
            and composability_status in {"reusable", "revalidate"}
            and has_causal_query
            and has_interface_mapping
        ):
            return SimulationCertificationStatus.IDENTIFIED
        return SimulationCertificationStatus.SCENARIO
    if proof.metadata.get("bounds_bundle_ref") or proof.metadata.get("partial_identification"):
        return SimulationCertificationStatus.BOUNDED
    return SimulationCertificationStatus.SCENARIO


def _has_blocking_reason(reasons: Sequence[str]) -> bool:
    return any(
        reason in {"constraint_report_hard_fail", "causal_readiness_blocked", "causal_validity_failed"}
        for reason in reasons
    )


def _constraint_blocked(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return bool(payload.get("hard_fail")) or str(payload.get("status", "")).lower() in {
        "block",
        "blocked",
        "failed",
    }


def _readiness_blocked(payload: Mapping[str, Any] | None) -> bool:
    return _payload_has_status(payload, {"block", "blocked", "failed"})


def _validity_failed(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    warnings = payload.get("warnings")
    if isinstance(warnings, Sequence) and not isinstance(warnings, (str, bytes)):
        if any(":failed" in str(item) for item in warnings):
            return True
    return _payload_has_status(payload, {"failed", "block", "blocked"})


def _payload_has_status(payload: Any, blocked_values: set[str]) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key) in {"status", "decision", "readiness_status", "validity_status"}:
                if str(value).strip().lower() in blocked_values:
                    return True
            if _payload_has_status(value, blocked_values):
                return True
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return any(_payload_has_status(item, blocked_values) for item in payload)
    return False


def _query_text(*, causal_query: str | None, causal_query_ref: ArtifactRefModel | None) -> str:
    if causal_query is not None and causal_query.strip():
        return causal_query.strip()
    if causal_query_ref is not None:
        return f"artifact:{causal_query_ref.artifact_id}"
    return "simulation_output"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "SimulationCalibrationReceipt",
    "SimulationCertificationStatus",
    "SimulationProofBridge",
    "SimulationProofBridgeArtifacts",
    "build_simulation_proof_bridge_artifacts",
    "load_simulation_calibration_receipt",
    "load_simulation_proof_bridge",
    "persist_simulation_calibration_receipt",
    "persist_simulation_proof_bridge",
]
