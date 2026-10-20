"""Public doe stress report module API."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from math import isclose, isfinite
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from polisyos.core.artifacts import ArtifactManifest, ArtifactRef
from polisyos.ir.world.ids import stable_world_id_from_canon

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.scientist.methods.doe.designs import AdversarialPlan


_STRESS_OUTCOME_BASIS_ARTIFACT_KIND = "scientist.stress_outcome_basis"
_STRESS_OUTCOME_BASIS_SCHEMA_NAME = "polisyos.scientist.StressOutcomeBasis"
_STRESS_OUTCOME_BASIS_SCHEMA_VERSION = "1.0"
_STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION = "1.1"
_STRESS_OBJECTIVE_SOURCE_ARTIFACT_KIND = "scientist.stress_objective_source"
_STRESS_OBJECTIVE_SOURCE_SCHEMA_NAME = "polisyos.scientist.StressObjectiveSource"
_STRESS_OBJECTIVE_SOURCE_SCHEMA_VERSION = "1.0"
_STRESS_TEST_REPORT_ARTIFACT_KIND = "scientist.stress_test_report"
_STRESS_TEST_REPORT_SCHEMA_NAME = "polisyos.scientist.StressTestReport"
_JSON_MEDIA_TYPE = "application/json"
_ModelT = TypeVar("_ModelT", bound=BaseModel)


class VulnerabilityType(str, Enum):
    """Vulnerability type public type."""

    CONSTRAINT_VIOLATION = "constraint_violation"
    NUMERICAL_INSTABILITY = "numerical_instability"
    OBJECTIVE_COLLAPSE = "objective_collapse"
    CONVERGENCE_FAILURE = "convergence_failure"
    EXTREME_SENSITIVITY = "extreme_sensitivity"
    DISTRIBUTIONAL = "distributional"
    COMBINATORIAL = "combinatorial"
    TEMPORAL = "temporal"


class Vulnerability(BaseModel):
    """Vulnerability public type."""

    model_config = ConfigDict(extra="forbid")

    vulnerability_id: str
    vulnerability_type: VulnerabilityType
    severity: str = "high"
    parameter_values: dict[str, float] = Field(default_factory=dict)
    objective_value: float | None = None
    description: str = ""
    affected_kpis: list[str] = Field(default_factory=list)
    constraint_violated: str | None = None
    mitigation: str = ""


def _canon_safe(value: Any) -> Any:
    """Normalize non-finite numbers for deterministic internal stress identifiers."""
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return f"{value:.12g}"
    if isinstance(value, dict):
        return {str(key): _canon_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canon_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_canon_safe(item) for item in value]
    return value


def _deduplicate_vulnerabilities(vulnerabilities: list[Vulnerability]) -> list[Vulnerability]:
    """Apply the one canonical stress vulnerability projection used by producers and readers."""
    unique: dict[str, Vulnerability] = {}
    for vulnerability in vulnerabilities:
        key = stable_world_id_from_canon(
            prefix="stress.vuln",
            payload=_canon_safe(
                {
                    "type": vulnerability.vulnerability_type.value,
                    "params": vulnerability.parameter_values,
                    "description": vulnerability.description,
                    "objective_value": vulnerability.objective_value,
                }
            ),
        )
        if key not in unique:
            unique[key] = vulnerability
    return list(unique.values())


class StressObjectiveEvidence(BaseModel):
    """One source-replayable objective assessment for a single stress occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    objective_name: str = Field(min_length=1)
    objective_direction: Literal["minimize", "maximize"]
    objective_rule_spec: str = Field(min_length=1)
    score_assessment: dict[str, Any]
    source_ref: ArtifactRef

    @model_validator(mode="after")
    def validate_selected_source(self) -> StressObjectiveEvidence:
        """Require an exact selected JSON source profile for fresh replay."""
        if (
            self.source_ref.kind != _STRESS_OBJECTIVE_SOURCE_ARTIFACT_KIND
            or self.source_ref.media_type != _JSON_MEDIA_TYPE
            or self.source_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("stress_objective_source_profile_missing_or_mismatched")
        return self


def _objective_badness(raw_objective: float, direction: Enum) -> float:
    """Map one finite raw objective to the existing adversarial badness scale."""
    if not isfinite(raw_objective):
        return float("nan")
    if direction.value == "maximize":
        return -raw_objective
    return raw_objective


def _is_objective_vulnerable(
    raw_objective: float,
    *,
    threshold: float | None,
    direction: Enum,
) -> bool:
    """Apply the existing adversarial threshold rule to a raw objective."""
    if threshold is None:
        return False
    badness = _objective_badness(raw_objective, direction)
    threshold_badness = _objective_badness(float(threshold), direction)
    return isfinite(badness) and badness >= threshold_badness


def _detect_objective_vulnerability(
    *,
    objective: float,
    threshold: float | None,
    direction: Enum,
    parameters: dict[str, float],
    vuln_id: str,
) -> Vulnerability | None:
    """Recompute the producer's typed objective-collapse finding."""
    if threshold is None or not _is_objective_vulnerable(
        objective, threshold=threshold, direction=direction
    ):
        return None
    badness = _objective_badness(objective, direction)
    threshold_badness = _objective_badness(threshold, direction)
    return Vulnerability(
        vulnerability_id=vuln_id,
        vulnerability_type=VulnerabilityType.OBJECTIVE_COLLAPSE,
        severity="high",
        parameter_values=parameters,
        objective_value=objective,
        description=(
            f"Objective {objective:.6f} violates threshold {threshold:.6f} "
            f"(badness {badness:.6f} >= {threshold_badness:.6f}; "
            f"direction {direction.value})"
        ),
    )


class StressOutcomeRecord(BaseModel):
    """One emitted scenario occurrence; duplicate IDs remain separate rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrence_index: int = Field(ge=0)
    scenario_id: str = Field(min_length=1)
    status: Literal["passed", "failed", "invalid", "skipped", "unknown"]
    parameter_values: dict[str, float] = Field(default_factory=dict)
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    reason_code: str | None = None
    objective_evidence: StressObjectiveEvidence | None = None


class StressOutcomeBasis(BaseModel):
    """Persisted source rows used for a finite empirical scenario score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.0"
    score_profile: Literal["finite_binary_scenario_v1"] = "finite_binary_scenario_v1"
    source_kind: Literal["adversarial_plan", "phase_d4_suite"]
    source_id: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expected_count: int = Field(ge=0)
    expected_scenario_ids: list[str] = Field(default_factory=list)
    outcomes: list[StressOutcomeRecord] = Field(default_factory=list)
    complete: bool
    adaptive_continuation: bool = False
    plan_ref: ArtifactRef | None = None
    benchmark_evaluation_ref: ArtifactRef | None = None
    suite_id: str | None = None
    suite_version: str | None = None
    candidate_ref: ArtifactRef | None = None


class StressScoreComponent(BaseModel):
    """Reference to one immutable finite-scenario outcome basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_id: str = Field(min_length=1)
    score_profile: Literal["finite_binary_scenario_v1"]
    outcome_basis_ref: ArtifactRef


class StressScoreResolution(BaseModel):
    """Freshly recomputed finite outcome status and score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    _vulnerability_projection: list[Vulnerability] | None = PrivateAttr(default=None)

    status: Literal[
        "available",
        "not_evaluated",
        "partial",
        "invalid",
        "legacy_unknown",
        "profile_mismatch",
        "unbound",
    ]
    score_profile: Literal["finite_binary_scenario_v1"] | None = None
    robustness_score: float | None = None
    total_scenarios_evaluated: int = Field(default=0, ge=0)
    passed_count: int = Field(default=0, ge=0)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    component_ids: list[str] = Field(default_factory=list)
    reason_code: str = Field(min_length=1)
    predicate_status: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ] = "not_established"


