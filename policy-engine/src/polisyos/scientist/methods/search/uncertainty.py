"""Typed search uncertainty contracts for funnel routing and judge semantics."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from threading import Lock, local
from typing import TYPE_CHECKING, Annotated, Any, BinaryIO, Literal, Protocol, runtime_checkable

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
    InputRef,
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    ensure_directory_durable,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    matches_runtime_protocol,
    resolve_manifest_by_profile,
    write_bytes_atomic,
)
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.canon import CanonSpec

if TYPE_CHECKING:
    from types import TracebackType

    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
    from polisyos.ir.analytics import HTEOutcome
from polisyos.core.contracts import (
    DataSnapshot,
    FoundryExecutionInputBasisRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.foundry.execute import admit_execution_source
from polisyos.foundry.uncertainty import PropagationConfig
from polisyos.ir import (
    ArtifactRefModel,
    TrinityBundle,
    UncertaintyType,
    WelfareBundle,
    WelfareBundleRef,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareSampleBundle,
    WelfareSampleBundleRef,
    WelfareStatus,
    get_json_artifact,
    load_welfare_bundle,
    load_welfare_sample_bundle,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


@runtime_checkable
class SearchUncertaintyStore(CoreJSONArtifactStore, Protocol):
    """Profile-aware artifact store with the root used by Search's existing CAS owner."""

    @property
    def root(self) -> Path: ...


def resolve_search_uncertainty_store(raw_store: object) -> SearchUncertaintyStore | None:
    """Resolve Search's native Core owner from an optional IR adapter."""
    candidate = (
        raw_store.store if isinstance(raw_store, CoreToIRArtifactStoreAdapter) else raw_store
    )
    if not isinstance(candidate, SearchUncertaintyStore):
        return None
    if not isinstance(candidate.root, Path):
        return None
    return candidate


class _SearchUncertaintyPhysicalInputStore(
    SearchUncertaintyStore,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Use-site view of Search storage after the bounded physical-input guard."""


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


def search_uncertainty_observation_ref(
    payload: Mapping[str, object],
) -> ArtifactRef | None:
    """Read a native producer ref for later content-bound intake, without admission."""
    raw = payload.get("uncertainty_observation_ref")
    if raw is None:
        return None
    try:
        return ArtifactRef.model_validate(raw)
    except TypeError, ValueError:
        return None


def persist_search_uncertainty(
    store: SearchUncertaintyStore,
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
        return_selected_profile=True,
    )


def load_search_uncertainty_observation(
    store: SearchUncertaintyStore,
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
    if not _source_refs_equal(basis.subject_ref, expected_subject_ref):
        raise ValueError("Search uncertainty basis differs from the configured candidate")
    observation = SearchUncertaintyObservation.model_validate(
        load_core_json_artifact(store, observation_ref)
    )
    if not _source_refs_equal(observation.basis_ref, expected_basis_ref):
        raise ValueError("Search uncertainty observation has a foreign or stale basis")
    if not _source_refs_equal(observation.producer_ref, basis.producer_ref):
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
        "same_selected_ref",
        "same_artifact_id_different_profile",
        "different_artifact_id",
    ]
    candidate_registry_bundle_ref: ArtifactRef
    compile_registry_bundle_ref: ArtifactRef
    binding_registry_bundle_ref: ArtifactRef
    runtime_registry_bundle_ref: ArtifactRef
    candidate_to_compile_registry_relation: Literal[
        "same_selected_ref",
        "same_artifact_id_different_profile",
        "different_artifact_id",
    ]
    binding_to_runtime_registry_relation: Literal[
        "same_selected_ref",
        "same_artifact_id_different_profile",
        "different_artifact_id",
    ]
    compile_to_runtime_registry_relation: Literal[
        "same_selected_ref",
        "same_artifact_id_different_profile",
        "different_artifact_id",
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


def _source_refs_equal(
    left: ArtifactRef | ArtifactRefModel,
    right: ArtifactRef | ArtifactRefModel,
) -> bool:
    """Compare complete selected identities independent of DTO subclass."""
    return artifact_ref_identity_key(_source_core_ref(left)) == artifact_ref_identity_key(
        _source_core_ref(right)
    )


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
    if not _source_refs_equal(resolved_ref, ref):
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
        if not _source_refs_equal(selected_ref, _source_core_ref(raw_ref)):
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
    left_key = artifact_ref_identity_key(left_ref)
    right_key = artifact_ref_identity_key(right_ref)
    if left_key == right_key:
        return "same_selected_ref"
    if left_key[0] != right_key[0]:
        return "different_artifact_id"
    if left_key[3] != right_key[3]:
        return "same_artifact_id_different_profile"
    raise ValueError("source-bound risk refs share a profile but differ in kind or media type")


def _source_inventory_key(items: Iterable[InputRef]) -> list[tuple[str, str, str | None]]:
    return sorted(
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in items
    )


def _recompute_execution_source(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_manifest: ArtifactManifest,
) -> tuple[
    ExecutionSourceProjection,
    ArtifactRef,
    ArtifactManifest,
    ArtifactRef,
    ArtifactManifest,
]:
    """Join the admitted Foundry source basis to its welfare candidate context."""
    simulation_edge = _source_input_by_role(welfare_manifest, "simulation_result")
    simulation_ref, _simulation_manifest = _source_manifest_for_edge(
        store,
        simulation_edge,
        require_selected=True,
        expected_model=SimulationResult,
    )
    reason_mapping = {
        "execution_source_status_has_no_admitted_mode": (
            "source-bound risk single-step execution basis is missing"
        ),
        "execution_source_basis_selected_profile_missing": (
            "source-bound risk selected execution basis profile is missing"
        ),
        "execution_source_requires_one_execution_input_basis_edge": (
            "source-bound risk requires one execution_input_basis lineage edge"
        ),
        "execution_source_basis_ref_differs_from_exact_result_edge": (
            "source-bound risk execution_input_basis edge differs from typed basis ref"
        ),
        "execution_source_basis_schema_mismatch": (
            "source-bound risk execution basis schema mismatch"
        ),
        "execution_source_basis_request_did_not_explicitly_select_profiles": (
            "source-bound risk execution basis was not produced with selected refs"
        ),
        "execution_source_basis_request_fields_set_invalid": (
            "source-bound risk request fields-set contains unknown fields"
        ),
        "execution_source_basis_exec_config_fields_set_invalid": (
            "source-bound risk execution-config fields-set contains unknown fields"
        ),
        "execution_source_basis_request_refs_disagree": (
            "source-bound risk execution basis request refs disagree"
        ),
        "execution_source_basis_request_does_not_match_result_inputs": (
            "source-bound risk execution basis request refs disagree"
        ),
        "execution_source_basis_manifest_does_not_bind_complete_source_graph": (
            "source-bound risk basis manifest does not bind its complete source graph"
        ),
        "execution_source_basis_graph_differs_from_exec_plan": (
            "source-bound risk execution basis graph differs from ExecPlan"
        ),
        "execution_source_basis_trinity_differs_from_program_graph": (
            "source-bound risk execution basis Trinity source differs from ProgramGraph"
        ),
        "execution_source_edge_payload_disagrees:program_graph": (
            "source-bound risk ExecPlan manifest names another ProgramGraph"
        ),
        "execution_source_edge_payload_disagrees:ir": (
            "source-bound risk ProgramGraph manifest names another Trinity source"
        ),
        "execution_source_edge_payload_disagrees:registry_bundle": (
            "source-bound risk compile registry differs from ProgramGraph"
        ),
        "execution_source_edge_payload_disagrees:policy_candidate": (
            "source-bound risk Trinity source names another candidate"
        ),
        "execution_source_basis_bindings_disagree": (
            "source-bound risk execution basis bindings disagree"
        ),
        "execution_source_edge_payload_disagrees:input.data_snapshot_ref": (
            "source-bound risk execution basis bindings disagree"
        ),
        "execution_source_edge_payload_disagrees:input.registry_bundle_ref": (
            "source-bound risk execution basis bindings disagree"
        ),
        "execution_source_edge_payload_disagrees:artifact.bound_state_snapshot_ref": (
            "source-bound risk execution basis bindings disagree"
        ),
        "execution_source_edge_payload_disagrees:input.input_bindings_ref": (
            "source-bound risk execution basis request refs disagree"
        ),
        "execution_source_edge_payload_disagrees:input.bound_state_snapshot_ref": (
            "source-bound risk execution basis bindings disagree"
        ),
        "execution_source_basis_registry_members_disagree": (
            "source-bound risk registry bundle payload differs from selected members"
        ),
        "execution_source_feedback_basis_uncomposed": (
            "source-bound risk feedback execution basis is uncomposed"
        ),
        "execution_source_basis_effective_posture_does_not_recompute": (
            "source-bound risk effective execution posture does not recompute"
        ),
        "execution_source_data_snapshot_profile_missing": (
            "source-bound risk actual DataSnapshot selected profile is missing"
        ),
        "execution_source_data_snapshot_state_profile_missing": (
            "source-bound risk DataSnapshot state source profile is missing"
        ),
        "execution_source_data_snapshot_requires_selected_edge:data_ref": (
            "source-bound risk DataSnapshot data_ref edge differs from payload"
        ),
        "execution_source_data_snapshot_unexpected_edge:data_ref": (
            "source-bound risk DataSnapshot has unexpected data_ref edge"
        ),
        "execution_source_basis_parameter_overrides_disagree": (
            "source-bound risk parameter overrides differ from selected source"
        ),
        "execution_source_state_delta_base_differs_from_basis": (
            "source-bound risk StateDelta base differs from observed execution basis"
        ),
        "execution_source_metrics_step_differs_from_basis": (
            "source-bound risk effective step differs from executed metrics"
        ),
    }
    typed_simulation_ref = SimulationResultRef.model_validate(
        simulation_ref.model_dump(mode="python")
    )
    try:
        source_context = admit_execution_source(store, typed_simulation_ref)
    except ValueError as exc:
        mapped_reason = reason_mapping.get(str(exc))
        if mapped_reason is None:
            raise
        raise ValueError(mapped_reason) from exc
    if source_context.mode == "feedback_uncomposed":
        raise ValueError("source-bound risk feedback execution basis is uncomposed")
    if source_context.mode != "single_step_basis":
        raise ValueError("source-bound risk single-step execution basis is missing")
    simulation_manifest = source_context.simulation_manifest
    basis_ref = source_context.basis_ref
    basis = source_context.basis
    basis_manifest = source_context.basis_manifest
    if basis_ref is None or basis is None or basis_manifest is None:
        raise ValueError("source-bound risk single-step execution basis is missing")
    basis_inventory = source_context.basis_inventory
    if basis_inventory is None:
        raise ValueError("source-bound risk selected execution basis has no recomputed inventory")
    if _source_inventory_key(basis_inventory) != _source_inventory_key(basis_manifest.inputs):
        raise ValueError(
            "source-bound risk admitted basis inventory differs from selected manifest"
        )
    if not _source_refs_equal(_source_core_ref(basis.candidate_ref), candidate_ref):
        raise ValueError("source-bound risk execution basis request refs disagree")

    candidate_manifest = _source_manifest(store, candidate_ref)
    candidate_payload = _source_typed_json_model(
        store, PolicyCandidateSchema, candidate_ref
    ).model_dump(mode="json")
    trinity = _source_typed_json_model(store, TrinityBundle, basis.trinity_bundle_ref)
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
    if not _source_refs_equal(
        _source_core_ref(basis.candidate_data_snapshot_ref), candidate_data_ref
    ):
        raise ValueError("source-bound risk basis candidate snapshot differs from candidate edge")
    candidate_snapshot_payload = _source_typed_json_model(
        store, DataSnapshot, basis.candidate_data_snapshot_ref
    )
    _verify_data_snapshot_source_edges(
        store, basis.candidate_data_snapshot_ref, candidate_snapshot_payload
    )
    if not _source_refs_equal(
        _source_core_ref(basis.candidate_registry_bundle_ref), candidate_registry_ref
    ):
        raise ValueError("source-bound risk basis candidate registry differs from candidate edge")

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
    if not _source_refs_equal(policy_ref, candidate_ref):
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
        ir_store,
        WelfareSampleBundleRef.model_validate(sample_ref.model_dump(mode="python")),
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
    if not _source_refs_equal(observation.candidate_ref, expected_candidate_ref):
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


# AD06 versioned current-state implementation extends the canonical uncertainty owner.
class SearchInputDependency(BaseModel):
    """One role-qualified member of an owner-derived selected input graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_path: str = Field(min_length=1)
    ref: ArtifactRef


class SearchOwnerSelectedSourceGraph(BaseModel):
    """Direct source refs selected by the Scientist owner for one policy run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    roots: tuple[SearchInputDependency, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_roots(self) -> SearchOwnerSelectedSourceGraph:
        roles = [item.role_path for item in self.roots]
        if len(roles) != len(set(roles)):
            raise ValueError("selected runtime source graph has duplicate root roles")
        if any(item.ref.manifest_profile_sha256 is None for item in self.roots):
            raise ValueError("selected runtime source roots must carry exact manifest profiles")
        return self


class SearchRuntimeStageConfiguration(BaseModel):
    """Readback of the instantiated Search stage stack and resolved scalar config."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    owner_fqn: Literal[
        "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine.run_runtime_funnel"
    ]
    stages: tuple[dict[str, str | int | float | bool | None], ...] = Field(min_length=1)
    unresolved_bindings: tuple[str, ...] = ()
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _finite_configuration(self) -> SearchRuntimeStageConfiguration:
        stage_names: list[str] = []
        fidelity_levels: list[int] = []
        for stage in self.stages:
            name = stage.get("stage_name")
            level = stage.get("fidelity_level")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("runtime stage configuration requires each stage name")
            if type(level) is not int or level < 0:
                raise ValueError("runtime stage configuration requires nonnegative integer levels")
            stage_names.append(name)
            fidelity_levels.append(level)
        if len(stage_names) != len(set(stage_names)):
            raise ValueError("runtime stage configuration repeats a stage name")
        if len(fidelity_levels) != len(set(fidelity_levels)):
            raise ValueError("runtime stage configuration repeats a fidelity level")
        if fidelity_levels != sorted(fidelity_levels):
            raise ValueError("runtime stage configuration must preserve execution order")
        for stage in self.stages:
            for value in stage.values():
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("runtime stage configuration must be finite")
        return self


class SearchUncertaintySemanticScope(BaseModel):
    """Owner-selected stable treatment-effect scope for one Search obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    quantity_ref: ArtifactRef
    treatment_contrast_ref: ArtifactRef
    population_ref: ArtifactRef
    outcome_ref: ArtifactRef
    unit_scope_ref: ArtifactRef | None = None
    unit_binding_status: Literal["bound", "unknown"]
    treatment_variable_id: str = Field(min_length=1)
    outcome_variable_id: str = Field(min_length=1)
    control_value: float = Field(strict=True)
    treated_value: float = Field(strict=True)
    requested_target_scope: Literal["selected_evaluation_rows", "population"]

    @model_validator(mode="after")
    def _selected_scope(self) -> SearchUncertaintySemanticScope:
        refs = (
            self.quantity_ref,
            self.treatment_contrast_ref,
            self.population_ref,
            self.outcome_ref,
        )
        if self.unit_scope_ref is not None:
            refs = (*refs, self.unit_scope_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("selected uncertainty scope requires profiled owner refs")
        if self.unit_binding_status == "bound" and self.unit_scope_ref is None:
            raise ValueError("bound uncertainty unit requires a source-owned scope ref")
        if self.unit_binding_status == "unknown" and self.unit_scope_ref is not None:
            raise ValueError("unknown uncertainty unit cannot carry a scope ref")
        if self.treatment_variable_id == self.outcome_variable_id:
            raise ValueError("uncertainty treatment and outcome variables must differ")
        if any(not math.isfinite(value) for value in (self.control_value, self.treated_value)):
            raise ValueError("selected treatment contrast must use finite values")
        if self.control_value == self.treated_value:
            raise ValueError("selected treatment contrast must contain distinct values")
        return self


class SearchUncertaintyHTERequestProjection(BaseModel):
    """Typed HTE request selectors frozen by the Search ticket owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    estimand: Literal["mean_effect_over_selected_x"]
    target_scope: Literal["selected_evaluation_rows", "population"]
    outcome_variable_id: str = Field(min_length=1)
    treatment_variable_id: str = Field(min_length=1)
    control_value: float = Field(strict=True)
    treated_value: float = Field(strict=True)
    alpha: float = Field(strict=True, gt=0.0, lt=1.0)
    requested_guarantee: (
        Literal["candidate_point", "backend_conditional_interval", "population_sampling_coverage"]
        | None
    ) = None

    @model_validator(mode="after")
    def _finite_contrast(self) -> SearchUncertaintyHTERequestProjection:
        if self.outcome_variable_id == self.treatment_variable_id:
            raise ValueError("HTE request variables must be distinct")
        if any(not math.isfinite(value) for value in (self.control_value, self.treated_value)):
            raise ValueError("HTE request contrast must be finite")
        if self.control_value == self.treated_value:
            raise ValueError("HTE request contrast arms must differ")
        return self


class SearchUncertaintyOwnerTaskContext(BaseModel):
    """Immutable Search submission context assembled by the Scientist task owner.

    This model is an input record, not proof by self-label. Search independently
    resolves every selected ref and recomputes the complete manifest closure.
    Missing method or scope owners remain explicit and disable current-assessment
    admission while candidate execution continues.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    owner_fqn: Literal[
        "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine.run_runtime_funnel"
    ]
    run_id: str = Field(min_length=1)
    subject_ref: ArtifactRef
    selected_plan_ref: ArtifactRef | None = None
    selected_configuration_ref: ArtifactRef | None = None
    selected_source_graph_ref: ArtifactRef | None = None
    selected_rule_ref: ArtifactRef | None = None
    selected_profile_ref: ArtifactRef | None = None
    selected_procedure_ref: ArtifactRef | None = None
    selected_selection_ref: ArtifactRef | None = None
    selected_method_fqn: str | None = None
    selected_method_abi_version: str | None = None
    selected_method_abi_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    selected_method_params_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    selected_method_params: dict[str, Any] | None = None
    selected_method_seed: int | None = Field(default=None, ge=0, le=4_294_967_295, strict=True)
    selected_inference_profile_id: str | None = None
    selected_method_input_ref: ArtifactRef | None = None
    selected_method_input_content_sha256: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    request_projection: SearchUncertaintyHTERequestProjection | None = None
    tenant_id: str | None = Field(default=None, min_length=1, max_length=128)
    cell_id: str | None = Field(default=None, min_length=1, max_length=128)
    semantic_scope: SearchUncertaintySemanticScope | None = None
    selected_stage_config_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_state_input_refs: tuple[SearchInputDependency, ...] = ()
    status: Literal["ready", "not_established"]
    missing_slices: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _complete_owner_context(self) -> SearchUncertaintyOwnerTaskContext:
        required_refs = (
            self.subject_ref,
            self.selected_plan_ref,
            self.selected_configuration_ref,
            self.selected_source_graph_ref,
            self.selected_rule_ref,
            self.selected_profile_ref,
            self.selected_procedure_ref,
            self.selected_selection_ref,
        )
        required_method = (
            self.selected_method_fqn,
            self.selected_method_abi_version,
            self.selected_method_abi_digest,
            self.selected_method_params_sha256,
            self.selected_method_params,
            self.selected_inference_profile_id,
        )
        derived_missing: set[str] = set()
        if self.semantic_scope is None:
            derived_missing.add("semantic_scope_owner")
        if self.request_projection is None:
            derived_missing.add("owned_hte_request_projection")
        elif self.semantic_scope is None or (
            self.request_projection.target_scope != self.semantic_scope.requested_target_scope
            or self.request_projection.outcome_variable_id
            != self.semantic_scope.outcome_variable_id
            or self.request_projection.treatment_variable_id
            != self.semantic_scope.treatment_variable_id
            or self.request_projection.control_value != self.semantic_scope.control_value
            or self.request_projection.treated_value != self.semantic_scope.treated_value
        ):
            raise ValueError("HTE request projection differs from the selected Search scope")
        if self.tenant_id is None:
            derived_missing.add("owner_tenant_scope")
        if self.selected_method_seed is None:
            derived_missing.add("selected_method_seed")
        if self.selected_method_input_ref is None:
            derived_missing.add("selected_method_input_owner")
        if self.selected_method_input_content_sha256 is None:
            derived_missing.add("selected_method_input_content_digest")
        if self.selected_method_input_ref is not None:
            if self.selected_method_input_ref.manifest_profile_sha256 is None:
                raise ValueError("selected HTE method input requires a manifest profile")
            if (
                self.selected_method_input_content_sha256 is not None
                and self.selected_method_input_ref.artifact_id.hex
                != self.selected_method_input_content_sha256
            ):
                raise ValueError("selected HTE input digest differs from its CAS identity")
        if any(ref is None for ref in required_refs[1:]):
            derived_missing.add(
                "selected_executable_plan_configuration_graph_rule_profile_procedure_selection"
            )
        if any(value is None or not str(value).strip() for value in required_method):
            derived_missing.add("selected_method_abi_params_profile")
        if (
            self.selected_method_params is not None
            and self.selected_method_params_sha256 is not None
        ):
            try:
                params_digest = _canonical_sha256(self.selected_method_params)
            except TypeError, ValueError:
                derived_missing.add("selected_method_params_not_canonical")
            else:
                if params_digest != self.selected_method_params_sha256:
                    raise ValueError("selected method params digest differs from owner mapping")
        refs = tuple(ref for ref in required_refs if ref is not None)
        refs += tuple(item.ref for item in self.selected_state_input_refs)
        if self.selected_method_input_ref is not None:
            refs += (self.selected_method_input_ref,)
        if self.semantic_scope is not None:
            scope_refs = (
                self.semantic_scope.quantity_ref,
                self.semantic_scope.treatment_contrast_ref,
                self.semantic_scope.population_ref,
                self.semantic_scope.outcome_ref,
                self.semantic_scope.unit_scope_ref,
            )
            refs += tuple(ref for ref in scope_refs if ref is not None)
        state_roles = [item.role_path for item in self.selected_state_input_refs]
        if len(state_roles) != len(set(state_roles)):
            raise ValueError("owner task context repeats a selected state-input role")
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("owner task context selected refs must carry manifest profiles")
        declared_missing = set(self.missing_slices)
        if not derived_missing.issubset(declared_missing):
            raise ValueError("owner context must name every unresolved required slice")
        if self.status == "ready" and (derived_missing or declared_missing):
            raise ValueError("ready owner task context has unresolved required slices")
        if self.status == "not_established" and not declared_missing:
            raise ValueError("not-established owner context must identify its unresolved slices")
        if any(not value.strip() for value in self.missing_slices):
            raise ValueError("owner context missing slice labels must be non-empty")
        if len(self.missing_slices) != len(declared_missing):
            raise ValueError("owner context missing slices must be unique")
        return self


class SearchUncertaintyTaskBinding(BaseModel):
    """Immutable Search-owned admission bound to one actual FunnelTicket."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    ticket_id: str = Field(min_length=1, max_length=128)
    parent_run_id: str = Field(min_length=1, max_length=128)
    ticket_generation: int = Field(ge=1, strict=True)
    owner_revision: int = Field(ge=1, strict=True)
    projection_revision: int = Field(ge=1, strict=True)
    source_projection_ref: ArtifactRef
    task_admission_ref: ArtifactRef
    task_epoch_ref: ArtifactRef
    owner_context_ref: ArtifactRef
    basis_ref: ArtifactRef
    dependency_inventory_ref: ArtifactRef
    dependency_inventory_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tenant_id: str = Field(min_length=1, max_length=128)
    cell_id: str | None = Field(default=None, min_length=1, max_length=128)
    request_projection: SearchUncertaintyHTERequestProjection
    selected_method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    selected_method_abi_version: Literal["2.0.0"]
    selected_method_abi_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_method_params_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_method_params: dict[str, Any]
    selected_method_seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    selected_inference_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    selected_method_input_ref: ArtifactRef
    selected_method_input_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    admitted_at: AwareDatetime

    @model_validator(mode="after")
    def _profiled_owner_refs(self) -> SearchUncertaintyTaskBinding:
        expected = (
            (self.source_projection_ref, "scientist.search.uncertainty_ticket_projection"),
            (self.task_admission_ref, "scientist.search.uncertainty_task_admission"),
            (self.task_epoch_ref, "scientist.search.uncertainty_task_epoch"),
            (self.owner_context_ref, "scientist.search.uncertainty_owner_task_context"),
            (self.basis_ref, "scientist.search.uncertainty_basis"),
            (self.dependency_inventory_ref, "scientist.search.uncertainty_input_inventory"),
        )
        for ref, kind in expected:
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("Search task binding contains an unselected owner ref")
        if self.selected_method_input_ref.manifest_profile_sha256 is None:
            raise ValueError("Search task binding requires the selected input manifest profile")
        if (
            self.selected_method_input_ref.artifact_id.hex
            != self.selected_method_input_content_sha256
        ):
            raise ValueError("Search task binding input digest differs from its CAS identity")
        if _canonical_sha256(self.selected_method_params) != self.selected_method_params_sha256:
            raise ValueError("Search task binding params digest differs from owner mapping")
        return self


class SearchUncertaintyTaskBindingResolution(BaseModel):
    """Typed result of recomputing current or historical Search binding closure."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    resolution_status: Literal["current", "historical"]
    closure_status: Literal["recomputed"] = "recomputed"
    binding_ref: ArtifactRef
    binding: SearchUncertaintyTaskBinding
    binding_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    ticket_id: str = Field(min_length=1, max_length=128)
    ticket_generation: int = Field(ge=1, strict=True)
    owner_revision: int = Field(ge=1, strict=True)
    projection_revision: int = Field(ge=1, strict=True)
    projection_ref: ArtifactRef
    task_admission_ref: ArtifactRef
    task_epoch_ref: ArtifactRef
    owner_context_ref: ArtifactRef
    basis_ref: ArtifactRef
    dependency_inventory_ref: ArtifactRef
    dependency_inventory_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_projection_ref: ArtifactRef
    request_projection: SearchUncertaintyHTERequestProjection
    selected_method_fqn: str = Field(min_length=1)
    selected_method_abi_version: str = Field(min_length=1)
    selected_method_abi_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_method_params_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_method_params: dict[str, Any]
    selected_method_seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    selected_inference_profile_id: str = Field(min_length=1)
    selected_method_input_ref: ArtifactRef
    selected_method_input_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tenant_id: str = Field(min_length=1, max_length=128)
    cell_id: str | None = Field(default=None, min_length=1, max_length=128)
    admitted_at: AwareDatetime
    resolved_at: AwareDatetime

    @model_validator(mode="after")
    def _matches_binding(self) -> SearchUncertaintyTaskBindingResolution:
        b = self.binding
        refs = (
            (self.binding_ref, "scientist.search.uncertainty_task_binding"),
            (self.projection_ref, "scientist.search.uncertainty_ticket_projection"),
            (self.source_projection_ref, "scientist.search.uncertainty_ticket_projection"),
        )
        if any(
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in refs
        ):
            raise ValueError("Search task binding resolution refs are not profile-selected")
        if self.binding_content_sha256 != self.binding_ref.artifact_id.hex:
            raise ValueError("Search task binding content digest differs from its ref")
        if (
            self.ticket_id != b.ticket_id
            or self.ticket_generation != b.ticket_generation
            or self.owner_revision != b.owner_revision
            or self.projection_revision != b.projection_revision
            or self.projection_ref != b.source_projection_ref
            or self.source_projection_ref != b.source_projection_ref
            or self.request_projection != b.request_projection
            or self.task_admission_ref != b.task_admission_ref
            or self.task_epoch_ref != b.task_epoch_ref
            or self.owner_context_ref != b.owner_context_ref
            or self.basis_ref != b.basis_ref
            or self.dependency_inventory_ref != b.dependency_inventory_ref
            or self.dependency_inventory_sha256 != b.dependency_inventory_sha256
            or self.selected_method_fqn != b.selected_method_fqn
            or self.selected_method_abi_version != b.selected_method_abi_version
            or self.selected_method_abi_digest != b.selected_method_abi_digest
            or self.selected_method_params_sha256 != b.selected_method_params_sha256
            or self.selected_method_params != b.selected_method_params
            or self.selected_method_seed != b.selected_method_seed
            or self.selected_inference_profile_id != b.selected_inference_profile_id
            or self.selected_method_input_ref != b.selected_method_input_ref
            or self.selected_method_input_content_sha256 != b.selected_method_input_content_sha256
            or self.tenant_id != b.tenant_id
            or self.cell_id != b.cell_id
            or self.admitted_at != b.admitted_at
        ):
            raise ValueError("Search task binding resolution differs from its immutable binding")
        return self


class SearchUncertaintyTaskEpoch(BaseModel):
    """Task-scoped as-of epoch; it never implies live-world validity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    scope: Literal["selected_search_task_epoch"] = "selected_search_task_epoch"
    ticket_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    owner_context_ref: ArtifactRef
    selected_at: AwareDatetime
    external_validity_status: Literal["not_established"] = "not_established"
    live_currentness_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _owner_context_ref(self) -> SearchUncertaintyTaskEpoch:
        if self.owner_context_ref.manifest_profile_sha256 is None:
            raise ValueError("task epoch requires the selected owner-context ref")
        return self


class SearchUncertaintyTaskAdmission(BaseModel):
    """Immutable outcome of the pre-dispatch Search task-admission producer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    ticket_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    status: Literal["unassessed", "not_established"]
    owner_context_ref: ArtifactRef
    task_epoch_ref: ArtifactRef
    basis_ref: ArtifactRef | None = None
    missing_slices: tuple[str, ...] = ()
    admitted_at: AwareDatetime
    as_of_status: Literal["pinned_task_epoch"] = "pinned_task_epoch"
    live_currentness_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _status_matches_refs(self) -> SearchUncertaintyTaskAdmission:
        if any(
            ref.manifest_profile_sha256 is None
            for ref in (self.owner_context_ref, self.task_epoch_ref)
        ):
            raise ValueError("task admission refs must select exact manifest profiles")
        if self.status == "unassessed":
            if self.basis_ref is None or self.missing_slices:
                raise ValueError("unassessed task admission requires a complete basis only")
            if self.basis_ref.manifest_profile_sha256 is None:
                raise ValueError("unassessed basis must select an exact manifest profile")
        elif self.basis_ref is not None or not self.missing_slices:
            raise ValueError("not-established admission requires limitations and no basis")
        return self


class SearchUncertaintyInputInventory(BaseModel):
    """Complete selected dependency inventory recomputed from source manifests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    roots: tuple[SearchInputDependency, ...] = Field(min_length=1)
    members: tuple[SearchInputDependency, ...] = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _unique_members(self) -> SearchUncertaintyInputInventory:
        keys = [(_ref_key(item.ref), item.role_path) for item in self.members]
        if len(keys) != len(set(keys)):
            raise ValueError("selected dependency inventory contains duplicate role/ref members")
        root_roles = [item.role_path for item in self.roots]
        if len(root_roles) != len(set(root_roles)):
            raise ValueError("selected dependency inventory roots must have unique roles")
        return self


