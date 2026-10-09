"""Deterministic compiler from claim/facet obligations to DataRequirementSpec."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from polisyos.core import contracts
from polisyos.ir import governance
from polisyos.obligation_graph import (
    ComplexityBudget,
    ObligationGraph,
    compile_obligation_graph,
)
from polisyos.obligation_rules import (
    ObligationRuleCatalog,
    build_seed_obligation_rule_catalog,
    select_governed_rules,
)
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)

if TYPE_CHECKING:
    from datetime import datetime

from ._impl.models import (
    DataQualityMinimums,
    DataRequirementCompilationReport,
    DataRequirementScope,
    DataRequirementSpec,
    data_requirement_authority_boundary,
)

UniversalAuthorityProfile = contracts.UniversalAuthorityProfile


@dataclass(frozen=True)
class DataRequirementObligationCompilation:
    """Existing policy-grammar and obligation-owner outputs for one requirement basis."""

    case: contracts.UniversalPolicyDesignCase
    facets: tuple[dict[str, object], ...] | None
    rule_catalog: ObligationRuleCatalog | None
    obligation_graph: ObligationGraph | None


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
_DATA_REQUIREMENT_FAMILY_FALLBACK_ENV = "POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED"
# POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED default false.
_DATA_REQUIREMENT_FAMILY_FALLBACK_DEFAULT = "false"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GOVERNED_CAPABILITY_ROWS_PATH = (
    _REPO_ROOT / "architecture/policy_design_case/layer2_s3_governed_capability_rows.json"
)


@dataclass(frozen=True)
class _ScenarioScopeProfile:
    """Explicit, versioned scope context owned by the scenario adapter."""

    profile_id: str
    jurisdiction: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    required_constructs: tuple[str, ...] = ()
    candidate_construct_proposals: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ScenarioAdapterInput:
    """Semantic inputs handed from a scenario mapping to the compiler."""

    scenario_id: str
    text: str
    domain: governance.ProblemDomain
    authority_type: governance.PolicyLayerLevel
    scope_profile: _ScenarioScopeProfile | None = None


@dataclass(frozen=True)
class _ConstructResolutionInputs:
    """Separate declared authority inputs from candidate semantic proposals."""

    required_constructs: tuple[str, ...] = ()
    candidate_construct_proposals: tuple[str, ...] = ()


def _data_requirement_family_fallback_enabled() -> bool:
    raw = os.environ.get(
        _DATA_REQUIREMENT_FAMILY_FALLBACK_ENV,
        _DATA_REQUIREMENT_FAMILY_FALLBACK_DEFAULT,
    )
    return str(raw).strip().casefold() in {"1", "true", "yes", "on"}


def _load_governed_scenario_family_construct_rows() -> tuple[
    contracts.ScenarioFamilyConstructRow,
    ...,
]:
    if not _GOVERNED_CAPABILITY_ROWS_PATH.exists():
        return ()
    try:
        payload = json.loads(_GOVERNED_CAPABILITY_ROWS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()
    rows = payload.get("scenario_family_construct_rows") if isinstance(payload, Mapping) else ()
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes | bytearray):
        return ()
    normalized: list[contracts.ScenarioFamilyConstructRow] = []
    for row in rows:
        try:
            normalized.append(contracts.ScenarioFamilyConstructRow.model_validate(row))
        except (TypeError, ValueError):
            continue
    return tuple(normalized)


class DataRequirementCompiler:
    """Compile claim-bound Fabric data needs from W6 facets and claim records."""

    def __init__(
        self,
        *,
        capability_resolver: CapabilityResolverPort | None = None,
        require_capability_index: bool = False,
        scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows | None = None,
    ) -> None:
        """Initialize the compiler with optional release-backed capability resolution.

        Args:
            capability_resolver: Already-loaded resolver supplied by orchestration
                code that owns capability-index loading.
            require_capability_index: When true, fail closed unless a resolver is
                injected by the caller.
            scenario_family_construct_rows: Optional governed source-family rows.
                When omitted, the compiler reads the persisted governed capability
                row artifact instead of falling back to Python literals.
        """

        self._capability_resolver = capability_resolver
        self._require_capability_index = require_capability_index
        self._scenario_family_construct_rows = tuple(
            contracts.ScenarioFamilyConstructRow.model_validate(row)
            for row in (
                scenario_family_construct_rows
                if scenario_family_construct_rows is not None
                else _load_governed_scenario_family_construct_rows()
            )
        )

    def compile_for_claim_ledger(
        self,
        *,
        run_id: str,
        claim_ledger: object | Mapping[str, Any],
        facet_snapshots: Sequence[Mapping[str, Any]],
        obligation_graph: object | Mapping[str, Any] | None = None,
        scenario_id: str | None = None,
        authority_profile_refs: Sequence[str] = (),
        scope_profile: _ScenarioScopeProfile | None = None,
    ) -> DataRequirementCompilationReport:
        """Compile data requirements for decision-bearing claims.

        Args:
            run_id: Runtime run/case identifier.
            claim_ledger: W6.D claim ledger or JSON payload.
            facet_snapshots: W6.A parallel facet snapshot interface.
            obligation_graph: Optional W6.C graph used for obligation refs.
            scenario_id: Optional scenario id for legacy bridge projections.
            authority_profile_refs: Additional authority refs from the run carrier.
            scope_profile: Explicit named-pilot scope context from the scenario
                adapter. Generic callers leave this unset.

        Returns:
            A claim-bound data requirement compilation report.
        """

        claims = _ledger_claims(claim_ledger)
        facets = tuple(dict(facet) for facet in facet_snapshots)
        facet_index = _facet_index(facets)
        resolution_inputs = _construct_resolution_inputs(
            facets=facets,
            claims=claims,
            obligation_graph=obligation_graph,
            scenario_id=scenario_id,
            scenario_family_construct_rows=self._scenario_family_construct_rows,
            declared_constructs=(scope_profile.required_constructs if scope_profile else ()),
            candidate_construct_proposals=(
                scope_profile.candidate_construct_proposals if scope_profile else ()
            ),
        )
        scope = _scope_from_facets(facet_index, scope_profile=scope_profile)
        capability_bindings = _capability_bindings_for_requirements(
            facets=facets,
            claims=claims,
            obligation_graph=obligation_graph,
            scenario_id=scenario_id,
            scope=scope,
            resolver=self._resolver_for_compilation(),
            scenario_family_construct_rows=self._scenario_family_construct_rows,
            scope_profile=scope_profile,
            resolution_inputs=resolution_inputs,
        )
        family_rules = tuple(
            dict.fromkeys(
                family
                for family in (
                    legacy_family_for_construct(
                        binding.construct_ref or "",
                        rows=self._scenario_family_construct_rows,
                    )
                    for binding in capability_bindings
                    if binding.construct_ref
                )
                if family
            )
        )
        bindings_by_family = {
            family: binding
            for binding in capability_bindings
            if binding.construct_ref
            for family in (
                legacy_family_for_construct(
                    binding.construct_ref or "",
                    rows=self._scenario_family_construct_rows,
                ),
            )
            if family
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
                    scope_profile=scope_profile,
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
                    scope_profile=scope_profile,
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
                "candidate_construct_proposals": resolution_inputs.candidate_construct_proposals,
            },
        )

    def compile_obligation_basis(
        self,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
        run_id: str,
        generated_at: datetime,
        intent_text: str,
    ) -> DataRequirementObligationCompilation:
        """Compile one typed W6.A basis through the existing W6.B/W6.C owners.

        The returned models are the objects produced by their owning compilers.
        A candidate or blocked grammar case is retained with no downstream
        compilation, so callers preserve its status and refuse downstream use.
        This stage establishes compilation only; it does not admit source
        authority or promote a resulting requirement.
        """
        case = PolicyGrammarCompiler().compile(
            intent=intent,
            authority_profile=authority_profile,
            concept_spine_refs=concept_spine_refs,
        )
        if case.status in {"blocked", "candidate_unverified"} or case.facets is None:
            return DataRequirementObligationCompilation(
                case=case,
                facets=None,
                rule_catalog=None,
                obligation_graph=None,
            )

        facets = facet_snapshots_for_obligation_graph(case)
        rule_catalog = build_seed_obligation_rule_catalog()
        obligation_graph = compile_obligation_graph(
            run_id=run_id,
            facets=facets,
            governed_rules=select_governed_rules(rule_catalog),
            generated_at=generated_at,
            intent_text=intent_text,
        )
        return DataRequirementObligationCompilation(
            case=case,
            facets=facets,
            rule_catalog=rule_catalog,
            obligation_graph=obligation_graph,
        )

    def compile_for_scenario(
        self,
        scenario: Mapping[str, Any],
    ) -> DataRequirementCompilationReport:
        """Compile data requirements for a golden scenario without reading legacy families."""

        adapter_input = _scenario_adapter_input(scenario)
        scenario_id = adapter_input.scenario_id
        text = adapter_input.text
        domain = adapter_input.domain
        case = PolicyGrammarCompiler().compile(
            intent=PolicyGrammarIntent(
                intent_id=scenario_id,
                text=text,
                domain=domain,
            ),
            authority_profile=contracts.UniversalAuthorityProfile(
                profile_id=f"authority_profile.{scenario_id}",
                authority_type=adapter_input.authority_type,
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
                scope_profile=adapter_input.scope_profile,
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
                        "authority_profile_refs": [facet["authority_profile"] for facet in facets],
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
            scope_profile=adapter_input.scope_profile,
        )

    def _compile_from_legacy_scenario_fallback(
        self,
        *,
        scenario: Mapping[str, Any],
        scenario_id: str,
        scope_profile: _ScenarioScopeProfile | None = None,
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
                scope_profile=scope_profile,
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
            {family for spec in model.specs for family in spec.required_data_families}
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
    scope_profile: _ScenarioScopeProfile | None = None,
) -> DataRequirementSpec:
    claim_id = claim.claim_id if claim is not None else f"claim:{family}"
    facets = _facets_for_claim(claim, facet_index=facet_index)
    scope_facets = dict(facet_index)
    scope_facets.update(facets)
    scope = _scope_from_facets(scope_facets, scope_profile=scope_profile)
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
    if scope_profile is not None:
        metadata["scope_profile"] = {
            "profile_id": scope_profile.profile_id,
            "jurisdiction": scope_profile.jurisdiction,
            "time_window": {
                "start": scope_profile.time_start,
                "end": scope_profile.time_end,
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
    scope_profile: _ScenarioScopeProfile | None = None,
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
            jurisdiction=scope_profile.jurisdiction if scope_profile else None,
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
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows = (),
    scope_profile: _ScenarioScopeProfile | None = None,
    resolution_inputs: _ConstructResolutionInputs | None = None,
) -> tuple[CapabilityBindingLike, ...]:
    rows = tuple(
        contracts.ScenarioFamilyConstructRow.model_validate(row)
        for row in scenario_family_construct_rows
    )
    inputs = resolution_inputs or _construct_resolution_inputs(
        facets=facets,
        claims=claims,
        obligation_graph=obligation_graph,
        scenario_id=scenario_id,
        scenario_family_construct_rows=rows,
        declared_constructs=(scope_profile.required_constructs if scope_profile else ()),
        candidate_construct_proposals=(
            scope_profile.candidate_construct_proposals if scope_profile else ()
        ),
    )
    constructs = inputs.required_constructs
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
            time_window={
                "start": _time_start_for_scope(scope, scope_profile=scope_profile),
                "end": _time_end_for_scope(scope, scope_profile=scope_profile),
            },
            authority_level="governed_pilot",
            claim_use="claim_evidence_closeout",
            required_evidence_modes=(
                "observed",
                "derived",
                "proxy_observational",
                "scholarly_causal_support",
            ),
            forbidden_evidence_modes=("simulation_only", "candidate_unverified"),
            source_family_alias=legacy_family_for_construct(construct, rows=rows),
        )
        bindings.append(resolver.resolve(query))
    return tuple(bindings)


def _construct_resolution_inputs(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    obligation_graph: object | Mapping[str, Any] | None,
    scenario_id: str | None,
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows = (),
    declared_constructs: Sequence[str] = (),
    candidate_construct_proposals: Sequence[str] = (),
) -> _ConstructResolutionInputs:
    """Build the explicit authority set and retain semantic proposals separately."""

    rows = tuple(
        contracts.ScenarioFamilyConstructRow.model_validate(row)
        for row in scenario_family_construct_rows
    )
    graph_constructs = _required_constructs_from_obligation_graph(
        obligation_graph,
        scenario_family_construct_rows=rows,
    )
    declared = _required_constructs_from_semantics(
        facets=facets,
        claims=claims,
        scenario_id=scenario_id,
    )
    explicit = _normalised_construct_refs(declared_constructs)
    required_constructs = graph_constructs or explicit or declared
    proposals = tuple(
        dict.fromkeys(
            (
                *_normalised_construct_refs(candidate_construct_proposals),
                *_construct_proposals_from_semantics(facets=facets, claims=claims),
            )
        )
    )
    return _ConstructResolutionInputs(
        required_constructs=required_constructs,
        candidate_construct_proposals=proposals,
    )


def _required_constructs_from_obligation_graph(
    obligation_graph: object | Mapping[str, Any] | None,
    *,
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows = (),
) -> tuple[str, ...]:
    if obligation_graph is None:
        return ()
    frontier = getattr(obligation_graph, "blocking_frontier", None)
    if frontier is None and isinstance(obligation_graph, Mapping):
        frontier = obligation_graph.get("blocking_frontier")
    constructs: list[str] = []
    for item in frontier or ():
        metadata = (
            item.get("metadata") if isinstance(item, Mapping) else getattr(item, "metadata", {})
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
            mapped = (
                construct_for_legacy_family(token, rows=scenario_family_construct_rows)
                if token
                else None
            )
            if mapped and mapped not in constructs:
                constructs.append(mapped)
    return tuple(constructs)


def _required_constructs_from_semantics(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    scenario_id: str | None,
) -> tuple[str, ...]:
    """Return only explicitly declared construct refs from semantic records.

    Text and scenario identifiers may produce candidate proposals, but they do
    not establish the construct set sent to the capability resolver.
    """

    del scenario_id
    constructs: list[str] = []
    for facet in facets:
        if not isinstance(facet, Mapping):
            continue
        for key in (
            "required_evidence_constructs",
            "required_constructs",
            "explicit_constructs",
            "construct_refs",
            "construct_ref",
        ):
            for construct in _normalised_construct_refs(facet.get(key)):
                if construct not in constructs:
                    constructs.append(construct)
    for claim in claims:
        metadata = getattr(claim, "metadata", {})
        sources: tuple[object, ...] = (metadata,)
        if isinstance(claim, Mapping):
            sources = (claim, metadata)
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            for key in (
                "required_evidence_constructs",
                "required_constructs",
                "explicit_constructs",
                "construct_refs",
                "construct_ref",
            ):
                for construct in _normalised_construct_refs(source.get(key)):
                    if construct not in constructs:
                        constructs.append(construct)
    return tuple(constructs)


def _construct_proposals_from_semantics(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
) -> tuple[str, ...]:
    """Discover bounded lexical candidates without granting resolver authority."""

    values = {str(facet.get("facet_type")): _enum_text(facet.get("value")) for facet in facets}
    words = _semantic_words(facets=facets, claims=claims)
    proposals: list[str] = []

    def add_if(condition: bool, construct: str) -> None:
        if condition and construct not in proposals:
            proposals.append(construct)

    add_if(values.get("population_predicate") == "msmes", "firm_survival")
    add_if(
        values.get("instrument_type") == "credit"
        or values.get("delivery_channel") == "credit_registry",
        "credit_program_enrollment",
    )
    add_if(
        bool(words.intersection({"displaced", "displacement"}))
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
        bool(words.intersection({"housing", "rent", "voucher"}))
        or values.get("population_predicate") == "low_income_renters",
        "housing_rent_burden",
    )
    add_if(
        values.get("instrument_type") == "subsidy" or {"means", "tested"}.issubset(words),
        "program_participation_rate",
    )
    return tuple(proposals)


def _semantic_words(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
) -> set[str]:
    values = [_enum_text(facet.get("value")) for facet in facets]
    claim_values: list[str] = []
    for claim in claims:
        claim_values.append(_text(getattr(claim, "text", None)))
        metadata = getattr(claim, "metadata", {})
        if isinstance(metadata, Mapping):
            claim_values.extend(_text(value) for value in metadata.values())
    return {
        word.strip(".,;:!?()[]{}\"'")
        for value in (*values, *claim_values)
        for word in _token_text(value).casefold().replace("-", " ").split()
        if word.strip(".,;:!?()[]{}\"'")
    }


def _normalised_construct_refs(value: object) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            normalized
            for raw in _text_tuple(value)
            if (normalized := raw.removeprefix("construct:"))
        )
    )


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


def _time_start_for_scope(
    scope: DataRequirementScope,
    *,
    scope_profile: _ScenarioScopeProfile | None = None,
) -> str | None:
    """Return only an interval explicitly supplied by a named scope profile."""

    del scope
    return scope_profile.time_start if scope_profile else None


def _time_end_for_scope(
    scope: DataRequirementScope,
    *,
    scope_profile: _ScenarioScopeProfile | None = None,
) -> str | None:
    """Return the named profile's explicit interval end, if present."""

    del scope
    return scope_profile.time_end if scope_profile else None


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