def _same_artifact(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.artifact_id == right.artifact_id
        and left.kind == right.kind
        and left.media_type == right.media_type
        and left.manifest_profile_sha256 == right.manifest_profile_sha256
    )


class _UnselectedArtifactProfileError(ValueError):
    """Signal that a source reference has no exact selected manifest profile."""


def _read_selected_manifest(store: ArtifactStore, ref: ArtifactRef) -> ArtifactManifest:
    """Resolve one exact selected manifest and verify its complete reference identity."""
    if ref.manifest_profile_sha256 is None:
        raise _UnselectedArtifactProfileError("selected_manifest_profile_missing")
    if ref.media_type != _JSON_MEDIA_TYPE:
        raise ValueError("selected_manifest_media_type_mismatch")
    from polisyos.core.artifacts import artifact_manifest_profile_sha256

    manifest = store.get_manifest(ref)
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise ValueError("selected_manifest_reference_mismatch")
    return manifest


def _load_selected_model(
    store: ArtifactStore,
    ref: ArtifactRef,
    model_type: type[_ModelT],
    *,
    expected_kind: str | Callable[[_ModelT], str],
    expected_schema_name: str,
    expected_schema_version: str | Callable[[_ModelT], str],
) -> tuple[_ModelT, ArtifactManifest]:
    """Decode a typed body only after its selected manifest matches the owner contract."""
    manifest = _read_selected_manifest(store, ref)
    schema = manifest.artifact_schema
    if schema is None or schema.name != expected_schema_name:
        raise ValueError("selected_source_schema_name_mismatch")
    from polisyos.core.artifacts import load_core_json_artifact

    body = load_core_json_artifact(store, ref, manifest_profile_sha256=ref.manifest_profile_sha256)
    model = model_type.model_validate(body)
    kind = expected_kind(model) if callable(expected_kind) else expected_kind
    version = (
        expected_schema_version(model)
        if callable(expected_schema_version)
        else expected_schema_version
    )
    if manifest.kind != kind or ref.kind != kind:
        raise ValueError("selected_source_kind_mismatch")
    if schema.version != version:
        raise ValueError("selected_source_schema_version_mismatch")
    return model, manifest


