"""Compile claim-bound Scholar support requirements for W7.D."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScholarPublicationTier = Literal[
    "grey_literature",
    "government_report",
    "working_paper",
    "peer_reviewed",
    "systematic_review",
]
CollapseDimension = Literal[
    "underlying_study_id",
    "dataset_id",
    "author_pool",
    "institution_pool",
    "citation_network",
    "replication_lineage",
]

_SERIOUS_CLAIM_TYPES = frozenset(
    {"causal", "distributional", "welfare", "forecast", "implementation"}
)
_PARTICIPATION_FAMILIES = frozenset(
    {
        "preference",
        "lived-experience",
        "lived_experience",
        "acceptability",
        "legitimacy",
        "procedural-fairness",
        "procedural_fairness",
        "objection-dissent",
        "objection_dissent",
        "participation",
    }
)
_PARTICIPATION_USES = frozenset(
    {
        "affected_person_preference",
        "affected-person-preference",
        "dissent",
        "existence",
        "legitimacy",
        "participation-context",
        "participation_context",
        "participation_legitimacy",
        "participation-legitimacy",
        "preference",
        "prevalence",
        "qualitative",
        "role-feasibility",
        "role_feasibility",
    }
)


class ScholarDependentCorpusCollapseRule(BaseModel):
    """One rule for collapsing dependent literature into an effective evidence line."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    collapse_on: CollapseDimension
    reason_code: str | None = None
    effective_support_per_cluster: int = Field(default=1, ge=0, le=1)
    description: str | None = None

    @model_validator(mode="after")
    def _default_reason(self) -> ScholarDependentCorpusCollapseRule:
        if self.reason_code is not None:
            return self
        reason = {
            "underlying_study_id": "shared_underlying_study",
            "dataset_id": "shared_dataset",
            "author_pool": "shared_author_pool",
            "institution_pool": "shared_institution_pool",
            "citation_network": "citation_network_dependence",
            "replication_lineage": "shared_replication_lineage",
        }[self.collapse_on]
        self.reason_code = reason
        return self


class ScholarClaimRequirementSeed(BaseModel):
    """Claim-level input seed consumed by the Scholar requirement compiler."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    claim_type: str = "factual"
    claim_family: str | None = None
    claim_use: str | None = None
    authority_level: str | None = None
    population_scope: str = "general_population"
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScholarSupportRequirementSpec(BaseModel):
    """Typed per-claim contract that the Scholar adapter must consume."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scholar.support_requirement.v1"] = (
        "policyos.scholar.support_requirement.v1"
    )
    requirement_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    claim_type: str = "factual"
    claim_family: str | None = None
    claim_use: str | None = None
    authority_level: str = "research"
    population_scope: str = "general_population"
    required_publication_tier: ScholarPublicationTier
    recency_days: int = Field(ge=1, le=3650)
    required_replication_count: int = Field(ge=1, le=20)
    required_independence_breadth: int = Field(ge=1, le=20)
    required_citation_network_depth: int = Field(ge=0, le=10)
    dependent_corpus_collapse_rules: list[ScholarDependentCorpusCollapseRule] = Field(
        min_length=1
    )
    participation_like_claim: bool = False
    participation_claim_use_requested: str = "academic_support"
    participation_claim_use_allowed: str = "academic_support"
    authority_boundary: str = "scholar_academic_support_only"
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    decision_refs: list[str] = Field(default_factory=lambda: ["ADR-0160", "C13", "C14", "C26"])
    pattern_guards: list[str] = Field(default_factory=lambda: ["P01", "P02", "P10", "P14"])
    rule_version: str = "scholar_support_requirement.v1"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_participation_boundary(self) -> ScholarSupportRequirementSpec:
        if self.participation_like_claim:
            if self.participation_claim_use_allowed != "context-only":
                raise ValueError("participation-like Scholar requirements must allow context-only")
            if self.authority_boundary != "academic_publication_not_participation_provenance":
                raise ValueError("participation-like Scholar requirements must preserve ADR-0167")
        return self


def scholar_support_requirement_authority_boundary() -> dict[str, list[str]]:
    """Return the W7.D authority boundary for Scholar requirement artifacts."""

    return {
        "authoritative_for": [
            "scholar_support_requirements",
            "scholar_independence_preconditions",
            "scholar_participation_firewall",
        ],
        "may_not_use_for": [
            "affected_person_representativeness",
            "participation_provenance",
            "legal_authority",
            "source_family_satisfaction",
            "method_validity",
            "closeout_pass",
        ],
    }


