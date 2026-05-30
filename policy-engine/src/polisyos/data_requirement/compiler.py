"""Deterministic compiler from claim/facet obligations to DataRequirementSpec."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from polisyos.core import contracts
from polisyos.ir import governance
from polisyos.obligation_graph import ComplexityBudget, compile_obligation_graph
from polisyos.obligation_rules import build_seed_obligation_rule_catalog
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)

from ._impl.models import (
    DataQualityMinimums,
    DataRequirementCompilationReport,
    DataRequirementScope,
    DataRequirementSpec,
    data_requirement_authority_boundary,
)

CapabilityBindingLike = contracts.CapabilityBindingLike
CapabilityResolverPort = contracts.CapabilityResolverPort
RequirementToCapabilityQuery = contracts.RequirementToCapabilityQuery
construct_for_legacy_family = contracts.construct_for_legacy_family
legacy_family_for_construct = contracts.legacy_family_for_construct

_MANDATORY_FACETS: tuple[str, ...] = (
    "source_contract_ref",
    "source_rights",
    "dictionary_ref",
    "schema_ref",
    "field_refs",
    "unit_refs",
    "geography_refs",
    "time_coverage_refs",
    "freshness_ref",
    "lineage_refs",
    "transformation_refs",
    "quality_assertion_refs",
    "missingness_refs",
    "outlier_refs",
    "construct_validity_refs",
    "claim_bindability_refs",
)
_ADMISSIBILITY_PREDICATES: tuple[str, ...] = (
    "source_family_matches_compiled_requirement",
    "source_contract_active",
    "observation_time_covers_claim_time",
    "lineage_preserves_required_transformations",
    "missingness_within_tolerance",
    "quality_minima_satisfied",
    "claim_bindability_refs_present",
)
_DECISION_CLAIM_USES = {
    "decision_support",
    "method_precondition",
    "superiority",
    "implementation_readiness",
}
_DECISION_CLAIM_FAMILIES = {
    "causal",
    "distributional",
    "welfare",
    "forecast",
    "implementation",
    "implementation_feasibility",
    "acceptability",
    "legitimacy",
}

# Track A1/Phase 4 feature flag. When ``true``, missing construct-capability
# bindings may still fall back to the legacy hardcoded heuristic in
# ``_required_data_families_from_heuristic``. The default is now ``false``:
# the primary path resolves constructs through an injected CapabilityResolverPort.
# Architecture/shims.toml carries the sunset trigger.
_DATA_REQUIREMENT_FAMILY_FALLBACK_ENV = (
    "POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED"
)
# POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED default false.
_DATA_REQUIREMENT_FAMILY_FALLBACK_DEFAULT = "false"
_DATA_FAMILY_ORDER: tuple[str, ...] = (
    "production_msme_panel",
    "credit_program_registry",
    "regional_displacement_indicators",
    "labor_force_panel",
    "employment_registry",
    "regional_vulnerability_index",
    "tax_admin_panel",
    "fiscal_revenue_series",
    "housing_beneficiary_registry",
    "rent_market_panel",
    "service_delivery_registry",
    "vaccination_coverage_panel",
    "rural_access_indicators",
)


def _data_requirement_family_fallback_enabled() -> bool:
    raw = os.environ.get(
        _DATA_REQUIREMENT_FAMILY_FALLBACK_ENV,
        _DATA_REQUIREMENT_FAMILY_FALLBACK_DEFAULT,
    )
    return str(raw).strip().casefold() in {"1", "true", "yes", "on"}


class DataRequirementCompiler:
    """Compile claim-bound Fabric data needs from W6 facets and claim records."""

    def __init__(
        self,
        *,
        capability_resolver: CapabilityResolverPort | None = None,
        require_capability_index: bool = False,
    ) -> None:
        """Initialize the compiler with optional release-backed capability resolution.

        Args:
            capability_resolver: Already-loaded resolver supplied by orchestration
                code that owns capability-index loading.
            require_capability_index: When true, fail closed unless a resolver is
                injected by the caller.
        """

        self._capability_resolver = capability_resolver
        self._require_capability_index = require_capability_index

    def compile_for_claim_ledger(
        self,
        *,
        run_id: str,
        claim_ledger: object | Mapping[str, Any],
        facet_snapshots: Sequence[Mapping[str, Any]],
        obligation_graph: object | Mapping[str, Any] | None = None,
        scenario_id: str | None = None,
        authority_profile_refs: Sequence[str] = (),
    ) -> DataRequirementCompilationReport:
        """Compile data requirements for decision-bearing claims.

        Args:
            run_id: Runtime run/case identifier.
            claim_ledger: W6.D claim ledger or JSON payload.
            facet_snapshots: W6.A parallel facet snapshot interface.
            obligation_graph: Optional W6.C graph used for obligation refs.
            scenario_id: Optional scenario id for legacy bridge projections.
            authority_profile_refs: Additional authority refs from the run carrier.

        Returns:
            A claim-bound data requirement compilation report.
        """

        claims = _ledger_claims(claim_ledger)
        facets = tuple(dict(facet) for facet in facet_snapshots)
        facet_index = _facet_index(facets)
        scope = _scope_from_facets(facet_index)
        capability_bindings = _capability_bindings_for_requirements(
            facets=facets,
            claims=claims,
            obligation_graph=obligation_graph,
            scenario_id=scenario_id,
            scope=scope,
            resolver=self._resolver_for_compilation(),
        )
        family_rules = tuple(
            dict.fromkeys(
                legacy_family_for_construct(binding.construct_ref or "")
                for binding in capability_bindings
                if binding.construct_ref
            )
        )
        bindings_by_family = {
            legacy_family_for_construct(binding.construct_ref or ""): binding
            for binding in capability_bindings
            if binding.construct_ref
        }
        family_derivation = "capability_resolver" if family_rules else None
        if not family_rules and _data_requirement_family_fallback_enabled():
            family_rules = _required_data_families_from_heuristic(
                facets=facets,
                claims=claims,
                scenario_id=scenario_id,
            )
            family_derivation = "legacy_heuristic_fallback"
        else:
            family_rules = family_rules or ()
        obligation_refs = _data_obligation_refs(obligation_graph)
        specs: list[DataRequirementSpec] = []
        for claim in claims:
            if not _claim_requires_data(claim):
                continue
            families = family_rules
            for family in families:
                spec = _spec_for_claim_family(
                    run_id=run_id,
                    scenario_id=scenario_id,
                    claim=claim,
                    family=family,
                    facet_index=facet_index,
                    obligation_refs=obligation_refs or tuple(claim.obligation_refs),
                    authority_profile_refs=tuple(authority_profile_refs)
                    or tuple(claim.authority_profile_refs),
                    capability_binding=bindings_by_family.get(family),
                    family_derivation=family_derivation,
                )
                specs.append(spec)
        if not specs and family_rules:
            specs.extend(
                _spec_for_claim_family(
                    run_id=run_id,
                    scenario_id=scenario_id,
                    claim=None,
                    family=family,
                    facet_index=facet_index,
                    obligation_refs=obligation_refs,
                    authority_profile_refs=tuple(authority_profile_refs)
                    or _authority_refs_from_facets(facets),
                    capability_binding=bindings_by_family.get(family),
                    family_derivation=family_derivation,
                )
                for family in family_rules
            )
        deduped = tuple(_dedupe_specs(specs))
        return DataRequirementCompilationReport(
            run_id=run_id,
            scenario_id=scenario_id,
            specs=deduped,
            authority_boundary=data_requirement_authority_boundary(),
            metadata={
                "producer": "data_requirement_compiler",
                "reuse_classification": "wire_existing",
                "consumes": [
                    "policy_grammar.facet_snapshots_for_obligation_graph",
                    "obligation_graph.blocking_frontier",
                    "scientist.claim_decomposition.ClaimLedger",
                    "core.contracts.CapabilityResolverPort",
                ],
                "capability_index_refs": tuple(
                    dict.fromkeys(
                        binding.capability_index_ref
                        for binding in capability_bindings
                        if binding.capability_index_ref
                    )
                ),
            },
        )

    def compile_for_scenario(
        self,
        scenario: Mapping[str, Any],
    ) -> DataRequirementCompilationReport:
        """Compile data requirements for a golden scenario without reading legacy families."""

        scenario_id = _text(scenario.get("scenario_id")) or "scenario"
        text = _scenario_text(scenario)
        domain = _problem_domain_for_scenario(scenario)
        case = PolicyGrammarCompiler().compile(
            intent=PolicyGrammarIntent(
                intent_id=scenario_id,
                text=text,
                domain=domain,
            ),
            authority_profile=contracts.UniversalAuthorityProfile(
                profile_id=f"authority_profile.{scenario_id}",
                authority_type=_authority_type_for_scenario(scenario),
            ),
            concept_spine_refs=PolicyGrammarConceptSpineRefs(
                concept_spine_ref=f"concept-spine://scenario/{scenario_id}",
                jurisdiction_spine_ref=f"jurisdiction-spine://scenario/{scenario_id}",
                canonical_concept_refs=(f"concept://scenario/{scenario_id}",),
            ),
        )
        if case.facets is None:
            return self._compile_from_legacy_scenario_fallback(
                scenario=scenario,
                scenario_id=scenario_id,
            )
        facets = facet_snapshots_for_obligation_graph(case)
        graph = compile_obligation_graph(
            run_id=f"scenario-{scenario_id}",
            facets=facets,
            governed_rules=build_seed_obligation_rule_catalog().rules,
            complexity_budget=ComplexityBudget(max_frontier_items=8),
            intent_text=text,
        )
        claim_ledger = _compile_claim_decomposition(
            {
                "run_id": f"scenario-{scenario_id}",
                "intent": text,
                "facets": [
                    {
                        "facet_id": facet["facet_id"],
                        "facet_type": facet["facet_type"],
                        "value": facet["value"],
                        "concept_spine_refs": [facet["concept_ref"]],
                        "authority_profile_refs": [facet["authority_profile"]],
                    }
                    for facet in facets
                ],
                "obligations": [
                    {
                        "obligation_id": item.frontier_id,
                        "family": item.bundle_key.family,
                        "description": item.obligation_text,
                        "facet_refs": [facet["facet_id"] for facet in facets],
                        "concept_spine_refs": [facet["concept_ref"] for facet in facets],
                        "authority_profile_refs": [
                            facet["authority_profile"] for facet in facets
                        ],
                    }
                    for item in graph.blocking_frontier
                ],
                "named_alternatives": [
                    {
                        "alternative_id": f"alternative-{scenario_id}-status-quo-plus",
                        "label": "Status quo plus",
                        "description": "Incremental improvement to current practice.",
                    }
                ],
                "concept_spine_refs": [case.concept_spine_ref],
                "authority_profile_refs": [case.authority_profile.profile_id],
            }
        )
        return self.compile_for_claim_ledger(
            run_id=f"scenario-{scenario_id}",
            scenario_id=scenario_id,
            claim_ledger=claim_ledger,
            facet_snapshots=facets,
            obligation_graph=graph,
            authority_profile_refs=(case.authority_profile.profile_id,),
        )

    def _compile_from_legacy_scenario_fallback(
        self,
        *,
        scenario: Mapping[str, Any],
        scenario_id: str,
    ) -> DataRequirementCompilationReport:
        expected = scenario.get("expected_evidence_contract")
        families = (
            _text_tuple(expected.get("admissible_data_source_families"))
            if isinstance(expected, Mapping)
            else ()
        ) or ("production_data",)
        specs = tuple(
            _minimal_spec(
                scenario_id=scenario_id,
                family=family,
                source_requirement_ref=(
                    f"legacy-scenario-contract:{scenario_id}:admissible_data_source_families"
                ),
            )
            for family in families
        )
        return DataRequirementCompilationReport(
            run_id=f"scenario-{scenario_id}",
            scenario_id=scenario_id,
            specs=specs,
            metadata={
                "producer": "data_requirement_compiler",
                "fallback": "legacy_scenario_contract_when_universal_grammar_blocked",
                "missing_capability_label": "bridge_missing",
            },
        )

    def _resolver_for_compilation(self) -> CapabilityResolverPort | None:
        if self._capability_resolver is not None:
            return self._capability_resolver
        if self._require_capability_index:
            raise FileNotFoundError(
                "capability resolver is required for this data-requirement compilation"
            )
        return None


def compile_data_requirements_for_scenario(
    scenario: Mapping[str, Any],
) -> DataRequirementCompilationReport:
    """Compile data requirements for a scenario mapping."""

    return DataRequirementCompiler().compile_for_scenario(scenario)


def data_requirement_compilation_audit_surface(
    report: DataRequirementCompilationReport | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an audit/API projection of compiled data requirements."""

    model = (
        report
        if isinstance(report, DataRequirementCompilationReport)
        else DataRequirementCompilationReport.model_validate(dict(report))
    )
    payload = model.model_dump(mode="json")
    payload["surface"] = "data_requirement.audit_surface"
    payload["summary"] = {
        "requirement_count": len(model.specs),
        "claim_ids": sorted({spec.claim_id for spec in model.specs}),
        "required_data_families": sorted(
            {
                family
                for spec in model.specs
                for family in spec.required_data_families
            }
        ),
        "legacy_admissible_data_source_families": list(
            model.legacy_admissible_data_source_families
        ),
    }
    return payload


