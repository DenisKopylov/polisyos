"""Typed search uncertainty contracts for funnel routing and judge semantics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.artifacts.protocol import ArtifactStore, resolve_manifest_by_profile
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecPlan,
    FeedbackConfig,
    FoundryExecConfig,
    FoundryExecutionInputBasis,
    FoundryExecutionInputBasisRef,
    FoundryInputBindings,
    Metrics,
    ParameterOverrideBundle,
    ProgramGraph,
    SimulationResult,
    StateDelta,
)
from polisyos.core.registry import load_registry_bundle_payload
from polisyos.foundry.execute._internal.posture import resolve_execution_posture
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir import UncertaintyType
from polisyos.ir.analytics.welfare import (
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareSampleBundle,
    WelfareStatus,
    load_welfare_bundle,
    load_welfare_sample_bundle,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel, WelfareBundleRef, WelfareSampleBundleRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


class UncertaintyEstimate(BaseModel):
    """Single typed uncertainty estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: float = Field(ge=0.0, le=1.0)
    source: str = Field(min_length=1)
    quantification_method: str = Field(min_length=1)
    is_reducible: bool
    recommended_action: str | None = None


class UncertaintyEnvelope(BaseModel):
    """Typed uncertainty attached to search-stage confidence claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    uncertainties: dict[UncertaintyType, UncertaintyEstimate]

    @model_validator(mode="after")
    def _validate_all_types_present(self) -> UncertaintyEnvelope:
        expected = set(UncertaintyType)
        actual = set(self.uncertainties)
        if actual != expected:
            missing = sorted(item.value for item in expected - actual)
            extra = sorted(str(item) for item in actual - expected)
            problems: list[str] = []
            if missing:
                problems.append(f"missing={missing}")
            if extra:
                problems.append(f"extra={extra}")
            raise ValueError(
                "uncertainties must contain exactly one estimate for each "
                f"UncertaintyType ({', '.join(problems)})"
            )
        return self

    @staticmethod
    def _unknown_estimate(
        *,
        source: str,
        quantification_method: str,
        is_reducible: bool,
    ) -> UncertaintyEstimate:
        return UncertaintyEstimate(
            level=1.0,
            source=source,
            quantification_method=quantification_method,
            is_reducible=is_reducible,
        )

    @classmethod
    def unknown(
        cls,
        source: str = "not assessed at this fidelity",
        *,
        quantification_method: str = "not_assessed",
        is_reducible: bool = True,
    ) -> UncertaintyEnvelope:
        """Build an envelope where every type is unassessed and maximally uncertain."""

        return cls(
            uncertainties={
                uncertainty_type: cls._unknown_estimate(
                    source=source,
                    quantification_method=quantification_method,
                    is_reducible=is_reducible,
                )
                for uncertainty_type in UncertaintyType
            }
        )

    @classmethod
    def deterministic(cls) -> UncertaintyEnvelope:
        """Compatibility factory for deterministic gates that do not assess uncertainty."""

        return cls.unknown(
            source="deterministic gate; not assessed at this fidelity",
            quantification_method="static_rule",
            is_reducible=True,
        )

    @classmethod
    def from_partial(
        cls,
        partial: Mapping[UncertaintyType, UncertaintyEstimate],
        *,
        source: str = "not assessed at this fidelity",
        quantification_method: str = "not_assessed",
        is_reducible: bool = True,
    ) -> UncertaintyEnvelope:
        """Fill missing uncertainty types with explicit unassessed estimates."""

        payload: dict[UncertaintyType, UncertaintyEstimate] = {}
        for uncertainty_type in UncertaintyType:
            payload[uncertainty_type] = partial.get(
                uncertainty_type,
                cls._unknown_estimate(
                    source=source,
                    quantification_method=quantification_method,
                    is_reducible=is_reducible,
                ),
            )
        return cls(uncertainties=payload)

    @classmethod
    def merge_max(
        cls,
        envelopes: Iterable[UncertaintyEnvelope],
    ) -> UncertaintyEnvelope:
        """Merge envelopes by taking the highest uncertainty estimate per type."""

        envelope_list = list(envelopes)
        if not envelope_list:
            return cls.unknown()

        payload: dict[UncertaintyType, UncertaintyEstimate] = {}
        for uncertainty_type in UncertaintyType:
            payload[uncertainty_type] = max(
                (env.uncertainties[uncertainty_type] for env in envelope_list),
                key=lambda estimate: estimate.level,
            )
        return cls(uncertainties=payload)

    def with_update(
        self,
        uncertainty_type: UncertaintyType,
        estimate: UncertaintyEstimate,
    ) -> UncertaintyEnvelope:
        """Return a new envelope with one estimate replaced."""

        updated = dict(self.uncertainties)
        updated[uncertainty_type] = estimate
        return UncertaintyEnvelope(uncertainties=updated)


class SearchUncertaintyBasis(BaseModel):
    """Producer-declared scientific identity for a routing observation.

    Content binding proves identity, not the producer's refinement law or any
    publication authority. No observation supersedes another under this contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    subject_ref: ArtifactRef
    value_ref: ArtifactRef
    input_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    rule_ref: ArtifactRef
    producer_ref: ArtifactRef
    valid_time: AwareDatetime
    estimand: str = Field(min_length=1)
    unit: str = Field(min_length=1)


class SearchUncertaintyObservation(BaseModel):
    """A producer observation whose envelope and complete basis are CAS bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    basis_ref: ArtifactRef
    producer_ref: ArtifactRef
    risk_ref: ArtifactRef
    envelope: UncertaintyEnvelope


def search_uncertainty_observation_ref(payload: Mapping[str, object]) -> ArtifactRef | None:
    """Read a native producer ref for later content-bound intake, without admission."""
    raw = payload.get("uncertainty_observation_ref")
    if raw is None:
        return None
    try:
        return ArtifactRef.model_validate(raw)
    except (TypeError, ValueError):
        return None


def persist_search_uncertainty(
    store: FileSystemCAS,
    payload: SearchUncertaintyBasis | SearchUncertaintyObservation,
) -> ArtifactRef:
    """Persist a supplied routing basis or observation without granting authority."""
    suffix = "basis" if isinstance(payload, SearchUncertaintyBasis) else "observation"
    dependencies = (
        [
            payload.subject_ref,
            payload.value_ref,
            *payload.input_refs,
            payload.rule_ref,
            payload.producer_ref,
        ]
        if isinstance(payload, SearchUncertaintyBasis)
        else [payload.basis_ref, payload.producer_ref, payload.risk_ref]
    )
    return store.put_json(
        payload,
        PutOptions(
            kind=f"scientist.search.uncertainty_{suffix}",
            media_type="application/json",
            schema=SchemaInfo(name=type(payload).__name__, version=payload.schema_version),
            inputs=[
                input_ref_from_artifact_ref(ref, role="uncertainty_input") for ref in dependencies
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_search_uncertainty_observation(
    store: FileSystemCAS,
    observation_ref: ArtifactRef,
    expected_basis_ref: ArtifactRef,
    expected_envelope: UncertaintyEnvelope,
    expected_subject_ref: ArtifactRef,
) -> SearchUncertaintyObservation:
    """Resolve actual bytes and reject a stale, foreign or substituted observation."""
    from polisyos.core.artifacts import load_core_json_artifact

    for ref, kind in (
        (observation_ref, "scientist.search.uncertainty_observation"),
        (expected_basis_ref, "scientist.search.uncertainty_basis"),
    ):
        if ref.kind != kind or store.get_manifest(ref).kind != kind:
            raise ValueError("Search uncertainty artifact kind mismatch")
        if not store.verify(ref).ok:
            raise ValueError("Search uncertainty artifact integrity failure")
    basis = SearchUncertaintyBasis.model_validate(
        load_core_json_artifact(store, expected_basis_ref)
    )
    if basis.subject_ref != expected_subject_ref:
        raise ValueError("Search uncertainty basis differs from the configured candidate")
    observation = SearchUncertaintyObservation.model_validate(
        load_core_json_artifact(store, observation_ref)
    )
    if observation.basis_ref != expected_basis_ref:
        raise ValueError("Search uncertainty observation has a foreign or stale basis")
    if observation.producer_ref != basis.producer_ref:
        raise ValueError("Search uncertainty observation has a foreign producer")
    if observation.envelope != expected_envelope:
        raise ValueError("Search uncertainty observation differs from the stage envelope")
    # Every declared input must resolve; a plausible ref is not a supplied input.
    for ref in (
        basis.subject_ref,
        basis.value_ref,
        *basis.input_refs,
        basis.rule_ref,
        basis.producer_ref,
        observation.risk_ref,
    ):
        store.get_manifest(ref)
        store.get_bytes(ref)
    return observation


_SOURCE_BOUND_RISK_OBSERVATION_KIND = "scientist.search.source_bound_risk_observation"
_SOURCE_BOUND_RISK_OBSERVATION_SCHEMA = "polisyos.scientist.SourceBoundRiskObservation"
_SOURCE_BOUND_RISK_OBSERVATION_VERSION = "1.2"


class ExecutionSourceProjection(BaseModel):
    """Recomputed identity relation from the candidate source to a real Foundry call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_status: Literal["recomputed_single_step_basis"]
    simulation_result_ref: ArtifactRef
    execution_input_basis_ref: FoundryExecutionInputBasisRef
    candidate_data_snapshot_ref: ArtifactRef
    execution_data_snapshot_ref: ArtifactRef
    candidate_to_execution_data_relation: Literal[
        "same_selected_ref", "same_artifact_id_different_profile", "different_artifact_id"
    ]
    candidate_registry_bundle_ref: ArtifactRef
    compile_registry_bundle_ref: ArtifactRef
    binding_registry_bundle_ref: ArtifactRef
    runtime_registry_bundle_ref: ArtifactRef
    candidate_to_compile_registry_relation: Literal[
        "same_selected_ref", "same_artifact_id_different_profile", "different_artifact_id"
    ]
    binding_to_runtime_registry_relation: Literal[
        "same_selected_ref", "same_artifact_id_different_profile", "different_artifact_id"
    ]
    compile_to_runtime_registry_relation: Literal[
        "same_selected_ref", "same_artifact_id_different_profile", "different_artifact_id"
    ]