class SearchUncertaintyBasisV2(BaseModel):
    """Frozen stable identity for one candidate uncertainty obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    obligation_id: str = Field(min_length=1)
    subject_ref: ArtifactRef
    quantity_ref: ArtifactRef
    treatment_contrast_ref: ArtifactRef
    population_ref: ArtifactRef
    outcome_ref: ArtifactRef
    unit_scope_ref: ArtifactRef | None = None
    unit_binding_status: Literal["bound", "unknown"]
    component: Literal["statistical"] = "statistical"
    selected_plan_ref: ArtifactRef
    selected_configuration_ref: ArtifactRef
    selected_source_graph_ref: ArtifactRef
    selected_rule_ref: ArtifactRef
    selected_profile_ref: ArtifactRef
    selected_procedure_ref: ArtifactRef
    selected_selection_ref: ArtifactRef
    selected_state_input_refs: tuple[SearchInputDependency, ...] = ()
    valid_epoch_ref: ArtifactRef
    selected_method_fqn: str = Field(min_length=1)
    selected_method_abi_version: str = Field(min_length=1)
    selected_method_abi_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_method_params_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_method_params: dict[str, Any]
    selected_method_seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    selected_inference_profile_id: str = Field(min_length=1)
    selected_method_input_ref: ArtifactRef
    selected_method_input_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_projection: SearchUncertaintyHTERequestProjection
    tenant_id: str = Field(min_length=1, max_length=128)
    cell_id: str | None = Field(default=None, min_length=1, max_length=128)
    dependency_inventory_ref: ArtifactRef
    dependency_inventory_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    quantity_semantics: Literal["causal_treatment_effect_contrast"]
    target_scope: Literal["selected_evaluation_rows", "population"]
    as_of_mode: Literal["pinned_task_epoch"] = "pinned_task_epoch"

    @model_validator(mode="after")
    def _selected_refs(self) -> SearchUncertaintyBasisV2:
        refs = (
            self.subject_ref,
            self.quantity_ref,
            self.treatment_contrast_ref,
            self.population_ref,
            self.outcome_ref,
            self.selected_plan_ref,
            self.selected_configuration_ref,
            self.selected_source_graph_ref,
            self.selected_rule_ref,
            self.selected_profile_ref,
            self.selected_procedure_ref,
            self.selected_selection_ref,
            self.valid_epoch_ref,
            self.dependency_inventory_ref,
            self.selected_method_input_ref,
        )
        refs = (*refs, *(item.ref for item in self.selected_state_input_refs))
        if self.unit_scope_ref is not None:
            refs = (*refs, self.unit_scope_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("v2 uncertainty basis requires selected manifest profiles")
        if (
            self.selected_method_input_ref.artifact_id.hex
            != self.selected_method_input_content_sha256
        ):
            raise ValueError("v2 basis input digest differs from its CAS identity")
        if (
            self.request_projection.target_scope != self.target_scope
            or self.request_projection.outcome_variable_id
            == self.request_projection.treatment_variable_id
        ):
            raise ValueError("v2 basis request projection differs from its selected target")
        if self.unit_binding_status == "bound" and self.unit_scope_ref is None:
            raise ValueError("bound v2 unit requires a selected unit-scope ref")
        if self.unit_binding_status == "unknown" and self.unit_scope_ref is not None:
            raise ValueError("unknown v2 unit cannot carry a selected scope ref")
        if self.quantity_semantics != "causal_treatment_effect_contrast":
            raise ValueError("relative routing score only supports a causal treatment contrast")
        return self


class SearchUnassessedObservationV2(BaseModel):
    """Explicit numeric-free task-admission observation for one obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    state: Literal["unassessed"] = "unassessed"
    basis_ref: ArtifactRef
    obligation_id: str = Field(min_length=1)
    task_admission_ref: ArtifactRef
    ticket_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    reason_code: Literal["native_method_assessment_pending"]
    admitted_at: AwareDatetime

    @model_validator(mode="after")
    def _selected_refs(self) -> SearchUnassessedObservationV2:
        if any(
            ref.manifest_profile_sha256 is None for ref in (self.basis_ref, self.task_admission_ref)
        ):
            raise ValueError("unassessed observation requires selected refs")
        return self


class SearchUncertaintyRoutingProfile(BaseModel):
    """Frozen candidate-routing formula selected independently of evidence status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    profile_id: Literal["relative_interval_halfwidth_routing@1.0"] = (
        "relative_interval_halfwidth_routing@1.0"
    )
    formula: Literal["min_1_width_over_2_abs_theta"] = "min_1_width_over_2_abs_theta"
    purpose: Literal["candidate_ordering_only"] = "candidate_ordering_only"
    zero_theta_behavior: Literal["assessment_retained_score_unavailable"] = (
        "assessment_retained_score_unavailable"
    )
    authority_effect: Literal["none"] = "none"


class SearchUncertaintyRoutingScore(BaseModel):
    """Named candidate-ordering quantity, never an evidence-strength predicate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    profile_id: Literal["relative_interval_halfwidth_routing@1.0"] = (
        "relative_interval_halfwidth_routing@1.0"
    )
    profile_ref: ArtifactRef
    status: Literal["available", "unavailable"]
    unavailable_reason: (
        Literal[
            "interval_not_qualified",
            "zero_reference_scale",
            "reference_scale_not_established",
            "interval_invalid",
            "unit_not_bound",
            "scope_not_comparable",
        ]
        | None
    ) = None
    theta: float | None = Field(default=None, strict=True)
    lower_bound: float | None = Field(default=None, strict=True)
    upper_bound: float | None = Field(default=None, strict=True)
    width: float | None = None
    width_decimal: str | None = None
    width_overflow: bool = False
    raw_ratio_decimal: str | None = None
    raw_ratio_overflow: bool = False
    saturated: bool = False
    score: float | None = None
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    interval_semantics: Literal["native_mean_confidence_interval"] | None = None
    comparison_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent_state(self) -> SearchUncertaintyRoutingScore:
        if self.status == "available":
            if (
                self.unavailable_reason is not None
                or self.score is None
                or (self.width is None and self.width_decimal is None)
                or self.theta is None
                or self.lower_bound is None
                or self.upper_bound is None
                or self.confidence_level is None
                or self.interval_semantics != "native_mean_confidence_interval"
                or self.comparison_key is None
            ):
                raise ValueError("available routing score requires finite result operands")
            values = (self.theta, self.lower_bound, self.upper_bound)
            if any(not math.isfinite(value) for value in values):
                raise ValueError("routing score operands must be finite")
            if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
                raise ValueError("routing score must be finite and capped to [0, 1]")
            if self.lower_bound > self.upper_bound or (self.width is not None and self.width < 0.0):
                raise ValueError("routing score interval must be ordered")
            if self.raw_ratio_decimal is None or self.width_decimal is None:
                raise ValueError("available routing score must retain raw arithmetic operands")
            try:
                width_value = Decimal(self.width_decimal)
                ratio_value = Decimal(self.raw_ratio_decimal)
            except InvalidOperation as exc:
                raise ValueError("routing score retained decimal is malformed") from exc
            if (
                not width_value.is_finite()
                or width_value < 0
                or not ratio_value.is_finite()
                or ratio_value < 0
            ):
                raise ValueError("routing score retained arithmetic must be finite and nonnegative")
            if self.profile_ref.kind != "scientist.search.uncertainty_routing_profile":
                raise ValueError("routing score has the wrong selected profile kind")
        else:
            if self.score is not None or self.unavailable_reason is None:
                raise ValueError("unavailable routing score must give a reason and no score")
            if self.unavailable_reason == "interval_not_qualified":
                if self.profile_ref.manifest_profile_sha256 is None:
                    raise ValueError("point-only routing profile must select a manifest profile")
                point_only_allowed_fields = {
                    "profile_ref",
                    "status",
                    "unavailable_reason",
                    "theta",
                    "limitations",
                }
                for field_name, field_info in type(self).model_fields.items():
                    if field_name in point_only_allowed_fields:
                        continue
                    if getattr(self, field_name) != field_info.default:
                        raise ValueError("point-only routing cannot carry interval arithmetic")
                if self.theta is not None and not math.isfinite(self.theta):
                    raise ValueError("point-only routing operand must be finite")
            else:
                if (
                    self.theta is None
                    or self.lower_bound is None
                    or self.upper_bound is None
                    or self.confidence_level is None
                    or self.interval_semantics != "native_mean_confidence_interval"
                    or self.comparison_key is None
                ):
                    raise ValueError("unavailable interval score must retain its compared inputs")
                if any(
                    not math.isfinite(value)
                    for value in (self.theta, self.lower_bound, self.upper_bound)
                ):
                    raise ValueError("unavailable interval operands must remain finite")
            if self.profile_ref.kind != "scientist.search.uncertainty_routing_profile":
                raise ValueError("routing score has the wrong selected profile kind")
        return self


def _point_candidate_routing_score(
    *, profile_ref: ArtifactRef, theta: float
) -> SearchUncertaintyRoutingScore:
    """Return the complete canonical score shape for a point-only candidate."""
    return SearchUncertaintyRoutingScore(
        profile_ref=profile_ref,
        status="unavailable",
        unavailable_reason="interval_not_qualified",
        theta=theta,
        limitations=("point_candidate_retained", "no_interval_routing_score"),
    )


class SearchAssessedTargetRelation(BaseModel):
    """Bounded owner-verified summary of requested and computed HTE scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    requested_scope_status: Literal["declared", "not_established"]
    requested_scope: str | None = None
    requested_guarantee_status: Literal["declared", "not_established"]
    requested_guarantee: (
        Literal["candidate_point", "backend_conditional_interval", "population_sampling_coverage"]
        | None
    ) = None
    computed_scope_status: Literal["recomputed", "not_established"]
    computed_scope: Literal["selected_evaluation_rows"] | None
    computed_guarantee_status: Literal["computed", "not_established"]
    computed_guarantee: Literal["candidate_point", "backend_conditional_interval"] | None
    source_content_status: Literal["content_bound", "not_established"]
    row_order_status: Literal["recomputed", "not_established"]
    contrast_status: Literal["recomputed", "not_established"]
    # HTE arrays still lack a typed source-variable-to-column mapping. A status
    # copied from the request cannot establish the Search estimand relation.
    estimand_status: Literal["not_established"] = "not_established"
    alpha_status: Literal["recomputed", "not_applicable", "not_established"]
    profile_status: Literal["qualified", "point_only", "not_established"]
    scope_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]
    guarantee_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]
    overall_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]

    @model_validator(mode="after")
    def _status_matches_values(self) -> SearchAssessedTargetRelation:
        if (self.requested_scope_status == "declared") != (self.requested_scope is not None):
            raise ValueError("assessed target relation scope status differs from its value")
        if (self.requested_guarantee_status == "declared") != (
            self.requested_guarantee is not None
        ):
            raise ValueError("assessed target relation guarantee status differs from its value")
        if (self.computed_scope_status == "recomputed") != (
            self.computed_scope == "selected_evaluation_rows"
        ):
            raise ValueError("assessed computed scope must match its recomputation status")
        if (self.computed_guarantee_status == "computed") != (self.computed_guarantee is not None):
            raise ValueError("assessed computed guarantee must match its status")
        if self.requested_scope_status == "declared" and self.computed_scope_status == "recomputed":
            known_population_mismatch = (
                self.requested_scope == "population"
                and self.computed_scope == "selected_evaluation_rows"
            )
            equal_scope = (
                self.requested_scope == self.computed_scope
                and self.source_content_status == "content_bound"
                and self.row_order_status == "recomputed"
            )
            expected_scope = (
                "requested_claim_not_satisfied"
                if known_population_mismatch
                else "satisfied"
                if equal_scope
                else "not_established"
            )
        else:
            expected_scope = "not_established"
        if self.scope_disposition != expected_scope:
            raise ValueError("assessed scope disposition differs from its bound predicates")
        if (
            self.requested_guarantee_status == "declared"
            and self.computed_guarantee_status == "computed"
        ):
            expected_guarantee = (
                "satisfied"
                if self.requested_guarantee == self.computed_guarantee
                else "requested_claim_not_satisfied"
            )
        else:
            expected_guarantee = "not_established"
        if self.guarantee_disposition != expected_guarantee:
            raise ValueError("assessed guarantee disposition differs from its bound predicates")
        expected_overall = (
            "requested_claim_not_satisfied"
            if "requested_claim_not_satisfied" in {expected_scope, expected_guarantee}
            else "not_established"
            if "not_established" in {expected_scope, expected_guarantee}
            or self.contrast_status != "recomputed"
            or self.estimand_status != "recomputed"
            else "satisfied"
        )
        if self.overall_disposition != expected_overall:
            raise ValueError("assessed overall disposition differs from its bound predicates")
        return self


class SearchAssessedObservationV2(BaseModel):
    """Owner-bound point or native-interval candidate assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    state: Literal["assessed"] = "assessed"
    basis_ref: ArtifactRef
    obligation_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    outcome_kind: Literal["point_estimate", "interval_estimate"]
    predecessor_ref: ArtifactRef
    search_uncertainty_task_binding_ref: ArtifactRef
    owned_attempt_anchor_ref: ArtifactRef
    hte_outcome_ref: ArtifactRef
    point_result_ref: ArtifactRef | None = None
    hte_result_ref: ArtifactRef | None = None
    inference_basis_ref: ArtifactRef | None = None
    materialization_binding_ref: ArtifactRef
    producer_method_fqn: str = Field(min_length=1)
    producer_method_abi_version: str = Field(min_length=1)
    producer_method_abi_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    producer_params_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    inference_profile_id: str = Field(min_length=1)
    runtime_summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    resolved_params_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_relation: SearchAssessedTargetRelation
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    attempt: int = Field(ge=1, strict=True)
    completed_event_id: int = Field(ge=1, strict=True)
    completed_event_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    completed_at: AwareDatetime
    invocation_basis_ref: ArtifactRef | None = None
    source_data_ref: ArtifactRef
    method_result_ref: ArtifactRef
    method_evidence_ref: ArtifactRef
    selected_x_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    n_selected_rows: int = Field(ge=1, strict=True)
    treatment_variable_id: str = Field(min_length=1)
    outcome_variable_id: str = Field(min_length=1)
    control_value: float = Field(strict=True)
    treated_value: float = Field(strict=True)
    theta: float = Field(strict=True)
    lower_bound: float | None = Field(default=None, strict=True)
    upper_bound: float | None = Field(default=None, strict=True)
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    unit_binding_status: Literal["bound", "unknown"]
    unit_scope_ref: ArtifactRef | None = None
    interval_semantics: Literal["native_mean_confidence_interval"] | None = None
    routing_score: SearchUncertaintyRoutingScore
    source_observation_interval_status: Literal["established", "not_established"]
    source_observation_interval_start: AwareDatetime | None = None
    source_observation_interval_end: AwareDatetime | None = None
    computed_at: AwareDatetime
    admitted_at: AwareDatetime
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_native_interval(self) -> SearchAssessedObservationV2:
        selected_refs = (
            self.basis_ref,
            self.predecessor_ref,
            self.search_uncertainty_task_binding_ref,
            self.owned_attempt_anchor_ref,
            self.hte_outcome_ref,
            self.materialization_binding_ref,
            self.routing_score.profile_ref,
            self.source_data_ref,
            self.method_result_ref,
            self.method_evidence_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in selected_refs):
            raise ValueError("assessed observation requires exact selected manifest profiles")
        expected_json_refs = (
            (self.basis_ref, "scientist.search.uncertainty_basis"),
            (self.predecessor_ref, "scientist.search.uncertainty_observation"),
            (
                self.search_uncertainty_task_binding_ref,
                "scientist.search.uncertainty_task_binding",
            ),
            (self.owned_attempt_anchor_ref, "runtime.owned_attempt_anchor"),
            (self.hte_outcome_ref, "ir.hte_outcome"),
            (self.routing_score.profile_ref, "scientist.search.uncertainty_routing_profile"),
        )
        if any(
            ref.kind != kind or ref.media_type != "application/json"
            for ref, kind in expected_json_refs
        ):
            raise ValueError("assessed observation contains a selected ref of the wrong kind")
        if (
            self.materialization_binding_ref.kind
            != "foundry.hte.physical_source_materialization_binding"
            or self.materialization_binding_ref.media_type != "application/json"
        ):
            raise ValueError("assessed observation requires the selected physical HTE binding")
        if any(
            ref is not None and ref.manifest_profile_sha256 is None
            for ref in (
                self.hte_result_ref,
                self.point_result_ref,
                self.inference_basis_ref,
                self.invocation_basis_ref,
                self.unit_scope_ref,
            )
        ):
            raise ValueError("assessed observation optional refs must select manifest profiles")
        branch_refs = (
            (self.point_result_ref, "ir.hte_point_result"),
            (self.hte_result_ref, "ir.hte_result"),
            (self.inference_basis_ref, "ir.ate_inference_basis"),
        )
        if any(
            ref is not None and (ref.kind != kind or ref.media_type != "application/json")
            for ref, kind in branch_refs
        ):
            raise ValueError("assessed observation HTE refs have the wrong artifact kind")
        if not math.isfinite(self.theta):
            raise ValueError("native candidate point must be finite")
        if self.outcome_kind == "interval_estimate":
            if (
                self.inference_basis_ref is None
                or self.lower_bound is None
                or self.upper_bound is None
                or self.confidence_level is None
                or self.interval_semantics != "native_mean_confidence_interval"
            ):
                raise ValueError("interval assessment requires its complete inference basis")
            if self.hte_result_ref is None or self.point_result_ref is not None:
                raise ValueError(
                    "interval assessment requires the unique HTEResult v1 value carrier"
                )
            if (
                not math.isfinite(self.lower_bound)
                or not math.isfinite(self.upper_bound)
                or self.lower_bound > self.upper_bound
            ):
                raise ValueError("native assessment interval bounds must be finite and ordered")
        elif any(
            value is not None
            for value in (
                self.hte_result_ref,
                self.lower_bound,
                self.upper_bound,
                self.confidence_level,
                self.interval_semantics,
            )
        ):
            raise ValueError("point-only assessment cannot carry interval-only artifacts")
        elif self.point_result_ref is None:
            raise ValueError("point-only assessment requires its point-result artifact")
        if self.unit_binding_status == "bound" and self.unit_scope_ref is None:
            raise ValueError("bound native assessment requires a unit scope ref")
        if self.unit_binding_status == "unknown" and self.unit_scope_ref is not None:
            raise ValueError("unknown native assessment cannot carry a unit scope ref")
        if self.routing_score.theta != self.theta:
            raise ValueError("routing score theta differs from the native point")
        if self.outcome_kind == "interval_estimate" and (
            self.routing_score.lower_bound != self.lower_bound
            or self.routing_score.upper_bound != self.upper_bound
            or self.routing_score.confidence_level != self.confidence_level
        ):
            raise ValueError("routing score inputs differ from the native interval")
        if self.outcome_kind == "point_estimate":
            expected_point_score = _point_candidate_routing_score(
                profile_ref=self.routing_score.profile_ref,
                theta=self.theta,
            )
            if self.routing_score != expected_point_score:
                raise ValueError(
                    "point-only outcome must retain the canonical assessment without interval score"
                )
        if self.source_observation_interval_status == "established":
            if (
                self.source_observation_interval_start is None
                or self.source_observation_interval_end is None
            ):
                raise ValueError("established source interval requires both endpoints")
            if self.source_observation_interval_start > self.source_observation_interval_end:
                raise ValueError("source observation interval is reversed")
        elif (
            self.source_observation_interval_start is not None
            or self.source_observation_interval_end is not None
        ):
            raise ValueError("unestablished source interval cannot carry endpoints")
        return self


type SearchUncertaintyObservationV2 = Annotated[
    SearchUnassessedObservationV2 | SearchAssessedObservationV2,
    Field(discriminator="state"),
]


class SearchUncertaintyRefinement(BaseModel):
    """Persisted first-assessment edge from an explicit unassessed predecessor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    relation: Literal["unassessed_to_assessed_same_basis@1.0"] = (
        "unassessed_to_assessed_same_basis@1.0"
    )
    predecessor_ref: ArtifactRef
    successor_ref: ArtifactRef
    basis_ref: ArtifactRef
    profile_ref: ArtifactRef
    owned_attempt_anchor_ref: ArtifactRef
    expected_ticket_generation: int = Field(ge=0, strict=True)
    admitted_at: AwareDatetime

    @model_validator(mode="after")
    def _selected_refs(self) -> SearchUncertaintyRefinement:
        if self.profile_ref.kind != "scientist.search.uncertainty_refinement_profile":
            raise ValueError("refinement requires the selected first-assessment profile")
        refs = (
            self.predecessor_ref,
            self.successor_ref,
            self.basis_ref,
            self.profile_ref,
            self.owned_attempt_anchor_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("refinement requires exact selected artifact refs")
        return self


class SearchUncertaintyRefinementProfile(BaseModel):
    """Executable contract for the sole admitted first-assessment relation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    profile_id: Literal["unassessed_to_assessed_same_basis@1.0"] = (
        "unassessed_to_assessed_same_basis@1.0"
    )
    predecessor_state: Literal["unassessed"] = "unassessed"
    successor_state: Literal["assessed"] = "assessed"
    same_basis_required: Literal[True] = True
    assessed_to_assessed_update: Literal["forbidden"] = "forbidden"
    component: Literal["statistical"] = "statistical"


class SearchUncertaintyCurrentSuccessor(BaseModel):
    """One indivisible successor/refinement/score tuple in a current obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_ref: ArtifactRef
    refinement_ref: ArtifactRef
    routing_score: SearchUncertaintyRoutingScore

    @model_validator(mode="after")
    def _selected_refs(self) -> SearchUncertaintyCurrentSuccessor:
        if any(
            ref.manifest_profile_sha256 is None
            for ref in (self.observation_ref, self.refinement_ref)
        ):
            raise ValueError("current successor tuple requires selected artifact refs")
        return self


class SearchUncertaintyCurrentObligation(BaseModel):
    """Current or contested assessments for one stable obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str = Field(min_length=1)
    basis_ref: ArtifactRef
    predecessor_ref: ArtifactRef
    successors: tuple[SearchUncertaintyCurrentSuccessor, ...] = Field(min_length=1)
    status: Literal["assessed", "contested"]
    expected_ticket_generation: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def _state_matches_refs(self) -> SearchUncertaintyCurrentObligation:
        keys = [_ref_key(item.observation_ref) for item in self.successors]
        if len(keys) != len(set(keys)):
            raise ValueError("current obligation cannot repeat a successor")
        if self.status == "contested" and len(self.successors) < 2:
            raise ValueError("contested obligation must retain at least two successors")
        if self.status == "assessed" and len(self.successors) != 1:
            raise ValueError("assessed obligation must have exactly one current successor")
        return self


class SearchUncertaintyTicketProjection(BaseModel):
    """Immutable bounded current/as-of projection over one funnel ticket."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    ticket_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    projection_revision: int = Field(ge=0, strict=True)
    previous_projection_ref: ArtifactRef | None = None
    task_admission_ref: ArtifactRef | None = None
    unassessed_observation_refs: tuple[ArtifactRef, ...] = ()
    current_obligations: tuple[SearchUncertaintyCurrentObligation, ...] = ()
    historical_observation_refs: tuple[ArtifactRef, ...] = ()
    historical_refinement_refs: tuple[ArtifactRef, ...] = ()
    historical_binding_refs: tuple[ArtifactRef, ...] = ()
    active_unknown_obligation_ids: tuple[str, ...] = ()
    incomplete_obligation_ids: tuple[str, ...] = ()
    as_of_status: Literal["pinned_task_epoch"] = "pinned_task_epoch"
    live_currentness_status: Literal["not_established"] = "not_established"
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_obligations(self) -> SearchUncertaintyTicketProjection:
        ids = [item.obligation_id for item in self.current_obligations]
        if len(ids) != len(set(ids)):
            raise ValueError("ticket projection has duplicate current obligation IDs")
        refs = (
            *self.unassessed_observation_refs,
            *self.historical_observation_refs,
            *self.historical_binding_refs,
        )
        if self.task_admission_ref is not None:
            refs = (*refs, self.task_admission_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("ticket projection observation refs must be profile-selected")
        if any(
            ref.kind != "scientist.search.uncertainty_task_binding"
            or ref.media_type != "application/json"
            for ref in self.historical_binding_refs
        ):
            raise ValueError("ticket projection contains a non-binding history ref")
        if len({_ref_key(ref) for ref in self.historical_binding_refs}) != len(
            self.historical_binding_refs
        ):
            raise ValueError("ticket projection repeats a historical binding ref")
        return self


class SearchUncertaintyResolvedUnassessedObservation(BaseModel):
    """One fresh-read unassessed observation with its exact selected basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_ref: ArtifactRef
    observation: SearchUnassessedObservationV2
    basis_ref: ArtifactRef
    basis: SearchUncertaintyBasisV2

    @model_validator(mode="after")
    def _selected_basis(self) -> SearchUncertaintyResolvedUnassessedObservation:
        if (
            self.observation_ref.kind != "scientist.search.uncertainty_observation"
            or self.observation_ref.manifest_profile_sha256 is None
            or self.basis_ref.kind != "scientist.search.uncertainty_basis"
            or self.basis_ref.manifest_profile_sha256 is None
            or _ref_key(self.observation.basis_ref) != _ref_key(self.basis_ref)
            or self.observation.obligation_id != self.basis.obligation_id
        ):
            raise ValueError("resolved unassessed observation differs from its selected basis")
        return self


class SearchUncertaintyResolvedCurrentSuccessor(BaseModel):
    """Content-bound typed successor and relation selected by a current obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_ref: ArtifactRef
    observation: SearchAssessedObservationV2
    refinement_ref: ArtifactRef
    refinement: SearchUncertaintyRefinement
    refinement_profile_ref: ArtifactRef
    refinement_profile: SearchUncertaintyRefinementProfile
    routing_profile_ref: ArtifactRef
    routing_profile: SearchUncertaintyRoutingProfile

    @model_validator(mode="after")
    def _selected_relation(self) -> SearchUncertaintyResolvedCurrentSuccessor:
        if (
            self.observation_ref.kind != "scientist.search.uncertainty_observation"
            or self.observation_ref.manifest_profile_sha256 is None
            or self.refinement_ref.kind != "scientist.search.uncertainty_refinement"
            or self.refinement_ref.manifest_profile_sha256 is None
            or self.refinement_profile_ref.kind != "scientist.search.uncertainty_refinement_profile"
            or self.refinement_profile_ref.manifest_profile_sha256 is None
            or self.routing_profile_ref.kind != "scientist.search.uncertainty_routing_profile"
            or self.routing_profile_ref.manifest_profile_sha256 is None
            or _ref_key(self.refinement.profile_ref) != _ref_key(self.refinement_profile_ref)
            or _ref_key(self.observation.routing_score.profile_ref)
            != _ref_key(self.routing_profile_ref)
            or self.refinement_profile.profile_id != self.refinement.relation
            or self.routing_profile.profile_id != self.observation.routing_score.profile_id
            or _ref_key(self.refinement.predecessor_ref)
            != _ref_key(self.observation.predecessor_ref)
            or _ref_key(self.refinement.successor_ref) != _ref_key(self.observation_ref)
            or _ref_key(self.refinement.basis_ref) != _ref_key(self.observation.basis_ref)
        ):
            raise ValueError("resolved current successor differs from its selected CAS relation")
        return self


class SearchUncertaintyResolvedCurrentObligation(BaseModel):
    """Full current basis, admitted predecessor, and selected assessed children."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selection: SearchUncertaintyCurrentObligation
    basis_ref: ArtifactRef
    basis: SearchUncertaintyBasisV2
    predecessor: SearchUncertaintyResolvedUnassessedObservation
    successors: tuple[SearchUncertaintyResolvedCurrentSuccessor, ...]

    @model_validator(mode="after")
    def _selected_obligation(self) -> SearchUncertaintyResolvedCurrentObligation:
        if (
            self.basis_ref.kind != "scientist.search.uncertainty_basis"
            or self.basis_ref.manifest_profile_sha256 is None
            or _ref_key(self.selection.basis_ref) != _ref_key(self.basis_ref)
            or _ref_key(self.predecessor.observation_ref)
            != _ref_key(self.selection.predecessor_ref)
            or _ref_key(self.predecessor.basis_ref) != _ref_key(self.basis_ref)
            or self.basis.obligation_id != self.selection.obligation_id
            or self.predecessor.observation.obligation_id != self.selection.obligation_id
            or self.predecessor.observation.ticket_generation
            != self.selection.expected_ticket_generation
        ):
            raise ValueError("resolved current obligation does not preserve its selected basis")
        expected = tuple(
            (item.observation_ref, item.refinement_ref, item.routing_score)
            for item in self.selection.successors
        )
        actual = tuple(
            (item.observation_ref, item.refinement_ref, item.observation.routing_score)
            for item in self.successors
        )
        if expected != actual:
            raise ValueError("resolved current children differ from the selected projection")
        if any(
            item.observation.obligation_id != self.selection.obligation_id
            or _ref_key(item.observation.basis_ref) != _ref_key(self.basis_ref)
            for item in self.successors
        ):
            raise ValueError("resolved current child differs from its selected obligation")
        return self


class SearchUncertaintyResolvedCurrentProjection(BaseModel):
    """Fresh-read current payloads bound to the immutable owner projection refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    projection_ref: ArtifactRef
    projection: SearchUncertaintyTicketProjection
    selected_unassessed_observations: tuple[SearchUncertaintyResolvedUnassessedObservation, ...]
    current_obligations: tuple[SearchUncertaintyResolvedCurrentObligation, ...]

    @model_validator(mode="after")
    def _matches_selected_projection(self) -> SearchUncertaintyResolvedCurrentProjection:
        if (
            self.projection_ref.kind != "scientist.search.uncertainty_ticket_projection"
            or self.projection_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("resolved current projection requires its selected owner view")
        expected_unassessed = tuple(
            _ref_key(ref) for ref in self.projection.unassessed_observation_refs
        )
        actual_unassessed = tuple(
            _ref_key(item.observation_ref) for item in self.selected_unassessed_observations
        )
        if actual_unassessed != expected_unassessed:
            raise ValueError(
                "resolved current projection omitted or reordered a selected observation"
            )
        expected_current = self.projection.current_obligations
        actual_current = tuple(item.selection for item in self.current_obligations)
        if actual_current != expected_current:
            raise ValueError("resolved current projection omitted or changed a selected obligation")
        unassessed_by_ref = {
            _ref_key(item.observation_ref): item for item in self.selected_unassessed_observations
        }
        for item in self.current_obligations:
            selected_predecessor = unassessed_by_ref.get(_ref_key(item.selection.predecessor_ref))
            if selected_predecessor != item.predecessor:
                raise ValueError(
                    "resolved obligation predecessor is not the selected current record"
                )
        return self


class SearchUncertaintyTicketIndexRow(BaseModel):
    """Single-ticket durable current pointer and stage-state generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    ticket_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    owner_revision: int = Field(default=0, ge=0, strict=True)
    projection_revision: int = Field(ge=0, strict=True)
    current_projection_ref: ArtifactRef | None = None
    projection_ticket_generation: int | None = Field(default=None, ge=0, strict=True)
    owner_context_ref: ArtifactRef | None = None
    task_epoch_ref: ArtifactRef | None = None
    task_admission_ref: ArtifactRef | None = None
    current_binding_ref: ArtifactRef | None = None
    historical_binding_refs: tuple[ArtifactRef, ...] = ()

    @model_validator(mode="after")
    def _binding_owner_refs(self) -> SearchUncertaintyTicketIndexRow:
        refs = (*self.historical_binding_refs,)
        if self.current_binding_ref is not None:
            refs = (*refs, self.current_binding_ref)
        if any(
            ref.kind != "scientist.search.uncertainty_task_binding"
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref in refs
        ):
            raise ValueError("ticket owner binding refs must be profiled Search bindings")
        if len({_ref_key(ref) for ref in refs}) != len(refs):
            raise ValueError("ticket owner cannot repeat an admitted binding ref")
        return self


