"""Plain-language front door for the canonical recursive generation cycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime  # Pydantic resolves at runtime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import (
    ArtifactRef,
    read_core_json_artifact,
    read_core_manifest_profile,
)
from polisyos.core.contracts import (
    AgentPipelineCostEvent,
    ControlJobResponse,
)
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.http.services.control.nl_pipeline import (
    build_design_problem_from_nl_request,
)
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationContextHandoff,  # Pydantic model field
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.design_axes.value_choice_provenance import (
    NORMATIVE_GENERATION_SOURCE_KIND,
    NormativeAuthorityTrust,
    NormativeGenerationBinding,
    NormativeGenerationDisposition,
    NormativeGenerationEvidenceRefs,
    NormativeValueScheduleOwner,
    P20NormativeChoiceError,
)
from polisyos.runtime.quality.design_problem import (
    DesignProblem,
    DesignProblemAuthorityError,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationContextHandoffV1,
)
from polisyos.runtime.quality.open_world_risk import (
    OpenWorldRiskPublicLimitation,
)
from polisyos.runtime.quality.promotion_sequence import CanonicalPromotionReceipt
from polisyos.runtime.quality.public_export import (
    PublicExportRedactionError,
    project_pre_n9_open_world_limitations,
    project_promotion_open_world_limitation,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    ExecutionIntent,
    RecursiveGenerationCyclePartialRunV2,
    RecursiveGenerationCyclePartialRunV3,
    RecursiveGenerationCycleRun,
    RecursiveLeafContextOwner,
    build_default_recursive_generation_cycle_controller,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from polisyos.core.contracts import CatalogRunProfile
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _DesignProblemGatewayClient,
        _SpanSupportVerifierClient,
    )
    from polisyos.runtime.quality.confidence_ledger import (
        N6DeploymentCurrentnessObservation,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContext,
        VerifiedNLJobScope,
    )
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootExecutionBinding,
    )
    from polisyos.runtime.quality.design_generation import (
        DesignGenerationOrganRun,
        GenerationUnderAResult,
        N4CandidateProposalSource,
    )
    from polisyos.runtime.quality.evaluation_safety import (
        EvalSafetyVerifierPort,
        EvaluationExecutionContext,
    )
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
    )
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.scientist import BudgetState
    from polisyos.scientist.orchestration.engine import BudgetMiddleware

COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v1"
)
COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v2"
)
COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v3"
)
COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v4"
)


COMPILED_RECURSIVE_GENERATION_CYCLE_GENERIC_PROFILE_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v5"
)
COMPILED_RECURSIVE_GENERATION_CYCLE_CREDAL_SOURCE_ATTEMPT_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v6"
)
NORMATIVE_RUN_DISPOSITION_KIND = "runtime.normative_generation_composition"
NORMATIVE_RUN_DISPOSITION_V1_SCHEMA = "policyos.normative_generation_composition.v1"
NORMATIVE_RUN_DISPOSITION_SCHEMA = NORMATIVE_RUN_DISPOSITION_V1_SCHEMA
_NORMATIVE_OUTER_V1_CANON = canon.CanonSpec(
    name="polisyos.canon.json",
    version="0.2.0",
    forbid_floats=True,
    forbid_nan_inf=True,
    exclude_none=True,
    max_depth=128,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
_NORMATIVE_OUTER_V1_FIELDS = (
    "schema_version",
    "compiled_run_ref",
    "leaf_disposition_refs",
    "leaf_dispositions",
    "authorization_status",
    "ranked_recommendations",
    "strangle_receipt",
)
_NORMATIVE_LEAF_V1_FIELDS = (
    "schema_version",
    "generation_binding",
    "compiled_membership_status",
    "case_id",
    "candidate_fronts",
    "dominance_status",
    "evidence",
    "input_limitation",
    "authorization_status",
    "ranked_recommendations",
    "decision_request",
    "ranking_bundle_ref",
    "admitted_at",
    "trust_epoch",
    "authoritative_for",
    "may_not_use_for",
)
_NORMATIVE_STRANGLE_V1_FIELDS = (
    "status",
    "default_entrypoint",
    "predecessor",
    "default_flipped",
    "compiled_run_ref",
    "source_node_refs",
    "disposition_node_refs",
)
_ROOT_EVALUATION_CONTEXT_UNSET = object()
_HTTP_RECURSIVE_MAX_DEPTH = 0
_HTTP_RECURSIVE_MAX_NODES = 1
_HTTP_RECURSIVE_MAX_CYCLES_PER_LEAF = 3


class RecursiveBudgetProjection(BaseModel):
    """The fixed recursive budget actually handed to the HTTP worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_depth: int = Field(ge=0)
    max_nodes: int = Field(ge=1)
    min_cycles_per_leaf: int = Field(ge=1)
    max_cycles_per_leaf: int = Field(ge=1)


class RecursiveBudgetResolution(BaseModel):
    """Requested/effective HTTP limits retained with the compiled run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_max_iterations: int
    effective_max_iterations: int = Field(ge=1)
    recursive_budget: RecursiveBudgetProjection
    clamp_reason: str
    requested_candidate_children: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    effective_candidate_children: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    child_budget_profile: (
        Literal[
            "candidate-lever-exploration-at-most-2.v1",
            "n4-source-complete-child-set.v1",
        ]
        | None
    ) = Field(default=None, exclude_if=lambda value: value is None)


def _resolve_http_recursive_budget(
    requested_max_iterations: object,
    *,
    candidate_child_count: int | None = None,
    generic_child_count: int | None = None,
) -> tuple[int, RecursiveBudgetResolution]:
    """Resolve HTTP cycles and an exact source-derived child-set budget."""

    if candidate_child_count is not None and (
        type(candidate_child_count) is not int or not 1 <= candidate_child_count <= 2
    ):
        raise DesignProblemAuthorityError("n4_recursive_child_count_outside_supported_profile")
    if generic_child_count is not None and (
        candidate_child_count is not None
        or type(generic_child_count) is not int
        or generic_child_count < 1
    ):
        raise DesignProblemAuthorityError("generic_n4_recursive_child_count_invalid")
    complete_child_count = (
        generic_child_count if generic_child_count is not None else candidate_child_count
    )
    requested = int(requested_max_iterations or 1)
    effective = max(1, min(requested, _HTTP_RECURSIVE_MAX_CYCLES_PER_LEAF))
    if requested > _HTTP_RECURSIVE_MAX_CYCLES_PER_LEAF:
        clamp_reason = "requested_max_iterations_above_http_cycle_cap_3"
    elif requested < 1:
        clamp_reason = "requested_max_iterations_below_http_minimum_1"
    else:
        clamp_reason = "none"
    return effective, RecursiveBudgetResolution(
        requested_max_iterations=requested,
        effective_max_iterations=effective,
        recursive_budget=RecursiveBudgetProjection(
            max_depth=1 if complete_child_count is not None else _HTTP_RECURSIVE_MAX_DEPTH,
            max_nodes=1 + complete_child_count
            if complete_child_count is not None
            else _HTTP_RECURSIVE_MAX_NODES,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=effective,
        ),
        clamp_reason=clamp_reason,
        requested_candidate_children=complete_child_count,
        effective_candidate_children=complete_child_count,
        child_budget_profile=(
            "n4-source-complete-child-set.v1"
            if generic_child_count is not None
            else "candidate-lever-exploration-at-most-2.v1"
            if candidate_child_count is not None
            else None
        ),
    )


class CompiledN4ChildProfileBinding(BaseModel):
    """One source-derived child problem and its exact owner-produced context handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_ref: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    handoff: CandidateSimulationContextHandoff

    @model_validator(mode="after")
    def _verify_node_binding(self) -> CompiledN4ChildProfileBinding:
        expected_node_ref = "design-problem://" + self.design_problem_ref.removeprefix("sha256:")
        if self.node_ref != expected_node_ref:
            raise ValueError("compiled_n4_child_profile_node_binding_mismatch")
        if self.handoff.context.design_problem_ref != self.design_problem_ref:
            raise ValueError("compiled_n4_child_profile_context_binding_mismatch")
        return self


class NormativeRunEvidenceRefs(BaseModel):
    """Data-only external evidence references, keyed by the actual source node."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    by_node: dict[str, NormativeGenerationEvidenceRefs] = Field(default_factory=dict)
    input_limitation: (
        Literal[
            "p20_normative_evidence_invalid",
            "p20_normative_generation_disposition_missing",
            "p20_normative_sidecar_replay_failed",
        ]
        | None
    ) = None


NORMATIVE_GENERATION_HEAD_KIND = "runtime.normative_generation_head"
NORMATIVE_GENERATION_HEAD_SCHEMA = "policyos.normative_generation_head.v1"


class NormativeEvidenceSubmissionRequest(BaseModel):
    """Attach external evidence to one exact completed job, without source or trust overrides."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    job_id: str = Field(min_length=1)
    expected_prior_head_ref: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence: NormativeRunEvidenceRefs


class NormativeEvidenceHeadStrangleReceipt(BaseModel):
    """Run-emitted replacement witness for the current job's original worker-only sidecar."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["strangled"] = "strangled"
    default_entrypoint: Literal["ControlPlaneService._current_normative_job_record"] = (
        "ControlPlaneService._current_normative_job_record"
    )
    predecessor: Literal["worker_only_normative_disposition"] = "worker_only_normative_disposition"
    default_flipped: Literal[True] = True
    original_disposition_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_disposition_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class NormativeGenerationHead(BaseModel):
    """Immutable source-bound transition admitted by the existing job event owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.normative_generation_head.v1"] = (
        NORMATIVE_GENERATION_HEAD_SCHEMA
    )
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    compiled_run_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    previous_head_ref: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    disposition_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence: NormativeRunEvidenceRefs
    evaluated_at: datetime
    strangle_receipt: NormativeEvidenceHeadStrangleReceipt


class NormativeEvidenceSubmissionResponse(BaseModel):
    """Durable intake outcome and the shared current job projection after compare-and-append."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["admitted", "refused", "conflict"]
    head_ref: str | None
    attempted_disposition_ref: str
    job: ControlJobResponse


def load_normative_generation_head(
    store: artifacts.ArtifactStore, head_ref: str
) -> NormativeGenerationHead:
    """Resolve one head's real CAS bytes and governed artifact epoch before projection."""
    payload = _read_normative_source(store, head_ref, kind=NORMATIVE_GENERATION_HEAD_KIND)
    manifest = store.get_manifest(artifacts.ArtifactID.model_validate(head_ref))
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.version != NORMATIVE_GENERATION_HEAD_SCHEMA
    ):
        raise ValueError("normative_head_schema_epoch_mismatch")
    return NormativeGenerationHead.model_validate(payload)


def parse_normative_run_evidence(value: object) -> NormativeRunEvidenceRefs | None:
    """Keep malformed external evidence as a typed refusal instead of silently dropping it."""
    if value is None:
        return None
    try:
        return NormativeRunEvidenceRefs.model_validate(value)
    except ValueError:
        return NormativeRunEvidenceRefs(input_limitation="p20_normative_evidence_invalid")


class NormativeRunStrangleReceipt(BaseModel):
    """Run-emitted witness reconciling every source leaf with the required S8 result."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["strangled"] = "strangled"
    default_entrypoint: Literal["ControlPlaneService.resolve_generation_value_choices"] = (
        "ControlPlaneService.resolve_generation_value_choices"
    )
    predecessor: Literal["compiled_run_completion_without_normative_disposition"] = (
        "compiled_run_completion_without_normative_disposition"
    )
    default_flipped: Literal[True] = True
    compiled_run_ref: str
    source_node_refs: tuple[str, ...]
    disposition_node_refs: tuple[str, ...]


class NormativeRunDisposition(BaseModel):
    """Frozen outer-v1 projection; future schemas require a separate model."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.normative_generation_composition.v1"] = (
        NORMATIVE_RUN_DISPOSITION_V1_SCHEMA
    )
    compiled_run_ref: str
    leaf_disposition_refs: dict[str, str]
    leaf_dispositions: dict[str, NormativeGenerationDisposition]
    authorization_status: Literal["authorized", "blocked"]
    ranked_recommendations: tuple[str, ...]
    strangle_receipt: NormativeRunStrangleReceipt
    disposition_ref: str | None = Field(default=None, exclude=True)
    _persisted_artifact_ref: ArtifactRef | None = PrivateAttr(default=None)

    @property
    def persisted_artifact_ref(self) -> ArtifactRef | None:
        """Return the exact store-selected manifest view for this produced artifact."""
        return self._persisted_artifact_ref


@dataclass(frozen=True, slots=True)
class NormativeRunDispositionHistory:
    """Immutable outer replay plus the persisted admission-currentness evidence per leaf."""

    disposition: NormativeRunDisposition
    admission_currentness_by_node: dict[str, N6DeploymentCurrentnessObservation | None]

    @property
    def admission_authority_established(self) -> bool:
        """Whether every historical leaf recorded currentness when it was admitted."""

        return bool(self.admission_currentness_by_node) and all(
            observation is not None and observation.status == "current"
            for observation in self.admission_currentness_by_node.values()
        )


def _normative_run_disposition_v1_payload(
    disposition: NormativeRunDisposition,
) -> dict[str, object]:
    """Freeze the persisted v1 fields independently of future model additions."""

    receipt = disposition.strangle_receipt
    return {
        "schema_version": NORMATIVE_RUN_DISPOSITION_V1_SCHEMA,
        "compiled_run_ref": disposition.compiled_run_ref,
        "leaf_disposition_refs": disposition.leaf_disposition_refs,
        "leaf_dispositions": {
            node_ref: leaf.model_dump(mode="json", include=set(_NORMATIVE_LEAF_V1_FIELDS))
            for node_ref, leaf in disposition.leaf_dispositions.items()
        },
        "authorization_status": disposition.authorization_status,
        "ranked_recommendations": list(disposition.ranked_recommendations),
        "strangle_receipt": {
            "status": receipt.status,
            "default_entrypoint": receipt.default_entrypoint,
            "predecessor": receipt.predecessor,
            "default_flipped": receipt.default_flipped,
            "compiled_run_ref": receipt.compiled_run_ref,
            "source_node_refs": list(receipt.source_node_refs),
            "disposition_node_refs": list(receipt.disposition_node_refs),
        },
    }