def write_data_requirement_compilation_report(
    report: DataRequirementCompilationReport | Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    """Persist a data requirement compilation report as deterministic JSON."""

    model = (
        report
        if isinstance(report, DataRequirementCompilationReport)
        else DataRequirementCompilationReport.model_validate(dict(report))
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(model.run_id)}-data-requirements.json"
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _compile_claim_decomposition(payload: Mapping[str, Any]) -> Any:
    policy_design = importlib.import_module("polisyos.scientist.policy_design")
    return policy_design.compile_claim_decomposition(payload)


def _ledger_claims(claim_ledger: object | Mapping[str, Any]) -> tuple[Any, ...]:
    raw_claims = (
        claim_ledger.get("claims")
        if isinstance(claim_ledger, Mapping)
        else getattr(claim_ledger, "claims", ())
    )
    return tuple(_claim_record_like(item) for item in raw_claims or ())


def _claim_record_like(claim: object) -> Any:
    if not isinstance(claim, Mapping):
        return claim
    return SimpleNamespace(
        claim_id=_text(claim.get("claim_id")) or "claim:unknown",
        claim_family=claim.get("claim_family"),
        claim_type=claim.get("claim_type"),
        claim_use=claim.get("claim_use"),
        text=_text(claim.get("text")),
        metadata=claim.get("metadata") if isinstance(claim.get("metadata"), Mapping) else {},
        facet_refs=_text_tuple(claim.get("facet_refs")),
        obligation_refs=_text_tuple(claim.get("obligation_refs")),
        authority_profile_refs=_text_tuple(claim.get("authority_profile_refs")),
        concept_spine_refs=_text_tuple(claim.get("concept_spine_refs")),
        source_attribution=_text_tuple(claim.get("source_attribution")),
    )


def _spec_for_claim_family(
    *,
    run_id: str,
    scenario_id: str | None,
    claim: Any | None,
    family: str,
    facet_index: Mapping[str, Mapping[str, Any]],
    obligation_refs: Sequence[str],
    authority_profile_refs: Sequence[str],
    capability_binding: CapabilityBindingLike | None = None,
    family_derivation: str | None = None,
) -> DataRequirementSpec:
    claim_id = claim.claim_id if claim is not None else f"claim:{family}"
    facets = _facets_for_claim(claim, facet_index=facet_index)
    scope_facets = dict(facet_index)
    scope_facets.update(facets)
    scope = _scope_from_facets(scope_facets)
    concept_refs = _concept_refs_from_facets(facets) or tuple(
        claim.concept_spine_refs if claim else ()
    )
    authority_refs = tuple(authority_profile_refs) or tuple(
        claim.authority_profile_refs if claim else ()
    )
    if not concept_refs:
        concept_refs = ("concept://data-requirement/fallback",)
    if not authority_refs:
        authority_refs = ("authority_profile.data_requirement.default",)
    metadata: dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "family_derivation": family_derivation or _family_derivation_label(family),
        "scenario_family_authority_status": "sunset_projection_only",
        "may_not_use_for": [
            "scenario_family_authority_lookup",
            "source_family_authority_decision_path",
        ],
        "compatibility_projection": {
            "source_family": family,
            "replacement": "capability_index_v1",
        },
    }
    if capability_binding is not None:
        metadata["capability_binding"] = _capability_binding_metadata(capability_binding)
        metadata["construct_ref"] = capability_binding.construct_ref
        metadata["capability_index_ref"] = capability_binding.capability_index_ref
        metadata["binding_status"] = capability_binding.status
    return DataRequirementSpec(
        requirement_id=_requirement_id(
            run_id=run_id,
            scenario_id=scenario_id,
            claim_id=claim_id,
            family=family,
        ),
        claim_id=claim_id,
        claim_family=_enum_value(getattr(claim, "claim_family", None)),
        claim_type=_enum_value(getattr(claim, "claim_type", None)),
        claim_use=_enum_value(getattr(claim, "claim_use", None)),
        required_data_families=(family,),
        scope=scope,
        recency_horizon=_recency_horizon(scope),
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(
            min_quality_score=0.8,
            min_completeness=0.95,
            required_quality_refs=("quality_assertion_refs", "construct_validity_refs"),
        ),
        missingness_tolerance=0.05,
        transformation_tolerance="traceable",
        admissibility_predicates=_ADMISSIBILITY_PREDICATES,
        mandatory_facets=_MANDATORY_FACETS,
        facet_refs=tuple(facets),
        obligation_refs=tuple(obligation_refs),
        concept_spine_refs=concept_refs,
        authority_profile_refs=tuple(authority_refs),
        source_requirement_refs=tuple(claim.source_attribution if claim else ()),
        metadata=metadata,
    )