def _manifest_has_input(manifest: ArtifactManifest, ref: ArtifactRef, *, role: str) -> bool:
    """Check a manifest's direct lineage edge against one exact selected source ref."""
    return any(
        item.role == role
        and item.artifact_id == ref.artifact_id
        and item.manifest_profile_sha256 == ref.manifest_profile_sha256
        for item in manifest.inputs
    )


def _resolve_adversarial_objective_evidence(
    store: ArtifactStore,
    basis: StressOutcomeBasis,
    basis_manifest: ArtifactManifest,
    component_ids: list[str],
    plan: AdversarialPlan,
) -> StressScoreResolution | None:
    """Replay objective values and derive every persisted finite pass/fail row."""
    if basis.schema_version == "1.0":
        return _resolution(
            "unbound",
            component_ids,
            "legacy_adversarial_objective_source_evidence_missing",
        )

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.methods.doe.sampling import generate_adversarial_samples
    from polisyos.scientist.methods.search.objective import (
        ObjectiveScoreAssessment,
        ObjectiveScoreStatus,
        ObjectiveValue,
        OptimizationDirection,
        objective_value_matches_rule,
    )

    try:
        planned_samples = generate_adversarial_samples(plan)
    except Exception:
        return _resolution(
            "profile_mismatch", component_ids, "adversarial_plan_sampling_not_reproducible"
        )
    if len(planned_samples) != len(basis.outcomes):
        return _resolution("invalid", component_ids, "plan_outcome_sample_count_mismatch")

    selected_rule: tuple[str, str, str] | None = None
    replayed_vulnerabilities: list[Vulnerability] = []
    for sample, outcome in zip(planned_samples, basis.outcomes, strict=True):
        if outcome.status not in {"passed", "failed"}:
            continue
        expected_parameters = {
            parameter.name: float(value)
            for parameter, value in zip(plan.parameter_specs, sample, strict=True)
        }
        if outcome.parameter_values != expected_parameters:
            return _resolution("invalid", component_ids, "plan_parameter_values_mismatch")
        evidence = outcome.objective_evidence
        if evidence is None:
            return _resolution("unbound", component_ids, "objective_source_evidence_missing")
        if evidence.source_ref.manifest_profile_sha256 is None:
            return _resolution("unbound", component_ids, "objective_source_profile_missing")
        rule_identity = (
            evidence.objective_name,
            evidence.objective_direction,
            evidence.objective_rule_spec,
        )
        if selected_rule is None:
            selected_rule = rule_identity
        elif selected_rule != rule_identity:
            return _resolution(
                "invalid", component_ids, "selected_objective_rule_changed_between_occurrences"
            )

        if not _manifest_has_input(
            basis_manifest,
            evidence.source_ref,
            role=f"objective_source:{outcome.occurrence_index}",
        ):
            return _resolution("invalid", component_ids, "objective_source_lineage_mismatch")
        try:
            source_manifest = _read_selected_manifest(store, evidence.source_ref)
            source_schema = source_manifest.artifact_schema
            if (
                source_manifest.kind != _STRESS_OBJECTIVE_SOURCE_ARTIFACT_KIND
                or source_schema is None
                or source_schema.name != _STRESS_OBJECTIVE_SOURCE_SCHEMA_NAME
                or source_schema.version != _STRESS_OBJECTIVE_SOURCE_SCHEMA_VERSION
            ):
                return _resolution("invalid", component_ids, "objective_source_schema_mismatch")
            source = load_core_json_artifact(
                store,
                evidence.source_ref,
                manifest_profile_sha256=evidence.source_ref.manifest_profile_sha256,
            )
            if not isinstance(source, dict):
                return _resolution("invalid", component_ids, "objective_source_not_mapping")
        except _UnselectedArtifactProfileError:
            return _resolution("unbound", component_ids, "objective_source_profile_missing")
        except Exception:
            return _resolution("invalid", component_ids, "objective_source_unreadable")

        payload = evidence.score_assessment
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schema_version",
                "objective_ref",
                "rule_spec",
                "required_input_groups",
                "source_field_names",
                "source_values",
                "source_unit_bindings",
                "source_sha256",
                "value",
                "status",
                "limitation",
            }
            or payload.get("schema_version") != "2.0"
            or payload.get("rule_spec") != evidence.objective_rule_spec
        ):
            return _resolution("invalid", component_ids, "objective_assessment_contract_mismatch")
        assessment = ObjectiveScoreAssessment.from_payload(payload)
        if assessment.to_payload() != payload:
            return _resolution("invalid", component_ids, "objective_assessment_payload_malformed")
        if assessment.status is not ObjectiveScoreStatus.AVAILABLE:
            if assessment.status in {
                ObjectiveScoreStatus.UNAVAILABLE,
                ObjectiveScoreStatus.NOT_ESTABLISHED,
            }:
                return _resolution(
                    "unbound",
                    component_ids,
                    assessment.limitation or "objective_score_not_available",
                )
            return _resolution("invalid", component_ids, "objective_score_assessment_invalid")
        if assessment.value is None:
            return _resolution("invalid", component_ids, "objective_score_value_missing")
        try:
            direction = OptimizationDirection(evidence.objective_direction)
            objective = ObjectiveValue(
                name=evidence.objective_name,
                raw_value=assessment.value,
                direction=direction,
                score_status=assessment.status,
                score_assessment=assessment,
            )
        except (TypeError, ValueError):
            return _resolution("invalid", component_ids, "objective_assessment_invalid")
        if not objective_value_matches_rule(
            objective,
            source,
            expected_name=evidence.objective_name,
            expected_direction=direction,
            expected_rule_spec=evidence.objective_rule_spec,
        ):
            return _resolution("invalid", component_ids, "objective_source_replay_mismatch")

        expected_vulnerability = _detect_objective_vulnerability(
            objective=assessment.value,
            threshold=plan.vulnerability_threshold,
            direction=direction,
            parameters=expected_parameters,
            vuln_id=f"vuln_objective_{outcome.occurrence_index}",
        )
        expected_status = "failed" if expected_vulnerability is not None else "passed"
        if outcome.status != expected_status:
            return _resolution(
                "invalid", component_ids, "objective_outcome_classification_mismatch"
            )
        expected_vulnerabilities = (
            [] if expected_vulnerability is None else [expected_vulnerability]
        )
        if [item.model_dump(mode="json") for item in outcome.vulnerabilities] != [
            item.model_dump(mode="json") for item in expected_vulnerabilities
        ]:
            return _resolution(
                "invalid", component_ids, "objective_vulnerability_classification_mismatch"
            )
        replayed_vulnerabilities.extend(expected_vulnerabilities)

    if selected_rule is None:
        return _resolution("unbound", component_ids, "objective_source_evidence_missing")
    # The selected objective is carried by the basis itself. The source and rows replay, but no
    # independent request/run-state selection reference reaches this consumer, so this cannot
    # qualify a protected finite score.
    return _resolution(
        "unbound",
        component_ids,
        "selected_objective_intent_not_independently_established",
        vulnerability_projection=_deduplicate_vulnerabilities(replayed_vulnerabilities)[
            : plan.collect_top_k
        ],
    )