def build_scholar_capability_requirement_bindings(
    *,
    scholar_support_requirement_specs: Sequence[ScholarSupportRequirementSpec | Mapping[str, Any]],
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> dict[str, Any]:
    """Bind Scholar support requirements to construct-linked SKG capabilities.

    The adapter consumes the shared capability graph. It keeps Scholar support
    advisory for claim evidence, but makes causal-edge, transport, contested,
    parameter, and boundary-condition refs visible to downstream orchestration.
    """

    requirements = normalize_scholar_support_requirement_specs(
        scholar_support_requirement_specs
    )
    bindings = [_payload(binding) for binding in capability_bindings]
    support_links: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for requirement in requirements:
        matches = [
            binding
            for binding in bindings
            if _scholar_binding_matches_requirement(binding, requirement)
        ]
        if not matches:
            blockers.append(
                {
                    "code": "scholar_capability_binding_missing",
                    "severity": "fail",
                    "requirement_id": requirement.requirement_id,
                    "claim_id": requirement.claim_id,
                    "capability_reality_label": "bridge_missing",
                }
            )
            continue
        selected = sorted(matches, key=_scholar_binding_rank)[0]
        link = _scholar_support_link_from_capability(selected, requirement)
        support_links.append(link)
        transport_score = float(link.get("transport_score") or 0.0)
        if transport_score < 0.5:
            blockers.append(
                {
                    "code": "scholar_capability_transport_below_floor",
                    "severity": "fail",
                    "requirement_id": requirement.requirement_id,
                    "claim_id": requirement.claim_id,
                    "capability_ref": link.get("capability_ref"),
                    "construct_ref": link.get("construct_ref"),
                    "observed": transport_score,
                    "required": 0.5,
                    "capability_reality_label": "implemented",
                }
            )
        if link.get("ac_skg_contested_edge_refs"):
            blockers.append(
                {
                    "code": "scholar_capability_contested_edge_review_required",
                    "severity": "warning",
                    "requirement_id": requirement.requirement_id,
                    "claim_id": requirement.claim_id,
                    "capability_ref": link.get("capability_ref"),
                    "construct_ref": link.get("construct_ref"),
                    "capability_reality_label": "implemented",
                }
            )
    blocking = [blocker for blocker in blockers if blocker.get("severity") == "fail"]
    return {
        "schema_version": "policyos.scholar.capability_requirement_bindings.v1",
        "status": "blocked" if blocking else "pass",
        "support_links": support_links,
        "literature_deficit_blockers": blockers,
        "support_requirement_specs": [
            requirement.model_dump(mode="json") for requirement in requirements
        ],
        "authority_boundary": {
            "authoritative_for": [
                "scholar_capability_requirement_binding",
                "scholar_transport_limitations",
                "scholar_contested_edge_visibility",
            ],
            "may_not_use_for": [
                "claim_evidence_authority",
                "legal_authority",
                "data_authority",
                "participation_authority",
                "closeout_pass",
            ],
        },
        "summary": {
            "support_link_count": len(support_links),
            "blocked": len(blocking),
            "capability_binding_count": len(bindings),
        },
    }


class ScholarRequirementCompilationInput(BaseModel):
    """Input packet for compiling a batch of Scholar support requirements."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    claims: list[ScholarClaimRequirementSeed] = Field(min_length=1)
    authority_level: str = "research"
    default_recency_days: int | None = Field(default=None, ge=1, le=3650)
    rule_version: str = "scholar_support_requirement.v1"
    created_by_node_id: str = (
        "polisyos.scholar_requirement.ScholarSupportRequirementCompiler"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_claims(self) -> ScholarRequirementCompilationInput:
        seen: set[str] = set()
        for claim in self.claims:
            if claim.claim_id in seen:
                raise ValueError(f"duplicate claim_id: {claim.claim_id}")
            seen.add(claim.claim_id)
        return self


class ScholarSupportRequirementCompilationResult(BaseModel):
    """Compiler artifact holding all Scholar support requirements for one run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scholar.support_requirement_result.v1"] = (
        "policyos.scholar.support_requirement_result.v1"
    )
    run_id: str = Field(min_length=1)
    requirements: list[ScholarSupportRequirementSpec]
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    capability_reality_label: Literal["implemented"] = "implemented"
    producer_component: str = "polisyos.scholar_requirement"
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    authority_boundary: dict[str, list[str]] = Field(
        default_factory=scholar_support_requirement_authority_boundary
    )
    decision_refs: list[str] = Field(default_factory=lambda: ["ADR-0160", "ADR-0167"])
    pattern_guards: list[str] = Field(default_factory=lambda: ["P01", "P02", "P10", "P14"])
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_runtime_event_ref(self) -> ScholarSupportRequirementCompilationResult:
        if self.runtime_event_ref is None:
            self.runtime_event_ref = f"event://scholar-requirement/{_slug(self.run_id)}"
        if not self.authority_boundary:
            self.authority_boundary = scholar_support_requirement_authority_boundary()
        return self


