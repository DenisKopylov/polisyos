"""Structured W6.E LLM formulator candidate channel.

The formulator is deliberately candidate-only. It may propose typed fields,
risks, obligations, missing questions, and method needs, but every emitted item
is marked ``candidate_unverified`` and carries an authority envelope that
prevents downstream readers from treating it as legal, evidence, method,
participation, closeout, or projection authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FORMULATOR_SCHEMA_VERSION = "policyos.scientist.policy_design.llm_formulator.v1"
FORMULATOR_COMPONENT = "policy_design.llm_formulator"
FORMULATOR_VERSION = "1.0.0"

CandidateKind = Literal["field", "risk", "obligation", "missing_question", "method_need"]
CandidateSourceClass = Literal[
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
    "deterministic_producer",
    "historical_failure",
    "human_reviewer",
    "public_contestation",
]
CandidateAdmissionState = Literal[
    "candidate_unverified",
    "rejected_speculation",
    "typed_blocker",
    "limitation",
    "admitted_to_obligation",
    "admitted_to_claim",
]

AUTHORITY_DENYLIST: tuple[str, ...] = (
    "evidence",
    "legal_authority",
    "method_authority",
    "participation_authority",
    "closeout",
    "public_projection",
    "dashboard_readiness",
    "claim_registry_admission",
)
RUNTIME_CANDIDATE_AUTHORITY_SLOTS: tuple[str, ...] = (
    "legal_authority",
    "data_authority",
    "method_authority",
    "participation_authority",
    "closeout_authority",
    "projection_authority",
    "claim_authority",
    "obligation_authority",
)
DEFAULT_FORMULATOR_TOOL_REFS: tuple[str, ...] = (
    "tool.schema.policy_design.llm_formulator.v1",
    "tool.parser.typed_candidate_channel.v1",
)
DEFAULT_REPAIR_DECISION_LINEAGE: tuple[str, ...] = ("repair.none",)


class CandidateAuthorityEnvelope(BaseModel):
    """Authority envelope that keeps formulator and critic output candidate-only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=AUTHORITY_DENYLIST)
    boundary: str = Field(default="candidate_to_authority_firewall", min_length=1)
    admission_state: CandidateAdmissionState = "candidate_unverified"

    @field_validator("authoritative_for", "may_not_use_for")
    @classmethod
    def _clean_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))

    @model_validator(mode="after")
    def _reject_candidate_authority(self) -> CandidateAuthorityEnvelope:
        if self.authoritative_for:
            raise ValueError("candidate authority envelope must not be authoritative")
        missing = set(AUTHORITY_DENYLIST) - set(self.may_not_use_for)
        if missing:
            raise ValueError("candidate authority envelope missing denylist entries")
        if self.admission_state != "candidate_unverified":
            raise ValueError("candidate authority envelope must remain candidate_unverified")
        return self


class HypothesisCandidateAuthorityEnvelope(BaseModel):
    """Runtime-compatible authority envelope for W6.F hypothesis ledger entries."""

    model_config = ConfigDict(extra="allow", frozen=True)

    authoritative_for: tuple[str, ...] = ("candidate_hypothesis",)
    may_not_use_for: tuple[str, ...] = RUNTIME_CANDIDATE_AUTHORITY_SLOTS

    @field_validator("authoritative_for", "may_not_use_for")
    @classmethod
    def _clean_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))