def _expected_adversarial_count(plan) -> int | None:
    """Recompute a finite plan denominator without trusting report counters."""
    from polisyos.scientist.methods.doe.designs import AdversarialStrategy

    if plan.strategy is AdversarialStrategy.GRID_EXTREME:
        parameter_count = len(plan.parameter_specs)
        if parameter_count >= plan.max_iterations.bit_length():
            return plan.max_iterations
        return min(2**parameter_count, plan.max_iterations)
    if plan.strategy is AdversarialStrategy.RANDOM_TAIL:
        return plan.max_iterations
    if plan.strategy is AdversarialStrategy.SEARCH_LOOP:
        return min(plan.max_iterations, 32)
    return None


def _resolution(
    status,
    component_ids: list[str],
    reason_code: str,
    *,
    predicate_status="not_established",
    vulnerability_projection: list[Vulnerability] | None = None,
    score_profile: Literal["finite_binary_scenario_v1"] | None = None,
    total_scenarios_evaluated: int = 0,
    passed_count: int = 0,
    critical_count: int = 0,
    high_count: int = 0,
    medium_count: int = 0,
) -> StressScoreResolution:
    resolution = StressScoreResolution(
        status=status,
        score_profile=score_profile,
        total_scenarios_evaluated=total_scenarios_evaluated,
        passed_count=passed_count,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        component_ids=component_ids,
        reason_code=reason_code,
        predicate_status=predicate_status,
    )
    resolution._vulnerability_projection = vulnerability_projection
    return resolution


