"""Public decide policy runtime support module API."""

from __future__ import annotations

import math
from collections.abc import Buffer, Iterable, Mapping
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NamedTuple,
    Protocol,
    SupportsFloat,
    SupportsIndex,
    TypeGuard,
    cast,
)

from pydantic import BaseModel

from polisyos.core import components as core_components
from polisyos.core.artifacts import (
    ArtifactStore,
    CoreJSONArtifactStore,
    CoreJSONArtifactStreamingReader,
    RootedArtifactStore,
    matches_runtime_protocol,
    matches_runtime_protocol_definition,
)
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.scientist import DiscoveryArtifactBundleRef
from polisyos.foundry.methods.catalog.optimization.protocols import AmbiguityCertificate
from polisyos.foundry.validation import normalize_phase2_artifact_family
from polisyos.ir.analytics.causal import CausalEffectReport, load_data_readiness_report
from polisyos.ir.analytics.causal_discovery import LatentDiscoveryBundle
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
)
from polisyos.ir.analytics.distributional import (
    DistributionalReport,
)
from polisyos.ir.registry import DataReadinessReportRef
from polisyos.pdc import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyVerifierPort,
    EvaluationExecutionContext,
    WorldModelRecord,
    evaluation_safety_consumer_admission_is_verified,
    gy_content_hash,
    world_model_record_content_hash,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.discovery.priors import (
    PriorKnowledgeBundle,
)
from polisyos.scientist.methods.search.adversarial import load_platform_meta_evaluation_report
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket, FunnelOutcome
from polisyos.scientist.methods.search.judge_stack import (
    PolicyPromotionCoordinator,
    PolicyPromotionResult,
)
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    _PhaseD4ChallengeSourceBasis,
    _PolicyRuntimeSelectionSourceBasis,
)
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_artifacts as _runtime_artifacts,
)
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_method_metrics as _runtime_method_metrics,
)
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_metrics as _runtime_metrics,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    CompletedMethodMetricProjectionReadResult,
    CompletedMethodMetricSelectionOwner,
    MethodExecutionSelectionOwner,
    MethodMetricProjectionReadResult,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CHAMPION_POLICY_DOSSIER_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONSTRAINT_SATISFACTION_REPORT_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_GOVERNANCE_GATE_PACKET_REF,
    ARTIFACT_IMPLEMENTATION_PLAN_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_POLICY_FRONTIER_REPORT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_POLICY_TRANSPORTABILITY_REPORT_REF,
    ARTIFACT_POLICY_UNCERTAINTY_REPORT_REF,
    ARTIFACT_REJECTED_ALTERNATIVES_SUMMARY_REF,
    ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF,
    ARTIFACT_SUBGROUP_IMPACT_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    _direct_mutation_journal_for_state,
    branch_state,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.phase3 import resolve_phase3_gate
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
)
from polisyos.scientist.replay.verification import (
    ReplayRegistry,
    load_replay_verification_report,
    verify_and_persist_replay_bundle,
)

_POLICY_RUNTIME_VALIDATION_ERRORS = _runtime_metrics._POLICY_RUNTIME_VALIDATION_ERRORS
_POLICY_RUNTIME_LOAD_ERRORS = _runtime_metrics._POLICY_RUNTIME_LOAD_ERRORS
_EVAL_SAFETY_BLOCKER_PREFIX = "polisyos.eval_safety"

_CURRENT_POLICY_PROMOTION_PARAM_KEYS = (
    "policy_promotion_result",
    "judge_verdict",
    "decision_readiness_contract",
    "promotion_decision",
    "policy_promotion_projection_status",
    "policy_brief",
    "translator_compliance",
)

_CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS = (
    ARTIFACT_CHAMPION_POLICY_DOSSIER_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONSTRAINT_SATISFACTION_REPORT_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_GOVERNANCE_GATE_PACKET_REF,
    ARTIFACT_IMPLEMENTATION_PLAN_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_POLICY_FRONTIER_REPORT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_POLICY_TRANSPORTABILITY_REPORT_REF,
    ARTIFACT_POLICY_UNCERTAINTY_REPORT_REF,
    ARTIFACT_REJECTED_ALTERNATIVES_SUMMARY_REF,
    ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF,
    ARTIFACT_SUBGROUP_IMPACT_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
)


_CURRENT_POLICY_STATE_REF_FIELDS = (
    "policy_output_bundle_ref",
    "policy_brief_ref",
    "champion_policy_dossier_ref",
)
_CURRENT_POLICY_PROJECTION_WRITE_PATHS = (
    *(f"params.{key}" for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS),
    "params.reported_policy_promotion_history",
    *_CURRENT_POLICY_STATE_REF_FIELDS,
    *(f"artifacts_index.{key}" for key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS),
    "reports_index.governance_report_ref",
    "params.reported_governance_report_history",
)


def clear_current_policy_promotion_projection(state: ExperimentState) -> None:
    """Clear the current policy promotion surface without deleting its CAS artifacts."""
    for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS:
        state.params.pop(key, None)
    for key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS:
        state.artifacts_index.pop(key, None)
    state.policy_output_bundle_ref = None
    state.policy_brief_ref = None
    state.champion_policy_dossier_ref = None


def project_policy_promotion_state(
    state: ExperimentState,
    *,
    preserved_state_refs: Mapping[str, ArtifactRef] | None = None,
    preserved_artifact_refs: Mapping[str, ArtifactRef] | None = None,
    archive_prior: bool = True,
    ctx: ExecutionContext | None = None,
    branch_write_paths: Iterable[str] | None = None,
) -> ExperimentState:
    """Project policy-mode promotion inputs as report-only before a direct consumer.

    Persisted candidate-only bundles may be supplied through the preserved-ref maps only
    after the caller has recomputed their complete candidate, run, and input binding.
    A producer that continues writing after projection may pass its declared parent write
    paths; the nested branch still validates that grant against the active producer scope.
    With no explicit grant, an active enforced root journal keeps its exact path set; ordinary
    inputs retain the narrow projection scope.
    """
    if not _is_policy_mode_state(state):
        return state
    parent_journal = _direct_mutation_journal_for_state(state)
    if branch_write_paths is not None:
        projection_write_paths = branch_write_paths
    elif parent_journal is not None and parent_journal.enforce_write_scope:
        projection_write_paths = parent_journal.isolated_paths
    else:
        projection_write_paths = _CURRENT_POLICY_PROJECTION_WRITE_PATHS
    projected = branch_state(state, write_paths=projection_write_paths).state
    previous_status = state.params.get("policy_promotion_projection_status")
    from polisyos.scientist.governance.report_currentness import (
        resolve_current_governance_report,
    )

    governance_report_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
    governance_report_admission = (
        resolve_current_governance_report(ctx, state, governance_report_ref)
        if ctx is not None and governance_report_ref is not None
        else None
    )
    governance_report_is_current = bool(
        governance_report_admission is not None and governance_report_admission.is_current
    )
    safe_status = _reported_only_policy_projection_status(previous_status)
    prior_params = {
        key: _policy_projection_json_value(state.params[key])
        for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS
        if key in state.params and key != "policy_promotion_projection_status"
    }
    prior_refs: dict[str, Any] = {}
    preserved_state_refs = preserved_state_refs or {}
    preserved_artifact_refs = preserved_artifact_refs or {}
    state_refs = {
        key: _policy_projection_json_value(getattr(state, key))
        for key in _CURRENT_POLICY_STATE_REF_FIELDS
        if getattr(state, key) is not None and key not in preserved_state_refs
    }
    artifact_refs = {
        key: _policy_projection_json_value(value)
        for key, value in state.artifacts_index.items()
        if key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS and key not in preserved_artifact_refs
    }
    if state_refs:
        prior_refs["state"] = state_refs
    if artifact_refs:
        prior_refs["artifacts_index"] = artifact_refs
    if not safe_status and previous_status is not None:
        prior_params["policy_promotion_projection_status"] = _policy_projection_json_value(
            previous_status
        )

    raw_history = state.params.get("reported_policy_promotion_history")
    if isinstance(raw_history, list):
        history_items = list(raw_history)
    elif "reported_policy_promotion_history" in state.params:
        history_items = [
            {
                "record_type": "unparsed_prior_history",
                "value": _policy_projection_json_value(raw_history),
            }
        ]
    else:
        history_items = []
    raw_governance_history = state.params.get("reported_governance_report_history")
    if isinstance(raw_governance_history, list):
        governance_history_items = list(raw_governance_history)
    elif "reported_governance_report_history" in state.params:
        governance_history_items = [
            {
                "record_type": "unparsed_prior_governance_report_history",
                "value": _policy_projection_json_value(raw_governance_history),
            }
        ]
    else:
        governance_history_items = []
    prior_governance_report = None
    if governance_report_ref is not None and not governance_report_is_current:
        prior_governance_report = {
            "record_type": "reported_governance_report",
            "run_id": state.run_id,
            "status": (
                governance_report_admission.status
                if governance_report_admission is not None
                else "not_established"
            ),
            "reason_code": (
                governance_report_admission.reason_code
                if governance_report_admission is not None
                else "governance_report_currentness_context_missing"
            ),
            "artifact_ref": _policy_projection_json_value(governance_report_ref),
        }
    if archive_prior and (prior_params or prior_refs):
        history_items.append(
            {
                "record_type": "prior_current_projection",
                "run_id": state.run_id,
                "params": prior_params,
                "refs": prior_refs,
            }
        )

    clear_current_policy_promotion_projection(projected)
    if governance_report_ref is not None and not governance_report_is_current:
        projected.reports_index.pop(REPORT_GOVERNANCE_REPORT_REF, None)
        if prior_governance_report is not None:
            governance_history_items.append(prior_governance_report)
    if (
        archive_prior and (prior_params or prior_refs)
    ) or "reported_policy_promotion_history" in state.params:
        projected.params["reported_policy_promotion_history"] = history_items
    if (
        archive_prior and prior_governance_report is not None
    ) or "reported_governance_report_history" in state.params:
        projected.params["reported_governance_report_history"] = governance_history_items
    for key, ref in preserved_state_refs.items():
        if key in _CURRENT_POLICY_STATE_REF_FIELDS:
            setattr(projected, key, ref)
    for key, ref in preserved_artifact_refs.items():
        if key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS:
            projected.artifacts_index[key] = ref
    if safe_status and not prior_params and not prior_refs:
        projected.params["policy_promotion_projection_status"] = _policy_projection_json_value(
            previous_status
        )
    else:
        projected.params["policy_promotion_projection_status"] = {
            "schema_version": "1.0",
            "status": "reported_only",
            "authority_status": "not_established",
            "reason": "protected_owner_receipt_not_established",
            "run_id": state.run_id,
            "source": "direct_policy_current_state_projection",
        }
    return projected


