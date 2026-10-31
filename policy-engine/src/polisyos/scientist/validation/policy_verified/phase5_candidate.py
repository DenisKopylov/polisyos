"""Selected, candidate-only Phase-5 evaluation and its exact source edges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    CoreArtifactOwnerProfile,
    InputRef,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    require_return_selected_profile_writer,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.search.judge_stack import (
    CANDIDATE_JUDGE_VERDICT_KIND,
    load_candidate_judge_verdict,
)
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdEntry

if TYPE_CHECKING:
    from polisyos.scientist.governance.report import GovernanceReport
    from polisyos.scientist.methods.search.judge_stack import JudgeVerdict
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
    from polisyos.scientist.validation.policy_verified.models import VerifiedPolicyReport

_KIND = "scientist.policy_phase5_candidate_assessment"
_SCHEMA = "polisyos.scientist.policy_verified.Phase5CandidateAssessment"
_OWNER = CoreArtifactOwnerProfile(
    kind=_KIND,
    media_type="application/json",
    schema_variants=(SchemaInfo(name=_SCHEMA, version="1.0"),),
    payload_schema_version_by_manifest=(((_SCHEMA, "1.0"), "1.0"),),
)


class Phase5ThresholdUse(BaseModel):
    """One actual judge decision-path threshold lookup."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    judge_name: str | None
    metric_name: str
    threshold_tier: Literal["warning", "blocker"]
    scope: tuple[tuple[str, str | None], ...]
    source: Literal["registry", "fallback", "missing"]
    selected_entry: JudgeThresholdEntry | None
    fallback_rule: str | None
    fallback_value: float | None
    observed_value: float