def resolve_stress_score_components(
    store,
    components: list[StressScoreComponent],
    *,
    expected_candidate_ref: ArtifactRef | None,
) -> StressScoreResolution:
    """Resolve actual CAS outcome rows and recompute the finite binary score."""
    from polisyos.scientist.methods.autotune.models import (
        _BENCHMARK_EVALUATION_SCHEMA_NAME,
        BenchmarkEvaluation,
        BenchmarkSplit,
        _benchmark_evaluation_artifact_kind,
    )
    from polisyos.scientist.methods.doe.designs import (
        _ADVERSARIAL_PLAN_ARTIFACT_KIND,
        _ADVERSARIAL_PLAN_SCHEMA_NAME,
        _ADVERSARIAL_PLAN_SCHEMA_VERSION,
        AdversarialPlan,
    )
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    component_ids = [item.component_id for item in components]
    if not components:
        return _resolution("not_evaluated", [], "no_finite_score_components")
    if expected_candidate_ref is None:
        return _resolution("unbound", component_ids, "current_candidate_ref_missing")
    if expected_candidate_ref.kind != PolicyCandidateSchema.ARTIFACT_KIND:
        return _resolution("unbound", component_ids, "current_candidate_ref_not_canonical")
    if expected_candidate_ref.media_type != PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE:
        return _resolution("invalid", component_ids, "current_candidate_media_type_mismatch")
    if expected_candidate_ref.manifest_profile_sha256 is None:
        return _resolution("unbound", component_ids, "current_candidate_profile_missing")
    try:
        current_candidate, _candidate_manifest = _load_selected_model(
            store,
            expected_candidate_ref,
            PolicyCandidateSchema,
            expected_kind=PolicyCandidateSchema.ARTIFACT_KIND,
            expected_schema_name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
            expected_schema_version=PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION,
        )
    except Exception:
        return _resolution("invalid", component_ids, "current_candidate_manifest_invalid")
    if current_candidate.schema_version != PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION:
        return _resolution("invalid", component_ids, "current_candidate_body_version_mismatch")
    if len(component_ids) != len(set(component_ids)):
        return _resolution("invalid", component_ids, "duplicate_component_id")

    total = passed = critical = high = medium = 0
    projected_vulnerabilities: list[Vulnerability] = []
    selected_intent_unbound: StressScoreResolution | None = None
    for component in components:
        if component.outcome_basis_ref.manifest_profile_sha256 is None:
            return _resolution("unbound", component_ids, "outcome_basis_profile_missing")
        try:
            basis, basis_manifest = _load_selected_model(
                store,
                component.outcome_basis_ref,
                StressOutcomeBasis,
                expected_kind=_STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
                expected_schema_name=_STRESS_OUTCOME_BASIS_SCHEMA_NAME,
                expected_schema_version=lambda item: (
                    _STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION
                    if item.schema_version == _STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION
                    else _STRESS_OUTCOME_BASIS_SCHEMA_VERSION
                ),
            )
        except Exception:
            return _resolution("invalid", component_ids, "outcome_basis_unreadable")
        if (
            component.score_profile != basis.score_profile
            or component.component_id != basis.source_id
        ):
            return _resolution("invalid", component_ids, "basis_component_mismatch")
        if not _same_artifact(basis.candidate_ref, expected_candidate_ref):
            return _resolution("invalid", component_ids, "candidate_binding_missing_or_mismatched")
        if basis.candidate_ref is None or not _manifest_has_input(
            basis_manifest, basis.candidate_ref, role="candidate"
        ):
            return _resolution("invalid", component_ids, "basis_candidate_lineage_mismatch")

        if basis.source_kind == "adversarial_plan":
            if basis.plan_ref is None or basis.benchmark_evaluation_ref is not None:
                return _resolution("invalid", component_ids, "adversarial_source_refs_invalid")
            if basis.plan_ref.manifest_profile_sha256 is None:
                return _resolution("unbound", component_ids, "adversarial_plan_profile_missing")
            try:
                plan, _plan_manifest = _load_selected_model(
                    store,
                    basis.plan_ref,
                    AdversarialPlan,
                    expected_kind=_ADVERSARIAL_PLAN_ARTIFACT_KIND,
                    expected_schema_name=_ADVERSARIAL_PLAN_SCHEMA_NAME,
                    expected_schema_version=_ADVERSARIAL_PLAN_SCHEMA_VERSION,
                )
            except Exception:
                return _resolution("invalid", component_ids, "adversarial_plan_unreadable")
            if not _manifest_has_input(basis_manifest, basis.plan_ref, role="adversarial_plan"):
                return _resolution("invalid", component_ids, "basis_plan_lineage_mismatch")
            expected_count = _expected_adversarial_count(plan)
            if expected_count is None:
                return _resolution(
                    "profile_mismatch",
                    component_ids,
                    "unsupported_adversarial_strategy",
                )
            if basis.adaptive_continuation:
                return _resolution(
                    "profile_mismatch",
                    component_ids,
                    "adaptive_continuation_not_finite",
                )
            if basis.expected_count != expected_count:
                return _resolution("invalid", component_ids, "plan_denominator_mismatch")
            if basis.expected_scenario_ids != [f"initial:{i}" for i in range(expected_count)]:
                return _resolution("invalid", component_ids, "plan_occurrence_roster_mismatch")
            actual_scenario_ids = [item.scenario_id for item in basis.outcomes]
            if actual_scenario_ids != basis.expected_scenario_ids[: len(actual_scenario_ids)]:
                return _resolution("invalid", component_ids, "plan_outcome_roster_mismatch")
        else:
            if basis.schema_version != _STRESS_OUTCOME_BASIS_SCHEMA_VERSION:
                return _resolution(
                    "invalid", component_ids, "phase_d4_basis_schema_version_mismatch"
                )
            if (
                basis.benchmark_evaluation_ref is None
                or basis.plan_ref is not None
                or basis.suite_id is None
                or basis.suite_version is None
            ):
                return _resolution("invalid", component_ids, "phase_d4_source_refs_invalid")
            if basis.benchmark_evaluation_ref.manifest_profile_sha256 is None:
                return _resolution("unbound", component_ids, "benchmark_evaluation_profile_missing")
            try:
                evaluation, evaluation_manifest = _load_selected_model(
                    store,
                    basis.benchmark_evaluation_ref,
                    BenchmarkEvaluation,
                    expected_kind=lambda item: _benchmark_evaluation_artifact_kind(item.loop_id),
                    expected_schema_name=_BENCHMARK_EVALUATION_SCHEMA_NAME,
                    expected_schema_version=lambda item: item.suite_version,
                )
            except Exception:
                return _resolution("invalid", component_ids, "benchmark_evaluation_unreadable")
            if (
                not _manifest_has_input(
                    basis_manifest,
                    basis.benchmark_evaluation_ref,
                    role="benchmark_evaluation",
                )
                or basis.candidate_ref is None
                or not _manifest_has_input(
                    evaluation_manifest, basis.candidate_ref, role="candidate"
                )
            ):
                return _resolution("invalid", component_ids, "benchmark_lineage_mismatch")
            executed = [item for item in basis.outcomes if item.status != "skipped"]
            sample_count = evaluation.sample_counts.get(BenchmarkSplit.ROTATING_CHALLENGE.value)
            if (
                evaluation.suite_id != basis.suite_id
                or evaluation.suite_version != basis.suite_version
                or evaluation.resolved_runtime_split_type() is not BenchmarkSplit.ROTATING_CHALLENGE
                or type(sample_count) is not int
                or sample_count != len(executed)
                or not _same_artifact(evaluation.candidate_ref, basis.candidate_ref)
                or evaluation.metadata.get("challenge_case_ids") != basis.expected_scenario_ids
                or [item.scenario_id for item in basis.outcomes] != basis.expected_scenario_ids
            ):
                return _resolution("invalid", component_ids, "phase_d4_evaluation_binding_mismatch")
            if executed:
                fraction = sum(item.status == "passed" for item in executed) / len(executed)
                for metrics in (
                    evaluation.selection_metrics,
                    evaluation.holdout_metrics,
                ):
                    reported = metrics.get("challenge_pass_rate")
                    if (
                        type(reported) not in {int, float}
                        or not isfinite(float(reported))
                        or not isclose(float(reported), fraction, rel_tol=0.0, abs_tol=1e-12)
                    ):
                        return _resolution("invalid", component_ids, "phase_d4_rate_mismatch")
            elif basis.expected_count:
                return _resolution("partial", component_ids, "phase_d4_has_no_executed_cases")

        indexes = [item.occurrence_index for item in basis.outcomes]
        if indexes != list(range(len(basis.outcomes))):
            return _resolution("invalid", component_ids, "occurrences_not_ordered")
        if basis.expected_count == 0:
            return _resolution("not_evaluated", component_ids, "zero_expected_denominator")
        if not basis.complete or len(basis.outcomes) != basis.expected_count:
            return _resolution("partial", component_ids, "expected_occurrence_rows_incomplete")
        if any(item.status == "skipped" for item in basis.outcomes):
            return _resolution("partial", component_ids, "skipped_occurrence_present")
        if any(item.status in {"invalid", "unknown"} for item in basis.outcomes):
            return _resolution("invalid", component_ids, "invalid_or_unknown_evaluation_present")
        for outcome in basis.outcomes:
            if outcome.status in {"passed", "failed"} and (
                (outcome.status == "passed") != (len(outcome.vulnerabilities) == 0)
            ):
                return _resolution("invalid", component_ids, "outcome_and_violations_disagree")
        if basis.source_kind == "adversarial_plan":
            objective_resolution = _resolve_adversarial_objective_evidence(
                store, basis, basis_manifest, component_ids, plan
            )
            if objective_resolution is not None:
                if (
                    objective_resolution.status == "unbound"
                    and objective_resolution.reason_code
                    == "selected_objective_intent_not_independently_established"
                    and objective_resolution._vulnerability_projection is not None
                ):
                    projected_vulnerabilities.extend(objective_resolution._vulnerability_projection)
                    selected_intent_unbound = objective_resolution
                else:
                    return objective_resolution
        else:
            projected_vulnerabilities.extend(
                vulnerability
                for outcome in basis.outcomes
                for vulnerability in outcome.vulnerabilities
            )
        total += len(basis.outcomes)
        passed += sum(item.status == "passed" for item in basis.outcomes)
        violations = [v for item in basis.outcomes for v in item.vulnerabilities]
        critical += sum(item.severity == "critical" for item in violations)
        high += sum(item.severity == "high" for item in violations)
        medium += sum(item.severity == "medium" for item in violations)

    if total == 0:
        return _resolution("not_evaluated", component_ids, "zero_observed_denominator")
    if selected_intent_unbound is not None:
        resolution = _resolution(
            "unbound",
            component_ids,
            "selected_objective_intent_not_independently_established",
            score_profile="finite_binary_scenario_v1",
            total_scenarios_evaluated=total,
            passed_count=passed,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            vulnerability_projection=projected_vulnerabilities,
        )
        return resolution
    resolution = StressScoreResolution(
        status="available",
        score_profile="finite_binary_scenario_v1",
        robustness_score=passed / total,
        total_scenarios_evaluated=total,
        passed_count=passed,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        component_ids=component_ids,
        reason_code="source_bound_occurrences_recomputed",
        # Phase D4 remains independently bound to its benchmark evaluation.
        predicate_status="recomputed",
    )
    resolution._vulnerability_projection = projected_vulnerabilities
    return resolution


