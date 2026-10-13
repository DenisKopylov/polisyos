"""Typed search uncertainty contracts for funnel routing and judge semantics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

import numpy as np

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.artifacts.protocol import ArtifactStore, resolve_manifest_by_profile
from polisyos.core.canon import CanonSpec
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.welfare import (
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    load_welfare_bundle,
    load_welfare_sample_bundle,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir import UncertaintyType
from polisyos.ir.registry.refs import ArtifactRefModel, WelfareBundleRef, WelfareSampleBundleRef


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
_SOURCE_BOUND_RISK_OBSERVATION_VERSION = "1.0"


class SourceBoundRiskObservation(BaseModel):
    """Candidate-only raw welfare measurement; never a search-risk refinement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
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
    method_config_ref: ArtifactRef
    propagation_report_ref: ArtifactRef
    sample_bundle_ref: ArtifactRef
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


def _source_manifest(store: ArtifactStore, ref: ArtifactRef) -> ArtifactManifest:
    manifest = store.get_manifest(ref)
    if manifest.kind != ref.kind or manifest.media_type != ref.media_type:
        raise ValueError("source-bound risk artifact manifest contract mismatch")
    if not store.verify(ref).ok:
        raise ValueError("source-bound risk artifact integrity failure")
    return manifest


def _source_manifest_for_edge(
    store: ArtifactStore, edge: InputRef
) -> tuple[ArtifactRef, ArtifactManifest]:
    if edge.manifest_profile_sha256 is None:
        manifest = store.get_manifest(edge.artifact_id)
    else:
        manifest = resolve_manifest_by_profile(
            store, edge.artifact_id, edge.manifest_profile_sha256
        )
    ref = ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    _source_manifest(store, ref)
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


def _source_observation_inputs(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_ref: ArtifactRef,
    policy_ref: ArtifactRef,
    method_ref: ArtifactRef,
    report_ref: ArtifactRef,
    sample_ref: ArtifactRef,
    source_manifests: tuple[tuple[str, ArtifactManifest], ...],
) -> list[InputRef]:
    inputs = [
        input_ref_from_artifact_ref(candidate_ref, role="search_candidate"),
        input_ref_from_artifact_ref(welfare_ref, role="source_welfare_bundle"),
        input_ref_from_artifact_ref(policy_ref, role="policy_scope_claim"),
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


def _build_source_bound_risk_observation(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    welfare_bundle_ref: ArtifactRef,
) -> tuple[SourceBoundRiskObservation, list[InputRef]]:
    """Recompute a candidate-only welfare observation from its existing CAS sources."""
    if candidate_ref.kind != "scientist.policy_design.candidate":
        raise ValueError("source-bound risk requires the selected policy candidate ref")
    candidate_manifest = _source_manifest(store, candidate_ref)
    if (
        candidate_manifest.artifact_schema is None
        or candidate_manifest.artifact_schema.name
        != "polisyos.scientist.policy_design.PolicyCandidateSchema"
        or candidate_manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("source-bound risk candidate schema mismatch")

    welfare_ref = _source_core_ref(welfare_bundle_ref)
    if welfare_ref.kind != "ir.welfare_bundle":
        raise ValueError("source-bound risk requires an ir.welfare_bundle")
    welfare_manifest = _source_manifest(store, welfare_ref)
    if (
        welfare_manifest.artifact_schema is None
        or welfare_manifest.artifact_schema.name != "ir.welfare_bundle"
        or welfare_manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("source-bound risk welfare bundle schema mismatch")
    bundle = load_welfare_bundle(
        store, WelfareBundleRef.model_validate(welfare_ref.model_dump(mode="python"))
    )
    if bundle.policy_ref is None:
        raise ValueError("welfare bundle has no policy scope claim")
    policy_ref = _source_core_ref(bundle.policy_ref)
    if policy_ref != candidate_ref:
        raise ValueError("welfare bundle policy claim differs from the selected candidate")
    _source_manifest(store, policy_ref)

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
        or sample_manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("welfare sample bundle schema mismatch")

    method_payload = get_json_artifact(store, method_ref)
    method_config = PropagationConfig.model_validate(method_payload, strict=True)
    sample_bundle = load_welfare_sample_bundle(
        store, WelfareSampleBundleRef.model_validate(sample_ref.model_dump(mode="python"))
    )
    report_payload = get_json_artifact(store, report_ref)
    if not isinstance(report_payload, Mapping):
        raise ValueError("welfare propagation report payload is not an object")
    if report_manifest.artifact_schema.version != report_payload.get("schema_version"):
        raise ValueError("welfare propagation report schema version differs from its content")
    if sample_manifest.artifact_schema.version != sample_bundle.schema_version:
        raise ValueError("welfare sample schema version differs from its content")
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
    ] = (
        "complete_requested_draws"
        if complete
        else "successful_draws_only_conditional_on_execution"
    )
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

    inputs = _source_observation_inputs(
        store,
        candidate_ref=candidate_ref,
        welfare_ref=welfare_ref,
        policy_ref=policy_ref,
        method_ref=method_ref,
        report_ref=report_ref,
        sample_ref=sample_ref,
        source_manifests=(
            ("welfare_bundle", welfare_manifest),
            ("welfare_method", method_manifest),
            ("welfare_report", report_manifest),
            ("welfare_sample", sample_manifest),
        ),
    )
    observation = SourceBoundRiskObservation(
        candidate_ref=candidate_ref,
        welfare_bundle_ref=welfare_ref,
        policy_scope_claim_ref=policy_ref,
        method_config_ref=method_ref,
        propagation_report_ref=report_ref,
        sample_bundle_ref=sample_ref,
        welfare_measure=bundle.welfare_measure,
        method_used=bundle.method_used,
        source_status=bundle.status,
        confidence_level=method_config.confidence_level,
        mc_sampling_method=method_config.mc_sampling_method,
        observed_at=welfare_manifest.created_at,
        nominal_point_estimate=bundle.point_estimate,
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