def _minimal_spec(
    *,
    scenario_id: str,
    family: str,
    source_requirement_ref: str,
) -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id=f"data-requirement:scenario-{scenario_id}:{family}",
        claim_id=f"scenario:{scenario_id}:legacy-data-claim",
        claim_family="context_only",
        claim_type="source_quality",
        claim_use="decision_support",
        required_data_families=(family,),
        scope=DataRequirementScope(
            population="scenario_population",
            geography="scenario_geography",
            time="scenario_time",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(),
        missingness_tolerance=0.05,
        transformation_tolerance="traceable",
        admissibility_predicates=_ADMISSIBILITY_PREDICATES,
        mandatory_facets=_MANDATORY_FACETS,
        facet_refs=("legacy_scenario_contract",),
        obligation_refs=("legacy_scenario_contract",),
        concept_spine_refs=(f"concept://scenario/{scenario_id}",),
        authority_profile_refs=(f"authority_profile.{scenario_id}",),
        source_requirement_refs=(source_requirement_ref,),
    )


def _capability_bindings_for_requirements(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    obligation_graph: object | Mapping[str, Any] | None,
    scenario_id: str | None,
    scope: DataRequirementScope,
    resolver: CapabilityResolverPort | None = None,
) -> tuple[CapabilityBindingLike, ...]:
    constructs = _required_constructs_from_obligation_graph(obligation_graph)
    if not constructs:
        constructs = _required_constructs_from_semantics(
            facets=facets,
            claims=claims,
            scenario_id=scenario_id,
        )
    if not constructs:
        return ()
    if resolver is None:
        return ()
    bindings: list[CapabilityBindingLike] = []
    for construct in constructs:
        query = RequirementToCapabilityQuery(
            requirement_id=f"data-requirement:{_slug(scenario_id or 'run')}:{construct}",
            construct=construct,
            entity_scope=_entity_scope_for_construct(construct),
            population_filter=_population_filter_for_construct(construct, scope),
            geography=scope.jurisdiction or scope.geography,
            time_window={"start": _time_start_for_scope(scope), "end": None},
            authority_level="governed_pilot",
            claim_use="claim_evidence_closeout",
            required_evidence_modes=(
                "observed",
                "derived",
                "proxy_observational",
                "scholarly_causal_support",
            ),
            forbidden_evidence_modes=("simulation_only", "candidate_unverified"),
            source_family_alias=legacy_family_for_construct(construct),
        )
        bindings.append(resolver.resolve(query))
    return tuple(bindings)