class StressTestReport(BaseModel):
    """Summary of vulnerabilities, worst cases, and scenario evidence from adversarial stress testing."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.1"
    report_id: str

    total_scenarios_evaluated: int = 0
    score_profile: (
        Literal["finite_binary_scenario_v1", "continuous_severity_v1", "mixed_unscored"] | None
    ) = None
    score_status: Literal[
        "available",
        "not_evaluated",
        "partial",
        "invalid",
        "legacy_unknown",
        "profile_mismatch",
        "unbound",
    ] = "legacy_unknown"
    score_reason: str | None = None
    score_predicate_status: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ] = "not_established"
    score_components: list[StressScoreComponent] = Field(default_factory=list)
    adversarial_plan_ref: str | None = None
    fidelity_mode: str = "stress_preset"

    worst_case_parameters: dict[str, float] = Field(default_factory=dict)
    worst_case_objective: float | None = None

    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0

    robustness_score: float | None = None
    set_adequacy_status: str | None = None
    coverage_empirical: float | None = Field(default=None, ge=0.0, le=1.0)
    coverage_target: float | None = Field(default=None, ge=0.0, le=1.0)
    inflation_mean: float | None = None
    inflation_budget: float | None = Field(default=None, ge=0.0)
    frontier_knee_rho: float | None = Field(default=None, ge=0.0)
    undercoverage_vulnerability: Vulnerability | None = None
    overconservatism_vulnerability: Vulnerability | None = None
    decision_packet_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    _cas_artifact_ref: ArtifactRef | None = PrivateAttr(default=None)

    @property
    def cas_artifact_ref(self) -> ArtifactRef | None:
        """Return this producer invocation's exact selected CAS report reference."""
        return self._cas_artifact_ref

    @property
    def is_robust(self) -> bool:
        """Return true only for an available finite-profile score."""
        return (
            self.score_status == "available"
            and self.score_profile == "finite_binary_scenario_v1"
            and self.robustness_score is not None
            and self.critical_count == 0
            and self.high_count == 0
        )


