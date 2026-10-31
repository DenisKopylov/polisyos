"""Public doe stress report module API."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import isclose, isfinite
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from polisyos.core.artifacts import ArtifactManifest, ArtifactRef, input_ref_from_artifact_ref
from polisyos.ir.world import stable_world_id_from_canon

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.scientist.methods.backtesting.phase_d4_source import PhaseD4SuiteRoster
    from polisyos.scientist.methods.doe.designs import AdversarialPlan


_STRESS_OUTCOME_BASIS_ARTIFACT_KIND = "scientist.stress_outcome_basis"
_STRESS_OUTCOME_BASIS_SCHEMA_NAME = "polisyos.scientist.StressOutcomeBasis"
_STRESS_OUTCOME_BASIS_SCHEMA_VERSION = "1.0"
_STRESS_OUTCOME_BASIS_D4_SCHEMA_VERSION = "2.0"
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

    schema_version: Literal["1.0", "1.1", "2.0"] = "1.0"
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
    phase_d4_replay_source_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def validate_replay_source_contract(self) -> StressOutcomeBasis:
        """Require the replay artifact only for the source-bound D.4 schema."""
        if self.schema_version == "2.0" and (
            self.source_kind != "phase_d4_suite" or self.phase_d4_replay_source_ref is None
        ):
            raise ValueError("phase_d4_replay_source_required_for_schema_v2")
        if self.source_kind == "adversarial_plan" and self.phase_d4_replay_source_ref is not None:
            raise ValueError("adversarial_basis_cannot_carry_phase_d4_replay_source")
        if self.schema_version != "2.0" and self.phase_d4_replay_source_ref is not None:
            raise ValueError("phase_d4_replay_source_requires_schema_v2")
        return self

    @model_serializer(mode="wrap")
    def _serialize_versioned_replay_source(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        """Keep the old wire shape for outcome bases before schema 2.0."""
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("stress_outcome_basis_serializer_must_return_object")
        if self.schema_version != _STRESS_OUTCOME_BASIS_D4_SCHEMA_VERSION:
            payload.pop("phase_d4_replay_source_ref", None)
        return payload


class StressScoreComponent(BaseModel):
    """Reference to one immutable finite-scenario outcome basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_id: str = Field(min_length=1)
    score_profile: Literal["finite_binary_scenario_v1"]
    outcome_basis_ref: ArtifactRef


@dataclass(frozen=True)
class _ObservedStressAccounting:
    """Fresh source-row accounting, independent of protected score admission."""

    attempted: int
    finite_evaluated: int
    violated_scenarios: int
    unknown_or_nonfinite: int
    planned_scenarios: int
    complete: bool