def _required_constructs_from_obligation_graph(
    obligation_graph: object | Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if obligation_graph is None:
        return ()
    frontier = getattr(obligation_graph, "blocking_frontier", None)
    if frontier is None and isinstance(obligation_graph, Mapping):
        frontier = obligation_graph.get("blocking_frontier")
    constructs: list[str] = []
    for item in frontier or ():
        metadata = (
            item.get("metadata")
            if isinstance(item, Mapping)
            else getattr(item, "metadata", {})
        )
        if not isinstance(metadata, Mapping):
            continue
        for key in ("required_evidence_constructs", "construct_refs", "construct_ref"):
            for construct in _text_tuple(metadata.get(key)):
                normalized = construct.removeprefix("construct:")
                if normalized and normalized not in constructs:
                    constructs.append(normalized)
        for key in (
            "legacy_evidence_family_alias",
            "data_family",
            "evidence_family",
            "required_evidence_family",
        ):
            token = _text(metadata.get(key))
            mapped = construct_for_legacy_family(token) if token else None
            if mapped and mapped not in constructs:
                constructs.append(mapped)
    return tuple(constructs)


def _required_constructs_from_semantics(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    scenario_id: str | None,
) -> tuple[str, ...]:
    values = {str(facet.get("facet_type")): _enum_text(facet.get("value")) for facet in facets}
    haystack = " ".join(
        [
            *values.values(),
            *[claim.text for claim in claims],
            *[
                " ".join(str(value) for value in claim.metadata.values())
                for claim in claims
                if isinstance(claim.metadata, Mapping)
            ],
            scenario_id or "",
        ]
    ).casefold()
    constructs: list[str] = []

    def add_if(condition: bool, construct: str) -> None:
        if condition and construct not in constructs:
            constructs.append(construct)

    add_if(values.get("population_predicate") == "msmes", "firm_survival")
    add_if(
        values.get("instrument_type") == "credit"
        or values.get("delivery_channel") == "credit_registry",
        "credit_program_enrollment",
    )
    add_if(
        "displaced" in haystack
        or "displacement" in haystack
        or values.get("geography_predicate") == "displacement_affected",
        "regional_displacement_pressure",
    )
    add_if(
        values.get("population_predicate") == "msmes"
        and values.get("instrument_type") == "credit"
        and values.get("geography_predicate") == "state_or_region",
        "regional_displacement_pressure",
    )
    add_if(
        "housing" in haystack
        or "rent" in haystack
        or "voucher" in haystack
        or values.get("population_predicate") == "low_income_renters",
        "housing_rent_burden",
    )
    add_if(
        values.get("instrument_type") == "subsidy"
        or "means-tested" in haystack
        or "means tested" in haystack,
        "program_participation_rate",
    )
    return tuple(constructs)


def _entity_scope_for_construct(construct: str) -> str:
    return {
        "firm_survival": "firm",
        "credit_program_enrollment": "firm_or_program",
        "regional_displacement_pressure": "region",
    }.get(construct.removeprefix("construct:"), "entity")


def _population_filter_for_construct(
    construct: str,
    scope: DataRequirementScope,
) -> dict[str, str]:
    return {
        "regional_displacement_pressure": {"type": "displacement_affected_regions"},
    }.get(construct.removeprefix("construct:"), {"type": scope.population})


def _time_start_for_scope(scope: DataRequirementScope) -> str | None:
    if scope.time in {"annual", "phased_rollout", "event_triggered"}:
        return "2022-02-01"
    return None


def _capability_binding_metadata(binding: CapabilityBindingLike) -> dict[str, Any]:
    return {
        "schema_version": binding.schema_version,
        "rule_version_ref": binding.rule_version_ref,
        "requirement_id": binding.requirement_id,
        "status": binding.status,
        "selected_capability_ref": binding.selected_capability_ref,
        "construct_ref": binding.construct_ref,
        "capability_index_ref": binding.capability_index_ref,
        "authority_level": binding.authority_level,
        "authority_envelope_result": binding.authority_envelope_result,
        "binding_reasons": list(binding.binding_reasons),
        "blocked_reasons": list(binding.blocked_reasons),
        "limitations": list(binding.limitations),
        "acquisition_strategies": list(binding.acquisition_strategies),
        "rejected_alternatives": list(binding.rejected_alternatives),
        "conflict_markers": list(binding.conflict_markers),
    }


def _data_families_from_obligation_graph(
    obligation_graph: object | Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Extract data source families from W6.C blocking frontier metadata.

    Track A1 introduces this primary path. Vertical governance rules seeded
    in Track B2 carry a ``data_family`` (or ``evidence_family``) field in the
    rule logic; the obligation-graph compiler surfaces those through the
    frontier item ``metadata`` mapping. When the W6.B catalog has no vertical
    rule for a given case, this function returns an empty tuple and the
    caller falls back to the legacy heuristic (see
    ``_required_data_families_from_heuristic``).
    """

    if obligation_graph is None:
        return ()
    frontier = getattr(obligation_graph, "blocking_frontier", None)
    if frontier is None and isinstance(obligation_graph, Mapping):
        frontier = obligation_graph.get("blocking_frontier")
    if not frontier:
        return ()
    families: list[str] = []
    for item in frontier:
        family_token = _data_family_token_from_frontier_item(item)
        if family_token and family_token not in families:
            families.append(family_token)
    return _ordered_data_families(families)


def _data_family_token_from_frontier_item(item: Any) -> str | None:
    bundle_key = getattr(item, "bundle_key", None)
    bundle_family = (
        getattr(bundle_key, "family", None)
        if bundle_key is not None
        else None
    )
    if isinstance(item, Mapping):
        bundle_family = bundle_family or _nested(item, ("bundle_key", "family"))
        metadata = item.get("metadata") or {}
    else:
        metadata = getattr(item, "metadata", {}) or {}
    if _normalised_family(bundle_family) != "data":
        return None
    if isinstance(metadata, Mapping):
        for key in ("data_family", "evidence_family"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return _slug_family(value)
    return None


def _nested(payload: Mapping[str, Any], path: Sequence[str]) -> Any:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, Mapping):
            return None
        cursor = cursor.get(key)
    return cursor


def _normalised_family(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    return text or None


def _slug_family(value: str) -> str:
    return "_".join(value.strip().casefold().replace("-", "_").split())


def _ordered_data_families(families: Sequence[str]) -> tuple[str, ...]:
    priority = {family: index for index, family in enumerate(_DATA_FAMILY_ORDER)}
    return tuple(
        sorted(
            families,
            key=lambda family: (priority.get(family, len(priority)), family),
        )
    )


def _required_data_families_from_heuristic(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    scenario_id: str | None,
) -> tuple[str, ...]:
    values = {str(facet.get("facet_type")): _enum_text(facet.get("value")) for facet in facets}
    haystack = " ".join(
        [
            *values.values(),
            *[claim.text for claim in claims],
            *[
                " ".join(str(value) for value in claim.metadata.values())
                for claim in claims
            if isinstance(claim.metadata, Mapping)
            ],
            scenario_id or "",
        ]
    ).casefold()
    families: list[str] = []

    def add_if(condition: bool, family: str) -> None:
        if condition and family not in families:
            families.append(family)

    add_if(values.get("population_predicate") == "msmes", "production_msme_panel")
    add_if(
        values.get("instrument_type") == "credit"
        or values.get("delivery_channel") == "credit_registry",
        "credit_program_registry",
    )
    add_if(
        "displaced" in haystack
        or "displacement" in haystack
        or values.get("geography_predicate") == "displacement_affected",
        "regional_displacement_indicators",
    )
    add_if(
        values.get("population_predicate") == "msmes"
        and values.get("instrument_type") == "credit"
        and values.get("geography_predicate") == "state_or_region",
        "regional_displacement_indicators",
    )
    add_if(values.get("population_predicate") == "workers", "labor_force_panel")
    add_if(values.get("population_predicate") == "workers", "employment_registry")
    add_if(
        values.get("risk_facet") in {"equity_harm", "fairness_threshold_reversal"}
        and values.get("geography_predicate") in {"state_or_region", "rural", "municipal"}
        and not (
            values.get("population_predicate") == "msmes"
            and values.get("instrument_type") == "credit"
        ),
        "regional_vulnerability_index",
    )
    add_if(values.get("instrument_type") == "tax", "tax_admin_panel")
    add_if(values.get("instrument_type") == "tax", "fiscal_revenue_series")
    add_if(
        values.get("instrument_type") == "subsidy"
        and values.get("population_predicate") == "low_income_renters",
        "housing_beneficiary_registry",
    )
    add_if(
        values.get("instrument_type") == "subsidy"
        and values.get("population_predicate") == "low_income_renters",
        "rent_market_panel",
    )
    add_if(
        values.get("delivery_channel") == "public_service"
        and values.get("population_predicate") in {"children", "patients"},
        "service_delivery_registry",
    )
    add_if(
        "vaccination" in haystack or "vaccine" in haystack,
        "vaccination_coverage_panel",
    )
    add_if(values.get("geography_predicate") == "rural", "rural_access_indicators")
    return tuple(families)


def _claim_requires_data(claim: Any) -> bool:
    claim_use = _enum_value(claim.claim_use)
    family = _enum_value(claim.claim_family)
    claim_type = _enum_value(claim.claim_type)
    if claim_use == "context-only" or family == "context_only":
        return False
    return (
        claim_use in _DECISION_CLAIM_USES
        or family in _DECISION_CLAIM_FAMILIES
        or claim_type in {"causal", "distributional", "welfare", "forecast", "implementation"}
    )


def _facet_index(facets: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(facet.get("facet_id")): dict(facet) for facet in facets if facet.get("facet_id")}


def _facets_for_claim(
    claim: Any | None,
    *,
    facet_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if claim is None:
        return dict(facet_index)
    selected = {
        facet_ref: facet_index[facet_ref]
        for facet_ref in claim.facet_refs
        if facet_ref in facet_index
    }
    return selected or dict(facet_index)


def _scope_from_facets(facets: Mapping[str, Mapping[str, Any]]) -> DataRequirementScope:
    by_type = {str(facet.get("facet_type")): facet for facet in facets.values()}
    population = _enum_text(by_type.get("population_predicate", {}).get("value")) or "population"
    geography = _enum_text(by_type.get("geography_predicate", {}).get("value")) or "geography"
    time = _enum_text(by_type.get("time_predicate", {}).get("value")) or "time"
    return DataRequirementScope(
        population=population,
        geography=geography,
        time=time,
        time_role="observation_time",
        jurisdiction=_jurisdiction_for_geography(geography),
    )


def _recency_horizon(scope: DataRequirementScope) -> str:
    if scope.time in {"single_period", "annual", "phased_rollout", "event_triggered"}:
        return "P90D"
    return "P180D"


def _concept_refs_from_facets(facets: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    refs = [_text(facet.get("concept_ref")) for facet in facets.values()]
    return tuple(dict.fromkeys(ref for ref in refs if ref))


def _authority_refs_from_facets(facets: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    refs = [_text(facet.get("authority_profile")) for facet in facets]
    return tuple(dict.fromkeys(ref for ref in refs if ref))


def _data_obligation_refs(obligation_graph: object | Mapping[str, Any] | None) -> tuple[str, ...]:
    if obligation_graph is None:
        return ()
    frontier = (
        getattr(obligation_graph, "blocking_frontier", None)
        if not isinstance(obligation_graph, Mapping)
        else obligation_graph.get("blocking_frontier")
    )
    refs: list[str] = []
    for item in frontier or ():
        family = getattr(getattr(item, "bundle_key", None), "family", None)
        if family is None and isinstance(item, Mapping):
            bundle_key = item.get("bundle_key")
            family = bundle_key.get("family") if isinstance(bundle_key, Mapping) else None
        if _enum_text(family) != "data":
            continue
        refs.append(
            _text(getattr(item, "frontier_id", None))
            or _text(item.get("frontier_id") if isinstance(item, Mapping) else None)
        )
    return tuple(ref for ref in refs if ref)


def _dedupe_specs(specs: Sequence[DataRequirementSpec]) -> list[DataRequirementSpec]:
    seen: set[tuple[str, str]] = set()
    deduped: list[DataRequirementSpec] = []
    for spec in specs:
        key = (spec.claim_id, spec.required_data_families[0])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(spec)
    return deduped


def _requirement_id(
    *,
    run_id: str,
    scenario_id: str | None,
    claim_id: str,
    family: str,
) -> str:
    scope = scenario_id or run_id
    digest = hashlib.sha256(f"{scope}:{claim_id}:{family}".encode()).hexdigest()[:12]
    return f"data-requirement:{scope}:{claim_id}:{family}:{digest}"


def _scenario_text(scenario: Mapping[str, Any]) -> str:
    context = scenario.get("context") if isinstance(scenario.get("context"), Mapping) else {}
    metadata = (
        scenario.get("scenario_evidence_contract")
        if isinstance(scenario.get("scenario_evidence_contract"), Mapping)
        else {}
    )
    expected = (
        scenario.get("expected_evidence_contract")
        if isinstance(scenario.get("expected_evidence_contract"), Mapping)
        else {}
    )
    parts = [
        scenario.get("scenario_id"),
        scenario.get("request"),
        scenario.get("title"),
        scenario.get("domain_hint"),
        *[_token_text(context.get(key)) for key in sorted(context) if key.startswith("query_")],
        context.get("policy_domain"),
        context.get("target_population"),
        context.get("country"),
        _token_text(metadata.get("authority_scope")),
        _token_text(metadata.get("instrument_type")),
        _token_text(metadata.get("beneficiary_class")),
        _token_text(expected.get("normative_fact_classes")),
        _token_text(expected.get("foundry_method_expectations")),
        _token_text(expected.get("conflict_checks")),
        _token_text(expected.get("unacceptable_recommendations")),
        "annual",
    ]
    return " ".join(_text(part) for part in parts if _text(part)) or "compile policy data needs"


def _token_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_token_text(item) for item in value)
    return str(value).replace("_", " ").replace("-", " ")


def _problem_domain_for_scenario(scenario: Mapping[str, Any]) -> governance.ProblemDomain:
    haystack = _scenario_text(scenario).casefold()
    if any(token in haystack for token in ("health", "clinic", "vaccination", "medicine")):
        return governance.ProblemDomain.HEALTHCARE
    if any(token in haystack for token in ("housing", "rent", "benefit", "social")):
        return governance.ProblemDomain.SOCIAL
    return governance.ProblemDomain.FISCAL


def _authority_type_for_scenario(
    scenario: Mapping[str, Any],
) -> governance.PolicyLayerLevel:
    context = scenario.get("context") if isinstance(scenario.get("context"), Mapping) else {}
    text = " ".join((_scenario_text(scenario), _text(context.get("authority_type")))).casefold()
    if "national" in text or "ukraine" in text:
        return governance.PolicyLayerLevel.FEDERAL
    if "oblast" in text or "region" in text:
        return governance.PolicyLayerLevel.STATE
    return governance.PolicyLayerLevel.LOCAL


def _jurisdiction_for_geography(geography: str) -> str | None:
    if geography in {"national", "state_or_region", "municipal", "displacement_affected"}:
        return "UA"
    return None


def _family_derivation_label(family: str) -> str:
    return {
        "production_msme_panel": "population_predicate:msmes",
        "credit_program_registry": "instrument_or_delivery:credit",
        "regional_displacement_indicators": "scope_or_claim_text:displacement",
    }.get(family, "facet_claim_composition")


def _enum_value(value: object) -> str | None:
    text = _enum_text(value)
    return text or None


def _enum_text(value: object) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", value)
    return str(enum_value).strip()


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    return tuple(
        dict.fromkeys(
            text
            for item in raw_values
            if (text := _text(item))
        )
    )


def _digest(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()[:16]


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "DataRequirementCompiler",
    "compile_data_requirements_for_scenario",
    "data_requirement_compilation_audit_surface",
    "write_data_requirement_compilation_report",
]
