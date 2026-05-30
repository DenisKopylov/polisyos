"""Acyclic contracts shared by policy-design critics and ensembles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.scientist.policy_design.formulator import (
    CandidateProvenance,
    FormulatorCandidate,
    LLMFormulatorInput,
    context_input_refs,
    fingerprint_payload,
    mapping_from_any,
    normalise_for_fingerprint,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


CriticRole = Literal[
    "legal",
    "fiscal",
    "equity",
    "data",
    "implementation",
    "affected_person",
    "adversarial",
    "monitoring",
]
CriticSubstantiveBasis = Literal[
    "deterministic_rule_set",
    "statistical_pattern",
    "historical_failure_corpus",
    "legal_corpus_probe",
    "simulation_probe",
    "participation_provenance_check",
    "adversarial_scenario_generator",
    "monitoring_lifecycle_drift_simulator",
]
CriticVerdictType = Literal[
    "agree",
    "contest",
    "add_candidate_obligation",
    "flag_missing_evidence",
    "flag_speculation",
    "flag_scope_drift",
]

CRITIC_ENSEMBLE_SCHEMA_VERSION = "policyos.scientist.policy_design.critic_ensemble.v1"


class CriticEnvelope(BaseModel):
    """Critic identity and non-persona substantive basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    critic_role: CriticRole
    substantive_basis: CriticSubstantiveBasis
    critic_version: str = Field(min_length=1)
    basis_ref: str | None = None

    @field_validator("critic_version", "basis_ref")
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class CriticVerdict(BaseModel):
    """Typed critic output over formulator candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict_id: str | None = None
    verdict: CriticVerdictType
    envelope: CriticEnvelope
    target_candidate_ids: tuple[str, ...] = Field(default=())
    message: str = Field(min_length=1, max_length=1000)
    failure_modes: tuple[str, ...] = Field(default=())
    evidence_refs: tuple[str, ...] = Field(default=())
    proposed_candidate: FormulatorCandidate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("verdict_id", "message")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("target_candidate_ids", "failure_modes", "evidence_refs")
    @classmethod
    def _clean_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))

    @model_validator(mode="after")
    def _validate_verdict(self) -> CriticVerdict:
        if self.verdict == "add_candidate_obligation" and self.proposed_candidate is None:
            raise ValueError("add_candidate_obligation verdicts require proposed_candidate")
        if self.proposed_candidate is not None:
            if self.proposed_candidate.source_class != "llm_critic":
                raise ValueError("critic proposed candidates must use source_class=llm_critic")
            if self.proposed_candidate.admission_state != "candidate_unverified":
                raise ValueError("critic proposed candidates must remain candidate_unverified")
        return self

    @property
    def signature(self) -> tuple[Any, ...]:
        """Substantive signature excluding critic identity."""

        proposed = None
        if self.proposed_candidate is not None:
            proposed = (
                self.proposed_candidate.kind,
                self.proposed_candidate.text,
                self.proposed_candidate.method_need_kind,
                self.proposed_candidate.question_use,
            )
        return (
            self.verdict,
            tuple(sorted(self.target_candidate_ids)),
            self.message,
            tuple(sorted(self.failure_modes)),
            proposed,
        )


class CriticDiversityWarning(BaseModel):
    """Warning emitted when the ensemble collapses or loses a basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: Literal["warning"] = "warning"


class CriticDiversitySummary(BaseModel):
    """Baseline diversity metrics emitted for W11.F tooling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    critic_count: int = Field(ge=0)
    basis_count: int = Field(ge=0)
    verdict_signature_count: int = Field(ge=0)
    warnings: tuple[CriticDiversityWarning, ...] = Field(default=())


class CriticEnsembleReport(BaseModel):
    """Complete report returned by the W6.E multi-critic ensemble."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = CRITIC_ENSEMBLE_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    verdicts: tuple[CriticVerdict, ...]
    diversity: CriticDiversitySummary
    metadata: dict[str, Any] = Field(default_factory=dict)