class SearchUncertaintyCurrentRead(BaseModel):
    """Fresh snapshot of the selected Search pointer and resolved current content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    ticket_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0, strict=True)
    projection_revision: int = Field(ge=0, strict=True)
    projection_ref: ArtifactRef | None = None
    projection: SearchUncertaintyTicketProjection | None = None
    resolved_projection: SearchUncertaintyResolvedCurrentProjection | None = None
    task_admission_ref: ArtifactRef | None = None
    task_binding_ref: ArtifactRef | None = None
    task_admission: SearchUncertaintyTaskAdmission | None = None
    admission_status: Literal["unassessed", "not_established", "missing"] = "missing"
    status: Literal["available_as_of_task_epoch", "not_established"]
    reason_code: (
        Literal[
            "owner_projection_missing_or_stale",
            "search_projection_mismatch",
            "runtime_attempt_association_unavailable",
            "runtime_attempt_association_mismatch",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def _selected_projection(self) -> SearchUncertaintyCurrentRead:
        if self.status == "available_as_of_task_epoch":
            if self.reason_code is not None:
                raise ValueError("available current read cannot carry a refusal reason")
            if self.projection is None or self.projection_ref is None:
                raise ValueError("available current read requires its selected projection")
            if self.resolved_projection is None:
                raise ValueError("available current read requires resolved current payloads")
            if (
                _ref_key(self.resolved_projection.projection_ref) != _ref_key(self.projection_ref)
                or self.resolved_projection.projection != self.projection
            ):
                raise ValueError("resolved current read differs from its selected projection")
            if (
                self.projection.ticket_id != self.ticket_id
                or self.projection.ticket_generation != self.ticket_generation
                or self.projection.projection_revision != self.projection_revision
            ):
                raise ValueError("current read snapshot differs from its selected ticket row")
            if self.projection_ref.manifest_profile_sha256 is None:
                raise ValueError("current read projection ref must select a manifest profile")
            if (self.task_admission_ref is None) != (self.task_admission is None):
                raise ValueError("current task admission ref and payload must travel together")
            if self.task_binding_ref is not None and (
                self.task_binding_ref.kind != "scientist.search.uncertainty_task_binding"
                or self.task_binding_ref.media_type != "application/json"
                or self.task_binding_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("current task binding must select a profiled Search binding")
            if self.task_admission_ref is None:
                if (
                    self.admission_status != "missing"
                    or self.projection.task_admission_ref is not None
                ):
                    raise ValueError("task admission absence must remain explicitly missing")
            else:
                if self.task_admission_ref.manifest_profile_sha256 is None:
                    raise ValueError("current task admission ref must select a manifest profile")
                admission = self.task_admission
                if admission is None:
                    raise ValueError("current task admission ref has no selected record")
                if self.admission_status != admission.status:
                    raise ValueError(
                        "current task admission status differs from its selected record"
                    )
                if self.projection.task_admission_ref is None or _ref_key(
                    self.projection.task_admission_ref
                ) != _ref_key(self.task_admission_ref):
                    raise ValueError("current projection does not bind the selected task admission")
        else:
            if self.reason_code is None:
                raise ValueError("unestablished current read requires a typed reason")
            if (
                self.projection is not None
                or self.projection_ref is not None
                or self.resolved_projection is not None
            ):
                raise ValueError("unestablished current read cannot expose stale projection bytes")
            if self.task_admission is not None or self.task_admission_ref is not None:
                raise ValueError("unestablished current read cannot expose a stale task admission")
            if self.task_binding_ref is not None:
                raise ValueError("unestablished current read cannot expose a stale task binding")
        return self


class SearchUncertaintyAdmissionError(ValueError):
    """A typed method outcome did not satisfy the selected Search basis."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: Literal[
            "owner_projection_missing_or_stale",
            "runtime_attempt_association_unavailable",
            "runtime_attempt_association_mismatch",
            "search_projection_mismatch",
            "native_hte_outcome_content_unavailable",
            "search_binding_resolution_unavailable",
            "search_binding_mismatch",
            "unassessed_obligation_unavailable",
            "hte_content_unavailable",
            "hte_content_mismatch",
            "hte_method_refusal",
        ] = "runtime_attempt_association_unavailable",
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class SearchUncertaintyCompletionReceipt(BaseModel):
    """Bounded result of consuming one owner-selected HTE completion event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["admitted", "already_admitted", "not_applicable", "not_established"]
    job_id: str = Field(min_length=1, max_length=128)
    completed_event_id: int = Field(ge=1, strict=True)
    ticket_id: str | None = Field(default=None, min_length=1, max_length=128)
    ticket_generation: int | None = Field(default=None, ge=1, strict=True)
    observation_ref: ArtifactRef | None = None
    reason_code: (
        Literal[
            "search_binding_absence_proven",
            "historical_completion_unavailable",
            "historical_completion_mismatch",
            "search_binding_missing",
            "search_binding_resolution_unavailable",
            "search_binding_mismatch",
            "unassessed_obligation_unavailable",
            "hte_content_unavailable",
            "hte_content_mismatch",
            "hte_method_refusal",
            "owner_state_unavailable",
        ]
        | None
    ) = None
    next_check: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def _status_payload(self) -> SearchUncertaintyCompletionReceipt:
        if self.status in {"admitted", "already_admitted"}:
            if (
                self.ticket_id is None
                or self.ticket_generation is None
                or self.observation_ref is None
                or self.reason_code is not None
                or self.next_check is not None
            ):
                raise ValueError("admitted completion receipt requires its Search CAS result")
        elif self.status == "not_applicable":
            if (
                self.reason_code != "search_binding_absence_proven"
                or self.next_check is not None
                or self.observation_ref is not None
            ):
                raise ValueError("not-applicable receipt requires owner-proven Search absence")
        elif self.reason_code is None or self.next_check is None:
            raise ValueError("not-established completion receipt requires a next check")
        if (
            self.observation_ref is not None
            and self.observation_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("completion receipt observation ref must be profile selected")
        return self


class SearchOwnedAttemptAssociation(Protocol):
    """Actual Runtime-owned attempt selected by its durable completion event."""

    @property
    def schema_version(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def anchor_ref(self) -> ArtifactRef: ...

    @property
    def outcome_ref(self) -> ArtifactRef: ...

    @property
    def outcome_kind(self) -> str: ...

    @property
    def invocation_basis_ref(self) -> ArtifactRef | None: ...

    @property
    def source_data_ref(self) -> ArtifactRef: ...

    @property
    def materialization_binding_ref(self) -> ArtifactRef | None: ...

    @property
    def search_uncertainty_task_binding_ref(self) -> ArtifactRef | None: ...

    @property
    def method_result_ref(self) -> ArtifactRef: ...

    @property
    def method_evidence_ref(self) -> ArtifactRef: ...

    @property
    def refusal_diagnostic_ref(self) -> ArtifactRef | None: ...

    @property
    def point_result_ref(self) -> ArtifactRef | None: ...

    @property
    def hte_result_ref(self) -> ArtifactRef | None: ...

    @property
    def inference_basis_ref(self) -> ArtifactRef | None: ...

    @property
    def job_id(self) -> str: ...

    @property
    def run_id(self) -> str: ...

    @property
    def attempt(self) -> int: ...

    @property
    def job_completed_event(self) -> SearchOwnedLifecycleEvent: ...


class SearchOwnedLifecycleEvent(Protocol):
    """Owner event identity returned inline by the current Runtime reader."""

    @property
    def event_id(self) -> int: ...

    @property
    def job_id(self) -> str: ...

    @property
    def event_type(self) -> str: ...

    @property
    def payload_sha256(self) -> str: ...

    @property
    def created_at(self) -> AwareDatetime: ...


class SearchOwnedAttemptAssociationResolver(Protocol):
    """Legacy current-attempt lookup retained for unrelated Search readers."""

    def __call__(self, *, anchor_ref: ArtifactRef) -> SearchOwnedAttemptAssociation | None: ...


class _SearchOwnerCellScopeUnset:
    """Distinguish an omitted current-owner selector from an explicit no-cell scope."""


_OWNER_SCOPE_UNSET = _SearchOwnerCellScopeUnset()


class SearchOwnedHistoricalAttemptAssociationResolver(Protocol):
    """Resolve one exact Search completion using its durable owner selectors."""

    def __call__(
        self,
        *,
        anchor_ref: ArtifactRef,
        expected_job_id: str,
        expected_completed_event_id: int,
        expected_tenant_id: str,
        expected_cell_id: str | None | _SearchOwnerCellScopeUnset = _OWNER_SCOPE_UNSET,
    ) -> SearchOwnedAttemptAssociation | None: ...


class SearchHTECompletionOwner(Protocol):
    """Runtime owner APIs needed to consume and reconcile exact HTE completions."""

    def resolve_historical_completed_method_execution(
        self,
        *,
        job_id: str,
        completed_event_id: int,
        tenant_id: str,
        cell_id: str | None,
    ) -> SearchOwnedAttemptAssociation | None: ...

    def resolve_historical_search_uncertainty_task_binding(
        self,
        *,
        binding_ref: ArtifactRef,
        owner_association: SearchOwnedAttemptAssociation,
    ) -> SearchUncertaintyTaskBindingResolution | None: ...


class SearchHTESourceProjectionBasis(Protocol):
    """Read-only selected Search inputs supplied to an optional source verifier."""

    @property
    def selected_method_input_ref(self) -> ArtifactRef: ...

    @property
    def selected_state_input_refs(self) -> tuple[SearchInputDependency, ...]: ...

    @property
    def unit_binding_status(self) -> Literal["bound", "unknown"]: ...

    @property
    def unit_scope_ref(self) -> ArtifactRef | None: ...


class SearchHTESourceProjectionError(ValueError):
    """A source verifier refused the optional candidate-only content join."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class SearchHTESourceProjectionJoin(BaseModel):
    """Selected subject refs returned by a wired source-content verifier.

    This in-process result is not a persisted authority receipt. The concrete
    verifier must resolve and compare source bytes before constructing it;
    constructing the DTO alone does not establish the join property.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    selected_method_input_ref: ArtifactRef
    assignment_ref: ArtifactRef
    outcome_profile_ref: ArtifactRef
    role_mapping_status: Literal["consumer_asserted"] = "consumer_asserted"
    owner_issuance_status: Literal["not_established"] = "not_established"
    semantic_alignment_status: Literal["not_established"] = "not_established"
    source_time_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _selected_subject_refs(self) -> SearchHTESourceProjectionJoin:
        for ref, kind in (
            (self.selected_method_input_ref, "ir.observation_method_input"),
            (self.assignment_ref, "runtime.value_owner_source_variable_assignment"),
            (self.outcome_profile_ref, "runtime.value_data_profile"),
        ):
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("source projection verifier result must bind selected refs")
        return self


class SearchHTESourceProjectionVerifier(Protocol):
    """Injected owner implementation for a selected snapshot's content join.

    The consumer owns this dependency contract. Runtime wires its concrete
    verifier at the completion receiver; Scientist never imports Runtime or
    reconstructs the ValueOwner row algorithm. Absence leaves routing unavailable.
    """

    def __call__(
        self,
        *,
        store: SearchUncertaintyStore,
        selected_method_input_ref: ArtifactRef,
        basis: SearchHTESourceProjectionBasis,
        request_projection: SearchUncertaintyHTERequestProjection,
        limits: CoreJsonReadLimits,
    ) -> SearchHTESourceProjectionJoin: ...


def _resolve_hte_source_projection_join(
    *,
    verifier: SearchHTESourceProjectionVerifier | None,
    store: SearchUncertaintyStore,
    selected_method_input_ref: ArtifactRef,
    basis: SearchHTESourceProjectionBasis,
    request_projection: SearchUncertaintyHTERequestProjection,
    limits: CoreJsonReadLimits,
) -> tuple[SearchHTESourceProjectionJoin | None, str | None]:
    """Invoke the wired verifier and bind its result to this frozen subject."""
    if verifier is None:
        return None, "source_projection_verifier_unavailable"
    if (
        basis.unit_binding_status != "bound"
        or basis.unit_scope_ref is None
        or artifact_ref_identity_key(basis.selected_method_input_ref)
        != artifact_ref_identity_key(selected_method_input_ref)
    ):
        return None, "source_unit_scope_not_frozen_in_basis"
    try:
        joined = verifier(
            store=store,
            selected_method_input_ref=selected_method_input_ref,
            basis=basis,
            request_projection=request_projection,
            limits=limits,
        )
    except SearchHTESourceProjectionError as exc:
        return None, exc.reason_code
    if type(joined) is not SearchHTESourceProjectionJoin:
        return None, "source_projection_verifier_result_invalid"
    selected_assignments = tuple(
        item.ref
        for item in basis.selected_state_input_refs
        if item.role_path == "source_variable_assignment"
    )
    if (
        len(selected_assignments) != 1
        or artifact_ref_identity_key(joined.selected_method_input_ref)
        != artifact_ref_identity_key(selected_method_input_ref)
        or artifact_ref_identity_key(joined.outcome_profile_ref)
        != artifact_ref_identity_key(basis.unit_scope_ref)
        or artifact_ref_identity_key(joined.assignment_ref)
        != artifact_ref_identity_key(selected_assignments[0])
    ):
        return None, "source_projection_verifier_subject_mismatch"
    return joined, None


class SearchOwnedAttemptProjectionResolver(Protocol):
    """Resolve only the bounded current Runtime projection for a completed attempt."""

    def __call__(
        self,
        *,
        run_id: str,
        expected_job_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> object | None: ...


class SearchOwnedHTESummaryResolver(Protocol):
    """Read the current owner-selected scalar HTE summary for one completed run."""

    def __call__(self, *, run_id: str, tenant_id: str, cell_id: str | None) -> object | None: ...


def _ref_key(ref: ArtifactRef | ArtifactRefModel) -> tuple[str, str, str, str | None]:
    return artifact_ref_identity_key(_source_core_ref(ref))


def _require_optional_artifact_ref_match(
    left: ArtifactRef | ArtifactRefModel | None,
    right: ArtifactRef | ArtifactRefModel | None,
    label: str,
) -> None:
    """Require exact equality for a field whose typed owner contract is optional."""
    if left is None and right is None:
        return
    if left is None or right is None or _ref_key(left) != _ref_key(right):
        raise SearchUncertaintyAdmissionError(
            f"selected HTE {label} ref differs from the exact owner-bound result",
            reason_code="hte_content_mismatch",
        )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_owned_lifecycle_event_digest_hex(event: object) -> str | None:
    """Validate the Runtime event wire ABI and return its digest in Search's DTO form."""
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptLifecycleEvent

    fields = ("event_id", "job_id", "event_type", "payload_sha256", "created_at")
    try:
        typed_event = OwnedAttemptLifecycleEvent.model_validate(
            {name: getattr(event, name) for name in fields},
            strict=True,
        )
        digest = ArtifactID(typed_event.payload_sha256)
    except (AttributeError, TypeError, ValidationError, ValueError):
        return None
    if str(digest) != typed_event.payload_sha256:
        return None
    return digest.hex


def _resolved_hte_params_sha256(params: Mapping[str, Any], seed: int) -> str:
    """Hash the HTE execution params and seed using the producer's exact basis."""
    return _canonical_sha256({"params": dict(params), "seed": seed})


def derive_search_uncertainty_ticket_id(run_id: str, subject_ref: ArtifactRef) -> str:
    """Derive a stable owner ticket key from the run and selected subject ref."""
    if not run_id.strip() or subject_ref.manifest_profile_sha256 is None:
        raise ValueError("stable Search ticket identity requires run and selected subject")
    return "search-uncertainty:" + _canonical_sha256(
        {"run_id": run_id, "subject_ref": _ref_key(subject_ref)}
    )


def _selected_ref(
    store: SearchUncertaintyStore, ref: ArtifactRef, *, role: str
) -> tuple[ArtifactRef, ArtifactManifest]:
    if ref.manifest_profile_sha256 is None:
        raise ValueError(f"selected input {role} has no manifest profile")
    manifest = resolve_manifest_by_profile(store, ref.artifact_id, ref.manifest_profile_sha256)
    if (manifest.kind, manifest.media_type) != (ref.kind, ref.media_type):
        raise ValueError(f"selected input {role} identity differs from manifest")
    if not store.verify(ref).ok:
        raise ValueError(f"selected input {role} failed content verification")
    return ref, manifest


def derive_selected_dependency_inventory(
    store: SearchUncertaintyStore,
    roots: Mapping[str, ArtifactRef],
) -> SearchUncertaintyInputInventory:
    """Recompute the full role-qualified transitive input set from selected manifests."""
    if not roots or any(not role.strip() for role in roots):
        raise ValueError("dependency inventory needs named selected roots")
    root_items = tuple(
        SearchInputDependency(role_path=role, ref=ref) for role, ref in sorted(roots.items())
    )
    members: dict[tuple[tuple[str, str, str, str | None], str], SearchInputDependency] = {}

    def visit(
        role_path: str, ref: ArtifactRef, ancestors: frozenset[tuple[str, str, str, str | None]]
    ) -> None:
        selected_ref, manifest = _selected_ref(store, ref, role=role_path)
        key = _ref_key(selected_ref)
        if key in ancestors:
            raise ValueError("selected source graph contains a cycle")
        member_key = (key, role_path)
        members[member_key] = SearchInputDependency(role_path=role_path, ref=selected_ref)
        next_ancestors = ancestors | {key}
        for edge in sorted(manifest.inputs, key=lambda item: (item.role, item.artifact_id)):
            if edge.manifest_profile_sha256 is None:
                raise ValueError(
                    f"selected source graph edge {role_path}/{edge.role} is unselected"
                )
            child_manifest = resolve_manifest_by_profile(
                store, edge.artifact_id, edge.manifest_profile_sha256
            )
            child = ArtifactRef(
                artifact_id=child_manifest.artifact_id,
                kind=child_manifest.kind,
                media_type=child_manifest.media_type,
                manifest_profile_sha256=edge.manifest_profile_sha256,
            )
            child_role = f"{role_path}/{edge.role}"
            visit(child_role, child, next_ancestors)

    for role, ref in sorted(roots.items()):
        visit(role, ref, frozenset())
    ordered = tuple(members[key] for key in sorted(members))
    digest_payload = [
        {
            "role_path": item.role_path,
            "artifact_id": str(item.ref.artifact_id),
            "kind": item.ref.kind,
            "media_type": item.ref.media_type,
            "manifest_profile_sha256": item.ref.manifest_profile_sha256,
        }
        for item in ordered
    ]
    return SearchUncertaintyInputInventory(
        roots=root_items,
        members=ordered,
        sha256=_canonical_sha256(digest_payload),
    )


def validate_search_basis_v2(
    store: SearchUncertaintyStore,
    basis_ref: ArtifactRef,
    basis: SearchUncertaintyBasisV2,
    inventory: SearchUncertaintyInputInventory,
) -> None:
    """Recompute selected dependencies and compare the whole basis inventory."""
    if basis_ref.kind != "scientist.search.uncertainty_basis":
        raise ValueError("v2 basis artifact kind mismatch")
    if basis_ref.manifest_profile_sha256 is None or not store.verify(basis_ref).ok:
        raise ValueError("v2 basis ref is unselected or invalid")
    roots = {
        "subject": basis.subject_ref,
        "quantity": basis.quantity_ref,
        "treatment_contrast": basis.treatment_contrast_ref,
        "population": basis.population_ref,
        "outcome": basis.outcome_ref,
        "selected_plan": basis.selected_plan_ref,
        "selected_configuration": basis.selected_configuration_ref,
        "selected_source_graph": basis.selected_source_graph_ref,
        "selected_rule": basis.selected_rule_ref,
        "selected_profile": basis.selected_profile_ref,
        "selected_procedure": basis.selected_procedure_ref,
        "selected_selection": basis.selected_selection_ref,
        "valid_epoch": basis.valid_epoch_ref,
        "selected_method_input": basis.selected_method_input_ref,
    }
    for item in basis.selected_state_input_refs:
        role = f"state_input.{item.role_path}"
        if role in roots:
            raise ValueError("selected Search input role shadows a basis root")
        roots[role] = item.ref
    if basis.unit_scope_ref is not None:
        roots["unit_scope"] = basis.unit_scope_ref
    recomputed = derive_selected_dependency_inventory(store, roots)
    if recomputed != inventory:
        raise ValueError("v2 dependency inventory differs from the complete selected source graph")
    if basis.dependency_inventory_sha256 != inventory.sha256:
        raise ValueError("v2 basis dependency inventory digest differs")
    inv_ref, _ = _selected_ref(store, basis.dependency_inventory_ref, role="dependency_inventory")
    if inv_ref.kind != "scientist.search.uncertainty_input_inventory":
        raise ValueError("v2 dependency inventory artifact kind mismatch")
    manifest = store.get_manifest(inv_ref)
    expected_members = {
        (str(item.ref.artifact_id), f"selected.{item.role_path}", item.ref.manifest_profile_sha256)
        for item in recomputed.members
    }
    actual_members = {
        (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)
        for edge in manifest.inputs
        if edge.role.startswith("selected.")
    }
    if expected_members != actual_members:
        raise ValueError(
            "inventory artifact manifest does not bind the complete selected input set"
        )
    basis_roots = dict(roots)
    basis_roots["dependency_inventory"] = basis.dependency_inventory_ref
    expected_basis_inputs = {
        (str(ref.artifact_id), f"selected.{role}", ref.manifest_profile_sha256)
        for role, ref in basis_roots.items()
    }
    actual_basis_inputs = {
        (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)
        for edge in store.get_manifest(basis_ref).inputs
        if edge.role.startswith("selected.")
    }
    if expected_basis_inputs != actual_basis_inputs:
        raise ValueError("basis manifest does not bind all selected scientific input roots")


def load_search_uncertainty_input_inventory(
    store: SearchUncertaintyStore, inventory_ref: ArtifactRef
) -> SearchUncertaintyInputInventory:
    """Load the exact inventory artifact through its owner schema."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    if inventory_ref.kind != "scientist.search.uncertainty_input_inventory":
        raise ValueError("v2 dependency inventory kind mismatch")
    return validate_core_model_json_artifact(SearchUncertaintyInputInventory, store, inventory_ref)


def load_search_uncertainty_basis_v2(
    store: SearchUncertaintyStore, basis_ref: ArtifactRef
) -> SearchUncertaintyBasisV2:
    """Fresh-read a v2 basis and recompute its complete selected dependency graph."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    if basis_ref.kind != "scientist.search.uncertainty_basis":
        raise ValueError("v2 basis artifact kind mismatch")
    basis = validate_core_model_json_artifact(SearchUncertaintyBasisV2, store, basis_ref)
    inventory = load_search_uncertainty_input_inventory(store, basis.dependency_inventory_ref)
    validate_search_basis_v2(store, basis_ref, basis, inventory)
    return basis


def load_search_uncertainty_task_binding(
    store: SearchUncertaintyStore, binding_ref: ArtifactRef
) -> SearchUncertaintyTaskBinding:
    """Fresh-read one Search binding and recompute every selected owner dependency."""
    binding = _load_typed_search_artifact(
        store,
        binding_ref,
        SearchUncertaintyTaskBinding,
        kind="scientist.search.uncertainty_task_binding",
    )
    _validate_search_task_binding_closure(store, binding_ref, binding)
    return binding


def _validate_search_owner_task_context(
    store: SearchUncertaintyStore,
    owner_context: SearchUncertaintyOwnerTaskContext,
) -> tuple[str, ...]:
    """Resolve the selected stage configuration and source graph before admission.

    The owner-context DTO is not self-authenticating. Its graph must agree with
    the concrete refs selected by the Scientist caller, and its configuration
    digest must recompute from the instantiated funnel stages.
    """
    roots: dict[str, ArtifactRef] = {"candidate": owner_context.subject_ref}
    if owner_context.selected_plan_ref is not None:
        roots["execution_plan"] = owner_context.selected_plan_ref
    if owner_context.selected_configuration_ref is not None:
        roots["stage_configuration"] = owner_context.selected_configuration_ref
    if owner_context.selected_rule_ref is not None:
        roots["selected_rule"] = owner_context.selected_rule_ref
    if owner_context.selected_profile_ref is not None:
        roots["selected_profile"] = owner_context.selected_profile_ref
    if owner_context.selected_procedure_ref is not None:
        roots["selected_procedure"] = owner_context.selected_procedure_ref
    if owner_context.selected_selection_ref is not None:
        roots["policy_selection"] = owner_context.selected_selection_ref
    if owner_context.selected_method_input_ref is not None:
        roots["selected_method_input"] = owner_context.selected_method_input_ref
    if owner_context.semantic_scope is not None:
        scope = owner_context.semantic_scope
        for role, ref in (
            ("quantity", scope.quantity_ref),
            ("treatment_contrast", scope.treatment_contrast_ref),
            ("population", scope.population_ref),
            ("outcome", scope.outcome_ref),
            ("unit_scope", scope.unit_scope_ref),
        ):
            if ref is not None:
                roots[role] = ref
    for item in owner_context.selected_state_input_refs:
        if item.role_path in roots:
            raise ValueError("Search owner context source roles shadow selected roots")
        roots[item.role_path] = item.ref

    for role, ref in roots.items():
        _selected_ref(store, ref, role=role)

    missing: set[str] = set(
        reconcile_search_method_selection_sources(
            store,
            expected_run_id=owner_context.run_id,
            plan_ref=owner_context.selected_plan_ref,
            selected_state_input_refs=owner_context.selected_state_input_refs,
            selected_method_fqn=owner_context.selected_method_fqn,
            selected_method_params=owner_context.selected_method_params,
        )
    )
    if missing and owner_context.status == "ready":
        raise ValueError("ready Search owner context lacks selected plan/catalog content join")
    if owner_context.selected_source_graph_ref is None:
        if owner_context.status == "ready":
            raise ValueError("ready Search owner context lacks its selected source graph")
        missing.add("selected_source_graph_owner")
    else:
        graph = _load_typed_search_artifact(
            store,
            owner_context.selected_source_graph_ref,
            SearchOwnerSelectedSourceGraph,
            kind="scientist.search.selected_source_graph",
        )
        graph_roots = {item.role_path: _ref_key(item.ref) for item in graph.roots}
        expected_roots = {role: _ref_key(ref) for role, ref in roots.items()}
        if graph_roots != expected_roots:
            raise ValueError(
                "selected Search source graph differs from Scientist-owned context refs"
            )

    if owner_context.selected_configuration_ref is None:
        if owner_context.status == "ready":
            raise ValueError("ready Search owner context lacks actual stage configuration")
        missing.add("selected_stage_configuration_owner")
    else:
        configuration = _load_typed_search_artifact(
            store,
            owner_context.selected_configuration_ref,
            SearchRuntimeStageConfiguration,
            kind="scientist.search.runtime_stage_configuration",
        )
        recomputed_digest = _canonical_sha256(
            {
                "owner_fqn": configuration.owner_fqn,
                "stages": configuration.stages,
                "unresolved_bindings": configuration.unresolved_bindings,
            }
        )
        if (
            configuration.configuration_sha256 != owner_context.selected_stage_config_sha256
            or recomputed_digest != configuration.configuration_sha256
        ):
            raise ValueError("selected Search stage configuration digest does not recompute")
        if configuration.unresolved_bindings:
            if owner_context.status == "ready":
                raise ValueError("ready Search owner context has unresolved stage configuration")
            missing.update(configuration.unresolved_bindings)

    return tuple(sorted(missing))


def reconcile_search_method_selection_sources(
    store: SearchUncertaintyStore,
    *,
    expected_run_id: str,
    plan_ref: ArtifactRef | None,
    selected_state_input_refs: tuple[SearchInputDependency, ...],
    selected_method_fqn: str | None,
    selected_method_params: dict[str, Any] | None,
) -> tuple[str, ...]:
    """Read back the selected plan node and catalog entry for this method invocation.

    The method name and parameters on the task context are only projections of
    workflow state. This join resolves the selected, profile-qualified plan and
    catalog artifacts and checks that exactly one planned node has the same
    method FQN and canonical parameters, backed by exactly one catalog entry.
    It deliberately does not infer an ABI, inference profile, rule, query,
    population, or unit from catalog metadata.
    """
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodCatalogSnapshot

    missing: set[str] = set()
    catalog_roles = {
        "method_catalog_snapshot",
        "state.method_catalog_snapshot_ref",
    }
    catalog_refs = {
        _ref_key(item.ref): item.ref
        for item in selected_state_input_refs
        if item.role_path in catalog_roles
    }
    if len(catalog_refs) > 1:
        raise ValueError("Search owner context selects conflicting method-catalog refs")
    if plan_ref is None:
        missing.add("selected_execution_plan_owner")
    if not catalog_refs:
        missing.add("selected_method_catalog_owner")
    if not selected_method_fqn:
        missing.add("selected_method_owner")
    if selected_method_params is None:
        missing.add("selected_method_params_owner")
    if missing:
        missing.add("selected_method_plan_catalog_content_join")
        return tuple(sorted(missing))

    assert plan_ref is not None
    catalog_ref = next(iter(catalog_refs.values()))
    if (
        plan_ref.kind != "scientist.execution_plan"
        or catalog_ref.kind != "foundry.method_catalog_snapshot"
    ):
        raise ValueError("selected Search method sources have unexpected artifact kinds")
    if plan_ref.manifest_profile_sha256 is None or catalog_ref.manifest_profile_sha256 is None:
        missing.add("selected_method_plan_catalog_profile")
        missing.add("selected_method_plan_catalog_content_join")
        return tuple(sorted(missing))

    plan = validate_core_model_json_artifact(ExecutionPlan, store, plan_ref)
    catalog = validate_core_model_json_artifact(MethodCatalogSnapshot, store, catalog_ref)
    assert selected_method_fqn is not None
    assert selected_method_params is not None
    if plan.run_id is not None and plan.run_id != expected_run_id:
        missing.add("selected_execution_plan_run_scope_match")
    if catalog.run_id is not None and catalog.run_id != expected_run_id:
        missing.add("selected_method_catalog_run_scope_match")
    nodes = [node for node in plan.method_dag if node.method_fqn == selected_method_fqn]
    entries = [entry for entry in catalog.entries if entry.fqn == selected_method_fqn]
    if len(nodes) != 1:
        missing.add("selected_method_plan_node_unique")
    else:
        try:
            plan_params_sha256 = _canonical_sha256(nodes[0].params)
            state_params_sha256 = _canonical_sha256(selected_method_params)
        except TypeError, ValueError:
            missing.add("selected_method_params_not_canonical")
        else:
            if plan_params_sha256 != state_params_sha256:
                missing.add("selected_method_plan_params_match")
    if len(entries) != 1:
        missing.add("selected_method_catalog_entry_unique")
    elif len(nodes) == 1:
        node_version = nodes[0].method_version
        fqn_version = selected_method_fqn.rpartition("@")[2] if "@" in selected_method_fqn else None
        if (
            (node_version is not None and node_version != entries[0].version)
            or (fqn_version is not None and fqn_version != entries[0].version)
            or (node_version is None and fqn_version is None)
        ):
            missing.add("selected_method_plan_catalog_version_match")
    if missing:
        missing.add("selected_method_plan_catalog_content_join")
    return tuple(sorted(missing))