class CandidateProvenance(BaseModel):
    """Prompt/tool/repair provenance required before a candidate can enter a ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)
    source_class: CandidateSourceClass
    prompt_fingerprint: str = Field(min_length=1)
    tool_refs: tuple[str, ...]
    repair_decision_lineage: tuple[str, ...]
    input_refs: tuple[str, ...] = Field(default=())

    @field_validator(
        "producer",
        "producer_version",
        "prompt_fingerprint",
    )
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("tool_refs", "repair_decision_lineage", "input_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))

    @model_validator(mode="after")
    def _require_llm_lineage(self) -> CandidateProvenance:
        if self.source_class.startswith("llm_"):
            if not self.prompt_fingerprint:
                raise ValueError("prompt_fingerprint is required for LLM candidates")
            if not self.tool_refs:
                raise ValueError("tool_refs are required for LLM candidates")
            if not self.repair_decision_lineage:
                raise ValueError("repair_decision_lineage is required for LLM candidates")
        return self


class FormulatorCandidate(BaseModel):
    """Typed candidate emitted by the W6.E formulator or critic channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = FORMULATOR_SCHEMA_VERSION
    candidate_id: str = Field(min_length=1)
    kind: CandidateKind
    text: str = Field(min_length=1, max_length=1000)
    field_name: str | None = None
    claim_refs: tuple[str, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    facet_refs: tuple[str, ...] = Field(default=())
    risk_tags: tuple[str, ...] = Field(default=())
    method_need_kind: str | None = None
    question_use: str | None = None
    source_class: CandidateSourceClass = "llm_candidate"
    admission_state: CandidateAdmissionState = "candidate_unverified"
    authority_envelope: CandidateAuthorityEnvelope = Field(
        default_factory=CandidateAuthorityEnvelope
    )
    provenance: CandidateProvenance
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "candidate_id",
        "text",
        "field_name",
        "method_need_kind",
        "question_use",
    )
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("claim_refs", "obligation_refs", "facet_refs", "risk_tags")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))

    @model_validator(mode="after")
    def _validate_candidate_only_semantics(self) -> FormulatorCandidate:
        if self.source_class.startswith("llm_") and self.admission_state != "candidate_unverified":
            raise ValueError("LLM-derived candidates must remain candidate_unverified")
        if self.provenance.source_class != self.source_class:
            raise ValueError("candidate source_class must match provenance source_class")
        if self.kind == "field" and self.field_name is None:
            raise ValueError("field candidates require field_name")
        if self.kind == "method_need" and self.method_need_kind is None:
            raise ValueError("method_need candidates require method_need_kind")
        if self.kind == "missing_question" and self.question_use is None:
            raise ValueError("missing_question candidates require question_use")
        if self.authority_envelope.authoritative_for:
            raise ValueError("formulator candidates cannot be authoritative")
        return self

    def to_ledger_entry(self) -> HypothesisLedgerEntry:
        """Return the candidate as the W6.F-compatible ledger entry shape."""

        target_slots = _target_authority_slots_for_kind(self.kind)
        return HypothesisLedgerEntry(
            candidate_id=self.candidate_id,
            candidate_ref=self.candidate_id,
            source_class=self.source_class,
            candidate_kind=self.kind,
            target_authority_slots=target_slots,
            target_claim_ids=self.claim_refs,
            admission_state=self.admission_state,
            prompt_fingerprint=self.provenance.prompt_fingerprint,
            tool_refs=self.provenance.tool_refs,
            repair_decision_lineage=self.provenance.repair_decision_lineage,
            authority_envelope=HypothesisCandidateAuthorityEnvelope(
                authoritative_for=("candidate_hypothesis",),
                may_not_use_for=tuple(
                    dict.fromkeys([*RUNTIME_CANDIDATE_AUTHORITY_SLOTS, *target_slots])
                ),
            ),
            content={
                "schema_version": self.schema_version,
                "text": self.text,
                "field_name": self.field_name,
                "claim_refs": list(self.claim_refs),
                "obligation_refs": list(self.obligation_refs),
                "facet_refs": list(self.facet_refs),
                "risk_tags": list(self.risk_tags),
                "method_need_kind": self.method_need_kind,
                "question_use": self.question_use,
                "metadata": self.metadata,
            },
            provenance=self.provenance.model_dump(mode="json"),
        )