def _assert_normative_run_disposition_v1_shape(payload: object, *, producer: bool = False) -> None:
    """Reject a post-v1 outer or embedded field before v1 admission."""

    if not isinstance(payload, dict):
        raise P20NormativeChoiceError("p20_normative_outer_v1_shape_mismatch")
    leaves = payload.get("leaf_dispositions")
    receipt = payload.get("strangle_receipt")
    outer_keys = set(payload)
    expected_outer = set(_NORMATIVE_OUTER_V1_FIELDS)
    expected_leaf = set(_NORMATIVE_LEAF_V1_FIELDS)
    expected_receipt = set(_NORMATIVE_STRANGLE_V1_FIELDS)
    if (
        (outer_keys != expected_outer if producer else not outer_keys <= expected_outer)
        or not isinstance(leaves, dict)
        or any(
            not isinstance(leaf, dict)
            or (set(leaf) != expected_leaf if producer else not set(leaf) <= expected_leaf)
            for leaf in leaves.values()
        )
        or not isinstance(receipt, dict)
        or (set(receipt) != expected_receipt if producer else not set(receipt) <= expected_receipt)
    ):
        raise P20NormativeChoiceError("p20_normative_outer_v1_shape_mismatch")


def _read_normative_run_disposition_v1(
    store: artifacts.ArtifactStore, ref: str | ArtifactRef
) -> NormativeRunDisposition:
    """Resolve the exact historical outer-v1 bytes and manifest profile."""

    try:
        selected_ref = (
            ref if isinstance(ref, ArtifactRef) else artifacts.ArtifactID.model_validate(ref)
        )
        artifact_id = (
            selected_ref.artifact_id if isinstance(selected_ref, ArtifactRef) else selected_ref
        )
        raw = store.get_bytes(selected_ref)
        manifest = read_core_manifest_profile(store, selected_ref)[0]
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise P20NormativeChoiceError("p20_normative_outer_v1_unavailable") from exc
    if (
        (isinstance(ref, str) and str(artifact_id) != ref)
        or str(artifact_id) != f"sha256:{canon.content_hash(raw)}"
        or manifest.artifact_id != artifact_id
    ):
        raise P20NormativeChoiceError("p20_normative_outer_v1_content_mismatch")
    schema = manifest.artifact_schema
    if (
        manifest.kind != NORMATIVE_RUN_DISPOSITION_KIND
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != NORMATIVE_RUN_DISPOSITION_KIND
        or schema.version != NORMATIVE_RUN_DISPOSITION_V1_SCHEMA
    ):
        raise P20NormativeChoiceError("p20_normative_outer_v1_schema_mismatch")
    try:
        payload = read_core_json_artifact(store, selected_ref, raw_payload_bytes=raw).value
        _assert_normative_run_disposition_v1_shape(payload)
        recorded = NormativeRunDisposition.model_validate(payload)
    except P20NormativeChoiceError:
        raise
    except (TypeError, ValueError) as exc:
        raise P20NormativeChoiceError("p20_normative_outer_v1_invalid") from exc
    if raw != canon.to_canonical_bytes(
        _normative_run_disposition_v1_payload(recorded), _NORMATIVE_OUTER_V1_CANON
    ):
        raise P20NormativeChoiceError("p20_normative_outer_v1_bytes_mismatch")
    recorded._persisted_artifact_ref = (
        selected_ref if isinstance(selected_ref, ArtifactRef) else None
    )
    return recorded


def normative_owner_for_runtime_store(
    store: artifacts.ArtifactStore,
    trust: NormativeAuthorityTrust,
    *,
    signature_verifier: artifacts.SignatureVerifyingArtifactStore | None = None,
    repo_root: Path | None = None,
) -> NormativeValueScheduleOwner:
    """Reuse the exact runtime store and its optional signature capability."""
    try:
        required_operations = tuple(
            getattr(store, name, None) for name in ("get_bytes", "get_manifest", "put_json")
        )
    except (AttributeError, TypeError) as exc:
        raise P20NormativeChoiceError("p20_normative_signed_store_unavailable") from exc
    if not all(callable(operation) for operation in required_operations):
        raise P20NormativeChoiceError("p20_normative_signed_store_unavailable")
    if signature_verifier is not None:
        try:
            verifier_store = signature_verifier.guarded_store
            verify_signature = signature_verifier.verify_signature
        except (AttributeError, TypeError) as exc:
            raise P20NormativeChoiceError("p20_normative_signature_port_unavailable") from exc
        if verifier_store is not store:
            raise P20NormativeChoiceError("p20_normative_signature_store_mismatch")
        if not callable(verify_signature):
            raise P20NormativeChoiceError("p20_normative_signature_port_unavailable")
    return NormativeValueScheduleOwner(
        store=store,
        trust=trust,
        signature_verifier=signature_verifier,
        repo_root=repo_root,
    )


def _read_normative_source(
    store: artifacts.ArtifactStore, ref: str | ArtifactRef, *, kind: str
) -> dict[str, object]:
    selected_ref = ref if isinstance(ref, ArtifactRef) else artifacts.ArtifactID.model_validate(ref)
    artifact_id = (
        selected_ref.artifact_id if isinstance(selected_ref, ArtifactRef) else selected_ref
    )
    raw = store.get_bytes(selected_ref)
    manifest = read_core_manifest_profile(store, selected_ref)[0]
    if str(artifact_id) != f"sha256:{canon.content_hash(raw)}" or manifest.kind != kind:
        raise P20NormativeChoiceError("p20_normative_compiled_source_mismatch")
    payload = read_core_json_artifact(store, selected_ref, raw_payload_bytes=raw).value
    if not isinstance(payload, dict):
        raise P20NormativeChoiceError("p20_normative_compiled_source_invalid")
    return payload


def _normative_generation_sources(
    store: artifacts.ArtifactStore,
    compiled_run_ref: str,
    *,
    persist: bool,
    compiled_artifact_ref: ArtifactRef | None = None,
) -> dict[str, NormativeGenerationBinding]:
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        _read_normative_source(
            store,
            compiled_artifact_ref or compiled_run_ref,
            kind="runtime.compiled_recursive_generation_cycle",
        )
    )
    if isinstance(
        compiled.recursive_run,
        (RecursiveGenerationCyclePartialRunV2, RecursiveGenerationCyclePartialRunV3),
    ):
        raise P20NormativeChoiceError("p20_normative_partial_compiled_run")
    sources = {}
    for node in compiled.recursive_run.leaf_nodes:
        if node.cycle_run is None or node.node_ref in sources:
            raise P20NormativeChoiceError("p20_normative_compiled_leaf_invalid")
        payload = node.cycle_run.model_dump(mode="json")
        raw = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        source_ref = f"sha256:{canon.content_hash(raw)}"
        if persist:
            emitted = store.put_json(
                payload,
                artifacts.PutOptions(
                    kind=NORMATIVE_GENERATION_SOURCE_KIND,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(
                        name=NORMATIVE_GENERATION_SOURCE_KIND,
                        version=node.cycle_run.schema_version,
                    ),
                ),
                canon_spec=canon.CanonSpec(forbid_floats=False),
            )
            if str(emitted.artifact_id) != source_ref:
                raise P20NormativeChoiceError("p20_normative_leaf_persistence_mismatch")
        else:
            stored = _read_normative_source(
                store, source_ref, kind=NORMATIVE_GENERATION_SOURCE_KIND
            )
            if stored != payload:
                raise P20NormativeChoiceError("p20_normative_compiled_leaf_mismatch")
        sources[node.node_ref] = NormativeGenerationBinding(
            compiled_run_ref=compiled_run_ref,
            source_run_ref=source_ref,
            node_ref=node.node_ref,
        )
    if not sources:
        raise P20NormativeChoiceError("p20_normative_compiled_leaf_population_empty")
    return sources