class SourceBoundRiskObservation(BaseModel):
    """Candidate-only raw welfare measurement; never a search-risk refinement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.2"] = "1.2"
    authority_purpose: Literal["candidate_only_audit_measurement"] = (
        "candidate_only_audit_measurement"
    )
    admission_status: Literal["candidate_only"] = "candidate_only"
    risk_interpretation_status: Literal["not_established"] = "not_established"
    refinement_status: Literal["not_established"] = "not_established"
    scope_relation_status: Literal["consumer_asserted"] = "consumer_asserted"
    unit_binding_status: Literal["not_established"] = "not_established"
    valid_time_status: Literal["not_established"] = "not_established"
    production_time_role: Literal["source_bundle_manifest_created_at"] = (
        "source_bundle_manifest_created_at"
    )

    candidate_ref: ArtifactRef
    welfare_bundle_ref: ArtifactRef
    policy_scope_claim_ref: ArtifactRef
    welfare_weights_ref: ArtifactRef
    weight_application_status: Literal["recomputed_from_component_draws"] = (
        "recomputed_from_component_draws"
    )
    method_config_ref: ArtifactRef
    propagation_report_ref: ArtifactRef
    sample_bundle_ref: ArtifactRef
    execution_source: ExecutionSourceProjection
    welfare_measure: str = Field(min_length=1)
    method_used: WelfareMethod
    source_status: WelfareStatus
    confidence_level: float = Field(gt=0.0, lt=1.0)
    mc_sampling_method: str = Field(min_length=1)
    observed_at: AwareDatetime
    valid_time: None = None
    unit: None = None
    nominal_point_estimate: float | None = None
    welfare_draw_mean: float
    welfare_draw_std: float = Field(ge=0.0)
    draw_summary_semantics: Literal[
        "complete_requested_draws", "successful_draws_only_conditional_on_execution"
    ]
    credible_interval: tuple[float, float] | None = None
    interval_semantics: WelfareIntervalSemantics
    draw_completion_status: Literal["complete", "partial"]
    requested_draw_count: int = Field(ge=0, strict=True)
    attempted_draw_count: int = Field(ge=0, strict=True)
    successful_draw_count: int = Field(ge=0, strict=True)
    failed_draw_count: int = Field(ge=0, strict=True)
    unattempted_draw_count: int = Field(ge=0, strict=True)
    valid_draw_count: int = Field(ge=0, strict=True)
    simulation_attempt_count: int = Field(ge=0, strict=True)
    retry_attempt_count: int = Field(ge=0, strict=True)


def _source_core_ref(ref: ArtifactRef | ArtifactRefModel) -> ArtifactRef:
    """Convert an IR ref to the core ref while preserving its selected profile."""
    if isinstance(ref, ArtifactRef):
        return ref
    return ArtifactRef.model_validate(ref.model_dump(mode="python"))


def _source_typed_json_model[SourceModelT: BaseModel](
    store: ArtifactStore,
    model: type[SourceModelT],
    ref: ArtifactRef | ArtifactRefModel,
) -> SourceModelT:
    """Validate one typed source through its exact selected Core JSON profile."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    selected_ref = _source_core_ref(ref)
    expected_kind, expected_media_type = _source_model_artifact_identity(model)
    expected_schema = _source_model_schema(model)
    _source_manifest(
        store,
        selected_ref,
        expected_kind=expected_kind,
        expected_media_type=expected_media_type,
        expected_schema=expected_schema,
    )
    return validate_core_model_json_artifact(model, store, selected_ref)


def _source_model_schema(model: type[BaseModel]) -> SchemaInfo:
    """Read the canonical serialization descriptor declared by the model owner."""
    name = getattr(model, "ARTIFACT_SCHEMA_NAME", None)
    version = getattr(model, "ARTIFACT_SCHEMA_VERSION", None)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("source-bound risk typed source has no owner schema name")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("source-bound risk typed source has no owner schema version")
    return SchemaInfo(name=name, version=version)


def _source_model_artifact_identity(model: type[BaseModel]) -> tuple[str, str]:
    """Read the artifact kind and media type declared by the typed source owner."""
    kind = getattr(model, "ARTIFACT_KIND", None)
    media_type = getattr(model, "ARTIFACT_MEDIA_TYPE", None)
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("source-bound risk typed source has no owner artifact kind")
    if not isinstance(media_type, str) or not media_type.strip():
        raise ValueError("source-bound risk typed source has no owner artifact media type")
    return kind, media_type


def _source_manifest(
    store: ArtifactStore,
    ref: ArtifactRef | ArtifactRefModel,
    *,
    expected_kind: str | None = None,
    expected_media_type: str | None = None,
    expected_schema: SchemaInfo | None = None,
) -> ArtifactManifest:
    core_ref = _source_core_ref(ref)
    if core_ref.manifest_profile_sha256 is None:
        raise ValueError("source-bound risk selected manifest profile is missing")
    if expected_kind is not None and core_ref.kind != expected_kind:
        raise ValueError("source-bound risk typed source kind does not match its owner")
    if expected_media_type is not None and core_ref.media_type != expected_media_type:
        raise ValueError("source-bound risk typed source media type does not match its owner")
    manifest = resolve_manifest_by_profile(
        store, core_ref.artifact_id, core_ref.manifest_profile_sha256
    )
    if manifest.kind != core_ref.kind or manifest.media_type != core_ref.media_type:
        raise ValueError("source-bound risk artifact manifest contract mismatch")
    if expected_kind is not None and manifest.kind != expected_kind:
        raise ValueError("source-bound risk manifest kind does not match its typed owner")
    if expected_media_type is not None and manifest.media_type != expected_media_type:
        raise ValueError("source-bound risk manifest media type does not match its typed owner")
    if not store.verify(core_ref).ok:
        raise ValueError("source-bound risk artifact integrity failure")
    if expected_schema is not None and manifest.artifact_schema != expected_schema:
        raise ValueError("source-bound risk artifact schema does not match its typed model owner")
    return manifest


