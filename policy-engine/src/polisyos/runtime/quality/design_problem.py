"""Canonical design-problem bridge over existing PolicyOS problem surfaces."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.kernel.time_semantics import TimeSemantics

DESIGN_PROBLEM_SCHEMA_VERSION = "policyos.runtime.design_problem.v1"
DESIGN_PROBLEM_PROJECTION_SCHEMA_VERSION = "policyos.runtime.design_problem.projection.v1"
_DESIGN_PROBLEM_PROJECTION_KEY = "design_problem_projection"
_DESIGN_PROBLEM_PROJECTION_NOTE_PREFIX = "design_problem_projection:"
_PROJECTION_LOSSY_FIELDS: dict[str, tuple[str, ...]] = {
    "policy_intent_envelope": (),
    "scientist_problem_frame": (),
    "ir_problem_frame": (),
    "model_spec": (),
    "policy_request_frame": (),
}


class DesignProblemAuthorityError(ValueError):
    """Fail-closed DesignProblem authority or admissibility violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Base strict model for DesignProblem subcontracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class NLProvenance(_StrictModel):
    """Record raw natural-language request provenance.

    Attributes:
        raw_request: Original user request text before producer interpretation.
        source_surface: Runtime or API surface that captured the request.
        source_context: Structured context supplied at capture time.
    """

    raw_request: str = Field(..., min_length=1)
    source_surface: str = Field(..., min_length=1)
    source_context: dict[str, Any] = Field(default_factory=dict)


class AuthorityProfile(_StrictModel):
    """Record requester authority and mandate context for the problem."""

    requester_authority: str = Field(..., min_length=1)
    requested_authority_level: Literal["research", "governed", "production"]
    mandate: str = Field(..., min_length=1)
    authority_refs: list[str] = Field(default_factory=list)


class JurisdictionTimeSemantics(_StrictModel):
    """Bind jurisdiction and time-role semantics for the design problem."""

    region: str = Field(..., min_length=1)
    valid_time: str = Field(..., min_length=1)
    as_of: str = Field(..., min_length=1)
    policy_time: str = Field(..., min_length=1)
    data_time: str = Field(..., min_length=1)
    time_semantics: TimeSemantics | None = None

    @field_validator("time_semantics", mode="before")
    @classmethod
    def _validate_time_semantics(cls, value: object) -> TimeSemantics | None:
        """Validate through the existing IR ModelSpec time-semantics owner."""

        if value is None or isinstance(value, TimeSemantics):
            return value
        return TimeSemantics.model_validate(value)


class DesignObjective(_StrictModel):
    """Represent one objective reused by generator and IR projections."""

    objective_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1)
    metric_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    direction: Literal["maximize", "minimize", "maintain_range"] = "maximize"


class DesignConstraint(_StrictModel):
    """Represent a constraint with explicit admissibility provenance."""

    constraint_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1)
    hard: bool = True
    admissibility_basis: str = Field(..., min_length=1)
    source_text: str | None = None
    evidence_ref: str | None = None


class DesignStakeholder(_StrictModel):
    """Represent an affected stakeholder shared across projections."""

    stakeholder_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1)
    role: str | None = None


class OutcomeOfInterest(_StrictModel):
    """Represent the target variable the value gate will estimate."""

    target_variable: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    metric_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    estimand: str = Field(..., min_length=1)
    direction: Literal["maximize", "minimize", "maintain_range"] = "maximize"


class CandidateLever(_StrictModel):
    """Represent one candidate operator/instrument slot for atom binding."""

    lever_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    operator_kind: str = Field(..., min_length=1)
    instrument: str = Field(..., min_length=1)
    target_slot: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")


class CandidateLeverSpace(_StrictModel):
    """Represent the allowed lever/operator space for candidate generation."""

    allowed_operator_kinds: list[str] = Field(default_factory=list)
    candidate_levers: list[CandidateLever] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_levers(self) -> CandidateLeverSpace:
        """Validate lever/operator consistency."""

        if not self.candidate_levers:
            raise ValueError("candidate_lever_space_empty")
        allowed = {item.strip() for item in self.allowed_operator_kinds if item.strip()}
        if not allowed:
            raise ValueError("candidate_lever_space_allowed_operator_kinds_empty")
        unknown = [
            lever.operator_kind
            for lever in self.candidate_levers
            if lever.operator_kind not in allowed
        ]
        if unknown:
            raise ValueError(f"candidate_lever_space_operator_not_allowed:{','.join(unknown)}")
        return self


