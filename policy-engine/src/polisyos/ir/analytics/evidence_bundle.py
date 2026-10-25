"""EvidenceBundle IR — machine-readable audit trail for causal identification and estimation.

Assembles proof steps, data provenance, and diagnostic scores into a single
serializable object for audit, reproducibility, and explanation purposes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.artifacts.contracts import (
    ArtifactOwnerDeclaration,
    CanonInfo,
    OwnedArtifactRead,
)
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact_with_bytes,
    _put_owned_json_artifact,
)
from polisyos.ir.migrations.base import (
    IRCompatibilityKind,
    IRRepresentationKey,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
)
from polisyos.ir.model_layer.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.registry.refs import (
    BoundsBundleRef,
    DataReadinessReportRef,
    EvidenceBundleRef,
    KernelEstimatorSpecRef,
    NegativeCertificateRef,
    ProofBundleRef,
    TwinNetworkResultRef,
)

MAX_FINGERPRINT_DEPTH = 32
_CAUSAL_EVIDENCE_BUNDLE_SCHEMA = "ir.causal_evidence_bundle"
_CAUSAL_EVIDENCE_BUNDLE_LEGACY_VERSION = "1.0"
_CAUSAL_EVIDENCE_BUNDLE_CURRENT_VERSION = "1.1"


class EvidenceFingerprintError(ValueError):
    """Raised when audit evidence cannot be reduced to a stable fingerprint."""


def _normalize_fingerprint_value(value: object, *, path: str = "$", depth: int = 0) -> object:
    if depth > MAX_FINGERPRINT_DEPTH:
        raise EvidenceFingerprintError(
            f"Fingerprint payload exceeds max depth {MAX_FINGERPRINT_DEPTH} at {path}"
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceFingerprintError(
                f"Fingerprint bytes are not UTF-8 decodable at {path}"
            ) from exc
    if isinstance(value, BaseModel):
        return _normalize_fingerprint_value(
            value.model_dump(mode="json"),
            path=path,
            depth=depth + 1,
        )
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            normalized[str(key)] = _normalize_fingerprint_value(
                value[key],
                path=f"{path}.{key}",
                depth=depth + 1,
            )
        return normalized
    if isinstance(value, set):
        normalized_items = [
            _normalize_fingerprint_value(item, path=f"{path}[]", depth=depth + 1) for item in value
        ]
        return sorted(
            normalized_items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_fingerprint_value(item, path=f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    raise EvidenceFingerprintError(
        f"Unsupported fingerprint payload type at {path}: {type(value).__name__}"
    )


def _fingerprint(data: object) -> str:
    """Return a 16-char SHA-256 hex fingerprint of JSON-serializable data."""
    content = json.dumps(
        _normalize_fingerprint_value(data),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class ProofStep(BaseModel):
    """A single step in a do-calculus / identification proof.

    This is the JSON-serializable IR counterpart of the internal
    ``ProofStep`` frozen dataclass in ``id_engine.py``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_name: str
    """Name of the rule applied (e.g. 'RULE1', 'C_COMPONENT', 'HEDGE')."""

    description: str
    """Human-readable description of what the rule accomplished."""

    variables_affected: tuple[str, ...] = ()
    """Variables whose status changed during this step."""

    graph_subset: str = ""
    """Compact description of the graph scope at this step."""

    rule_formal_name: str = ""
    """Formal name of the rule in do-calculus literature (e.g. 'do-calculus rule 3', \
'c-component factorization')."""

    applicable_theorem: str = ""
    """Theorem or lemma reference (e.g. 'do-calculus-R3', 'ID-algorithm', 'hedge-certificate')."""

    graph_state_before: str = ""
    """Compact description of the graph state before this rule was applied."""

    graph_state_after: str = ""
    """Compact description of the graph state after this rule was applied."""

    step_id: str = ""
    """Stable identifier for cross-artifact replay/revalidation of this proof step."""

    theorem_family: str = ""
    """The theorem family or algorithm regime that licensed this step."""

    input_expr_ref: str | None = None
    """Artifact or inline ref describing the expression before applying the step."""

    output_expr_ref: str | None = None
    """Artifact or inline ref describing the expression after applying the step."""

    witness_ids: tuple[str, ...] = ()
    """Graphical witness ids that license this step under replay."""

    depends_on_steps: tuple[str, ...] = ()
    """Prior step ids that must still hold for this step to remain reusable."""

    local_status: Literal["valid", "invalid", "unknown"] = "unknown"
    """Replay status of this step on a composed graph."""

    invalidation_reason: str | None = None
    """Short machine-readable explanation when replay invalidates the step."""