class ScholarSupportRequirementCompiler:
    """Deterministically compile claim seeds into Scholar support specs."""

    def compile(
        self,
        payload: ScholarRequirementCompilationInput | Mapping[str, Any],
    ) -> ScholarSupportRequirementCompilationResult:
        """Compile claim-bound Scholar evidence requirements."""

        item = (
            payload
            if isinstance(payload, ScholarRequirementCompilationInput)
            else ScholarRequirementCompilationInput.model_validate(payload)
        )
        requirements = [self._compile_claim(item, claim) for claim in item.claims]
        return ScholarSupportRequirementCompilationResult(
            run_id=item.run_id,
            requirements=requirements,
            metadata={
                "created_by_node_id": item.created_by_node_id,
                "rule_version": item.rule_version,
                **dict(item.metadata),
            },
        )

    def _compile_claim(
        self,
        item: ScholarRequirementCompilationInput,
        claim: ScholarClaimRequirementSeed,
    ) -> ScholarSupportRequirementSpec:
        authority_level = _normalize(claim.authority_level or item.authority_level)
        claim_type = _normalize(claim.claim_type)
        claim_family = _normalize_optional(claim.claim_family)
        claim_use = _normalize_optional(claim.claim_use)
        participation_like = _participation_like(claim)
        serious = claim_type in _SERIOUS_CLAIM_TYPES or (claim_family or "") in _SERIOUS_CLAIM_TYPES
        publication_tier = _publication_tier(
            authority_level=authority_level,
            serious=serious,
            participation_like=participation_like,
        )
        recency_days = item.default_recency_days or _recency_days(
            authority_level=authority_level,
            claim_type=claim_type,
        )
        replication_count = _replication_count(
            authority_level=authority_level,
            serious=serious,
            participation_like=participation_like,
        )
        decision_refs = ["ADR-0160", "C13", "C14", "C26"]
        if participation_like:
            decision_refs.append("FT-ADR-02")
            decision_refs.append("ADR-0167")
        return ScholarSupportRequirementSpec(
            requirement_id=f"scholar-support:{item.run_id}:{claim.claim_id}",
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            claim_type=claim_type,
            claim_family=claim_family,
            claim_use=claim_use,
            authority_level=authority_level,
            population_scope=_normalize(claim.population_scope),
            required_publication_tier=publication_tier,
            recency_days=recency_days,
            required_replication_count=replication_count,
            required_independence_breadth=replication_count,
            required_citation_network_depth=2
            if authority_level in {"production", "governed"} and not participation_like
            else 1,
            dependent_corpus_collapse_rules=_default_collapse_rules(),
            participation_like_claim=participation_like,
            participation_claim_use_requested=claim_use or "academic_support",
            participation_claim_use_allowed="context-only"
            if participation_like
            else "academic_support",
            authority_boundary="academic_publication_not_participation_provenance"
            if participation_like
            else "scholar_academic_support_only",
            facet_refs=claim.facet_refs,
            obligation_refs=claim.obligation_refs,
            concept_spine_refs=claim.concept_spine_refs,
            authority_profile_refs=claim.authority_profile_refs,
            decision_refs=decision_refs,
            rule_version=item.rule_version,
            metadata=dict(claim.metadata),
        )