def _is_policy_mode_state(state: ExperimentState) -> bool:
    workflow_id = str(state.params.get("workflow_id") or "").strip().lower()
    if workflow_id == "scientist_policy_design":
        return True
    raw = state.params.get("policy_mode")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _reported_only_policy_projection_status(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("status") == "reported_only"
        and value.get("authority_status") == "not_established"
    )


def _policy_projection_json_value(value: Any) -> Any:
    """Retain prior projection input as finite JSON without promoting its meaning."""
    if value is None or type(value) in {str, bool, int}:
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"non_finite_float": repr(value)}
    if isinstance(value, BaseModel):
        return _policy_projection_json_value(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _policy_projection_json_value(
            {field.name: getattr(value, field.name) for field in fields(value)}
        )
    if isinstance(value, Mapping):
        return {str(key): _policy_projection_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_policy_projection_json_value(item) for item in value]
    return {
        "unprojected_type": f"{type(value).__module__}.{type(value).__qualname__}",
        "repr": repr(value),
    }


if TYPE_CHECKING:

    def _is_core_json_artifact_store(store: object) -> TypeGuard[CoreJSONArtifactStore]: ...

else:

    def _is_core_json_artifact_store(store: object) -> bool:
        return matches_runtime_protocol(store, CoreJSONArtifactStore)


def _require_policy_runtime_registry_root(
    store: ArtifactStore,
    *,
    error_code: str = "policy_runtime_registry_root_unavailable",
) -> Path:
    """Capture the typed backing root once for local registry operations."""
    if not matches_runtime_protocol_definition(store, ArtifactStore):
        raise ValueError(error_code)
    try:
        root = cast("RootedArtifactStore", store).root
    except AttributeError as exc:
        raise ValueError(error_code) from exc
    if not isinstance(root, Path):
        raise ValueError(error_code)
    return root


def _require_policy_runtime_store(
    store: ArtifactStore,
    *,
    error_code: str = "policy_runtime_registry_root_unavailable",
) -> tuple[CoreJSONArtifactStore, Path]:
    """Require the protected store and capture its registry root once."""
    registry_root = _require_policy_runtime_registry_root(store, error_code=error_code)
    if not _is_core_json_artifact_store(store):
        raise ValueError(error_code)
    return store, registry_root


def _parse_policy_claim_mode(value: object) -> Literal["proof_only", "bounds", "estimation"]:
    """Return an admitted policy claim mode without filling missing intent."""
    if not isinstance(value, str):
        raise ValueError("promotion_benchmark_scope_unavailable")
    normalized = value.strip().lower()
    if normalized == "proof_only":
        return "proof_only"
    if normalized == "bounds":
        return "bounds"
    if normalized == "estimation":
        return "estimation"
    raise ValueError("promotion_benchmark_scope_unavailable")


class _PolicyRuntimeNumericInputs(NamedTuple):
    """Optional measurements consumed by policy runtime promotion."""

    compute_cost_usd: float | None
    replay_cost_usd: float | None
    timeout_risk: float | None


def _optional_runtime_number(value: object) -> float | None:
    """Parse one optional finite numeric measurement without defaulting absence."""
    if value is None:
        return None
    if not isinstance(value, (str, Buffer, SupportsFloat, SupportsIndex)):
        raise TypeError("runtime numeric input must be float-convertible")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("runtime numeric input must be finite")
    return result


def _policy_runtime_numeric_inputs(state: ExperimentState) -> _PolicyRuntimeNumericInputs:
    """Preserve absence and parse all optional promotion measurements centrally."""
    return _PolicyRuntimeNumericInputs(
        compute_cost_usd=_optional_runtime_number(state.params.get("estimated_compute_cost_usd")),
        replay_cost_usd=_optional_runtime_number(state.params.get("estimated_replay_cost_usd")),
        timeout_risk=_optional_runtime_number(state.params.get("timeout_risk")),
    )


def _eval_safety_blocker(name: str) -> str:
    return f"{_EVAL_SAFETY_BLOCKER_PREFIX}.{name}@1.0.0"


PRODUCTION_POLICY_EVALUATION_BACKEND_ID = core_components.ComponentId.parse(
    "scientist.production_policy_evaluation_backend@1.0.0"
)


class PolicyRuntimeEvaluationSafetyError(RuntimeError):
    """Raised when direct production evaluation lacks exact safety admission."""

    def __init__(self, blocker_codes: tuple[str, ...]) -> None:
        self.blocker_codes = blocker_codes
        super().__init__(
            "Attempted-evaluation safety admission blocked policy runtime evaluation: "
            + ", ".join(blocker_codes)
        )


@dataclass(frozen=True)
class PolicyRuntimeProvenance:
    """Policy runtime provenance public type."""

    backend_kind: str
    fidelity_mode: str
    promotable_source: bool
    degradation_mode: str | None = None
    source_components: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyRuntimeEvaluationArtifact:
    """Policy runtime evaluation artifact public type."""

    simulation_metrics: dict[str, float]
    simulation_results: dict[str, Any]
    evaluation_vector: PolicyEvaluationVector
    fidelity: str
    provenance: PolicyRuntimeProvenance
    completed_projection_binding: object | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class LatentDiscoveryBundleResolution:
    """Latent discovery bundle resolution public type."""

    bundle: LatentDiscoveryBundle | None
    status: Literal["ok", "missing", "unreadable"] = "missing"
    source_bundle_ref: DiscoveryArtifactBundleRef | None = None
    error_code: str | None = None
    error_message: str | None = None

    def error_payload(self) -> dict[str, Any] | None:
        if self.status != "unreadable":
            return None
        payload: dict[str, Any] = {
            "status": self.status,
            "error_code": self.error_code or "latent_discovery_bundle_unreadable",
            "error_message": (self.error_message or "latent discovery bundle could not be loaded"),
        }
        if self.source_bundle_ref is not None:
            payload["source_bundle_ref"] = self.source_bundle_ref.model_dump(mode="json")
        return payload


class PolicyEvaluationBackend(Protocol):
    """Policy evaluation backend implementation."""

    backend_kind: str

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: UncertaintyEnvelope | None,
        distributional_report: DistributionalReport | None,
        causal_effect_report: CausalEffectReport | None,
        cross_graph_profile: CrossGraphEvidenceProfile | None,
        governance_report: GovernanceReport | None,
        ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
        evaluation_attempt_id: str | None = None,
        effective_estimation_config: Mapping[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact: ...


def _policy_runtime_input_hash(value: object) -> str:
    model_dump = getattr(value, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else value
    return gy_content_hash(payload)


def _production_policy_evaluation_safety_blockers(
    *,
    context: EvaluationExecutionContext | None,
    verifier: EvalSafetyVerifierPort | None,
    world_model_record: WorldModelRecord | None,
    candidate: PolicyCandidateSchema,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None,
) -> tuple[str, ...]:
    return _runtime_artifacts._production_policy_evaluation_safety_blockers_impl(
        context=context,
        verifier=verifier,
        world_model_record=world_model_record,
        candidate=candidate,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
        ambiguity_certificate=ambiguity_certificate,
        blocker_fn=_eval_safety_blocker,
        input_hash_fn=_policy_runtime_input_hash,
        production_owner_component_id=PRODUCTION_POLICY_EVALUATION_BACKEND_ID,
        world_model_record_content_hash_fn=world_model_record_content_hash,
        challenge_factory=EvalSafetyAdmissionChallenge,
        admission_check=evaluation_safety_consumer_admission_is_verified,
    )


class _MethodMetricProjectionCapabilitySlot:
    """Non-serializable storage reserved for one in-process admission capability."""

    __slots__ = (
        "_policyos_completed_evaluation_bindings",
        "_policyos_completed_work_bindings",
        "_policyos_method_metric_projection_basis",
        "_policyos_method_metric_projection_candidate_ref",
    )


@dataclass(frozen=True, slots=True)
class ProductionPolicyEvaluationBackend(_MethodMetricProjectionCapabilitySlot):
    """Production policy evaluation backend implementation."""

    eval_safety_execution_context: EvaluationExecutionContext | None = None
    eval_safety_verifier: EvalSafetyVerifierPort | None = None
    world_model_record: WorldModelRecord | None = None
    backend_kind: str = "production"

    def __post_init__(self) -> None:
        object.__setattr__(self, "_policyos_completed_evaluation_bindings", ())
        object.__setattr__(self, "_policyos_completed_work_bindings", ())
        object.__setattr__(self, "_policyos_method_metric_projection_basis", None)
        object.__setattr__(self, "_policyos_method_metric_projection_candidate_ref", None)

    def __copy__(self) -> ProductionPolicyEvaluationBackend:
        """Copy public configuration without carrying an owner-issued capability."""
        return replace(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> ProductionPolicyEvaluationBackend:
        """Deep-copy public configuration without carrying an owner-issued capability."""
        duplicate = replace(self)
        memo[id(self)] = duplicate
        return duplicate

    def __reduce_ex__(self, protocol: int) -> tuple[Any, tuple[Any, ...]]:
        """Serialize only ordinary backend configuration, never ephemeral admission."""
        del protocol
        return (
            type(self),
            (
                self.eval_safety_execution_context,
                self.eval_safety_verifier,
                self.world_model_record,
                self.backend_kind,
            ),
        )

    def with_method_metric_projection_basis(
        self,
        *,
        basis: object | None,
        candidate_ref: ArtifactRef | None,
    ) -> ProductionPolicyEvaluationBackend:
        """Bind one in-process owner basis outside dataclass and serialization fields."""
        if basis is None and candidate_ref is not None:
            raise ValueError("method_metric_projection_candidate_ref_without_basis")
        if basis is not None and candidate_ref is None:
            raise ValueError("method_metric_projection_candidate_ref_missing")
        object.__setattr__(self, "_policyos_completed_evaluation_bindings", ())
        object.__setattr__(self, "_policyos_completed_work_bindings", ())
        object.__setattr__(self, "_policyos_method_metric_projection_basis", basis)
        object.__setattr__(self, "_policyos_method_metric_projection_candidate_ref", candidate_ref)
        return self

    def bind_completed_work_packet(
        self,
        *,
        store: object,
        packet_ref: ArtifactRef,
        evaluation: PolicyEvaluationVector,
        candidate_ref: ArtifactRef,
        run_id: str,
        ticket_id: str,
        candidate_hash: str,
        attempt_id: str,
        fidelity: str,
        _record: bool = True,
    ) -> None:
        """Bind a packet emitted by this live backend to its actual evaluation."""
        from polisyos.core.artifacts.canonical_profile import (
            CoreJsonReadLimits,
            read_core_json_artifact_bounded,
            read_core_manifest_profile_bounded,
            validate_core_model_bounded_read,
        )
        from polisyos.core.artifacts.manifest import artifact_ref_identity_key

        matching = [
            item
            for item in self._policyos_completed_evaluation_bindings
            if _runtime_method_metrics._completed_projection_evaluation_binding_matches(
                item, evaluation=evaluation, candidate_ref=candidate_ref
            )
        ]
        if (
            len(matching) != 1
            or type(packet_ref) is not ArtifactRef
            or not packet_ref.manifest_profile_sha256
        ):
            raise ValueError("completed_projection_work_binding_unavailable")
        limits = CoreJsonReadLimits(
            max_bytes=8 * 1024 * 1024,
            max_depth=128,
            max_elements=1000000,
            max_manifest_bytes=16 * 1024 * 1024,
        )
        mr = read_core_manifest_profile_bounded(
            store, packet_ref, max_manifest_bytes=limits.max_manifest_bytes
        )
        manifest = mr.manifest
        schema = manifest.artifact_schema
        if (
            manifest.kind,
            manifest.media_type,
            schema.name if schema else None,
            schema.version if schema else None,
        ) != (
            "scientist.search.funnel_native_work_packet",
            "application/json",
            "polisyos.scientist.search.FunnelExecutedWorkPacket",
            "1.1",
        ):
            raise ValueError("completed_projection_work_packet_schema_invalid")
        packet = validate_core_model_bounded_read(
            FunnelExecutedWorkPacket,
            read_core_json_artifact_bounded(store, packet_ref, limits=limits, manifest_read=mr),
        )
        if (
            packet.run_id != run_id
            or packet.ticket_id != ticket_id
            or packet.candidate_hash != candidate_hash
            or packet.evaluation_attempt_id != attempt_id
            or packet.fidelity != fidelity
            or artifact_ref_identity_key(packet.candidate_ref)
            != artifact_ref_identity_key(candidate_ref)
        ):
            raise ValueError("completed_projection_work_packet_identity_mismatch")
        expected = {
            "candidate": (str(candidate_ref.artifact_id), candidate_ref.manifest_profile_sha256),
            "source_result": (
                str(packet.source_result_ref.artifact_id),
                packet.source_result_ref.manifest_profile_sha256,
            ),
        }
        actual = {
            edge.role: (str(edge.artifact_id), edge.manifest_profile_sha256)
            for edge in manifest.inputs
        }
        if len(manifest.inputs) != 2 or actual != expected:
            raise ValueError("completed_projection_work_packet_inputs_mismatch")
        result_mr = read_core_manifest_profile_bounded(
            store, packet.source_result_ref, max_manifest_bytes=limits.max_manifest_bytes
        )
        result_schema = result_mr.manifest.artifact_schema
        if (
            result_mr.manifest.kind,
            result_schema.name if result_schema else None,
            result_schema.version if result_schema else None,
        ) != (
            "scientist.policy_evaluation_vector",
            "polisyos.scientist.policy_design.PolicyEvaluationVector",
            "1.3",
        ):
            raise ValueError("completed_projection_work_result_schema_invalid")
        result = validate_core_model_bounded_read(
            PolicyEvaluationVector,
            read_core_json_artifact_bounded(
                store, packet.source_result_ref, limits=limits, manifest_read=result_mr
            ),
        )
        if result.model_dump(mode="json") != evaluation.model_dump(mode="json"):
            raise ValueError("completed_projection_work_result_mismatch")
        if not _record:
            return
        record = (
            matching[0],
            artifact_ref_identity_key(packet_ref),
            ticket_id,
            candidate_hash,
            store,
            run_id,
            attempt_id,
            fidelity,
        )
        if len(self._policyos_completed_work_bindings) >= 256:
            raise ValueError("completed_projection_live_binding_limit")
        object.__setattr__(
            self,
            "_policyos_completed_work_bindings",
            (*self._policyos_completed_work_bindings, record),
        )

    def select_completed_evaluation_binding(
        self,
        *,
        evaluation: PolicyEvaluationVector,
        candidate_ref: ArtifactRef,
        packet_ref: ArtifactRef | None,
        ticket_id: str | None,
        candidate_hash: str | None,
    ) -> object | None:
        """Select an actual bound packet/result for this ticket and live backend."""
        from polisyos.core.artifacts.manifest import artifact_ref_identity_key

        if (
            type(packet_ref) is not ArtifactRef
            or not packet_ref.manifest_profile_sha256
            or not ticket_id
            or not candidate_hash
        ):
            return None
        matches = [
            record
            for record in self._policyos_completed_work_bindings
            for binding, packet_key, bound_ticket, bound_hash, _store, _run, _attempt, _fidelity in (
                record,
            )
            if packet_key == artifact_ref_identity_key(packet_ref)
            and bound_ticket == ticket_id
            and bound_hash == candidate_hash
            and _runtime_method_metrics._completed_projection_evaluation_binding_matches(
                binding, evaluation=evaluation, candidate_ref=candidate_ref
            )
        ]
        if len(matches) > 1:
            raise ValueError("completed_projection_live_binding_ambiguous")
        if not matches:
            return None
        binding, _key, _ticket, _hash, store, run_id, attempt_id, fidelity = matches[0]
        self.bind_completed_work_packet(
            store=store,
            packet_ref=packet_ref,
            evaluation=evaluation,
            candidate_ref=candidate_ref,
            run_id=run_id,
            ticket_id=ticket_id,
            candidate_hash=candidate_hash,
            attempt_id=attempt_id,
            fidelity=fidelity,
            _record=False,
        )
        return binding

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: UncertaintyEnvelope | None,
        distributional_report: DistributionalReport | None,
        causal_effect_report: CausalEffectReport | None,
        cross_graph_profile: CrossGraphEvidenceProfile | None,
        governance_report: GovernanceReport | None,
        ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
        evaluation_attempt_id: str | None = None,
        effective_estimation_config: Mapping[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact:
        runtime_execution = _runtime_metrics._policy_runtime_execution_metadata(
            evaluation_attempt_id=evaluation_attempt_id,
            effective_estimation_config=effective_estimation_config,
        )
        safety_blockers = _production_policy_evaluation_safety_blockers(
            context=self.eval_safety_execution_context,
            verifier=self.eval_safety_verifier,
            world_model_record=self.world_model_record,
            candidate=candidate,
            simulation_metrics=simulation_metrics,
            uncertainty=uncertainty,
            distributional_report=distributional_report,
            causal_effect_report=causal_effect_report,
            cross_graph_profile=cross_graph_profile,
            governance_report=governance_report,
            ambiguity_certificate=ambiguity_certificate,
        )
        if safety_blockers:
            raise PolicyRuntimeEvaluationSafetyError(safety_blockers)

        metrics, source_components, notes = _build_evidence_driven_simulation_metrics(
            candidate,
            fidelity=fidelity,
            simulation_metrics=simulation_metrics,
            uncertainty=uncertainty,
            distributional_report=distributional_report,
            causal_effect_report=causal_effect_report,
            cross_graph_profile=cross_graph_profile,
            governance_report=governance_report,
        )
        source_components_list = list(source_components)
        if ambiguity_certificate is not None:
            source_components_list.append("ambiguity_certificate")
        fiscal_measurement = _runtime_metrics._budget_deficit_measurement(metrics)
        evaluation_vector = ObjectiveStack().evaluate(
            PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=distributional_report,
                causal_effect_report=causal_effect_report,
                cross_graph_profile=cross_graph_profile,
                governance_report=governance_report,
                uncertainty_envelope=uncertainty,
                ambiguity_certificate=ambiguity_certificate,
                metadata={
                    "generated_by": f"policy_runtime::{self.backend_kind}::{fidelity}",
                    "source_components": list(dict.fromkeys(source_components_list)),
                    "policy_runtime_invocation": runtime_execution,
                    "policy_runtime_fiscal_measurement": fiscal_measurement,
                },
            )
        )
        evaluation_vector = _runtime_metrics._attach_policy_runtime_source_metadata(
            evaluation_vector,
            runtime_execution=runtime_execution,
            fiscal_measurement=fiscal_measurement,
        )
        method_metric_projection_basis = getattr(
            self, "_policyos_method_metric_projection_basis", None
        )
        method_metric_projection_candidate_ref = getattr(
            self, "_policyos_method_metric_projection_candidate_ref", None
        )
        if method_metric_projection_basis is not None:
            if method_metric_projection_candidate_ref is None:
                raise ValueError("method_metric_projection_candidate_ref_missing")
            evaluation_vector = (
                _runtime_method_metrics.attach_completed_method_metric_observation_projection(
                    evaluation_vector,
                    candidate_ref=method_metric_projection_candidate_ref,
                    evaluated_candidate=candidate,
                    basis=method_metric_projection_basis,
                )
            )
            source_components_list.append("completed_method_metric_observation_projection")
        promotable_source = (
            fidelity == "full"
            and causal_effect_report is not None
            and uncertainty is not None
            and governance_report is not None
            and (bool(simulation_metrics) or "causal_effect_report" in source_components)
        )
        provenance = PolicyRuntimeProvenance(
            backend_kind=self.backend_kind,
            fidelity_mode=fidelity,
            promotable_source=promotable_source,
            degradation_mode=None if promotable_source or fidelity != "full" else "research_only",
            source_components=tuple(dict.fromkeys(source_components_list)),
            notes=notes,
        )
        simulation_results = _runtime_metrics._build_policy_simulation_results_impl(
            evaluation_vector,
            fidelity=fidelity,
            uncertainty=uncertainty,
            base_metrics=metrics,
            provenance=provenance,
            ambiguity_certificate=ambiguity_certificate,
            runtime_execution=runtime_execution,
        )
        evaluation_vector = evaluation_vector.with_score_source_results(simulation_results)
        completed_projection_binding = None
        if method_metric_projection_basis is not None:
            completed_projection_binding = (
                _runtime_method_metrics._issue_completed_projection_evaluation_binding(
                    evaluation_vector,
                    evaluated_candidate=candidate,
                    candidate_ref=method_metric_projection_candidate_ref,
                    basis=method_metric_projection_basis,
                )
            )
        if completed_projection_binding is not None:
            existing = self._policyos_completed_evaluation_bindings
            if len(existing) >= 256:
                raise ValueError("completed_projection_live_binding_limit")
            object.__setattr__(
                self,
                "_policyos_completed_evaluation_bindings",
                (*existing, completed_projection_binding),
            )
        return PolicyRuntimeEvaluationArtifact(
            simulation_metrics=metrics,
            simulation_results=simulation_results,
            evaluation_vector=evaluation_vector,
            fidelity=fidelity,
            provenance=provenance,
            completed_projection_binding=completed_projection_binding,
        )


@dataclass(frozen=True)
class SyntheticPolicyEvaluationBackend:
    """Synthetic policy evaluation backend implementation."""

    backend_kind: str = "synthetic"

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: UncertaintyEnvelope | None,
        distributional_report: DistributionalReport | None,
        causal_effect_report: CausalEffectReport | None,
        cross_graph_profile: CrossGraphEvidenceProfile | None,
        governance_report: GovernanceReport | None,
        ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
        evaluation_attempt_id: str | None = None,
        effective_estimation_config: Mapping[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact:
        del simulation_metrics, causal_effect_report, cross_graph_profile
        metrics = _build_runtime_simulation_metrics(
            candidate,
            fidelity=fidelity,
            governance_report=governance_report,
            distributional_report=distributional_report,
        )
        runtime_execution = _runtime_metrics._policy_runtime_execution_metadata(
            evaluation_attempt_id=evaluation_attempt_id,
            effective_estimation_config=effective_estimation_config,
        )
        fiscal_measurement = _runtime_metrics._budget_deficit_measurement(metrics)
        evaluation_vector = ObjectiveStack().evaluate(
            PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=distributional_report,
                causal_effect_report=None,
                cross_graph_profile=None,
                governance_report=governance_report,
                uncertainty_envelope=uncertainty,
                ambiguity_certificate=ambiguity_certificate,
                metadata={
                    "generated_by": f"policy_runtime::{self.backend_kind}::{fidelity}",
                    "source_components": (
                        ["synthetic_policy_runtime", "ambiguity_certificate"]
                        if ambiguity_certificate is not None
                        else ["synthetic_policy_runtime"]
                    ),
                    "policy_runtime_invocation": runtime_execution,
                    "policy_runtime_fiscal_measurement": fiscal_measurement,
                },
            )
        )
        evaluation_vector = _runtime_metrics._attach_policy_runtime_source_metadata(
            evaluation_vector,
            runtime_execution=runtime_execution,
            fiscal_measurement=fiscal_measurement,
        )
        source_components = (
            ("synthetic_policy_runtime", "ambiguity_certificate")
            if ambiguity_certificate is not None
            else ("synthetic_policy_runtime",)
        )
        provenance = PolicyRuntimeProvenance(
            backend_kind=self.backend_kind,
            fidelity_mode=fidelity,
            promotable_source=False,
            degradation_mode="research_only",
            source_components=source_components,
            notes=("Synthetic backend is test-only and not promotion-safe.",),
        )
        simulation_results = _runtime_metrics._build_policy_simulation_results_impl(
            evaluation_vector,
            fidelity=fidelity,
            uncertainty=uncertainty,
            base_metrics=metrics,
            provenance=provenance,
            ambiguity_certificate=ambiguity_certificate,
            runtime_execution=runtime_execution,
        )
        evaluation_vector = evaluation_vector.with_score_source_results(simulation_results)
        return PolicyRuntimeEvaluationArtifact(
            simulation_metrics=metrics,
            simulation_results=simulation_results,
            evaluation_vector=evaluation_vector,
            fidelity=fidelity,
            provenance=provenance,
        )


def ensure_policy_candidate_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef | None,
) -> ArtifactRef:
    """Ensure a persisted policy-candidate reference is available."""
    return _runtime_artifacts._ensure_policy_candidate_ref_impl(
        ctx, state, candidate, candidate_ref
    )


def resolve_policy_evaluation(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
) -> tuple[PolicyEvaluationVector | None, ArtifactRef | None]:
    """Resolve a policy evaluation from inputs or the configured objective stack."""
    return _runtime_artifacts._resolve_policy_evaluation_impl(
        ctx,
        state,
        candidate,
        candidate_ref,
        parse_evaluation=_parse_policy_evaluation,
        load_metrics=load_simulation_metrics,
        objective_stack_factory=ObjectiveStack,
        bundle_factory=PolicyEvaluationBundle,
        load_distributional=load_distributional_report_for_state,
        load_causal=load_causal_report,
        load_cross_graph=load_cross_graph_profile,
        load_governance=load_governance_report,
        load_uncertainty=load_search_uncertainty,
        load_ambiguity=load_ambiguity_certificate,
        persist_vector=persist_policy_evaluation_vector,
    )


def persist_policy_evaluation_vector(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    completed_projection_basis: object | None = None,
    completed_projection_binding: object | None = None,
) -> ArtifactRef:
    """Persist a policy-evaluation vector through the execution context store.

    On a re-persisted completed projection, source_run_id is only a lookup key:
    the current Runtime owner reselects the whole basis, after which the writer
    compares its complete projection with the owner-issued result.
    """
    if "completed_method_metric_projection" in evaluation_vector.metadata:
        owner = ctx.method_metric_selection_owner
        if owner is None:
            raise ValueError("completed_projection_owner_unavailable")
        if completed_projection_basis is None:
            projection = _runtime_method_metrics.CompletedMethodMetricProjection.model_validate(
                evaluation_vector.metadata["completed_method_metric_projection"]
            )
            read = _runtime_method_metrics.read_completed_admitted_method_metric_projection(
                ctx.store,
                owner=owner,
                source_run_id=projection.source_run_id,
                candidate_ref=candidate_ref,
                tenant_id=ctx.run.tenant_id,
                cell_id=ctx.run.cell_id,
            )
            if read.status != "selected" or read.basis is None:
                raise ValueError("completed_projection_current_owner_not_selected")
            completed_projection_basis = read.basis
        elif (
            getattr(completed_projection_basis, "_selection_owner", None) is not owner
            or getattr(completed_projection_basis, "_tenant_id", None) != ctx.run.tenant_id
            or getattr(completed_projection_basis, "_cell_id", None) != ctx.run.cell_id
        ):
            raise ValueError("completed_projection_owner_scope_mismatch")
    return _runtime_artifacts._persist_policy_evaluation_vector_impl(
        ctx,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
        completed_projection_basis=completed_projection_basis,
        completed_projection_binding=completed_projection_binding,
    )


def persist_policy_evaluation_vector_to_store(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    completed_projection_basis: object | None = None,
    completed_projection_binding: object | None = None,
) -> ArtifactRef:
    """Persist a native policy-runtime evaluation vector to the supplied CAS."""
    return _runtime_artifacts._persist_policy_evaluation_vector_to_store_impl(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
        completed_projection_basis=completed_projection_basis,
        completed_projection_binding=completed_projection_binding,
    )


def read_current_admitted_method_metric_projection(
    store: ArtifactStore,
    *,
    owner: MethodExecutionSelectionOwner,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> MethodMetricProjectionReadResult:
    """Read a metric projection through the authenticated current Runtime owner."""
    return _runtime_method_metrics.read_current_admitted_method_metric_projection(
        store,
        owner=owner,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )


def read_completed_admitted_method_metric_projection(
    store: CoreJSONArtifactStreamingReader,
    *,
    owner: CompletedMethodMetricSelectionOwner | None,
    source_run_id: str | None,
    candidate_ref: ArtifactRef,
    tenant_id: str | None,
    cell_id: str | None,
    request_status: Literal["absent", "requested", "invalid"],
) -> CompletedMethodMetricProjectionReadResult:
    """Resolve a completed source through the Runtime owner for a later evaluation."""
    if request_status == "invalid":
        return CompletedMethodMetricProjectionReadResult(
            status="invalid",
            limitations=("completed_method_metric_source_run_request_invalid",),
        )
    if request_status == "absent" or owner is None:
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=(
                "completed_method_metric_source_not_requested"
                if request_status == "absent"
                else "completed_method_metric_runtime_owner_not_installed",
            ),
        )
    return _runtime_method_metrics.read_completed_admitted_method_metric_projection(
        store,
        owner=owner,
        source_run_id=source_run_id,
        candidate_ref=candidate_ref,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )


def persist_funnel_executed_work_packet(
    store: ArtifactStore,
    packet: FunnelExecutedWorkPacket,
) -> ArtifactRef:
    """Persist a completed policy-runtime invocation record with CAS lineage."""
    return _runtime_artifacts._persist_funnel_executed_work_packet_impl(store, packet)


def build_selection_benchmark_evaluation(
    *,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    runtime_artifact: PolicyRuntimeEvaluationArtifact | None = None,
    source: str = "policy_runtime_selection",
    metadata_extension: Mapping[str, Any] | None = None,
) -> BenchmarkEvaluation:
    """Build the selection benchmark view for an evaluation vector."""
    return _runtime_artifacts._build_selection_benchmark_evaluation_impl(
        state=state,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
        runtime_artifact=runtime_artifact,
        source=source,
        metadata_extension=metadata_extension,
        selection_score_fn=selection_score,
    )


def build_policy_runtime_evaluation(
    candidate: PolicyCandidateSchema,
    *,
    backend: PolicyEvaluationBackend,
    fidelity: str,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
) -> PolicyRuntimeEvaluationArtifact:
    """Build a policy-runtime evaluation through its configured backend."""
    return _runtime_artifacts._build_policy_runtime_evaluation_impl(
        candidate,
        backend=backend,
        fidelity=fidelity,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
        ambiguity_certificate=ambiguity_certificate,
    )


def build_policy_simulation_results(
    evaluation: PolicyEvaluationVector,
    *,
    fidelity: str,
    uncertainty: UncertaintyEnvelope | None,
    base_metrics: dict[str, float] | None = None,
    provenance: PolicyRuntimeProvenance | None = None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metric and provenance projections for a policy-runtime result."""
    return _runtime_metrics._build_policy_simulation_results_impl(
        evaluation,
        fidelity=fidelity,
        uncertainty=uncertainty,
        base_metrics=base_metrics,
        provenance=provenance,
        ambiguity_certificate=ambiguity_certificate,
    )


def build_vulnerabilities(
    *,
    evaluation: PolicyEvaluationVector | None,
    distributional: DistributionalReport | None,
    causal_report: CausalEffectReport | None,
    governance_report: GovernanceReport | None,
) -> list[Any]:
    """Build vulnerability records from evaluation and evidence inputs."""
    return _runtime_artifacts._build_vulnerabilities_impl(
        evaluation=evaluation,
        distributional=distributional,
        causal_report=causal_report,
        governance_report=governance_report,
    )


def selection_score(evaluation_vector: PolicyEvaluationVector) -> float:
    """Return a primary score only after source-bound availability is established."""
    return _runtime_metrics._selection_score_impl(evaluation_vector)


def load_simulation_metrics(ctx: ExecutionContext, state: ExperimentState) -> dict[str, float]:
    """Load normalized simulation metrics from the state artifact index."""
    return _runtime_artifacts._load_simulation_metrics_impl(ctx, state)


def load_distributional_report_for_state(
    ctx: ExecutionContext, state: ExperimentState
) -> DistributionalReport | None:
    """Load the state-bound distributional report, when present."""
    return _runtime_artifacts._load_distributional_report_for_state_impl(ctx, state)


def load_causal_report(ctx: ExecutionContext, state: ExperimentState) -> CausalEffectReport | None:
    """Load the causal report indexed by the current state."""
    return _runtime_artifacts._load_causal_report_impl(ctx, state)


def load_governance_report(
    ctx: ExecutionContext, state: ExperimentState
) -> GovernanceReport | None:
    """Load the governance report indexed by the current state."""
    return _runtime_artifacts._load_governance_report_impl(ctx, state)


def load_cross_graph_profile(
    ctx: ExecutionContext, state: ExperimentState
) -> CrossGraphEvidenceProfile | None:
    """Load the cross-graph evidence profile indexed by the current state."""
    return _runtime_artifacts._load_cross_graph_profile_impl(ctx, state)


def load_prior_knowledge_bundle_for_state(
    ctx: ExecutionContext, state: ExperimentState
) -> PriorKnowledgeBundle | None:
    """Load prior knowledge directly or through the discovery bundle reference."""
    return _runtime_artifacts._load_prior_knowledge_bundle_for_state_impl(ctx, state)


def resolve_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LatentDiscoveryBundleResolution:
    """Resolve latent discovery bundle for state."""
    return _runtime_artifacts._resolve_latent_discovery_bundle_for_state_impl(
        ctx, state, resolution_factory=LatentDiscoveryBundleResolution
    )


def resolve_effective_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None = None,
) -> LatentDiscoveryBundleResolution:
    """Resolve effective latent discovery bundle for state."""
    return _runtime_artifacts._resolve_effective_latent_discovery_bundle_for_state_impl(
        ctx,
        state,
        causal_report=causal_report,
        resolve_base=resolve_latent_discovery_bundle_for_state,
        merge_proxy=_merge_proxy_boundary_into_latent_bundle,
        resolution_factory=LatentDiscoveryBundleResolution,
    )


def load_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LatentDiscoveryBundle | None:
    """Load latent discovery bundle for state."""
    return _runtime_artifacts._load_latent_discovery_bundle_for_state_impl(
        ctx, state, resolve_base=resolve_latent_discovery_bundle_for_state
    )


def load_effective_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None = None,
) -> LatentDiscoveryBundle | None:
    """Load effective latent discovery bundle for state."""
    return _runtime_artifacts._load_effective_latent_discovery_bundle_for_state_impl(
        ctx,
        state,
        causal_report=causal_report,
        resolve_effective=resolve_effective_latent_discovery_bundle_for_state,
    )


def _proxy_boundary_payload_from_causal_report(
    report: CausalEffectReport | None,
) -> dict[str, Any] | None:
    return _runtime_artifacts._proxy_boundary_payload_from_causal_report_impl(report)


def _merge_proxy_boundary_into_latent_bundle(
    bundle: LatentDiscoveryBundle | None,
    proxy_boundary_payload: dict[str, Any] | None,
) -> LatentDiscoveryBundle | None:
    return _runtime_artifacts._merge_proxy_boundary_into_latent_bundle_impl(
        bundle, proxy_boundary_payload
    )


def load_search_uncertainty(ctx: ExecutionContext, state: ExperimentState) -> UncertaintyEnvelope:
    """Load the causal uncertainty envelope for search consumption."""
    return _runtime_artifacts._load_search_uncertainty_impl(ctx, state)


def load_ambiguity_certificate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> AmbiguityCertificate | None:
    """Load an ambiguity certificate from runtime params or artifacts."""
    return _runtime_artifacts._load_ambiguity_certificate_impl(
        ctx,
        state,
        parse_certificate=_parse_ambiguity_certificate,
        artifact_ref_parser=maybe_artifact_ref,
    )


def resolve_funnel_outcome(state: ExperimentState) -> FunnelOutcome | None:
    """Resolve a typed funnel outcome from state params."""
    return _runtime_artifacts._resolve_funnel_outcome_impl(state)


def maybe_artifact_ref(value: Any) -> ArtifactRef | None:
    """Parse a canonical artifact reference when the input shape permits it."""
    return _runtime_artifacts._maybe_artifact_ref_impl(value)


def load_benchmark_evaluation(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> BenchmarkEvaluation:
    """Load a benchmark evaluation artifact."""
    return _runtime_artifacts._load_benchmark_evaluation_impl(ctx, ref)


def load_governance_report_from_ref(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> GovernanceReport:
    """Load a governance report artifact from its reference."""
    return _runtime_artifacts._load_governance_report_from_ref_impl(ctx, ref)


def _build_promotion_benchmark_source_basis(
    *,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    evidence_bundle: PromotionEvidenceBundle,
    promotion_context: Mapping[str, Any] | None,
    expected_loop_id: str,
) -> dict[str, _PolicyRuntimeSelectionSourceBasis | _PhaseD4ChallengeSourceBasis]:
    """Recompute policy selection and bind D4 rotations to resolved outcome rows.

    Registry membership alone does not establish a benchmark source. Hidden-holdout
    references without an independently reconciled producer basis are omitted so the
    protected admission check refuses them.
    """
    selection_projection = build_selection_benchmark_evaluation(
        state=state,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
    )
    if selection_projection.loop_id != expected_loop_id:
        raise ValueError("PromotionEvidenceBundle policy selection belongs to another loop.")
    source_basis: dict[str, _PolicyRuntimeSelectionSourceBasis | _PhaseD4ChallengeSourceBasis] = {
        "selection_evaluation_ref": _PolicyRuntimeSelectionSourceBasis(
            expected_evaluation=selection_projection
        )
    }
    current_stress_report_ref = (promotion_context or {}).get("stress_test_report_ref")
    if (
        evidence_bundle.rotating_challenge_evaluation_refs
        and current_stress_report_ref is not None
        and current_stress_report_ref == evidence_bundle.stress_test_report_ref
    ):
        source_basis["rotating_challenge_evaluation_refs"] = _PhaseD4ChallengeSourceBasis(
            stress_report_ref=current_stress_report_ref
        )
    return source_basis


def run_promotion_with_evidence(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    evidence_bundle: PromotionEvidenceBundle,
    promotion_context: dict[str, Any] | None = None,
    evaluation_provenance: dict[str, Any] | None = None,
) -> PolicyPromotionResult:
    """Run promotion with evidence."""
    policy_runtime_store, registry_root = _require_policy_runtime_store(ctx.store)
    policy_runtime_context = replace(ctx, store=policy_runtime_store)
    evidence_metadata = dict(evidence_bundle.metadata)
    raw_artifact_family = evidence_metadata.get("artifact_family")
    raw_claim_mode = evidence_metadata.get("claim_mode")
    if (
        not isinstance(raw_artifact_family, str)
        or not raw_artifact_family.strip()
        or not isinstance(raw_claim_mode, str)
        or not raw_claim_mode.strip()
    ):
        raise ValueError("promotion_benchmark_scope_unavailable")
    artifact_family = normalize_phase2_artifact_family(raw_artifact_family)
    claim_mode = _parse_policy_claim_mode(raw_claim_mode)
    expected_loop_id = str(state.params.get("policy_loop_id") or state.run_id)
    selection_ref = evidence_bundle.selection_evaluation_ref
    if selection_ref is None:
        raise ValueError("PromotionEvidenceBundle selection_evaluation_ref is required.")
    verification_ref = evidence_bundle.replay_verification_ref
    verification_report = None
    if verification_ref is not None:
        verification_report = load_replay_verification_report(
            policy_runtime_store, verification_ref
        )
    elif evidence_bundle.replay_bundle_ref is not None:
        verification_ref = verify_and_persist_replay_bundle(
            policy_runtime_store,
            run_id=state.run_id,
            replay_bundle_ref=evidence_bundle.replay_bundle_ref,
            candidate_ref=candidate_ref,
            evaluation_ref=evidence_bundle.evaluation_ref or selection_ref,
            registry=ReplayRegistry(registry_root / "search_registry" / "replay_registry"),
        )
        verification_report = load_replay_verification_report(
            policy_runtime_store, verification_ref
        )
        evidence_bundle = evidence_bundle.model_copy(
            update={"replay_verification_ref": verification_ref}
        )
    evidence_bundle.assert_runtime_compatible(
        run_id=state.run_id,
        store=policy_runtime_store,
        expected_loop_id=expected_loop_id,
        expected_refs={
            "candidate_ref": candidate_ref,
            "selection_evaluation_ref": selection_ref,
            "hidden_holdout_evaluation_ref": maybe_artifact_ref(
                state.params.get("hidden_holdout_evaluation_ref")
            ),
            "promotion_evidence_bundle_ref": maybe_artifact_ref(
                state.params.get("promotion_evidence_bundle_ref")
            ),
            "replay_bundle_ref": state.artifacts_index.get("replayable_audit_bundle_ref"),
            "governance_report_ref": state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF),
        },
        source_basis_by_role=_build_promotion_benchmark_source_basis(
            state=state,
            candidate_ref=candidate_ref,
            evaluation_vector=evaluation_vector,
            evidence_bundle=evidence_bundle,
            promotion_context=promotion_context,
            expected_loop_id=expected_loop_id,
        ),
    )
    missing = evidence_bundle.missing_required_refs(
        require_hidden_holdout=True,
        require_replay_bundle=True,
        require_replay_verification=True,
        require_governance=True,
        require_calibration=True,
    )
    if missing:
        raise ValueError(
            "PromotionEvidenceBundle is incomplete for promotion: " + ", ".join(sorted(missing))
        )

    hidden_holdout_ref = evidence_bundle.hidden_holdout_evaluation_ref
    platform_meta_ref = evidence_bundle.adversarial_meta_evaluation_ref
    assert hidden_holdout_ref is not None
    assert platform_meta_ref is not None

    selection_evaluation = load_benchmark_evaluation(policy_runtime_context, selection_ref)
    hidden_holdout = load_benchmark_evaluation(policy_runtime_context, hidden_holdout_ref)
    platform_meta = load_platform_meta_evaluation_report(policy_runtime_store, platform_meta_ref)
    from polisyos.scientist.governance.report_currentness import (
        load_current_governance_report,
    )

    governance_report = load_current_governance_report(
        policy_runtime_context,
        state,
        evidence_bundle.governance_report_ref,
    )
    if governance_report is None:
        raise ValueError("PromotionEvidenceBundle governance_report_ref could not be resolved.")
    causal_report = load_causal_report(policy_runtime_context, state)
    distributional_report = load_distributional_report_for_state(policy_runtime_context, state)
    cross_graph_profile = load_cross_graph_profile(policy_runtime_context, state)
    prior_knowledge_bundle = load_prior_knowledge_bundle_for_state(policy_runtime_context, state)
    latent_resolution = resolve_effective_latent_discovery_bundle_for_state(
        policy_runtime_context,
        state,
        causal_report=causal_report,
    )
    latent_discovery_bundle = latent_resolution.bundle
    uncertainty = load_search_uncertainty(policy_runtime_context, state)
    l2_result = (
        promotion_context.get("_funnel_L2_result") if isinstance(promotion_context, dict) else None
    )
    l2_feedback = dict(getattr(l2_result, "feedback", {}) or {})
    data_readiness_report_ref = maybe_artifact_ref(l2_feedback.get("data_readiness_report_ref"))
    data_readiness_report = None
    if data_readiness_report_ref is not None:
        try:
            data_readiness_report = load_data_readiness_report(
                _ensure_ir_artifact_store(policy_runtime_store),
                DataReadinessReportRef.model_validate(
                    data_readiness_report_ref.model_dump(mode="json")
                ),
            )
        except _POLICY_RUNTIME_LOAD_ERRORS:
            data_readiness_report = None
    proof_bundle_ref = maybe_artifact_ref(l2_feedback.get("proof_bundle_ref"))
    bounds_bundle_ref = maybe_artifact_ref(l2_feedback.get("bounds_bundle_ref"))
    negative_certificate_ref = maybe_artifact_ref(l2_feedback.get("negative_certificate_ref"))
    query_type = (
        str(evidence_metadata.get("query_type"))
        if evidence_metadata.get("query_type") is not None
        else None
    )
    estimator_name = (
        str(evidence_metadata.get("estimator_name"))
        if evidence_metadata.get("estimator_name") is not None
        else None
    )
    readiness_target = (
        str(evidence_metadata.get("readiness_target"))
        if evidence_metadata.get("readiness_target") is not None
        else None
    )

    champion_registry = ChampionRegistry(
        root=registry_root / "search_registry",
        store=policy_runtime_store,
    )
    coordinator = PolicyPromotionCoordinator(
        champion_registry=champion_registry,
        store=policy_runtime_store,
    )
    loop_id = expected_loop_id
    runtime_provenance = dict(evaluation_provenance or {})
    phase3_gate = resolve_phase3_gate(policy_runtime_context, state, candidate=candidate)
    runtime_numeric_inputs = _policy_runtime_numeric_inputs(state)
    judge_input = coordinator.build_input_bundle(
        candidate=candidate,
        funnel_outcome=resolve_funnel_outcome(state),
        benchmark_evaluation=selection_evaluation,
        hidden_holdout_evaluation=hidden_holdout,
        platform_meta_evaluation_report=platform_meta,
        evaluation_vector=evaluation_vector,
        distributional_report=distributional_report,
        causal_effect_report=causal_report,
        data_readiness_report=data_readiness_report,
        data_readiness_report_ref=data_readiness_report_ref,
        artifact_family=artifact_family,
        claim_mode=claim_mode,
        query_type=query_type,
        estimator_name=estimator_name,
        readiness_target=readiness_target,
        proof_bundle_ref=proof_bundle_ref,
        bounds_bundle_ref=bounds_bundle_ref,
        negative_certificate_ref=negative_certificate_ref,
        replay_bundle_ref=evidence_bundle.replay_bundle_ref,
        replay_verification_ref=verification_ref,
        replay_verification_report=verification_report,
        promotion_evidence_bundle_ref=maybe_artifact_ref(
            state.params.get("promotion_evidence_bundle_ref")
        ),
        cross_graph_profile=cross_graph_profile,
        prior_knowledge_bundle=prior_knowledge_bundle,
        governance_report=governance_report,
        latent_discovery_bundle=latent_discovery_bundle,
        latent_discovery_resolution_error=latent_resolution.error_payload(),
        uncertainty_envelope=uncertainty,
        candidate_ref=candidate_ref,
        evaluation_ref=evidence_bundle.evaluation_ref or selection_ref,
        run_id=state.run_id,
        state={
            "audit_lineage_complete": (
                candidate_ref is not None
                and evidence_bundle.replay_bundle_ref is not None
                and verification_ref is not None
                and selection_ref is not None
            ),
            "checkpoints": [str(state.last_checkpoint_ref.artifact_id)]
            if state.last_checkpoint_ref is not None
            else [],
            "data_sources": [str(ref.artifact_id) for ref in state.inputs.values()],
            "knowledge_metadata": {
                "workflow_id": str(state.params.get("workflow_id") or ""),
            },
            "current_pareto_position": "unknown",
        },
        compute_cost_usd=runtime_numeric_inputs.compute_cost_usd,
        replay_cost_usd=runtime_numeric_inputs.replay_cost_usd,
        timeout_risk=runtime_numeric_inputs.timeout_risk,
        evaluation_backend_kind=(
            str(runtime_provenance.get("backend_kind"))
            if runtime_provenance.get("backend_kind") is not None
            else None
        ),
        evaluation_fidelity_mode=(
            str(runtime_provenance.get("fidelity_mode"))
            if runtime_provenance.get("fidelity_mode") is not None
            else None
        ),
        evaluation_promotable_source=bool(runtime_provenance.get("promotable_source", True)),
        evaluation_degradation_mode=(
            str(runtime_provenance.get("degradation_mode"))
            if runtime_provenance.get("degradation_mode") is not None
            else None
        ),
        evaluation_provenance_notes=[
            str(item) for item in list(runtime_provenance.get("notes", []) or [])
        ],
        phase3_gate=phase3_gate,
    )
    promotion_policy = PromotionPolicy(
        loop_id=loop_id,
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
    )
    return coordinator.coordinate_promotion(
        loop_id=loop_id,
        candidate_ref=candidate_ref,
        evaluation_ref=evidence_bundle.evaluation_ref or selection_ref,
        promotion_policy=promotion_policy,
        judge_input=judge_input,
    )


def _build_runtime_simulation_metrics(
    candidate: PolicyCandidateSchema,
    *,
    fidelity: str,
    governance_report: GovernanceReport | None,
    distributional_report: DistributionalReport | None,
) -> dict[str, float]:
    return _runtime_metrics._build_runtime_simulation_metrics(
        candidate,
        fidelity=fidelity,
        governance_report=governance_report,
        distributional_report=distributional_report,
    )


def _build_evidence_driven_simulation_metrics(
    candidate: PolicyCandidateSchema,
    *,
    fidelity: str,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
) -> tuple[dict[str, float], tuple[str, ...], tuple[str, ...]]:
    return _runtime_metrics._build_evidence_driven_simulation_metrics(
        candidate,
        fidelity=fidelity,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
    )


def _parse_policy_evaluation(value: Any) -> PolicyEvaluationVector | None:
    return _runtime_metrics._parse_policy_evaluation(value)


def _parse_ambiguity_certificate(value: Any) -> AmbiguityCertificate | None:
    return _runtime_metrics._parse_ambiguity_certificate(value)


def _ambiguity_certificate_payload(
    value: AmbiguityCertificate | dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _runtime_metrics._ambiguity_certificate_payload(value)


def _channel_higher_is_better(
    evaluation: PolicyEvaluationVector,
    name: str,
    *,
    fallback: float = 0.0,
) -> float:
    return _runtime_metrics._channel_higher_is_better(evaluation, name, fallback=fallback)


def _budget_pressure(evaluation: PolicyEvaluationVector) -> float:
    return _runtime_metrics._budget_pressure(evaluation)


def _employment_signal_from_distribution(
    distributional_report: DistributionalReport | None,
    *,
    fallback: float,
) -> float:
    return _runtime_metrics._employment_signal_from_distribution(
        distributional_report, fallback=fallback
    )


def _distributional_shift_penalty(distributional_report: DistributionalReport | None) -> float:
    return _runtime_metrics._distributional_shift_penalty(distributional_report)


def _transport_penalty(cross_graph_profile: CrossGraphEvidenceProfile | None) -> float:
    return _runtime_metrics._transport_penalty(cross_graph_profile)


def _policy_budget_total(candidate: PolicyCandidateSchema) -> float:
    return _runtime_metrics._policy_budget_total(candidate)


def _resolve_current_policy_promotion_result(
    state: ExperimentState,
) -> tuple[PolicyPromotionResult | None, str]:
    """Fail closed until the protected policy-promotion owner bridge is present.

    A PolicyPromotionResult and its nested verdict are report artifacts. The
    current runtime has no issuer-owned receipt that binds a promoted decision to
    the selected candidate, current score admission, and the permitted action.
    Therefore neither typed results nor caller mappings in params can be
    projected as current authority.
    """
    if state.params.get("policy_promotion_result") is None:
        status = state.params.get("policy_promotion_projection_status")
        if (
            _reported_only_policy_projection_status(status)
            and isinstance(status.get("reason"), str)
            and status["reason"].strip()
        ):
            return None, status["reason"]
        return None, "policy_promotion_result_absent"
    return None, "protected_owner_receipt_not_established"


__all__ = [
    "LatentDiscoveryBundleResolution",
    "PRODUCTION_POLICY_EVALUATION_BACKEND_ID",
    "PolicyEvaluationBackend",
    "PolicyRuntimeEvaluationArtifact",
    "PolicyRuntimeEvaluationSafetyError",
    "PolicyRuntimeProvenance",
    "ProductionPolicyEvaluationBackend",
    "SyntheticPolicyEvaluationBackend",
    "build_policy_runtime_evaluation",
    "build_policy_simulation_results",
    "build_selection_benchmark_evaluation",
    "build_vulnerabilities",
    "ensure_policy_candidate_ref",
    "load_ambiguity_certificate",
    "load_benchmark_evaluation",
    "load_causal_report",
    "load_cross_graph_profile",
    "load_distributional_report_for_state",
    "load_effective_latent_discovery_bundle_for_state",
    "load_governance_report",
    "load_governance_report_from_ref",
    "load_latent_discovery_bundle_for_state",
    "load_prior_knowledge_bundle_for_state",
    "load_search_uncertainty",
    "maybe_artifact_ref",
    "persist_policy_evaluation_vector",
    "read_current_admitted_method_metric_projection",
    "read_completed_admitted_method_metric_projection",
    "resolve_effective_latent_discovery_bundle_for_state",
    "resolve_funnel_outcome",
    "resolve_latent_discovery_bundle_for_state",
    "resolve_policy_evaluation",
    "run_promotion_with_evidence",
    "selection_score",
]