def _source_manifest_for_edge(
    store: ArtifactStore,
    edge: InputRef,
    *,
    require_selected: bool = False,
    expected_model: type[BaseModel] | None = None,
) -> tuple[ArtifactRef, ArtifactManifest]:
    if edge.manifest_profile_sha256 is None:
        if require_selected:
            raise ValueError("source-bound risk parent edge profile is missing")
        manifest = store.get_manifest(edge.artifact_id)
    else:
        manifest = resolve_manifest_by_profile(
            store, edge.artifact_id, edge.manifest_profile_sha256
        )
    expected_kind = expected_media_type = None
    expected_schema = None
    if expected_model is not None:
        expected_kind, expected_media_type = _source_model_artifact_identity(expected_model)
        expected_schema = _source_model_schema(expected_model)
        if manifest.kind != expected_kind or manifest.media_type != expected_media_type:
            raise ValueError("source-bound risk edge does not match its typed artifact owner")
        if manifest.artifact_schema != expected_schema:
            raise ValueError(
                "source-bound risk edge schema does not match its typed artifact owner"
            )
    ref = ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    _source_manifest(
        store,
        ref,
        expected_kind=expected_kind,
        expected_media_type=expected_media_type,
        expected_schema=expected_schema,
    )
    return ref, manifest


def _source_input_by_role(manifest: ArtifactManifest, role: str) -> InputRef:
    matches = [item for item in manifest.inputs if item.role == role]
    if len(matches) != 1:
        raise ValueError(f"source-bound risk requires one {role} lineage edge")
    return matches[0]


def _source_ref_matches_edge(ref: ArtifactRef, edge: InputRef) -> bool:
    return (
        ref.artifact_id == edge.artifact_id
        and ref.manifest_profile_sha256 == edge.manifest_profile_sha256
    )


def _source_child_manifest(
    store: ArtifactStore, manifest: ArtifactManifest, *, role: str, ref: ArtifactRef
) -> ArtifactManifest:
    edge = _source_input_by_role(manifest, role)
    if not _source_ref_matches_edge(ref, edge):
        raise ValueError(f"source-bound risk {role} profile differs from its parent edge")
    resolved_ref, child_manifest = _source_manifest_for_edge(store, edge)
    if resolved_ref != ref:
        raise ValueError(f"source-bound risk {role} ref differs from its selected child")
    return child_manifest


def _verify_data_snapshot_source_edges(
    store: ArtifactStore,
    ref: ArtifactRef | ArtifactRefModel,
    snapshot: DataSnapshot,
) -> None:
    """Reconcile used DataSnapshot fields to exact selected manifest edges."""
    manifest = _source_manifest(
        store,
        ref,
        expected_kind=DataSnapshot.ARTIFACT_KIND,
        expected_media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
        expected_schema=_source_model_schema(DataSnapshot),
    )
    for role, raw_ref in (
        ("data_ref", snapshot.data_ref),
        ("uncertainty_envelope_ref", snapshot.uncertainty_envelope_ref),
    ):
        edges = [edge for edge in manifest.inputs if edge.role == role]
        if raw_ref is None:
            if edges:
                raise ValueError(f"source-bound risk DataSnapshot has unexpected {role} edge")
            continue
        if len(edges) != 1:
            raise ValueError(f"source-bound risk DataSnapshot requires one {role} edge")
        selected_ref, _ = _source_manifest_for_edge(store, edges[0], require_selected=True)
        if selected_ref != _source_core_ref(raw_ref):
            raise ValueError(f"source-bound risk DataSnapshot {role} edge differs from payload")


def _verify_welfare_bundle_role_edges(
    store: ArtifactStore,
    manifest: ArtifactManifest,
    bundle: WelfareBundle,
) -> None:
    """Reconcile every typed WelfareBundle ref with its selected manifest role."""
    role_refs: list[tuple[str, ArtifactRef | ArtifactRefModel | None]] = [
        ("welfare_source", bundle.welfare_ref),
        ("social_weight_manifest", bundle.social_weight_ref),
        ("policy_scope_claim", bundle.policy_ref),
        ("baseline", bundle.baseline_ref),
        ("pe_model", bundle.pe_model_ref),
        ("ge_model", bundle.ge_model_ref),
        ("welfare_weights", bundle.welfare_weights_ref),
        ("method_config", bundle.method_config_ref),
        ("sample_bundle", bundle.sample_bundle_ref),
        ("sensitivity_diagnostics", bundle.sensitivity_diagnostics_ref),
        ("ge_uncertainty", bundle.ge_uncertainty_ref),
        ("dependence_structure", bundle.dependence_structure_ref),
        ("channel_decomposition", bundle.channel_decomposition_ref),
        *((f"pe_uncertainty.{name}", ref) for name, ref in bundle.pe_uncertainty_refs.items()),
    ]
    expected_roles = {role for role, _ in role_refs}
    for edge in manifest.inputs:
        if (
            edge.role
            in {
                "welfare_source",
                "social_weight_manifest",
                "policy_scope_claim",
                "baseline",
                "pe_model",
                "ge_model",
                "welfare_weights",
                "method_config",
                "sample_bundle",
                "sensitivity_diagnostics",
                "ge_uncertainty",
                "dependence_structure",
                "channel_decomposition",
            }
            or edge.role.startswith("pe_uncertainty.")
        ) and edge.role not in expected_roles:
            raise ValueError(f"source-bound risk undeclared typed WelfareBundle role {edge.role}")
    for role, raw_ref in role_refs:
        edges = [edge for edge in manifest.inputs if edge.role == role]
        if raw_ref is None:
            if edges:
                raise ValueError(f"source-bound risk undeclared {role} manifest edge")
            continue
        if len(edges) != 1:
            raise ValueError(f"source-bound risk requires one typed {role} manifest edge")
        ref = _source_core_ref(raw_ref)
        if ref.manifest_profile_sha256 is None or not _source_ref_matches_edge(ref, edges[0]):
            raise ValueError(f"source-bound risk typed {role} ref differs from its selected edge")
        _source_manifest(store, ref)