class DataProvenance(BaseModel):
    """Provenance record for a single data source used in estimation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_ref: str
    """Identifier of the dataset (matches DataKnowledgeBase.dataset_ref)."""

    n_obs: int | None = None
    """Number of observations in the dataset."""

    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    """Data quality score [0, 1]."""

    domain: str = "source"
    """Domain identifier ('source', 'target', 'experimental')."""

    availability_status: str = "available"
    """Availability status ('available', 'partial', 'proxy_only', 'unavailable')."""


class CompilationStep(BaseModel):
    """Records the transition from EstimandAST → ExecutorGraph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    estimand_shape: str
    """EstimandShape.value (e.g. 'backdoor', 'frontdoor', 'transport_reweight')."""

    estimation_strategy: str
    """EstimationStrategy.value (e.g. 'aipw', 'dml', 'density_ratio_reweight')."""

    n_executor_nodes: int
    """Number of nodes in the compiled ExecutorGraph."""

    nuisance_components: tuple[str, ...] = ()
    """Names of nuisance components emitted by the compiler (e.g. 'propensity', 'outcome_model')."""

    compiler_warnings: tuple[str, ...] = ()
    """Any warnings raised during compilation."""


class EstimationStep(BaseModel):
    """Records the execution of one MethodDagNode in the executor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    """Identifier of the executor node."""

    method_fqn: str
    """Fully-qualified method name (namespace.name)."""

    method_version: str | None = None
    """SemVer string of the method version used."""

    backend: str = ""
    """Compute backend used (e.g. 'numpy', 'sklearn', 'jax')."""

    params_hash: str = ""
    """Truncated SHA-256 of the params dict — does not store raw params."""

    wall_time_ms: float | None = None
    """Wall-clock execution time in milliseconds."""

    determinism_tier: str = ""
    """DeterminismTier.value at execution time."""

    warnings: tuple[str, ...] = ()
    """Any warnings emitted by this node."""

    is_nuisance: bool = False
    """True if this was a nuisance estimator node."""


class EvidenceBundle(BaseModel):
    """Machine-readable audit trail for a causal identification and estimation run.

    Stores the full proof of identification (proof_steps), the data sources
    used (data_provenance), diagnostic scores, and method configuration.
    Intended for reproducibility, explainability, and policy-level audit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    """Unique identifier for this analysis run."""

    query_str: str
    """Human-readable query string (e.g. 'P(Y | do(X), Z, domain=target)')."""

    estimand_ast: dict[str, Any] = Field(default_factory=dict)
    """Serialized EstimandAST (model_dump()).

    Stored as dict to avoid circular imports between IR and foundry layers.
    Consumers can reconstruct via ``EstimandAST.model_validate(bundle.estimand_ast)``.
    """

    proof_steps: tuple[ProofStep, ...] = ()
    """Ordered sequence of identification proof steps."""

    data_provenance: tuple[DataProvenance, ...] = ()
    """Data sources used in this run."""

    diagnostic_scores: dict[str, float] = Field(default_factory=dict)
    """Key diagnostic metrics (e.g. 'overlap_score', 'positivity_score')."""

    method_config: dict[str, Any] = Field(default_factory=dict)
    """Configuration of the estimator(s) used."""

    identification_status: str = ""
    """Status string from IdentificationResult.status.value."""

    algorithm_version: str = ""
    """Version string of the identification algorithm used."""

    created_at: str = ""
    """ISO 8601 timestamp of when this bundle was created."""

    # ------------------------------------------------------------------
    # 5.1 — full proof trail additions
    # ------------------------------------------------------------------

    graph_fingerprint: str = ""
    """Truncated SHA-256 of the CausalGraphModel at run time."""

    estimand_fingerprint: str = ""
    """Truncated SHA-256 of the serialised EstimandAST."""

    compilation_steps: tuple[CompilationStep, ...] = ()
    """Steps recording the EstimandAST → ExecutorGraph compilation."""

    estimation_steps: tuple[EstimationStep, ...] = ()
    """Per-node execution records from the executor."""

    # ------------------------------------------------------------------
    # 5.2 — diagnostic dashboard
    # ------------------------------------------------------------------

    diagnostic_dashboard: dict[str, Any] | None = None
    """Serialised DiagnosticDashboardData.  Stored as dict to avoid circular
    imports; reconstruct with DiagnosticDashboardData.model_validate(bundle.diagnostic_dashboard)\
."""

    # ------------------------------------------------------------------
    # 5.4 — quality report
    # ------------------------------------------------------------------

    quality_report: dict[str, Any] | None = None
    """Serialised CausalQualityReport.  Reconstruct with
    CausalQualityReport.model_validate(bundle.quality_report)."""

    proof_bundle_ref: ProofBundleRef | None = None
    """CAS-backed reference to the canonical proof artifact for this run."""

    bounds_bundle_ref: BoundsBundleRef | None = None
    """CAS-backed reference to the canonical bounds artifact, when available."""

    negative_certificate_ref: NegativeCertificateRef | None = None
    """CAS-backed reference to the impossibility artifact, when available."""

    data_readiness_report_ref: DataReadinessReportRef | None = None
    """CAS-backed reference to the canonical readiness gate, when available."""

    kernel_estimator_spec_ref: KernelEstimatorSpecRef | None = None
    """CAS-backed reference to the kernel lowering contract, when applicable."""

    twin_network_result_ref: TwinNetworkResultRef | None = None
    """CAS-backed reference to a typed twin-network result, when one was produced."""

    def to_summary(self) -> str:
        """Return a concise human-readable summary of this bundle."""
        n_steps = len(self.proof_steps)
        n_data = len(self.data_provenance)
        if self.diagnostic_scores:
            scores_str = ", ".join(f"{k}={v:.3f}" for k, v in self.diagnostic_scores.items())
        else:
            scores_str = "none"
        grade = ""
        if self.quality_report:
            grade = f" grade={self.quality_report.get('composite_grade', '?')}"
        fp = f" graph={self.graph_fingerprint!r}" if self.graph_fingerprint else ""
        return (
            f"EvidenceBundle[{self.run_id}] "
            f"query={self.query_str!r} "
            f"status={self.identification_status!r} "
            f"proof_steps={n_steps} "
            f"data_sources={n_data} "
            f"diagnostics=[{scores_str}]"
            f"{fp}{grade}"
        )