def _scope_from_facets(
    facets: Mapping[str, Mapping[str, Any]],
    *,
    scope_profile: _ScenarioScopeProfile | None = None,
) -> DataRequirementScope:
    by_type = {str(facet.get("facet_type")): facet for facet in facets.values()}
    population = _enum_text(by_type.get("population_predicate", {}).get("value")) or "population"
    geography = _enum_text(by_type.get("geography_predicate", {}).get("value")) or "geography"
    time = _enum_text(by_type.get("time_predicate", {}).get("value")) or "time"
    return DataRequirementScope(
        population=population,
        geography=geography,
        time=time,
        time_role="observation_time",
        jurisdiction=_jurisdiction_for_geography(
            geography,
            scope_profile=scope_profile,
        ),
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


def _scenario_adapter_input(scenario: Mapping[str, Any]) -> _ScenarioAdapterInput:
    """Normalize one scenario mapping without promoting identity to content."""

    return _ScenarioAdapterInput(
        scenario_id=_text(scenario.get("scenario_id")) or "scenario",
        text=_scenario_text(scenario),
        domain=_problem_domain_for_scenario(scenario),
        authority_type=_authority_type_for_scenario(scenario),
        scope_profile=_scenario_scope_profile(scenario),
    )


def _scenario_scope_profile(
    scenario: Mapping[str, Any],
) -> _ScenarioScopeProfile | None:
    """Read an explicit versioned scope profile; absent input stays generic."""

    raw_profile: Mapping[str, Any] | None = None
    for key in ("scenario_profile", "pilot_profile", "scope_profile", "profile"):
        candidate = scenario.get(key)
        if isinstance(candidate, Mapping):
            raw_profile = candidate
            break
    if raw_profile is None:
        context = scenario.get("context")
        if isinstance(context, Mapping):
            for key in ("scenario_profile", "pilot_profile", "scope_profile"):
                candidate = context.get(key)
                if isinstance(candidate, Mapping):
                    raw_profile = candidate
                    break
    if raw_profile is None:
        return None

    profile_id = _text(
        raw_profile.get("profile_id")
        or raw_profile.get("profile_ref")
        or raw_profile.get("versioned_profile_id")
        or raw_profile.get("id")
        or raw_profile.get("name")
    )
    if not profile_id:
        return None
    scope = raw_profile.get("scope")
    scope_mapping = scope if isinstance(scope, Mapping) else {}
    interval = raw_profile.get("time_window")
    if not isinstance(interval, Mapping):
        interval = raw_profile.get("temporal_interval")
    if not isinstance(interval, Mapping):
        interval = scope_mapping.get("time_window")
    interval_mapping = interval if isinstance(interval, Mapping) else {}
    return _ScenarioScopeProfile(
        profile_id=profile_id,
        jurisdiction=(
            _text(raw_profile.get("jurisdiction"))
            or _text(scope_mapping.get("jurisdiction"))
            or None
        ),
        time_start=(
            _text(interval_mapping.get("start"))
            or _text(interval_mapping.get("from"))
            or _text(raw_profile.get("time_start"))
            or _text(raw_profile.get("start"))
            or None
        ),
        time_end=(
            _text(interval_mapping.get("end"))
            or _text(interval_mapping.get("to"))
            or _text(raw_profile.get("time_end"))
            or _text(raw_profile.get("end"))
            or None
        ),
        required_constructs=_normalised_construct_refs(
            raw_profile.get("required_constructs")
            or raw_profile.get("required_evidence_constructs")
            or raw_profile.get("declared_constructs")
        ),
        candidate_construct_proposals=_normalised_construct_refs(
            raw_profile.get("candidate_construct_proposals")
            or raw_profile.get("construct_proposals")
            or raw_profile.get("topic_proposals")
        ),
    )


def _scenario_text(scenario: Mapping[str, Any]) -> str:
    supplied_text = _text(scenario.get("text")) or _text(scenario.get("request"))
    if supplied_text:
        return supplied_text
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
    ]
    return " ".join(_text(part) for part in parts if _text(part)) or "compile policy data needs"