def _recompute_weighted_component_outputs(
    bundle: WelfareBundle,
    sample_bundle: WelfareSampleBundle,
    weight_payload: Mapping[str, Any],
) -> float:
    """Recompute nominal and MC welfare outputs from selected weights and producer operands."""
    labels = weight_payload.get("labels")
    raw_weights = weight_payload.get("weights")
    if (
        not isinstance(labels, list)
        or not labels
        or any(not isinstance(label, str) or not label.strip() for label in labels)
        or len(set(labels)) != len(labels)
        or not isinstance(raw_weights, list)
        or len(raw_weights) != len(labels)
        or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw_weights
        )
    ):
        raise ValueError("source-bound risk welfare weight payload is malformed")
    weights = np.asarray(raw_weights, dtype=np.float64)
    if not np.all(np.isfinite(weights)):
        raise ValueError("source-bound risk welfare weights are not finite")
    expected_labels = tuple(labels)
    if sample_bundle.component_labels != expected_labels:
        raise ValueError("source-bound risk sample component labels differ from selected weights")
    if bundle.nominal_component_labels != expected_labels:
        raise ValueError("source-bound risk nominal component labels differ from selected weights")
    declared_labels = bundle.metadata.get("response_labels")
    if declared_labels is not None and tuple(declared_labels) != expected_labels:
        raise ValueError("source-bound risk bundle response labels differ from selected weights")
    sample_count = len(sample_bundle.welfare_draws)
    if (
        sample_count < 1
        or len(sample_bundle.welfare_pe_draws) != sample_count
        or len(sample_bundle.welfare_ge_draws) != sample_count
        or len(sample_bundle.welfare_pe_component_draws) != sample_count
        or len(sample_bundle.welfare_total_component_draws) != sample_count
    ):
        raise ValueError("source-bound risk raw component vectors are missing or incomplete")
    for index, (pe_components, total_components) in enumerate(
        zip(
            sample_bundle.welfare_pe_component_draws,
            sample_bundle.welfare_total_component_draws,
            strict=True,
        )
    ):
        pe_vector = np.asarray(pe_components, dtype=np.float64)
        total_vector = np.asarray(total_components, dtype=np.float64)
        if (
            len(pe_vector) != len(weights)
            or len(total_vector) != len(weights)
            or not np.all(np.isfinite(pe_vector))
            or not np.all(np.isfinite(total_vector))
        ):
            raise ValueError("source-bound risk component vector width or values are invalid")
        expected_pe = float(np.dot(weights, pe_vector))
        expected_total = float(np.dot(weights, total_vector))
        if (
            sample_bundle.welfare_pe_draws[index] != expected_pe
            or sample_bundle.welfare_draws[index] != expected_total
            or sample_bundle.welfare_ge_draws[index] != expected_total - expected_pe
        ):
            raise ValueError(
                "source-bound risk weighted draws do not recompute from selected weights"
            )
    nominal_pe_components = np.asarray(bundle.nominal_welfare_pe_components, dtype=np.float64)
    nominal_total_components = np.asarray(bundle.nominal_welfare_total_components, dtype=np.float64)
    if (
        len(nominal_pe_components) != len(weights)
        or len(nominal_total_components) != len(weights)
        or not np.all(np.isfinite(nominal_pe_components))
        or not np.all(np.isfinite(nominal_total_components))
    ):
        raise ValueError("source-bound risk nominal component vectors are missing or invalid")
    nominal_pe = float(np.dot(weights, nominal_pe_components))
    nominal_total = float(np.dot(weights, nominal_total_components))
    nominal_ge = nominal_total - nominal_pe
    if (
        bundle.point_estimate is None
        or bundle.point_estimate != nominal_total
        or bundle.channel_decomposition.get("pe") != nominal_pe
        or bundle.channel_decomposition.get("ge") != nominal_ge
    ):
        raise ValueError(
            "source-bound risk nominal weighted outputs do not recompute from selected weights"
        )
    return nominal_total


def _source_observation_inputs(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_ref: ArtifactRef,
    policy_ref: ArtifactRef,
    weights_ref: ArtifactRef,
    method_ref: ArtifactRef,
    report_ref: ArtifactRef,
    sample_ref: ArtifactRef,
    source_manifests: tuple[tuple[str, ArtifactManifest], ...],
) -> list[InputRef]:
    inputs = [
        input_ref_from_artifact_ref(candidate_ref, role="search_candidate"),
        input_ref_from_artifact_ref(welfare_ref, role="source_welfare_bundle"),
        input_ref_from_artifact_ref(policy_ref, role="policy_scope_claim"),
        input_ref_from_artifact_ref(weights_ref, role="welfare_weights"),
        input_ref_from_artifact_ref(method_ref, role="method_profile"),
        input_ref_from_artifact_ref(report_ref, role="propagation_report"),
        input_ref_from_artifact_ref(sample_ref, role="sample_bundle"),
    ]
    for parent_name, manifest in source_manifests:
        for edge in manifest.inputs:
            _source_manifest_for_edge(store, edge)
            inputs.append(
                InputRef(
                    artifact_id=edge.artifact_id,
                    role=f"{parent_name}.{edge.role}",
                    manifest_profile_sha256=edge.manifest_profile_sha256,
                )
            )
    return inputs


def _source_identity_relation(
    left: ArtifactRef | ArtifactRefModel,
    right: ArtifactRef | ArtifactRefModel,
) -> Literal["same_selected_ref", "same_artifact_id_different_profile", "different_artifact_id"]:
    left_ref = _source_core_ref(left)
    right_ref = _source_core_ref(right)
    if left_ref.artifact_id != right_ref.artifact_id:
        return "different_artifact_id"
    if left_ref.manifest_profile_sha256 != right_ref.manifest_profile_sha256:
        return "same_artifact_id_different_profile"
    return "same_selected_ref"


def _source_inventory_for_basis(
    store: ArtifactStore,
    basis: FoundryExecutionInputBasis,
) -> list[InputRef]:
    """Recompute the exact basis manifest inputs from its typed refs and their parents."""
    sources: list[tuple[str, ArtifactRef | ArtifactRefModel]] = [
        ("exec_plan", basis.exec_plan_ref),
        ("program_graph", basis.program_graph_ref),
        ("trinity_bundle", basis.trinity_bundle_ref),
        ("candidate", basis.candidate_ref),
        ("candidate_data_snapshot", basis.candidate_data_snapshot_ref),
        ("candidate_registry_bundle", basis.candidate_registry_bundle_ref),
        ("input_bindings", basis.input_bindings_ref),
        ("actual_data_snapshot", basis.data_snapshot_ref),
        ("bound_state_snapshot", basis.bound_state_snapshot_ref),
        ("base_state_snapshot", basis.base_state_snapshot_ref),
        ("binding_registry_bundle", basis.binding_registry_ref),
        ("compile_registry_bundle", basis.compile_registry_ref),
        ("runtime_registry_bundle", basis.runtime_registry_ref),
    ]
    for role, payload in (
        ("binding", basis.binding_registry_members),
        ("compile", basis.compile_registry_members),
        ("runtime", basis.runtime_registry_members),
    ):
        for member_role, member_ref in payload.model_dump(mode="python").items():
            if member_ref is not None:
                sources.append(
                    (
                        f"{role}_registry_member.{member_role}",
                        ArtifactRef.model_validate(member_ref),
                    )
                )
    if basis.parameter_override_bundle_ref is not None:
        sources.append(("parameter_override_bundle", basis.parameter_override_bundle_ref))
    if basis.observed_range_bundle_ref is not None:
        sources.append(("observed_range_bundle", basis.observed_range_bundle_ref))
    if basis.request.feedback_config_ref is not None:
        sources.append(("feedback_config", basis.request.feedback_config_ref))

    inventory: list[InputRef] = []
    for source_role, raw_ref in sources:
        ref = _source_core_ref(raw_ref)
        manifest = _source_manifest(store, ref)
        inventory.append(input_ref_from_artifact_ref(ref, role=f"basis.source.{source_role}"))
        for edge in manifest.inputs:
            resolved_ref, _ = _source_manifest_for_edge(store, edge, require_selected=True)
            inventory.append(
                InputRef(
                    artifact_id=resolved_ref.artifact_id,
                    role=f"basis.edge.{source_role}.{edge.role}",
                    manifest_profile_sha256=resolved_ref.manifest_profile_sha256,
                )
            )
    return inventory


def _source_inventory_key(items: list[InputRef]) -> list[tuple[str, str, str | None]]:
    return sorted(
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in items
    )