def _project_normative_composition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    compiled_run_ref: str,
    leaf_refs: dict[str, str],
    evaluated_at: datetime,
    historical: bool = False,
    compiled_artifact_ref: ArtifactRef | None = None,
) -> NormativeRunDisposition:
    sources = _normative_generation_sources(
        store,
        compiled_run_ref,
        persist=False,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    if set(sources) != set(leaf_refs):
        raise P20NormativeChoiceError("p20_normative_compiled_leaf_population_mismatch")
    leaves = {}
    for node_ref, source in sources.items():
        leaf = (
            owner.replay_generation_disposition(leaf_refs[node_ref])
            if historical
            else owner.project_generation_disposition(
                leaf_refs[node_ref], evaluated_at=evaluated_at
            )
        )
        if leaf.generation_binding != source:
            raise P20NormativeChoiceError("p20_normative_compiled_leaf_binding_mismatch")
        leaves[node_ref] = leaf
    authorized = all(leaf.authorization_status == "authorized" for leaf in leaves.values())
    return NormativeRunDisposition(
        compiled_run_ref=compiled_run_ref,
        leaf_disposition_refs=leaf_refs,
        leaf_dispositions=leaves,
        authorization_status="authorized" if authorized else "blocked",
        # A mixed composition cannot silently turn a partial selection into a run recommendation.
        ranked_recommendations=tuple(
            choice for leaf in leaves.values() for choice in leaf.ranked_recommendations
        )
        if authorized
        else (),
        strangle_receipt=NormativeRunStrangleReceipt(
            compiled_run_ref=compiled_run_ref,
            source_node_refs=tuple(sorted(sources)),
            disposition_node_refs=tuple(sorted(leaves)),
        ),
    )


def produce_normative_run_disposition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    compiled_run_ref: str,
    evidence: NormativeRunEvidenceRefs | None,
    evaluated_at: datetime,
    compiled_artifact_ref: ArtifactRef | None = None,
) -> NormativeRunDisposition:
    """Default production bridge from current compiled CAS bytes to every S8 leaf."""
    sources = _normative_generation_sources(
        store,
        compiled_run_ref,
        persist=True,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    by_node = evidence.by_node if evidence else {}
    limitation = evidence.input_limitation if evidence else None
    if not set(by_node).issubset(sources):
        limitation = "p20_normative_evidence_node_mismatch"
    leaf_refs = {
        node_ref: owner.produce_generation_disposition(
            binding=binding,
            evidence=by_node.get(node_ref),
            evaluated_at=evaluated_at,
            input_limitation=limitation,
        )
        for node_ref, binding in sources.items()
    }
    projection = _project_normative_composition(
        store=store,
        owner=owner,
        compiled_run_ref=compiled_run_ref,
        leaf_refs=leaf_refs,
        evaluated_at=evaluated_at,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    _assert_normative_run_disposition_v1_shape(projection.model_dump(mode="json"), producer=True)
    ref = store.put_json(
        _normative_run_disposition_v1_payload(projection),
        artifacts.PutOptions(
            kind=NORMATIVE_RUN_DISPOSITION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=NORMATIVE_RUN_DISPOSITION_KIND,
                version=NORMATIVE_RUN_DISPOSITION_SCHEMA,
            ),
        ),
        canon_spec=_NORMATIVE_OUTER_V1_CANON,
    )
    disposition = project_normative_run_disposition(
        store=store,
        owner=owner,
        disposition_ref=ref,
        compiled_run_ref=compiled_run_ref,
        evaluated_at=evaluated_at,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    disposition._persisted_artifact_ref = ref
    return disposition


def project_normative_run_disposition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    disposition_ref: str | ArtifactRef,
    compiled_run_ref: str,
    evaluated_at: datetime,
    disposition_artifact_ref: ArtifactRef | None = None,
    compiled_artifact_ref: ArtifactRef | None = None,
) -> NormativeRunDisposition:
    """Recompute complete compiled membership and current S8 authority at every egress."""
    replay = replay_normative_run_disposition(
        store=store,
        owner=owner,
        disposition_ref=disposition_artifact_ref or disposition_ref,
        compiled_run_ref=compiled_run_ref,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    current = _project_normative_composition(
        store=store,
        owner=owner,
        compiled_run_ref=compiled_run_ref,
        leaf_refs=replay.disposition.leaf_disposition_refs,
        evaluated_at=evaluated_at,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    return current.model_copy(
        update={
            "disposition_ref": str(
                disposition_ref.artifact_id
                if isinstance(disposition_ref, ArtifactRef)
                else disposition_ref
            )
        }
    )


def replay_normative_run_disposition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    disposition_ref: str | ArtifactRef,
    compiled_run_ref: str,
    compiled_artifact_ref: ArtifactRef | None = None,
) -> NormativeRunDispositionHistory:
    """Replay stored S8 history without sampling the live Confidence Ledger."""
    recorded = _read_normative_run_disposition_v1(store, disposition_ref)
    if recorded.compiled_run_ref != compiled_run_ref:
        raise P20NormativeChoiceError("p20_normative_compiled_run_substitution")
    historical_times = {leaf.admitted_at for leaf in recorded.leaf_dispositions.values()}
    if len(historical_times) != 1:
        raise P20NormativeChoiceError("p20_normative_composition_time_mismatch")
    historical = _project_normative_composition(
        store=store,
        owner=owner,
        compiled_run_ref=compiled_run_ref,
        leaf_refs=recorded.leaf_disposition_refs,
        evaluated_at=next(iter(historical_times)),
        historical=True,
        compiled_artifact_ref=compiled_artifact_ref,
    )
    # Persisted v1 equality is the contract here. Runtime-only ownership data
    # such as ``_persisted_artifact_ref`` is deliberately excluded from the
    # wire projection, so comparing the Pydantic models would reject a valid
    # replay whenever the selected manifest view is present on ``recorded``.
    if canon.to_canonical_bytes(
        _normative_run_disposition_v1_payload(historical), _NORMATIVE_OUTER_V1_CANON
    ) != canon.to_canonical_bytes(
        _normative_run_disposition_v1_payload(recorded), _NORMATIVE_OUTER_V1_CANON
    ):
        raise P20NormativeChoiceError("p20_normative_composition_content_mismatch")
    historical._persisted_artifact_ref = recorded._persisted_artifact_ref
    currentness = {
        node_ref: owner.generation_disposition_admission_currentness(leaf_ref)
        for node_ref, leaf_ref in recorded.leaf_disposition_refs.items()
    }
    return NormativeRunDispositionHistory(
        disposition=historical.model_copy(
            update={
                "disposition_ref": str(
                    disposition_ref.artifact_id
                    if isinstance(disposition_ref, ArtifactRef)
                    else disposition_ref
                )
            }
        ),
        admission_currentness_by_node=currentness,
    )


class CompiledRecursiveGenerationCycleRun(BaseModel):
    """Content-bound plain-language problem and its canonical recursive run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "policyos.runtime.http.compiled_recursive_generation_cycle.v1",
        "policyos.runtime.http.compiled_recursive_generation_cycle.v2",
        "policyos.runtime.http.compiled_recursive_generation_cycle.v3",
        "policyos.runtime.http.compiled_recursive_generation_cycle.v4",
        "policyos.runtime.http.compiled_recursive_generation_cycle.v5",
        "policyos.runtime.http.compiled_recursive_generation_cycle.v6",
    ] = COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem: DesignProblem
    cycle_substrate_context_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    recursive_run: (
        RecursiveGenerationCycleRun
        | RecursiveGenerationCyclePartialRunV2
        | RecursiveGenerationCyclePartialRunV3
    )
    recursive_budget_resolution: RecursiveBudgetResolution | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    nl_preflight_cost_events: tuple[AgentPipelineCostEvent, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )
    n4_generation_cost_events: tuple[AgentPipelineCostEvent, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )
    n4_recursive_source_ref: ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_job_id: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_run_id: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_tenant_id: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_cell_id: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_context_job_ref: ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_profile_config_ref: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_profile_selection_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
        exclude_if=lambda value: value is None,
    )
    n4_recursive_source_result_status: (
        Literal[
            "generated",
            "generation_unavailable",
            "preflight_rejected",
        ]
        | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    n4_credal_source_attempt_ref: ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    n4_child_profile_status: Literal[
        "not_attempted",
        "resolved",
        "not_established",
    ] = Field(default="not_attempted", exclude_if=lambda value: value == "not_attempted")
    n4_child_profile_bindings: tuple[CompiledN4ChildProfileBinding, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )
    n4_child_profile_limitation_code: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    generic_cycle_simulation_handoff: GenericCycleSimulationContextHandoffV1 | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    generic_n4_child_profile_status: Literal[
        "not_attempted",
        "resolved",
        "not_established",
    ] = Field(default="not_attempted", exclude_if=lambda value: value == "not_attempted")
    n4_child_profile_set_ref: ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    generic_n4_child_profile_limitation_code: str | None = Field(
        default=None,
        min_length=1,
        exclude_if=lambda value: value is None,
    )
    open_world_risk_limitations: tuple[OpenWorldRiskPublicLimitation, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_bindings(self) -> CompiledRecursiveGenerationCycleRun:
        if (
            self.schema_version
            == COMPILED_RECURSIVE_GENERATION_CYCLE_GENERIC_PROFILE_SCHEMA_VERSION
        ):
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_design_problem_ref,
            )

            expected_problem_ref = cycle_job_design_problem_ref(self.design_problem)
        else:
            expected_problem_ref = gy_content_hash(self.design_problem.model_dump(mode="json"))
        if self.design_problem_ref != expected_problem_ref:
            raise ValueError("compiled_recursive_design_problem_hash_mismatch")
        if self.recursive_run.root_design_problem_ref != self.design_problem_ref:
            raise ValueError("compiled_recursive_run_problem_binding_mismatch")
        producer_events = (
            *self.nl_preflight_cost_events,
            *self.n4_generation_cost_events,
        )
        event_ids = tuple(event.event_id for event in producer_events)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("compiled_recursive_preflight_cost_event_duplicate")
        has_producer_events = bool(producer_events)
        has_scoped_n4_source = self.n4_recursive_source_ref is not None
        source_scope = (
            self.n4_recursive_source_job_id,
            self.n4_recursive_source_run_id,
            self.n4_recursive_source_tenant_id,
            self.n4_recursive_source_cell_id,
            self.n4_recursive_source_context_job_ref,
            self.n4_recursive_source_profile_config_ref,
            self.n4_recursive_source_profile_selection_ref,
            self.n4_recursive_source_result_status,
        )
        if has_scoped_n4_source:
            if (
                any(value is None for value in source_scope)
                or self.n4_recursive_source_ref.kind != "runtime.generation_source_handoff"
                or self.n4_recursive_source_ref.media_type != "application/json"
                or self.n4_recursive_source_context_job_ref is None
                or self.n4_recursive_source_context_job_ref.kind
                != "runtime.quality.cycle_substrate_context_job"
                or self.n4_recursive_source_context_job_ref.media_type != "application/json"
            ):
                raise ValueError("compiled_recursive_n4_source_binding_invalid")
        elif any(value is not None for value in source_scope):
            raise ValueError("compiled_recursive_n4_source_scope_without_ref")
        if self.n4_child_profile_status == "resolved" and (
            not has_scoped_n4_source
            or self.n4_child_profile_limitation_code is not None
            or not self.n4_child_profile_bindings
        ):
            raise ValueError("compiled_recursive_child_profile_resolution_invalid")
        if self.n4_child_profile_status == "not_established" and (
            self.n4_child_profile_limitation_code is None or self.n4_child_profile_bindings
        ):
            raise ValueError("compiled_recursive_child_profile_limitation_missing")
        if self.n4_child_profile_status != "not_established" and (
            self.n4_child_profile_limitation_code is not None
        ):
            raise ValueError("compiled_recursive_child_profile_limitation_unexpected")
        has_generic_handoff = self.generic_cycle_simulation_handoff is not None
        has_generic_family = self.n4_child_profile_set_ref is not None
        has_credal_source_attempt = self.n4_credal_source_attempt_ref is not None
        if has_credal_source_attempt:
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_profile_selection_ref,
            )

            if (
                self.generic_cycle_simulation_handoff is None
                or self.generic_cycle_simulation_handoff.profile.profile_selection_ref
                != cycle_job_profile_selection_ref(self.design_problem)
            ):
                raise ValueError("compiled_recursive_credal_source_attempt_root_profile_mismatch")
        if has_credal_source_attempt and (
            type(self.n4_credal_source_attempt_ref) is not ArtifactRef
            or self.n4_credal_source_attempt_ref.kind
            != "runtime.quality.candidate_credal_source_attempt"
            or self.n4_credal_source_attempt_ref.media_type != "application/json"
            or not has_generic_handoff
            or not has_scoped_n4_source
            or self.n4_recursive_source_result_status
            not in {"generation_unavailable", "preflight_rejected"}
            or self.generic_n4_child_profile_status != "not_established"
            or self.generic_n4_child_profile_limitation_code is None
            or self.n4_recursive_source_job_id != self.generic_cycle_simulation_handoff.job_id
            or self.n4_recursive_source_run_id != self.generic_cycle_simulation_handoff.run_id
            or self.n4_recursive_source_tenant_id != self.generic_cycle_simulation_handoff.tenant_id
            or self.n4_recursive_source_cell_id != self.generic_cycle_simulation_handoff.cell_id
            or self.n4_recursive_source_context_job_ref
            != self.generic_cycle_simulation_handoff.context_job_ref
            or self.n4_recursive_source_profile_config_ref
            != self.generic_cycle_simulation_handoff.profile.profile_id
            or self.n4_recursive_source_profile_selection_ref
            != self.generic_cycle_simulation_handoff.profile.profile_selection_ref
            or self.generic_cycle_simulation_handoff.profile.profile_selection_kind != "problem"
        ):
            raise ValueError("compiled_recursive_credal_source_attempt_binding_invalid")
        if (
            "n4_credal_source_attempt_ref" in self.model_fields_set
            and self.schema_version
            != COMPILED_RECURSIVE_GENERATION_CYCLE_CREDAL_SOURCE_ATTEMPT_SCHEMA_VERSION
        ):
            raise ValueError("compiled_recursive_credal_source_attempt_requires_v6")
        if self.generic_n4_child_profile_status == "resolved":
            handoff = self.generic_cycle_simulation_handoff
            family_ref = self.n4_child_profile_set_ref
            if (
                not has_scoped_n4_source
                or handoff is None
                or family_ref is None
                or self.generic_n4_child_profile_limitation_code is not None
                or family_ref.kind != "runtime.quality.recursive_n4_child_profile_set"
                or family_ref.media_type != "application/json"
                or (
                    handoff.job_id,
                    handoff.run_id,
                    handoff.tenant_id,
                    handoff.cell_id,
                )
                != (
                    self.n4_recursive_source_job_id,
                    self.n4_recursive_source_run_id,
                    self.n4_recursive_source_tenant_id,
                    self.n4_recursive_source_cell_id,
                )
                or handoff.context_job_ref != self.n4_recursive_source_context_job_ref
            ):
                raise ValueError("compiled_recursive_generic_child_profile_resolution_invalid")
        elif self.generic_n4_child_profile_status == "not_established":
            if self.generic_n4_child_profile_limitation_code is None or has_generic_family:
                raise ValueError("compiled_recursive_generic_child_profile_limitation_missing")
        elif self.generic_n4_child_profile_limitation_code is not None or has_generic_family:
            raise ValueError("compiled_recursive_generic_child_profile_projection_unexpected")
        if has_generic_handoff and self.generic_n4_child_profile_status == "not_attempted":
            raise ValueError("compiled_recursive_generic_handoff_without_attempt")
        if self.n4_child_profile_status != "not_attempted" and has_generic_handoff:
            raise ValueError("compiled_recursive_candidate_and_generic_child_profile_conflict")
        has_generic_projection = (
            has_generic_handoff
            or has_generic_family
            or (self.generic_n4_child_profile_status != "not_attempted")
            or self.generic_n4_child_profile_limitation_code is not None
            or has_credal_source_attempt
        )
        child_nodes = tuple(row.node_ref for row in self.n4_child_profile_bindings)
        if len(child_nodes) != len(set(child_nodes)):
            raise ValueError("compiled_recursive_child_profile_binding_duplicate")
        if any(
            row.handoff.job_id != self.n4_recursive_source_job_id
            or row.handoff.run_id != self.n4_recursive_source_run_id
            or row.handoff.tenant_id != self.n4_recursive_source_tenant_id
            or row.handoff.cell_id != self.n4_recursive_source_cell_id
            or row.handoff.profile.profile_selection_ref
            == self.n4_recursive_source_profile_selection_ref
            for row in self.n4_child_profile_bindings
        ):
            raise ValueError("compiled_recursive_child_profile_source_scope_mismatch")
        has_n4_projection = self.n4_child_profile_status != "not_attempted" or bool(
            self.n4_child_profile_bindings
        )
        if has_generic_projection:
            expected_schema_version = (
                COMPILED_RECURSIVE_GENERATION_CYCLE_CREDAL_SOURCE_ATTEMPT_SCHEMA_VERSION
                if has_credal_source_attempt
                else COMPILED_RECURSIVE_GENERATION_CYCLE_GENERIC_PROFILE_SCHEMA_VERSION
            )
        elif has_producer_events or has_scoped_n4_source or has_n4_projection:
            expected_schema_version = COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION
        elif isinstance(self.recursive_run, RecursiveGenerationCyclePartialRunV2):
            expected_schema_version = COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION
        elif isinstance(self.recursive_run, RecursiveGenerationCyclePartialRunV3):
            expected_schema_version = (
                COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION
            )
        else:
            expected_schema_version = COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
        if self.schema_version != expected_schema_version:
            raise ValueError("compiled_recursive_generation_cycle_schema_run_mismatch")
        if self.schema_version == COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION and not (
            has_producer_events or has_scoped_n4_source or has_n4_projection
        ):
            raise ValueError("compiled_recursive_v4_payload_extension_missing")
        if has_credal_source_attempt:
            if (
                self.schema_version
                != COMPILED_RECURSIVE_GENERATION_CYCLE_CREDAL_SOURCE_ATTEMPT_SCHEMA_VERSION
            ):
                raise ValueError("compiled_recursive_v6_payload_extension_mismatch")
        elif (
            self.schema_version
            == COMPILED_RECURSIVE_GENERATION_CYCLE_GENERIC_PROFILE_SCHEMA_VERSION
        ) != has_generic_projection:
            raise ValueError("compiled_recursive_v5_payload_extension_mismatch")
        if (
            isinstance(
                self.recursive_run,
                (
                    RecursiveGenerationCyclePartialRunV2,
                    RecursiveGenerationCyclePartialRunV3,
                ),
            )
            and self.open_world_risk_limitations
        ):
            raise ValueError("compiled_recursive_partial_open_world_projection_forbidden")
        payload = gy_artifact_self_identity_projection(self)
        recursive_run = dict(payload["recursive_run"])
        recursive_run.pop("leaf_nodes", None)
        payload["recursive_run"] = recursive_run
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("compiled_recursive_generation_cycle_hash_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class N4CandidateProposalExecution:
    """Proposal-only N4 result stopped before recursive execution when scope is unknown."""

    design_problem: DesignProblem
    proposal: N4CandidateProposalSource | DesignGenerationOrganRun
    target_world_scope_profile_id: str | None = None
    target_world_scope_status: Literal["not_established"] = "not_established"
    target_world_scope_profile_status: Literal[
        "profile_not_requested",
        "profile_admission_missing",
        "profile_refresh_unavailable",
    ] = "profile_not_requested"
    target_world_scope_profile_limitation_code: str | None = None
    target_world_model_record_ref: str | None = None
    nl_preflight_cost_events: tuple[AgentPipelineCostEvent, ...] = ()
    n4_generation_cost_events: tuple[AgentPipelineCostEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class N4CandidateScenarioProposalOnlyExecution:
    """Ephemeral HTTP outcome for one persisted profile-limited N4 proposal."""

    design_problem: DesignProblem
    source_ref: artifacts.ArtifactRef | None
    limitation_code: str


def _parent_joint_simulation_requests_by_node(
    root_ref: str,
    root_problem: DesignProblem,
) -> dict[str, JointSimulationRequest]:
    """Read only an explicitly supplied, typed root N5 request candidate."""

    if "joint_simulation_request" not in root_problem.runtime_hints:
        return {}
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest

    try:
        request = JointSimulationRequest.model_validate(
            root_problem.runtime_hints["joint_simulation_request"]
        )
    except (TypeError, ValueError) as exc:
        raise DesignProblemAuthorityError(
            "recursive_parent_n5_request_invalid",
            str(exc),
        ) from exc
    return {root_ref: request}


def _compile_parent_joint_n4_atom_members(
    *,
    problem: DesignProblem,
    source_result: object,
    child_problems: Sequence[object],
    model_id: str,
    world_model_record_ref: str,
) -> tuple[object, ...]:
    """Select parent-frame atoms only from the exact N4 source groups.

    This compiler does not choose among multiple proposals in one semantic
    child group. A source group contributes a parent N5 member only when it has
    exactly one producer-owned atom; downstream child-frame refinement remains
    a separate, unresolved scope question.
    """

    from polisyos.runtime.quality.design_generation import (
        GenerationUnderAResult,
        N4CandidateChildProblem,
        ShadowGeneratedCandidate,
    )
    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
    )

    if type(problem) is not DesignProblem or type(source_result) is not GenerationUnderAResult:
        raise DesignProblemAuthorityError("recursive_parent_n5_source_untyped")
    normalized_problem = DesignProblem.model_validate(problem.model_dump(mode="python"))
    normalized_source = GenerationUnderAResult.model_validate(
        source_result.model_dump(mode="python")
    )
    problem_ref = gy_content_hash(normalized_problem.model_dump(mode="json"))
    source_ref = gy_content_hash(normalized_source.model_dump(mode="json"))
    if (
        normalized_source.design_problem_ref != problem_ref
        or normalized_source.model_id != model_id
        or normalized_source.status != "generated"
        or not normalized_source.candidates
    ):
        raise DesignProblemAuthorityError("recursive_parent_n5_source_binding_not_established")
    if len(child_problems) < 2 or any(
        type(child) is not N4CandidateChildProblem for child in child_problems
    ):
        raise DesignProblemAuthorityError("recursive_parent_n5_child_denominator_not_established")

    candidates_by_hash: dict[str, list[ShadowGeneratedCandidate]] = {}
    for candidate in normalized_source.candidates:
        if type(candidate) is not ShadowGeneratedCandidate:
            raise DesignProblemAuthorityError("recursive_parent_n5_source_candidate_untyped")
        candidates_by_hash.setdefault(candidate.atom.content_hash, []).append(candidate)
    if any(len(rows) != 1 for rows in candidates_by_hash.values()):
        raise DesignProblemAuthorityError("recursive_parent_n5_source_candidate_duplicate")

    selected: list[InterventionAtomBinding] = []
    selected_hashes: set[str] = set()
    outcome = normalized_problem.outcome_of_interest.target_variable
    for child in child_problems:
        child_source = child.problem.runtime_hints.get("n4_candidate_child_source")
        if (
            child.source_result_ref != source_ref
            or not isinstance(child_source, Mapping)
            or child_source.get("parent_design_problem_ref") != problem_ref
            or child_source.get("source_result_ref") != source_ref
        ):
            raise DesignProblemAuthorityError(
                "recursive_parent_n5_child_source_binding_not_established"
            )
        atom_refs = tuple(child.source_atom_refs)
        if len(atom_refs) != 1 or len(set(atom_refs)) != 1:
            raise DesignProblemAuthorityError(
                "recursive_parent_n5_source_member_selection_not_established"
            )
        source_atom_ref = atom_refs[0]
        source_candidates = candidates_by_hash.get(source_atom_ref, ())
        if len(source_candidates) != 1:
            raise DesignProblemAuthorityError("recursive_parent_n5_source_member_not_established")
        candidate = source_candidates[0]
        atom = candidate.atom
        estimand = atom.intended_downstream_estimand
        if (
            candidate.provenance.model_id != model_id
            or candidate.provenance.content_hash != atom.content_hash
            or type(atom) is not InterventionAtomBinding
            or atom.status != "candidate_unverified"
            or atom.problem_frame_ref != problem_ref
            or atom.world_model_record_ref != world_model_record_ref
            or estimand.outcome_variables != (outcome,)
            or estimand.target_population != normalized_problem.jurisdiction_time.region
            or (
                estimand.metric_id is not None
                and estimand.metric_id != normalized_problem.outcome_of_interest.metric_id
            )
        ):
            raise DesignProblemAuthorityError(
                "recursive_parent_n5_source_atom_binding_not_established"
            )
        if atom.content_hash in selected_hashes:
            raise DesignProblemAuthorityError("recursive_parent_n5_source_member_duplicate")
        selected_hashes.add(atom.content_hash)
        selected.append(atom)

    if selected_hashes != set(candidates_by_hash):
        raise DesignProblemAuthorityError("recursive_parent_n5_source_member_denominator_mismatch")
    return tuple(selected)


def _build_parent_joint_candidate_request(
    *,
    candidate_intent: Literal["n4_unique_parent_source_members.v1"] | None,
    problem: DesignProblem,
    source_result: object,
    source_ref: ArtifactRef,
    child_problems: Sequence[object],
    child_node_refs: Sequence[str],
    model_id: str,
    handoff: GenericCycleSimulationContextHandoffV1,
    admission_owner: GenericCycleSimulationAdmissionOwner,
) -> tuple[object, object]:
    """Build an explicitly requested all-member hypothetical N5 diagnostic.

    The profile supplies every simulation axis. The selected atoms and child
    denominator are re-derived from the source artifact; this function accepts
    no caller- or model-authored request axes. The result is not an N4-authored
    compound design: source candidates remain alternatives, and composition
    and child-to-parent refinement stay not established.
    """

    if candidate_intent != "n4_unique_parent_source_members.v1":
        raise DesignProblemAuthorityError("recursive_parent_joint_candidate_intent_not_established")

    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.design_generation import GenerationUnderAResult
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.joint_simulation_horizon import (
        EnginePlan,
        JointSimulationRequest,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        ParentJointCandidateSelectionV2,
        ParentJointCandidateSourceMember,
    )

    if (
        type(source_result) is not GenerationUnderAResult
        or type(source_ref) is not ArtifactRef
        or type(handoff) is not GenericCycleSimulationContextHandoffV1
        or type(admission_owner) is not GenericCycleSimulationAdmissionOwner
        or handoff.profile.profile_selection_kind != "problem"
    ):
        raise DesignProblemAuthorityError("recursive_parent_joint_candidate_owner_untyped")
    parent_ref = cycle_job_design_problem_ref(problem)
    raw_parent_ref = gy_content_hash(problem.model_dump(mode="json"))
    world_record = handoff.profile.context_inputs.world_model_record
    if (
        source_result.design_problem_ref != raw_parent_ref
        or parent_ref != raw_parent_ref
        or handoff.context.design_problem_ref != parent_ref
        or len(child_problems) != len(child_node_refs)
        or len(child_problems) < 2
    ):
        raise DesignProblemAuthorityError(
            "recursive_parent_joint_candidate_parent_frame_not_established"
        )

    atoms = _compile_parent_joint_n4_atom_members(
        problem=problem,
        source_result=source_result,
        child_problems=child_problems,
        model_id=model_id,
        world_model_record_ref=world_record.world_model_record_id,
    )
    candidates_by_hash = {
        candidate.atom.content_hash: candidate for candidate in source_result.candidates
    }
    members = []
    for child, child_node_ref, atom in zip(
        child_problems,
        child_node_refs,
        atoms,
        strict=True,
    ):
        source_candidates = [
            candidate
            for candidate in source_result.candidates
            if candidate.atom.content_hash in child.source_atom_refs
        ]
        if (
            len(source_candidates) != 1
            or source_candidates[0].atom != atom
            or child.source_atom_refs != (atom.content_hash,)
            or atom.problem_frame_ref != parent_ref
        ):
            raise DesignProblemAuthorityError(
                "recursive_parent_joint_candidate_source_member_not_established"
            )
        candidate = source_candidates[0]
        members.append(
            ParentJointCandidateSourceMember(
                child_node_ref=child_node_ref,
                child_design_problem_ref=cycle_job_design_problem_ref(child.problem),
                semantic_ref=child.semantic_ref,
                source_candidate_id=candidate.candidate_id,
                source_candidate_content_hash=gy_content_hash(candidate.model_dump(mode="json")),
                source_atom_id=atom.atom_id,
                source_atom_content_hash=atom.content_hash,
                parent_problem_frame_ref=atom.problem_frame_ref,
            )
        )
    if set(candidates_by_hash) != {atom.content_hash for atom in atoms}:
        raise DesignProblemAuthorityError(
            "recursive_parent_joint_candidate_source_denominator_mismatch"
        )

    outcome = problem.outcome_of_interest.target_variable
    profile = handoff.profile
    if (
        profile.n5.resource != "ncm_parallel_worlds"
        or outcome not in profile.n5.baseline_state
        or profile.context_inputs.world_model_record.content_hash != world_record.content_hash
    ):
        raise DesignProblemAuthorityError(
            "recursive_parent_joint_candidate_profile_axes_not_established"
        )
    port = JointSimulationPort(
        cycle_substrate_context=handoff.context,
        artifact_store=admission_owner.store,
    )
    request = JointSimulationRequest(
        world_model_record_ref=world_record.world_model_record_id,
        world_model_record=world_record,
        intervention_atoms=atoms,
        selected_outcomes=(outcome,),
        horizon=profile.n5.horizon,
        engine_plan=(
            EnginePlan(
                engine_kind=profile.n5.resource,
                objective_ref=f"objective://{outcome}",
                eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
                ncm_spec=port._resolve_joint_simulation_ncm(
                    problem=problem,
                    world_record=world_record,
                ),
                variable_map=JointSimulationPort._joint_simulation_variable_map(
                    atoms=atoms,
                    outcome=outcome,
                    raw_hint=None,
                ),
            ),
        ),
        baseline_state=dict(profile.n5.baseline_state),
        comparator_refs=profile.n5.comparator_refs,
        budget_ref=profile.n5.budget_ref,
        seed=profile.n5.seed,
        replications=profile.n5.replications,
        candidate_intent=candidate_intent,
        member_basis="hypothetical_all_unique_n4_source_members",
        source_candidate_relationship="alternatives",
        composition_status="not_established",
        composition_limitation_code=(
            "n4_source_candidates_are_alternatives_not_authored_compound_design"
        ),
        child_to_parent_refinement_status="not_established",
        child_to_parent_refinement_limitation_code=(
            "child_to_parent_refinement_rule_not_established"
        ),
    )
    if request.coupling_graph is not None:
        raise DesignProblemAuthorityError(
            "recursive_parent_joint_candidate_cannot_supply_coupling_graph"
        )

    selection_fields = {
        "candidate_intent": candidate_intent,
        "selection_rule": "hypothetical_all_unique_n4_source_members.v2",
        "member_basis": "hypothetical_all_unique_n4_source_members",
        "source_candidate_relationship": "alternatives",
        "composition_status": "not_established",
        "composition_limitation_code": (
            "n4_source_candidates_are_alternatives_not_authored_compound_design"
        ),
        "child_to_parent_refinement_status": "not_established",
        "child_to_parent_refinement_limitation_code": (
            "child_to_parent_refinement_rule_not_established"
        ),
        "joint_simulation_request_content_hash": gy_content_hash(request.model_dump(mode="json")),
        "parent_design_problem_ref": parent_ref,
        "n4_source_ref": source_ref,
        "n4_source_result_content_hash": gy_content_hash(source_result.model_dump(mode="json")),
        "context_job_ref": handoff.context_job_ref,
        "profile_ref": handoff.profile_ref,
        "profile_selection_ref": profile.profile_selection_ref,
        "world_model_record_ref": world_record.world_model_record_id,
        "world_model_record_content_hash": world_record.content_hash,
        "outcome_variable": outcome,
        "child_node_refs": tuple(child_node_refs),
        "members": tuple(members),
    }
    provisional = ParentJointCandidateSelectionV2.model_construct(
        **selection_fields,
        content_hash="sha256:" + "0" * 64,
    )
    selection_payload = provisional.model_dump(mode="json", exclude={"content_hash"})
    selection = ParentJointCandidateSelectionV2.model_validate(
        {
            **selection_payload,
            "content_hash": gy_content_hash(selection_payload),
        }
    )
    if tuple(member.source_atom_id for member in selection.members) != tuple(
        atom.intervention_id for atom in request.intervention_atoms
    ) or tuple(member.source_atom_content_hash for member in selection.members) != tuple(
        atom.content_hash for atom in request.intervention_atoms
    ):
        raise DesignProblemAuthorityError(
            "recursive_parent_joint_candidate_request_member_mismatch"
        )
    return selection, request


async def compile_and_run_recursive_generation_cycle(
    *,
    raw_request: str,
    context: Mapping[str, object],
    model_name: str,
    trusted_source_context: Mapping[str, object | None] | None = None,
    execution_intent: ExecutionIntent | None = None,
    joint_interaction_candidate_intent: Literal["n4_unique_parent_source_members.v1"] | None = None,
    n4_proposal_only: bool = False,
    n4_proposal_only_origin: Literal["explicit", "derived_legacy_default"] = "explicit",
    producer_run_id: str | None = None,
    producer_settlement_store: BudgetMiddleware | None = None,
    _producer_budget_reconciler: Callable[[BudgetState], None] | None = None,
    compiler_gateway: _DesignProblemGatewayClient | None,
    controller: RecursiveGenerationCycleController | None = None,
    budget_state: BudgetState,
    recursive_budget: RecursiveCycleBudget,
    recursive_budget_resolution: RecursiveBudgetResolution | None = None,
    root_evaluation_context: EvaluationExecutionContext | None = (
        _ROOT_EVALUATION_CONTEXT_UNSET  # type: ignore[assignment]
    ),
    eval_safety_verifier: EvalSafetyVerifierPort | None = None,
    span_support_client: _SpanSupportVerifierClient | None = None,
    cycle_substrate_context: CycleSubstrateContext | None = None,
    cycle_substrate_context_resolver: Callable[[DesignProblem], object | None] | None = None,
    candidate_simulation_currentness_resolver: Callable[[], bool] | None = None,
    generic_cycle_simulation_handoff_resolver: (
        Callable[[DesignProblem], GenericCycleSimulationContextHandoffV1 | None] | None
    ) = None,
    generic_cycle_simulation_admission_owner: GenericCycleSimulationAdmissionOwner | None = None,
    verified_nl_job_scope: VerifiedNLJobScope | None = None,
    generic_cycle_simulation_currentness_resolver: Callable[[], bool] | None = None,
    enable_contract_testing_credal_source_attempts: bool = False,
    root_n4_generation_port: N4GenerationPort | None = None,
    root_n4_generation_client: object | None = None,
    n4_recursive_source: GenerationUnderAResult | None = None,
    generation_source_repository: GenerationSourceRepository | None = None,
    recursive_leaf_context_owner: RecursiveLeafContextOwner | None = None,
    target_world_scope_profile_id: str | None = None,
    catalog_run_profile: CatalogRunProfile | None = None,
    catalog_serving_source: CatalogServingSourcePaths | None = None,
    promotion_runtime: PromotionRuntime | None = None,
    measurement_root_execution_binding: MeasurementRootExecutionBinding | None = None,
    repo_root: Path | None = None,
) -> (
    CompiledRecursiveGenerationCycleRun
    | N4CandidateProposalExecution
    | N4CandidateScenarioProposalOnlyExecution
):
    """Compile natural language and run the appropriate candidate or authority path.

    ``trusted_source_context`` carries scope identities replayed by the served
    job owner. Caller and model context remain candidate input and cannot replace
    those identities in persisted DesignProblem provenance.
    """

    if n4_proposal_only_origin not in {"explicit", "derived_legacy_default"}:
        raise DesignProblemAuthorityError("n4_proposal_only_origin_not_canonical")
    if type(enable_contract_testing_credal_source_attempts) is not bool:
        raise TypeError("contract_testing_credal_source_attempts_flag_must_be_bool")
    if enable_contract_testing_credal_source_attempts and (
        generic_cycle_simulation_admission_owner is None
        or generic_cycle_simulation_handoff_resolver is None
    ):
        raise DesignProblemAuthorityError(
            "contract_testing_credal_source_attempts_owner_missing",
            "The candidate source attempt requires the configured generic test lane.",
        )
    if promotion_runtime is None:
        raise DesignProblemAuthorityError(
            "promotion_runtime_not_established",
            "The production composition requires its container-owned promotion runtime.",
        )
    if eval_safety_verifier is None:
        raise DesignProblemAuthorityError(
            "eval_safety_verifier_not_established",
            "The production composition requires its verification-only EvalSafety port.",
        )
    if root_evaluation_context is _ROOT_EVALUATION_CONTEXT_UNSET:
        raise DesignProblemAuthorityError(
            "eval_safety_execution_context_not_established",
            "The caller must explicitly choose the ordinary simulation-only route "
            "or provide an EvalSafety context.",
        )
    if recursive_budget_resolution is not None:
        observed_budget = recursive_budget_resolution.recursive_budget
        if (
            observed_budget.max_depth != recursive_budget.max_depth
            or observed_budget.max_nodes != recursive_budget.max_nodes
            or observed_budget.min_cycles_per_leaf != recursive_budget.min_cycles_per_leaf
            or observed_budget.max_cycles_per_leaf != recursive_budget.max_cycles_per_leaf
            or recursive_budget_resolution.effective_max_iterations
            != recursive_budget.max_cycles_per_leaf
        ):
            raise DesignProblemAuthorityError(
                "recursive_budget_resolution_mismatch",
                "The visible HTTP budget resolution must match the recursive budget used.",
            )
    from polisyos.runtime.quality.evaluation_modes import (
        ExecutionIntentBand,
        execution_intent_band_for_mode,
    )
    from polisyos.runtime.quality.evaluation_safety import EvaluationExecutionContext
    from polisyos.runtime.quality.generation_cycle import (
        FOUNDRY_VALUE_PORT_EVALUATOR_ID,
    )

    if root_evaluation_context is not None and not isinstance(
        root_evaluation_context, EvaluationExecutionContext
    ):
        raise DesignProblemAuthorityError(
            "eval_safety_execution_context_not_canonical",
            "The root EvalSafety context must be the canonical typed contract.",
        )
    if execution_intent is None:
        # Direct internal callers predating the served intent map retain their
        # explicit context's mode. The HTTP worker always supplies this value.
        execution_intent = (
            root_evaluation_context.evaluation_mode
            if root_evaluation_context is not None
            else "candidate_only"
        )
    elif execution_intent_band_for_mode(execution_intent) is ExecutionIntentBand.NOT_ESTABLISHED:
        raise DesignProblemAuthorityError(
            "execution_intent_not_canonical",
            "Execution intent must be selected from the server-owned mode vocabulary.",
        )
    if execution_intent == "candidate_only" and root_evaluation_context is not None:
        raise DesignProblemAuthorityError(
            "candidate_execution_intent_context_mismatch",
            "Candidate-only execution cannot carry an attempted EvalSafety context.",
        )
    intent_band = execution_intent_band_for_mode(execution_intent)
    if joint_interaction_candidate_intent is not None and (
        joint_interaction_candidate_intent != "n4_unique_parent_source_members.v1"
        or execution_intent != "simulate_only"
        or generic_cycle_simulation_handoff_resolver is None
        or n4_proposal_only
    ):
        raise DesignProblemAuthorityError(
            "joint_interaction_candidate_intent_scope_mismatch",
            "The compound interaction diagnostic requires the simulate_only generic-profile route.",
        )
    if n4_proposal_only and (
        execution_intent != "simulate_only"
        or controller is not None
        or root_evaluation_context is not None
        or cycle_substrate_context is not None
        or root_n4_generation_port is not None
    ):
        raise DesignProblemAuthorityError(
            "n4_proposal_only_context_conflict",
            "The N4-only selector requires simulate_only and no admitted EvalSafety "
            "context, CycleSubstrateContext, recursive controller, or explicit N4 port.",
        )
    if cycle_substrate_context_resolver is not None and (
        (not n4_proposal_only and n4_recursive_source is None)
        or execution_intent != "simulate_only"
    ):
        raise DesignProblemAuthorityError(
            "cycle_substrate_context_resolver_scope_mismatch",
            "The served context resolver is restricted to the simulate_only N4 handoff.",
        )
    if intent_band is ExecutionIntentBand.DATA_TRUST_REQUIRED:
        raise DesignProblemAuthorityError(
            "data_trust_owner_not_established",
            "DataTrust mode cannot reuse EvalSafety context; its owner bridge is not wired here.",
        )
    if intent_band is ExecutionIntentBand.EVAL_SAFETY_REQUIRED:
        if root_evaluation_context is None:
            raise DesignProblemAuthorityError(
                "eval_safety_execution_context_not_established",
                "Protected evaluation intent requires its admitted current context.",
            )
        if root_evaluation_context.evaluation_mode != execution_intent:
            raise DesignProblemAuthorityError(
                "eval_safety_execution_mode_mismatch",
                "Execution intent must match the canonical EvalSafety context mode.",
            )
    if (
        root_evaluation_context is not None
        and intent_band
        not in {
            ExecutionIntentBand.CANDIDATE_ONLY,
            ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
        }
        and root_evaluation_context.evaluation_mode != execution_intent
    ):
        raise DesignProblemAuthorityError(
            "eval_safety_execution_mode_mismatch",
            "Execution intent must match the canonical EvalSafety context mode.",
        )
    if (
        root_evaluation_context is not None
        and root_evaluation_context.evaluator_owner_id != FOUNDRY_VALUE_PORT_EVALUATOR_ID
    ):
        raise DesignProblemAuthorityError(
            "eval_safety_evaluator_owner_mismatch",
            "The root EvalSafety context must name the canonical Foundry value owner.",
        )
    from polisyos.runtime.http.services.control.response_shapes import (
        _project_call_event_cost,
    )

    nl_preflight_cost_events: list[AgentPipelineCostEvent] = []
    n4_generation_cost_events: list[AgentPipelineCostEvent] = []

    def _observe_preflight_call(event: dict[str, object]) -> None:
        projected = _project_call_event_cost(event)
        nl_preflight_cost_events.append(AgentPipelineCostEvent.model_validate(projected))

    def _observe_n4_call(event: dict[str, object]) -> None:
        projected = _project_call_event_cost(event)
        n4_generation_cost_events.append(AgentPipelineCostEvent.model_validate(projected))

    problem = await build_design_problem_from_nl_request(
        nl_request=raw_request,
        context=context,
        trusted_source_context=trusted_source_context,
        model_name=model_name,
        run_id=producer_run_id,
        producer_settlement_store=producer_settlement_store,
        call_observer=_observe_preflight_call,
        gateway_client=compiler_gateway,
        span_support_client=span_support_client,
    )
    if problem.nl_provenance.raw_request != raw_request:
        raise DesignProblemAuthorityError(
            "cycle_plain_language_content_mismatch",
            "compiled DesignProblem does not preserve the caller's raw request",
        )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextOwnerError,
        VerifiedNLJobScope,
        candidate_cycle_substrate_source_profile_selection,
    )

    try:
        candidate_source_profile_selection = candidate_cycle_substrate_source_profile_selection(
            problem
        )
    except CycleSubstrateContextOwnerError as exc:
        raise DesignProblemAuthorityError(
            "candidate_cycle_source_profile_selection_invalid", str(exc)
        ) from exc
    if candidate_source_profile_selection is not None:
        if n4_proposal_only and n4_proposal_only_origin == "explicit":
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_proposal_only_conflict",
                "Explicit N4-only intent cannot be upgraded to selected-profile generation.",
            )
        if (
            controller is not None
            or root_n4_generation_port is not None
            or n4_recursive_source is not None
        ):
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_recursive_owner_bypass",
                "The selected source profile requires the standard recursive owner route.",
            )
        if root_evaluation_context is not None:
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_eval_safety_context_conflict"
            )
        if not isinstance(repo_root, Path):
            raise DesignProblemAuthorityError("candidate_cycle_source_profile_repo_root_missing")
        if type(recursive_leaf_context_owner) is not RecursiveLeafContextOwner:
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_recursive_owner_missing"
            )
        source_profile_context_owner = recursive_leaf_context_owner._context_owner
        if type(source_profile_context_owner) is not CycleSubstrateContextArtifactOwner:
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_context_owner_missing"
            )
        owner_scope = recursive_leaf_context_owner._verified_nl_job_scope
        if (
            type(owner_scope) is not VerifiedNLJobScope
            or not owner_scope._was_issued_by_verified_nl_execution_owner
        ):
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_verified_scope_missing"
            )
        if verified_nl_job_scope is not None and verified_nl_job_scope is not owner_scope:
            raise DesignProblemAuthorityError(
                "candidate_cycle_source_profile_verified_scope_mismatch"
            )
        verified_nl_job_scope = owner_scope
        if n4_proposal_only:
            # The HTTP worker's legacy proposal-only default is derived from a missing generic
            # handoff resolver. A selected candidate source profile requires the recursive
            # owner path, which persists and freshly resolves V5 before invoking N4.
            n4_proposal_only = False

    producer_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    problem_ref = producer_problem_ref
    candidate_simulation_handoff: CandidateSimulationContextHandoff | None = None
    generic_cycle_simulation_handoff: GenericCycleSimulationContextHandoffV1 | None = None
    context_refresh_limitation_code: str | None = None
    n4_recursive_source_ref: ArtifactRef | None = None
    n4_recursive_source_job_id: str | None = None
    n4_recursive_source_run_id: str | None = None
    n4_recursive_source_tenant_id: str | None = None
    n4_recursive_source_cell_id: str | None = None
    n4_recursive_source_context_job_ref: ArtifactRef | None = None
    n4_recursive_source_profile_config_ref: str | None = None
    n4_recursive_source_profile_selection_ref: str | None = None
    n4_recursive_source_result_status: str | None = None
    n4_child_profile_status: Literal["not_attempted", "resolved", "not_established"] = (
        "not_attempted"
    )
    n4_child_profile_bindings: tuple[CompiledN4ChildProfileBinding, ...] = ()
    n4_child_profile_limitation_code: str | None = None
    generic_n4_child_profile_status: Literal["not_attempted", "resolved", "not_established"] = (
        "not_attempted"
    )
    generic_n4_child_profile_limitation_code: str | None = None
    n4_child_profile_set_ref: ArtifactRef | None = None
    n4_credal_source_attempt_ref: ArtifactRef | None = None
    generic_child_handoffs_by_node: dict[str, GenericCycleSimulationContextHandoffV1] = {}
    planned_child_handoffs: dict[str, CandidateSimulationContextHandoff] = {}

    def _resolve_candidate_context() -> None:
        nonlocal candidate_simulation_handoff
        nonlocal context_refresh_limitation_code
        nonlocal cycle_substrate_context
        if cycle_substrate_context_resolver is None:
            return
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextOwnerError,
        )

        try:
            resolved_context = cycle_substrate_context_resolver(problem)
        except CycleSubstrateContextOwnerError as exc:
            if exc.code != "candidate_simulation_context_evidence_refresh_not_established":
                raise
            if not (n4_proposal_only or execution_intent == "candidate_only"):
                raise
            context_refresh_limitation_code = exc.code
            resolved_context = None
        if type(resolved_context) is CandidateSimulationContextHandoff:
            candidate_simulation_handoff = resolved_context
            cycle_substrate_context = resolved_context.context
        else:
            cycle_substrate_context = resolved_context
        if cycle_substrate_context is not None:
            from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext

            if type(cycle_substrate_context) is not CycleSubstrateContext:
                raise DesignProblemAuthorityError(
                    "cycle_substrate_context_resolver_returned_untyped",
                    "The served context resolver must return the canonical typed artifact.",
                )

    if generic_cycle_simulation_handoff_resolver is not None:
        if (
            execution_intent != "simulate_only"
            or root_evaluation_context is not None
            or n4_proposal_only
            or type(generic_cycle_simulation_admission_owner)
            is not GenericCycleSimulationAdmissionOwner
            or type(recursive_leaf_context_owner) is not RecursiveLeafContextOwner
            or recursive_leaf_context_owner._generic_admission_owner
            is not generic_cycle_simulation_admission_owner
            or verified_nl_job_scope is None
            or recursive_leaf_context_owner._verified_nl_job_scope is not verified_nl_job_scope
        ):
            raise DesignProblemAuthorityError(
                "generic_cycle_simulation_handoff_scope_mismatch",
                "The generic N4/N5 route needs the configured owner and exact issued worker scope.",
            )
        resolved_generic_handoff = generic_cycle_simulation_handoff_resolver(problem)
        if resolved_generic_handoff is not None and (
            type(resolved_generic_handoff) is not GenericCycleSimulationContextHandoffV1
            or resolved_generic_handoff.profile.profile_selection_kind != "problem"
        ):
            raise DesignProblemAuthorityError(
                "generic_cycle_simulation_root_handoff_not_established",
                "The server resolver must return the configured root problem handoff or no match.",
            )
        if resolved_generic_handoff is not None:
            if candidate_simulation_handoff is not None:
                raise DesignProblemAuthorityError("candidate_and_generic_root_handoffs_conflict")
            if (
                generic_cycle_simulation_currentness_resolver is not None
                and not generic_cycle_simulation_currentness_resolver()
            ):
                raise DesignProblemAuthorityError(
                    "generic_cycle_simulation_currentness_not_established"
                )
            generic_cycle_simulation_handoff = (
                generic_cycle_simulation_admission_owner.resolve_handoff(
                    handoff=resolved_generic_handoff,
                    problem=problem,
                    verified_nl_job_scope=verified_nl_job_scope,
                    context_owner=recursive_leaf_context_owner._context_owner,
                    repo_root=repo_root,
                )
            )
            cycle_substrate_context = generic_cycle_simulation_handoff.context
            generic_n4_child_profile_status = "not_established"
            generic_n4_child_profile_limitation_code = "generic_n4_child_profile_not_resolved"
    if generic_cycle_simulation_handoff is None:
        _resolve_candidate_context()
    if generic_cycle_simulation_handoff is None and (
        generic_cycle_simulation_currentness_resolver is not None
        or (
            generic_cycle_simulation_admission_owner is not None
            and generic_cycle_simulation_handoff_resolver is None
        )
    ):
        raise DesignProblemAuthorityError("generic_cycle_simulation_owner_without_handoff")

    # The served simulate-only lane derives recursive children from a real N4
    # result. A root profile is used only to run this producer; each child must
    # independently resolve its own configured profile and job context.
    if (
        n4_recursive_source is None
        and n4_proposal_only
        and execution_intent == "simulate_only"
        and candidate_simulation_handoff is not None
    ):
        if generation_source_repository is None:
            n4_child_profile_status = "not_established"
            n4_child_profile_limitation_code = (
                "n4_recursive_generation_source_repository_not_established"
            )
        else:
            from polisyos.runtime.quality.design_generation import (
                DesignGenerationOrganRun,
                derive_n4_candidate_child_problems,
            )
            from polisyos.runtime.quality.generation_cycle import N4GenerationPort

            root_source_port = N4GenerationPort(
                model_id=model_name,
                llm_client=root_n4_generation_client,
                repo_root=repo_root,
                cycle_substrate_context=cycle_substrate_context,
                producer_run_id=producer_run_id,
                producer_settlement_store=producer_settlement_store,
                call_observer=_observe_n4_call,
            )
            root_organ = await root_source_port(problem, cycle_index=0)
            if type(root_organ) is not DesignGenerationOrganRun:
                raise DesignProblemAuthorityError(
                    "n4_recursive_source_producer_untyped",
                    "The configured N4 source port did not return its canonical organ run.",
                )
            root_handoff = candidate_simulation_handoff
            source_ref = generation_source_repository.persist_ref(
                run_id=root_handoff.run_id,
                cycle_index=0,
                problem=problem,
                organ=root_organ,
                job_id=root_handoff.job_id,
                tenant_id=root_handoff.tenant_id,
                cell_id=root_handoff.cell_id,
            )
            loaded_source = generation_source_repository.load(
                source_ref,
                run_id=root_handoff.run_id,
                expected_job_id=root_handoff.job_id,
                expected_tenant_id=root_handoff.tenant_id,
                expected_cell_id=root_handoff.cell_id,
            )
            if (
                gy_content_hash(loaded_source.problem.model_dump(mode="json")) != problem_ref
                or gy_content_hash(loaded_source.generation_result.model_dump(mode="json"))
                != gy_content_hash(root_organ.result.model_dump(mode="json"))
                or loaded_source.cycle_substrate_context is None
                or loaded_source.cycle_substrate_context.content_hash
                != cycle_substrate_context.content_hash
                or loaded_source.generation_result.design_problem_ref != problem_ref
            ):
                raise DesignProblemAuthorityError(
                    "n4_recursive_source_readback_binding_mismatch",
                    "Fresh N4 source readback did not match the producing problem and context.",
                )
            n4_recursive_source_ref = source_ref
            n4_recursive_source_job_id = root_handoff.job_id
            n4_recursive_source_run_id = root_handoff.run_id
            n4_recursive_source_tenant_id = root_handoff.tenant_id
            n4_recursive_source_cell_id = root_handoff.cell_id
            n4_recursive_source_context_job_ref = root_handoff.context_job_ref
            n4_recursive_source_profile_config_ref = root_handoff.profile_config_ref
            n4_recursive_source_profile_selection_ref = root_handoff.profile.profile_selection_ref
            n4_recursive_source_result_status = loaded_source.generation_result.status
            n4_recursive_source = loaded_source.generation_result

            if loaded_source.generation_result.status != "generated":
                n4_child_profile_status = "not_established"
                n4_child_profile_limitation_code = "n4_recursive_source_generation_not_complete"
            else:
                children = derive_n4_candidate_child_problems(
                    problem,
                    loaded_source.generation_result,
                    model_id=model_name,
                )
                if not 1 <= len(children) <= 2:
                    n4_child_profile_status = "not_established"
                    n4_child_profile_limitation_code = (
                        "n4_recursive_child_count_outside_supported_profile"
                    )
                elif cycle_substrate_context_resolver is None:
                    n4_child_profile_status = "not_established"
                    n4_child_profile_limitation_code = (
                        "n4_recursive_child_context_resolver_not_established"
                    )
                else:
                    child_handoffs: dict[str, CandidateSimulationContextHandoff] = {}
                    child_bindings: list[CompiledN4ChildProfileBinding] = []
                    root_scope = (
                        root_handoff.job_id,
                        root_handoff.run_id,
                        root_handoff.tenant_id,
                        root_handoff.cell_id,
                    )
                    child_context_missing = False
                    for child in children:
                        child_ref = "design-problem://" + gy_content_hash(
                            child.problem.model_dump(mode="json")
                        ).removeprefix("sha256:")
                        resolved_child_context = cycle_substrate_context_resolver(child.problem)
                        if type(resolved_child_context) is not CandidateSimulationContextHandoff:
                            child_context_missing = True
                            break
                        child_scope = (
                            resolved_child_context.job_id,
                            resolved_child_context.run_id,
                            resolved_child_context.tenant_id,
                            resolved_child_context.cell_id,
                        )
                        if (
                            child_scope != root_scope
                            or resolved_child_context.profile.profile_selection_ref
                            == root_handoff.profile.profile_selection_ref
                        ):
                            raise DesignProblemAuthorityError(
                                "n4_recursive_child_context_scope_or_profile_reused",
                                "Each generated child needs its own same-job configured profile.",
                            )
                        child_handoffs[child_ref] = resolved_child_context
                        child_bindings.append(
                            CompiledN4ChildProfileBinding(
                                node_ref=child_ref,
                                design_problem_ref=gy_content_hash(
                                    child.problem.model_dump(mode="json")
                                ),
                                handoff=resolved_child_context,
                            )
                        )
                    if child_context_missing:
                        n4_child_profile_status = "not_established"
                        n4_child_profile_limitation_code = (
                            "n4_recursive_child_configured_profile_not_established"
                        )
                    else:
                        requested_iterations = (
                            recursive_budget_resolution.requested_max_iterations
                            if recursive_budget_resolution is not None
                            else recursive_budget.max_cycles_per_leaf
                        )
                        _effective_iterations, child_budget_resolution = (
                            _resolve_http_recursive_budget(
                                requested_iterations,
                                candidate_child_count=len(children),
                            )
                        )
                        recursive_budget_resolution = child_budget_resolution
                        recursive_budget = type(recursive_budget).model_validate(
                            child_budget_resolution.recursive_budget.model_dump(mode="python")
                        )
                        planned_child_handoffs = child_handoffs
                        n4_child_profile_bindings = tuple(child_bindings)
                        n4_child_profile_status = "resolved"
                        n4_child_profile_limitation_code = None
    if (
        n4_recursive_source is None
        and generic_cycle_simulation_handoff is not None
        and execution_intent == "simulate_only"
    ):
        if generation_source_repository is None or recursive_leaf_context_owner is None:
            generic_n4_child_profile_status = "not_established"
            generic_n4_child_profile_limitation_code = (
                "generic_n4_source_or_family_owner_not_established"
            )
        else:
            from polisyos.runtime.quality.design_generation import (
                DesignGenerationOrganRun,
            )
            from polisyos.runtime.quality.generation_cycle import N4GenerationPort
            from polisyos.runtime.quality.generation_source import (
                _canonical_model_content_hash,
            )
            from polisyos.runtime.quality.recursive_generation_cycle import (
                RecursiveGenerationCycleError,
            )

            root_handoff = generic_cycle_simulation_handoff
            root_source_port = N4GenerationPort(
                model_id=model_name,
                llm_client=root_n4_generation_client,
                repo_root=repo_root,
                cycle_substrate_context=root_handoff.context,
                producer_run_id=producer_run_id,
                producer_settlement_store=producer_settlement_store,
                call_observer=_observe_n4_call,
            )
            root_organ = await root_source_port(problem, cycle_index=0)
            if type(root_organ) is not DesignGenerationOrganRun:
                raise DesignProblemAuthorityError(
                    "generic_n4_source_producer_untyped",
                    "The configured N4 source port did not return its canonical organ run.",
                )
            internal_source_run_id = producer_run_id or root_handoff.run_id
            source_ref = generation_source_repository.persist_ref(
                run_id=internal_source_run_id,
                expected_run_id=root_handoff.run_id,
                cycle_index=0,
                problem=problem,
                organ=root_organ,
                execution_scope=(
                    "contract_testing"
                    if enable_contract_testing_credal_source_attempts
                    else "production"
                ),
                job_id=root_handoff.job_id,
                tenant_id=root_handoff.tenant_id,
                cell_id=root_handoff.cell_id,
                context_job_ref=root_handoff.context_job_ref,
                profile_ref=root_handoff.profile_ref,
                n4_child_profile_family_ref=root_handoff.n4_child_profile_family_ref,
            )
            loaded_source = generation_source_repository.load(
                source_ref,
                run_id=internal_source_run_id,
                expected_run_id=root_handoff.run_id,
                expected_job_id=root_handoff.job_id,
                expected_tenant_id=root_handoff.tenant_id,
                expected_cell_id=root_handoff.cell_id,
                context_job_ref=root_handoff.context_job_ref,
                profile_ref=root_handoff.profile_ref,
                n4_child_profile_family_ref=root_handoff.n4_child_profile_family_ref,
            )
            if (
                _canonical_model_content_hash(loaded_source.problem)
                != _canonical_model_content_hash(problem)
                or _canonical_model_content_hash(loaded_source.generation_result)
                != _canonical_model_content_hash(root_organ.result)
                or loaded_source.cycle_substrate_context is None
                or _canonical_model_content_hash(loaded_source.cycle_substrate_context)
                != _canonical_model_content_hash(root_handoff.context)
                or loaded_source.generation_result.design_problem_ref != producer_problem_ref
            ):
                raise DesignProblemAuthorityError(
                    "generic_n4_source_readback_binding_mismatch",
                    "Fresh N4 source readback did not match the producer and generic handoff.",
                )
            n4_recursive_source_ref = source_ref
            n4_recursive_source_job_id = root_handoff.job_id
            n4_recursive_source_run_id = root_handoff.run_id
            n4_recursive_source_tenant_id = root_handoff.tenant_id
            n4_recursive_source_cell_id = root_handoff.cell_id
            n4_recursive_source_context_job_ref = root_handoff.context_job_ref
            n4_recursive_source_profile_config_ref = root_handoff.profile.profile_id
            n4_recursive_source_profile_selection_ref = root_handoff.profile.profile_selection_ref
            n4_recursive_source_result_status = loaded_source.generation_result.status
            n4_recursive_source = loaded_source.generation_result
            if enable_contract_testing_credal_source_attempts:
                n4_credal_source_attempt_ref = (
                    generation_source_repository.persist_candidate_credal_source_attempt(
                        n4_source_ref=source_ref,
                        source_run_id=internal_source_run_id,
                        job_id=root_handoff.job_id,
                        run_id=root_handoff.run_id,
                        tenant_id=root_handoff.tenant_id,
                        cell_id=root_handoff.cell_id,
                        problem=problem,
                        context=root_handoff.context,
                        context_job_ref=root_handoff.context_job_ref,
                        profile_ref=root_handoff.profile_ref,
                        profile_id=root_handoff.profile.profile_id,
                        profile_selection_ref=root_handoff.profile.profile_selection_ref,
                        n4_child_profile_family_ref=(root_handoff.n4_child_profile_family_ref),
                    )
                )
            if loaded_source.generation_result.status != "generated":
                generic_n4_child_profile_status = "not_established"
                generic_n4_child_profile_limitation_code = (
                    "generic_n4_source_generation_not_complete"
                )
            elif root_handoff.n4_child_profile_family_ref is None:
                generic_n4_child_profile_status = "not_established"
                generic_n4_child_profile_limitation_code = (
                    "generic_n4_child_profile_family_not_established"
                )
            else:
                try:
                    children, child_handoffs = (
                        recursive_leaf_context_owner.admit_n4_child_profile_family(
                            parent_problem=problem,
                            parent_handoff=root_handoff,
                            source_ref=source_ref,
                            source_run_id=internal_source_run_id,
                            source_repository=generation_source_repository,
                        )
                    )
                except RecursiveGenerationCycleError as exc:
                    if exc.code not in {
                        "recursive_generic_n4_child_family_denominator_mismatch",
                        "recursive_generic_n4_child_profile_not_in_pre_family",
                    }:
                        raise
                    generic_n4_child_profile_status = "not_established"
                    generic_n4_child_profile_limitation_code = exc.code
                else:
                    requested_iterations = (
                        recursive_budget_resolution.requested_max_iterations
                        if recursive_budget_resolution is not None
                        else recursive_budget.max_cycles_per_leaf
                    )
                    _effective_iterations, child_budget_resolution = _resolve_http_recursive_budget(
                        requested_iterations,
                        generic_child_count=len(children),
                    )
                    recursive_budget_resolution = child_budget_resolution
                    recursive_budget = type(recursive_budget).model_validate(
                        child_budget_resolution.recursive_budget.model_dump(mode="python")
                    )
                    n4_child_profile_set_ref = (
                        recursive_leaf_context_owner.persist_n4_child_profile_set(
                            parent_problem=problem,
                            parent_handoff=root_handoff,
                            source_ref=source_ref,
                            child_handoffs=child_handoffs,
                            source_run_id=internal_source_run_id,
                            source_repository=generation_source_repository,
                        )
                    )
                    generic_child_handoffs_by_node = child_handoffs
                    generic_n4_child_profile_status = "resolved"
                    generic_n4_child_profile_limitation_code = None
    if generic_cycle_simulation_handoff is not None:
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )

        problem_ref = cycle_job_design_problem_ref(problem)
    if cycle_substrate_context is None:
        scope_selection = _classify_target_world_scope_profile(target_world_scope_profile_id)
    else:
        scope_selection = None
    candidate_only_n4_route = (
        cycle_substrate_context is None
        and execution_intent == "candidate_only"
        and root_n4_generation_port is None
    )
    if candidate_only_n4_route or (n4_proposal_only and cycle_substrate_context is None):
        from polisyos.runtime.quality.design_generation import (
            generate_design_candidate_proposal_under_a,
        )

        proposal = await generate_design_candidate_proposal_under_a(
            problem,
            model_id=model_name,
            repo_root=repo_root,
            producer_run_id=producer_run_id,
            producer_settlement_store=producer_settlement_store,
            call_observer=_observe_n4_call,
        )
        return N4CandidateProposalExecution(
            design_problem=problem,
            proposal=proposal,
            nl_preflight_cost_events=tuple(nl_preflight_cost_events),
            n4_generation_cost_events=tuple(n4_generation_cost_events),
            target_world_scope_profile_id=target_world_scope_profile_id,
            target_world_scope_status="not_established",
            target_world_scope_profile_status=(
                "profile_refresh_unavailable"
                if context_refresh_limitation_code is not None
                else scope_selection.status
                if scope_selection is not None
                else "profile_not_requested"
            ),
            target_world_scope_profile_limitation_code=context_refresh_limitation_code,
            target_world_model_record_ref=None,
        )
    # Generic simulate_only calls retain the recursive route unless the served
    # owner explicitly selects its N4-only subcomputation after intent replay.
    if cycle_substrate_context is None and root_n4_generation_port is not None:
        raise DesignProblemAuthorityError(
            "cycle_substrate_context_not_established",
            "The HTTP composition rejects an explicit N4 producer without one "
            "owner-bound CycleSubstrateContext.",
        )
    if (
        cycle_substrate_context is not None
        and cycle_substrate_context.design_problem_ref != problem_ref
    ):
        raise DesignProblemAuthorityError(
            "cycle_substrate_design_problem_mismatch",
            "CycleSubstrateContext must be content-bound to the compiled DesignProblem",
        )
    if cycle_substrate_context is not None:
        from polisyos.runtime.quality.cycle_substrate import (
            revalidate_cycle_substrate_context,
        )

        revalidate_cycle_substrate_context(cycle_substrate_context)

    if controller is not None:
        if getattr(controller, "_authority_scope", None) != "production":
            raise DesignProblemAuthorityError(
                "recursive_controller_not_production_scoped",
                "The HTTP composition rejects contract-testing recursive controllers.",
            )
        if getattr(controller, "_promotion_runtime", None) is not promotion_runtime:
            raise DesignProblemAuthorityError(
                "recursive_controller_foreign_promotion_runtime",
                "The HTTP composition requires its container-owned promotion runtime.",
            )
        if getattr(controller, "_eval_safety_verifier", None) is not eval_safety_verifier:
            raise DesignProblemAuthorityError(
                "recursive_controller_eval_safety_verifier_mismatch",
                "The injected recursive controller must retain the exact EvalSafety verifier.",
            )
        if (
            getattr(controller, "_epoch_subject_authority", None)
            is not promotion_runtime.epoch_subject_authority
            or getattr(controller, "_epoch_validity_gate", None)
            is not promotion_runtime.epoch_validity_gate
            or getattr(controller, "_epoch_n9_evidence_resolver", None)
            is not promotion_runtime.epoch_n9_evidence_resolver
        ):
            raise DesignProblemAuthorityError(
                "recursive_controller_epoch_owner_binding_mismatch",
                "The HTTP composition derives every epoch dependency from one runtime.",
            )
        controller_repo_root = getattr(controller, "_repo_root", None)
        caller_repo_root = repo_root.resolve() if repo_root is not None else None
        if controller_repo_root != caller_repo_root:
            raise DesignProblemAuthorityError(
                "recursive_controller_repo_root_mismatch",
                "The injected recursive controller must retain the exact source checkout "
                "identity supplied by the HTTP composition.",
            )
        if getattr(controller, "_catalog_run_profile", None) != catalog_run_profile:
            raise DesignProblemAuthorityError(
                "recursive_controller_catalog_run_profile_mismatch",
                "The recursive controller must retain the selected Catalog run profile.",
            )
        if getattr(controller, "_catalog_serving_source", None) is not catalog_serving_source:
            raise DesignProblemAuthorityError(
                "recursive_controller_catalog_source_mismatch",
                "The recursive controller must retain the exact resolved Catalog source.",
            )
        if (
            getattr(controller, "_measurement_root_execution_binding", None)
            is not measurement_root_execution_binding
        ):
            raise DesignProblemAuthorityError(
                "recursive_controller_measurement_scope_binding_mismatch",
                "The controller must retain the exact immutable control-job admission binding.",
            )
        resolved_controller = controller
    else:
        resolved_controller = build_default_recursive_generation_cycle_controller(
            repo_root=repo_root,
            model_id=model_name,
            catalog_run_profile=catalog_run_profile,
            catalog_serving_source=catalog_serving_source,
            promotion_runtime=promotion_runtime,
            eval_safety_verifier=eval_safety_verifier,
            measurement_root_execution_binding=measurement_root_execution_binding,
        )

    # The internal candidate-child route takes complete immutable actual N4
    # source. HTTP request dictionaries cannot allocate this source or owner.
    problems_by_node = None
    contexts_by_node = None
    handoffs_by_node = None
    generation_ports_by_node = None
    generic_handoffs_by_node: dict[str, GenericCycleSimulationContextHandoffV1] | None = None
    if n4_recursive_source is not None and (
        n4_child_profile_status == "resolved"
        or generic_n4_child_profile_status == "resolved"
        or n4_recursive_source_ref is None
    ):
        from polisyos.runtime.quality.design_generation import (
            derive_n4_candidate_child_problems,
        )
        from polisyos.runtime.quality.generation_cycle import N4GenerationPort

        if execution_intent != "simulate_only" or root_evaluation_context is not None:
            raise DesignProblemAuthorityError("n4_recursive_child_intent_not_candidate")
        if type(recursive_leaf_context_owner) is not RecursiveLeafContextOwner:
            raise DesignProblemAuthorityError("n4_recursive_child_context_owner_missing")
        children = derive_n4_candidate_child_problems(
            problem, n4_recursive_source, model_id=model_name
        )
        if not children:
            raise DesignProblemAuthorityError("n4_recursive_child_source_empty")
        if (
            recursive_budget_resolution is None
            or recursive_budget_resolution.child_budget_profile
            != (
                "n4-source-complete-child-set.v1"
                if generic_n4_child_profile_status == "resolved"
                else "candidate-lever-exploration-at-most-2.v1"
            )
            or recursive_budget_resolution.requested_candidate_children != len(children)
            or recursive_budget_resolution.effective_candidate_children != len(children)
            or recursive_budget.max_depth != 1
            or recursive_budget.max_nodes != 1 + len(children)
        ):
            raise DesignProblemAuthorityError("n4_recursive_child_supported_budget_missing")
        if generic_n4_child_profile_status == "resolved":
            if (
                generic_cycle_simulation_handoff is None
                or n4_child_profile_set_ref is None
                or generation_source_repository is None
            ):
                raise DesignProblemAuthorityError("generic_n4_child_profile_set_inputs_missing")
            family = recursive_leaf_context_owner.load_n4_child_profile_set(
                n4_child_profile_set_ref,
                expected_job_id=generic_cycle_simulation_handoff.job_id,
                expected_run_id=generic_cycle_simulation_handoff.run_id,
                expected_tenant_id=generic_cycle_simulation_handoff.tenant_id,
                expected_cell_id=generic_cycle_simulation_handoff.cell_id,
                expected_parent_handoff=generic_cycle_simulation_handoff,
                source_repository=generation_source_repository,
            )
            if len(family.children) != len(children):
                raise DesignProblemAuthorityError(
                    "generic_n4_child_profile_family_source_denominator_mismatch"
                )
            family_rows = {row.node_ref: row for row in family.children}
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_design_problem_ref,
            )

            actual_children = {
                "design-problem://"
                + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:"): child
                for child in children
            }
            if set(family_rows) != set(actual_children):
                raise DesignProblemAuthorityError(
                    "generic_n4_child_profile_family_source_denominator_mismatch"
                )
            problems_by_node = {}
            contexts_by_node = {}
            generic_handoffs_by_node = {}
            generation_ports_by_node = {}
            root_scope = (
                generic_cycle_simulation_handoff.job_id,
                generic_cycle_simulation_handoff.run_id,
                generic_cycle_simulation_handoff.tenant_id,
                generic_cycle_simulation_handoff.cell_id,
            )
            for node_ref, child in actual_children.items():
                row = family_rows[node_ref]
                handoff = generic_child_handoffs_by_node.get(node_ref)
                if (
                    handoff is None
                    or handoff != row.handoff
                    or row.problem != child.problem
                    or (
                        handoff.job_id,
                        handoff.run_id,
                        handoff.tenant_id,
                        handoff.cell_id,
                    )
                    != root_scope
                ):
                    raise DesignProblemAuthorityError(
                        "generic_n4_child_profile_family_current_binding_mismatch"
                    )
                problems_by_node[node_ref] = child.problem
                contexts_by_node[node_ref] = handoff.context
                generic_handoffs_by_node[node_ref] = handoff
                generation_ports_by_node[node_ref] = N4GenerationPort(
                    model_id=model_name,
                    repo_root=repo_root,
                    cycle_substrate_context=handoff.context,
                    producer_run_id=producer_run_id,
                    producer_settlement_store=producer_settlement_store,
                    call_observer=_observe_n4_call,
                )
        else:
            if cycle_substrate_context_resolver is None:
                raise DesignProblemAuthorityError("n4_recursive_child_context_resolver_missing")
            problems_by_node = {}
            contexts_by_node = {}
            handoffs_by_node = {}
            generation_ports_by_node = {}
            root_scope = (
                (
                    candidate_simulation_handoff.job_id,
                    candidate_simulation_handoff.run_id,
                    candidate_simulation_handoff.tenant_id,
                    candidate_simulation_handoff.cell_id,
                )
                if candidate_simulation_handoff is not None
                else None
            )
            for child in children:
                child_ref = "design-problem://" + gy_content_hash(
                    child.problem.model_dump(mode="json")
                ).removeprefix("sha256:")
                handoff = planned_child_handoffs.get(child_ref)
                if handoff is None:
                    handoff = cycle_substrate_context_resolver(child.problem)
                if type(handoff) is not CandidateSimulationContextHandoff:
                    raise DesignProblemAuthorityError(
                        "n4_recursive_child_configured_context_missing"
                    )
                scope = (
                    handoff.job_id,
                    handoff.run_id,
                    handoff.tenant_id,
                    handoff.cell_id,
                )
                if root_scope is not None and scope != root_scope:
                    raise DesignProblemAuthorityError("n4_recursive_child_job_scope_mismatch")
                problems_by_node[child_ref] = child.problem
                contexts_by_node[child_ref] = handoff.context
                handoffs_by_node[child_ref] = handoff
                generation_ports_by_node[child_ref] = N4GenerationPort(
                    model_id=model_name,
                    repo_root=repo_root,
                    cycle_substrate_context=handoff.context,
                    candidate_simulation_handoff=handoff,
                    producer_run_id=producer_run_id,
                    producer_settlement_store=producer_settlement_store,
                    call_observer=_observe_n4_call,
                )

    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    if (
        not generation_ports_by_node
        and root_n4_generation_port is None
        and candidate_simulation_handoff is not None
    ):
        from polisyos.runtime.quality.generation_cycle import N4GenerationPort

        generation_ports_by_node = {
            root_ref: N4GenerationPort(
                model_id=model_name,
                repo_root=repo_root,
                cycle_substrate_context=cycle_substrate_context,
                candidate_simulation_handoff=candidate_simulation_handoff,
                producer_run_id=producer_run_id,
                producer_settlement_store=producer_settlement_store,
                call_observer=_observe_n4_call,
            )
        }
    recursive_graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=tuple(problems_by_node or ()),
        parent_child_edges=tuple((root_ref, child_ref) for child_ref in problems_by_node or ()),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    parent_joint_requests = _parent_joint_simulation_requests_by_node(root_ref, problem)
    parent_joint_candidate_selections: dict[str, object] = {}
    parent_joint_candidate_currentness: dict[str, object] = {}
    if joint_interaction_candidate_intent is not None:
        if any(
            key in problem.runtime_hints
            for key in (
                "joint_simulation_request",
                "joint_simulation_horizon",
                "joint_simulation_engine_plan",
                "joint_simulation_variable_map",
                "joint_simulation_baseline_state",
                "joint_simulation_comparator_refs",
                "joint_simulation_seed",
                "joint_simulation_replications",
                "joint_simulation_world_credal_state_before",
            )
        ):
            raise DesignProblemAuthorityError("joint_interaction_candidate_caller_axes_forbidden")
        if (
            generic_cycle_simulation_handoff is None
            or generic_cycle_simulation_admission_owner is None
            or n4_recursive_source is None
            or n4_recursive_source_ref is None
            or generic_n4_child_profile_status != "resolved"
            or n4_child_profile_set_ref is None
            or generation_source_repository is None
            or generic_cycle_simulation_currentness_resolver is None
        ):
            raise DesignProblemAuthorityError(
                "joint_interaction_candidate_parent_source_or_profile_not_established"
            )
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.design_generation import (
            derive_n4_candidate_child_problems,
        )

        parent_children = derive_n4_candidate_child_problems(
            problem,
            n4_recursive_source,
            model_id=model_name,
        )
        expected_child_node_refs = tuple(
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
            for child in parent_children
        )
        if (
            tuple(problems_by_node or ()) != expected_child_node_refs
            or len(parent_children) != len(expected_child_node_refs)
            or n4_recursive_source.status != "generated"
        ):
            raise DesignProblemAuthorityError(
                "joint_interaction_candidate_child_denominator_not_established"
            )
        selection, request = _build_parent_joint_candidate_request(
            candidate_intent=joint_interaction_candidate_intent,
            problem=problem,
            source_result=n4_recursive_source,
            source_ref=n4_recursive_source_ref,
            child_problems=parent_children,
            child_node_refs=expected_child_node_refs,
            model_id=model_name,
            handoff=generic_cycle_simulation_handoff,
            admission_owner=generic_cycle_simulation_admission_owner,
        )
        parent_joint_requests = {root_ref: request}
        parent_joint_candidate_selections = {root_ref: selection}
        parent_joint_candidate_currentness = {
            root_ref: generic_cycle_simulation_currentness_resolver
        }
    from polisyos.runtime.quality.generation_cycle import (
        _N4CandidateScenarioProposalOnlyError,
    )

    try:
        recursive_run = await resolved_controller.run(
            recursive_graph,
            problems_by_node={root_ref: problem, **(problems_by_node or {})},
            budget_state=budget_state,
            _producer_budget_reconciler=_producer_budget_reconciler,
            recursive_budget=recursive_budget,
            joint_simulation_requests_by_node=parent_joint_requests,
            joint_candidate_selections_by_node=parent_joint_candidate_selections,
            joint_candidate_currentness_resolvers_by_node=parent_joint_candidate_currentness,
            cycle_substrate_contexts_by_node=contexts_by_node
            or (
                {root_ref: cycle_substrate_context} if cycle_substrate_context is not None else None
            ),
            candidate_simulation_handoffs_by_node=handoffs_by_node
            or (
                {root_ref: candidate_simulation_handoff}
                if candidate_simulation_handoff is not None
                else None
            ),
            candidate_simulation_currentness_resolvers_by_node={}
            if handoffs_by_node
            else (
                {root_ref: candidate_simulation_currentness_resolver}
                if candidate_simulation_handoff is not None
                and candidate_simulation_currentness_resolver is not None
                else None
            ),
            n4_generation_ports_by_node=generation_ports_by_node
            or (
                {root_ref: root_n4_generation_port} if root_n4_generation_port is not None else None
            ),
            evaluation_contexts_by_node=None
            if handoffs_by_node
            else (
                {root_ref: root_evaluation_context} if root_evaluation_context is not None else None
            ),
            execution_intents_by_node=dict.fromkeys(
                problems_by_node or (root_ref,), execution_intent
            ),
            leaf_context_owner=recursive_leaf_context_owner,
            generic_simulation_handoffs_by_node=generic_handoffs_by_node,
            generic_n4_child_profile_set_ref=n4_child_profile_set_ref
            if generic_handoffs_by_node
            else None,
            generic_n4_source_repository=generation_source_repository
            if generic_handoffs_by_node
            else None,
            generic_parent_handoff=generic_cycle_simulation_handoff
            if generic_handoffs_by_node
            else None,
        )
    except _N4CandidateScenarioProposalOnlyError as signal:
        return N4CandidateScenarioProposalOnlyExecution(
            design_problem=problem,
            source_ref=signal.source_ref,
            limitation_code=signal.limitation_code,
        )
    limitations: list[OpenWorldRiskPublicLimitation] = []
    if isinstance(recursive_run, RecursiveGenerationCycleRun):
        seen_vector_refs: set[str] = set()
        from polisyos.runtime.quality.generation_cycle import (
            GenerationCycleError,
            eligible_n9_source_for_run,
        )

        for leaf in recursive_run.leaf_nodes:
            cycle_run = leaf.cycle_run
            if cycle_run is None:  # pragma: no cover - enforced by RecursiveCycleNode
                continue
            if cycle_run.promotion_port.reason == (
                "epoch_validity_refused:policy_admission_missing"
            ):
                for limitation in project_pre_n9_open_world_limitations(
                    run=cycle_run,
                    design_problem=problem,
                    resolver=promotion_runtime.resolver,
                    repo_root=repo_root,
                ):
                    vector_key = str(limitation.vector_artifact_ref.artifact_id)
                    if vector_key in seen_vector_refs:
                        raise PublicExportRedactionError("open_world_projection_duplicate")
                    seen_vector_refs.add(vector_key)
                    limitations.append(limitation)
            try:
                n9_source = eligible_n9_source_for_run(cycle_run)
            except GenerationCycleError as exc:
                raise PublicExportRedactionError(
                    exc.code,
                    str(exc),
                ) from exc
            if n9_source is None:
                if cycle_run.promotion_port.receipts:
                    raise PublicExportRedactionError(
                        "generation_cycle_blocked_before_n9_cannot_supply_receipt"
                    )
                continue
            for receipt_payload in n9_source.promotion_port.receipts:
                try:
                    receipt = CanonicalPromotionReceipt.model_validate(receipt_payload)
                except ValueError as exc:
                    raise PublicExportRedactionError(
                        "promotion_receipt_invalid",
                        str(exc),
                    ) from exc
                if promotion_runtime is None:
                    raise PublicExportRedactionError("open_world_resolver_not_established")
                limitation = project_promotion_open_world_limitation(
                    run=cycle_run,
                    design_problem=problem,
                    receipt=receipt,
                    resolver=promotion_runtime.resolver,
                    repo_root=repo_root,
                    n9_source=n9_source,
                )
                if limitation is None:
                    continue
                vector_key = str(limitation.vector_artifact_ref.artifact_id)
                if vector_key in seen_vector_refs:
                    raise PublicExportRedactionError("open_world_projection_duplicate")
                seen_vector_refs.add(vector_key)
                limitations.append(limitation)
    recursive_run_payload = recursive_run.model_dump(
        mode="json",
        exclude={"leaf_nodes"},
    )
    payload = {
        "schema_version": (
            COMPILED_RECURSIVE_GENERATION_CYCLE_CREDAL_SOURCE_ATTEMPT_SCHEMA_VERSION
            if n4_credal_source_attempt_ref is not None
            else COMPILED_RECURSIVE_GENERATION_CYCLE_GENERIC_PROFILE_SCHEMA_VERSION
            if (
                generic_cycle_simulation_handoff is not None
                or generic_n4_child_profile_status != "not_attempted"
                or n4_child_profile_set_ref is not None
            )
            else COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION
            if (
                nl_preflight_cost_events
                or n4_generation_cost_events
                or n4_recursive_source_ref is not None
                or n4_child_profile_status != "not_attempted"
            )
            else COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION
            if isinstance(recursive_run, RecursiveGenerationCyclePartialRunV3)
            else COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION
            if isinstance(recursive_run, RecursiveGenerationCyclePartialRunV2)
            else COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
        ),
        "design_problem_ref": problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": (
            cycle_substrate_context.content_hash if cycle_substrate_context is not None else None
        ),
        "recursive_run": recursive_run_payload,
    }
    if nl_preflight_cost_events:
        payload["nl_preflight_cost_events"] = [
            event.model_dump(mode="json") for event in nl_preflight_cost_events
        ]
    if n4_generation_cost_events:
        payload["n4_generation_cost_events"] = [
            event.model_dump(mode="json") for event in n4_generation_cost_events
        ]
    if n4_recursive_source_ref is not None:
        payload.update(
            {
                "n4_recursive_source_ref": n4_recursive_source_ref.model_dump(mode="json"),
                "n4_recursive_source_job_id": n4_recursive_source_job_id,
                "n4_recursive_source_run_id": n4_recursive_source_run_id,
                "n4_recursive_source_tenant_id": n4_recursive_source_tenant_id,
                "n4_recursive_source_cell_id": n4_recursive_source_cell_id,
                "n4_recursive_source_context_job_ref": (
                    n4_recursive_source_context_job_ref.model_dump(mode="json")
                    if n4_recursive_source_context_job_ref is not None
                    else None
                ),
                "n4_recursive_source_profile_config_ref": (n4_recursive_source_profile_config_ref),
                "n4_recursive_source_profile_selection_ref": (
                    n4_recursive_source_profile_selection_ref
                ),
                "n4_recursive_source_result_status": n4_recursive_source_result_status,
            }
        )
    if n4_child_profile_status != "not_attempted":
        payload["n4_child_profile_status"] = n4_child_profile_status
    if n4_child_profile_bindings:
        payload["n4_child_profile_bindings"] = [
            row.model_dump(mode="json") for row in n4_child_profile_bindings
        ]
    if n4_child_profile_limitation_code is not None:
        payload["n4_child_profile_limitation_code"] = n4_child_profile_limitation_code
    if generic_cycle_simulation_handoff is not None:
        payload["generic_cycle_simulation_handoff"] = generic_cycle_simulation_handoff.model_dump(
            mode="json"
        )
    if generic_n4_child_profile_status != "not_attempted":
        payload["generic_n4_child_profile_status"] = generic_n4_child_profile_status
    if n4_child_profile_set_ref is not None:
        payload["n4_child_profile_set_ref"] = n4_child_profile_set_ref.model_dump(mode="json")
    if n4_credal_source_attempt_ref is not None:
        payload["n4_credal_source_attempt_ref"] = n4_credal_source_attempt_ref.model_dump(
            mode="json"
        )
    if generic_n4_child_profile_limitation_code is not None:
        payload["generic_n4_child_profile_limitation_code"] = (
            generic_n4_child_profile_limitation_code
        )
    if recursive_budget_resolution is not None:
        payload["recursive_budget_resolution"] = recursive_budget_resolution.model_dump(mode="json")
    if limitations:
        payload["open_world_risk_limitations"] = tuple(
            row.model_dump(mode="json") for row in limitations
        )
    return CompiledRecursiveGenerationCycleRun.model_validate(
        {
            **payload,
            # Preserve the live recursive object so its leaf simulation keeps
            # the exact owner WMR internal provenance handle.  The JSON
            # projection above remains the content-hash/public-artifact view.
            "recursive_run": recursive_run,
            "recursive_budget_resolution": recursive_budget_resolution,
            "nl_preflight_cost_events": tuple(nl_preflight_cost_events),
            "n4_generation_cost_events": tuple(n4_generation_cost_events),
            "n4_recursive_source_ref": n4_recursive_source_ref,
            "n4_recursive_source_job_id": n4_recursive_source_job_id,
            "n4_recursive_source_run_id": n4_recursive_source_run_id,
            "n4_recursive_source_tenant_id": n4_recursive_source_tenant_id,
            "n4_recursive_source_cell_id": n4_recursive_source_cell_id,
            "n4_recursive_source_context_job_ref": (n4_recursive_source_context_job_ref),
            "n4_recursive_source_profile_config_ref": (n4_recursive_source_profile_config_ref),
            "n4_recursive_source_profile_selection_ref": (
                n4_recursive_source_profile_selection_ref
            ),
            "n4_recursive_source_result_status": n4_recursive_source_result_status,
            "n4_child_profile_status": n4_child_profile_status,
            "n4_child_profile_bindings": n4_child_profile_bindings,
            "n4_child_profile_limitation_code": n4_child_profile_limitation_code,
            "generic_cycle_simulation_handoff": generic_cycle_simulation_handoff,
            "generic_n4_child_profile_status": generic_n4_child_profile_status,
            "n4_child_profile_set_ref": n4_child_profile_set_ref,
            **(
                {"n4_credal_source_attempt_ref": n4_credal_source_attempt_ref}
                if n4_credal_source_attempt_ref is not None
                else {}
            ),
            "generic_n4_child_profile_limitation_code": (generic_n4_child_profile_limitation_code),
            "content_hash": gy_content_hash(payload),
        }
    )


@dataclass(frozen=True, slots=True)
class _TargetWorldScopeProfileSelection:
    """Carry selector status separately from an owner-bound cycle context."""

    target_world_scope_profile_id: str | None
    status: Literal[
        "profile_not_requested",
        "profile_admission_missing",
    ]


def _classify_target_world_scope_profile(
    target_world_scope_profile_id: str | None,
) -> _TargetWorldScopeProfileSelection:
    """Classify selector presence without inferring scope or authority.

    No authoritative profile registry/admission exists at this owner boundary.
    Any supplied selector remains unadmitted and cannot select a repo-root WMR.
    """

    status: Literal[
        "profile_not_requested",
        "profile_admission_missing",
    ]
    if target_world_scope_profile_id is None:
        status = "profile_not_requested"
    else:
        status = "profile_admission_missing"
    return _TargetWorldScopeProfileSelection(
        target_world_scope_profile_id=target_world_scope_profile_id,
        status=status,
    )


__all__ = [
    "COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION",
    "COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION",
    "COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION",
    "COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION",
    "CompiledRecursiveGenerationCycleRun",
    "N4CandidateProposalExecution",
    "compile_and_run_recursive_generation_cycle",
]