def _evidence_bundle_payload_version(_payload: object) -> None:
    """Declare that this family carries no embedded payload-version discriminator."""
    return None


_EVIDENCE_BUNDLE_LEGACY_WIRE_POLICY = ("evidence-bundle-no-twin-field", "1")
_EVIDENCE_BUNDLE_CURRENT_WIRE_POLICY = ("evidence-bundle-optional-twin-field", "1")


def _evidence_bundle_wire_policy(registration: IRRepresentationRegistration) -> tuple[str, str]:
    """Return the exact trusted semantic payload-law identity on one source row."""
    return registration.wire_policy_ref, registration.wire_policy_revision


def _validate_evidence_bundle_source(
    payload: object,
    admission: ResolvedSchemaAdmission,
) -> EvidenceBundle:
    """Validate source bytes under their registered semantic wire law."""
    registration = admission.source_registration
    if registration.schema_name != _CAUSAL_EVIDENCE_BUNDLE_SCHEMA:
        raise ValueError("EvidenceBundle owner row has the wrong schema name")
    if registration.payload_version is not None:
        raise ValueError("EvidenceBundle owner rows must declare no embedded payload version")
    if not isinstance(payload, Mapping):
        raise ValueError("Causal EvidenceBundle payload must be a JSON object")
    wire_policy = _evidence_bundle_wire_policy(registration)
    if wire_policy == _EVIDENCE_BUNDLE_LEGACY_WIRE_POLICY:
        if "twin_network_result_ref" in payload:
            raise ValueError(
                "EvidenceBundle no-Twin wire law forbids the 'twin_network_result_ref' key"
            )
    elif wire_policy != _EVIDENCE_BUNDLE_CURRENT_WIRE_POLICY:
        raise ValueError(f"Unsupported causal EvidenceBundle wire policy {wire_policy!r}")
    return EvidenceBundle.model_validate(payload)


def _project_evidence_bundle_for_consumer(
    source_value: EvidenceBundle,
    _admission: ResolvedSchemaAdmission,
) -> EvidenceBundle:
    """Return the validated family DTO without a projection that drops its provenance."""
    if not isinstance(source_value, EvidenceBundle):
        raise TypeError("Causal EvidenceBundle source was not validated by its owner")
    return source_value


def _validate_evidence_bundle_profile(
    profile: CanonInfo,
    registration: IRRepresentationRegistration,
) -> bool:
    """Bind each admitted row to the exact canonical profile used by its owner."""
    expected = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    return registration.profile_ref is None and profile == expected