def _token_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_token_text(item) for item in value)
    return str(value).replace("_", " ").replace("-", " ")


def _problem_domain_for_scenario(scenario: Mapping[str, Any]) -> governance.ProblemDomain:
    supplied = _enum_text(scenario.get("domain")) or _enum_text(scenario.get("domain_hint"))
    if supplied:
        normalized = supplied.casefold().replace("-", " ").replace("_", " ")
        for domain in governance.ProblemDomain:
            if normalized.strip() in {domain.value, domain.name.casefold()}:
                return domain
        supplied_words = set(normalized.split())
        if supplied_words.intersection({"health", "healthcare"}):
            return governance.ProblemDomain.HEALTHCARE
        if "social" in supplied_words:
            return governance.ProblemDomain.SOCIAL
        if "fiscal" in supplied_words:
            return governance.ProblemDomain.FISCAL

    haystack = _scenario_text(scenario).casefold().replace("-", " ").replace("_", " ")
    words = set(haystack.split())
    if words.intersection({"health", "healthcare", "clinic", "vaccination", "medicine"}):
        return governance.ProblemDomain.HEALTHCARE
    if words.intersection({"housing", "rent", "benefit", "social"}):
        return governance.ProblemDomain.SOCIAL
    return governance.ProblemDomain.FISCAL


def _authority_type_for_scenario(
    scenario: Mapping[str, Any],
) -> governance.PolicyLayerLevel:
    context = scenario.get("context") if isinstance(scenario.get("context"), Mapping) else {}
    text = (
        " ".join(
            (
                _scenario_text(scenario),
                _text(context.get("authority_type")),
                _text(context.get("country")),
            )
        )
        .casefold()
        .replace("-", " ")
        .replace("_", " ")
    )
    words = set(text.split())
    if words.intersection({"national", "ukraine"}):
        return governance.PolicyLayerLevel.FEDERAL
    if words.intersection({"oblast", "region", "state"}):
        return governance.PolicyLayerLevel.STATE
    return governance.PolicyLayerLevel.LOCAL


def _jurisdiction_for_geography(
    geography: str,
    *,
    scope_profile: _ScenarioScopeProfile | None = None,
) -> str | None:
    """Resolve jurisdiction only from an explicit named profile."""

    del geography
    return scope_profile.jurisdiction if scope_profile else None


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
    return tuple(dict.fromkeys(text for item in raw_values if (text := _text(item))))


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "DataRequirementCompiler",
    "compile_data_requirements_for_scenario",
    "data_requirement_compilation_audit_surface",
    "write_data_requirement_compilation_report",
]