class EvidenceNeed(_StrictModel):
    """Represent one grounding or acquisition demand."""

    need_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    question: str = Field(..., min_length=1)
    required_for: str = Field(..., min_length=1)
    status: Literal["required", "satisfied", "blocked"] = "required"
    source_hint: str | None = None
    artifact_ref: str | None = None


class EvidenceAcquisitionNeeds(_StrictModel):
    """Represent grounding demands carried into GY-N3/GY-N7."""

    needs: list[EvidenceNeed] = Field(default_factory=list)


class DesignProblem(_StrictModel):
    """Bridge one policy-design problem across existing PolicyOS owners.

    ``DesignProblem`` is the canonical request/problem bridge for the generation
    cycle. It reuses ``PolicyIntentEnvelope`` request semantics, projects to the
    Scientist agent ``ProblemFrame``, projects to IR governance ``ProblemFrame``,
    keeps the verified ``PolicyRequestFrame`` as a legal sub-projection, and
    carries ``ModelSpec`` time semantics by reference instead of creating a
    parallel ontology.

    Attributes:
        design_problem_id: Stable problem id used by projections.
        nl_provenance: Raw NL request and capture context.
        authority_profile: Requester authority and mandate boundaries.
        jurisdiction_time: Jurisdiction and valid/as-of/policy/data time roles.
        objectives: Formal objective candidates for generator and IR projection.
        constraints: Constraints admitted only with request, authority, or
            producer-evidence support.
        stakeholders: Affected actor set.
        outcome_of_interest: Target variable and estimand for value gating.
        candidate_lever_space: Operator/instrument space for atom binding.
        evidence_acquisition_needs: Grounding and acquisition demands.
        model_spec_ref: Optional persisted ModelSpec reference.
        ir_problem_frame_ref: Optional persisted IR ProblemFrame reference.
        policy_request_frame_ref: Optional verified-policy sub-projection ref.
        runtime_hints: Runtime-only projection hints for current cycle adapters.
    """

    schema_version: str = DESIGN_PROBLEM_SCHEMA_VERSION
    design_problem_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    problem_statement: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    nl_provenance: NLProvenance
    authority_profile: AuthorityProfile
    jurisdiction_time: JurisdictionTimeSemantics
    objectives: list[DesignObjective] = Field(default_factory=list)
    constraints: list[DesignConstraint] = Field(default_factory=list)
    stakeholders: list[DesignStakeholder] = Field(default_factory=list)
    outcome_of_interest: OutcomeOfInterest
    candidate_lever_space: CandidateLeverSpace
    evidence_acquisition_needs: EvidenceAcquisitionNeeds
    model_spec_ref: str | None = Field(None, pattern=r"^sha256:[a-f0-9]{64}$")
    ir_problem_frame_ref: str | None = None
    policy_request_frame_ref: str | None = None
    runtime_hints: dict[str, Any] = Field(default_factory=dict)
    _projection_lossy_fields: ClassVar[dict[str, tuple[str, ...]]] = _PROJECTION_LOSSY_FIELDS

    @field_validator("objectives")
    @classmethod
    def _objectives_required(cls, value: list[DesignObjective]) -> list[DesignObjective]:
        if not value:
            raise ValueError("design_problem_objectives_empty")
        return value

    @field_validator("stakeholders")
    @classmethod
    def _stakeholders_required(cls, value: list[DesignStakeholder]) -> list[DesignStakeholder]:
        if not value:
            raise ValueError("design_problem_stakeholders_empty")
        return value

    @model_validator(mode="after")
    def validate_admissibility(self) -> DesignProblem:
        """Validate structural admissibility fields without granting authority."""

        if not self.objectives:
            raise ValueError("design_problem_objectives_empty")
        if not self.stakeholders:
            raise ValueError("design_problem_stakeholders_empty")
        for constraint in self.constraints:
            if constraint.admissibility_basis not in {
                "request_text",
                "authority_profile",
                "producer_evidence",
            }:
                raise ValueError(
                    f"invented_admissibility:{constraint.constraint_id}:unsupported_basis"
                )
            if constraint.admissibility_basis == "producer_evidence":
                if not constraint.evidence_ref:
                    raise ValueError(
                        f"invented_admissibility:{constraint.constraint_id}:missing_evidence_ref"
                    )
                continue
            if not constraint.source_text:
                raise ValueError(
                    f"invented_admissibility:{constraint.constraint_id}:missing_source_text"
                )
        return self

    @classmethod
    def projection_lossy_fields(cls, owner: str) -> tuple[str, ...]:
        """Return declared lossy fields for a DesignProblem projection owner."""

        return cls._projection_lossy_fields.get(owner, ())

    def projection_payload(self, *, owner: str) -> dict[str, Any]:
        """Return the canonical no-loss DesignProblem projection sidecar."""

        return {
            "schema_version": DESIGN_PROBLEM_PROJECTION_SCHEMA_VERSION,
            "owner": owner,
            "lossy_fields": list(self.projection_lossy_fields(owner)),
            "design_problem": self.model_dump(mode="json"),
        }

    @classmethod
    def _from_projection_payload(cls, payload: object) -> DesignProblem | None:
        if not isinstance(payload, dict):
            return None
        if payload.get("schema_version") == DESIGN_PROBLEM_PROJECTION_SCHEMA_VERSION:
            design_problem = payload.get("design_problem")
            if isinstance(design_problem, dict):
                return cls.model_validate(design_problem)
            return None
        if payload.get("schema_version") == DESIGN_PROBLEM_SCHEMA_VERSION:
            return cls.model_validate(payload)
        return None

    @classmethod
    def _from_projection_notes(cls, notes: object) -> DesignProblem | None:
        if not isinstance(notes, list):
            return None
        for note in notes:
            if not isinstance(note, str):
                continue
            if not note.startswith(_DESIGN_PROBLEM_PROJECTION_NOTE_PREFIX):
                continue
            raw = note.removeprefix(_DESIGN_PROBLEM_PROJECTION_NOTE_PREFIX)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            projected = cls._from_projection_payload(payload)
            if projected is not None:
                return projected
        return None

    def _projection_note(self, *, owner: str) -> str:
        payload = self.projection_payload(owner=owner)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return f"{_DESIGN_PROBLEM_PROJECTION_NOTE_PREFIX}{encoded}"

    @classmethod
    def from_policy_intent_envelope(
        cls,
        envelope: dict[str, Any],
        *,
        raw_request: str,
        outcome_of_interest: dict[str, Any],
        candidate_lever_space: dict[str, Any],
        model_spec_ref: str | None = None,
        runtime_hints: dict[str, Any] | None = None,
    ) -> DesignProblem:
        """Build a DesignProblem from the runtime PolicyIntentEnvelope owner."""

        from polisyos.runtime.quality.assurance_case import validate_policy_intent_envelope

        intent = validate_policy_intent_envelope(envelope)
        projected = cls._from_projection_payload(
            intent.get("authoring_provenance", {}).get(_DESIGN_PROBLEM_PROJECTION_KEY)
        )
        if projected is not None:
            return projected
        objectives = [
            DesignObjective(
                objective_id=_slug_id(text, fallback=f"objective_{index + 1}"),
                description=text,
                metric_id=_slug_id(
                    outcome_of_interest.get("metric_id") or text,
                    fallback=f"metric_{index + 1}",
                ),
                direction=str(outcome_of_interest.get("direction") or "maximize"),
            )
            for index, text in enumerate(intent.get("objectives") or [])
        ] or [
            DesignObjective(
                objective_id="desired_outcome",
                description=str(intent["desired_outcome"]),
                metric_id=_slug_id(outcome_of_interest.get("metric_id"), fallback="outcome"),
                direction=str(outcome_of_interest.get("direction") or "maximize"),
            )
        ]
        constraints = [
            DesignConstraint(
                constraint_id=_slug_id(text, fallback=f"constraint_{index + 1}"),
                description=text,
                hard=True,
                admissibility_basis="request_text",
                source_text=text,
            )
            for index, text in enumerate(intent.get("constraints") or [])
        ]
        stakeholders = [
            DesignStakeholder(
                stakeholder_id=_slug_id(text, fallback=f"stakeholder_{index + 1}"),
                name=text,
                role="affected",
            )
            for index, text in enumerate(intent.get("affected_stakeholders") or [])
        ] or [
            DesignStakeholder(
                stakeholder_id=_slug_id(intent.get("target_population"), fallback="population"),
                name=str(intent.get("target_population") or "target population"),
                role="target_population",
            )
        ]
        evidence_needs = [
            EvidenceNeed(
                need_id=_slug_id(text, fallback=f"evidence_need_{index + 1}"),
                question=text,
                required_for="grounding",
                status="required",
            )
            for index, text in enumerate(intent.get("evidence_expectations") or [])
        ]
        return cls(
            design_problem_id=_slug_id(intent.get("intent_id"), fallback="design_problem"),
            problem_statement=str(intent["policy_problem"]),
            domain=_domain_from_text(intent.get("policy_problem")),
            nl_provenance=NLProvenance(
                raw_request=raw_request,
                source_surface="runtime.policy_intent_envelope",
                source_context={
                    "run_id": intent.get("run_id"),
                    "job_id": intent.get("job_id"),
                    "tenant_id": intent.get("tenant_id"),
                    "intent_id": intent.get("intent_id"),
                },
            ),
            authority_profile=AuthorityProfile(
                requester_authority=str(intent.get("requested_execution_profile") or "research"),
                requested_authority_level=str(intent["requested_authority_level"]),
                mandate=str(
                    intent.get("authoring_provenance", {}).get("mandate")
                    or "runtime captured requester intent"
                ),
            ),
            jurisdiction_time=JurisdictionTimeSemantics(
                region=str(intent["jurisdiction"]),
                valid_time=str(intent["policy_time"]),
                as_of=str(intent.get("generated_at") or intent["policy_time"]),
                policy_time=str(intent["policy_time"]),
                data_time=str(intent["data_time"]),
            ),
            objectives=objectives,
            constraints=constraints,
            stakeholders=stakeholders,
            outcome_of_interest=OutcomeOfInterest.model_validate(outcome_of_interest),
            candidate_lever_space=CandidateLeverSpace.model_validate(candidate_lever_space),
            evidence_acquisition_needs=EvidenceAcquisitionNeeds(needs=evidence_needs),
            model_spec_ref=model_spec_ref,
            runtime_hints=dict(runtime_hints or {}),
        )

    @classmethod
    def from_scientist_problem_frame(
        cls,
        frame: object,
        *,
        authority_profile: dict[str, Any],
        jurisdiction_time: dict[str, Any],
        outcome_of_interest: dict[str, Any],
        candidate_lever_space: dict[str, Any],
        raw_request: str | None = None,
    ) -> DesignProblem:
        """Build a DesignProblem from the Scientist agent ProblemFrame surface."""

        context = getattr(frame, "context", {}) or {}
        if isinstance(context, dict):
            projected = cls._from_projection_payload(context.get(_DESIGN_PROBLEM_PROJECTION_KEY))
            if projected is not None:
                return projected
        return cls(
            design_problem_id=_slug_id(getattr(frame, "frame_id", None), fallback="problem_frame"),
            problem_statement=str(frame.problem_statement),
            domain=str(frame.domain),
            nl_provenance=NLProvenance(
                raw_request=raw_request or str(frame.problem_statement),
                source_surface="scientist.agent.problem_frame",
                source_context={"frame_id": getattr(frame, "frame_id", None)},
            ),
            authority_profile=AuthorityProfile.model_validate(authority_profile),
            jurisdiction_time=JurisdictionTimeSemantics.model_validate(jurisdiction_time),
            objectives=[
                DesignObjective(
                    objective_id=_slug_id(goal, fallback=f"objective_{index + 1}"),
                    description=str(goal),
                    metric_id=_slug_id(goal, fallback=f"metric_{index + 1}"),
                    direction="maximize",
                )
                for index, goal in enumerate(getattr(frame, "goals", ()) or ())
            ],
            constraints=[
                DesignConstraint(
                    constraint_id=_slug_id(text, fallback=f"constraint_{index + 1}"),
                    description=str(text),
                    hard=True,
                    admissibility_basis="request_text",
                    source_text=str(text),
                )
                for index, text in enumerate(getattr(frame, "constraints", ()) or ())
            ],
            stakeholders=[
                DesignStakeholder(
                    stakeholder_id=_slug_id(actor, fallback=f"stakeholder_{index + 1}"),
                    name=str(actor),
                    role="actor",
                )
                for index, actor in enumerate(getattr(frame, "actors", ()) or ())
            ],
            outcome_of_interest=OutcomeOfInterest.model_validate(outcome_of_interest),
            candidate_lever_space=CandidateLeverSpace.model_validate(candidate_lever_space),
            evidence_acquisition_needs=EvidenceAcquisitionNeeds(needs=[]),
        )

    @classmethod
    def from_ir_problem_frame(cls, frame: object) -> DesignProblem:
        """Build a DesignProblem from the IR governance ProblemFrame projection."""

        projected = cls._from_projection_notes(getattr(frame, "notes", None))
        if projected is None:
            raise ValueError("design_problem_projection_missing:ir_problem_frame")
        return projected

    @classmethod
    def from_model_spec(cls, model_spec: object) -> DesignProblem:
        """Build a DesignProblem from the IR ModelSpec projection."""

        projected = cls._from_projection_notes(getattr(model_spec, "notes", None))
        if projected is None:
            raise ValueError("design_problem_projection_missing:model_spec")
        return projected

    @classmethod
    def from_policy_request_frame(
        cls,
        frame: object,
        *,
        authority_profile: dict[str, Any],
        outcome_of_interest: dict[str, Any],
        candidate_lever_space: dict[str, Any],
    ) -> DesignProblem:
        """Build a DesignProblem from the verified PolicyRequestFrame sub-surface."""

        target_context = getattr(frame, "target_context", {}) or {}
        if isinstance(target_context, dict):
            projected = cls._from_projection_payload(
                target_context.get(_DESIGN_PROBLEM_PROJECTION_KEY)
            )
            if projected is not None:
                return projected
        projected = cls._from_projection_notes(getattr(frame, "notes", None))
        if projected is not None:
            return projected
        return cls(
            design_problem_id=_slug_id(
                getattr(frame, "request_id", None),
                fallback="policy_request",
            ),
            problem_statement=str(frame.policy_question),
            domain=str(getattr(frame, "policy_domain", None) or "custom"),
            nl_provenance=NLProvenance(
                raw_request=str(frame.policy_question),
                source_surface="scientist.policy_verified.policy_request_frame",
                source_context={"request_id": getattr(frame, "request_id", None)},
            ),
            authority_profile=AuthorityProfile.model_validate(authority_profile),
            jurisdiction_time=JurisdictionTimeSemantics(
                region=str(getattr(frame, "jurisdiction", None) or "UA"),
                valid_time=str(getattr(frame, "as_of", None) or "unspecified"),
                as_of=str(getattr(frame, "as_of", None) or "unspecified"),
                policy_time=str(getattr(frame, "as_of", None) or "unspecified"),
                data_time=str(getattr(frame, "as_of", None) or "unspecified"),
            ),
            objectives=[
                DesignObjective(
                    objective_id=_slug_id(goal, fallback=f"objective_{index + 1}"),
                    description=str(goal),
                    metric_id=_slug_id(goal, fallback=f"metric_{index + 1}"),
                    direction="maximize",
                )
                for index, goal in enumerate(getattr(frame, "goals", []) or [])
            ],
            constraints=[
                DesignConstraint(
                    constraint_id=_slug_id(text, fallback=f"constraint_{index + 1}"),
                    description=str(text),
                    hard=True,
                    admissibility_basis="request_text",
                    source_text=str(text),
                )
                for index, text in enumerate(getattr(frame, "constraints", []) or [])
            ],
            stakeholders=[
                DesignStakeholder(stakeholder_id="target_context", name="target context")
            ],
            outcome_of_interest=OutcomeOfInterest.model_validate(outcome_of_interest),
            candidate_lever_space=CandidateLeverSpace.model_validate(candidate_lever_space),
            evidence_acquisition_needs=EvidenceAcquisitionNeeds(needs=[]),
        )

    def to_policy_intent_envelope(self) -> dict[str, Any]:
        """Project to the existing runtime PolicyIntentEnvelope surface."""

        from polisyos.runtime.quality.assurance_case import build_policy_intent_envelope

        context = self.nl_provenance.source_context
        return build_policy_intent_envelope(
            intent_id=str(context.get("intent_id") or f"intent_{self.design_problem_id}"),
            run_id=str(context.get("run_id") or f"run_{self.design_problem_id}"),
            job_id=str(context.get("job_id") or f"job_{self.design_problem_id}"),
            tenant_id=str(context.get("tenant_id") or "tenant-default"),
            policy_problem=self.problem_statement,
            desired_outcome="; ".join(item.description for item in self.objectives),
            proposed_intervention="; ".join(
                item.instrument for item in self.candidate_lever_space.candidate_levers
            ),
            jurisdiction=self.jurisdiction_time.region,
            target_population="; ".join(item.name for item in self.stakeholders),
            policy_time=self.jurisdiction_time.policy_time,
            data_time=self.jurisdiction_time.data_time,
            requester_preferred_conclusion=None,
            requested_authority_level=self.authority_profile.requested_authority_level,
            affected_stakeholders=[item.name for item in self.stakeholders],
            constraints=[item.description for item in self.constraints],
            objectives=[item.description for item in self.objectives],
            evidence_expectations=[
                item.question for item in self.evidence_acquisition_needs.needs
            ],
            authoring_provenance={
                "captured_by": "design_problem_bridge",
                "source_surface": self.nl_provenance.source_surface,
                "source_context": dict(context),
                "mandate": self.authority_profile.mandate,
                _DESIGN_PROBLEM_PROJECTION_KEY: self.projection_payload(
                    owner="policy_intent_envelope"
                ),
            },
            generated_at=datetime.now(UTC),
        )

    def to_scientist_problem_frame(self) -> object:
        """Project to the Scientist agent ProblemFrame generator surface."""

        from polisyos.scientist.agent.protocols import ProblemFrame

        return ProblemFrame(
            frame_id=self.design_problem_id,
            domain=self.domain,
            problem_statement=self.problem_statement,
            actors=tuple(item.name for item in self.stakeholders),
            goals=tuple(item.description for item in self.objectives),
            constraints=tuple(item.description for item in self.constraints),
            success_criteria={
                "outcome_of_interest": self.outcome_of_interest.model_dump(mode="json")
            },
            assumptions=(),
            context={
                "design_problem_id": self.design_problem_id,
                "nl_provenance": self.nl_provenance.model_dump(mode="json"),
                "authority_profile": self.authority_profile.model_dump(mode="json"),
                "jurisdiction_time": self.jurisdiction_time.model_dump(mode="json"),
                "outcome_of_interest": self.outcome_of_interest.model_dump(mode="json"),
                "candidate_lever_space": self.candidate_lever_space.model_dump(mode="json"),
                "evidence_acquisition_needs": self.evidence_acquisition_needs.model_dump(
                    mode="json"
                ),
                "model_spec_ref": self.model_spec_ref,
                _DESIGN_PROBLEM_PROJECTION_KEY: self.projection_payload(
                    owner="scientist_problem_frame"
                ),
            },
        )

    def to_ir_problem_frame(self) -> object:
        """Project to the IR governance ProblemFrame formal problem surface."""

        from polisyos.ir.governance.problem_frame import (
            ConstraintSpec,
            ConstraintType,
            ObjectiveSpec,
            ProblemDomain,
            ProblemFrame,
            StakeholderSpec,
        )
        from polisyos.ir.model_layer.types import EntityType, OptimizationDirection

        domain = _enum_value(ProblemDomain, self.domain, default=ProblemDomain.CUSTOM)
        return ProblemFrame(
            problem_id=self.design_problem_id,
            domain=domain,
            objectives=[
                ObjectiveSpec(
                    objective_id=item.objective_id,
                    metric_id=item.metric_id,
                    direction=_enum_value(
                        OptimizationDirection,
                        item.direction,
                        default=OptimizationDirection.MAXIMIZE,
                    ),
                )
                for item in self.objectives
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id=item.constraint_id,
                    constraint_type=ConstraintType.HARD,
                    value=item.description,
                )
                for item in self.constraints
                if item.hard
            ],
            soft_constraints=[
                ConstraintSpec(
                    constraint_id=item.constraint_id,
                    constraint_type=ConstraintType.SOFT,
                    value=item.description,
                )
                for item in self.constraints
                if not item.hard
            ],
            stakeholders=[
                StakeholderSpec(
                    stakeholder_id=item.stakeholder_id,
                    entity_type=EntityType.AGENT,
                    role=item.role,
                )
                for item in self.stakeholders
            ],
            narrative=self.problem_statement,
            labels=["design_problem"],
            notes=[
                f"outcome_of_interest:{self.outcome_of_interest.target_variable}",
                (
                    f"model_spec_ref:{self.model_spec_ref}"
                    if self.model_spec_ref
                    else "model_spec_ref:unset"
                ),
                self._projection_note(owner="ir_problem_frame"),
            ],
        )

    def to_policy_request_frame(self) -> object:
        """Project to the verified PolicyRequestFrame legal subflow surface."""

        from polisyos.scientist.validation.policy_verified.models import PolicyRequestFrame

        return PolicyRequestFrame(
            request_id=self.design_problem_id,
            policy_question=self.problem_statement,
            jurisdiction=self.jurisdiction_time.region,
            as_of=self.jurisdiction_time.as_of,
            policy_domain=self.domain,
            target_context={
                "region": self.jurisdiction_time.region,
                "stakeholders": [item.model_dump(mode="json") for item in self.stakeholders],
                _DESIGN_PROBLEM_PROJECTION_KEY: self.projection_payload(
                    owner="policy_request_frame"
                ),
            },
            evaluation_criteria=[self.outcome_of_interest.estimand],
            goals=[item.description for item in self.objectives],
            constraints=[item.description for item in self.constraints],
            notes=[
                f"design_problem_id:{self.design_problem_id}",
                (
                    f"model_spec_ref:{self.model_spec_ref}"
                    if self.model_spec_ref
                    else "model_spec_ref:unset"
                ),
                self._projection_note(owner="policy_request_frame"),
            ],
        )

    def to_model_spec(self, *, data_snapshot_ref: str) -> object:
        """Project time semantics into the existing IR ModelSpec surface."""

        from polisyos.ir.model_layer.model_spec import ModelSpec

        return ModelSpec(
            model_id=_slug_id(
                f"model_{self.design_problem_id}",
                fallback="model_design_problem",
            ),
            data_snapshot_ref=data_snapshot_ref,
            time_semantics=self.jurisdiction_time.time_semantics,
            description=f"ModelSpec projection for {self.design_problem_id}.",
            labels=["design_problem_projection"],
            notes=[self._projection_note(owner="model_spec")],
        )

    def to_workspace_intent(self) -> dict[str, Any]:
        """Project to the current workspace adapter's internal intent facts."""

        lever = self.candidate_lever_space.candidate_levers[0]
        intent: dict[str, Any] = {
            "design_problem_id": self.design_problem_id,
            "policy_question": self.problem_statement,
            "jurisdiction": self.jurisdiction_time.region,
            "causal_variables": [lever.target_slot, self.outcome_of_interest.target_variable],
            "outcome_of_interest": self.outcome_of_interest.model_dump(mode="json"),
            "candidate_lever_space": self.candidate_lever_space.model_dump(mode="json"),
            "evidence_acquisition_needs": self.evidence_acquisition_needs.model_dump(
                mode="json"
            ),
            "verification_required": bool(self.runtime_hints.get("verification_required")),
        }
        for key in (
            "observational_data_ref",
            "force_counterexample",
            "upper_bound",
            "random_seed",
            "causal_method_fqn",
        ):
            if key in self.runtime_hints:
                intent[key] = self.runtime_hints[key]
        return intent


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _slug_id(value: object, *, fallback: str) -> str:
    raw = str(value or "").casefold()
    chars = [char if char.isalnum() else "_" for char in raw]
    compact = "_".join(part for part in "".join(chars).split("_") if part)
    if not compact:
        compact = fallback
    if not compact[0].isalpha():
        compact = f"id_{compact}"
    return compact[:80]


def _domain_from_text(value: object) -> str:
    text = _normalize_text(value)
    if any(token in text for token in ("credit", "firm", "msme", "welfare")):
        return "social"
    if "health" in text:
        return "healthcare"
    if "education" in text:
        return "education"
    return "custom"


def _enum_value(enum_type: object, value: str, *, default: object) -> object:
    try:
        return enum_type(value)
    except ValueError:
        return default


__all__ = [
    "DESIGN_PROBLEM_PROJECTION_SCHEMA_VERSION",
    "DESIGN_PROBLEM_SCHEMA_VERSION",
    "AuthorityProfile",
    "CandidateLever",
    "CandidateLeverSpace",
    "DesignConstraint",
    "DesignObjective",
    "DesignProblem",
    "DesignProblemAuthorityError",
    "DesignStakeholder",
    "EvidenceAcquisitionNeeds",
    "EvidenceNeed",
    "JurisdictionTimeSemantics",
    "NLProvenance",
    "OutcomeOfInterest",
]