_CAUSAL_EVIDENCE_BUNDLE_OWNER = ArtifactOwnerDeclaration(
    contract_id="ir.analytics.causal_evidence_bundle",
    dto_fqn="polisyos.ir.analytics.evidence_bundle.EvidenceBundle",
    abi_key="ir.causal_evidence_bundle",
    registry_key="ir.causal_evidence_bundle",
    kind="fabric.evidence_bundle",
    media_type="application/json",
    purpose="causal_audit_evidence",
    policy_revision="ir.causal_evidence_bundle.owner-admission.v1",
    accepted_wire_policies=(
        _EVIDENCE_BUNDLE_LEGACY_WIRE_POLICY,
        _EVIDENCE_BUNDLE_CURRENT_WIRE_POLICY,
    ),
    payload_version_of=_evidence_bundle_payload_version,
    validate_source=_validate_evidence_bundle_source,
    project_for_consumer=_project_evidence_bundle_for_consumer,
    validate_profile=_validate_evidence_bundle_profile,
)


_CAUSAL_EVIDENCE_BUNDLE_V1_KEY = IRRepresentationKey(
    _CAUSAL_EVIDENCE_BUNDLE_SCHEMA,
    _CAUSAL_EVIDENCE_BUNDLE_LEGACY_VERSION,
    None,
)
register_ir_representation(
    registry_key=_CAUSAL_EVIDENCE_BUNDLE_OWNER.registry_key,
    owner_ref=_CAUSAL_EVIDENCE_BUNDLE_OWNER.contract_id,
    dto_abi=_CAUSAL_EVIDENCE_BUNDLE_OWNER.dto_fqn,
    wire_policy_ref=_EVIDENCE_BUNDLE_LEGACY_WIRE_POLICY[0],
    wire_policy_revision=_EVIDENCE_BUNDLE_LEGACY_WIRE_POLICY[1],
    schema_name=_CAUSAL_EVIDENCE_BUNDLE_SCHEMA,
    schema_version=_CAUSAL_EVIDENCE_BUNDLE_LEGACY_VERSION,
    payload_version=None,
    profile_ref=None,
    readable=True,
    writable=True,
    current=False,
    default_write=False,
)
register_ir_representation(
    registry_key=_CAUSAL_EVIDENCE_BUNDLE_OWNER.registry_key,
    owner_ref=_CAUSAL_EVIDENCE_BUNDLE_OWNER.contract_id,
    dto_abi=_CAUSAL_EVIDENCE_BUNDLE_OWNER.dto_fqn,
    wire_policy_ref=_EVIDENCE_BUNDLE_CURRENT_WIRE_POLICY[0],
    wire_policy_revision=_EVIDENCE_BUNDLE_CURRENT_WIRE_POLICY[1],
    schema_name=_CAUSAL_EVIDENCE_BUNDLE_SCHEMA,
    schema_version=_CAUSAL_EVIDENCE_BUNDLE_CURRENT_VERSION,
    payload_version=None,
    profile_ref=None,
    readable=True,
    writable=True,
    current=True,
    default_write=True,
    readable_from=(_CAUSAL_EVIDENCE_BUNDLE_V1_KEY,),
)


def persist_causal_evidence_bundle(
    store: ArtifactStore,
    bundle: EvidenceBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _CAUSAL_EVIDENCE_BUNDLE_SCHEMA,
    schema_version: str | None = None,
) -> EvidenceBundleRef:
    """Persist a causal audit bundle through its exact registered owner row.

    By default, a reference-free bundle uses the strict legacy 1.0 representation
    with the Twin key omitted. A Twin-linked bundle uses the unique current
    writable representation. A supplied version is an exact owner-row request;
    unknown, non-writable, or payload-mismatched rows refuse before CAS emission.
    """
    if schema_name != _CAUSAL_EVIDENCE_BUNDLE_SCHEMA:
        raise ValueError(f"Unsupported causal EvidenceBundle schema name {schema_name!r}")
    selected_schema_version = schema_version
    if selected_schema_version is None and bundle.twin_network_result_ref is None:
        selected_schema_version = _CAUSAL_EVIDENCE_BUNDLE_LEGACY_VERSION
    payload = bundle.model_dump(mode="json")
    if (
        bundle.twin_network_result_ref is None
        and selected_schema_version == _CAUSAL_EVIDENCE_BUNDLE_LEGACY_VERSION
    ):
        payload.pop("twin_network_result_ref", None)
    write_options: dict[str, object] = {}
    if selected_schema_version is not None:
        write_options.update(schema_name=schema_name, schema_version=selected_schema_version)
    ref = _put_owned_json_artifact(
        store,
        payload,
        owner=_CAUSAL_EVIDENCE_BUNDLE_OWNER,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        **write_options,
    )
    return EvidenceBundleRef.model_validate(ref)


