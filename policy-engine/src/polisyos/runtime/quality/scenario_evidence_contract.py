"""Typed scenario evidence obligations for production-quality canaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION = "policyos.scenario_evidence_contract.v1"

RequirementDomain = Literal["data", "legal", "method", "claim", "governance"]

DATA_REQUIRED_FACETS = (
    "source_rights",
    "dictionary_ref",
    "schema_ref",
    "field_refs",
    "unit_refs",
    "geography_refs",
    "time_coverage_refs",
    "quality_refs",
    "missingness_refs",
    "lineage_refs",
    "transformation_refs",
    "derived_feature_bindings",
)
LEGAL_REQUIRED_FACETS = (
    "jurisdiction_refs",
    "competence_refs",
    "temporal_validity_refs",
    "effective_date_filters",
    "policy_instrument_refs",
    "beneficiary_class_refs",
    "fiscal_authority_refs",
    "implementation_agency_refs",
    "legal_query_terms",
    "candidate_norm_refs",
    "selected_norm_refs",
    "rejected_norm_refs",
    "authority_blocker_refs",
)
METHOD_REQUIRED_FACETS = (
    "selected_method_refs",
    "input_refs",
    "assumptions",
    "uncertainty_refs",
    "sensitivity_refs",
    "missingness_diagnostics",
    "limitations",
)
CLAIM_REQUIRED_FACETS = (
    "evidence_portfolio_refs",
    "data_refs",
    "method_refs",
    "norm_refs",
    "argument_refs",
    "warrant_refs",
    "counter_evidence_refs",
    "limitation_refs",
    "publication_section_refs",
)
GOVERNANCE_REQUIRED_FACETS = (
    "conflict_check_refs",
    "budget_guardrail_refs",
    "equity_access_refs",
    "implementation_monitoring_refs",
)

OWNER_BY_DOMAIN: dict[RequirementDomain, str] = {
    "data": "team-fabric",
    "legal": "team-policy-semantics",
    "method": "team-foundry",
    "claim": "team-policy-semantics",
    "governance": "team-runtime-quality",
}


@dataclass(frozen=True)
class ScenarioEvidenceRequirement:
    """One typed obligation carried from a scenario into runtime evidence."""

    requirement_id: str
    domain: RequirementDomain
    expected_family: str
    required_facets: tuple[str, ...]
    claim_scope: tuple[str, ...]
    jurisdiction: str | None
    temporal_scope: str | None
    authority_scope: tuple[str, ...]
    instrument_type: str | None
    beneficiary_class: str | None
    rights_scope: str | None
    producer_owner: str
    reader_owner: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "requirement_id": self.requirement_id,
            "domain": self.domain,
            "expected_family": self.expected_family,
            "required_facets": list(self.required_facets),
            "claim_scope": list(self.claim_scope),
            "jurisdiction": self.jurisdiction,
            "temporal_scope": self.temporal_scope,
            "authority_scope": list(self.authority_scope),
            "instrument_type": self.instrument_type,
            "beneficiary_class": self.beneficiary_class,
            "rights_scope": self.rights_scope,
            "producer_owner": self.producer_owner,
            "reader_owner": self.reader_owner,
        }


@dataclass(frozen=True)
class ScenarioEvidenceContract:
    """Normalized, stable evidence contract for one quality scenario."""

    schema_version: str
    contract_id: str
    scenario_id: str
    title: str | None
    pack: str | None
    requirements: tuple[ScenarioEvidenceRequirement, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "schema_version": self.schema_version,
            "contract_id": self.contract_id,
            "scenario_id": self.scenario_id,
            "title": self.title,
            "pack": self.pack,
            "requirements": [item.to_dict() for item in self.requirements],
            "requirement_count": len(self.requirements),
        }


def normalize_scenario_evidence_contract(
    scenario: Mapping[str, Any],
) -> ScenarioEvidenceContract:
    """Normalize a golden scenario into runtime-owned evidence requirements."""

    scenario_id = _required_text(scenario.get("scenario_id"), "scenario_id")
    expected = _mapping(scenario.get("expected_evidence_contract"))
    context = _mapping(scenario.get("context"))
    metadata = _mapping(scenario.get("scenario_evidence_contract"))
    jurisdiction = _jurisdiction_from_context(context)
    temporal_scope = _optional_text(
        context.get("policy_time")
        or context.get("data_time")
        or metadata.get("temporal_scope")
    )
    authority_scope = _text_tuple(
        metadata.get("authority_scope")
        or [
            jurisdiction,
            context.get("policy_domain"),
            context.get("query_treatment"),
        ]
    )
    instrument_type = _optional_text(
        metadata.get("instrument_type") or context.get("query_treatment")
    )
    beneficiary_class = _optional_text(
        metadata.get("beneficiary_class") or context.get("target_population") or "msme"
    )
    rights_scope = _optional_text(metadata.get("rights_scope")) or "public_policy_research"
    claim_scope = _claim_scope(expected)
    requirements: list[ScenarioEvidenceRequirement] = []

    requirements.extend(
        _requirements_for_values(
            scenario_id=scenario_id,
            domain="data",
            values=expected.get("admissible_data_source_families"),
            facets=DATA_REQUIRED_FACETS,
            claim_scope=claim_scope,
            jurisdiction=jurisdiction,
            temporal_scope=temporal_scope,
            authority_scope=authority_scope,
            instrument_type=instrument_type,
            beneficiary_class=beneficiary_class,
            rights_scope=rights_scope,
        )
    )
    requirements.extend(
        _requirements_for_values(
            scenario_id=scenario_id,
            domain="legal",
            values=expected.get("normative_fact_classes"),
            facets=LEGAL_REQUIRED_FACETS,
            claim_scope=claim_scope,
            jurisdiction=jurisdiction,
            temporal_scope=temporal_scope,
            authority_scope=authority_scope,
            instrument_type=instrument_type,
            beneficiary_class=beneficiary_class,
            rights_scope=rights_scope,
        )
    )
    requirements.extend(
        _requirements_for_values(
            scenario_id=scenario_id,
            domain="method",
            values=expected.get("foundry_method_expectations"),
            facets=METHOD_REQUIRED_FACETS,
            claim_scope=claim_scope,
            jurisdiction=jurisdiction,
            temporal_scope=temporal_scope,
            authority_scope=authority_scope,
            instrument_type=instrument_type,
            beneficiary_class=beneficiary_class,
            rights_scope=rights_scope,
        )
    )
    requirements.extend(
        _requirements_for_values(
            scenario_id=scenario_id,
            domain="claim",
            values=expected.get("unacceptable_recommendations"),
            facets=CLAIM_REQUIRED_FACETS,
            claim_scope=claim_scope,
            jurisdiction=jurisdiction,
            temporal_scope=temporal_scope,
            authority_scope=authority_scope,
            instrument_type=instrument_type,
            beneficiary_class=beneficiary_class,
            rights_scope=rights_scope,
        )
    )
    requirements.extend(
        _requirements_for_values(
            scenario_id=scenario_id,
            domain="governance",
            values=expected.get("conflict_checks"),
            facets=GOVERNANCE_REQUIRED_FACETS,
            claim_scope=claim_scope,
            jurisdiction=jurisdiction,
            temporal_scope=temporal_scope,
            authority_scope=authority_scope,
            instrument_type=instrument_type,
            beneficiary_class=beneficiary_class,
            rights_scope=rights_scope,
        )
    )
    return ScenarioEvidenceContract(
        schema_version=SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION,
        contract_id=_contract_id(scenario_id, metadata),
        scenario_id=scenario_id,
        title=_optional_text(scenario.get("title")),
        pack=_optional_text(scenario.get("pack")),
        requirements=tuple(requirements),
    )


def evaluate_source_family_binding(
    requirement: ScenarioEvidenceRequirement | Mapping[str, Any],
    selected_source_family: str,
) -> dict[str, Any]:
    """Evaluate whether a selected source family satisfies a data requirement."""

    requirement_dict = (
        requirement.to_dict()
        if isinstance(requirement, ScenarioEvidenceRequirement)
        else dict(requirement)
    )
    expected = _required_text(requirement_dict.get("expected_family"), "expected_family")
    selected = _required_text(selected_source_family, "selected_source_family")
    satisfied = (
        requirement_dict.get("domain") == "data"
        and selected.casefold() == expected.casefold()
    )
    return {
        "requirement_id": requirement_dict.get("requirement_id"),
        "status": "satisfied" if satisfied else "failed",
        "selected_ref": selected,
        "expected_family": expected,
        "blocker_code": None if satisfied else "source_family_mismatch",
        "missing_facets": [] if satisfied else list(requirement_dict.get("required_facets") or ()),
    }


def _requirements_for_values(
    *,
    scenario_id: str,
    domain: RequirementDomain,
    values: Any,
    facets: tuple[str, ...],
    claim_scope: tuple[str, ...],
    jurisdiction: str | None,
    temporal_scope: str | None,
    authority_scope: tuple[str, ...],
    instrument_type: str | None,
    beneficiary_class: str | None,
    rights_scope: str | None,
) -> list[ScenarioEvidenceRequirement]:
    requirements: list[ScenarioEvidenceRequirement] = []
    for value in _text_tuple(values):
        requirements.append(
            ScenarioEvidenceRequirement(
                requirement_id=f"scenario:{scenario_id}:{domain}:{value}",
                domain=domain,
                expected_family=value,
                required_facets=facets,
                claim_scope=claim_scope,
                jurisdiction=jurisdiction,
                temporal_scope=temporal_scope,
                authority_scope=authority_scope,
                instrument_type=instrument_type,
                beneficiary_class=beneficiary_class,
                rights_scope=rights_scope,
                producer_owner=OWNER_BY_DOMAIN[domain],
                reader_owner="team-runtime-quality",
            )
        )
    return requirements


def _contract_id(scenario_id: str, metadata: Mapping[str, Any]) -> str:
    return (
        _optional_text(metadata.get("contract_id"))
        or f"scenario-evidence-contract:{scenario_id}:v1"
    )


def _claim_scope(expected: Mapping[str, Any]) -> tuple[str, ...]:
    return _text_tuple(
        expected.get("major_claim_ids")
        or expected.get("recommendation_ids")
        or ("major_recommendations",)
    )


def _jurisdiction_from_context(context: Mapping[str, Any]) -> str | None:
    explicit = _optional_text(context.get("jurisdiction"))
    if explicit:
        return explicit
    country = _optional_text(context.get("country"))
    if country and country.casefold() in {"ukraine", "ua", "ukr"}:
        return "UA"
    return country


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _required_text(value: Any, field: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"{field} is required")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    return tuple(
        text
        for text in (_optional_text(item) for item in raw_values)
        if text is not None
    )


__all__ = [
    "CLAIM_REQUIRED_FACETS",
    "DATA_REQUIRED_FACETS",
    "GOVERNANCE_REQUIRED_FACETS",
    "LEGAL_REQUIRED_FACETS",
    "METHOD_REQUIRED_FACETS",
    "SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION",
    "ScenarioEvidenceContract",
    "ScenarioEvidenceRequirement",
    "evaluate_source_family_binding",
    "normalize_scenario_evidence_contract",
]