class HypothesisLedgerEntry(BaseModel):
    """Runtime-compatible append-only candidate entry consumed by W6.F."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)
    source_class: CandidateSourceClass
    candidate_kind: str = Field(min_length=1)
    target_authority_slots: tuple[str, ...]
    target_claim_ids: tuple[str, ...] = Field(default=())
    prompt_fingerprint: str | None = None
    tool_refs: tuple[str, ...] = Field(default=())
    repair_decision_lineage: tuple[str, ...] = Field(default=())
    prompt_tool_ledger_ref: str | None = None
    authority_envelope: HypothesisCandidateAuthorityEnvelope = Field(
        default_factory=HypothesisCandidateAuthorityEnvelope
    )
    admission_state: CandidateAdmissionState = "candidate_unverified"
    producer_validation_refs: tuple[str, ...] = Field(default=())
    reader_validation_refs: tuple[str, ...] = Field(default=())
    admission_ref: str | None = None
    admitted_by: str | None = None
    content: Mapping[str, Any] = Field(default_factory=dict)
    provenance: Mapping[str, Any] = Field(default_factory=dict)
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "candidate_id",
        "candidate_ref",
        "candidate_kind",
        "prompt_fingerprint",
        "prompt_tool_ledger_ref",
        "admission_ref",
        "admitted_by",
    )
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "target_authority_slots",
        "target_claim_ids",
        "tool_refs",
        "repair_decision_lineage",
        "producer_validation_refs",
        "reader_validation_refs",
    )
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))

    @model_validator(mode="after")
    def _validate_runtime_candidate_contract(self) -> HypothesisLedgerEntry:
        if not self.target_authority_slots:
            raise ValueError("hypothesis candidates require target_authority_slots")
        if self.source_class.startswith("llm_") and self.admission_state != "candidate_unverified":
            raise ValueError("LLM-derived ledger entries must remain candidate_unverified")
        if self.admission_state == "candidate_unverified":
            missing = set(self.target_authority_slots) - set(
                self.authority_envelope.may_not_use_for
            )
            if missing:
                raise ValueError("candidate envelope must forbid target authority slots")
        if self.source_class.startswith("llm_") and not self.has_admission_lineage:
            raise ValueError(
                "LLM hypothesis ledger entries require prompt/tool/repair lineage"
            )
        return self

    @property
    def has_admission_lineage(self) -> bool:
        """Whether the entry carries prompt, tool, and repair lineage."""

        return bool(self.prompt_fingerprint and self.tool_refs and self.repair_decision_lineage)


class HypothesisLedgerSink(Protocol):
    """Minimal W6.F bridge contract used by the formulator producer."""

    def append_candidates(
        self,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[HypothesisLedgerEntry, ...]:
        """Append candidates and return the persisted entry shapes."""


class InMemoryHypothesisLedger:
    """Small append-only sink used in tests and until W6.F supplies persistence."""

    def __init__(self) -> None:
        self._entries: list[HypothesisLedgerEntry] = []

    @property
    def entries(self) -> tuple[HypothesisLedgerEntry, ...]:
        """Ledger entries in append order."""

        return tuple(self._entries)

    def append_candidates(
        self,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[HypothesisLedgerEntry, ...]:
        """Append candidate entries and return only the new entries."""

        entries = tuple(candidate.to_ledger_entry() for candidate in candidates)
        self._entries.extend(entries)
        return entries


class LLMFormulatorInput(BaseModel):
    """Input envelope for the structured LLM formulator producer."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, frozen=True)

    intent: str = Field(min_length=1)
    facets: Any = Field(default_factory=dict)
    obligations: Any = Field(default_factory=tuple)
    claim_decomposition: Any = Field(default_factory=tuple)
    authority_profile_ref: str | None = None
    concept_spine_refs: tuple[str, ...] = Field(default=())
    source_refs: tuple[str, ...] = Field(default=())
    run_id: str = Field(default="w6e_llm_formulator", min_length=1)
    prompt_fingerprint: str | None = None
    tool_refs: tuple[str, ...] = Field(default=DEFAULT_FORMULATOR_TOOL_REFS)
    repair_decision_lineage: tuple[str, ...] = Field(
        default=DEFAULT_REPAIR_DECISION_LINEAGE
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("intent", "authority_profile_ref", "run_id", "prompt_fingerprint")
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "concept_spine_refs",
        "source_refs",
        "tool_refs",
        "repair_decision_lineage",
    )
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_non_empty(value) for value in values))

    @model_validator(mode="after")
    def _require_prompt_lineage(self) -> LLMFormulatorInput:
        if not self.tool_refs:
            raise ValueError("tool_refs are required for formulator inputs")
        if not self.repair_decision_lineage:
            raise ValueError("repair_decision_lineage is required for formulator inputs")
        return self