def _validate_causal_evidence_bundle_read(
    read: OwnedArtifactRead[EvidenceBundle],
) -> None:
    """Bind a consumer projection to its selected owner row and same-byte witness."""
    if type(read) is not OwnedArtifactRead:
        raise ValueError("EvidenceBundle consumer requires an owned artifact read")
    if (
        read.contract_id != _CAUSAL_EVIDENCE_BUNDLE_OWNER.contract_id
        or read.dto_fqn != _CAUSAL_EVIDENCE_BUNDLE_OWNER.dto_fqn
        or read.abi_key != _CAUSAL_EVIDENCE_BUNDLE_OWNER.abi_key
        or read.registry_key != _CAUSAL_EVIDENCE_BUNDLE_OWNER.registry_key
        or read.purpose != _CAUSAL_EVIDENCE_BUNDLE_OWNER.purpose
        or read.owner_policy_revision != _CAUSAL_EVIDENCE_BUNDLE_OWNER.policy_revision
    ):
        raise ValueError("EvidenceBundle consumer read does not match its trusted owner")
    admission = read.admission
    if type(admission) is not ResolvedSchemaAdmission:
        raise ValueError("EvidenceBundle consumer read is missing resolved schema admission")
    if (
        type(admission.snapshot_revision) is not str
        or not admission.snapshot_revision.startswith("sha256:")
        or len(admission.snapshot_revision) != 71
        or admission.compatibility_kind
        not in (IRCompatibilityKind.EXACT, IRCompatibilityKind.DIRECT)
        or admission.migration_path
        or admission.profile_ref is not None
    ):
        raise ValueError("EvidenceBundle admission is not an exact or direct registered route")
    source = admission.source_registration
    current = admission.current_registration
    for registration in (source, current):
        if (
            registration.registry_key != _CAUSAL_EVIDENCE_BUNDLE_OWNER.registry_key
            or registration.owner_ref != _CAUSAL_EVIDENCE_BUNDLE_OWNER.contract_id
            or registration.dto_abi != _CAUSAL_EVIDENCE_BUNDLE_OWNER.dto_fqn
            or registration.schema_name != _CAUSAL_EVIDENCE_BUNDLE_SCHEMA
            or registration.payload_version is not None
            or registration.profile_ref is not None
            or not registration.readable
            or _evidence_bundle_wire_policy(registration)
            not in _CAUSAL_EVIDENCE_BUNDLE_OWNER.accepted_wire_policies
        ):
            raise ValueError("EvidenceBundle admission rows are not accepted owner registrations")
    if (
        not current.current
        or _evidence_bundle_wire_policy(current) != _EVIDENCE_BUNDLE_CURRENT_WIRE_POLICY
    ):
        raise ValueError("EvidenceBundle current reader does not use the selected current wire law")
    profile = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    if not _validate_evidence_bundle_profile(profile, source):
        raise ValueError("EvidenceBundle source profile is not owner-approved")
    profile_digest = read.manifest_profile_sha256
    if (
        type(profile_digest) is not str
        or len(profile_digest) != 71
        or not profile_digest.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in profile_digest[7:])
    ):
        raise ValueError("EvidenceBundle consumer read is missing selected manifest-profile proof")
    if type(read.raw_bytes) is not bytes or not read.raw_bytes:
        raise ValueError("EvidenceBundle consumer read is missing its exact byte witness")
    payload = from_canonical_bytes(read.raw_bytes)
    source_value = _validate_evidence_bundle_source(payload, admission)
    if not isinstance(read.value, EvidenceBundle) or source_value != read.value:
        raise ValueError("EvidenceBundle consumer DTO is not bound to its admitted source bytes")


def load_causal_evidence_bundle_with_admission(
    store: ArtifactStore,
    ref: EvidenceBundleRef,
) -> OwnedArtifactRead[EvidenceBundle]:
    """Load one EvidenceBundle with its exact registry admission and byte witness."""
    read = _get_owned_json_artifact_with_bytes(
        store,
        ref,
        owner=_CAUSAL_EVIDENCE_BUNDLE_OWNER,
    )
    _validate_causal_evidence_bundle_read(read)
    return read


def load_causal_evidence_bundle(
    store: ArtifactStore,
    ref: EvidenceBundleRef,
) -> EvidenceBundle:
    """Load a typed causal audit bundle while preserving the historical DTO return."""
    return load_causal_evidence_bundle_with_admission(store, ref).value


__all__ = [
    "CompilationStep",
    "DataProvenance",
    "EstimationStep",
    "EvidenceBundle",
    "EvidenceFingerprintError",
    "ProofStep",
    "_fingerprint",
    "load_causal_evidence_bundle",
    "load_causal_evidence_bundle_with_admission",
    "persist_causal_evidence_bundle",
]