class StressScoreResolution(BaseModel):
    """Freshly recomputed finite outcome status and score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    _vulnerability_projection: list[Vulnerability] | None = PrivateAttr(default=None)
    _observed_accounting: _ObservedStressAccounting | None = PrivateAttr(default=None)

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
    case_truth_required: bool | None = None
    case_truth_status: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ] = "not_established"
    case_truth_reason: str | None = None

    @property
    def observed_sample_assessment(self) -> dict[str, Any] | None:
        """Project fresh finite-sample accounting without granting score authority."""
        accounting = self._observed_accounting
        if accounting is None:
            return None
        finite = accounting.finite_evaluated
        return {
            "status": "complete" if accounting.complete else "partial",
            "score_scope": "observed_finite_scenarios",
            "observed_fraction": (
                (finite - accounting.violated_scenarios) / finite if finite else None
            ),
            "attempted": accounting.attempted,
            "finite_evaluated": finite,
            "violated_scenarios": accounting.violated_scenarios,
            "unknown_or_nonfinite": accounting.unknown_or_nonfinite,
            "planned_scenarios": accounting.planned_scenarios,
            "completeness": accounting.complete,
            "population_probability": "not_established",
            "model_uncertainty": "not_established",
            "predicate_status": "recomputed",
            "admission_status": self.status,
            "limitation": self.reason_code if self.status != "available" else None,
        }


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


def load_selected_stress_outcome_basis(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> tuple[StressOutcomeBasis, ArtifactManifest]:
    """Load an outcome basis from its exact selected Core JSON profile."""
    return _load_selected_model(
        store,
        ref,
        StressOutcomeBasis,
        expected_kind=_STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
        expected_schema_name=_STRESS_OUTCOME_BASIS_SCHEMA_NAME,
        expected_schema_version=lambda item: (
            _STRESS_OUTCOME_BASIS_D4_SCHEMA_VERSION
            if item.schema_version == _STRESS_OUTCOME_BASIS_D4_SCHEMA_VERSION
            else _STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION
            if item.schema_version == _STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION
            else _STRESS_OUTCOME_BASIS_SCHEMA_VERSION
        ),
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
    if len(basis.outcomes) > len(planned_samples):
        return _resolution("invalid", component_ids, "plan_outcome_sample_count_mismatch")

    selected_rule: tuple[str, str, str] | None = None
    replayed_vulnerabilities: list[Vulnerability] = []
    for sample, outcome in zip(planned_samples[: len(basis.outcomes)], basis.outcomes, strict=True):
        expected_parameters = {
            parameter.name: float(value)
            for parameter, value in zip(plan.parameter_specs, sample, strict=True)
        }
        if outcome.parameter_values != expected_parameters:
            return _resolution("invalid", component_ids, "plan_parameter_values_mismatch")
        if outcome.status not in {"passed", "failed"}:
            continue
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
    case_truth_required: bool | None = None,
    case_truth_status="not_established",
    case_truth_reason: str | None = None,
    observed_accounting: _ObservedStressAccounting | None = None,
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
        case_truth_required=case_truth_required,
        case_truth_status=case_truth_status,
        case_truth_reason=case_truth_reason,
    )
    resolution._vulnerability_projection = vulnerability_projection
    resolution._observed_accounting = observed_accounting
    return resolution


def resolve_stress_score_components(
    store,
    components: list[StressScoreComponent],
    *,
    expected_candidate_ref: ArtifactRef | None,
    expected_run_id: str | None = None,
    expected_selection_evaluation_ref: ArtifactRef | None = None,
    expected_phase_d4_roster: PhaseD4SuiteRoster | None = None,
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
    if expected_phase_d4_roster is not None:
        try:
            from polisyos.scientist.methods.backtesting.phase_d4_source import (
                revalidate_phase_d4_suite_roster,
            )

            expected_phase_d4_roster = revalidate_phase_d4_suite_roster(
                store,
                expected_phase_d4_roster,
            )
        except Exception:
            return _resolution(
                "invalid",
                component_ids,
                "phase_d4_selected_roster_invalid",
                case_truth_required=True,
            )
        if (
            expected_candidate_ref is None
            or not _same_artifact(expected_phase_d4_roster.candidate_ref, expected_candidate_ref)
            or expected_selection_evaluation_ref is None
            or not _same_artifact(
                expected_phase_d4_roster.selection_evaluation_ref,
                expected_selection_evaluation_ref,
            )
            or expected_run_id != expected_phase_d4_roster.run_id
        ):
            return _resolution(
                "unbound",
                component_ids,
                "phase_d4_selected_roster_context_missing_or_mismatched",
                case_truth_required=bool(expected_phase_d4_roster.suites),
            )
    if not components:
        if expected_phase_d4_roster is not None and expected_phase_d4_roster.suites:
            return _resolution(
                "partial",
                [],
                "phase_d4_selected_roster_component_missing",
                case_truth_required=True,
            )
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
    attempted = finite = violated = unknown = planned = 0
    complete = True
    accounting_available = True
    incomplete: tuple[Literal["partial", "invalid"], str] | None = None
    projected_vulnerabilities: list[Vulnerability] = []
    selected_intent_unbound: StressScoreResolution | None = None
    case_truth_required: bool | None = (
        True if expected_phase_d4_roster is not None and expected_phase_d4_roster.suites else None
    )
    resolved_d4_suites: dict[str, tuple[str, ArtifactRef]] = {}
    selected_d4_suites = (
        {item.suite_id: item for item in expected_phase_d4_roster.suites}
        if expected_phase_d4_roster is not None
        else {}
    )
    d4_case_truth_recomputed = True
    d4_case_truth_reason = "phase_d4_case_rows_recomputed"
    for component in components:
        if component.outcome_basis_ref.manifest_profile_sha256 is None:
            return _resolution("unbound", component_ids, "outcome_basis_profile_missing")
        try:
            basis, basis_manifest = load_selected_stress_outcome_basis(
                store,
                component.outcome_basis_ref,
            )
        except Exception:
            return _resolution("invalid", component_ids, "outcome_basis_unreadable")
        case_truth_required = basis.source_kind == "phase_d4_suite" or case_truth_required is True
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
            accounting_available = accounting_available and plan.vulnerability_threshold is not None
            if basis.expected_count != expected_count:
                return _resolution("invalid", component_ids, "plan_denominator_mismatch")
            if basis.expected_scenario_ids != [f"initial:{i}" for i in range(expected_count)]:
                return _resolution("invalid", component_ids, "plan_occurrence_roster_mismatch")
            actual_scenario_ids = [item.scenario_id for item in basis.outcomes]
            if actual_scenario_ids != basis.expected_scenario_ids[: len(actual_scenario_ids)]:
                return _resolution("invalid", component_ids, "plan_outcome_roster_mismatch")
        else:
            case_truth_required = True
            if expected_phase_d4_roster is None:
                return _resolution(
                    "unbound",
                    component_ids,
                    "phase_d4_selected_roster_missing",
                    case_truth_required=True,
                )
            if basis.suite_id is None or basis.suite_id not in selected_d4_suites:
                return _resolution(
                    "invalid",
                    component_ids,
                    "phase_d4_suite_outside_selected_roster",
                    case_truth_required=True,
                )
            if basis.suite_id in resolved_d4_suites:
                return _resolution(
                    "invalid",
                    component_ids,
                    "duplicate_phase_d4_typed_suite",
                    case_truth_required=True,
                )
            selected_suite = selected_d4_suites[basis.suite_id]
            if (
                basis.benchmark_evaluation_ref is None
                or basis.suite_version != selected_suite.suite_version
                or not _same_artifact(
                    basis.benchmark_evaluation_ref,
                    selected_suite.benchmark_evaluation_ref,
                )
            ):
                return _resolution(
                    "invalid",
                    component_ids,
                    "phase_d4_selected_suite_evaluation_mismatch",
                    case_truth_required=True,
                )
            resolved_d4_suites[basis.suite_id] = (
                basis.suite_version,
                basis.benchmark_evaluation_ref,
            )
            if basis.schema_version not in {
                _STRESS_OUTCOME_BASIS_SCHEMA_VERSION,
                _STRESS_OUTCOME_BASIS_D4_SCHEMA_VERSION,
            }:
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

            replay_source_ref = basis.phase_d4_replay_source_ref
            if basis.schema_version == _STRESS_OUTCOME_BASIS_D4_SCHEMA_VERSION:
                if replay_source_ref is None:
                    return _resolution(
                        "invalid", component_ids, "phase_d4_replay_source_missing_from_v2_basis"
                    )
                if not _same_artifact(replay_source_ref, selected_suite.replay_source_ref):
                    return _resolution(
                        "invalid",
                        component_ids,
                        "phase_d4_selected_replay_source_mismatch",
                        case_truth_required=True,
                    )
                if not (
                    _manifest_has_input(
                        basis_manifest, replay_source_ref, role="phase_d4_replay_source"
                    )
                    and _manifest_has_input(
                        evaluation_manifest, replay_source_ref, role="phase_d4_replay_source"
                    )
                ):
                    return _resolution(
                        "invalid", component_ids, "phase_d4_replay_source_lineage_mismatch"
                    )
                try:
                    from polisyos.scientist.methods.backtesting.phase_d4_source import (
                        PHASE_D4_SELECTION_INPUT_ROLE,
                        load_selected_phase_d4_replay_source,
                        replay_phase_d4_suite,
                    )

                    source, _source_manifest = load_selected_phase_d4_replay_source(
                        store, replay_source_ref
                    )
                    if expected_selection_evaluation_ref is None:
                        return _resolution(
                            "unbound",
                            component_ids,
                            "phase_d4_selected_selection_context_missing",
                        )
                    if not _same_artifact(
                        source.selection_evaluation_ref,
                        expected_selection_evaluation_ref,
                    ):
                        return _resolution(
                            "invalid",
                            component_ids,
                            "phase_d4_selected_selection_context_mismatch",
                        )
                    if not (
                        _manifest_has_input(
                            basis_manifest,
                            source.selection_evaluation_ref,
                            role=PHASE_D4_SELECTION_INPUT_ROLE,
                        )
                        and _manifest_has_input(
                            evaluation_manifest,
                            source.selection_evaluation_ref,
                            role=PHASE_D4_SELECTION_INPUT_ROLE,
                        )
                    ):
                        return _resolution(
                            "invalid", component_ids, "phase_d4_selection_lineage_mismatch"
                        )
                    replayed = replay_phase_d4_suite(
                        store,
                        source_ref=replay_source_ref,
                        expected_candidate_ref=expected_candidate_ref,
                        expected_selection_evaluation_ref=expected_selection_evaluation_ref,
                        expected_loop_id=evaluation.loop_id,
                        expected_suite_id=basis.suite_id,
                        expected_suite_version=basis.suite_version,
                        expected_run_id=expected_run_id,
                    )
                except Exception:
                    return _resolution(
                        "invalid", component_ids, "phase_d4_case_source_replay_failed"
                    )
                expected_rows = [
                    item.model_dump(mode="json") for item in replayed.stress_outcome_basis.outcomes
                ]
                actual_rows = [item.model_dump(mode="json") for item in basis.outcomes]
                expected_evaluation = replayed.benchmark_evaluation
                if (
                    expected_rows != actual_rows
                    or replayed.stress_outcome_basis.expected_scenario_ids
                    != basis.expected_scenario_ids
                    or replayed.stress_outcome_basis.expected_count != basis.expected_count
                    or replayed.stress_outcome_basis.complete != basis.complete
                    or expected_evaluation.model_dump(mode="json")
                    != evaluation.model_dump(mode="json")
                ):
                    return _resolution(
                        "invalid", component_ids, "phase_d4_case_rows_or_projection_mismatch"
                    )
            else:
                d4_case_truth_recomputed = False
                accounting_available = False
                d4_case_truth_reason = "phase_d4_aggregate_only_source_schema"

        indexes = [item.occurrence_index for item in basis.outcomes]
        if indexes != list(range(len(basis.outcomes))):
            return _resolution("invalid", component_ids, "occurrences_not_ordered")
        if basis.expected_count == 0:
            return _resolution("not_evaluated", component_ids, "zero_expected_denominator")
        if incomplete is None:
            if not basis.complete or len(basis.outcomes) != basis.expected_count:
                incomplete = ("partial", "expected_occurrence_rows_incomplete")
            elif any(item.status == "skipped" for item in basis.outcomes):
                incomplete = ("partial", "skipped_occurrence_present")
            elif any(item.status in {"invalid", "unknown"} for item in basis.outcomes):
                incomplete = ("invalid", "invalid_or_unknown_evaluation_present")
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
                if objective_resolution.status == "unbound" and (
                    (
                        objective_resolution.reason_code
                        == "selected_objective_intent_not_independently_established"
                        and objective_resolution._vulnerability_projection is not None
                    )
                    or (
                        objective_resolution.reason_code == "objective_source_evidence_missing"
                        and not any(item.status in {"passed", "failed"} for item in basis.outcomes)
                    )
                ):
                    projected_vulnerabilities.extend(
                        objective_resolution._vulnerability_projection or []
                    )
                    selected_intent_unbound = objective_resolution
                else:
                    if incomplete is not None:
                        return _resolution(incomplete[0], component_ids, incomplete[1])
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
        attempted += sum(item.status != "skipped" for item in basis.outcomes)
        finite += sum(item.status in {"passed", "failed"} for item in basis.outcomes)
        violated += sum(item.status == "failed" for item in basis.outcomes)
        unknown += sum(item.status in {"invalid", "unknown"} for item in basis.outcomes)
        planned += basis.expected_count
        complete = (
            complete
            and basis.complete
            and len(basis.outcomes) == basis.expected_count
            and all(item.status in {"passed", "failed"} for item in basis.outcomes)
        )

    if expected_phase_d4_roster is not None:
        missing_d4_suites = set(selected_d4_suites) - set(resolved_d4_suites)
        if missing_d4_suites:
            return _resolution(
                "partial",
                component_ids,
                "phase_d4_selected_roster_component_missing",
                score_profile="finite_binary_scenario_v1",
                total_scenarios_evaluated=total,
                passed_count=passed,
                critical_count=critical,
                high_count=high,
                medium_count=medium,
                vulnerability_projection=projected_vulnerabilities,
                case_truth_required=True,
                case_truth_status="not_established",
                case_truth_reason="phase_d4_selected_roster_component_missing",
            )
    accounting = (
        _ObservedStressAccounting(
            attempted=attempted,
            finite_evaluated=finite,
            violated_scenarios=violated,
            unknown_or_nonfinite=unknown,
            planned_scenarios=planned,
            complete=complete,
        )
        if accounting_available
        else None
    )
    if incomplete is not None:
        status, reason = incomplete
        return _resolution(
            status,
            component_ids,
            reason,
            score_profile="finite_binary_scenario_v1",
            total_scenarios_evaluated=total,
            passed_count=passed,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            case_truth_required=case_truth_required,
            observed_accounting=accounting,
        )
    if total == 0:
        return _resolution("not_evaluated", component_ids, "zero_observed_denominator")
    if selected_intent_unbound is not None:
        resolution = _resolution(
            "unbound",
            component_ids,
            "selected_objective_intent_not_independently_established",
            case_truth_required=case_truth_required,
            score_profile="finite_binary_scenario_v1",
            total_scenarios_evaluated=total,
            passed_count=passed,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            vulnerability_projection=projected_vulnerabilities,
            observed_accounting=accounting,
        )
        return resolution
    if case_truth_required is True and not d4_case_truth_recomputed:
        return _resolution(
            "unbound",
            component_ids,
            "phase_d4_case_truth_not_established",
            score_profile="finite_binary_scenario_v1",
            total_scenarios_evaluated=total,
            passed_count=passed,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            predicate_status="not_established",
            case_truth_required=True,
            case_truth_status="not_established",
            case_truth_reason=d4_case_truth_reason,
            observed_accounting=accounting,
        )
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
        # Aggregate score and per-case truth are separate recomputed predicates.
        predicate_status="recomputed",
        case_truth_required=case_truth_required,
        case_truth_status=("recomputed" if case_truth_required else "not_established"),
        case_truth_reason=d4_case_truth_reason if case_truth_required else None,
    )
    resolution._vulnerability_projection = projected_vulnerabilities
    resolution._observed_accounting = accounting
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
    case_truth_status: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ] = "not_established"
    case_truth_reason: str | None = None
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
    _case_truth_required: bool | None = PrivateAttr(default=None)

    @model_serializer(mode="wrap")
    def _serialize_versioned_case_truth(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        """Keep pre-1.2 report bodies compatible with their declared schema."""
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("stress_test_report_serializer_must_return_object")
        if self.schema_version != "1.2":
            payload.pop("case_truth_status", None)
            payload.pop("case_truth_reason", None)
        return payload

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
            and self._case_truth_required is not None
            and (not self._case_truth_required or self.case_truth_status == "recomputed")
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
    expected_run_id: str | None = None,
    expected_selection_evaluation_ref: ArtifactRef | None = None,
    expected_phase_d4_roster: PhaseD4SuiteRoster | None = None,
    require_phase_d4_roster: bool = False,
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
        if report.schema_version not in {"1.1", "1.2"}:
            return report, _resolution(
                "legacy_unknown", [], "legacy_report_without_occurrence_basis"
            )
        return report, _resolution("unbound", [], "stress_report_profile_missing")
    try:
        report, report_manifest = _load_stress_report_source(store, report_ref)
    except Exception:
        report = StressTestReport(report_id="unreadable-stress-report", schema_version="1.0")
        return report, _resolution("invalid", [], "stress_report_unreadable")
    component_ids = [item.component_id for item in report.score_components]
    if require_phase_d4_roster and expected_phase_d4_roster is None:
        return report, _resolution(
            "unbound",
            component_ids,
            "phase_d4_selected_roster_not_established",
            case_truth_required=True,
        )
    if expected_phase_d4_roster is not None:
        try:
            from polisyos.scientist.methods.backtesting.phase_d4_source import (
                PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                revalidate_phase_d4_suite_roster,
            )

            expected_phase_d4_roster = revalidate_phase_d4_suite_roster(
                store,
                expected_phase_d4_roster,
            )
            expected_selected_inputs = [
                input_ref_from_artifact_ref(
                    ref,
                    role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                ).model_dump_json()
                for ref in expected_phase_d4_roster.suite_evaluation_refs
            ]
            actual_selected_inputs = [
                item.model_dump_json()
                for item in report_manifest.inputs
                if item.role == PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE
            ]
            if actual_selected_inputs != expected_selected_inputs:
                return report, _resolution(
                    "invalid",
                    component_ids,
                    "stress_report_selected_phase_d4_roster_lineage_mismatch",
                    case_truth_required=bool(expected_phase_d4_roster.suites),
                )
        except Exception:
            return report, _resolution(
                "invalid",
                component_ids,
                "phase_d4_selected_roster_invalid",
                case_truth_required=True,
            )
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
    if report.schema_version not in {"1.1", "1.2"}:
        return report, _resolution("legacy_unknown", [], "legacy_report_without_occurrence_basis")
    if report.score_profile in {"continuous_severity_v1", "mixed_unscored"}:
        if report.score_components:
            component_resolution = resolve_stress_score_components(
                store,
                report.score_components,
                expected_candidate_ref=expected_candidate_ref,
                expected_run_id=expected_run_id,
                expected_selection_evaluation_ref=expected_selection_evaluation_ref,
                expected_phase_d4_roster=expected_phase_d4_roster,
            )
            report._case_truth_required = component_resolution.case_truth_required
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
        if expected_phase_d4_roster is not None and expected_phase_d4_roster.suites:
            report._case_truth_required = True
            return report, _resolution(
                "partial",
                [],
                "phase_d4_selected_roster_component_missing",
                case_truth_required=True,
                case_truth_status="not_established",
                case_truth_reason="phase_d4_selected_roster_component_missing",
            )
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
        store,
        report.score_components,
        expected_candidate_ref=expected_candidate_ref,
        expected_run_id=expected_run_id,
        expected_selection_evaluation_ref=expected_selection_evaluation_ref,
        expected_phase_d4_roster=expected_phase_d4_roster,
    )
    report._case_truth_required = resolution.case_truth_required
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
        and (
            report.schema_version != "1.2"
            or (
                report.case_truth_status == resolution.case_truth_status
                and report.case_truth_reason == resolution.case_truth_reason
            )
        )
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
