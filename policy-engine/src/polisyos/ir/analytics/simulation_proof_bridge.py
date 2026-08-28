"""Bridge simulation outputs into causal proof and calibration artifact surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics._truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
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
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
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
# Frozen to the existing Foundry producer manifests. Contract drift degrades
# calibration instead of silently widening which artifacts may authorize it.
_OWNER_ARTIFACT_CONTRACTS = {
    "simulation": (
        "foundry.simulation_result",
        "polisyos.core.SimulationResult",
        "1.3",
    ),
    "metrics": (
        "foundry.metrics",
        "polisyos.core.Metrics",
        "0.1.0",
    ),
}
_SIMULATION_RESULT_FIELDS = {
    "schema_version",
    "exec_plan_ref",
    "metrics_ref",
    "metric_observation_bundle_ref",
    "state_snapshot_ref",
    "environment_ref",
    "environment_fingerprint",
    "trace_slice_ref",
    "uncertainty_envelopes",
    "distributional_report_ref",
    "welfare_bundle_ref",
    "welfare_bound_refs",
    "metric_validation_report_ref",
    "fairness_audit_report_ref",
    "propagation_config_ref",
    "propagation_report_ref",
    "feedback_result_ref",
    "identifiability_diagnostic_ref",
    "notes",
}


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

    @model_validator(mode="after")
    def _require_current_authority_state(self) -> Self:
        if (
            self.accepted
            or self.source != "default_unverified"
            or any(
                truthfulness_depth(tier) > 0
                for tier in (
                    self.truthfulness_receipt.runtime_truthfulness_tier,
                    self.truthfulness_receipt.effective_truthfulness_tier,
                )
            )
        ):
            raise ValueError(
                "simulation calibration requires an admitted producer/verifier; "
                "current receipts must remain default_unverified, unaccepted, and runtime/effective "
                "unverified"
            )
        return self


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

    @model_validator(mode="after")
    def _require_current_authority_state(self) -> Self:
        if (
            self.calibration_status != "unverified"
            or self.certification_status is SimulationCertificationStatus.IDENTIFIED
        ):
            raise ValueError(
                "simulation proof authority requires an admitted producer/verifier; "
                "current bridges must remain calibration_status='unverified' and non-IDENTIFIED"
            )
        return self


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

    @model_validator(mode="after")
    def _require_current_authority_state(self) -> Self:
        if self.certification_status is SimulationCertificationStatus.IDENTIFIED:
            raise ValueError(
                "simulation proof authority requires an admitted producer/verifier; "
                "current artifact projections must remain non-IDENTIFIED"
            )
        return self


def persist_simulation_calibration_receipt(
    store: ArtifactStore,
    receipt: SimulationCalibrationReceipt,
    *,
    inputs: Sequence[Any] | None = None,
    schema_name: str = "ir.simulation_calibration_receipt",
    schema_version: str = _SCHEMA_VERSION,
) -> SimulationCalibrationReceiptRef:
    """Persist a simulation calibration receipt and return its typed ref."""

    validated = SimulationCalibrationReceipt.model_validate(
        receipt.model_dump(mode="python", warnings=False)
    )
    ref = put_json_artifact(
        store,
        validated.model_dump(mode="json"),
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

    validated = SimulationProofBridge.model_validate(
        bridge.model_dump(mode="python", warnings=False)
    )
    ref = put_json_artifact(
        store,
        validated.model_dump(mode="json"),
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

    bound_simulation_payload, simulation_intake_reasons = _load_truthfulness_owner_payload(
        store,
        sim_ref,
        role="simulation",
    )
    if metric_ref is not None:
        bound_metrics_payload, metrics_intake_reasons = _load_truthfulness_owner_payload(
            store,
            metric_ref,
            role="metrics",
        )
    else:
        bound_metrics_payload, metrics_intake_reasons = None, ()
    payload_binding_errors: list[str] = []
    if simulation_payload is not None and not _payloads_exact_match(
        simulation_payload,
        bound_simulation_payload,
    ):
        payload_binding_errors.append("simulation_payload_content_mismatch")
    if metrics_payload is not None and not _payloads_exact_match(
        metrics_payload,
        bound_metrics_payload,
    ):
        payload_binding_errors.append("metrics_payload_content_mismatch")

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
        intake_reasons=(
            *simulation_intake_reasons,
            *metrics_intake_reasons,
            *payload_binding_errors,
        ),
    )
    # The current strict Foundry owner DTOs cannot carry a truthfulness receipt,
    # and no admitted verifier artifact binds one to these payloads.
    calibration_accepted = False
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
        validity_payload=(
            _load_causal_validity_payload(store, validity_ref)
            if validity_ref is not None
            else None
        ),
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


def _load_truthfulness_owner_payload(
    store: ArtifactStore,
    ref: ArtifactRefModel,
    *,
    role: Literal["simulation", "metrics"],
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Reload one owner artifact and record why it cannot authorize truthfulness."""

    expected_kind, expected_schema, expected_version = _OWNER_ARTIFACT_CONTRACTS[role]
    reasons: list[str] = []
    try:
        manifest = store.get_manifest(ref.artifact_id)
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None, (f"{role}_manifest_unavailable",)

    manifest_kind = str(getattr(manifest, "kind", ""))
    manifest_media_type = str(getattr(manifest, "media_type", ""))
    manifest_artifact_id = str(getattr(manifest, "artifact_id", ""))
    if manifest_kind != expected_kind:
        reasons.append(f"{role}_manifest_kind_mismatch")
    if manifest_media_type != "application/json":
        reasons.append(f"{role}_manifest_media_type_mismatch")
    if manifest_artifact_id != str(ref.artifact_id):
        reasons.append(f"{role}_manifest_content_binding_mismatch")
    if ref.kind != manifest_kind or ref.media_type != manifest_media_type:
        reasons.append(f"{role}_ref_manifest_mismatch")

    schema = getattr(manifest, "artifact_schema", None)
    if (
        getattr(schema, "name", None) != expected_schema
        or getattr(schema, "version", None) != expected_version
    ):
        reasons.append(f"{role}_manifest_schema_mismatch")

    payload = _load_payload(store, ref)
    if payload is None or not _owner_payload_is_valid(role=role, payload=payload):
        reasons.append(f"{role}_owner_payload_invalid")

    producer = getattr(manifest, "producer", None)
    authority = getattr(manifest, "authority", None)
    if producer is None:
        reasons.append(f"{role}_truthfulness_producer_missing")
    else:
        reasons.append(f"{role}_truthfulness_producer_not_admitted")
    if authority is None:
        reasons.append(f"{role}_truthfulness_verifier_missing")
    else:
        reasons.append(f"{role}_truthfulness_verifier_not_admitted")

    return payload, tuple(dict.fromkeys(reasons))