class CriticConsensusCandidate(BaseModel):
    """Projection row for one candidate with enough critic support for review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    support_count: int = Field(ge=0)
    consensus_threshold: int = Field(ge=1)
    verdict_refs: tuple[str, ...] = Field(default=())
    verdict_types: tuple[CriticVerdictType, ...] = Field(default=())


class CriticConsensusReport(BaseModel):
    """Bounded consensus projection over a critic ensemble report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "policyos.scientist.policy_design.critic_consensus.v1"
    run_id: str = Field(min_length=1)
    consensus_threshold: int = Field(ge=1)
    candidates: tuple[CriticConsensusCandidate, ...] = Field(default=())


@runtime_checkable
class PolicyDesignCritic(Protocol):
    """Protocol for substantively different W6.E critics."""

    @property
    def envelope(self) -> CriticEnvelope:
        """Critic role and substantive basis."""

    def evaluate(
        self,
        context: LLMFormulatorInput,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[CriticVerdict, ...]:
        """Evaluate candidate-only formulator output."""


def critic_verdict(
    envelope: CriticEnvelope,
    *,
    verdict: CriticVerdictType,
    message: str,
    target_candidate_ids: Sequence[str] = (),
    failure_modes: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    proposed_candidate: FormulatorCandidate | None = None,
    metadata: dict[str, Any] | None = None,
) -> CriticVerdict:
    """Build one critic verdict with consistent tuple normalisation."""

    return CriticVerdict(
        verdict=verdict,
        envelope=envelope,
        target_candidate_ids=tuple(target_candidate_ids),
        message=message,
        failure_modes=tuple(failure_modes),
        evidence_refs=tuple(evidence_refs),
        proposed_candidate=proposed_candidate,
        metadata=metadata or {},
    )


def build_critic_candidate(
    envelope: CriticEnvelope,
    context: LLMFormulatorInput,
    *,
    kind: Literal["obligation", "risk", "missing_question", "method_need"],
    text: str,
    field_name: str | None = None,
    claim_refs: Sequence[str] = (),
    obligation_refs: Sequence[str] = (),
    facet_refs: Sequence[str] = (),
    risk_tags: Sequence[str] = (),
    method_need_kind: str | None = None,
    question_use: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> FormulatorCandidate:
    """Build a candidate proposed by a critic, still blocked as candidate-only."""

    prompt_fingerprint = context.prompt_fingerprint or fingerprint_payload(
        {
            "critic_role": envelope.critic_role,
            "substantive_basis": envelope.substantive_basis,
            "input": normalise_for_fingerprint(
                mapping_from_any(context)
                or {
                    "intent": context.intent,
                    "facets": context.facets,
                    "obligations": context.obligations,
                    "claim_decomposition": context.claim_decomposition,
                }
            ),
        }
    )
    provenance = CandidateProvenance(
        producer=f"policy_design.critic.{envelope.critic_role}",
        producer_version=envelope.critic_version,
        source_class="llm_critic",
        prompt_fingerprint=prompt_fingerprint,
        tool_refs=(f"critic_basis.{envelope.substantive_basis}",),
        repair_decision_lineage=("repair.none",),
        input_refs=context_input_refs(context),
    )
    from polisyos.scientist.policy_design.formulator import _candidate

    return _candidate(
        kind=kind,
        text=text,
        provenance=provenance,
        field_name=field_name,
        claim_refs=tuple(claim_refs),
        obligation_refs=tuple(obligation_refs),
        facet_refs=tuple(facet_refs),
        risk_tags=tuple(risk_tags),
        method_need_kind=method_need_kind,
        question_use=question_use,
        metadata={
            **(metadata or {}),
            "critic_role": envelope.critic_role,
            "substantive_basis": envelope.substantive_basis,
        },
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _non_empty(value)


def _non_empty(value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError("text fields must be non-empty")
    return cleaned


__all__ = [
    "CRITIC_ENSEMBLE_SCHEMA_VERSION",
    "CriticConsensusCandidate",
    "CriticConsensusReport",
    "CriticDiversitySummary",
    "CriticDiversityWarning",
    "CriticEnsembleReport",
    "CriticEnvelope",
    "CriticRole",
    "CriticSubstantiveBasis",
    "CriticVerdict",
    "CriticVerdictType",
    "PolicyDesignCritic",
    "build_critic_candidate",
    "critic_verdict",
]