class LLMFormulatorOutput(BaseModel):
    """Formulator output and the ledger entries it produced."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = FORMULATOR_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    prompt_fingerprint: str = Field(min_length=1)
    candidates: tuple[FormulatorCandidate, ...]
    ledger_entries: tuple[HypothesisLedgerEntry, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMFormulator:
    """Deterministic structured producer for the LLM-candidate channel."""

    def formulate(
        self,
        payload: LLMFormulatorInput,
        *,
        ledger: HypothesisLedgerSink | None = None,
    ) -> LLMFormulatorOutput:
        """Produce candidate-only ledger entries from intent, facets, obligations, and claims."""

        prompt_fingerprint = payload.prompt_fingerprint or fingerprint_payload(
            {
                "intent": payload.intent,
                "facets": normalise_for_fingerprint(payload.facets),
                "obligations": normalise_for_fingerprint(payload.obligations),
                "claim_decomposition": normalise_for_fingerprint(payload.claim_decomposition),
                "authority_profile_ref": payload.authority_profile_ref,
                "concept_spine_refs": payload.concept_spine_refs,
            }
        )
        provenance = CandidateProvenance(
            producer=FORMULATOR_COMPONENT,
            producer_version=FORMULATOR_VERSION,
            source_class="llm_candidate",
            prompt_fingerprint=prompt_fingerprint,
            tool_refs=payload.tool_refs,
            repair_decision_lineage=payload.repair_decision_lineage,
            input_refs=context_input_refs(payload),
        )
        candidates = tuple(self._build_candidates(payload, provenance))
        sink = ledger or InMemoryHypothesisLedger()
        ledger_entries = sink.append_candidates(candidates)
        return LLMFormulatorOutput(
            run_id=payload.run_id,
            prompt_fingerprint=prompt_fingerprint,
            candidates=candidates,
            ledger_entries=ledger_entries,
            metadata={
                "candidate_count": len(candidates),
                "source_class": "llm_candidate",
                "admission_state": "candidate_unverified",
                "capability_phase": "W6.E",
            },
        )

    def _build_candidates(
        self,
        payload: LLMFormulatorInput,
        provenance: CandidateProvenance,
    ) -> list[FormulatorCandidate]:
        facets = mapping_from_any(payload.facets)
        obligations = sequence_from_any(payload.obligations)
        claims = sequence_from_any(payload.claim_decomposition)
        candidates: list[FormulatorCandidate] = []

        candidates.append(
            _candidate(
                kind="field",
                text=f"Candidate policy intent summary: {_clip(payload.intent, 220)}",
                provenance=provenance,
                field_name="policy_intent_summary",
                facet_refs=tuple(sorted(facets)),
                metadata={"basis": "intent_plus_facets"},
            )
        )

        risk_facets = _as_text_tuple(facets.get("risk_facet"))
        if not risk_facets:
            risk_facets = ("unassessed_public_risk",)
        for risk in risk_facets[:5]:
            candidates.append(
                _candidate(
                    kind="risk",
                    text=f"Candidate risk to test before admission: {risk}.",
                    provenance=provenance,
                    risk_tags=(risk,),
                    facet_refs=("risk_facet",) if "risk_facet" in facets else (),
                    metadata={"basis": "risk_facet_candidate"},
                )
            )

        if obligations:
            for item in obligations[:5]:
                obligation = mapping_from_any(item)
                obligation_id = _first_text(
                    obligation,
                    "obligation_id",
                    "frontier_id",
                    "id",
                    "rule_id",
                    default="obligation.unresolved",
                )
                description = _first_text(
                    obligation,
                    "description",
                    "summary",
                    "text",
                    "obligation_text",
                    default="Verify compiled obligation before downstream use.",
                )
                candidates.append(
                    _candidate(
                        kind="obligation",
                        text=f"Candidate obligation follow-up: {_clip(description, 260)}",
                        provenance=provenance,
                        obligation_refs=(obligation_id,),
                        metadata={"basis": "compiled_obligation_follow_up"},
                    )
                )
        else:
            candidates.append(
                _candidate(
                    kind="obligation",
                    text=(
                        "Candidate obligation: compile governed obligations before "
                        "downstream use."
                    ),
                    provenance=provenance,
                    metadata={"basis": "empty_obligation_graph_guard"},
                )
            )

        for facet_name, question in _missing_questions(facets).items():
            candidates.append(
                _candidate(
                    kind="missing_question",
                    text=question,
                    provenance=provenance,
                    question_use=facet_name,
                    metadata={"basis": "facet_gap_prompt"},
                )
            )

        method_needs = _method_needs_from_claims(claims)
        if not method_needs:
            method_needs = ("method_validity_screen",)
        for method_need in method_needs[:6]:
            candidates.append(
                _candidate(
                    kind="method_need",
                    text=f"Candidate method need for W7.C compilation: {method_need}.",
                    provenance=provenance,
                    method_need_kind=method_need,
                    claim_refs=_claim_refs_for_method(claims, method_need),
                    metadata={"basis": "claim_decomposition_method_need"},
                )
            )

        return candidates


def context_input_refs(payload: LLMFormulatorInput | object) -> tuple[str, ...]:
    """Collect stable source refs from a formulator-like input object."""

    if isinstance(payload, LLMFormulatorInput):
        refs = list(payload.source_refs)
        if payload.authority_profile_ref is not None:
            refs.append(payload.authority_profile_ref)
        refs.extend(payload.concept_spine_refs)
        return tuple(dict.fromkeys(refs))
    data = mapping_from_any(payload)
    refs = list(_as_text_tuple(data.get("source_refs")))
    authority_profile_ref = data.get("authority_profile_ref")
    if isinstance(authority_profile_ref, str) and authority_profile_ref.strip():
        refs.append(authority_profile_ref.strip())
    refs.extend(_as_text_tuple(data.get("concept_spine_refs")))
    return tuple(dict.fromkeys(refs))


def mapping_from_any(value: object) -> dict[str, Any]:
    """Best-effort mapping view over dicts and Pydantic-like objects."""

    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if isinstance(dumped, Mapping):
            return dict(dumped)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def sequence_from_any(value: object) -> tuple[object, ...]:
    """Best-effort sequence view that treats mappings with record lists as collections."""

    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        for key in (
            "claims",
            "claim_assignments",
            "assignments",
            "obligations",
            "records",
            "items",
        ):
            nested = value.get(key)
            if nested is not None:
                return sequence_from_any(nested)
        return (dict(value),)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return sequence_from_any(model_dump(mode="python"))
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def normalise_for_fingerprint(value: object) -> object:
    """Convert arbitrary payload fragments into stable JSON-compatible structures."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {
            str(key): normalise_for_fingerprint(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple | list):
        return [normalise_for_fingerprint(item) for item in value]
    if isinstance(value, str | int | bool) or value is None:
        return value
    if isinstance(value, float):
        return repr(value)
    return str(value)