def _recompute_execution_source(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_manifest: ArtifactManifest,
) -> tuple[ExecutionSourceProjection, ArtifactRef, ArtifactManifest, ArtifactRef, ArtifactManifest]:
    """Resolve every source boundary from the stored WelfareBundle to the Foundry call."""
    simulation_edge = _source_input_by_role(welfare_manifest, "simulation_result")
    simulation_ref, simulation_manifest = _source_manifest_for_edge(
        store,
        simulation_edge,
        require_selected=True,
        expected_model=SimulationResult,
    )
    if simulation_manifest.artifact_schema != _source_model_schema(SimulationResult):
        raise ValueError("source-bound risk simulation result schema mismatch")
    simulation_result = _source_typed_json_model(store, SimulationResult, simulation_ref)
    if simulation_result.execution_source_status == "feedback_uncomposed":
        raise ValueError("source-bound risk feedback execution basis is uncomposed")
    if (
        simulation_result.execution_source_status != "single_step_basis"
        or simulation_result.execution_input_basis_ref is None
        or simulation_result.feedback_result_ref is not None
    ):
        raise ValueError("source-bound risk single-step execution basis is missing")
    basis_ref = _source_core_ref(simulation_result.execution_input_basis_ref)
    basis_manifest = _source_child_manifest(
        store, simulation_manifest, role="execution_input_basis", ref=basis_ref
    )
    if basis_manifest.artifact_schema != _source_model_schema(FoundryExecutionInputBasis):
        raise ValueError("source-bound risk execution basis schema mismatch")
    basis = _source_typed_json_model(store, FoundryExecutionInputBasis, basis_ref)
    if basis.request.return_selected_profile is not True:
        raise ValueError("source-bound risk execution basis was not produced with selected refs")
    if (
        _source_core_ref(basis.exec_plan_ref) != _source_core_ref(simulation_result.exec_plan_ref)
        or _source_core_ref(basis.request.exec_plan_ref) != _source_core_ref(basis.exec_plan_ref)
        or _source_core_ref(basis.request.input_bindings_ref)
        != _source_core_ref(basis.input_bindings_ref)
        or _source_core_ref(basis.request.registry_bundle_ref)
        != _source_core_ref(basis.runtime_registry_ref)
        or _source_core_ref(basis.candidate_ref) != candidate_ref
    ):
        raise ValueError("source-bound risk execution basis request refs disagree")
    # The ProgramGraph ref is reached from the actual ExecPlan payload, not inferred from IDs.
    exec_plan = _source_typed_json_model(store, ExecPlan, basis.exec_plan_ref)
    graph_ref = _source_core_ref(exec_plan.program_ref)
    if graph_ref != _source_core_ref(basis.program_graph_ref):
        raise ValueError("source-bound risk execution basis graph differs from ExecPlan")
    graph = _source_typed_json_model(store, ProgramGraph, graph_ref)
    exec_plan_manifest = _source_manifest(store, basis.exec_plan_ref)
    graph_manifest = _source_manifest(store, graph_ref)
    trinity_ref = _source_core_ref(basis.trinity_bundle_ref)
    if _source_core_ref(graph.ir_ref) != trinity_ref:
        raise ValueError(
            "source-bound risk execution basis Trinity source differs from ProgramGraph"
        )
    if (
        _source_ref_from_parent_edge(
            store, exec_plan_manifest, "program_graph", expected_kind="foundry.program_graph"
        )
        != graph_ref
    ):
        raise ValueError("source-bound risk ExecPlan manifest names another ProgramGraph")
    if (
        _source_ref_from_parent_edge(store, graph_manifest, "ir", expected_kind="ir.trinity_bundle")
        != trinity_ref
    ):
        raise ValueError("source-bound risk ProgramGraph manifest names another Trinity source")
    compile_registry_from_graph = _source_ref_from_parent_edge(
        store, graph_manifest, "registry_bundle", expected_kind="core.registry_bundle"
    )
    if compile_registry_from_graph != _source_core_ref(basis.compile_registry_ref):
        raise ValueError("source-bound risk compile registry differs from ProgramGraph")
    trinity_manifest = _source_manifest(store, trinity_ref)
    trinity_candidate_ref = _source_ref_from_parent_edge(
        store,
        trinity_manifest,
        "policy_candidate",
        expected_kind="scientist.policy_design.candidate",
    )
    if trinity_candidate_ref != candidate_ref:
        raise ValueError("source-bound risk Trinity source names another candidate")
    trinity = _source_typed_json_model(store, TrinityBundle, trinity_ref)
    bindings = _source_typed_json_model(store, FoundryInputBindings, basis.input_bindings_ref)
    binding_manifest = _source_manifest(store, basis.input_bindings_ref)
    if (
        _source_core_ref(bindings.data_snapshot_ref) != _source_core_ref(basis.data_snapshot_ref)
        or _source_core_ref(bindings.bound_state_snapshot_ref)
        != _source_core_ref(basis.bound_state_snapshot_ref)
        or _source_core_ref(bindings.registry_bundle_ref)
        != _source_core_ref(basis.binding_registry_ref)
        or _source_ref_from_parent_edge(
            store, binding_manifest, "input.data_snapshot_ref", expected_kind="fabric.data_snapshot"
        )
        != _source_core_ref(basis.data_snapshot_ref)
        or _source_ref_from_parent_edge(
            store,
            binding_manifest,
            "input.registry_bundle_ref",
            expected_kind="core.registry_bundle",
        )
        != _source_core_ref(basis.binding_registry_ref)
        or _source_ref_from_parent_edge(
            store,
            binding_manifest,
            "artifact.bound_state_snapshot_ref",
            expected_kind="foundry.state_snapshot",
        )
        != _source_core_ref(basis.bound_state_snapshot_ref)
    ):
        raise ValueError("source-bound risk execution basis bindings disagree")
    for registry_ref, declared_members in (
        (basis.binding_registry_ref, basis.binding_registry_members),
        (basis.compile_registry_ref, basis.compile_registry_members),
        (basis.runtime_registry_ref, basis.runtime_registry_members),
    ):
        actual_members = load_registry_bundle_payload(store, registry_ref)
        if actual_members != declared_members:
            raise ValueError(
                "source-bound risk registry bundle payload differs from selected members"
            )
    if _source_core_ref(basis.runtime_registry_ref) != _source_core_ref(
        basis.request.registry_bundle_ref
    ):
        raise ValueError("source-bound risk runtime registry differs from ExecuteRequest")
    if set(basis.request_fields_set) - set(basis.request.model_fields):
        raise ValueError("source-bound risk request fields-set contains unknown fields")
    if "return_selected_profile" not in basis.request_fields_set:
        raise ValueError("source-bound risk request did not explicitly request selected profiles")
    if set(basis.request_exec_config_fields_set) - set(basis.request.exec_config.model_fields):
        raise ValueError("source-bound risk execution-config fields-set contains unknown fields")
    if basis.request.feedback_config_ref is not None:
        feedback_config = _source_typed_json_model(
            store, FeedbackConfig, basis.request.feedback_config_ref
        )
        if feedback_config.mode != "off":
            raise ValueError("source-bound risk feedback execution basis is uncomposed")
    config_values = basis.request.exec_config.model_dump(mode="python")
    configured = FoundryExecConfig.model_construct(
        _fields_set=set(basis.request_exec_config_fields_set), **config_values
    )
    posture = resolve_execution_posture(exec_plan, configured)
    effective_posture = {
        "effective_seed": posture.seed,
        "effective_seed_source": posture.seed_source,
        "effective_mode": posture.mode,
        "effective_max_steps": posture.max_steps,
        "effective_determinism_tier": posture.determinism_tier,
        "effective_nan_guard_enabled": posture.nan_guard_enabled,
        "effective_jit": posture.jit,
        "effective_capture_env": posture.capture_env,
    }
    if any(getattr(basis, key) != value for key, value in effective_posture.items()):
        raise ValueError("source-bound risk effective execution posture does not recompute")
    if _source_core_ref(basis.data_snapshot_ref).manifest_profile_sha256 is None:
        raise ValueError("source-bound risk actual DataSnapshot selected profile is missing")
    actual_snapshot_payload = _source_typed_json_model(store, DataSnapshot, basis.data_snapshot_ref)
    _verify_data_snapshot_source_edges(store, basis.data_snapshot_ref, actual_snapshot_payload)
    if _source_core_ref(actual_snapshot_payload.data_ref).manifest_profile_sha256 is None:
        raise ValueError("source-bound risk DataSnapshot state source profile is missing")
    if basis.parameter_override_bundle_ref is None:
        expected_overrides = None
    else:
        override_payload = _source_typed_json_model(
            store, ParameterOverrideBundle, basis.parameter_override_bundle_ref
        )
        expected_overrides = {
            str(node_id): dict(values)
            for node_id, values in override_payload.overrides.items()
            if isinstance(values, dict)
        }
    if basis.parameter_overrides != expected_overrides:
        raise ValueError("source-bound risk parameter overrides differ from selected source")

    candidate_manifest = _source_manifest(store, candidate_ref)
    candidate_payload = _source_typed_json_model(
        store, PolicyCandidateSchema, candidate_ref
    ).model_dump(mode="json")
    if not isinstance(candidate_payload, Mapping) or not isinstance(
        candidate_payload.get("trinity_bundle"), Mapping
    ):
        raise ValueError("source-bound risk candidate Trinity payload is missing")
    if dict(candidate_payload["trinity_bundle"]) != trinity.model_dump(mode="json"):
        raise ValueError("source-bound risk executed Trinity differs from candidate payload")
    candidate_data_ref = _source_ref_from_parent_edge(
        store,
        candidate_manifest,
        "world_model_data_snapshot",
        expected_kind="fabric.data_snapshot",
    )
    candidate_registry_ref = _source_ref_from_parent_edge(
        store,
        candidate_manifest,
        "world_model_registry",
        expected_kind="core.registry_bundle",
    )
    if str(trinity.model_spec.data_snapshot_ref) != str(candidate_data_ref.artifact_id):
        raise ValueError("source-bound risk ModelSpec snapshot ID differs from candidate edge")
    if str(trinity.model_spec.registry_bundle_ref) != str(candidate_registry_ref.artifact_id):
        raise ValueError("source-bound risk ModelSpec registry ID differs from candidate edge")
    if _source_core_ref(basis.candidate_data_snapshot_ref) != candidate_data_ref:
        raise ValueError("source-bound risk basis candidate snapshot differs from candidate edge")
    candidate_snapshot_payload = _source_typed_json_model(
        store, DataSnapshot, basis.candidate_data_snapshot_ref
    )
    _verify_data_snapshot_source_edges(
        store, basis.candidate_data_snapshot_ref, candidate_snapshot_payload
    )
    if _source_core_ref(basis.candidate_registry_bundle_ref) != candidate_registry_ref:
        raise ValueError("source-bound risk basis candidate registry differs from candidate edge")
    if _source_core_ref(basis.data_snapshot_ref) != _source_core_ref(bindings.data_snapshot_ref):
        raise ValueError("source-bound risk runtime DataSnapshot differs from bindings")
    for role, ref in (
        ("metrics", simulation_result.metrics_ref),
        ("state_snapshot", simulation_result.state_snapshot_ref),
    ):
        if ref is None:
            raise ValueError(f"source-bound risk SimulationResult is missing {role}")
        _source_child_manifest(store, simulation_manifest, role=role, ref=_source_core_ref(ref))
    delta_edge = _source_input_by_role(simulation_manifest, "state_delta")
    delta_ref, delta_manifest = _source_manifest_for_edge(
        store,
        delta_edge,
        require_selected=True,
        expected_model=StateDelta,
    )
    delta = _source_typed_json_model(store, StateDelta, delta_ref)
    if _source_core_ref(delta.base_ref) != _source_core_ref(basis.base_state_snapshot_ref):
        raise ValueError("source-bound risk StateDelta base differs from observed execution basis")
    if _source_ref_from_parent_edge(
        store, simulation_manifest, "exec_plan", expected_kind="foundry.exec_plan"
    ) != _source_core_ref(basis.exec_plan_ref):
        raise ValueError("source-bound risk SimulationResult ExecPlan differs from basis")
    metrics_ref = _source_core_ref(simulation_result.metrics_ref)
    metrics_manifest = _source_manifest(store, metrics_ref)
    for parent_role, parent_manifest in (
        ("metrics", metrics_manifest),
        ("state_delta", delta_manifest),
    ):
        basis_edge = _source_input_by_role(parent_manifest, "execution_input_basis")
        if not _source_ref_matches_edge(basis_ref, basis_edge):
            raise ValueError(f"source-bound risk {parent_role} is detached from execution basis")
    metrics = _source_typed_json_model(store, Metrics, metrics_ref)
    if metrics.values.get("step") != basis.effective_step:
        raise ValueError("source-bound risk effective step differs from executed metrics")

    expected_inventory = _source_inventory_for_basis(store, basis)
    if _source_inventory_key(basis_manifest.inputs) != _source_inventory_key(expected_inventory):
        raise ValueError("source-bound risk basis manifest does not bind its complete source graph")
    actual_candidate_data_relation = _source_identity_relation(
        candidate_data_ref, basis.data_snapshot_ref
    )
    candidate_compile_relation = _source_identity_relation(
        candidate_registry_ref, basis.compile_registry_ref
    )
    binding_runtime_relation = _source_identity_relation(
        basis.binding_registry_ref, basis.runtime_registry_ref
    )
    compile_runtime_relation = _source_identity_relation(
        basis.compile_registry_ref, basis.runtime_registry_ref
    )
    projection = ExecutionSourceProjection(
        verification_status="recomputed_single_step_basis",
        simulation_result_ref=simulation_ref,
        execution_input_basis_ref=basis_ref,
        candidate_data_snapshot_ref=candidate_data_ref,
        execution_data_snapshot_ref=_source_core_ref(basis.data_snapshot_ref),
        candidate_to_execution_data_relation=actual_candidate_data_relation,
        candidate_registry_bundle_ref=candidate_registry_ref,
        compile_registry_bundle_ref=_source_core_ref(basis.compile_registry_ref),
        binding_registry_bundle_ref=_source_core_ref(basis.binding_registry_ref),
        runtime_registry_bundle_ref=_source_core_ref(basis.runtime_registry_ref),
        candidate_to_compile_registry_relation=candidate_compile_relation,
        binding_to_runtime_registry_relation=binding_runtime_relation,
        compile_to_runtime_registry_relation=compile_runtime_relation,
    )
    return projection, simulation_ref, simulation_manifest, basis_ref, basis_manifest