def _load_stress_report_source(
    store: ArtifactStore,
    report_ref: ArtifactRef,
    *,
    allow_unselected_profile: bool = False,
) -> tuple[StressTestReport, ArtifactManifest]:
    """Read a report under its selected schema contract; unselected reads are candidate-only."""
    if (
        report_ref.kind != _STRESS_TEST_REPORT_ARTIFACT_KIND
        or report_ref.media_type != _JSON_MEDIA_TYPE
    ):
        raise ValueError("stress_report_source_identity_mismatch")
    if report_ref.manifest_profile_sha256 is None and allow_unselected_profile:
        manifest = store.get_manifest(report_ref)
        if manifest.kind != report_ref.kind or manifest.media_type != report_ref.media_type:
            raise ValueError("stress_report_source_manifest_identity_mismatch")
        schema = manifest.artifact_schema
        if schema is None or schema.name != _STRESS_TEST_REPORT_SCHEMA_NAME:
            raise ValueError("stress_report_source_schema_mismatch")
        from polisyos.core.artifacts import load_core_json_artifact

        report = StressTestReport.model_validate(load_core_json_artifact(store, report_ref))
        if schema.version != report.schema_version:
            raise ValueError("stress_report_source_schema_version_mismatch")
        return report, manifest
    report, manifest = _load_selected_model(
        store,
        report_ref,
        StressTestReport,
        expected_kind=_STRESS_TEST_REPORT_ARTIFACT_KIND,
        expected_schema_name=_STRESS_TEST_REPORT_SCHEMA_NAME,
        expected_schema_version=lambda item: item.schema_version,
    )
    return report, manifest


def _vulnerability_projection_matches(
    reported: list[Vulnerability], expected: list[Vulnerability]
) -> bool:
    """Compare the complete typed report projection in order, including descriptive fields."""
    return [item.model_dump(mode="json") for item in reported] == [
        item.model_dump(mode="json") for item in expected
    ]