def fingerprint_payload(payload: object) -> str:
    """Return a stable sha256 fingerprint for prompt/input provenance."""

    encoded = json.dumps(
        normalise_for_fingerprint(payload),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _candidate(
    *,
    kind: CandidateKind,
    text: str,
    provenance: CandidateProvenance,
    field_name: str | None = None,
    claim_refs: tuple[str, ...] = (),
    obligation_refs: tuple[str, ...] = (),
    facet_refs: tuple[str, ...] = (),
    risk_tags: tuple[str, ...] = (),
    method_need_kind: str | None = None,
    question_use: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> FormulatorCandidate:
    candidate_id = _stable_id(
        "candidate",
        kind,
        text,
        field_name or "",
        "|".join(claim_refs),
        "|".join(obligation_refs),
        "|".join(facet_refs),
        "|".join(risk_tags),
        method_need_kind or "",
        question_use or "",
        provenance.producer,
        provenance.prompt_fingerprint,
    )
    return FormulatorCandidate(
        candidate_id=candidate_id,
        kind=kind,
        text=text,
        field_name=field_name,
        claim_refs=claim_refs,
        obligation_refs=obligation_refs,
        facet_refs=facet_refs,
        risk_tags=risk_tags,
        method_need_kind=method_need_kind,
        question_use=question_use,
        source_class=provenance.source_class,
        provenance=provenance,
        metadata=metadata or {},
    )


def _missing_questions(facets: Mapping[str, Any]) -> dict[str, str]:
    required = {
        "population_predicate": "Which affected population is in scope for this design case?",
        "geography_predicate": "Which geography or jurisdiction bounds this design case?",
        "time_predicate": (
            "What policy, data, and evaluation time window should constrain the case?"
        ),
        "authority_type": "Which authority purpose allows this policy instrument to be considered?",
    }
    return {key: question for key, question in required.items() if not facets.get(key)}


def _method_needs_from_claims(claims: Sequence[Any]) -> tuple[str, ...]:
    needs: list[str] = []
    for item in claims:
        claim = mapping_from_any(item)
        needs.extend(_as_text_tuple(claim.get("method_needs")))
        family = _first_text(claim, "claim_family", "family", "claim_type", default="")
        if family == "causal":
            needs.append("causal_identification")
        elif family == "distributional":
            needs.append("distributional_fairness_decomposition")
        elif family == "welfare":
            needs.append("welfare_bounds_with_social_weight_provenance")
        elif family == "forecast":
            needs.append("forecast_validation")
        elif family in {"implementation", "implementation_feasibility"}:
            needs.append("implementation_feasibility_probe")
        elif family in {"preference", "lived_experience", "acceptability"}:
            needs.append("participation_provenance_requirement")
    return tuple(dict.fromkeys(_non_empty(need) for need in needs if str(need).strip()))


def _claim_refs_for_method(claims: Sequence[Any], method_need: str) -> tuple[str, ...]:
    refs: list[str] = []
    for item in claims:
        claim = mapping_from_any(item)
        claim_id = _first_text(claim, "claim_id", "id", default="")
        if not claim_id:
            continue
        explicit = set(_as_text_tuple(claim.get("method_needs")))
        family = _first_text(claim, "claim_family", "family", "claim_type", default="")
        derived = set(_method_needs_from_claims((claim,)))
        if method_need in explicit or method_need in derived or method_need == family:
            refs.append(claim_id)
    return tuple(dict.fromkeys(refs))


def _as_text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_non_empty(value),) if value.strip() else ()
    if isinstance(value, Sequence):
        return tuple(
            dict.fromkeys(str(item).strip() for item in value if str(item).strip())
        )
    return (str(value).strip(),) if str(value).strip() else ()


def _first_text(mapping: Mapping[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    if prefix == "candidate":
        return f"hypothesis-candidate:{digest}"
    return f"{prefix}_{digest}"


def _target_authority_slots_for_kind(kind: CandidateKind) -> tuple[str, ...]:
    match kind:
        case "obligation":
            preferred = ("obligation_authority", "closeout_authority", "projection_authority")
        case "method_need":
            preferred = ("method_authority", "claim_authority", "projection_authority")
        case "missing_question":
            preferred = ("claim_authority", "participation_authority", "projection_authority")
        case "risk":
            preferred = ("claim_authority", "closeout_authority", "projection_authority")
        case "field":
            preferred = ("claim_authority", "projection_authority")
    return tuple(dict.fromkeys([*preferred, *RUNTIME_CANDIDATE_AUTHORITY_SLOTS]))


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


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
    "AUTHORITY_DENYLIST",
    "FORMULATOR_SCHEMA_VERSION",
    "CandidateAdmissionState",
    "CandidateAuthorityEnvelope",
    "CandidateKind",
    "CandidateProvenance",
    "CandidateSourceClass",
    "FormulatorCandidate",
    "HypothesisLedgerEntry",
    "HypothesisLedgerSink",
    "InMemoryHypothesisLedger",
    "LLMFormulator",
    "LLMFormulatorInput",
    "LLMFormulatorOutput",
    "context_input_refs",
    "fingerprint_payload",
    "mapping_from_any",
    "normalise_for_fingerprint",
    "sequence_from_any",
]