def _owner_payload_is_valid(
    *,
    role: Literal["simulation", "metrics"],
    payload: Mapping[str, Any],
) -> bool:
    if role == "metrics":
        if not set(payload).issubset({"values", "notes"}):
            return False
        values = payload.get("values", {})
        notes = payload.get("notes", [])
        return isinstance(values, Mapping) and all(
            isinstance(value, (bool, int, float, str)) for value in values.values()
        ) and isinstance(notes, list) and all(isinstance(note, str) for note in notes)

    if not {"schema_version", "exec_plan_ref", "metrics_ref"}.issubset(payload):
        return False
    if not set(payload).issubset(_SIMULATION_RESULT_FIELDS):
        return False
    if payload.get("schema_version") != "1.3":
        return False
    return _owner_ref_is_valid(payload.get("exec_plan_ref"), kind="foundry.exec_plan") and (
        _owner_ref_is_valid(payload.get("metrics_ref"), kind="foundry.metrics")
    )


def _owner_ref_is_valid(value: Any, *, kind: str) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        ArtifactID.model_validate(str(value.get("artifact_id")))
    except (TypeError, ValueError):
        return False
    return value.get("kind") == kind and value.get("media_type") == "application/json"


def _payloads_exact_match(left: Mapping[str, Any], right: Mapping[str, Any] | None) -> bool:
    if right is None:
        return False
    try:
        spec = CanonSpec(forbid_floats=False)
        return to_canonical_bytes(dict(left), spec) == to_canonical_bytes(dict(right), spec)
    except (TypeError, ValueError):
        return False


def _load_causal_validity_payload(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> dict[str, Any]:
    """Require the Scientist-owned validity artifact, never execution evidence."""

    try:
        manifest = store.get_manifest(ref.artifact_id)
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise ValueError(f"causal_validity_bundle_ref manifest is unavailable: {exc}") from exc
    schema = getattr(manifest, "artifact_schema", None)
    schema_name = getattr(schema, "name", None)
    if (
        getattr(manifest, "kind", None) != "scientist.causal_validity_bundle"
        or schema_name != "polisyos.scientist.CausalValidityBundle"
    ):
        raise ValueError(
            "causal_validity_bundle_ref must identify "
            "scientist.causal_validity_bundle / polisyos.scientist.CausalValidityBundle"
        )
    payload = _load_payload(store, ref)
    if payload is None:
        raise ValueError("causal_validity_bundle_ref payload is unavailable or invalid")
    return payload


def _resolve_truthfulness_receipt(
    *,
    explicit: TruthfulnessReceipt | Mapping[str, Any] | None,
    intake_reasons: Sequence[str],
) -> tuple[TruthfulnessReceipt, Literal["explicit", "simulation_result", "metrics", "default_unverified"]]:
    reasons = list(intake_reasons)
    if explicit is not None:
        validate_truthfulness_receipt(explicit)
        reasons.append("explicit_truthfulness_receipt_unverified")
    else:
        reasons.append("runtime_calibration_receipt_missing")
    return _default_unverified_receipt(reasons), "default_unverified"


def _default_unverified_receipt(reasons: Sequence[str]) -> TruthfulnessReceipt:
    return TruthfulnessReceipt(
        runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
        truthfulness_scope=TruthfulnessScope.POSTERIOR,
        diagnostics={"source": "simulation_proof_bridge"},
        degradation_reasons=tuple(dict.fromkeys(str(reason) for reason in reasons)),
    )


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