def _source_ref_from_parent_edge(
    store: ArtifactStore,
    parent_manifest: ArtifactManifest,
    role: str,
    *,
    expected_kind: str,
) -> ArtifactRef:
    edge = _source_input_by_role(parent_manifest, role)
    ref, manifest = _source_manifest_for_edge(store, edge, require_selected=True)
    if manifest.kind != expected_kind:
        raise ValueError(f"source-bound risk {role} selected artifact kind mismatch")
    return ref


def _build_source_bound_risk_observation(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_bundle_ref: ArtifactRef,
) -> tuple[SourceBoundRiskObservation, list[InputRef]]:
    """Recompute a candidate-only welfare observation from its existing CAS sources."""
    ir_store = ensure_ir_artifact_store(store)
    if candidate_ref.kind != "scientist.policy_design.candidate":
        raise ValueError("source-bound risk requires the selected policy candidate ref")
    candidate_manifest = _source_manifest(store, candidate_ref)
    if candidate_manifest.artifact_schema != _source_model_schema(PolicyCandidateSchema):
        raise ValueError("source-bound risk candidate schema mismatch")

    welfare_ref = _source_core_ref(welfare_bundle_ref)
    if welfare_ref.kind != "ir.welfare_bundle":
        raise ValueError("source-bound risk requires an ir.welfare_bundle")
    welfare_manifest = _source_manifest(store, welfare_ref)
    if (
        welfare_manifest.artifact_schema is None
        or welfare_manifest.artifact_schema.name != "ir.welfare_bundle"
        or welfare_manifest.artifact_schema.version != "1.1"
    ):
        raise ValueError("source-bound risk welfare bundle schema mismatch")
    bundle = load_welfare_bundle(
        ir_store, WelfareBundleRef.model_validate(welfare_ref.model_dump(mode="python"))
    )
    if bundle.schema_version != welfare_manifest.artifact_schema.version:
        raise ValueError("source-bound risk welfare schema version differs from its content")
    _verify_welfare_bundle_role_edges(store, welfare_manifest, bundle)
    if bundle.policy_ref is None:
        raise ValueError("welfare bundle has no policy scope claim")
    policy_ref = _source_core_ref(bundle.policy_ref)
    if policy_ref != candidate_ref:
        raise ValueError("welfare bundle policy claim differs from the selected candidate")
    policy_manifest = _source_child_manifest(
        store, welfare_manifest, role="policy_scope_claim", ref=policy_ref
    )
    if policy_manifest.kind != "scientist.policy_design.candidate":
        raise ValueError("welfare bundle policy role is not the selected candidate artifact")
    if bundle.welfare_weights_ref is None:
        raise ValueError("welfare bundle has no typed welfare weight source")
    weights_ref = _source_core_ref(bundle.welfare_weights_ref)
    weights_manifest = _source_child_manifest(
        store, welfare_manifest, role="welfare_weights", ref=weights_ref
    )
    if (
        weights_manifest.kind != "ir.welfare_weights"
        or weights_manifest.artifact_schema is None
        or weights_manifest.artifact_schema.name != "ir.welfare_weights"
        or weights_manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("welfare weight source schema mismatch")
    weight_payload = get_json_artifact(ir_store, weights_ref)
    if not isinstance(weight_payload, Mapping):
        raise ValueError("welfare weight source payload is not an object")

    if bundle.method_config_ref is None or bundle.sample_bundle_ref is None:
        raise ValueError("welfare Monte Carlo method, sample, or report ref is missing")
    method_ref = _source_core_ref(bundle.method_config_ref)
    sample_ref = _source_core_ref(bundle.sample_bundle_ref)
    method_manifest = _source_child_manifest(
        store, welfare_manifest, role="method_config", ref=method_ref
    )
    sample_manifest = _source_child_manifest(
        store, welfare_manifest, role="sample_bundle", ref=sample_ref
    )
    _source_child_manifest(store, sample_manifest, role="welfare_weights", ref=weights_ref)
    report_edge = _source_input_by_role(welfare_manifest, "propagation_report")
    report_ref = ArtifactRef(
        artifact_id=report_edge.artifact_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
        manifest_profile_sha256=report_edge.manifest_profile_sha256,
    )
    report_manifest = _source_child_manifest(
        store, welfare_manifest, role="propagation_report", ref=report_ref
    )
    if report_manifest.artifact_schema is None or (
        report_manifest.artifact_schema.name != "polisyos.foundry.WelfarePropagationReport"
    ):
        raise ValueError("welfare propagation report schema mismatch")
    if method_manifest.artifact_schema is None or (
        method_manifest.artifact_schema.name != "polisyos.foundry.WelfareMethodConfig"
        or method_manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("welfare method config schema mismatch")
    if sample_manifest.artifact_schema is None or (
        sample_manifest.artifact_schema.name != "ir.welfare_sample_bundle"
        or sample_manifest.artifact_schema.version != "1.1"
    ):
        raise ValueError("welfare sample bundle schema mismatch")

    method_payload = get_json_artifact(ir_store, method_ref)
    method_config = PropagationConfig.model_validate(method_payload, strict=True)
    sample_bundle = load_welfare_sample_bundle(
        ir_store, WelfareSampleBundleRef.model_validate(sample_ref.model_dump(mode="python"))
    )
    report_payload = get_json_artifact(ir_store, report_ref)
    if not isinstance(report_payload, Mapping):
        raise ValueError("welfare propagation report payload is not an object")
    if report_manifest.artifact_schema.version != report_payload.get("schema_version"):
        raise ValueError("welfare propagation report schema version differs from its content")
    if (
        sample_manifest.artifact_schema.version != sample_bundle.schema_version
        or sample_bundle.schema_version != "1.1"
    ):
        raise ValueError("welfare sample schema version differs from its content")
    nominal_point_estimate = _recompute_weighted_component_outputs(
        bundle, sample_bundle, weight_payload
    )
    provenance = report_payload.get("draw_outcome_provenance")
    sample_provenance = sample_bundle.metadata.get("draw_outcome_provenance")
    if not isinstance(provenance, Mapping) or dict(provenance) != sample_provenance:
        raise ValueError("welfare report and sample provenance disagree")
    outcomes = provenance.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise ValueError("welfare draw outcomes are missing")
    if any(not isinstance(outcome, Mapping) for outcome in outcomes):
        raise ValueError("welfare draw outcome record is invalid")
    requested = provenance.get("requested_draw_count")
    if type(requested) is not int or requested < 1 or requested != method_config.mc_n_samples:
        raise ValueError("welfare requested draw count differs from its method profile")
    max_attempts_per_draw = provenance.get("max_attempts_per_draw")
    if type(max_attempts_per_draw) is not int or max_attempts_per_draw < 1:
        raise ValueError("welfare maximum attempts per draw are not established")
    attempted = len(outcomes)
    successful = 0
    simulation_attempt_count = 0
    for draw_index, outcome in enumerate(outcomes):
        attempts = outcome.get("execution_attempts")
        outcome_code = outcome.get("outcome_code")
        input_digest = outcome.get("sampled_input_sha256")
        if (
            type(outcome.get("draw_index")) is not int
            or outcome.get("draw_index") != draw_index
            or not isinstance(attempts, list)
            or not attempts
            or len(attempts) > max_attempts_per_draw
            or type(outcome.get("execution_attempt_count")) is not int
            or outcome.get("execution_attempt_count") != len(attempts)
            or not isinstance(outcome_code, str)
            or not outcome_code
            or not isinstance(input_digest, str)
            or not input_digest
        ):
            raise ValueError("welfare draw execution records are incoherent")
        for attempt_number, attempt in enumerate(attempts, start=1):
            if (
                not isinstance(attempt, Mapping)
                or type(attempt.get("draw_index")) is not int
                or attempt.get("draw_index") != draw_index
                or type(attempt.get("attempt_number")) is not int
                or attempt.get("attempt_number") != attempt_number
                or not isinstance(attempt.get("outcome_code"), str)
                or not attempt.get("outcome_code")
                or attempt.get("sampled_input_sha256") != input_digest
            ):
                raise ValueError("welfare draw attempt identity is incoherent")
        if attempts[-1].get("outcome_code") != outcome_code:
            raise ValueError("welfare terminal outcome differs from its last execution attempt")
        simulation_attempt_count += len(attempts)
        if outcome_code == "success":
            if (
                type(outcome.get("sample_index")) is not int
                or outcome.get("sample_index") != successful
            ):
                raise ValueError("welfare successful draw indexes do not match sample order")
            successful += 1
        elif outcome.get("sample_index") is not None:
            raise ValueError("welfare failed draw cannot refer to a successful sample")
    failed = attempted - successful
    retry_attempt_count = simulation_attempt_count - attempted
    unattempted = requested - attempted
    if unattempted < 0:
        raise ValueError("welfare attempted draw count exceeds its requested budget")
    denominator_complete = attempted == requested
    complete = denominator_complete and successful == requested
    expected_summary_semantics: Literal[
        "complete_requested_draws", "successful_draws_only_conditional_on_execution"
    ] = "complete_requested_draws" if complete else "successful_draws_only_conditional_on_execution"
    source_counts = {
        "attempted_draw_count": attempted,
        "successful_draw_count": successful,
        "failed_draw_count": failed,
        "unattempted_draw_count": unattempted,
        "simulation_attempt_count": simulation_attempt_count,
        "retry_attempt_count": retry_attempt_count,
    }
    if (
        any(
            type(provenance.get(name)) is not int or provenance.get(name) != value
            for name, value in source_counts.items()
        )
        or provenance.get("outcome_denominator_complete") is not denominator_complete
        or provenance.get("summary_semantics") != expected_summary_semantics
    ):
        raise ValueError("welfare draw counters do not recompute from terminal outcomes")
    valid_draw_count = len(sample_bundle.welfare_draws)
    if (
        valid_draw_count != successful
        or valid_draw_count < 1
        or len(sample_bundle.welfare_pe_draws) != valid_draw_count
        or len(sample_bundle.welfare_ge_draws) != valid_draw_count
        or type(report_payload.get("valid_draw_count")) is not int
        or report_payload.get("valid_draw_count") != valid_draw_count
    ):
        raise ValueError("welfare draw count differs from persisted sample contents")
    expected_summary = {
        "welfare_mean": float(np.mean(np.asarray(sample_bundle.welfare_draws, dtype=np.float64))),
        "welfare_std": float(np.std(np.asarray(sample_bundle.welfare_draws, dtype=np.float64))),
        "welfare_pe_mean": float(
            np.mean(np.asarray(sample_bundle.welfare_pe_draws, dtype=np.float64))
        ),
        "welfare_ge_mean": float(
            np.mean(np.asarray(sample_bundle.welfare_ge_draws, dtype=np.float64))
        ),
    }
    summary_key = "draw_summary" if complete else "conditional_draw_summary"
    if report_payload.get(summary_key) != expected_summary:
        raise ValueError("welfare report summary does not recompute from persisted samples")
    if report_payload.get("methods") != ["monte_carlo"]:
        raise ValueError("welfare report method differs from the bundle method")

    expected_interval = None
    if complete:
        alpha = max((1.0 - method_config.confidence_level) / 2.0, 0.0)
        values = np.asarray(sample_bundle.welfare_draws, dtype=np.float64)
        expected_interval = (
            float(np.quantile(values, alpha)),
            float(np.quantile(values, 1.0 - alpha)),
        )
    if bundle.credible_interval != expected_interval:
        raise ValueError("welfare bundle interval does not recompute from persisted samples")
    expected_semantics = (
        WelfareIntervalSemantics.MIXED_NESTED
        if complete and bundle.robust_interval is not None
        else WelfareIntervalSemantics.CREDIBLE
        if complete
        else WelfareIntervalSemantics.ROBUST_OUTER
        if bundle.robust_interval is not None
        else WelfareIntervalSemantics.NONE
    )
    if bundle.interval_semantics is not expected_semantics:
        raise ValueError("welfare interval semantics differ from its recomputed contents")
    expected_method = (
        WelfareMethod.MIXED_NESTED
        if complete and bundle.robust_interval is not None
        else WelfareMethod.MONTE_CARLO
        if complete
        else WelfareMethod.INTERVAL_OUTER
        if bundle.robust_interval is not None
        else WelfareMethod.MONTE_CARLO
    )
    if bundle.method_used is not expected_method:
        raise ValueError("welfare method label differs from its recomputed interval contents")

    execution_source, simulation_ref, simulation_manifest, basis_ref, basis_manifest = (
        _recompute_execution_source(
            store, candidate_ref=candidate_ref, welfare_manifest=welfare_manifest
        )
    )
    _source_child_manifest(store, welfare_manifest, role="execution_input_basis", ref=basis_ref)
    _source_child_manifest(store, welfare_manifest, role="policy_scope_claim", ref=policy_ref)
    _source_child_manifest(store, welfare_manifest, role="welfare_weights", ref=weights_ref)
    simulation_result = _source_typed_json_model(store, SimulationResult, simulation_ref)
    if simulation_result.metrics_ref is None:
        raise ValueError("source-bound risk SimulationResult has no Metrics source")
    metrics_ref = _source_core_ref(simulation_result.metrics_ref)
    _source_child_manifest(store, welfare_manifest, role="metrics", ref=metrics_ref)
    for source_manifest in (method_manifest, report_manifest, sample_manifest):
        _source_child_manifest(store, source_manifest, role="execution_input_basis", ref=basis_ref)
    _source_child_manifest(store, report_manifest, role="sample_bundle", ref=sample_ref)
    inputs = _source_observation_inputs(
        store,
        candidate_ref=candidate_ref,
        welfare_ref=welfare_ref,
        policy_ref=policy_ref,
        weights_ref=weights_ref,
        method_ref=method_ref,
        report_ref=report_ref,
        sample_ref=sample_ref,
        source_manifests=(
            ("welfare_bundle", welfare_manifest),
            ("welfare_method", method_manifest),
            ("welfare_report", report_manifest),
            ("welfare_sample", sample_manifest),
            ("welfare_weights", weights_manifest),
            ("simulation_result", simulation_manifest),
            ("execution_input_basis", basis_manifest),
        ),
    )
    inputs.extend(
        [
            input_ref_from_artifact_ref(simulation_ref, role="execution.simulation_result"),
            input_ref_from_artifact_ref(basis_ref, role="execution.input_basis"),
        ]
    )
    observation = SourceBoundRiskObservation(
        candidate_ref=candidate_ref,
        welfare_bundle_ref=welfare_ref,
        policy_scope_claim_ref=policy_ref,
        welfare_weights_ref=weights_ref,
        weight_application_status="recomputed_from_component_draws",
        method_config_ref=method_ref,
        propagation_report_ref=report_ref,
        sample_bundle_ref=sample_ref,
        execution_source=execution_source,
        welfare_measure=bundle.welfare_measure,
        method_used=bundle.method_used,
        source_status=bundle.status,
        confidence_level=method_config.confidence_level,
        mc_sampling_method=method_config.mc_sampling_method,
        observed_at=welfare_manifest.created_at,
        nominal_point_estimate=nominal_point_estimate,
        welfare_draw_mean=expected_summary["welfare_mean"],
        welfare_draw_std=expected_summary["welfare_std"],
        draw_summary_semantics=expected_summary_semantics,
        credible_interval=bundle.credible_interval,
        interval_semantics=bundle.interval_semantics,
        draw_completion_status="complete" if complete else "partial",
        requested_draw_count=requested,
        attempted_draw_count=attempted,
        successful_draw_count=successful,
        failed_draw_count=failed,
        unattempted_draw_count=unattempted,
        valid_draw_count=valid_draw_count,
        simulation_attempt_count=simulation_attempt_count,
        retry_attempt_count=retry_attempt_count,
    )
    return observation, inputs


def persist_source_bound_risk_observation(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_bundle_ref: ArtifactRef,
) -> ArtifactRef:
    """Persist one raw candidate measurement with exact source/profile edges."""
    observation, inputs = _build_source_bound_risk_observation(
        store, candidate_ref=candidate_ref, welfare_bundle_ref=welfare_bundle_ref
    )
    ref = store.put_json(
        observation.model_dump(mode="json"),
        PutOptions(
            kind=_SOURCE_BOUND_RISK_OBSERVATION_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=_SOURCE_BOUND_RISK_OBSERVATION_SCHEMA,
                version=_SOURCE_BOUND_RISK_OBSERVATION_VERSION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    resolved_ref = ArtifactRef.model_validate(ref)
    if resolved_ref.manifest_profile_sha256 is None:
        raise ValueError("source-bound risk observation selected profile is missing")
    return resolved_ref


def load_source_bound_risk_observation(
    store: ArtifactStore,
    observation_ref: ArtifactRef,
    expected_candidate_ref: ArtifactRef,
) -> SourceBoundRiskObservation:
    """Freshly re-resolve and recompute an observation before audit projection."""
    from polisyos.core.artifacts import load_core_json_artifact

    if observation_ref.kind != _SOURCE_BOUND_RISK_OBSERVATION_KIND:
        raise ValueError("source-bound risk observation kind mismatch")
    manifest = _source_manifest(store, observation_ref)
    schema = manifest.artifact_schema
    if (
        schema is None
        or schema.name != _SOURCE_BOUND_RISK_OBSERVATION_SCHEMA
        or schema.version != _SOURCE_BOUND_RISK_OBSERVATION_VERSION
    ):
        raise ValueError("source-bound risk observation schema mismatch")
    observation = SourceBoundRiskObservation.model_validate(
        load_core_json_artifact(store, observation_ref)
    )
    if observation.candidate_ref != expected_candidate_ref:
        raise ValueError("source-bound risk observation belongs to another candidate view")
    expected, expected_inputs = _build_source_bound_risk_observation(
        store,
        candidate_ref=expected_candidate_ref,
        welfare_bundle_ref=observation.welfare_bundle_ref,
    )
    if observation != expected:
        raise ValueError("source-bound risk observation differs from recomputed source contents")

    def input_key(items: list[InputRef]) -> list[tuple[str, str, str | None]]:
        return sorted(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in items
        )

    if input_key(manifest.inputs) != input_key(expected_inputs):
        raise ValueError("source-bound risk observation selected input edges changed")
    return observation