def normalize_scholar_support_requirement_specs(
    value: object,
) -> list[ScholarSupportRequirementSpec]:
    """Normalize mixed requirement-spec payloads into typed specs."""

    if value is None:
        return []
    if isinstance(value, ScholarSupportRequirementCompilationResult):
        return list(value.requirements)
    if isinstance(value, ScholarSupportRequirementSpec):
        return [value]
    if isinstance(value, Mapping):
        if "requirements" in value:
            result = ScholarSupportRequirementCompilationResult.model_validate(value)
            return list(result.requirements)
        return [ScholarSupportRequirementSpec.model_validate(value)]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    specs: list[ScholarSupportRequirementSpec] = []
    for item in value:
        if isinstance(item, ScholarSupportRequirementSpec):
            specs.append(item)
        elif isinstance(item, Mapping):
            specs.append(ScholarSupportRequirementSpec.model_validate(item))
    return specs


def requirement_specs_by_claim(
    specs: Sequence[ScholarSupportRequirementSpec],
) -> dict[str, ScholarSupportRequirementSpec]:
    """Index Scholar requirement specs by claim id."""

    return {spec.claim_id: spec for spec in specs}


def scholar_support_requirement_audit_surface(
    result: ScholarSupportRequirementCompilationResult | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an audit/API projection of Scholar support requirements."""

    model = (
        result
        if isinstance(result, ScholarSupportRequirementCompilationResult)
        else ScholarSupportRequirementCompilationResult.model_validate(dict(result))
    )
    payload = model.model_dump(mode="json")
    payload["surface"] = "scholar_requirement.audit_surface"
    payload["summary"] = {
        "requirement_count": len(model.requirements),
        "claim_ids": [requirement.claim_id for requirement in model.requirements],
        "participation_like_claim_count": sum(
            1 for requirement in model.requirements if requirement.participation_like_claim
        ),
        "publication_tiers": sorted(
            {requirement.required_publication_tier for requirement in model.requirements}
        ),
    }
    return payload


def write_scholar_support_requirement_result(
    result: ScholarSupportRequirementCompilationResult | Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    """Persist a Scholar support requirement result as deterministic JSON."""

    model = (
        result
        if isinstance(result, ScholarSupportRequirementCompilationResult)
        else ScholarSupportRequirementCompilationResult.model_validate(dict(result))
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(model.run_id)}-scholar-support-requirements.json"
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _default_collapse_rules() -> list[ScholarDependentCorpusCollapseRule]:
    return [
        ScholarDependentCorpusCollapseRule(
            rule_id=f"collapse:{collapse_on}",
            collapse_on=collapse_on,
        )
        for collapse_on in (
            "underlying_study_id",
            "dataset_id",
            "author_pool",
            "institution_pool",
            "citation_network",
            "replication_lineage",
        )
    ]


def _scholar_support_link_from_capability(
    binding: Mapping[str, Any],
    requirement: ScholarSupportRequirementSpec,
) -> dict[str, Any]:
    metadata = _mapping(binding.get("metadata"))
    capability_ref = _text(
        binding.get("selected_capability_ref") or binding.get("capability_ref")
    )
    transport_score = _float(metadata.get("transport_score"))
    if transport_score is None:
        transport_score = _float(binding.get("transport_score"))
    transport_score = 1.0 if transport_score is None else transport_score
    degraded = transport_score < 0.5
    return {
        "link_id": f"scholar-capability:{_slug(requirement.requirement_id)}",
        "support_link_ref": f"scholar-support-ref:{requirement.requirement_id}",
        "requirement_id": requirement.requirement_id,
        "claim_id": requirement.claim_id,
        "claim_text": requirement.claim_text,
        "capability_ref": capability_ref,
        "construct_ref": _text(binding.get("construct_ref")),
        "capability_index_ref": _text(binding.get("capability_index_ref")),
        "construct_registry_ref": _text(binding.get("construct_registry_ref")),
        "authority_composition_rule_ref": _text(
            binding.get("authority_composition_rule_ref")
            or binding.get("rule_version_ref")
        ),
        "authority_envelope_result": "limited" if degraded else "advisory",
        "support_status": "limited" if degraded else "supported",
        "support_score": _float(metadata.get("support_score")) or 0.0,
        "transport_score": transport_score,
        "authority_degradation_reason": "transport_score_below_0_5"
        if degraded
        else None,
        "ac_skg_edge_refs": _text_list(metadata.get("ac_skg_edge_refs")),
        "ac_skg_transport_score_refs": _text_list(
            metadata.get("ac_skg_transport_score_refs")
        ),
        "ac_skg_contested_edge_refs": _text_list(
            metadata.get("ac_skg_contested_edge_refs")
        ),
        "ac_parameter_estimate_refs": _text_list(
            metadata.get("ac_parameter_estimate_refs")
        ),
        "ac_boundary_condition_refs": _text_list(
            metadata.get("ac_boundary_condition_refs")
        ),
        "limitations": _text_list(binding.get("limitations")),
        "metadata": metadata,
    }


def _scholar_binding_matches_requirement(
    binding: Mapping[str, Any],
    requirement: ScholarSupportRequirementSpec,
) -> bool:
    modalities = {item.casefold() for item in _text_list(binding.get("modality"))}
    mode = _text(binding.get("evidence_mode")).casefold()
    metadata = _mapping(binding.get("metadata"))
    if not (
        "scholar_claim" in modalities
        or mode == "scholarly_causal_support"
        or metadata.get("ac_skg_edge_refs")
    ):
        return False
    if _text(binding.get("requirement_id")) == requirement.requirement_id:
        return True
    claim_refs = set(_text_list(binding.get("target_claim_ids")))
    if requirement.claim_id in claim_refs:
        return True
    construct = _text(binding.get("construct_ref")).removeprefix("construct:")
    if not construct:
        return False
    return any(
        construct in ref.removeprefix("concept:")
        for ref in requirement.concept_spine_refs
    )


def _scholar_binding_rank(binding: Mapping[str, Any]) -> tuple[int, str]:
    status = _text(binding.get("status"))
    selected_rank = 0 if status.startswith("selected_") else 1
    return (selected_rank, _text(binding.get("selected_capability_ref")))


def _payload(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text_list(value: object) -> list[str]:
    if value is None:
        return []
    values = (
        value
        if isinstance(value, Sequence)
        and not isinstance(value, str | bytes | bytearray)
        else (value,)
    )
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _text(value: object) -> str:
    return str(value or "").strip()


def _float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _participation_like(claim: ScholarClaimRequirementSeed) -> bool:
    metadata = claim.metadata
    if metadata.get("participation_like") is True:
        return True
    family = _normalize_optional(claim.claim_family)
    use = _normalize_optional(claim.claim_use)
    return (family in _PARTICIPATION_FAMILIES) or (use in _PARTICIPATION_USES)


def _publication_tier(
    *,
    authority_level: str,
    serious: bool,
    participation_like: bool,
) -> ScholarPublicationTier:
    if participation_like:
        return "grey_literature"
    if serious and authority_level in {"production", "governed"}:
        return "peer_reviewed"
    if serious:
        return "working_paper"
    if authority_level == "production":
        return "government_report"
    return "grey_literature"


def _recency_days(*, authority_level: str, claim_type: str) -> int:
    if claim_type == "forecast":
        return 365
    if authority_level == "production":
        return 730
    if authority_level == "governed":
        return 1095
    return 1825


def _replication_count(
    *,
    authority_level: str,
    serious: bool,
    participation_like: bool,
) -> int:
    if participation_like:
        return 1
    if serious and authority_level in {"production", "governed"}:
        return 2
    return 1


def _normalize_optional(value: object) -> str | None:
    text = _normalize(value)
    return text or None


def _normalize(value: object) -> str:
    text = str(value or "").strip().casefold()
    return re.sub(r"[\s_]+", "-", text).replace("decision-support", "decision_support")


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "CollapseDimension",
    "ScholarClaimRequirementSeed",
    "ScholarDependentCorpusCollapseRule",
    "ScholarPublicationTier",
    "ScholarRequirementCompilationInput",
    "ScholarSupportRequirementCompilationResult",
    "ScholarSupportRequirementCompiler",
    "ScholarSupportRequirementSpec",
    "build_scholar_capability_requirement_bindings",
    "normalize_scholar_support_requirement_specs",
    "requirement_specs_by_claim",
    "scholar_support_requirement_audit_surface",
    "scholar_support_requirement_authority_boundary",
    "write_scholar_support_requirement_result",
]
