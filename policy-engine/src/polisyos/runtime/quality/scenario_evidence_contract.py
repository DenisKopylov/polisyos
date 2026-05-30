"""Typed scenario evidence obligations for production-quality canaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from polisyos.data_requirement import DataRequirementCompiler, DataRequirementSpec

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
LEGACY_SCENARIO_FAMILY_ORDER = (
    "production_msme_panel",
    "credit_program_registry",
    "regional_displacement_indicators",
)


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
    admissible_data_source_families: tuple[str, ...]
    data_requirement_specs: tuple[DataRequirementSpec, ...]

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
            "admissible_data_source_families": list(
                self.admissible_data_source_families
            ),
            "data_requirement_specs": [
                item.model_dump(mode="json") for item in self.data_requirement_specs
            ],
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
    data_requirement_report = DataRequirementCompiler().compile_for_scenario(scenario)
    admissible_data_source_families = _legacy_scenario_family_projection(
        expected,
        data_requirement_report.legacy_admissible_data_source_families,
    )
    data_requirement_specs = _legacy_data_requirement_specs(
        data_requirement_report.specs,
        admissible_data_source_families,
    )
    requirements: list[ScenarioEvidenceRequirement] = []

    requirements.extend(
        _requirements_for_values(
            scenario_id=scenario_id,
            domain="data",
            values=admissible_data_source_families,
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
        admissible_data_source_families=admissible_data_source_families,
        data_requirement_specs=data_requirement_specs,
    )


def _legacy_scenario_family_projection(
    expected: Mapping[str, Any],
    compiled_families: tuple[str, ...],
) -> tuple[str, ...]:
    expected_families = _text_tuple(expected.get("admissible_data_source_families"))
    legacy_family_set = set(LEGACY_SCENARIO_FAMILY_ORDER)
    if expected_families and set(expected_families) <= legacy_family_set:
        return tuple(
            family for family in LEGACY_SCENARIO_FAMILY_ORDER if family in expected_families
        )

    compiled_legacy_families = tuple(
        family for family in LEGACY_SCENARIO_FAMILY_ORDER if family in compiled_families
    )
    return compiled_legacy_families or expected_families or compiled_families


def _legacy_data_requirement_specs(
    specs: tuple[DataRequirementSpec, ...],
    legacy_families: tuple[str, ...],
) -> tuple[DataRequirementSpec, ...]:
    family_order = {family: index for index, family in enumerate(legacy_families)}
    filtered = [
        spec
        for spec in specs
        if spec.required_data_families
        and spec.required_data_families[0] in family_order
    ]
    if not filtered:
        return specs
    return tuple(
        sorted(
            filtered,
            key=lambda spec: (
                family_order[spec.required_data_families[0]],
                spec.claim_id,
                spec.requirement_id,
            ),
        )
    )


def evaluate_source_family_binding(
    requirement: ScenarioEvidenceRequirement | Mapping[str, Any],
    selected_source_family: str,
) -> dict[str, Any]:
    """Evaluate the legacy source-family compatibility projection.

    Scenario-family strings are kept only for old dashboards and audit views.
    Matching the projected family name does not grant evidence authority; current
    authority must come from construct/capability bindings compiled elsewhere.
    """

    requirement_dict = (
        requirement.to_dict()
        if isinstance(requirement, ScenarioEvidenceRequirement)
        else dict(requirement)
    )
    expected = _required_text(requirement_dict.get("expected_family"), "expected_family")
    selected = _required_text(selected_source_family, "selected_source_family")
    projected_match = (
        requirement_dict.get("domain") == "data"
        and selected.casefold() == expected.casefold()
    )
    if projected_match:
        return {
            "requirement_id": requirement_dict.get("requirement_id"),
            "status": "compatibility_projection_only",
            "selected_ref": selected,
            "expected_family": expected,
            "blocker_code": "scenario_family_authority_lookup_sunset",
            "authority_granted": False,
            "missing_facets": list(requirement_dict.get("required_facets") or ()),
            "replacement": "capability_index_v1",
            "may_not_use_for": [
                "scenario_family_authority_lookup",
                "source_family_authority_decision_path",
            ],
        }
    return {
        "requirement_id": requirement_dict.get("requirement_id"),
        "status": "failed",
        "selected_ref": selected,
        "expected_family": expected,
        "blocker_code": "source_family_mismatch",
        "authority_granted": False,
        "missing_facets": list(requirement_dict.get("required_facets") or ()),
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