class Phase5ValidationProfileUse(BaseModel):
    """One validation profile actually passed to a judge."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    level: str
    pass_ids: tuple[str, ...]
    thresholds: tuple[tuple[str, float], ...]
    short_circuit_on_blocker: bool


class Phase5CandidateAssessment(BaseModel):
    """A diagnostic attempt, not a completed or publication-grade assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    body_ref: ArtifactRef
    candidate_ref: ArtifactRef
    governance_ref: ArtifactRef
    threshold_basis_ref: ArtifactRef
    judge_verdict_ref: ArtifactRef
    selected_input_ref: ArtifactRef
    selected_attempt_ref: ArtifactRef
    threshold_uses: tuple[Phase5ThresholdUse, ...] = ()
    validation_profiles: tuple[Phase5ValidationProfileUse, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    status: Literal["candidate_diagnostic"] = "candidate_diagnostic"
    publishable: Literal[False] = False
    option_program_correspondence: Literal["not_established"] = "not_established"

    @field_validator(
        "body_ref",
        "candidate_ref",
        "governance_ref",
        "threshold_basis_ref",
        "judge_verdict_ref",
        "selected_input_ref",
        "selected_attempt_ref",
        mode="before",
    )
    @classmethod
    def _normalize_reference_model(cls, value: object) -> object:
        """Preserve complete identities across typed-ref and Core-ref readback."""
        return value.model_dump(mode="python") if isinstance(value, ArtifactRef) else value

    @model_validator(mode="after")
    def _require_selected_profiles(self) -> Phase5CandidateAssessment:
        for _role, ref in _source_refs(self):
            if ref.manifest_profile_sha256 is None:
                raise ValueError("phase5_candidate_source_profile_not_established")
        if self.judge_verdict_ref.kind != CANDIDATE_JUDGE_VERDICT_KIND:
            raise ValueError("phase5_candidate_verdict_kind_invalid")
        return self


@dataclass(frozen=True)
class Phase5JudgeEvaluation:
    """Candidate-only judge output with the exact observed threshold basis."""

    verdict: JudgeVerdict | None = None
    reason: str | None = None
    threshold_basis_ref: ArtifactRef | None = None
    threshold_basis_status: Literal["current_at_evaluation", "stale", "not_established"] = (
        "not_established"
    )
    threshold_uses: tuple[Phase5ThresholdUse, ...] = ()
    validation_profiles: tuple[Phase5ValidationProfileUse, ...] = ()


def evaluate_phase5_candidate(
    store: ArtifactStore,
    *,
    candidate: PolicyCandidateSchema,
    governance_report: GovernanceReport,
    run_id: str,
    candidate_ref: ArtifactRef | None = None,
    body: VerifiedPolicyReport | None = None,
) -> Phase5JudgeEvaluation:
    """Evaluate the real six judges as a limited candidate diagnostic.

    Callers must separately establish source and Engine attempt currentness.
    Threshold currentness is checked before and after this evaluation, while
    threshold coverage and issuer authority remain separate questions.
    """
    from polisyos.scientist.methods.search.judge_stack import (
        JudgeInputBundle,
        JudgeStack,
        capture_judge_validation_profiles,
    )
    from polisyos.scientist.methods.search.judge_threshold_basis import (
        capture_judge_threshold_basis,
        resolve_judge_threshold_basis,
        selected_judge_threshold_registry,
    )
    from polisyos.scientist.methods.search.judge_thresholds import (
        capture_judge_threshold_requirements,
    )

    try:
        live_registry = selected_judge_threshold_registry()
        frozen_registry, basis_ref = capture_judge_threshold_basis(store, live_registry)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        reason = str(exc)
        if reason not in {
            "threshold_registry_not_established",
            "threshold_registry_changed",
            "threshold_registry_owner_not_established",
        }:
            reason = "threshold_registry_invalid"
        return Phase5JudgeEvaluation(reason=f"phase5_{reason}")

    body_state = (
        {"verified_claims": [claim.model_dump(mode="json") for claim in body.verified_legal_basis]}
        if body is not None and body.verified_legal_basis
        else {}
    )
    bundle = JudgeInputBundle(
        candidate=candidate,
        candidate_ref=candidate_ref,
        governance_report=governance_report,
        run_id=run_id,
        evaluation_promotable_source=False,
        state=body_state,
    )
    try:
        with (
            capture_judge_threshold_requirements() as requirements,
            capture_judge_validation_profiles() as profiles,
        ):
            verdict = JudgeStack(
                store=store, threshold_registry=frozen_registry
            ).evaluate_phase5_preflight(bundle)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return Phase5JudgeEvaluation(
            reason=f"phase5_candidate_judge_evaluation_failed:{type(exc).__name__}",
            threshold_basis_ref=basis_ref,
        )
    admission = resolve_judge_threshold_basis(store, basis_ref, live_registry)
    if admission.status != "current":
        return Phase5JudgeEvaluation(
            reason=(
                "phase5_threshold_registry_changed"
                if admission.status == "stale"
                else "phase5_threshold_registry_invalid"
            ),
            threshold_basis_ref=basis_ref,
            threshold_basis_status="stale" if admission.status == "stale" else "not_established",
        )
    uses = tuple(
        Phase5ThresholdUse(
            judge_name=item.judge_name,
            metric_name=item.metric_name,
            threshold_tier=item.threshold_tier,
            scope=item.scope,
            source=item.source,
            selected_entry=item.selected_entry,
            fallback_rule=item.fallback_rule,
            fallback_value=item.fallback_value,
            observed_value=item.observed_value,
        )
        for item in requirements
    )
    profile_uses = tuple(
        Phase5ValidationProfileUse(
            level=item.level,
            pass_ids=item.pass_ids,
            thresholds=item.thresholds,
            short_circuit_on_blocker=item.short_circuit_on_blocker,
        )
        for item in profiles
    )
    missing = sorted(
        {
            f"{item.judge_name or 'unknown'}:{item.metric_name}:{item.threshold_tier}"
            for item in uses
            if item.source == "missing"
        }
    )
    return Phase5JudgeEvaluation(
        verdict=verdict,
        reason=(
            "phase5_threshold_requirement_not_established:" + ",".join(missing) if missing else None
        ),
        threshold_basis_ref=basis_ref,
        threshold_basis_status="current_at_evaluation",
        threshold_uses=uses,
        validation_profiles=profile_uses,
    )


def _source_refs(assessment: Phase5CandidateAssessment) -> tuple[tuple[str, ArtifactRef], ...]:
    return (
        ("verified_body", assessment.body_ref),
        ("policy_candidate", assessment.candidate_ref),
        ("governance_assessment", assessment.governance_ref),
        ("threshold_basis", assessment.threshold_basis_ref),
        ("judge_verdict", assessment.judge_verdict_ref),
        ("selected_input", assessment.selected_input_ref),
        ("selected_attempt", assessment.selected_attempt_ref),
    )


def _source_inputs(assessment: Phase5CandidateAssessment) -> list[InputRef]:
    return [input_ref_from_artifact_ref(ref, role=role) for role, ref in _source_refs(assessment)]


def _validate_selected_sources(store: ArtifactStore, assessment: Phase5CandidateAssessment) -> None:
    from polisyos.scientist.governance.report import load_governance_report_artifact
    from polisyos.scientist.methods.search.judge_threshold_basis import load_judge_threshold_basis
    from polisyos.scientist.policy_design.schema import load_policy_candidate_schema
    from polisyos.scientist.validation.policy_verified.models import load_verified_policy_body

    load_verified_policy_body(store, assessment.body_ref)
    load_policy_candidate_schema(store, assessment.candidate_ref)
    load_governance_report_artifact(store, assessment.governance_ref)
    load_judge_threshold_basis(store, assessment.threshold_basis_ref)
    load_candidate_judge_verdict(store, assessment.judge_verdict_ref)
    expected_judge_inputs = [
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in _source_refs(assessment)
        if role != "judge_verdict"
    ]
    if store.get_manifest(assessment.judge_verdict_ref).inputs != expected_judge_inputs:
        raise ValueError("phase5_candidate_verdict_source_edges_mismatch")


def persist_phase5_candidate_assessment(
    store: ArtifactStore, assessment: Phase5CandidateAssessment
) -> ArtifactRef:
    """Persist the selected diagnostic and its complete typed lineage.

    This writer does not establish an Engine attempt or publication authority.
    """
    assessment = Phase5CandidateAssessment.model_validate(assessment.model_dump(mode="python"))
    _validate_selected_sources(store, assessment)
    require_return_selected_profile_writer(store, "put_json")
    ref = store.put_json(
        assessment,
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA, version="1.0"),
            inputs=_source_inputs(assessment),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    if ref.manifest_profile_sha256 is None:
        raise ValueError("phase5_candidate_profile_not_established")
    return ref


def load_phase5_candidate_assessment(
    store: ArtifactStore, ref: ArtifactRef
) -> Phase5CandidateAssessment:
    """Read an owner-profiled diagnostic and verify its complete source edges.

    Engine producer currentness remains a separate required admission.
    """
    if ref.manifest_profile_sha256 is None:
        raise ValueError("phase5_candidate_profile_not_established")
    assessment = validate_owned_core_model_json_artifact(
        Phase5CandidateAssessment, store, ref, expected_owner=_OWNER
    ).value
    if store.get_manifest(ref).inputs != _source_inputs(assessment):
        raise ValueError("phase5_candidate_source_edges_mismatch")
    _validate_selected_sources(store, assessment)
    return assessment


__all__ = [
    "Phase5CandidateAssessment",
    "Phase5JudgeEvaluation",
    "Phase5ThresholdUse",
    "Phase5ValidationProfileUse",
    "load_phase5_candidate_assessment",
    "evaluate_phase5_candidate",
    "persist_phase5_candidate_assessment",
]