def _derive_search_obligation_id(
    ticket_id: str,
    subject_ref: ArtifactRef,
    scope: SearchUncertaintySemanticScope,
) -> str:
    return "search-uncertainty:" + _canonical_sha256(
        {
            "ticket_id": ticket_id,
            "subject": _ref_key(subject_ref),
            "quantity": _ref_key(scope.quantity_ref),
            "contrast": _ref_key(scope.treatment_contrast_ref),
            "population": _ref_key(scope.population_ref),
            "outcome": _ref_key(scope.outcome_ref),
            "unit_scope": None if scope.unit_scope_ref is None else _ref_key(scope.unit_scope_ref),
        }
    )


def _verify_search_basis_owner_binding(
    basis: SearchUncertaintyBasisV2,
    owner_context: SearchUncertaintyOwnerTaskContext,
    *,
    ticket_id: str,
    task_epoch_ref: ArtifactRef,
) -> None:
    """Reconcile a persisted basis against its task-owner and epoch sources."""
    scope = owner_context.semantic_scope
    if owner_context.status != "ready" or scope is None:
        raise ValueError("unassessed basis requires a complete Scientist owner context")
    ref_pairs = (
        (basis.subject_ref, owner_context.subject_ref),
        (basis.quantity_ref, scope.quantity_ref),
        (basis.treatment_contrast_ref, scope.treatment_contrast_ref),
        (basis.population_ref, scope.population_ref),
        (basis.outcome_ref, scope.outcome_ref),
        (basis.unit_scope_ref, scope.unit_scope_ref),
        (basis.selected_plan_ref, owner_context.selected_plan_ref),
        (basis.selected_configuration_ref, owner_context.selected_configuration_ref),
        (basis.selected_source_graph_ref, owner_context.selected_source_graph_ref),
        (basis.selected_rule_ref, owner_context.selected_rule_ref),
        (basis.selected_profile_ref, owner_context.selected_profile_ref),
        (basis.selected_procedure_ref, owner_context.selected_procedure_ref),
        (basis.selected_selection_ref, owner_context.selected_selection_ref),
        (basis.valid_epoch_ref, task_epoch_ref),
    )
    for actual, expected in ref_pairs:
        if (actual is None) != (expected is None) or (
            actual is not None and expected is not None and _ref_key(actual) != _ref_key(expected)
        ):
            raise ValueError("Search uncertainty basis ref differs from its selected owner context")
    selected_state_inputs = sorted(
        (item.role_path, _ref_key(item.ref)) for item in basis.selected_state_input_refs
    )
    owner_state_inputs = sorted(
        (item.role_path, _ref_key(item.ref)) for item in owner_context.selected_state_input_refs
    )
    if selected_state_inputs != owner_state_inputs:
        raise ValueError("Search uncertainty basis input inventory differs from its task owner")
    if (
        basis.obligation_id
        != _derive_search_obligation_id(ticket_id, owner_context.subject_ref, scope)
        or basis.unit_binding_status != scope.unit_binding_status
        or basis.selected_method_fqn != owner_context.selected_method_fqn
        or basis.selected_method_abi_version != owner_context.selected_method_abi_version
        or basis.selected_method_abi_digest != owner_context.selected_method_abi_digest
        or basis.selected_method_params_sha256 != owner_context.selected_method_params_sha256
        or basis.selected_method_params != owner_context.selected_method_params
        or basis.selected_method_seed != owner_context.selected_method_seed
        or basis.selected_inference_profile_id != owner_context.selected_inference_profile_id
        or owner_context.selected_method_input_ref is None
        or _ref_key(basis.selected_method_input_ref)
        != _ref_key(owner_context.selected_method_input_ref)
        or basis.selected_method_input_content_sha256
        != owner_context.selected_method_input_content_sha256
        or basis.request_projection != owner_context.request_projection
        or basis.tenant_id != owner_context.tenant_id
        or basis.cell_id != owner_context.cell_id
        or basis.target_scope != scope.requested_target_scope
        or basis.valid_epoch_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("Search uncertainty basis semantics differ from its task owner")


def _validate_search_task_binding_closure(
    store: SearchUncertaintyStore,
    binding_ref: ArtifactRef,
    binding: SearchUncertaintyTaskBinding,
) -> None:
    """Recompute a binding from its frozen task, source, scope, and CAS owners."""
    if (
        binding_ref.kind != "scientist.search.uncertainty_task_binding"
        or binding_ref.media_type != "application/json"
        or binding_ref.manifest_profile_sha256 is None
        or not store.verify(binding_ref).ok
        or binding_ref.artifact_id.hex
        != hashlib.sha256(store.get_bytes(binding_ref.artifact_id)).hexdigest()
    ):
        raise ValueError("Search task binding ref is not a valid selected CAS object")
    source_projection = _load_typed_search_artifact(
        store,
        binding.source_projection_ref,
        SearchUncertaintyTicketProjection,
        kind="scientist.search.uncertainty_ticket_projection",
    )
    admission = _load_typed_search_artifact(
        store,
        binding.task_admission_ref,
        SearchUncertaintyTaskAdmission,
        kind="scientist.search.uncertainty_task_admission",
    )
    task_epoch = _load_typed_search_artifact(
        store,
        binding.task_epoch_ref,
        SearchUncertaintyTaskEpoch,
        kind="scientist.search.uncertainty_task_epoch",
    )
    owner_context = _load_typed_search_artifact(
        store,
        binding.owner_context_ref,
        SearchUncertaintyOwnerTaskContext,
        kind="scientist.search.uncertainty_owner_task_context",
    )
    if (
        source_projection.ticket_id != binding.ticket_id
        or source_projection.ticket_generation != binding.ticket_generation
        or source_projection.projection_revision != binding.projection_revision
        or source_projection.task_admission_ref is None
        or _ref_key(source_projection.task_admission_ref) != _ref_key(binding.task_admission_ref)
        or admission.ticket_id != binding.ticket_id
        or admission.run_id != binding.parent_run_id
        or admission.ticket_generation != binding.ticket_generation
        or admission.status != "unassessed"
        or admission.basis_ref is None
        or _ref_key(admission.basis_ref) != _ref_key(binding.basis_ref)
        or _ref_key(admission.owner_context_ref) != _ref_key(binding.owner_context_ref)
        or _ref_key(admission.task_epoch_ref) != _ref_key(binding.task_epoch_ref)
        or task_epoch.ticket_id != binding.ticket_id
        or task_epoch.run_id != binding.parent_run_id
        or task_epoch.ticket_generation != binding.ticket_generation
        or _ref_key(task_epoch.owner_context_ref) != _ref_key(binding.owner_context_ref)
        or owner_context.run_id != binding.parent_run_id
        or owner_context.tenant_id != binding.tenant_id
        or owner_context.cell_id != binding.cell_id
    ):
        raise ValueError("Search task binding differs from its frozen task owner records")
    unresolved = _validate_search_owner_task_context(store, owner_context)
    if owner_context.status != "ready" or unresolved:
        raise ValueError("Search task binding owner context is not complete and current")
    basis = load_search_uncertainty_basis_v2(store, binding.basis_ref)
    inventory = load_search_uncertainty_input_inventory(store, binding.dependency_inventory_ref)
    _verify_search_basis_owner_binding(
        basis,
        owner_context,
        ticket_id=binding.ticket_id,
        task_epoch_ref=binding.task_epoch_ref,
    )
    if (
        _ref_key(basis.dependency_inventory_ref) != _ref_key(binding.dependency_inventory_ref)
        or basis.dependency_inventory_sha256 != binding.dependency_inventory_sha256
        or inventory.sha256 != binding.dependency_inventory_sha256
        or _ref_key(basis.selected_method_input_ref) != _ref_key(binding.selected_method_input_ref)
        or basis.selected_method_input_content_sha256
        != binding.selected_method_input_content_sha256
        or basis.request_projection != binding.request_projection
        or basis.tenant_id != binding.tenant_id
        or basis.cell_id != binding.cell_id
        or basis.selected_method_fqn != binding.selected_method_fqn
        or basis.selected_method_abi_version != binding.selected_method_abi_version
        or basis.selected_method_abi_digest != binding.selected_method_abi_digest
        or basis.selected_method_params_sha256 != binding.selected_method_params_sha256
        or basis.selected_method_params != binding.selected_method_params
        or basis.selected_method_seed != binding.selected_method_seed
        or basis.selected_inference_profile_id != binding.selected_inference_profile_id
        or admission.admitted_at != binding.admitted_at
    ):
        raise ValueError("Search task binding differs from its recomputed source basis")
    _selected_ref(store, binding.selected_method_input_ref, role="selected_method_input")
    if not any(
        _ref_key(item.ref) == _ref_key(binding.selected_method_input_ref)
        for item in inventory.members
    ):
        raise ValueError("selected HTE input is outside the complete dependency inventory")


def _search_task_binding_resolution(
    *,
    binding_ref: ArtifactRef,
    binding: SearchUncertaintyTaskBinding,
    resolution_status: Literal["current", "historical"],
) -> SearchUncertaintyTaskBindingResolution:
    """Project one recomputed binding into the stable Runtime port DTO."""
    return SearchUncertaintyTaskBindingResolution(
        resolution_status=resolution_status,
        binding_ref=binding_ref,
        binding=binding,
        binding_content_sha256=binding_ref.artifact_id.hex,
        ticket_id=binding.ticket_id,
        ticket_generation=binding.ticket_generation,
        owner_revision=binding.owner_revision,
        projection_revision=binding.projection_revision,
        projection_ref=binding.source_projection_ref,
        source_projection_ref=binding.source_projection_ref,
        request_projection=binding.request_projection,
        task_admission_ref=binding.task_admission_ref,
        task_epoch_ref=binding.task_epoch_ref,
        owner_context_ref=binding.owner_context_ref,
        basis_ref=binding.basis_ref,
        dependency_inventory_ref=binding.dependency_inventory_ref,
        dependency_inventory_sha256=binding.dependency_inventory_sha256,
        selected_method_fqn=binding.selected_method_fqn,
        selected_method_abi_version=binding.selected_method_abi_version,
        selected_method_abi_digest=binding.selected_method_abi_digest,
        selected_method_params_sha256=binding.selected_method_params_sha256,
        selected_method_params=binding.selected_method_params,
        selected_method_seed=binding.selected_method_seed,
        selected_inference_profile_id=binding.selected_inference_profile_id,
        selected_method_input_ref=binding.selected_method_input_ref,
        selected_method_input_content_sha256=binding.selected_method_input_content_sha256,
        tenant_id=binding.tenant_id,
        cell_id=binding.cell_id,
        admitted_at=binding.admitted_at,
        resolved_at=datetime.now(UTC),
    )


def resolve_current_search_uncertainty_task_binding(
    *,
    store: SearchUncertaintyStore,
    binding_ref: ArtifactRef,
    tenant_id: str,
    cell_id: str | None,
    request_projection: SearchUncertaintyHTERequestProjection,
    selected_method_fqn: str,
    selected_method_abi_version: str,
    selected_method_abi_digest: str,
    selected_method_params_sha256: str,
    selected_method_params: Mapping[str, Any],
    selected_method_seed: int,
    selected_inference_profile_id: str,
    selected_input_ref: ArtifactRef,
    selected_input_sha256: str,
) -> SearchUncertaintyTaskBindingResolution:
    """Recompute a current owner binding against the actual Runtime request and input."""
    if not tenant_id or type(selected_method_seed) is not int or selected_method_seed < 0:
        raise ValueError("Search binding Runtime scope or seed is invalid")
    if _canonical_sha256(selected_method_params) != selected_method_params_sha256:
        raise ValueError("Search binding Runtime params digest differs from its actual mapping")
    if selected_input_ref.manifest_profile_sha256 is None:
        raise ValueError("Search binding Runtime input must select a manifest profile")
    if selected_input_ref.artifact_id.hex != selected_input_sha256:
        raise ValueError("Search binding Runtime input digest differs from its CAS identity")
    binding = load_search_uncertainty_task_binding(store, binding_ref)
    state = SearchUncertaintyTicketState(store)
    with state._locked(binding.ticket_id):
        row = state._read_row(binding.ticket_id)
        if row is None or row.current_binding_ref is None:
            raise ValueError("Search task binding is not the live FunnelTicket owner selection")
        if (
            _ref_key(row.current_binding_ref) != _ref_key(binding_ref)
            or row.ticket_generation != binding.ticket_generation
            or row.owner_revision != binding.owner_revision
            or row.projection_revision != binding.projection_revision
            or row.current_projection_ref is None
            or _ref_key(row.current_projection_ref) != _ref_key(binding.source_projection_ref)
            or row.projection_ticket_generation != binding.ticket_generation
            or row.task_admission_ref is None
            or _ref_key(row.task_admission_ref) != _ref_key(binding.task_admission_ref)
        ):
            raise ValueError("Search task binding is stale for the current FunnelTicket owner")
    _validate_search_task_binding_closure(store, binding_ref, binding)
    if (
        binding.tenant_id != tenant_id
        or binding.cell_id != cell_id
        or binding.request_projection != request_projection
        or binding.selected_method_fqn != selected_method_fqn
        or binding.selected_method_abi_version != selected_method_abi_version
        or binding.selected_method_abi_digest != selected_method_abi_digest
        or binding.selected_method_params_sha256 != selected_method_params_sha256
        or binding.selected_method_params != dict(selected_method_params)
        or binding.selected_method_seed != selected_method_seed
        or binding.selected_inference_profile_id != selected_inference_profile_id
        or _ref_key(binding.selected_method_input_ref) != _ref_key(selected_input_ref)
        or binding.selected_method_input_content_sha256 != selected_input_sha256
    ):
        raise ValueError("Search task binding differs from the actual Runtime request")
    return _search_task_binding_resolution(
        binding_ref=binding_ref,
        binding=binding,
        resolution_status="current",
    )


def resolve_admitted_search_uncertainty_task_binding(
    *,
    store: SearchUncertaintyStore,
    binding_ref: ArtifactRef,
    expected_ticket_id: str,
    expected_ticket_generation: int,
    expected_owner_revision: int,
    expected_projection_revision: int,
    expected_projection_ref: ArtifactRef,
    expected_task_admission_ref: ArtifactRef,
    expected_task_epoch_ref: ArtifactRef,
    expected_owner_context_ref: ArtifactRef,
    expected_tenant_id: str,
    expected_cell_id: str | None,
    owned_historical_attempt_association_resolver: (
        SearchOwnedHistoricalAttemptAssociationResolver | None
    ) = None,
) -> SearchUncertaintyTaskBindingResolution:
    """Recompute a previously admitted binding against the same live task epoch.

    A queued Runtime job may consume its exact POST-selected binding after a
    same-generation owner projection has moved that ref into immutable history.
    This route does not admit a new selection: it requires the binding's exact
    owner refs and scope, current ticket generation, and membership in the current
    or historical owner pointer before validating its full CAS closure.
    """
    binding = load_search_uncertainty_task_binding(store, binding_ref)
    if (
        binding.ticket_id != expected_ticket_id
        or binding.ticket_generation != expected_ticket_generation
    ):
        raise ValueError("Search task binding ticket identity or generation differs")
    if (
        binding.owner_revision != expected_owner_revision
        or binding.projection_revision != expected_projection_revision
        or _ref_key(binding.source_projection_ref) != _ref_key(expected_projection_ref)
    ):
        raise ValueError("Search task binding differs from the selected owner projection")
    if (
        _ref_key(binding.task_admission_ref) != _ref_key(expected_task_admission_ref)
        or _ref_key(binding.task_epoch_ref) != _ref_key(expected_task_epoch_ref)
        or _ref_key(binding.owner_context_ref) != _ref_key(expected_owner_context_ref)
    ):
        raise ValueError("Search task binding differs from the selected task epoch")
    if binding.tenant_id != expected_tenant_id or binding.cell_id != expected_cell_id:
        raise ValueError("Search task binding differs from the selected task scope")

    state = SearchUncertaintyTicketState(
        store,
        owned_historical_attempt_association_resolver=(
            owned_historical_attempt_association_resolver
        ),
    )
    with state._locked(binding.ticket_id):
        row = state._read_row(binding.ticket_id)
        if row is None:
            raise ValueError("Search task binding has no FunnelTicket owner row")
        if row.ticket_generation != expected_ticket_generation:
            raise ValueError("Search task binding generation differs from the live owner row")
        if (
            row.projection_ticket_generation != expected_ticket_generation
            or row.task_admission_ref is None
            or _ref_key(row.task_admission_ref) != _ref_key(expected_task_admission_ref)
            or row.task_epoch_ref is None
            or _ref_key(row.task_epoch_ref) != _ref_key(expected_task_epoch_ref)
            or row.owner_context_ref is None
            or _ref_key(row.owner_context_ref) != _ref_key(expected_owner_context_ref)
        ):
            raise ValueError("Search task binding differs from the selected task epoch")
        if (
            row.projection_revision < expected_projection_revision
            or row.owner_revision < expected_owner_revision
        ):
            raise ValueError("Search task binding owner revisions precede its admission")
        if row.current_projection_ref is None:
            raise ValueError("Search task binding has no selected owner projection")
        if row.current_binding_ref is not None and _ref_key(row.current_binding_ref) == _ref_key(
            binding_ref
        ):
            if (
                row.owner_revision != expected_owner_revision
                or row.projection_revision != expected_projection_revision
                or _ref_key(row.current_projection_ref) != _ref_key(expected_projection_ref)
            ):
                raise ValueError("current Search task binding differs from its owner pointer")
            resolution_status: Literal["current", "historical"] = "current"
        elif any(_ref_key(ref) == _ref_key(binding_ref) for ref in row.historical_binding_refs):
            if row.current_binding_ref is not None:
                raise ValueError("Search task binding history conflicts with a current binding")
            if (
                row.owner_revision <= expected_owner_revision
                or row.projection_revision <= expected_projection_revision
            ):
                raise ValueError(
                    "historical Search binding lacks a later same-generation owner row"
                )
            resolution_status = "historical"
        else:
            raise ValueError("Search task binding was not selected by the current owner row")
        selected_projection = state._read_projection_for_row(row)
        if (
            selected_projection is None
            or selected_projection.ticket_generation != expected_ticket_generation
            or selected_projection.task_admission_ref is None
            or _ref_key(selected_projection.task_admission_ref)
            != _ref_key(expected_task_admission_ref)
        ):
            raise ValueError("Search task binding differs from the selected task epoch projection")

    _validate_search_task_binding_closure(store, binding_ref, binding)
    with state._locked(binding.ticket_id):
        latest_row = state._read_row(binding.ticket_id)
        if latest_row != row:
            raise ValueError("Search task owner row changed during admitted binding resolution")
    return _search_task_binding_resolution(
        binding_ref=binding_ref,
        binding=binding,
        resolution_status=resolution_status,
    )


def resolve_historical_search_uncertainty_task_binding(
    *,
    store: SearchUncertaintyStore,
    binding_ref: ArtifactRef,
    owner_association: object,
) -> SearchUncertaintyTaskBindingResolution:
    """Reconcile an already admitted binding to the real completed Runtime owner result."""
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorAssociation

    if type(owner_association) is not OwnedAttemptAnchorAssociation:
        raise TypeError("historical Search resolution requires the typed Runtime owner association")
    association = owner_association
    binding = load_search_uncertainty_task_binding(store, binding_ref)
    state = SearchUncertaintyTicketState(store)
    with state._locked(binding.ticket_id):
        row = state._read_row(binding.ticket_id)
        if row is None:
            raise ValueError("historical Search binding has no FunnelTicket owner row")
        known_binding_refs = {
            _ref_key(ref)
            for ref in (
                *row.historical_binding_refs,
                *(() if row.current_binding_ref is None else (row.current_binding_ref,)),
            )
        }
        if _ref_key(binding_ref) not in known_binding_refs:
            raise ValueError("historical Search binding was never published by this ticket owner")
    _validate_search_task_binding_closure(store, binding_ref, binding)
    if (
        association.status != "owner_selection_reconciled"
        or association.search_uncertainty_task_binding_ref is None
        or _ref_key(association.search_uncertainty_task_binding_ref) != _ref_key(binding_ref)
        or association.anchor_ref.manifest_profile_sha256 is None
        or association.outcome_ref.manifest_profile_sha256 is None
        or association.source_data_ref.manifest_profile_sha256 is None
        or _ref_key(association.source_data_ref) != _ref_key(binding.selected_method_input_ref)
        or association.job_completed_event.event_type != "job_completed"
        or association.job_completed_event.job_id != association.job_id
    ):
        raise ValueError(
            "Runtime completed output does not reconcile to the admitted Search binding"
        )
    return _search_task_binding_resolution(
        binding_ref=binding_ref,
        binding=binding,
        resolution_status="historical",
    )


def produce_search_task_admission(
    store: SearchUncertaintyStore,
    owner_context: SearchUncertaintyOwnerTaskContext,
    *,
    ticket_id: str,
    ticket_generation: int,
    selected_at: AwareDatetime,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef, ArtifactRef | None]:
    """Persist a pre-dispatch task epoch and its numeric-free obligation, if complete.

    This producer accepts the Scientist-owned context only after callers have built
    the actual selected stage stack. It resolves all supplied roots through CAS,
    derives the full transitive role-qualified dependency inventory itself, and
    returns an explicit not-established admission when any required scope or
    owner slice is absent.
    """
    configuration_missing = _validate_search_owner_task_context(store, owner_context)
    context_ref = persist_search_uncertainty_v2(store, owner_context)
    task_epoch = SearchUncertaintyTaskEpoch(
        ticket_id=ticket_id,
        run_id=owner_context.run_id,
        ticket_generation=ticket_generation,
        owner_context_ref=context_ref,
        selected_at=selected_at,
    )
    task_epoch_ref = persist_search_uncertainty_v2(store, task_epoch)
    if (
        owner_context.status != "ready"
        or owner_context.semantic_scope is None
        or configuration_missing
    ):
        missing = tuple(
            sorted(
                set(owner_context.missing_slices)
                | set(configuration_missing)
                | {"complete_search_basis"}
            )
        )
        admission = SearchUncertaintyTaskAdmission(
            ticket_id=ticket_id,
            run_id=owner_context.run_id,
            ticket_generation=ticket_generation,
            status="not_established",
            owner_context_ref=context_ref,
            task_epoch_ref=task_epoch_ref,
            missing_slices=missing,
            admitted_at=selected_at,
        )
        admission_ref = persist_search_uncertainty_v2(store, admission)
        return context_ref, task_epoch_ref, admission_ref, None

    scope = owner_context.semantic_scope
    roots: dict[str, ArtifactRef] = {
        "subject": owner_context.subject_ref,
        "quantity": scope.quantity_ref,
        "treatment_contrast": scope.treatment_contrast_ref,
        "population": scope.population_ref,
        "outcome": scope.outcome_ref,
        "selected_plan": owner_context.selected_plan_ref,  # type: ignore[dict-item]
        "selected_configuration": owner_context.selected_configuration_ref,  # type: ignore[dict-item]
        "selected_source_graph": owner_context.selected_source_graph_ref,  # type: ignore[dict-item]
        "selected_rule": owner_context.selected_rule_ref,  # type: ignore[dict-item]
        "selected_profile": owner_context.selected_profile_ref,  # type: ignore[dict-item]
        "selected_procedure": owner_context.selected_procedure_ref,  # type: ignore[dict-item]
        "selected_selection": owner_context.selected_selection_ref,  # type: ignore[dict-item]
        "valid_epoch": task_epoch_ref,
        "selected_method_input": owner_context.selected_method_input_ref,  # type: ignore[dict-item]
    }
    if scope.unit_scope_ref is not None:
        roots["unit_scope"] = scope.unit_scope_ref
    for item in owner_context.selected_state_input_refs:
        role = f"state_input.{item.role_path}"
        if role in roots:
            raise ValueError("owner-selected input roles cannot shadow a required basis root")
        roots[role] = item.ref
    inventory = derive_selected_dependency_inventory(store, roots)
    inventory_ref = persist_search_uncertainty_v2(store, inventory)
    obligation_id = _derive_search_obligation_id(ticket_id, owner_context.subject_ref, scope)
    basis = SearchUncertaintyBasisV2(
        obligation_id=obligation_id,
        subject_ref=owner_context.subject_ref,
        quantity_ref=scope.quantity_ref,
        treatment_contrast_ref=scope.treatment_contrast_ref,
        population_ref=scope.population_ref,
        outcome_ref=scope.outcome_ref,
        unit_scope_ref=scope.unit_scope_ref,
        unit_binding_status=scope.unit_binding_status,
        selected_plan_ref=owner_context.selected_plan_ref,  # type: ignore[arg-type]
        selected_configuration_ref=owner_context.selected_configuration_ref,  # type: ignore[arg-type]
        selected_source_graph_ref=owner_context.selected_source_graph_ref,  # type: ignore[arg-type]
        selected_rule_ref=owner_context.selected_rule_ref,  # type: ignore[arg-type]
        selected_profile_ref=owner_context.selected_profile_ref,  # type: ignore[arg-type]
        selected_procedure_ref=owner_context.selected_procedure_ref,  # type: ignore[arg-type]
        selected_selection_ref=owner_context.selected_selection_ref,  # type: ignore[arg-type]
        selected_state_input_refs=owner_context.selected_state_input_refs,
        valid_epoch_ref=task_epoch_ref,
        selected_method_fqn=owner_context.selected_method_fqn,  # type: ignore[arg-type]
        selected_method_abi_version=owner_context.selected_method_abi_version,  # type: ignore[arg-type]
        selected_method_abi_digest=owner_context.selected_method_abi_digest,  # type: ignore[arg-type]
        selected_method_params_sha256=owner_context.selected_method_params_sha256,  # type: ignore[arg-type]
        selected_method_params=owner_context.selected_method_params,  # type: ignore[arg-type]
        selected_method_seed=owner_context.selected_method_seed,  # type: ignore[arg-type]
        selected_inference_profile_id=owner_context.selected_inference_profile_id,  # type: ignore[arg-type]
        selected_method_input_ref=owner_context.selected_method_input_ref,  # type: ignore[arg-type]
        selected_method_input_content_sha256=(
            owner_context.selected_method_input_content_sha256  # type: ignore[arg-type]
        ),
        request_projection=owner_context.request_projection,  # type: ignore[arg-type]
        tenant_id=owner_context.tenant_id,  # type: ignore[arg-type]
        cell_id=owner_context.cell_id,
        dependency_inventory_ref=inventory_ref,
        dependency_inventory_sha256=inventory.sha256,
        quantity_semantics="causal_treatment_effect_contrast",
        target_scope=scope.requested_target_scope,
    )
    basis_ref = persist_search_uncertainty_v2(store, basis)
    persisted_basis = load_search_uncertainty_basis_v2(store, basis_ref)
    _verify_search_basis_owner_binding(
        persisted_basis,
        owner_context,
        ticket_id=ticket_id,
        task_epoch_ref=task_epoch_ref,
    )
    admission = SearchUncertaintyTaskAdmission(
        ticket_id=ticket_id,
        run_id=owner_context.run_id,
        ticket_generation=ticket_generation,
        status="unassessed",
        owner_context_ref=context_ref,
        task_epoch_ref=task_epoch_ref,
        basis_ref=basis_ref,
        admitted_at=selected_at,
    )
    admission_ref = persist_search_uncertainty_v2(store, admission)
    return context_ref, task_epoch_ref, admission_ref, basis_ref


def compute_relative_interval_halfwidth_routing(
    *,
    profile_ref: ArtifactRef,
    theta: float,
    lower_bound: float,
    upper_bound: float,
    confidence_level: float,
    comparison_key: str,
    unit_binding_status: Literal["bound", "unknown"],
) -> SearchUncertaintyRoutingScore:
    """Compute a stable, bounded routing ratio without promoting the measure."""
    if (
        profile_ref.kind != "scientist.search.uncertainty_routing_profile"
        or profile_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("routing profile must be selected before computing a score")
    operands = (theta, lower_bound, upper_bound)
    if not math.isfinite(confidence_level) or not 0.0 < confidence_level < 1.0:
        raise ValueError("native interval confidence level must be finite and in (0, 1)")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in operands):
        raise ValueError("native interval operands must be numeric")
    if any(not math.isfinite(float(value)) for value in operands) or lower_bound > upper_bound:
        raise ValueError("native interval operands must be finite and ordered")
    if unit_binding_status != "bound":
        reason: Literal[
            "unit_not_bound",
            "reference_scale_not_established",
            "zero_reference_scale",
            "interval_invalid",
            "scope_not_comparable",
        ] = "unit_not_bound"
    elif theta == 0.0:
        reason = "zero_reference_scale"
    else:
        try:
            with localcontext() as context:
                context.prec = 80
                lower = Decimal(str(lower_bound))
                upper = Decimal(str(upper_bound))
                point = abs(Decimal(str(theta)))
                width = upper - lower
                raw_ratio = width / (Decimal(2) * point)
                if not raw_ratio.is_finite() or raw_ratio < 0:
                    raise InvalidOperation
                capped = min(Decimal(1), raw_ratio)
                float_score = float(capped)
                if not math.isfinite(float_score):
                    raise InvalidOperation
                try:
                    width_float = float(width)
                    width_overflow = not math.isfinite(width_float)
                except OverflowError:
                    width_float = None
                    width_overflow = True
                try:
                    ratio_overflow = not math.isfinite(float(raw_ratio))
                except OverflowError:
                    ratio_overflow = True
                return SearchUncertaintyRoutingScore(
                    status="available",
                    profile_ref=profile_ref,
                    theta=float(theta),
                    lower_bound=float(lower_bound),
                    upper_bound=float(upper_bound),
                    width=None if width_overflow else width_float,
                    width_decimal=str(width),
                    width_overflow=width_overflow,
                    raw_ratio_decimal=str(raw_ratio),
                    raw_ratio_overflow=ratio_overflow,
                    saturated=raw_ratio > 1,
                    score=float_score,
                    confidence_level=confidence_level,
                    interval_semantics="native_mean_confidence_interval",
                    comparison_key=comparison_key,
                    limitations=(
                        "candidate_ordering_only",
                        "not_probability_or_calibrated_risk",
                        "model_conditional_selected_rows",
                        "does_not_promote_prune_stop_or_certify",
                    ),
                )
        except InvalidOperation, OverflowError, ValueError:
            # A finite positive ratio too large for Decimal evaluation is unavailable,
            # never represented by a spurious zero or hidden saturation.
            reason = "interval_invalid"
    return _unavailable_routing_score(
        profile_ref=profile_ref,
        theta=float(theta),
        lower_bound=float(lower_bound),
        upper_bound=float(upper_bound),
        confidence_level=confidence_level,
        comparison_key=comparison_key,
        reason=reason,
    )


def _unavailable_routing_score(
    *,
    profile_ref: ArtifactRef,
    theta: float,
    lower_bound: float,
    upper_bound: float,
    confidence_level: float,
    comparison_key: str,
    reason: Literal[
        "zero_reference_scale",
        "reference_scale_not_established",
        "interval_invalid",
        "unit_not_bound",
        "scope_not_comparable",
    ],
) -> SearchUncertaintyRoutingScore:
    return SearchUncertaintyRoutingScore(
        status="unavailable",
        profile_ref=profile_ref,
        unavailable_reason=reason,
        theta=theta,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        confidence_level=confidence_level,
        interval_semantics="native_mean_confidence_interval",
        comparison_key=comparison_key,
        limitations=(
            "native_assessment_retained",
            "candidate_ordering_only",
            f"routing_score_unavailable:{reason}",
        ),
    )


def make_comparison_key(
    *,
    basis: SearchUncertaintyBasisV2,
    confidence_level: float,
    interval_semantics: Literal["native_mean_confidence_interval"],
    sampling_profile_ref: ArtifactRef,
) -> str:
    """Bind a routing comparison to identical quantity, scope, alpha and method profile."""
    if not math.isfinite(confidence_level) or not 0.0 < confidence_level < 1.0:
        raise ValueError("comparison confidence level must be finite and in (0, 1)")
    if sampling_profile_ref.manifest_profile_sha256 is None:
        raise ValueError("comparison sampling profile must select a manifest profile")
    payload = {
        "quantity": _ref_key(basis.quantity_ref),
        "contrast": _ref_key(basis.treatment_contrast_ref),
        "population": _ref_key(basis.population_ref),
        "outcome": _ref_key(basis.outcome_ref),
        "unit_scope": (None if basis.unit_scope_ref is None else _ref_key(basis.unit_scope_ref)),
        "unit_binding_status": basis.unit_binding_status,
        "valid_epoch": _ref_key(basis.valid_epoch_ref),
        "confidence_level": confidence_level,
        "interval_semantics": interval_semantics,
        "sampling_profile": _ref_key(sampling_profile_ref),
        "profile": _ref_key(basis.selected_profile_ref),
        "method_fqn": basis.selected_method_fqn,
        "method_abi_version": basis.selected_method_abi_version,
        "method_params_sha256": basis.selected_method_params_sha256,
        "method_seed": basis.selected_method_seed,
        "method_input": _ref_key(basis.selected_method_input_ref),
        "request_projection": basis.request_projection.model_dump(mode="json"),
        "tenant_id": basis.tenant_id,
        "cell_id": basis.cell_id,
        "inference_profile_id": basis.selected_inference_profile_id,
    }
    return _canonical_sha256(payload)


def persist_search_uncertainty_v2(
    store: SearchUncertaintyStore,
    payload: (
        SearchUncertaintyRoutingProfile
        | SearchUncertaintyRefinementProfile
        | SearchUncertaintyOwnerTaskContext
        | SearchUncertaintyTaskEpoch
        | SearchUncertaintyTaskAdmission
        | SearchUncertaintyTaskBinding
        | SearchOwnerSelectedSourceGraph
        | SearchRuntimeStageConfiguration
        | SearchUncertaintyInputInventory
        | SearchUncertaintyBasisV2
        | SearchUnassessedObservationV2
        | SearchAssessedObservationV2
        | SearchUncertaintyRefinement
        | SearchUncertaintyTicketProjection
    ),
) -> ArtifactRef:
    """Persist one strict AD06 value with content-bound selected dependency edges."""
    if isinstance(payload, SearchUncertaintyOwnerTaskContext):
        kind = "scientist.search.uncertainty_owner_task_context"
        role_refs = [("subject", payload.subject_ref)]
        for role, ref in (
            ("selected_plan", payload.selected_plan_ref),
            ("selected_configuration", payload.selected_configuration_ref),
            ("selected_source_graph", payload.selected_source_graph_ref),
            ("selected_rule", payload.selected_rule_ref),
            ("selected_profile", payload.selected_profile_ref),
            ("selected_procedure", payload.selected_procedure_ref),
            ("selected_selection", payload.selected_selection_ref),
        ):
            if ref is not None:
                role_refs.append((role, ref))
        role_refs.extend(
            (f"state_input.{item.role_path}", item.ref)
            for item in payload.selected_state_input_refs
        )
        if payload.selected_method_input_ref is not None:
            role_refs.append(("selected_method_input", payload.selected_method_input_ref))
        if payload.semantic_scope is not None:
            for role in (
                "quantity",
                "treatment_contrast",
                "population",
                "outcome",
                "unit_scope",
            ):
                ref = getattr(payload.semantic_scope, f"{role}_ref")
                if ref is not None:
                    role_refs.append((f"semantic_scope.{role}", ref))
        schema_name, version = "polisyos.scientist.SearchUncertaintyOwnerTaskContext", "1.0"
    elif isinstance(payload, SearchUncertaintyTaskEpoch):
        kind = "scientist.search.uncertainty_task_epoch"
        role_refs = [("owner_context", payload.owner_context_ref)]
        schema_name, version = "polisyos.scientist.SearchUncertaintyTaskEpoch", "1.0"
    elif isinstance(payload, SearchUncertaintyTaskAdmission):
        kind = "scientist.search.uncertainty_task_admission"
        role_refs = [
            ("owner_context", payload.owner_context_ref),
            ("task_epoch", payload.task_epoch_ref),
        ]
        if payload.basis_ref is not None:
            role_refs.append(("basis", payload.basis_ref))
        schema_name, version = "polisyos.scientist.SearchUncertaintyTaskAdmission", "1.0"
    elif isinstance(payload, SearchUncertaintyTaskBinding):
        kind = "scientist.search.uncertainty_task_binding"
        role_refs = [
            ("source_projection", payload.source_projection_ref),
            ("task_admission", payload.task_admission_ref),
            ("task_epoch", payload.task_epoch_ref),
            ("owner_context", payload.owner_context_ref),
            ("basis", payload.basis_ref),
            ("dependency_inventory", payload.dependency_inventory_ref),
            ("selected_method_input", payload.selected_method_input_ref),
        ]
        schema_name, version = "polisyos.scientist.SearchUncertaintyTaskBinding", "1.0"
    elif isinstance(payload, SearchOwnerSelectedSourceGraph):
        kind = "scientist.search.selected_source_graph"
        role_refs = [(item.role_path, item.ref) for item in payload.roots]
        schema_name, version = "polisyos.scientist.SearchOwnerSelectedSourceGraph", "1.0"
    elif isinstance(payload, SearchRuntimeStageConfiguration):
        kind = "scientist.search.runtime_stage_configuration"
        role_refs = []
        schema_name, version = "polisyos.scientist.SearchRuntimeStageConfiguration", "1.0"
    elif isinstance(payload, SearchUncertaintyRoutingProfile):
        kind = "scientist.search.uncertainty_routing_profile"
        role_refs = []
        schema_name, version = "polisyos.scientist.SearchUncertaintyRoutingProfile", "1.0"
    elif isinstance(payload, SearchUncertaintyRefinementProfile):
        kind = "scientist.search.uncertainty_refinement_profile"
        role_refs = []
        schema_name, version = "polisyos.scientist.SearchUncertaintyRefinementProfile", "1.0"
    elif isinstance(payload, SearchUncertaintyInputInventory):
        kind = "scientist.search.uncertainty_input_inventory"
        role_refs = [(member.role_path, member.ref) for member in payload.members]
        schema_name, version = "polisyos.scientist.SearchUncertaintyInputInventory", "1.0"
    elif isinstance(payload, SearchUncertaintyBasisV2):
        kind = "scientist.search.uncertainty_basis"
        role_refs = [
            ("subject", payload.subject_ref),
            ("quantity", payload.quantity_ref),
            ("treatment_contrast", payload.treatment_contrast_ref),
            ("population", payload.population_ref),
            ("outcome", payload.outcome_ref),
            ("selected_plan", payload.selected_plan_ref),
            ("selected_configuration", payload.selected_configuration_ref),
            ("selected_source_graph", payload.selected_source_graph_ref),
            ("selected_rule", payload.selected_rule_ref),
            ("selected_profile", payload.selected_profile_ref),
            ("selected_procedure", payload.selected_procedure_ref),
            ("selected_selection", payload.selected_selection_ref),
            ("valid_epoch", payload.valid_epoch_ref),
            ("dependency_inventory", payload.dependency_inventory_ref),
            ("selected_method_input", payload.selected_method_input_ref),
        ]
        role_refs.extend(
            (f"state_input.{item.role_path}", item.ref)
            for item in payload.selected_state_input_refs
        )
        if payload.unit_scope_ref is not None:
            role_refs.append(("unit_scope", payload.unit_scope_ref))
        schema_name, version = "polisyos.scientist.SearchUncertaintyBasis", "2.0"
    elif isinstance(payload, SearchUnassessedObservationV2):
        kind = "scientist.search.uncertainty_observation"
        role_refs = [("basis", payload.basis_ref), ("task_admission", payload.task_admission_ref)]
        schema_name, version = "polisyos.scientist.SearchUncertaintyObservation", "2.0"
    elif isinstance(payload, SearchAssessedObservationV2):
        kind = "scientist.search.uncertainty_observation"
        role_refs = [
            ("basis", payload.basis_ref),
            ("predecessor", payload.predecessor_ref),
            ("search_task_binding", payload.search_uncertainty_task_binding_ref),
            ("owned_attempt_anchor", payload.owned_attempt_anchor_ref),
            ("hte_outcome", payload.hte_outcome_ref),
            ("routing_profile", payload.routing_score.profile_ref),
            ("source_data", payload.source_data_ref),
            ("method_result", payload.method_result_ref),
            ("method_evidence", payload.method_evidence_ref),
        ]
        if payload.point_result_ref is not None:
            role_refs.append(("point_result", payload.point_result_ref))
        if payload.hte_result_ref is not None:
            role_refs.append(("hte_result", payload.hte_result_ref))
        if payload.inference_basis_ref is not None:
            role_refs.append(("inference_basis", payload.inference_basis_ref))
        if payload.unit_scope_ref is not None:
            role_refs.append(("unit_scope", payload.unit_scope_ref))
        if payload.invocation_basis_ref is not None:
            role_refs.append(("invocation_basis", payload.invocation_basis_ref))
        schema_name, version = "polisyos.scientist.SearchUncertaintyObservation", "2.0"
    elif isinstance(payload, SearchUncertaintyRefinement):
        kind = "scientist.search.uncertainty_refinement"
        role_refs = [
            ("predecessor", payload.predecessor_ref),
            ("successor", payload.successor_ref),
            ("basis", payload.basis_ref),
            ("profile", payload.profile_ref),
            ("owned_attempt_anchor", payload.owned_attempt_anchor_ref),
        ]
        schema_name, version = "polisyos.scientist.SearchUncertaintyRefinement", "1.0"
    else:
        kind = "scientist.search.uncertainty_ticket_projection"
        role_refs = [
            (f"unassessed.{index:06d}", ref)
            for index, ref in enumerate(payload.unassessed_observation_refs)
        ]
        role_refs.extend(
            (f"historical_observation.{index:06d}", ref)
            for index, ref in enumerate(payload.historical_observation_refs)
        )
        role_refs.extend(
            (f"historical_refinement.{index:06d}", ref)
            for index, ref in enumerate(payload.historical_refinement_refs)
        )
        if payload.previous_projection_ref is not None:
            role_refs.append(("previous_projection", payload.previous_projection_ref))
        if payload.task_admission_ref is not None:
            role_refs.append(("task_admission", payload.task_admission_ref))
        for index, obligation in enumerate(payload.current_obligations):
            role_refs.extend(
                [
                    (f"current.{index:06d}.basis", obligation.basis_ref),
                    (f"current.{index:06d}.predecessor", obligation.predecessor_ref),
                    *[
                        (f"current.{index:06d}.successor.{member:06d}", item.observation_ref)
                        for member, item in enumerate(obligation.successors)
                    ],
                    *[
                        (f"current.{index:06d}.refinement.{member:06d}", item.refinement_ref)
                        for member, item in enumerate(obligation.successors)
                    ],
                    *[
                        (
                            f"current.{index:06d}.routing_profile.{member:06d}",
                            item.routing_score.profile_ref,
                        )
                        for member, item in enumerate(obligation.successors)
                    ],
                ]
            )
        schema_name, version = "polisyos.scientist.SearchUncertaintyTicketProjection", "1.0"
    role_refs = sorted({(role, _ref_key(ref)): (role, ref) for role, ref in role_refs}.values())
    inputs = [input_ref_from_artifact_ref(ref, role=f"selected.{role}") for role, ref in role_refs]
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def persist_search_uncertainty_routing_profile(store: SearchUncertaintyStore) -> ArtifactRef:
    """Persist the selected routing profile through the Search artifact owner."""
    return persist_search_uncertainty_v2(store, SearchUncertaintyRoutingProfile())


def persist_search_uncertainty_refinement_profile(store: SearchUncertaintyStore) -> ArtifactRef:
    """Persist the single selected same-basis first-assessment relation profile."""
    return persist_search_uncertainty_v2(store, SearchUncertaintyRefinementProfile())


def _load_typed_search_artifact[T: BaseModel](
    store: SearchUncertaintyStore, ref: ArtifactRef, model: type[T], *, kind: str
) -> T:
    from polisyos.core.artifacts import validate_core_model_json_artifact

    if ref.kind != kind or ref.manifest_profile_sha256 is None:
        raise ValueError(f"selected Search uncertainty artifact has wrong identity: {kind}")
    if not store.verify(ref).ok:
        raise ValueError("selected Search uncertainty artifact failed integrity verification")
    return validate_core_model_json_artifact(model, store, ref)


def _verify_first_assessment_edge(
    *,
    ticket_id: str,
    predecessor_ref: ArtifactRef,
    predecessor: SearchUnassessedObservationV2,
    successor_ref: ArtifactRef,
    successor: SearchAssessedObservationV2,
    refinement_ref: ArtifactRef,
    refinement: SearchUncertaintyRefinement,
    expected_generation: int,
) -> None:
    """Enforce the exact first-assessment relation over loaded CAS payloads."""
    pairs = (
        (_ref_key(predecessor_ref), _ref_key(successor.predecessor_ref)),
        (_ref_key(predecessor_ref), _ref_key(refinement.predecessor_ref)),
        (_ref_key(successor_ref), _ref_key(refinement.successor_ref)),
        (_ref_key(predecessor.basis_ref), _ref_key(successor.basis_ref)),
        (_ref_key(successor.basis_ref), _ref_key(refinement.basis_ref)),
        (
            _ref_key(successor.owned_attempt_anchor_ref),
            _ref_key(refinement.owned_attempt_anchor_ref),
        ),
    )
    if any(left != right for left, right in pairs):
        raise ValueError("first-assessment relation refs disagree")
    if predecessor.state != "unassessed" or successor.state != "assessed":
        raise ValueError("first-assessment relation requires unassessed→assessed states")
    if predecessor.obligation_id != successor.obligation_id:
        raise ValueError("first-assessment relation changes the uncertainty obligation")
    if predecessor.ticket_id != ticket_id or successor.ticket_id != ticket_id:
        raise ValueError("first-assessment relation is not bound to the selected ticket")
    if refinement.relation != "unassessed_to_assessed_same_basis@1.0":
        raise ValueError("unsupported Search uncertainty refinement relation")
    if (
        predecessor.ticket_generation != expected_generation
        or successor.ticket_generation != expected_generation
        or refinement.expected_ticket_generation != expected_generation
    ):
        raise StaleSearchTicketGenerationError(
            "refinement does not match the selected ticket generation"
        )
    if any(
        ref.manifest_profile_sha256 is None
        for ref in (predecessor_ref, successor_ref, refinement_ref)
    ):
        raise ValueError("first-assessment refs must be selected by manifest profile")


def _dedupe_refs(refs: Iterable[ArtifactRef]) -> list[ArtifactRef]:
    by_identity = {_ref_key(ref): ref for ref in refs}
    return [by_identity[key] for key in sorted(by_identity)]


class StaleSearchTicketGenerationError(RuntimeError):
    """A refinement was produced for an older owned ticket state revision."""


class StaleSearchTicketRevisionError(RuntimeError):
    """A Search ticket write used a stale projection revision."""


class SearchUncertaintyTicketState:
    """Atomic Search-owned pointer to immutable ticket projections.

    The per-ticket file is a bounded extension of the existing funnel ticket
    owner. CAS objects hold immutable history; the file stores only generation,
    revision, and the current projection ref. It is not an event store.
    """

    def __init__(
        self,
        store: SearchUncertaintyStore,
        *,
        owned_attempt_association_resolver: SearchOwnedAttemptAssociationResolver | None = None,
        owned_historical_attempt_association_resolver: (
            SearchOwnedHistoricalAttemptAssociationResolver | None
        ) = None,
        completion_owner: SearchHTECompletionOwner | None = None,
        owned_attempt_projection_resolver: SearchOwnedAttemptProjectionResolver | None = None,
        owned_hte_summary_resolver: SearchOwnedHTESummaryResolver | None = None,
    ) -> None:
        self._store = store
        self._root = Path(store.root) / "scientist-funnel" / "ticket-owner-state"
        self._legacy_root = Path(store.root) / "scientist-search" / "funnel-uncertainty-current"
        self._owned_attempt_association_resolver = owned_attempt_association_resolver
        self._owned_historical_attempt_association_resolver = (
            owned_historical_attempt_association_resolver
        )
        self._completion_owner = completion_owner
        self._owned_attempt_projection_resolver = owned_attempt_projection_resolver
        self._owned_hte_summary_resolver = owned_hte_summary_resolver

    def initialize(self, ticket_id: str) -> SearchUncertaintyTicketIndexRow:
        """Create an initial ticket row, preserving any already-owned row."""
        return self._transact(
            ticket_id,
            lambda row: (
                row
                or SearchUncertaintyTicketIndexRow(
                    ticket_id=ticket_id,
                    ticket_generation=1,
                    owner_revision=0,
                    projection_revision=0,
                )
            ),
        )

    def publish_task_binding(
        self,
        ticket_id: str,
        *,
        expected_generation: int,
        expected_projection_revision: int,
    ) -> ArtifactRef | None:
        """Publish a complete owner-derived binding through the FunnelTicket row.

        A not-established admission remains candidate-only and returns no binding.
        The selected projection is written first; the binding then references its
        frozen bytes and the ticket owner atomically advances its own revision.
        """
        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            if row is None:
                raise KeyError("Search uncertainty ticket state is not initialized")
            if row.ticket_generation != expected_generation:
                raise StaleSearchTicketGenerationError(
                    "task binding was produced for an older FunnelTicket generation"
                )
            if row.current_binding_ref is not None:
                binding = load_search_uncertainty_task_binding(self._store, row.current_binding_ref)
                if (
                    binding.ticket_generation == expected_generation
                    and binding.ticket_id == ticket_id
                    and binding.source_projection_ref == row.current_projection_ref
                ):
                    return row.current_binding_ref
                raise ValueError("ticket generation already has a different task binding")
            if row.task_admission_ref is not None:
                for historical_ref in reversed(row.historical_binding_refs):
                    historical = load_search_uncertainty_task_binding(self._store, historical_ref)
                    if (
                        historical.ticket_generation == expected_generation
                        and historical.ticket_id == ticket_id
                        and _ref_key(historical.task_admission_ref)
                        == _ref_key(row.task_admission_ref)
                    ):
                        # One admitted task gets one pre-fit capability. After a
                        # completion clears the live pointer, replaying this producer
                        # returns the historical ref; Runtime's live resolver will
                        # correctly deny a new attempt against that stale ref.
                        return historical_ref
            if row.projection_revision != expected_projection_revision:
                raise StaleSearchTicketRevisionError(
                    "task binding used a stale FunnelTicket projection revision"
                )
            if row.current_projection_ref is None or row.task_admission_ref is None:
                return None
            admission = _load_typed_search_artifact(
                self._store,
                row.task_admission_ref,
                SearchUncertaintyTaskAdmission,
                kind="scientist.search.uncertainty_task_admission",
            )
            if admission.status != "unassessed" or admission.basis_ref is None:
                return None
            context = _load_typed_search_artifact(
                self._store,
                admission.owner_context_ref,
                SearchUncertaintyOwnerTaskContext,
                kind="scientist.search.uncertainty_owner_task_context",
            )
            if context.status != "ready" or context.request_projection is None:
                return None
            if context.selected_method_params is None:
                raise ValueError("ready owner context omitted selected method parameters")
            if (
                row.owner_context_ref is None
                or _ref_key(row.owner_context_ref) != _ref_key(admission.owner_context_ref)
                or row.task_epoch_ref is None
                or _ref_key(row.task_epoch_ref) != _ref_key(admission.task_epoch_ref)
            ):
                raise ValueError("FunnelTicket owner row differs from its selected admission")
            basis = load_search_uncertainty_basis_v2(self._store, admission.basis_ref)
            inventory = load_search_uncertainty_input_inventory(
                self._store, basis.dependency_inventory_ref
            )
            source_projection = self._read_projection_for_row(row)
            if (
                source_projection is None
                or source_projection.ticket_id != ticket_id
                or source_projection.ticket_generation != expected_generation
                or source_projection.projection_revision != expected_projection_revision
                or source_projection.task_admission_ref is None
                or _ref_key(source_projection.task_admission_ref)
                != _ref_key(row.task_admission_ref)
            ):
                raise ValueError("binding source projection does not select this task admission")
            if (
                context.tenant_id is None
                or context.selected_method_seed is None
                or context.selected_method_input_ref is None
                or context.selected_method_input_content_sha256 is None
                or context.selected_inference_profile_id is None
                or context.selected_method_fqn is None
                or context.selected_method_abi_version is None
                or context.selected_method_abi_digest is None
                or context.selected_method_params_sha256 is None
            ):
                return None
            _verify_search_basis_owner_binding(
                basis,
                context,
                ticket_id=ticket_id,
                task_epoch_ref=admission.task_epoch_ref,
            )
            _selected_ref(
                self._store,
                context.selected_method_input_ref,
                role="selected_method_input",
            )
            if (
                context.selected_method_input_ref.artifact_id.hex
                != context.selected_method_input_content_sha256
                or not any(
                    _ref_key(item.ref) == _ref_key(context.selected_method_input_ref)
                    for item in inventory.members
                )
            ):
                raise ValueError("binding input is not a member of the recomputed dependency set")
            binding = SearchUncertaintyTaskBinding.model_validate(
                {
                    "ticket_id": ticket_id,
                    "parent_run_id": context.run_id,
                    "ticket_generation": expected_generation,
                    "owner_revision": row.owner_revision + 1,
                    "projection_revision": row.projection_revision,
                    "source_projection_ref": row.current_projection_ref,
                    "task_admission_ref": row.task_admission_ref,
                    "task_epoch_ref": admission.task_epoch_ref,
                    "owner_context_ref": admission.owner_context_ref,
                    "basis_ref": admission.basis_ref,
                    "dependency_inventory_ref": basis.dependency_inventory_ref,
                    "dependency_inventory_sha256": basis.dependency_inventory_sha256,
                    "tenant_id": context.tenant_id,
                    "cell_id": context.cell_id,
                    "request_projection": context.request_projection,
                    "selected_method_fqn": context.selected_method_fqn,
                    "selected_method_abi_version": context.selected_method_abi_version,
                    "selected_method_abi_digest": context.selected_method_abi_digest,
                    "selected_method_params_sha256": context.selected_method_params_sha256,
                    "selected_method_params": context.selected_method_params,
                    "selected_method_seed": context.selected_method_seed,
                    "selected_inference_profile_id": context.selected_inference_profile_id,
                    "selected_method_input_ref": context.selected_method_input_ref,
                    "selected_method_input_content_sha256": (
                        context.selected_method_input_content_sha256
                    ),
                    "admitted_at": admission.admitted_at,
                }
            )
            if _ref_key(binding.basis_ref) != _ref_key(admission.basis_ref):
                raise ValueError("task binding basis differs from its selected admission")
            binding_ref = persist_search_uncertainty_v2(self._store, binding)
            _validate_search_task_binding_closure(self._store, binding_ref, binding)
            updated = row.model_copy(
                update={
                    "owner_revision": binding.owner_revision,
                    "current_binding_ref": binding_ref,
                }
            )
            self._write_row(updated)
            return binding_ref

    def bump_ticket_generation(
        self, ticket_id: str, *, expected_generation: int
    ) -> SearchUncertaintyTicketIndexRow:
        """Start a new task generation and retain prior state only as history."""
        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            if row is None:
                raise KeyError("Search uncertainty ticket state is not initialized")
            if row.ticket_generation != expected_generation:
                raise StaleSearchTicketGenerationError(
                    "ticket generation changed before task reissue"
                )
            prior = self._read_projection_for_row(row)
            next_generation = expected_generation + 1
            if prior is None:
                next_projection = SearchUncertaintyTicketProjection(
                    ticket_id=ticket_id,
                    ticket_generation=next_generation,
                    projection_revision=row.projection_revision,
                    limitations=("as_of_task_epoch_only", "live_currentness_not_established"),
                )
            else:
                prior_successors = tuple(
                    item.observation_ref
                    for obligation in prior.current_obligations
                    for item in obligation.successors
                )
                prior_refinements = tuple(
                    item.refinement_ref
                    for obligation in prior.current_obligations
                    for item in obligation.successors
                )
                next_projection = SearchUncertaintyTicketProjection(
                    ticket_id=ticket_id,
                    ticket_generation=next_generation,
                    projection_revision=row.projection_revision,
                    previous_projection_ref=row.current_projection_ref,
                    historical_observation_refs=tuple(
                        _dedupe_refs(
                            (
                                *prior.historical_observation_refs,
                                *prior.unassessed_observation_refs,
                                *prior_successors,
                            )
                        )
                    ),
                    historical_refinement_refs=tuple(
                        _dedupe_refs((*prior.historical_refinement_refs, *prior_refinements))
                    ),
                    limitations=("as_of_task_epoch_only", "live_currentness_not_established"),
                )
            # Advance the owner row and immutable projection in one locked write.
            # Passing the old row to _publish_locked would reject every legitimate
            # generation bump as stale (row.ticket_generation != next_generation).
            advanced_row = row.model_copy(update={"ticket_generation": next_generation})
            advanced_row = advanced_row.model_copy(
                update={
                    "owner_context_ref": None,
                    "task_epoch_ref": None,
                    "task_admission_ref": None,
                }
            )
            return self._publish_locked(
                advanced_row,
                expected_generation=next_generation,
                projection=next_projection,
            )

    def record_task_admission(
        self,
        *,
        ticket_id: str,
        expected_generation: int,
        expected_projection_revision: int,
        admission_ref: ArtifactRef,
    ) -> SearchUncertaintyTicketIndexRow:
        """Atomically select the immutable pre-dispatch admission for this ticket."""
        admission = _load_typed_search_artifact(
            self._store,
            admission_ref,
            SearchUncertaintyTaskAdmission,
            kind="scientist.search.uncertainty_task_admission",
        )
        if admission.ticket_id != ticket_id or admission.ticket_generation != expected_generation:
            raise ValueError("task admission does not match the selected ticket generation")
        owner_context = _load_typed_search_artifact(
            self._store,
            admission.owner_context_ref,
            SearchUncertaintyOwnerTaskContext,
            kind="scientist.search.uncertainty_owner_task_context",
        )
        configuration_missing = _validate_search_owner_task_context(self._store, owner_context)
        task_epoch = _load_typed_search_artifact(
            self._store,
            admission.task_epoch_ref,
            SearchUncertaintyTaskEpoch,
            kind="scientist.search.uncertainty_task_epoch",
        )
        if (
            owner_context.run_id != admission.run_id
            or task_epoch.run_id != admission.run_id
            or task_epoch.ticket_id != ticket_id
            or task_epoch.ticket_generation != expected_generation
            or _ref_key(task_epoch.owner_context_ref) != _ref_key(admission.owner_context_ref)
        ):
            raise ValueError("task-admission owner context and epoch do not reconcile")
        unassessed_ref: ArtifactRef | None = None
        obligation_id: str | None = None
        if admission.status == "unassessed":
            assert admission.basis_ref is not None
            basis = load_search_uncertainty_basis_v2(self._store, admission.basis_ref)
            if configuration_missing:
                raise ValueError("unassessed task admission has unresolved stage bindings")
            _verify_search_basis_owner_binding(
                basis,
                owner_context,
                ticket_id=ticket_id,
                task_epoch_ref=admission.task_epoch_ref,
            )
            obligation_id = basis.obligation_id
            unassessed_ref = persist_search_uncertainty_v2(
                self._store,
                SearchUnassessedObservationV2(
                    basis_ref=admission.basis_ref,
                    obligation_id=basis.obligation_id,
                    task_admission_ref=admission_ref,
                    ticket_id=ticket_id,
                    ticket_generation=expected_generation,
                    reason_code="native_method_assessment_pending",
                    admitted_at=admission.admitted_at,
                ),
            )

        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            if row is None:
                raise KeyError("Search uncertainty ticket state is not initialized")
            if row.ticket_generation != expected_generation:
                raise StaleSearchTicketGenerationError(
                    "task admission was produced for an older ticket generation"
                )
            if row.task_admission_ref is not None:
                if _ref_key(row.task_admission_ref) == _ref_key(admission_ref):
                    return row
                selected = _load_typed_search_artifact(
                    self._store,
                    row.task_admission_ref,
                    SearchUncertaintyTaskAdmission,
                    kind="scientist.search.uncertainty_task_admission",
                )
                if (
                    _ref_key(selected.owner_context_ref) == _ref_key(admission.owner_context_ref)
                    and selected.ticket_id == admission.ticket_id
                    and selected.ticket_generation == admission.ticket_generation
                ):
                    # Concurrent duplicate delivery for one unchanged owner context is
                    # idempotent. The first CAS selection fixes selected_at for this epoch.
                    return row
                raise ValueError("ticket generation already has a different task admission")
            if row.projection_revision != expected_projection_revision:
                raise StaleSearchTicketRevisionError(
                    "task admission used a stale Search projection revision"
                )
            projection = self._read_projection_for_row(row) or SearchUncertaintyTicketProjection(
                ticket_id=ticket_id,
                ticket_generation=expected_generation,
                projection_revision=row.projection_revision,
                limitations=("as_of_task_epoch_only", "live_currentness_not_established"),
            )
            if projection.task_admission_ref is not None:
                raise ValueError("ticket projection already selects another task admission")
            unassessed_refs = projection.unassessed_observation_refs
            historical_refs = projection.historical_observation_refs
            unknown_ids = set(projection.active_unknown_obligation_ids)
            limitations = set(projection.limitations)
            if admission.status == "unassessed":
                if unassessed_ref is None or obligation_id is None:
                    raise ValueError("unassessed admission omitted its selected observation")
                unassessed_refs = tuple(_dedupe_refs((*unassessed_refs, unassessed_ref)))
                historical_refs = tuple(_dedupe_refs((*historical_refs, unassessed_ref)))
                unknown_ids.add(obligation_id)
                limitations.add("native_assessment_pending")
            else:
                limitations.update(admission.missing_slices)
                limitations.add("pre_dispatch_basis_not_established")
            next_projection = projection.model_copy(
                update={
                    "task_admission_ref": admission_ref,
                    "unassessed_observation_refs": unassessed_refs,
                    "historical_observation_refs": historical_refs,
                    "active_unknown_obligation_ids": tuple(sorted(unknown_ids)),
                    "limitations": tuple(sorted(limitations)),
                }
            )
            selected_row = row.model_copy(
                update={
                    "owner_context_ref": admission.owner_context_ref,
                    "task_epoch_ref": admission.task_epoch_ref,
                    "task_admission_ref": admission_ref,
                }
            )
            return self._publish_locked(
                selected_row,
                expected_generation=expected_generation,
                projection=next_projection,
            )

    def record_first_assessment(
        self,
        *,
        ticket_id: str,
        expected_generation: int,
        expected_projection_revision: int,
        predecessor_ref: ArtifactRef,
        successor_ref: ArtifactRef,
        refinement_ref: ArtifactRef,
        completion_owner: SearchHTECompletionOwner,
        completion_association: SearchOwnedAttemptAssociation | None = None,
        tenant_id: str,
        cell_id: str | None,
    ) -> SearchUncertaintyTicketIndexRow:
        """Admit the first same-basis assessment or retain a real same-generation conflict."""
        predecessor = _load_typed_search_artifact(
            self._store,
            predecessor_ref,
            SearchUnassessedObservationV2,
            kind="scientist.search.uncertainty_observation",
        )
        successor = _load_typed_search_artifact(
            self._store,
            successor_ref,
            SearchAssessedObservationV2,
            kind="scientist.search.uncertainty_observation",
        )
        refinement = _load_typed_search_artifact(
            self._store,
            refinement_ref,
            SearchUncertaintyRefinement,
            kind="scientist.search.uncertainty_refinement",
        )
        relation_profile = _load_typed_search_artifact(
            self._store,
            refinement.profile_ref,
            SearchUncertaintyRefinementProfile,
            kind="scientist.search.uncertainty_refinement_profile",
        )
        if relation_profile.profile_id != refinement.relation:
            raise ValueError("refinement profile does not implement its declared relation")
        _verify_first_assessment_edge(
            ticket_id=ticket_id,
            predecessor_ref=predecessor_ref,
            predecessor=predecessor,
            successor_ref=successor_ref,
            successor=successor,
            refinement_ref=refinement_ref,
            refinement=refinement,
            expected_generation=expected_generation,
        )
        load_search_uncertainty_basis_v2(self._store, predecessor.basis_ref)
        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            if row is None:
                raise KeyError("Search uncertainty ticket state is not initialized")
            # The exact event is immutable and remains addressable after a newer
            # attempt or ticket generation supersedes the current pointer.
            self._verify_owned_attempt_association(
                successor,
                completion_owner=completion_owner if completion_association is None else None,
                owner_association=completion_association,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            projection = self._read_projection_for_row(row) or SearchUncertaintyTicketProjection(
                ticket_id=ticket_id,
                ticket_generation=row.ticket_generation,
                projection_revision=row.projection_revision,
                limitations=("as_of_task_epoch_only", "live_currentness_not_established"),
            )
            if row.ticket_generation < expected_generation:
                raise StaleSearchTicketGenerationError(
                    "Search ticket owner is older than the admitted completion generation"
                )
            admitted_binding_refs = {
                _ref_key(ref)
                for ref in (
                    *row.historical_binding_refs,
                    *(() if row.current_binding_ref is None else (row.current_binding_ref,)),
                )
            }
            if (
                successor.ticket_id != ticket_id
                or successor.ticket_generation != expected_generation
                or _ref_key(successor.search_uncertainty_task_binding_ref)
                not in admitted_binding_refs
            ):
                raise ValueError(
                    "assessment does not resolve to a binding admitted by this owner row"
                )
            admitted_observations = tuple(
                _dedupe_refs(
                    (
                        *projection.historical_observation_refs,
                        *projection.unassessed_observation_refs,
                        *(
                            item.observation_ref
                            for obligation in projection.current_obligations
                            for item in obligation.successors
                        ),
                    )
                )
            )
            for admitted_ref in admitted_observations:
                payload = get_json_artifact(self._store, admitted_ref)
                if not isinstance(payload, Mapping) or payload.get("state") != "assessed":
                    continue
                existing = SearchAssessedObservationV2.model_validate(payload)
                if (
                    existing.job_id == successor.job_id
                    and existing.completed_event_id == successor.completed_event_id
                ):
                    if (
                        existing.completed_event_payload_sha256
                        != successor.completed_event_payload_sha256
                        or _ref_key(existing.search_uncertainty_task_binding_ref)
                        != _ref_key(successor.search_uncertainty_task_binding_ref)
                        or _ref_key(existing.hte_outcome_ref) != _ref_key(successor.hte_outcome_ref)
                    ):
                        raise ValueError(
                            "one Runtime completion event resolved to different Search content"
                        )
                    return row
            slot = next(
                (
                    item
                    for item in projection.current_obligations
                    if item.obligation_id == successor.obligation_id
                    and _ref_key(item.basis_ref) == _ref_key(successor.basis_ref)
                    and _ref_key(item.predecessor_ref) == _ref_key(predecessor_ref)
                    and item.expected_ticket_generation == expected_generation
                ),
                None,
            )
            if slot is not None and any(
                _ref_key(existing.observation_ref) == _ref_key(successor_ref)
                and _ref_key(existing.refinement_ref) == _ref_key(refinement_ref)
                for existing in slot.successors
            ):
                return row
            if _ref_key(successor_ref) in {
                _ref_key(ref) for ref in projection.historical_observation_refs
            } and _ref_key(refinement_ref) in {
                _ref_key(ref) for ref in projection.historical_refinement_refs
            }:
                return row
            if row.ticket_generation > expected_generation:
                # A late completion belongs to the old immutable task epoch. Keep
                # it in history, but never let it replace the new generation's
                # unknown/current obligation.
                history_keys = {_ref_key(ref) for ref in projection.historical_observation_refs}
                if _ref_key(predecessor_ref) not in history_keys:
                    raise ValueError(
                        "late completion predecessor is not retained as ticket history"
                    )
                updated_projection = projection.model_copy(
                    update={
                        "historical_observation_refs": tuple(
                            _dedupe_refs((*projection.historical_observation_refs, successor_ref))
                        ),
                        "historical_refinement_refs": tuple(
                            _dedupe_refs((*projection.historical_refinement_refs, refinement_ref))
                        ),
                        "historical_binding_refs": tuple(
                            _dedupe_refs(
                                (
                                    *projection.historical_binding_refs,
                                    successor.search_uncertainty_task_binding_ref,
                                )
                            )
                        ),
                        "limitations": tuple(
                            sorted(
                                set(projection.limitations)
                                | {"late_completed_attempt_retained_as_history"}
                            )
                        ),
                    }
                )
                return self._publish_locked(
                    row,
                    expected_generation=row.ticket_generation,
                    projection=updated_projection,
                )
            if slot is not None:
                for existing in slot.successors:
                    if _ref_key(existing.observation_ref) == _ref_key(successor_ref):
                        if _ref_key(existing.refinement_ref) != _ref_key(refinement_ref):
                            raise ValueError(
                                "one successor cannot be rebound to a different refinement"
                            )
                        return row
                contenders = tuple(
                    sorted(
                        (
                            *slot.successors,
                            SearchUncertaintyCurrentSuccessor(
                                observation_ref=successor_ref,
                                refinement_ref=refinement_ref,
                                routing_score=successor.routing_score,
                            ),
                        ),
                        key=lambda item: _ref_key(item.observation_ref),
                    )
                )
                contested = slot.model_copy(
                    update={"successors": contenders, "status": "contested"}
                )
                obligations = tuple(
                    contested if item is slot else item for item in projection.current_obligations
                )
                next_projection = projection.model_copy(
                    update={
                        "current_obligations": obligations,
                        "historical_observation_refs": tuple(
                            _dedupe_refs((*projection.historical_observation_refs, successor_ref))
                        ),
                        "historical_refinement_refs": tuple(
                            _dedupe_refs((*projection.historical_refinement_refs, refinement_ref))
                        ),
                        "incomplete_obligation_ids": tuple(
                            sorted(
                                set(projection.incomplete_obligation_ids)
                                | {successor.obligation_id}
                            )
                        ),
                    }
                )
            else:
                if row.projection_revision != expected_projection_revision and _ref_key(
                    predecessor_ref
                ) not in {_ref_key(ref) for ref in projection.unassessed_observation_refs}:
                    raise StaleSearchTicketRevisionError(
                        "stale assessment predecessor is no longer a current admitted task state"
                    )
                if _ref_key(predecessor_ref) not in {
                    _ref_key(ref) for ref in projection.unassessed_observation_refs
                }:
                    raise ValueError(
                        "refinement predecessor is not the admitted unassessed task state"
                    )
                if any(
                    item.obligation_id == successor.obligation_id
                    for item in projection.current_obligations
                ):
                    raise ValueError(
                        "first-assessment relation cannot replace an assessed obligation"
                    )
                current = SearchUncertaintyCurrentObligation(
                    obligation_id=successor.obligation_id,
                    basis_ref=successor.basis_ref,
                    predecessor_ref=predecessor_ref,
                    successors=(
                        SearchUncertaintyCurrentSuccessor(
                            observation_ref=successor_ref,
                            refinement_ref=refinement_ref,
                            routing_score=successor.routing_score,
                        ),
                    ),
                    status="assessed",
                    expected_ticket_generation=expected_generation,
                )
                next_projection = projection.model_copy(
                    update={
                        "current_obligations": tuple(
                            sorted(
                                (*projection.current_obligations, current),
                                key=lambda item: item.obligation_id,
                            )
                        ),
                        "active_unknown_obligation_ids": tuple(
                            item
                            for item in projection.active_unknown_obligation_ids
                            if item != successor.obligation_id
                        ),
                        "historical_observation_refs": tuple(
                            _dedupe_refs((*projection.historical_observation_refs, successor_ref))
                        ),
                        "historical_refinement_refs": tuple(
                            _dedupe_refs((*projection.historical_refinement_refs, refinement_ref))
                        ),
                    }
                )
            return self._publish_locked(
                row,
                expected_generation=expected_generation,
                projection=next_projection,
            )

    def read_current_snapshot(self, ticket_id: str) -> SearchUncertaintyCurrentRead | None:
        """Resolve the current pointer, generation, and projection under one lock."""
        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            if row is None:
                return None
            if (
                row.current_projection_ref is None
                or row.projection_ticket_generation != row.ticket_generation
            ):
                return SearchUncertaintyCurrentRead(
                    ticket_id=ticket_id,
                    ticket_generation=row.ticket_generation,
                    projection_revision=row.projection_revision,
                    status="not_established",
                    reason_code="owner_projection_missing_or_stale",
                )
            try:
                projection = self._read_projection_for_row(row)
                if projection is None:
                    raise ValueError("current owner pointer resolved without a projection")
                resolved_projection = self._resolve_current_projection(
                    row.current_projection_ref,
                    projection,
                )
                admission_ref = row.task_admission_ref
                admission = None
                if admission_ref is not None:
                    admission = _load_typed_search_artifact(
                        self._store,
                        admission_ref,
                        SearchUncertaintyTaskAdmission,
                        kind="scientist.search.uncertainty_task_admission",
                    )
            except SearchUncertaintyAdmissionError as exc:
                reason_code: Literal[
                    "owner_projection_missing_or_stale",
                    "search_projection_mismatch",
                    "runtime_attempt_association_unavailable",
                    "runtime_attempt_association_mismatch",
                ] = "search_projection_mismatch"
                if exc.reason_code == "owner_projection_missing_or_stale":
                    reason_code = "owner_projection_missing_or_stale"
                elif exc.reason_code == "runtime_attempt_association_unavailable":
                    reason_code = "runtime_attempt_association_unavailable"
                elif exc.reason_code == "runtime_attempt_association_mismatch":
                    reason_code = "runtime_attempt_association_mismatch"
                return SearchUncertaintyCurrentRead(
                    ticket_id=ticket_id,
                    ticket_generation=row.ticket_generation,
                    projection_revision=row.projection_revision,
                    status="not_established",
                    reason_code=reason_code,
                )
            except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
                return SearchUncertaintyCurrentRead(
                    ticket_id=ticket_id,
                    ticket_generation=row.ticket_generation,
                    projection_revision=row.projection_revision,
                    status="not_established",
                    reason_code="search_projection_mismatch",
                )
            return SearchUncertaintyCurrentRead(
                ticket_id=ticket_id,
                ticket_generation=row.ticket_generation,
                projection_revision=row.projection_revision,
                projection_ref=row.current_projection_ref,
                projection=projection,
                resolved_projection=resolved_projection,
                task_admission_ref=admission_ref,
                task_binding_ref=row.current_binding_ref,
                task_admission=admission,
                admission_status="missing" if admission is None else admission.status,
                status="available_as_of_task_epoch",
            )

    def _resolve_current_projection(
        self,
        projection_ref: ArtifactRef,
        projection: SearchUncertaintyTicketProjection,
    ) -> SearchUncertaintyResolvedCurrentProjection:
        """Resolve every selected current observation and relation from the Search CAS."""
        unassessed: dict[
            tuple[str, str, str, str | None],
            SearchUncertaintyResolvedUnassessedObservation,
        ] = {}
        for observation_ref in projection.unassessed_observation_refs:
            observation = _load_typed_search_artifact(
                self._store,
                observation_ref,
                SearchUnassessedObservationV2,
                kind="scientist.search.uncertainty_observation",
            )
            basis = load_search_uncertainty_basis_v2(self._store, observation.basis_ref)
            if (
                observation.ticket_id != projection.ticket_id
                or observation.ticket_generation != projection.ticket_generation
                or observation.obligation_id != basis.obligation_id
            ):
                raise ValueError("resolved current observation differs from its ticket or basis")
            resolved = SearchUncertaintyResolvedUnassessedObservation(
                observation_ref=observation_ref,
                observation=observation,
                basis_ref=observation.basis_ref,
                basis=basis,
            )
            key = _ref_key(observation_ref)
            if key in unassessed:
                raise ValueError("resolved current projection repeats an observation")
            unassessed[key] = resolved

        current: list[SearchUncertaintyResolvedCurrentObligation] = []
        for selection in projection.current_obligations:
            basis = load_search_uncertainty_basis_v2(self._store, selection.basis_ref)
            predecessor = unassessed.get(_ref_key(selection.predecessor_ref))
            if predecessor is None:
                raise ValueError("resolved current obligation has no selected predecessor")
            if (
                basis.obligation_id != selection.obligation_id
                or predecessor.observation.obligation_id != selection.obligation_id
                or _ref_key(predecessor.basis_ref) != _ref_key(selection.basis_ref)
            ):
                raise ValueError("resolved current obligation differs from its selected basis")
            successors: list[SearchUncertaintyResolvedCurrentSuccessor] = []
            for selected in selection.successors:
                observation = _load_typed_search_artifact(
                    self._store,
                    selected.observation_ref,
                    SearchAssessedObservationV2,
                    kind="scientist.search.uncertainty_observation",
                )
                refinement = _load_typed_search_artifact(
                    self._store,
                    selected.refinement_ref,
                    SearchUncertaintyRefinement,
                    kind="scientist.search.uncertainty_refinement",
                )
                refinement_profile = _load_typed_search_artifact(
                    self._store,
                    refinement.profile_ref,
                    SearchUncertaintyRefinementProfile,
                    kind="scientist.search.uncertainty_refinement_profile",
                )
                routing_profile = _load_typed_search_artifact(
                    self._store,
                    selected.routing_score.profile_ref,
                    SearchUncertaintyRoutingProfile,
                    kind="scientist.search.uncertainty_routing_profile",
                )
                successors.append(
                    SearchUncertaintyResolvedCurrentSuccessor(
                        observation_ref=selected.observation_ref,
                        observation=observation,
                        refinement_ref=selected.refinement_ref,
                        refinement=refinement,
                        refinement_profile_ref=refinement.profile_ref,
                        refinement_profile=refinement_profile,
                        routing_profile_ref=selected.routing_score.profile_ref,
                        routing_profile=routing_profile,
                    )
                )
            current.append(
                SearchUncertaintyResolvedCurrentObligation(
                    selection=selection,
                    basis_ref=selection.basis_ref,
                    basis=basis,
                    predecessor=predecessor,
                    successors=tuple(successors),
                )
            )
        return SearchUncertaintyResolvedCurrentProjection(
            projection_ref=projection_ref,
            projection=projection,
            selected_unassessed_observations=tuple(
                unassessed[_ref_key(ref)] for ref in projection.unassessed_observation_refs
            ),
            current_obligations=tuple(current),
        )

    def read_current(self, ticket_id: str) -> SearchUncertaintyTicketProjection | None:
        """Fresh-read the current projection only when its generation still matches."""
        current = self.read_current_snapshot(ticket_id)
        return None if current is None else current.projection

    def read_as_of(self, ticket_id: str) -> SearchUncertaintyTicketProjection | None:
        """Fresh-read the latest pinned task-epoch projection as historical state."""
        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            if row is None or row.current_projection_ref is None:
                return None
            return self._read_projection_for_row(row)

    def read_generation(self, ticket_id: str) -> int | None:
        """Return the current owner generation without trusting cached ticket state."""
        with self._locked(ticket_id):
            row = self._read_row(ticket_id)
            return None if row is None else row.ticket_generation

    def _publish_locked(
        self,
        row: SearchUncertaintyTicketIndexRow,
        *,
        expected_generation: int,
        projection: SearchUncertaintyTicketProjection,
    ) -> SearchUncertaintyTicketIndexRow:
        if row.ticket_generation != expected_generation:
            raise StaleSearchTicketGenerationError(
                "ticket generation changed before projection commit"
            )
        if (
            projection.ticket_id != row.ticket_id
            or projection.ticket_generation != expected_generation
        ):
            raise ValueError("projection ticket identity/generation mismatch")
        projection_revision = row.projection_revision + 1
        historical_bindings = tuple(
            _dedupe_refs(
                (
                    *projection.historical_binding_refs,
                    *row.historical_binding_refs,
                    *(() if row.current_binding_ref is None else (row.current_binding_ref,)),
                )
            )
        )
        projection = projection.model_copy(
            update={
                "projection_revision": projection_revision,
                "previous_projection_ref": row.current_projection_ref,
                "historical_binding_refs": historical_bindings,
            }
        )
        projection_ref = persist_search_uncertainty_v2(self._store, projection)
        updated = row.model_copy(
            update={
                "owner_revision": row.owner_revision + 1,
                "projection_revision": projection_revision,
                "current_projection_ref": projection_ref,
                "projection_ticket_generation": expected_generation,
                "current_binding_ref": None,
                "historical_binding_refs": historical_bindings,
            }
        )
        self._write_row(updated)
        return updated

    def _read_projection_for_row(
        self, row: SearchUncertaintyTicketIndexRow
    ) -> SearchUncertaintyTicketProjection | None:
        if row.current_projection_ref is None:
            return None
        projection = self._load_projection(
            row.current_projection_ref, expected_revision=row.projection_revision
        )
        if (
            projection.ticket_id != row.ticket_id
            or projection.ticket_generation != row.ticket_generation
            or projection.projection_revision != row.projection_revision
        ):
            raise ValueError("current projection differs from its selected owner pointer")
        if (projection.task_admission_ref is None) != (row.task_admission_ref is None) or (
            projection.task_admission_ref is not None
            and row.task_admission_ref is not None
            and _ref_key(projection.task_admission_ref) != _ref_key(row.task_admission_ref)
        ):
            raise ValueError("current projection differs from its selected task admission")
        if row.task_admission_ref is not None:
            admission = _load_typed_search_artifact(
                self._store,
                row.task_admission_ref,
                SearchUncertaintyTaskAdmission,
                kind="scientist.search.uncertainty_task_admission",
            )
            if (
                row.owner_context_ref is None
                or _ref_key(row.owner_context_ref) != _ref_key(admission.owner_context_ref)
                or row.task_epoch_ref is None
                or _ref_key(row.task_epoch_ref) != _ref_key(admission.task_epoch_ref)
            ):
                raise ValueError("current task admission differs from its selected owner pointers")
        try:
            self._verify_projection_references(projection)
        except SearchUncertaintyAdmissionError:
            raise
        except StaleSearchTicketGenerationError as exc:
            raise SearchUncertaintyAdmissionError(
                "selected Search projection contains a stale ticket-generation relation",
                reason_code="owner_projection_missing_or_stale",
            ) from exc
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise SearchUncertaintyAdmissionError(
                "selected Search projection or one of its CAS relations is malformed",
                reason_code="search_projection_mismatch",
            ) from exc
        return projection

    def _verify_projection_references(self, projection: SearchUncertaintyTicketProjection) -> None:
        """Recompute the bounded current relation from fresh CAS reads.

        A valid pointer and intact bytes are insufficient: the current selection
        must still resolve to the exact admitted predecessor, same-basis successor,
        relation profile, and routing profile after a process restart.
        """
        refs = [
            *projection.unassessed_observation_refs,
            *projection.historical_observation_refs,
            *projection.historical_refinement_refs,
            *projection.historical_binding_refs,
        ]
        if projection.task_admission_ref is not None:
            refs.append(projection.task_admission_ref)
        if projection.previous_projection_ref is not None:
            refs.append(projection.previous_projection_ref)
        for obligation in projection.current_obligations:
            refs.extend((obligation.basis_ref, obligation.predecessor_ref))
            for successor in obligation.successors:
                refs.extend((successor.observation_ref, successor.refinement_ref))
                refs.append(successor.routing_score.profile_ref)
        for ref in refs:
            if ref.manifest_profile_sha256 is None or not self._store.verify(ref).ok:
                raise ValueError("fresh ticket projection contains an invalid artifact ref")

        task_admission: SearchUncertaintyTaskAdmission | None = None
        if projection.task_admission_ref is not None:
            task_admission = _load_typed_search_artifact(
                self._store,
                projection.task_admission_ref,
                SearchUncertaintyTaskAdmission,
                kind="scientist.search.uncertainty_task_admission",
            )
            owner_context = _load_typed_search_artifact(
                self._store,
                task_admission.owner_context_ref,
                SearchUncertaintyOwnerTaskContext,
                kind="scientist.search.uncertainty_owner_task_context",
            )
            task_epoch = _load_typed_search_artifact(
                self._store,
                task_admission.task_epoch_ref,
                SearchUncertaintyTaskEpoch,
                kind="scientist.search.uncertainty_task_epoch",
            )
            configuration_missing = _validate_search_owner_task_context(self._store, owner_context)
            if (
                task_admission.ticket_id != projection.ticket_id
                or task_admission.ticket_generation != projection.ticket_generation
                or owner_context.run_id != task_admission.run_id
                or task_epoch.run_id != task_admission.run_id
                or task_epoch.ticket_id != task_admission.ticket_id
                or task_epoch.ticket_generation != task_admission.ticket_generation
                or _ref_key(task_epoch.owner_context_ref)
                != _ref_key(task_admission.owner_context_ref)
            ):
                raise ValueError("selected task admission is outside the ticket generation")
            if task_admission.status == "unassessed":
                assert task_admission.basis_ref is not None
                if configuration_missing:
                    raise ValueError("unassessed task admission has unresolved stage bindings")
                basis = load_search_uncertainty_basis_v2(self._store, task_admission.basis_ref)
                _verify_search_basis_owner_binding(
                    basis,
                    owner_context,
                    ticket_id=projection.ticket_id,
                    task_epoch_ref=task_admission.task_epoch_ref,
                )
                if not any(
                    _ref_key(item.task_admission_ref) == _ref_key(projection.task_admission_ref)
                    and _ref_key(item.basis_ref) == _ref_key(task_admission.basis_ref)
                    for ref in projection.unassessed_observation_refs
                    for item in (
                        _load_typed_search_artifact(
                            self._store,
                            ref,
                            SearchUnassessedObservationV2,
                            kind="scientist.search.uncertainty_observation",
                        ),
                    )
                ):
                    raise ValueError(
                        "unassessed task admission has no matching current observation"
                    )
            elif projection.unassessed_observation_refs or projection.active_unknown_obligation_ids:
                raise ValueError(
                    "not-established task admission cannot claim an unassessed obligation"
                )

        unassessed: dict[tuple[str, str, str, str | None], SearchUnassessedObservationV2] = {}
        unassessed_obligations: set[str] = set()
        for observation_ref in projection.unassessed_observation_refs:
            observation = _load_typed_search_artifact(
                self._store,
                observation_ref,
                SearchUnassessedObservationV2,
                kind="scientist.search.uncertainty_observation",
            )
            if (
                observation.ticket_id != projection.ticket_id
                or observation.ticket_generation != projection.ticket_generation
            ):
                raise ValueError("current unassessed observation is outside the ticket generation")
            basis = load_search_uncertainty_basis_v2(self._store, observation.basis_ref)
            if basis.obligation_id != observation.obligation_id:
                raise ValueError("current unassessed observation has a mismatched basis")
            key = _ref_key(observation_ref)
            if key in unassessed:
                raise ValueError("current projection repeats an unassessed observation")
            unassessed[key] = observation
            unassessed_obligations.add(observation.obligation_id)

        current_ids: set[str] = set()
        contested_ids: set[str] = set()
        for obligation in projection.current_obligations:
            current_ids.add(obligation.obligation_id)
            if obligation.expected_ticket_generation != projection.ticket_generation:
                raise ValueError("current obligation is stale for the ticket generation")
            basis = load_search_uncertainty_basis_v2(self._store, obligation.basis_ref)
            if basis.obligation_id != obligation.obligation_id:
                raise ValueError("current obligation is not bound to its selected basis")
            predecessor = unassessed.get(_ref_key(obligation.predecessor_ref))
            if predecessor is None:
                raise ValueError(
                    "current obligation predecessor is not an admitted unassessed observation"
                )
            if predecessor.obligation_id != obligation.obligation_id or _ref_key(
                predecessor.basis_ref
            ) != _ref_key(obligation.basis_ref):
                raise ValueError("current obligation predecessor does not match its basis")
            for contender in obligation.successors:
                successor = _load_typed_search_artifact(
                    self._store,
                    contender.observation_ref,
                    SearchAssessedObservationV2,
                    kind="scientist.search.uncertainty_observation",
                )
                refinement = _load_typed_search_artifact(
                    self._store,
                    contender.refinement_ref,
                    SearchUncertaintyRefinement,
                    kind="scientist.search.uncertainty_refinement",
                )
                relation_profile = _load_typed_search_artifact(
                    self._store,
                    refinement.profile_ref,
                    SearchUncertaintyRefinementProfile,
                    kind="scientist.search.uncertainty_refinement_profile",
                )
                routing_profile = _load_typed_search_artifact(
                    self._store,
                    contender.routing_score.profile_ref,
                    SearchUncertaintyRoutingProfile,
                    kind="scientist.search.uncertainty_routing_profile",
                )
                if relation_profile.profile_id != refinement.relation:
                    raise ValueError("current refinement profile does not implement its relation")
                _verify_first_assessment_edge(
                    ticket_id=projection.ticket_id,
                    predecessor_ref=obligation.predecessor_ref,
                    predecessor=predecessor,
                    successor_ref=contender.observation_ref,
                    successor=successor,
                    refinement_ref=contender.refinement_ref,
                    refinement=refinement,
                    expected_generation=projection.ticket_generation,
                )
                if (
                    successor.obligation_id != obligation.obligation_id
                    or _ref_key(successor.basis_ref) != _ref_key(obligation.basis_ref)
                    or contender.routing_score != successor.routing_score
                    or routing_profile.profile_id != contender.routing_score.profile_id
                    or successor.producer_method_fqn != basis.selected_method_fqn
                    or successor.producer_method_abi_version != basis.selected_method_abi_version
                    or successor.producer_params_sha256 != basis.selected_method_params_sha256
                    or successor.inference_profile_id != basis.selected_inference_profile_id
                    or successor.unit_binding_status != basis.unit_binding_status
                    or (
                        None
                        if successor.unit_scope_ref is None
                        else _ref_key(successor.unit_scope_ref)
                    )
                    != (None if basis.unit_scope_ref is None else _ref_key(basis.unit_scope_ref))
                ):
                    raise ValueError(
                        "current successor projection differs from its CAS observation or basis"
                    )
                if self._completion_owner is not None:
                    self._verify_owned_attempt_association(
                        successor,
                        completion_owner=self._completion_owner,
                        tenant_id=basis.tenant_id,
                        cell_id=basis.cell_id,
                    )
                elif self._owned_historical_attempt_association_resolver is not None:
                    try:
                        association = self._owned_historical_attempt_association_resolver(
                            anchor_ref=successor.owned_attempt_anchor_ref,
                            expected_job_id=successor.job_id,
                            expected_completed_event_id=successor.completed_event_id,
                            expected_tenant_id=basis.tenant_id,
                            expected_cell_id=basis.cell_id,
                        )
                    except SearchUncertaintyAdmissionError:
                        raise
                    except (
                        AttributeError,
                        KeyError,
                        OSError,
                        RuntimeError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        raise SearchUncertaintyAdmissionError(
                            "exact historical Runtime completion could not be resolved",
                            reason_code="runtime_attempt_association_unavailable",
                        ) from exc
                    self._verify_owned_attempt_association(
                        successor,
                        owner_association=association,
                    )
                else:
                    self._verify_owned_attempt_association(successor)
                if successor.outcome_kind == "interval_estimate":
                    if (
                        successor.lower_bound is None
                        or successor.upper_bound is None
                        or successor.confidence_level is None
                        or contender.routing_score.comparison_key is None
                        or contender.routing_score.confidence_level is None
                        or contender.routing_score.interval_semantics is None
                    ):
                        raise ValueError(
                            "current interval assessment omitted its compared routing inputs"
                        )
                    expected_score = compute_relative_interval_halfwidth_routing(
                        profile_ref=contender.routing_score.profile_ref,
                        theta=successor.theta,
                        lower_bound=successor.lower_bound,
                        upper_bound=successor.upper_bound,
                        confidence_level=successor.confidence_level,
                        comparison_key=contender.routing_score.comparison_key,
                        unit_binding_status=successor.unit_binding_status,
                    )
                    if contender.routing_score != expected_score:
                        raise ValueError(
                            "current routing score is not recomputed from its native interval"
                        )
                    expected_key = make_comparison_key(
                        basis=basis,
                        confidence_level=contender.routing_score.confidence_level,
                        interval_semantics=contender.routing_score.interval_semantics,
                        sampling_profile_ref=basis.selected_profile_ref,
                    )
                    if contender.routing_score.comparison_key != expected_key:
                        raise ValueError("current routing score does not match its frozen basis")
                elif successor.outcome_kind == "point_estimate":
                    expected_score = _point_candidate_routing_score(
                        profile_ref=contender.routing_score.profile_ref,
                        theta=successor.theta,
                    )
                    if contender.routing_score != expected_score:
                        raise ValueError(
                            "current point assessment does not carry its canonical unavailable score"
                        )
                else:
                    raise ValueError("current assessment has an unsupported outcome kind")
            if obligation.status == "contested":
                contested_ids.add(obligation.obligation_id)

        if set(projection.active_unknown_obligation_ids) != unassessed_obligations - current_ids:
            raise ValueError("active unknown obligations differ from current admitted observations")
        if set(projection.incomplete_obligation_ids) != contested_ids:
            raise ValueError("incomplete obligations differ from contested current selections")

    def _verify_owned_attempt_association(
        self,
        successor: SearchAssessedObservationV2,
        *,
        owner_association: SearchOwnedAttemptAssociation | None = None,
        completion_owner: SearchHTECompletionOwner | None = None,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> SearchOwnedAttemptAssociation:
        """Reconcile copied HTE refs against the exact durable completion owner."""
        if owner_association is not None:
            association = owner_association
        elif completion_owner is not None:
            if tenant_id is None:
                raise SearchUncertaintyAdmissionError(
                    "historical Runtime lookup requires the Search tenant scope",
                    reason_code="runtime_attempt_association_mismatch",
                )
            try:
                association = completion_owner.resolve_historical_completed_method_execution(
                    job_id=successor.job_id,
                    completed_event_id=successor.completed_event_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                raise SearchUncertaintyAdmissionError(
                    "historical Runtime completion could not be resolved",
                    reason_code="runtime_attempt_association_unavailable",
                ) from exc
        else:
            resolver = self._owned_attempt_association_resolver
            if resolver is None:
                raise SearchUncertaintyAdmissionError(
                    "Runtime-owned attempt association reader is not installed",
                    reason_code="runtime_attempt_association_unavailable",
                )
            try:
                association = resolver(anchor_ref=successor.owned_attempt_anchor_ref)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                raise SearchUncertaintyAdmissionError(
                    "Runtime-owned attempt association could not be resolved: "
                    f"{type(exc).__name__}",
                    reason_code="runtime_attempt_association_unavailable",
                ) from exc
        if association is None:
            raise SearchUncertaintyAdmissionError(
                "Runtime-owned completion association is unavailable for this event",
                reason_code="runtime_attempt_association_unavailable",
            )
        required_fields = (
            "schema_version",
            "status",
            "anchor_ref",
            "outcome_ref",
            "outcome_kind",
            "invocation_basis_ref",
            "refusal_diagnostic_ref",
            "source_data_ref",
            "materialization_binding_ref",
            "search_uncertainty_task_binding_ref",
            "method_result_ref",
            "method_evidence_ref",
            "inference_basis_ref",
            "point_result_ref",
            "hte_result_ref",
            "job_id",
            "run_id",
            "attempt",
            "job_completed_event",
        )
        if any(not hasattr(association, name) for name in required_fields):
            raise SearchUncertaintyAdmissionError(
                "Runtime association reader did not return the typed resolved association",
                reason_code="runtime_attempt_association_mismatch",
            )
        if association.status != "owner_selection_reconciled":
            raise SearchUncertaintyAdmissionError(
                "Runtime-owned current selection is not reconciled for this anchor",
                reason_code="runtime_attempt_association_unavailable",
            )
        event = association.job_completed_event
        event_fields = (
            "event_id",
            "job_id",
            "event_type",
            "payload_sha256",
            "created_at",
        )
        if any(not hasattr(event, name) for name in event_fields):
            raise SearchUncertaintyAdmissionError(
                "Runtime association reader omitted its inline completion event",
                reason_code="runtime_attempt_association_mismatch",
            )
        event_payload_sha256 = _canonical_owned_lifecycle_event_digest_hex(event)
        if (
            type(association.attempt) is not int
            or association.attempt < 1
            or type(event.event_id) is not int
            or event.event_id < 1
            or event.event_type != "job_completed"
            or event.job_id != association.job_id
            or event_payload_sha256 is None
            or not isinstance(event.created_at, datetime)
            or event.created_at.tzinfo is None
            or event.created_at.utcoffset() is None
        ):
            raise SearchUncertaintyAdmissionError(
                "Runtime association completion event is malformed or mismatched",
                reason_code="runtime_attempt_association_mismatch",
            )
        expected_pairs = (
            (association.anchor_ref, successor.owned_attempt_anchor_ref),
            (association.outcome_ref, successor.hte_outcome_ref),
            (association.invocation_basis_ref, successor.invocation_basis_ref),
            (association.source_data_ref, successor.source_data_ref),
            (association.materialization_binding_ref, successor.materialization_binding_ref),
            (association.method_result_ref, successor.method_result_ref),
            (association.method_evidence_ref, successor.method_evidence_ref),
            (association.inference_basis_ref, successor.inference_basis_ref),
            (association.point_result_ref, successor.point_result_ref),
            (association.hte_result_ref, successor.hte_result_ref),
            (
                association.search_uncertainty_task_binding_ref,
                successor.search_uncertainty_task_binding_ref,
            ),
        )
        point_selection_shape = (
            association.outcome_kind == "point_estimate"
            and association.point_result_ref is not None
            and association.hte_result_ref is None
            and association.refusal_diagnostic_ref is None
        )
        interval_selection_shape = (
            association.outcome_kind == "interval_estimate"
            and association.point_result_ref is None
            and association.hte_result_ref is not None
            and association.inference_basis_ref is not None
            and association.refusal_diagnostic_ref is None
        )
        if (
            association.schema_version != "1.0"
            or association.status != "owner_selection_reconciled"
            or not (point_selection_shape or interval_selection_shape)
            or association.job_id != successor.job_id
            or association.run_id != successor.run_id
            or association.attempt != successor.attempt
            or event.event_id != successor.completed_event_id
            or event.job_id != successor.job_id
            or event_payload_sha256 != successor.completed_event_payload_sha256
            or event.created_at != successor.completed_at
            or any(
                (left is None) != (right is None)
                or (left is not None and right is not None and _ref_key(left) != _ref_key(right))
                for left, right in expected_pairs
            )
        ):
            raise SearchUncertaintyAdmissionError(
                "Search assessment refs differ from the Runtime-owned current attempt",
                reason_code="runtime_attempt_association_mismatch",
            )
        return association

    def _load_projection(
        self, ref: ArtifactRef, *, expected_revision: int
    ) -> SearchUncertaintyTicketProjection:
        from polisyos.core.artifacts import validate_core_model_json_artifact

        if ref.kind != "scientist.search.uncertainty_ticket_projection":
            raise ValueError("current pointer has wrong artifact kind")
        projection = validate_core_model_json_artifact(
            SearchUncertaintyTicketProjection, self._store, ref
        )
        if projection.projection_revision != expected_revision:
            raise ValueError("current projection revision differs from owned pointer")
        return projection

    def _path(self, ticket_id: str) -> Path:
        if not ticket_id or not ticket_id.strip():
            raise ValueError("ticket id is required")
        ticket_key = hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()
        return self._root / f"{ticket_key}.json"

    def _legacy_path(self, ticket_id: str) -> Path:
        ticket_key = hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()
        return self._legacy_root / f"{ticket_key}.json"

    def _read_row(self, ticket_id: str) -> SearchUncertaintyTicketIndexRow | None:
        path = self._path(ticket_id)
        if not path.exists():
            path = self._legacy_path(ticket_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        row = SearchUncertaintyTicketIndexRow.model_validate(payload)
        if row.ticket_id != ticket_id:
            raise ValueError("ticket index row is bound to a different ticket")
        return row

    def _write_row(self, row: SearchUncertaintyTicketIndexRow) -> None:
        ensure_directory_durable(self._root)
        path = self._path(row.ticket_id)
        payload = row.model_dump_json(by_alias=True, exclude_none=False).encode("utf-8")
        write_bytes_atomic(path, payload, durable_parent=True)

    def _locked(self, ticket_id: str) -> _TicketFileLock:
        return _TicketFileLock(self._path(ticket_id).with_suffix(".lock"))

    def _transact(
        self,
        ticket_id: str,
        update: Callable[[SearchUncertaintyTicketIndexRow | None], SearchUncertaintyTicketIndexRow],
    ) -> SearchUncertaintyTicketIndexRow:
        with self._locked(ticket_id):
            current = self._read_row(ticket_id)
            updated = update(current)
            if updated.ticket_id != ticket_id:
                raise ValueError("ticket index updater changed ticket identity")
            self._write_row(updated)
            return updated


@dataclass(slots=True)
class _TicketFileLockState:
    """Hold one OS ticket lock while same-thread owner callbacks re-enter it."""

    handle: BinaryIO
    owner_pid: int
    depth: int = 0


_TICKET_FILE_LOCK_LOCAL = local()
_TICKET_FILE_LOCK_REGISTRY: dict[int, _TicketFileLockState] = {}
_TICKET_FILE_LOCK_REGISTRY_GUARD = Lock()


def _before_ticket_file_lock_fork() -> None:
    """Freeze active descriptor registration while the process forks."""
    _TICKET_FILE_LOCK_REGISTRY_GUARD.acquire()


def _after_ticket_file_lock_fork_parent() -> None:
    """Resume parent-side descriptor registration after fork."""
    _TICKET_FILE_LOCK_REGISTRY_GUARD.release()


def _after_ticket_file_lock_fork_child() -> None:
    """Close inherited child descriptors without unlocking parent file locks."""
    global _TICKET_FILE_LOCK_REGISTRY, _TICKET_FILE_LOCK_REGISTRY_GUARD
    for state in _TICKET_FILE_LOCK_REGISTRY.values():
        try:
            state.handle.close()
        except OSError:
            pass
    _TICKET_FILE_LOCK_REGISTRY = {}
    _TICKET_FILE_LOCK_LOCAL.active = {}
    _TICKET_FILE_LOCK_REGISTRY_GUARD = Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_before_ticket_file_lock_fork,
        after_in_parent=_after_ticket_file_lock_fork_parent,
        after_in_child=_after_ticket_file_lock_fork_child,
    )


class _TicketFileLock:
    """Reentrant same-thread wrapper over the process-shared ticket file lock."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._state: _TicketFileLockState | None = None
        self._active: dict[str, _TicketFileLockState] | None = None
        self._key: str | None = None

    def __enter__(self) -> _TicketFileLock:
        active = getattr(_TICKET_FILE_LOCK_LOCAL, "active", None)
        if active is None:
            active = {}
            _TICKET_FILE_LOCK_LOCAL.active = active
        key = self._path.as_posix()
        state = active.get(key)
        if state is None:
            ensure_directory_durable(self._path.parent)
            with _TICKET_FILE_LOCK_REGISTRY_GUARD:
                handle = open(self._path, "a+b")
                state = _TicketFileLockState(handle=handle, owner_pid=os.getpid())
                _TICKET_FILE_LOCK_REGISTRY[id(state)] = state
            active[key] = state
            try:
                fcntl.flock(state.handle.fileno(), fcntl.LOCK_EX)
            except BaseException:
                try:
                    with _TICKET_FILE_LOCK_REGISTRY_GUARD:
                        state.handle.close()
                        _TICKET_FILE_LOCK_REGISTRY.pop(id(state), None)
                finally:
                    active.pop(key, None)
                raise
        state.depth += 1
        self._state = state
        self._active = active
        self._key = key
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        state = self._state
        if state is None:
            return
        if state.owner_pid != os.getpid():
            # The at-fork child hook closed this inherited descriptor without
            # unlocking the parent's open-file-description lock. Discard the
            # inherited context frame without issuing LOCK_UN on a closed fd.
            self._state = None
            self._active = None
            self._key = None
            return
        state.depth -= 1
        active = self._active
        key = self._key
        self._state = None
        self._active = None
        self._key = None
        if state.depth > 0:
            return
        if state.depth < 0:
            raise RuntimeError("ticket file lock nesting became negative")
        try:
            with _TICKET_FILE_LOCK_REGISTRY_GUARD:
                try:
                    fcntl.flock(state.handle.fileno(), fcntl.LOCK_UN)
                finally:
                    try:
                        state.handle.close()
                    finally:
                        _TICKET_FILE_LOCK_REGISTRY.pop(id(state), None)
        finally:
            if active is not None and key is not None and active.get(key) is state:
                del active[key]


def consume_owned_hte_completion(
    *,
    store: SearchUncertaintyStore,
    owner: SearchHTECompletionOwner,
    binding_ref: ArtifactRef,
    owner_association: SearchOwnedAttemptAssociation,
    source_projection_verifier: SearchHTESourceProjectionVerifier | None = None,
) -> SearchUncertaintyCompletionReceipt:
    """Consume an already-resolved Runtime completion into the Search owner CAS.

    Runtime supplies the association for its exact durable completion event, so
    this bounded receiver never re-resolves a latest/current attempt. It
    reloads the Search binding, HTE results, and owner ticket from the same CAS,
    then advances only the existing ticket pointer. It never fits a model or
    writes a parallel assessment ledger.
    """
    job_id = getattr(owner_association, "job_id", None)
    event = getattr(owner_association, "job_completed_event", None)
    completed_event_id = getattr(event, "event_id", None)
    event_payload_sha256 = _canonical_owned_lifecycle_event_digest_hex(event)
    if (
        not isinstance(job_id, str)
        or not job_id.strip()
        or type(completed_event_id) is not int
        or completed_event_id < 1
        or getattr(owner_association, "schema_version", None) != "1.0"
        or getattr(owner_association, "status", None) != "owner_selection_reconciled"
        or event is None
        or getattr(event, "event_id", None) != completed_event_id
        or getattr(event, "job_id", None) != job_id
        or getattr(event, "event_type", None) != "job_completed"
        or event_payload_sha256 is None
        or not isinstance(getattr(event, "created_at", None), datetime)
        or event.created_at.tzinfo is None
        or event.created_at.utcoffset() is None
    ):
        return _not_established_completion(
            job_id=job_id if isinstance(job_id, str) and job_id.strip() else "unknown",
            completed_event_id=completed_event_id if type(completed_event_id) is int else 1,
            reason_code="historical_completion_mismatch",
            next_check=(
                "Reconcile the supplied event identity against Runtime's durable owner history."
            ),
        )

    association_binding_ref = getattr(
        owner_association, "search_uncertainty_task_binding_ref", None
    )
    if association_binding_ref is None or _ref_key(binding_ref) != _ref_key(
        association_binding_ref
    ):
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            reason_code="search_binding_mismatch",
            next_check="Reconcile the supplied Search binding ref with the exact Runtime event.",
        )

    resolution: SearchUncertaintyTaskBindingResolution | None = None
    tenant_id: str | None = None
    cell_id: str | None = None
    try:
        resolution = owner.resolve_historical_search_uncertainty_task_binding(
            binding_ref=binding_ref,
            owner_association=owner_association,
        )
        if resolution is None:
            raise SearchUncertaintyAdmissionError(
                "Runtime did not return a historical Search binding resolution",
                reason_code="search_binding_resolution_unavailable",
            )
        if (
            resolution.closure_status != "recomputed"
            or _ref_key(resolution.binding_ref) != _ref_key(binding_ref)
            or resolution.ticket_id != resolution.binding.ticket_id
            or resolution.ticket_generation != resolution.binding.ticket_generation
        ):
            raise SearchUncertaintyAdmissionError(
                "historical Search binding resolution differs from the exact owner event",
                reason_code="search_binding_mismatch",
            )
        tenant_id = resolution.tenant_id
        cell_id = resolution.cell_id
        binding = load_search_uncertainty_task_binding(store, binding_ref)
        if binding != resolution.binding:
            raise SearchUncertaintyAdmissionError(
                "reloaded Search task binding differs from Runtime's recomputed resolution",
                reason_code="search_binding_mismatch",
            )
        if binding.tenant_id != tenant_id or binding.cell_id != cell_id:
            raise SearchUncertaintyAdmissionError(
                "Search task binding belongs to a different tenant or cell",
                reason_code="search_binding_mismatch",
            )
    except SearchUncertaintyAdmissionError as exc:
        reason_code = (
            "search_binding_resolution_unavailable"
            if exc.reason_code == "search_binding_resolution_unavailable"
            else "search_binding_mismatch"
        )
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            ticket_id=getattr(getattr(resolution, "binding", None), "ticket_id", None),
            ticket_generation=getattr(
                getattr(resolution, "binding", None), "ticket_generation", None
            ),
            reason_code=reason_code,
            next_check="Reconcile the exact owner-selected binding and its ticket generation.",
        )
    except AttributeError, OSError, RuntimeError, TypeError, ValueError, KeyError:
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            reason_code="search_binding_resolution_unavailable",
            next_check="Retry Search binding resolution from the durable Runtime completion.",
        )

    if tenant_id is None:
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            ticket_id=binding.ticket_id,
            ticket_generation=binding.ticket_generation,
            reason_code="search_binding_mismatch",
            next_check="Resolve the owner-bound Search tenant scope for this completion.",
        )

    state = SearchUncertaintyTicketState(store, completion_owner=owner)
    try:
        predecessor_ref, predecessor, basis = _find_completion_predecessor(state, binding)
        successor = _build_hte_assessment_candidate(
            store=store,
            association=owner_association,
            binding_ref=binding_ref,
            binding=binding,
            basis=basis,
            predecessor=predecessor,
            predecessor_ref=predecessor_ref,
            completed_at=event.created_at,
            source_projection_verifier=source_projection_verifier,
        )
        successor_ref = persist_search_uncertainty_v2(store, successor)
        refinement_profile_ref = persist_search_uncertainty_refinement_profile(store)
        refinement = SearchUncertaintyRefinement(
            predecessor_ref=predecessor_ref,
            successor_ref=successor_ref,
            basis_ref=binding.basis_ref,
            profile_ref=refinement_profile_ref,
            owned_attempt_anchor_ref=owner_association.anchor_ref,
            expected_ticket_generation=binding.ticket_generation,
            admitted_at=datetime.now(UTC),
        )
        refinement_ref = persist_search_uncertainty_v2(store, refinement)
        state.record_first_assessment(
            ticket_id=binding.ticket_id,
            expected_generation=binding.ticket_generation,
            expected_projection_revision=binding.projection_revision,
            predecessor_ref=predecessor_ref,
            successor_ref=successor_ref,
            refinement_ref=refinement_ref,
            completion_owner=owner,
            completion_association=owner_association,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except SearchUncertaintyAdmissionError as exc:
        mapped_reason: dict[
            str,
            Literal[
                "historical_completion_unavailable",
                "historical_completion_mismatch",
                "search_binding_missing",
                "search_binding_resolution_unavailable",
                "search_binding_mismatch",
                "unassessed_obligation_unavailable",
                "hte_content_unavailable",
                "hte_content_mismatch",
                "hte_method_refusal",
                "owner_state_unavailable",
            ],
        ] = {
            "runtime_attempt_association_unavailable": "historical_completion_unavailable",
            "runtime_attempt_association_mismatch": "historical_completion_mismatch",
            "search_binding_resolution_unavailable": "search_binding_resolution_unavailable",
            "search_binding_mismatch": "search_binding_mismatch",
            "unassessed_obligation_unavailable": "unassessed_obligation_unavailable",
            "hte_content_unavailable": "hte_content_unavailable",
            "hte_content_mismatch": "hte_content_mismatch",
            "hte_method_refusal": "hte_method_refusal",
            "native_hte_outcome_content_unavailable": "hte_content_unavailable",
            "search_projection_mismatch": "owner_state_unavailable",
        }
        reason: Literal[
            "historical_completion_unavailable",
            "historical_completion_mismatch",
            "search_binding_missing",
            "search_binding_resolution_unavailable",
            "search_binding_mismatch",
            "unassessed_obligation_unavailable",
            "hte_content_unavailable",
            "hte_content_mismatch",
            "hte_method_refusal",
            "owner_state_unavailable",
        ] = mapped_reason.get(exc.reason_code, "hte_content_unavailable")
        next_check = (
            "Preserve the Search unknown state; resolve the typed HTE refusal before retry."
            if reason == "hte_method_refusal"
            else "Preserve the Search unknown state and repair the named owner/content "
            "join before retry."
        )
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            ticket_id=binding.ticket_id,
            ticket_generation=binding.ticket_generation,
            reason_code=reason,
            next_check=next_check,
        )
    except AttributeError, OSError, RuntimeError, TypeError, ValueError, KeyError, ImportError:
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            ticket_id=binding.ticket_id,
            ticket_generation=binding.ticket_generation,
            reason_code="hte_content_mismatch",
            next_check=(
                "Preserve the Search unknown state and reconcile the selected HTE CAS content."
            ),
        )

    accepted_ref, already_admitted = _read_admitted_completion_result(
        state,
        ticket_id=binding.ticket_id,
        job_id=job_id,
        completed_event_id=completed_event_id,
        candidate_ref=successor_ref,
    )
    if accepted_ref is None:
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            ticket_id=binding.ticket_id,
            ticket_generation=binding.ticket_generation,
            reason_code="owner_state_unavailable",
            next_check=(
                "Retry Search owner projection reconciliation; no assessment pointer was confirmed."
            ),
        )
    return SearchUncertaintyCompletionReceipt(
        status="already_admitted" if already_admitted else "admitted",
        job_id=job_id,
        completed_event_id=completed_event_id,
        ticket_id=binding.ticket_id,
        ticket_generation=binding.ticket_generation,
        observation_ref=accepted_ref,
    )


def consume_completed_search_hte_attempt(
    *,
    store: SearchUncertaintyStore,
    owner: SearchHTECompletionOwner,
    job_id: str,
    completed_event_id: int,
    tenant_id: str,
    cell_id: str | None,
    source_projection_verifier: SearchHTESourceProjectionVerifier | None = None,
) -> SearchUncertaintyCompletionReceipt:
    """Resolve one exact Runtime completion and route it to the Search receiver."""
    if type(completed_event_id) is not int or completed_event_id < 1:
        raise ValueError("a positive Runtime event ID is required")
    if not isinstance(job_id, str) or not job_id.strip() or not tenant_id.strip():
        return _not_established_completion(
            job_id=job_id if isinstance(job_id, str) and job_id.strip() else "unknown",
            completed_event_id=completed_event_id,
            reason_code="historical_completion_mismatch",
            next_check="Call the consumer with the exact owner job, event ID, tenant, and cell.",
        )
    try:
        association = owner.resolve_historical_completed_method_execution(
            job_id=job_id,
            completed_event_id=completed_event_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except AttributeError, OSError, RuntimeError, TypeError, ValueError:
        association = None
    if association is None:
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            reason_code="historical_completion_unavailable",
            next_check="Retry Runtime reconciliation for this durable completed event.",
        )
    binding_ref = getattr(association, "search_uncertainty_task_binding_ref", None)
    if binding_ref is None:
        return _not_established_completion(
            job_id=job_id,
            completed_event_id=completed_event_id,
            reason_code="search_binding_missing",
            next_check="Recover the Search binding from this exact durable completion.",
        )
    return consume_owned_hte_completion(
        store=store,
        owner=owner,
        binding_ref=binding_ref,
        owner_association=association,
        source_projection_verifier=source_projection_verifier,
    )


def _not_established_completion(
    *,
    job_id: str,
    completed_event_id: int,
    reason_code: Literal[
        "historical_completion_unavailable",
        "historical_completion_mismatch",
        "search_binding_missing",
        "search_binding_resolution_unavailable",
        "search_binding_mismatch",
        "unassessed_obligation_unavailable",
        "hte_content_unavailable",
        "hte_content_mismatch",
        "hte_method_refusal",
        "owner_state_unavailable",
    ],
    next_check: str,
    ticket_id: str | None = None,
    ticket_generation: int | None = None,
) -> SearchUncertaintyCompletionReceipt:
    return SearchUncertaintyCompletionReceipt(
        status="not_established",
        job_id=job_id,
        completed_event_id=completed_event_id,
        ticket_id=ticket_id,
        ticket_generation=ticket_generation,
        reason_code=reason_code,
        next_check=next_check,
    )


def _find_completion_predecessor(
    state: SearchUncertaintyTicketState,
    binding: SearchUncertaintyTaskBinding,
) -> tuple[ArtifactRef, SearchUnassessedObservationV2, SearchUncertaintyBasisV2]:
    """Find the exact admitted numeric-free predecessor for one ticket epoch."""
    with state._locked(binding.ticket_id):
        row = state._read_row(binding.ticket_id)
        if row is None or row.ticket_generation < binding.ticket_generation:
            raise SearchUncertaintyAdmissionError(
                "Search ticket owner does not contain the selected task generation",
                reason_code="unassessed_obligation_unavailable",
            )
        projection = state._read_projection_for_row(row)
        if projection is None:
            raise SearchUncertaintyAdmissionError(
                "Search ticket owner has no admitted uncertainty projection",
                reason_code="unassessed_obligation_unavailable",
            )
        refs = tuple(
            _dedupe_refs(
                (*projection.unassessed_observation_refs, *projection.historical_observation_refs)
            )
        )
        matches: list[tuple[ArtifactRef, SearchUnassessedObservationV2]] = []
        for ref in refs:
            if ref.kind != "scientist.search.uncertainty_observation":
                continue
            payload = get_json_artifact(state._store, ref)
            if not isinstance(payload, Mapping) or payload.get("state") != "unassessed":
                continue
            observation = SearchUnassessedObservationV2.model_validate(payload)
            if (
                observation.ticket_id == binding.ticket_id
                and observation.ticket_generation == binding.ticket_generation
                and _ref_key(observation.basis_ref) == _ref_key(binding.basis_ref)
                and _ref_key(observation.task_admission_ref) == _ref_key(binding.task_admission_ref)
            ):
                matches.append((ref, observation))
        if len(matches) != 1:
            raise SearchUncertaintyAdmissionError(
                "exact owner-derived unassessed task obligation is missing or ambiguous",
                reason_code="unassessed_obligation_unavailable",
            )
        predecessor_ref, predecessor = matches[0]
        basis = load_search_uncertainty_basis_v2(state._store, binding.basis_ref)
        if (
            predecessor.obligation_id != basis.obligation_id
            or predecessor.ticket_id != binding.ticket_id
            or _ref_key(predecessor.basis_ref) != _ref_key(binding.basis_ref)
            or basis.tenant_id != binding.tenant_id
            or basis.cell_id != binding.cell_id
            or basis.request_projection != binding.request_projection
            or basis.selected_method_fqn != binding.selected_method_fqn
            or basis.selected_method_abi_version != binding.selected_method_abi_version
            or basis.selected_method_abi_digest != binding.selected_method_abi_digest
            or basis.selected_method_params_sha256 != binding.selected_method_params_sha256
            or basis.selected_method_params != binding.selected_method_params
            or basis.selected_method_seed != binding.selected_method_seed
            or basis.selected_inference_profile_id != binding.selected_inference_profile_id
            or _ref_key(basis.selected_method_input_ref)
            != _ref_key(binding.selected_method_input_ref)
        ):
            raise SearchUncertaintyAdmissionError(
                "Search binding no longer matches its admitted task basis",
                reason_code="search_binding_mismatch",
            )
        return predecessor_ref, predecessor, basis


def _core_artifact_ref_from_owner_ref(
    ref: ArtifactRef | ArtifactRefModel,
) -> ArtifactRef:
    """Project a typed owner ref into Core's exact selected-reader selector."""
    return ArtifactRef.model_validate(ref.model_dump(mode="python"), strict=True)


def _load_hte_outcome_from_owner_ref(
    store: SearchUncertaintyStore,
    owner_ref: ArtifactRef | ArtifactRefModel,
) -> HTEOutcome:
    """Normalize the Core owner selection into IR's exact HTE outcome ref."""
    from polisyos.ir.analytics import HTEOutcomeRef, load_hte_outcome

    selected_ref = HTEOutcomeRef.model_validate(
        _core_artifact_ref_from_owner_ref(owner_ref).model_dump(mode="python"),
        strict=True,
    )
    ir_store = ensure_ir_artifact_store(store)
    return load_hte_outcome(ir_store, selected_ref)


def _build_hte_assessment_candidate(
    *,
    store: SearchUncertaintyStore,
    association: SearchOwnedAttemptAssociation,
    binding_ref: ArtifactRef,
    binding: SearchUncertaintyTaskBinding,
    basis: SearchUncertaintyBasisV2,
    predecessor: SearchUnassessedObservationV2,
    predecessor_ref: ArtifactRef,
    completed_at: datetime,
    source_projection_verifier: SearchHTESourceProjectionVerifier | None = None,
) -> SearchAssessedObservationV2:
    """Load and content-join the selected HTE output without promoting its status."""
    from polisyos.ir.analytics import (
        HTEIntervalOutcome,
        HTEPointOutcome,
        HTERefusalOutcome,
        load_ate_inference_basis,
        load_hte_point_result,
        load_hte_result_v2,
    )

    ir_store = ensure_ir_artifact_store(store)

    def require_ref(
        left: ArtifactRef | ArtifactRefModel | None,
        right: ArtifactRef | ArtifactRefModel | None,
        label: str,
    ) -> None:
        if left is None or right is None or _ref_key(left) != _ref_key(right):
            raise SearchUncertaintyAdmissionError(
                f"selected HTE {label} ref differs from the exact owner-bound result",
                reason_code="hte_content_mismatch",
            )

    # Search stores a params-only digest. HTE's selected execution digest binds
    # both the params and the owner-selected seed, so recompute that exact
    # producer quantity instead of conflating the two hashes.
    expected_resolved_params_sha256 = _resolved_hte_params_sha256(
        binding.selected_method_params,
        binding.selected_method_seed,
    )

    def verify_physical_materialization(
        physical_ref: ArtifactRef,
        *,
        outcome: HTEPointOutcome | HTEIntervalOutcome,
        selected_rows: int,
        selected_row_order_sha256: str,
    ) -> CoreJsonReadLimits:
        """Recompute the selected physical HTE input binding from this CAS."""
        from polisyos.foundry.data_plane import (
            load_hte_physical_source_materialization_binding,
        )

        owned_materialization_ref = association.materialization_binding_ref
        if owned_materialization_ref is None:
            raise SearchUncertaintyAdmissionError(
                "selected @2 HTE completion omitted its owner-selected physical source binding",
                reason_code="hte_content_mismatch",
            )
        if not matches_runtime_protocol(store, _SearchUncertaintyPhysicalInputStore):
            raise SearchUncertaintyAdmissionError(
                "selected HTE source store lacks the bounded member reader",
                reason_code="hte_content_unavailable",
            )
        require_ref(
            physical_ref,
            owned_materialization_ref,
            "physical materialization",
        )
        from polisyos.core.artifacts import (
            read_core_json_artifact_bounded,
            validate_core_model_bounded_read,
        )
        from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
        from polisyos.core.contracts.owned_attempt_anchor import (
            OwnedAttemptAnchor,
            OwnedAttemptHTEInputAdmitted,
        )
        from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy

        # The anchor and policy precede the estimator read. Keep this bootstrap
        # read strictly bounded, then apply the exact persisted policy limits
        # when Foundry recomputes both selected source views.
        bootstrap_limits = CoreJsonReadLimits(
            max_bytes=8_388_608,
            max_depth=64,
            max_elements=200_000,
            max_manifest_bytes=65_536,
        )
        anchor_ref = _core_artifact_ref_from_owner_ref(association.anchor_ref)
        anchor_read = read_core_json_artifact_bounded(
            store,
            anchor_ref,
            limits=bootstrap_limits,
        )
        require_ref(anchor_read.effective_ref, anchor_ref, "owner anchor")
        if (
            anchor_read.manifest.kind != "runtime.owned_attempt_anchor"
            or anchor_read.manifest.media_type != "application/json"
            or anchor_read.manifest.artifact_schema
            != SchemaInfo(name="polisyos.runtime.OwnedAttemptAnchor", version="1.0")
        ):
            raise SearchUncertaintyAdmissionError(
                "selected physical binding owner anchor does not resolve to its declared schema",
                reason_code="hte_content_mismatch",
            )
        anchor = validate_core_model_bounded_read(OwnedAttemptAnchor, anchor_read)
        admitted = anchor.input_admission
        if (
            anchor.job_id != association.job_id
            or anchor.run_id != association.run_id
            or anchor.attempt != association.attempt
            or not isinstance(admitted, OwnedAttemptHTEInputAdmitted)
        ):
            raise SearchUncertaintyAdmissionError(
                "selected HTE input differs from the historical admitted Runtime anchor",
                reason_code="hte_content_mismatch",
            )
        require_ref(admitted.effective_input_ref, association.source_data_ref, "admitted source")
        require_ref(
            admitted.effective_input_ref, binding.selected_method_input_ref, "selected input"
        )
        capture = admitted.input_capture
        anchor_physical_ref = capture.materialization_binding_ref
        request_context = capture.request_context
        if (
            anchor_physical_ref is None
            or request_context.search_uncertainty_task_binding_ref is None
        ):
            raise SearchUncertaintyAdmissionError(
                "selected HTE result differs from its historical owner input capture",
                reason_code="hte_content_mismatch",
            )
        require_ref(anchor_physical_ref, physical_ref, "owner materialization")
        require_ref(
            anchor.request_context.materialization_binding_ref,
            anchor_physical_ref,
            "anchor materialization",
        )
        require_ref(
            request_context.search_uncertainty_task_binding_ref,
            binding_ref,
            "anchor Search binding",
        )
        require_ref(capture.source_data_ref, binding.selected_method_input_ref, "captured source")
        if (
            capture.method_fqn != outcome.method_fqn
            or capture.method_abi != outcome.method_abi
            or capture.method_abi_digest != outcome.method_abi_digest
            or capture.method_profile_id != outcome.method_profile_id
            or capture.resolved_params_sha256 != expected_resolved_params_sha256
            or capture.seed != binding.selected_method_seed
            or capture.input_profile_id != outcome.input_profile_id
            or capture.selected_input_sha256 != outcome.selected_input_sha256
            or capture.selected_rows_sha256 != outcome.selected_rows_sha256
            or capture.selected_x_sha256 != outcome.selected_x_sha256
            or capture.selected_row_order_sha256 != outcome.selected_row_order_sha256
            or capture.n_selected_rows != outcome.n_selected_rows
            or request_context.request_estimand_status != outcome.request_estimand_status
            or request_context.request_estimand != outcome.request_estimand
            or request_context.request_target_scope_status != outcome.request_target_scope_status
            or request_context.request_target_scope != outcome.request_target_scope
            or request_context.outcome_variable_status != outcome.outcome_variable_status
            or request_context.outcome_variable_id != outcome.outcome_variable_id
            or request_context.treatment_variable_status != outcome.treatment_variable_status
            or request_context.treatment_variable_id != outcome.treatment_variable_id
            or (request_context.contrast_status == "declared")
            != (outcome.contrast_status == "established")
            or request_context.control_value != outcome.control_value
            or request_context.treated_value != outcome.treated_value
            or request_context.request_alpha_status != outcome.request_alpha_status
            or request_context.requested_alpha != outcome.requested_alpha
            or request_context.requested_guarantee_status != outcome.requested_guarantee_status
            or request_context.requested_guarantee != outcome.requested_guarantee
        ):
            raise SearchUncertaintyAdmissionError(
                "selected HTE result differs from its historical owner input capture",
                reason_code="hte_content_mismatch",
            )

        policy_ref = _core_artifact_ref_from_owner_ref(anchor.resource_policy_ref)
        policy_read = read_core_json_artifact_bounded(
            store,
            policy_ref,
            limits=bootstrap_limits,
        )
        require_ref(policy_read.effective_ref, policy_ref, "resource policy")
        if (
            policy_read.manifest.kind != "runtime.observational_input_resource_policy"
            or policy_read.manifest.media_type != "application/json"
            or policy_read.manifest.artifact_schema
            != SchemaInfo(name="polisyos.runtime.ObservationalInputResourcePolicy", version="1.0")
        ):
            raise SearchUncertaintyAdmissionError(
                "selected input resource policy does not resolve to its declared schema",
                reason_code="hte_content_mismatch",
            )
        resource_policy = validate_core_model_bounded_read(
            ObservationalInputResourcePolicy,
            policy_read,
        )
        if (
            resource_policy.schema_version != anchor.resource_policy_schema_version
            or resource_policy.revision != anchor.resource_policy_revision
        ):
            raise SearchUncertaintyAdmissionError(
                "selected input resource policy differs from its owner anchor revision",
                reason_code="hte_content_mismatch",
            )
        selected_limits = CoreJsonReadLimits(
            max_bytes=resource_policy.max_bytes,
            max_depth=resource_policy.max_depth,
            max_elements=resource_policy.max_elements,
            max_manifest_bytes=resource_policy.max_manifest_bytes,
        )
        physical_binding = load_hte_physical_source_materialization_binding(
            store=store,
            binding_ref=_core_artifact_ref_from_owner_ref(physical_ref),
            expected_submitted_ref=_core_artifact_ref_from_owner_ref(anchor.submitted_input_ref),
            expected_effective_ref=_core_artifact_ref_from_owner_ref(anchor.effective_input_ref),
            limits=selected_limits,
        )
        if (
            physical_binding.binding_scope != "physical_materialization_only"
            or physical_binding.semantic_alignment_status != "not_established"
            or physical_binding.observation_count != selected_rows
            or physical_binding.row_order_sha256 != f"sha256:{selected_row_order_sha256}"
            or physical_binding.effective_payload_sha256
            != f"sha256:{binding.selected_method_input_content_sha256}"
        ):
            raise SearchUncertaintyAdmissionError(
                "physical HTE materialization differs from the selected result row basis",
                reason_code="hte_content_mismatch",
            )
        return selected_limits

    outcome_artifact = _load_hte_outcome_from_owner_ref(store, association.outcome_ref)
    outcome = outcome_artifact.root
    if isinstance(outcome, HTERefusalOutcome):
        raise SearchUncertaintyAdmissionError(
            f"selected HTE attempt ended in typed refusal: {outcome.diagnostic_code}",
            reason_code="hte_method_refusal",
        )
    if not isinstance(outcome, (HTEPointOutcome, HTEIntervalOutcome)):
        raise SearchUncertaintyAdmissionError(
            "selected HTE outcome is not a point-bearing candidate",
            reason_code="hte_content_unavailable",
        )

    require_ref(association.search_uncertainty_task_binding_ref, binding_ref, "Search binding")
    require_ref(outcome.search_uncertainty_task_binding_ref, binding_ref, "outcome Search binding")
    require_ref(outcome.owned_attempt_anchor_ref, association.anchor_ref, "owner anchor")
    require_ref(
        outcome.materialization_binding_ref,
        association.materialization_binding_ref,
        "outcome physical materialization",
    )
    require_ref(outcome.source_data_ref, binding.selected_method_input_ref, "source input")
    require_ref(outcome.method_result_ref, association.method_result_ref, "method result")
    require_ref(outcome.method_evidence_ref, association.method_evidence_ref, "method evidence")
    _require_optional_artifact_ref_match(
        outcome.invocation_basis_ref, association.invocation_basis_ref, "invocation basis"
    )
    if (
        outcome.kind != association.outcome_kind
        or outcome.method_fqn != binding.selected_method_fqn
        or outcome.method_abi != binding.selected_method_abi_version
        or outcome.method_abi_digest != binding.selected_method_abi_digest
        or outcome.resolved_params_sha256 != expected_resolved_params_sha256
        or outcome.method_profile_id != binding.selected_inference_profile_id
        or outcome.input_profile_id != "all_source_rows_in_input_order@1.0"
        or outcome.request_estimand != binding.request_projection.estimand
        or outcome.request_target_scope != binding.request_projection.target_scope
        or outcome.outcome_variable_id != binding.request_projection.outcome_variable_id
        or outcome.treatment_variable_id != binding.request_projection.treatment_variable_id
        or outcome.control_value != binding.request_projection.control_value
        or outcome.treated_value != binding.request_projection.treated_value
        or outcome.requested_alpha != binding.request_projection.alpha
        or outcome.requested_guarantee != binding.request_projection.requested_guarantee
    ):
        raise SearchUncertaintyAdmissionError(
            "selected HTE output differs from the frozen Search task request or method profile",
            reason_code="hte_content_mismatch",
        )
    if not store.verify(binding.selected_method_input_ref).ok:
        raise SearchUncertaintyAdmissionError(
            "selected HTE source input failed CAS integrity verification",
            reason_code="hte_content_unavailable",
        )

    if (
        binding.selected_method_input_ref.artifact_id.hex
        != binding.selected_method_input_content_sha256
    ):
        raise SearchUncertaintyAdmissionError(
            "selected Search input content identity differs from its owner binding",
            reason_code="search_binding_mismatch",
        )
    point_ref = getattr(outcome, "point_result_ref", None)
    hte_result_ref = getattr(outcome, "hte_result_ref", None)
    inference_basis_ref = outcome.inference_basis_ref
    if (inference_basis_ref is None) != (association.inference_basis_ref is None):
        raise SearchUncertaintyAdmissionError(
            "selected HTE inference basis ref differs from the exact owner-bound result",
            reason_code="hte_content_mismatch",
        )
    if inference_basis_ref is not None:
        require_ref(inference_basis_ref, association.inference_basis_ref, "inference basis")
    point_result = None
    hte_result = None
    inference_basis = None
    if isinstance(outcome, HTEPointOutcome):
        if point_ref is None:
            raise SearchUncertaintyAdmissionError(
                "point-only HTE outcome omitted its selected point result",
                reason_code="hte_content_mismatch",
            )
        require_ref(point_ref, association.point_result_ref, "point result")
        if hte_result_ref is not None or association.hte_result_ref is not None:
            raise SearchUncertaintyAdmissionError(
                "point-only HTE outcome carries an interval HTEResult ref",
                reason_code="hte_content_mismatch",
            )
        point_result = load_hte_point_result(ir_store, point_ref)
        require_ref(
            point_result.owned_attempt_anchor_ref,
            association.anchor_ref,
            "point owner anchor",
        )
        require_ref(
            point_result.source_data_ref,
            binding.selected_method_input_ref,
            "point source input",
        )
        require_ref(
            point_result.method_result_ref,
            association.method_result_ref,
            "point method result",
        )
        require_ref(
            point_result.method_evidence_ref,
            association.method_evidence_ref,
            "point method evidence",
        )
        require_ref(
            point_result.search_uncertainty_task_binding_ref,
            binding_ref,
            "point Search binding",
        )
        require_ref(
            point_result.materialization_binding_ref,
            association.materialization_binding_ref,
            "point physical materialization",
        )
        if (
            point_result.method_fqn != binding.selected_method_fqn
            or point_result.method_abi != binding.selected_method_abi_version
            or point_result.method_abi_digest != binding.selected_method_abi_digest
            or point_result.resolved_params_sha256 != expected_resolved_params_sha256
            or point_result.method_profile_id != binding.selected_inference_profile_id
            or point_result.source_data_sha256 != outcome.selected_input_sha256
            or point_result.selected_input_sha256 != outcome.selected_input_sha256
            or point_result.selected_rows_sha256 != outcome.selected_rows_sha256
            or point_result.selected_x_sha256 != outcome.selected_x_sha256
            or point_result.selected_row_order_sha256 != outcome.selected_row_order_sha256
            or point_result.n_selected_rows != outcome.n_selected_rows
            or point_result.input_profile_id != outcome.input_profile_id
            or not math.isclose(
                point_result.point_estimate,
                outcome.point_estimate.value,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
        ):
            raise SearchUncertaintyAdmissionError(
                "HTE point outcome and selected point artifact do not content-join",
                reason_code="hte_content_mismatch",
            )
        if inference_basis_ref is not None:
            inference_basis = load_ate_inference_basis(ir_store, inference_basis_ref)
            require_ref(
                getattr(inference_basis, "point_result_ref", None),
                point_ref,
                "diagnostic basis point result",
            )
            if (
                getattr(inference_basis, "hte_result_ref", None) is not None
                or getattr(inference_basis, "native_result_disposition", None)
                != "legacy_hte_result_unrepresentable"
            ):
                raise SearchUncertaintyAdmissionError(
                    "point-only HTE basis is not a typed unrepresentable-interval diagnostic",
                    reason_code="hte_content_mismatch",
                )
    elif isinstance(outcome, HTEIntervalOutcome):
        if point_ref is not None or association.point_result_ref is not None:
            raise SearchUncertaintyAdmissionError(
                "HTEResult-backed interval duplicates the point vector artifact",
                reason_code="hte_content_mismatch",
            )
        require_ref(hte_result_ref, association.hte_result_ref, "HTEResult v1")
        if inference_basis_ref is None:
            raise SearchUncertaintyAdmissionError(
                "HTEResult-backed interval omitted its inference basis",
                reason_code="hte_content_mismatch",
            )
        if hte_result_ref is None:
            raise SearchUncertaintyAdmissionError(
                "HTEResult-backed interval omitted its selected value carrier",
                reason_code="hte_content_mismatch",
            )
        hte_result = load_hte_result_v2(ir_store, hte_result_ref)
        inference_basis = load_ate_inference_basis(ir_store, inference_basis_ref)
        expected_ir_method = {
            "causal.hte.causal_forest@2.0.0": "causal_forest",
            "causal.hte.forest_dr@2.0.0": "forest_dr",
        }.get(outcome.method_fqn)
        require_ref(
            getattr(inference_basis, "hte_result_ref", None),
            hte_result_ref,
            "inference basis HTEResult v1",
        )
        if (
            inference_basis.native_result_disposition != "legacy_hte_result_admitted"
            or getattr(inference_basis, "point_result_ref", None) is not None
        ):
            raise SearchUncertaintyAdmissionError(
                "admitted interval basis does not select the HTEResult carrier exclusively",
                reason_code="hte_content_mismatch",
            )
        if (
            expected_ir_method is None
            or getattr(hte_result.method, "value", hte_result.method) != expected_ir_method
            or inference_basis.native_result_disposition != "legacy_hte_result_admitted"
            or getattr(inference_basis, "point_result_ref", None) is not None
            or hte_result.schema_version != "1.0"
            or inference_basis.inference_profile_id != "econml_native_mean_over_selected_x@1.0"
            or inference_basis.inference_route != "ate_inference.conf_int_mean"
            or hte_result.n_samples != outcome.n_selected_rows
            or len(hte_result.cate_values) != outcome.n_selected_rows
            or hte_result.confidence_level != outcome.confidence_level
            or hte_result.ate_ci_lower != outcome.lower_bound
            or hte_result.ate_ci_upper != outcome.upper_bound
            or not math.isclose(
                hte_result.ate,
                outcome.point_estimate.value,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
            or not math.isclose(
                inference_basis.native_point,
                hte_result.ate,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
            or not math.isclose(
                inference_basis.native_lower_bound,
                hte_result.ate_ci_lower,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
            or not math.isclose(
                inference_basis.native_upper_bound,
                hte_result.ate_ci_upper,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            )
            or inference_basis.method_fqn != binding.selected_method_fqn
            or inference_basis.method_abi != binding.selected_method_abi_version
            or inference_basis.method_abi_digest != binding.selected_method_abi_digest
            or inference_basis.resolved_params_sha256 != expected_resolved_params_sha256
            or inference_basis.method_profile_id != binding.selected_inference_profile_id
            or inference_basis.seed != binding.selected_method_seed
            or inference_basis.alpha != binding.request_projection.alpha
            or inference_basis.confidence_level != outcome.confidence_level
            or inference_basis.selected_input_sha256 != outcome.selected_input_sha256
            or inference_basis.selected_rows_sha256 != outcome.selected_rows_sha256
            or inference_basis.selected_x_sha256 != outcome.selected_x_sha256
            or inference_basis.selected_row_order_sha256 != outcome.selected_row_order_sha256
            or inference_basis.input_profile_id != outcome.input_profile_id
            or inference_basis.fit_rows_sha256 != outcome.selected_row_order_sha256
            or inference_basis.eval_rows_sha256 != outcome.selected_row_order_sha256
            or inference_basis.n_selected_rows != outcome.n_selected_rows
            or inference_basis.source_data_sha256 != outcome.selected_input_sha256
            or inference_basis.contrast_status != outcome.contrast_status
            or inference_basis.control_value != outcome.control_value
            or inference_basis.treated_value != outcome.treated_value
            or inference_basis.request_estimand_status != outcome.request_estimand_status
            or inference_basis.request_estimand != outcome.request_estimand
            or inference_basis.request_target_scope_status != outcome.request_target_scope_status
            or inference_basis.request_target_scope != outcome.request_target_scope
            or inference_basis.outcome_variable_status != outcome.outcome_variable_status
            or inference_basis.outcome_variable_id != outcome.outcome_variable_id
            or inference_basis.treatment_variable_status != outcome.treatment_variable_status
            or inference_basis.treatment_variable_id != outcome.treatment_variable_id
            or inference_basis.request_alpha_status != outcome.request_alpha_status
            or inference_basis.requested_alpha != outcome.requested_alpha
            or inference_basis.requested_guarantee_status != outcome.requested_guarantee_status
            or inference_basis.requested_guarantee != outcome.requested_guarantee
            or inference_basis.target_relation != outcome.target_relation
        ):
            raise SearchUncertaintyAdmissionError(
                "HTEResult v1 and its selected inference basis do not content-join",
                reason_code="hte_content_mismatch",
            )
    else:
        raise SearchUncertaintyAdmissionError(
            "selected HTE outcome has an unsupported point or interval branch",
            reason_code="hte_content_unavailable",
        )

    if inference_basis is not None:
        require_ref(
            inference_basis.owned_attempt_anchor_ref,
            association.anchor_ref,
            "inference basis owner anchor",
        )
        require_ref(
            inference_basis.source_data_ref,
            binding.selected_method_input_ref,
            "inference basis source input",
        )
        require_ref(
            inference_basis.method_result_ref,
            association.method_result_ref,
            "inference basis method result",
        )
        require_ref(
            inference_basis.method_evidence_ref,
            association.method_evidence_ref,
            "inference basis method evidence",
        )
        require_ref(
            inference_basis.search_uncertainty_task_binding_ref,
            binding_ref,
            "inference basis Search binding",
        )
        require_ref(
            inference_basis.materialization_binding_ref,
            association.materialization_binding_ref,
            "inference basis physical materialization",
        )
        if (
            inference_basis.method_fqn != binding.selected_method_fqn
            or inference_basis.method_abi != binding.selected_method_abi_version
            or inference_basis.method_abi_digest != binding.selected_method_abi_digest
            or inference_basis.resolved_params_sha256 != expected_resolved_params_sha256
            or inference_basis.method_profile_id != binding.selected_inference_profile_id
            or inference_basis.seed != binding.selected_method_seed
            or inference_basis.alpha != binding.request_projection.alpha
            or inference_basis.selected_input_sha256 != outcome.selected_input_sha256
            or inference_basis.selected_rows_sha256 != outcome.selected_rows_sha256
            or inference_basis.selected_x_sha256 != outcome.selected_x_sha256
            or inference_basis.selected_row_order_sha256 != outcome.selected_row_order_sha256
            or inference_basis.n_selected_rows != outcome.n_selected_rows
            or inference_basis.source_data_sha256 != outcome.selected_input_sha256
        ):
            raise SearchUncertaintyAdmissionError(
                "inference basis differs from the selected source, method, or request",
                reason_code="hte_content_mismatch",
            )

    materialization_binding_ref = association.materialization_binding_ref
    if materialization_binding_ref is None:
        raise SearchUncertaintyAdmissionError(
            "selected @2 HTE completion omitted its owner-selected physical source binding",
            reason_code="hte_content_mismatch",
        )
    physical_read_limits = verify_physical_materialization(
        materialization_binding_ref,
        outcome=outcome,
        selected_rows=outcome.n_selected_rows,
        selected_row_order_sha256=outcome.selected_row_order_sha256,
    )
    source_projection_join = None
    source_projection_refusal: str | None = None
    if hte_result is not None and basis.unit_binding_status == "bound":
        source_projection_join, source_projection_refusal = _resolve_hte_source_projection_join(
            verifier=source_projection_verifier,
            store=store,
            selected_method_input_ref=binding.selected_method_input_ref,
            basis=basis,
            request_projection=basis.request_projection,
            limits=physical_read_limits,
        )

    guarantee: Literal["candidate_point", "backend_conditional_interval"] = (
        "backend_conditional_interval" if hte_result is not None else "candidate_point"
    )
    if (
        outcome.target_relation.computed_guarantee_status != "computed"
        or outcome.target_relation.computed_guarantee != guarantee
    ):
        raise SearchUncertaintyAdmissionError(
            "selected HTE output guarantee differs from its source result branch",
            reason_code="hte_content_mismatch",
        )
    if hte_result is not None:
        point_value = hte_result.ate
    elif point_result is not None:
        point_value = point_result.point_estimate
    else:
        raise SearchUncertaintyAdmissionError(
            "selected HTE output has no persisted point value carrier",
            reason_code="hte_content_unavailable",
        )
    interval_lower = None if hte_result is None else hte_result.ate_ci_lower
    interval_upper = None if hte_result is None else hte_result.ate_ci_upper
    interval_confidence = None if hte_result is None else hte_result.confidence_level
    requested_guarantee = binding.request_projection.requested_guarantee
    request_guarantee_status: Literal["declared", "not_established"] = (
        "declared" if requested_guarantee is not None else "not_established"
    )
    guarantee_disposition: Literal[
        "satisfied", "requested_claim_not_satisfied", "not_established"
    ] = (
        "not_established"
        if requested_guarantee is None
        else "satisfied"
        if requested_guarantee == guarantee
        else "requested_claim_not_satisfied"
    )
    computed_scope_status: Literal["recomputed", "not_established"] = (
        "recomputed"
        if outcome.target_relation.computed_scope_status == "recomputed"
        and outcome.target_relation.computed_scope == "selected_evaluation_rows"
        else "not_established"
    )
    computed_scope: Literal["selected_evaluation_rows"] | None = (
        "selected_evaluation_rows" if computed_scope_status == "recomputed" else None
    )
    scope_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"] = (
        "requested_claim_not_satisfied"
        if binding.request_projection.target_scope == "population"
        and computed_scope == "selected_evaluation_rows"
        else "satisfied"
        if binding.request_projection.target_scope == computed_scope
        and computed_scope_status == "recomputed"
        else "not_established"
    )
    overall_disposition: Literal[
        "satisfied", "requested_claim_not_satisfied", "not_established"
    ] = (
        "requested_claim_not_satisfied"
        if "requested_claim_not_satisfied" in {scope_disposition, guarantee_disposition}
        else "not_established"
    )
    target_relation = SearchAssessedTargetRelation(
        requested_scope_status="declared",
        requested_scope=binding.request_projection.target_scope,
        requested_guarantee_status=request_guarantee_status,
        requested_guarantee=requested_guarantee,
        # The current HTE source protocol has no typed source-variable-to-array
        # mapping. Preserve numeric content while keeping target identity unknown.
        computed_scope_status=computed_scope_status,
        computed_scope=computed_scope,
        computed_guarantee_status="computed",
        computed_guarantee=guarantee,
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="recomputed" if hte_result is not None else "not_applicable",
        profile_status="qualified" if hte_result is not None else "point_only",
        scope_disposition=scope_disposition,
        guarantee_disposition=guarantee_disposition,
        overall_disposition=overall_disposition,
    )
    routing_profile_ref = persist_search_uncertainty_routing_profile(store)
    if hte_result is None:
        routing_score = SearchUncertaintyRoutingScore(
            status="unavailable",
            profile_ref=routing_profile_ref,
            unavailable_reason="interval_not_qualified",
            theta=point_value,
            limitations=("point_candidate_retained", "no_interval_routing_score"),
        )
    else:
        comparison_key = make_comparison_key(
            basis=basis,
            confidence_level=hte_result.confidence_level,
            interval_semantics="native_mean_confidence_interval",
            sampling_profile_ref=basis.selected_profile_ref,
        )
        if source_projection_join is not None:
            routing_score = compute_relative_interval_halfwidth_routing(
                profile_ref=routing_profile_ref,
                theta=point_value,
                lower_bound=hte_result.ate_ci_lower,
                upper_bound=hte_result.ate_ci_upper,
                confidence_level=hte_result.confidence_level,
                comparison_key=comparison_key,
                unit_binding_status="bound",
            )
        else:
            unavailable_reason: Literal["scope_not_comparable", "unit_not_bound"] = (
                "unit_not_bound"
                if basis.unit_binding_status == "unknown"
                else "scope_not_comparable"
            )
            routing_score = _unavailable_routing_score(
                profile_ref=routing_profile_ref,
                theta=point_value,
                lower_bound=hte_result.ate_ci_lower,
                upper_bound=hte_result.ate_ci_upper,
                confidence_level=hte_result.confidence_level,
                comparison_key=comparison_key,
                reason=unavailable_reason,
            )
    event_payload_sha256 = _canonical_owned_lifecycle_event_digest_hex(
        association.job_completed_event
    )
    if event_payload_sha256 is None:
        raise SearchUncertaintyAdmissionError(
            "Runtime completion event does not carry its canonical typed digest",
            reason_code="runtime_attempt_association_mismatch",
        )
    now = datetime.now(UTC)
    return SearchAssessedObservationV2(
        basis_ref=binding.basis_ref,
        obligation_id=basis.obligation_id,
        ticket_id=binding.ticket_id,
        ticket_generation=binding.ticket_generation,
        outcome_kind="interval_estimate" if hte_result is not None else "point_estimate",
        predecessor_ref=predecessor_ref,
        search_uncertainty_task_binding_ref=binding_ref,
        owned_attempt_anchor_ref=association.anchor_ref,
        hte_outcome_ref=association.outcome_ref,
        point_result_ref=association.point_result_ref,
        hte_result_ref=association.hte_result_ref,
        inference_basis_ref=association.inference_basis_ref,
        producer_method_fqn=binding.selected_method_fqn,
        producer_method_abi_version=binding.selected_method_abi_version,
        producer_method_abi_digest=binding.selected_method_abi_digest,
        producer_params_sha256=binding.selected_method_params_sha256,
        inference_profile_id=binding.selected_inference_profile_id,
        runtime_summary_sha256=association.outcome_ref.artifact_id.hex,
        input_profile_id=outcome.input_profile_id,
        selected_input_sha256=outcome.selected_input_sha256,
        selected_rows_sha256=outcome.selected_rows_sha256,
        resolved_params_sha256=outcome.resolved_params_sha256,
        target_relation=target_relation,
        run_id=association.run_id,
        job_id=association.job_id,
        attempt=association.attempt,
        completed_event_id=association.job_completed_event.event_id,
        completed_event_payload_sha256=event_payload_sha256,
        completed_at=association.job_completed_event.created_at,
        invocation_basis_ref=(
            None
            if outcome.invocation_basis_ref is None
            else _core_artifact_ref_from_owner_ref(outcome.invocation_basis_ref)
        ),
        source_data_ref=association.source_data_ref,
        materialization_binding_ref=materialization_binding_ref,
        method_result_ref=association.method_result_ref,
        method_evidence_ref=association.method_evidence_ref,
        selected_x_sha256=outcome.selected_x_sha256,
        selected_row_order_sha256=outcome.selected_row_order_sha256,
        n_selected_rows=outcome.n_selected_rows,
        treatment_variable_id=binding.request_projection.treatment_variable_id,
        outcome_variable_id=binding.request_projection.outcome_variable_id,
        control_value=binding.request_projection.control_value,
        treated_value=binding.request_projection.treated_value,
        theta=point_value,
        lower_bound=interval_lower,
        upper_bound=interval_upper,
        confidence_level=interval_confidence,
        unit_binding_status=basis.unit_binding_status,
        unit_scope_ref=basis.unit_scope_ref,
        interval_semantics=(None if hte_result is None else "native_mean_confidence_interval"),
        routing_score=routing_score,
        source_observation_interval_status="not_established",
        source_observation_interval_start=None,
        source_observation_interval_end=None,
        computed_at=completed_at,
        admitted_at=now,
        limitations=tuple(
            sorted(
                set(outcome.limitations)
                | {
                    "estimand_and_contrast_not_established",
                    "population_sampling_coverage_not_claimed",
                    "source_semantic_alignment_not_established",
                    "source_owner_issuance_not_established",
                    "source_time_not_established",
                }
                | (
                    {
                        "source_variable_to_array_mapping_consumer_asserted",
                    }
                    if source_projection_join is not None
                    else {
                        "source_variable_to_array_mapping_not_established",
                        "candidate_ordering_score_unavailable_until_scope_join",
                    }
                )
                | (
                    {f"source_variable_to_array_join_refused:{source_projection_refusal}"}
                    if source_projection_refusal is not None
                    else set()
                )
                | (
                    {"native_interval_is_backend_conditional_on_selected_rows"}
                    if hte_result is not None
                    else {"no_qualified_interval_retained_as_point_candidate"}
                )
                | (
                    {"rejected_native_capture_preserved_in_inference_basis"}
                    if hte_result is None and inference_basis_ref is not None
                    else set()
                )
            )
        ),
    )


def _read_admitted_completion_result(
    state: SearchUncertaintyTicketState,
    *,
    ticket_id: str,
    job_id: str,
    completed_event_id: int,
    candidate_ref: ArtifactRef,
) -> tuple[ArtifactRef | None, bool]:
    """Confirm the exact event is represented in the freshly selected Search CAS."""
    with state._locked(ticket_id):
        row = state._read_row(ticket_id)
        if row is None:
            return None, False
        projection = state._read_projection_for_row(row)
        if projection is None:
            return None, False
        refs = tuple(
            _dedupe_refs(
                (
                    *projection.historical_observation_refs,
                    *(
                        item.observation_ref
                        for obligation in projection.current_obligations
                        for item in obligation.successors
                    ),
                )
            )
        )
        for ref in refs:
            payload = get_json_artifact(state._store, ref)
            if not isinstance(payload, Mapping) or payload.get("state") != "assessed":
                continue
            observation = SearchAssessedObservationV2.model_validate(payload)
            if (
                observation.job_id == job_id
                and observation.completed_event_id == completed_event_id
            ):
                return ref, _ref_key(ref) != _ref_key(candidate_ref)
        return None, False