def resolve_stress_report_artifact(
    store,
    report_ref: ArtifactRef,
    *,
    expected_candidate_ref: ArtifactRef | None,
) -> tuple[StressTestReport, StressScoreResolution]:
    """Freshly resolve a selected report and reject summaries that disagree with CAS rows."""
    if report_ref.manifest_profile_sha256 is None:
        try:
            report, _manifest = _load_stress_report_source(
                store, report_ref, allow_unselected_profile=True
            )
        except Exception:
            report = StressTestReport(report_id="unreadable-stress-report", schema_version="1.0")
            return report, _resolution("invalid", [], "stress_report_unreadable")
        if report.schema_version != "1.1":
            return report, _resolution(
                "legacy_unknown", [], "legacy_report_without_occurrence_basis"
            )
        return report, _resolution("unbound", [], "stress_report_profile_missing")
    try:
        report, report_manifest = _load_stress_report_source(store, report_ref)
    except Exception:
        report = StressTestReport(report_id="unreadable-stress-report", schema_version="1.0")
        return report, _resolution("invalid", [], "stress_report_unreadable")
    if report.score_components:
        required_inputs = [
            ("stress_outcome_basis", item.outcome_basis_ref) for item in report.score_components
        ]
        if expected_candidate_ref is not None:
            required_inputs.append(("candidate", expected_candidate_ref))
        if any(
            not _manifest_has_input(report_manifest, ref, role=role)
            for role, ref in required_inputs
        ):
            return report, _resolution("invalid", [], "stress_report_lineage_mismatch")
    if report.schema_version != "1.1":
        return report, _resolution("legacy_unknown", [], "legacy_report_without_occurrence_basis")
    if report.score_profile in {"continuous_severity_v1", "mixed_unscored"}:
        if report.score_components:
            component_resolution = resolve_stress_score_components(
                store,
                report.score_components,
                expected_candidate_ref=expected_candidate_ref,
            )
            if component_resolution.status != "available":
                return report, component_resolution
            reason_code = (
                "mixed_profile_is_not_binary"
                if report.score_profile == "mixed_unscored"
                else "continuous_profile_is_not_binary"
            )
            return report, component_resolution.model_copy(
                update={
                    "status": "profile_mismatch",
                    "score_profile": None,
                    "robustness_score": None,
                    "reason_code": reason_code,
                }
            )
        reason_code = (
            "mixed_profile_is_not_binary"
            if report.score_profile == "mixed_unscored"
            else "continuous_profile_is_not_binary"
        )
        return report, _resolution("profile_mismatch", [], reason_code)
    if not report.score_components:
        if report.score_status == "not_evaluated" and report.robustness_score is None:
            return report, _resolution("not_evaluated", [], "no_finite_occurrence_basis")
        if report.score_status == "available" or report.robustness_score is not None:
            return report, _resolution("invalid", [], "score_claim_without_finite_basis")
        if report.score_status in {"unbound", "partial", "invalid", "profile_mismatch"}:
            return report, _resolution(
                report.score_status,
                [],
                report.score_reason or "finite_objective_basis_not_available",
            )
        return report, _resolution("legacy_unknown", [], "finite_basis_not_established")
    resolution = resolve_stress_score_components(
        store, report.score_components, expected_candidate_ref=expected_candidate_ref
    )
    projected_vulnerabilities = resolution._vulnerability_projection
    if projected_vulnerabilities is not None and not _vulnerability_projection_matches(
        report.vulnerabilities, projected_vulnerabilities
    ):
        return report, resolution.model_copy(
            update={
                "status": "invalid",
                "robustness_score": None,
                "reason_code": "report_vulnerability_projection_reconciliation_failed",
            }
        )
    if resolution.status != "available":
        if resolution.reason_code == "selected_objective_intent_not_independently_established":
            diagnostic_matches = (
                report.score_profile == resolution.score_profile
                and report.total_scenarios_evaluated == resolution.total_scenarios_evaluated
                and report.critical_count == resolution.critical_count
                and report.high_count == resolution.high_count
                and report.medium_count == resolution.medium_count
            )
            if not diagnostic_matches:
                return report, resolution.model_copy(
                    update={
                        "status": "invalid",
                        "robustness_score": None,
                        "reason_code": "report_summary_reconciliation_failed",
                    }
                )
            return report, resolution
        if report.score_status == "available" or report.robustness_score is not None:
            if resolution.reason_code == "legacy_adversarial_objective_source_evidence_missing":
                return report, resolution
            resolution = resolution.model_copy(
                update={
                    "status": "invalid",
                    "robustness_score": None,
                    "reason_code": "score_claim_without_resolved_basis",
                }
            )
        return report, resolution
    matches = (
        report.score_profile == resolution.score_profile
        and report.total_scenarios_evaluated == resolution.total_scenarios_evaluated
        and report.critical_count == resolution.critical_count
        and report.high_count == resolution.high_count
        and report.medium_count == resolution.medium_count
        and report.score_predicate_status == resolution.predicate_status
        and report.score_status == "available"
        and report.robustness_score is not None
        and isclose(
            float(report.robustness_score),
            float(resolution.robustness_score),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    )
    if not matches:
        resolution = resolution.model_copy(
            update={
                "status": "invalid",
                "robustness_score": None,
                "reason_code": "report_summary_reconciliation_failed",
            }
        )
    return report, resolution
