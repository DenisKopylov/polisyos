"""Deterministic compiler from claim/facet obligations to DataRequirementSpec."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, get_args

from polisyos.core import contracts
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    InputRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts import (
    CapabilitySourceDiscoveryResult,
    CapabilitySourceDiscoveryUnavailableError,
    candidate_source_time_coverage,
)
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

    from polisyos.core.contracts.model_input_requirements import ModelInputContext

    from .model_input_requirements import ModelInputCompilationReport

from ._impl.models import (
    CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION,
    DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION,
    DATA_REQUIREMENT_COMPILATION_V1_SCHEMA_VERSION,
    CapabilityBindingSnapshot,
    CapabilityRequirementResolution,
    DataQualityMinimums,
    DataRequirementBasisResolution,
    DataRequirementCompilationReport,
    DataRequirementCompilationReportV1,
    DataRequirementScope,
    DataRequirementSpec,
    DataRequirementTimeRole,
    data_requirement_authority_boundary,
    data_requirement_compilation_event_ref,
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
    time_role: DataRequirementTimeRole | None = None
    granularity: str | None = None
    population: str | None = None
    entity_scope: str | None = None
    unrepresented_fields: tuple[str, ...] = ()
    required_constructs: tuple[str, ...] = ()
    candidate_construct_proposals: tuple[str, ...] = ()


class ScenarioScopeProfileInputError(ValueError):
    """Typed refusal for a supplied scenario scope profile that cannot be admitted."""

    code = "scenario_scope_profile_invalid"

    def __init__(self, reason_code: str, field_path: str) -> None:
        self.reason_code = reason_code
        self.field_path = field_path
        super().__init__(f"{self.code}:{reason_code}:{field_path}")


class ScenarioFamilyDeclarationInputError(ValueError):
    """Typed refusal for a malformed or ambiguous legacy family declaration."""

    code = "scenario_family_declaration_invalid"

    def __init__(self, reason_code: str, field_path: str) -> None:
        self.reason_code = reason_code
        self.field_path = field_path
        super().__init__(f"{self.code}:{reason_code}:{field_path}")


class ScenarioDomainInputError(ValueError):
    """Refuse malformed or conflicting declared scenario domain inputs."""

    code = "scenario_domain_input_invalid"

    def __init__(self, reason_code: str, field_path: str) -> None:
        self.reason_code = reason_code
        self.field_path = field_path
        super().__init__(f"{self.code}:{reason_code}:{field_path}")


class ClaimConstructDeclarationInputError(ValueError):
    """Refuse a construct declaration outside the supported per-claim shape."""

    code = "claim_construct_declaration_invalid"

    def __init__(self, reason_code: str, field_path: str) -> None:
        self.reason_code = reason_code
        self.field_path = field_path
        super().__init__(f"{self.code}:{reason_code}:{field_path}")


_SCENARIO_DOMAIN_RULE_REF = "policyos.data_requirement.scenario_domain.v1"
_CLAIM_CONSTRUCT_KEYS = (
    "required_evidence_constructs",
    "required_constructs",
    "explicit_constructs",
    "construct_refs",
    "construct_ref",
)


@dataclass(frozen=True)
class _ScenarioDomainResolution:
    """Declared routing vocabulary and its original, unpromoted input."""

    domain: governance.ProblemDomain
    raw_inputs: tuple[tuple[str, str], ...]
    status: str
    reason_code: str

    def metadata(self) -> dict[str, Any]:
        return {
            "rule_version_ref": _SCENARIO_DOMAIN_RULE_REF,
            "canonical_domain": self.domain.value,
            "raw_inputs": dict(self.raw_inputs),
            "status": self.status,
            "reason_code": self.reason_code,
            "purpose": "routing_vocabulary_only",
            "may_not_use_for": ["domain_semantic_support", "source_authority"],
        }


_SCENARIO_PROFILE_TOP_LEVEL_ALIASES = (
    "scenario_profile",
    "pilot_profile",
    "scope_profile",
    "profile",
)
_SCENARIO_PROFILE_CONTEXT_ALIASES = ("scenario_profile", "pilot_profile", "scope_profile")
_SCENARIO_DIRECT_REQUIRED_CONSTRUCT_ALIASES = ("required_constructs", "construct_refs")
_SCENARIO_DIRECT_CANDIDATE_CONSTRUCT_ALIASES = ("candidate_construct_proposals",)
_SCENARIO_PROFILE_REQUIRED_CONSTRUCT_ALIASES = (
    "required_constructs",
    "required_evidence_constructs",
    "declared_constructs",
)
_SCENARIO_PROFILE_CANDIDATE_CONSTRUCT_ALIASES = (
    "candidate_construct_proposals",
    "construct_proposals",
    "topic_proposals",
)


@dataclass(frozen=True)
class _ScenarioAdapterInput:
    """Semantic inputs handed from a scenario mapping to the compiler."""

    scenario_id: str
    text: str
    domain: governance.ProblemDomain
    authority_type: governance.PolicyLayerLevel
    domain_resolution: _ScenarioDomainResolution
    scope_profile: _ScenarioScopeProfile | None = None


@dataclass(frozen=True)
class _ConstructResolutionInputs:
    """Separate declared authority inputs from candidate semantic proposals."""

    required_constructs: tuple[str, ...] = ()
    candidate_construct_proposals: tuple[str, ...] = ()


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

    @staticmethod
    def compile_model_input_obligations(
        store: ArtifactStore,
        *,
        obligation_set_ref: ArtifactRef,
        expected_context: ModelInputContext,
        expected_interface_ref: ArtifactRef,
    ) -> ModelInputCompilationReport:
        """Compile exact owner-produced missing model ports for source selection.

        Runtime must replay the selected preflight before providing its
        exact set ref. The compiler reopens the whole set and checks its
        candidate, interface and member bindings. This reports a measurement
        need without establishing execution, claim support or source admission.
        """
        from polisyos.core.contracts.model_input_requirements import (
            load_model_input_obligation_set,
            verify_model_input_port_semantics,
        )

        from .model_input_requirements import (
            CompiledModelInputRequirement,
            ModelInputCompilationReport,
        )

        obligation_set, members = load_model_input_obligation_set(store, obligation_set_ref)
        if obligation_set.invocation.context != expected_context or artifact_ref_identity_key(
            obligation_set.invocation.interface_ref
        ) != artifact_ref_identity_key(expected_interface_ref):
            raise ValueError("model_input_compiler_selected_origin_mismatch")
        if not members:
            raise ValueError("model_input_compiler_no_missing_inputs")
        requirements: list[CompiledModelInputRequirement] = []
        for ref, obligation in zip(obligation_set.obligation_refs, members, strict=True):
            port = obligation.port
            verify_model_input_port_semantics(store, port)
            scope = port.scope
            requirements.append(
                CompiledModelInputRequirement(
                    requirement_id=f"model-input:{_sha256_json_value(ref.model_dump(mode='json'))}",
                    obligation_ref=ref,
                    port=port,
                    scope=DataRequirementScope(
                        population=scope.population_ref,
                        geography=scope.geography_ref,
                        jurisdiction=scope.jurisdiction_ref,
                        time=f"{scope.period_start.isoformat()}/{scope.period_end.isoformat()}",
                        time_role=scope.time_role,
                    ),
                )
            )
        return ModelInputCompilationReport(
            context=expected_context,
            interface_ref=expected_interface_ref,
            obligation_set_ref=obligation_set_ref,
            requirements=tuple(requirements),
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
        capability_bindings, capability_resolutions = _resolve_capability_requirements(
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
        producer_report_ref = data_requirement_compilation_event_ref(run_id)
        subject_refs = _data_requirement_subject_refs(
            run_id=run_id,
            scenario_id=scenario_id,
            claims=claims,
            facets=facets,
            obligation_graph=obligation_graph,
        )
        rule_version_refs = _data_requirement_rule_refs(
            specs=deduped,
            capability_resolutions=capability_resolutions,
            scenario_family_construct_rows=self._scenario_family_construct_rows,
        )
        input_content_hash = _data_requirement_input_content_hash(
            run_id=run_id,
            scenario_id=scenario_id,
            claims=claims,
            facets=facets,
            obligation_graph=obligation_graph,
            authority_profile_refs=authority_profile_refs,
            scope_profile=scope_profile,
            resolution_inputs=resolution_inputs,
            capability_resolutions=capability_resolutions,
            scenario_family_construct_rows=self._scenario_family_construct_rows,
        )
        requirement_basis = _capability_requirement_basis(
            producer_report_ref=producer_report_ref,
            subject_refs=subject_refs,
            rule_version_refs=rule_version_refs,
            capability_resolutions=capability_resolutions,
            family_rules=family_rules,
            scenario_family_construct_rows=self._scenario_family_construct_rows,
        )
        return DataRequirementCompilationReport(
            run_id=run_id,
            scenario_id=scenario_id,
            specs=deduped,
            capability_resolution_schema_version=(CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION),
            capability_requirement_resolutions=capability_resolutions,
            requirement_basis=requirement_basis,
            producer_report_ref=producer_report_ref,
            subject_refs=subject_refs,
            rule_version_refs=rule_version_refs,
            input_content_hash=input_content_hash,
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
            report = self._compile_from_legacy_scenario_fallback(
                scenario=scenario,
                scenario_id=scenario_id,
                scope_profile=adapter_input.scope_profile,
            )
            return _bind_scenario_compilation_inputs(
                report, scenario=scenario, domain_resolution=adapter_input.domain_resolution
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
        report = self.compile_for_claim_ledger(
            run_id=f"scenario-{scenario_id}",
            scenario_id=scenario_id,
            claim_ledger=claim_ledger,
            facet_snapshots=facets,
            obligation_graph=graph,
            authority_profile_refs=(case.authority_profile.profile_id,),
            scope_profile=adapter_input.scope_profile,
        )
        return _bind_scenario_compilation_inputs(
            report, scenario=scenario, domain_resolution=adapter_input.domain_resolution
        )

    def _compile_from_legacy_scenario_fallback(
        self,
        *,
        scenario: Mapping[str, Any],
        scenario_id: str,
        scope_profile: _ScenarioScopeProfile | None = None,
    ) -> DataRequirementCompilationReport:
        families, family_declaration = _legacy_scenario_family_declaration(scenario)
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
        # A missing grammar facet does not erase an explicitly declared need.
        # Reuse the canonical producer; its requirement basis is separate from
        # source/claim admission and the full authority binding stays intact.
        compiled = self.compile_for_claim_ledger(
            run_id=f"scenario-{scenario_id}",
            claim_ledger={"claims": ()},
            facet_snapshots=(),
            scenario_id=scenario_id,
            scope_profile=scope_profile,
        )
        canonical_families = {
            family for spec in compiled.specs for family in spec.required_data_families
        }
        legacy_only: list[DataRequirementSpec] = []
        slot_aliases: list[dict[str, str]] = []
        source_refs_by_requirement: dict[str, list[str]] = {}
        for spec in specs:
            if canonical_families.intersection(spec.required_data_families):
                continue
            world_slot = spec.required_data_families[0]
            matched = compiled_requirements_for_world_slot(
                world_slot=world_slot,
                specs=compiled.specs,
                capability_resolutions=compiled.capability_requirement_resolutions,
            )
            if len(matched) != 1:
                legacy_only.append(spec)
                continue
            canonical_ref = matched[0].requirement_id
            source_refs_by_requirement.setdefault(canonical_ref, []).extend(
                spec.source_requirement_refs
            )
            slot_aliases.append(
                {"world_slot": world_slot, "compiled_requirement_ref": canonical_ref}
            )
        canonical_specs = tuple(
            DataRequirementSpec.model_validate(
                {
                    **spec.model_dump(mode="json"),
                    "source_requirement_refs": list(
                        dict.fromkeys(
                            (
                                *spec.source_requirement_refs,
                                *source_refs_by_requirement.get(spec.requirement_id, ()),
                            )
                        )
                    ),
                }
            )
            for spec in compiled.specs
        )
        legacy_only_specs = tuple(legacy_only)
        basis = compiled.requirement_basis
        if legacy_only_specs:
            # A verified canonical subset cannot upgrade a caller-only tail.
            basis = DataRequirementBasisResolution(
                state="established",
                source="explicit_scenario_family_declaration",
                basis_grade="consumer_asserted",
                reason_codes=("explicit_scenario_family_declaration_candidate_only",),
                source_refs=tuple(
                    dict.fromkeys(
                        (
                            *basis.source_refs,
                            f"scenario:{scenario_id}/expected_evidence_contract/admissible_data_source_families",
                        )
                    )
                ),
            )
        payload = compiled.model_dump(mode="json")
        payload.update(
            {
                "specs": [
                    spec.model_dump(mode="json") for spec in (*canonical_specs, *legacy_only_specs)
                ],
                "legacy_admissible_data_source_families": [],
                "requirement_basis": basis.model_dump(mode="json"),
                "metadata": {
                    **compiled.metadata,
                    "fallback": "declared_candidate_requirements_when_grammar_facets_unavailable",
                    "grammar_facets_status": "not_established",
                    "grammar_may_not_use_for": [
                        "grounded_policy_design",
                        "claim_evidence",
                        "policy_execution",
                    ],
                    "family_declaration": family_declaration,
                    "declared_legacy_data_source_families": list(families),
                    "candidate_world_slot_aliases": slot_aliases,
                    "candidate_construct_proposals": (
                        scope_profile.candidate_construct_proposals if scope_profile else ()
                    ),
                },
            }
        )
        if slot_aliases:
            payload["rule_version_refs"] = list(
                dict.fromkeys(
                    (
                        *compiled.rule_version_refs,
                        "policyos.data_requirement.world_slot_projection.v1",
                    )
                )
            )
        return DataRequirementCompilationReport.model_validate(payload)

    def _resolver_for_compilation(self) -> CapabilityResolverPort | None:
        if self._capability_resolver is not None:
            return self._capability_resolver
        if self._require_capability_index:
            raise FileNotFoundError(
                "capability resolver is required for this data-requirement compilation"
            )
        return None


def _model_input_compilation_inputs(report: ModelInputCompilationReport) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(report.interface_ref, role="model_input_interface"),
        input_ref_from_artifact_ref(report.obligation_set_ref, role="model_input_obligation_set"),
        *(
            input_ref_from_artifact_ref(item.obligation_ref, role="model_input_obligation")
            for item in report.requirements
        ),
    ]


def _read_model_input_compilation_report(
    store: ArtifactStore, ref: ArtifactRef
) -> ModelInputCompilationReport:
    from .model_input_requirements import ModelInputCompilationReport

    if ref.manifest_profile_sha256 is None:
        raise ValueError("model_input_compiler_report_ref_unselected")
    report = validate_core_model_json_artifact(ModelInputCompilationReport, store, ref)
    if store.get_manifest(ref).inputs != _model_input_compilation_inputs(report):
        raise ValueError("model_input_compiler_report_lineage_mismatch")
    return report


def persist_model_input_compilation_report(
    store: ArtifactStore, report: ModelInputCompilationReport
) -> ArtifactRef:
    """Write the candidate compiler result and verify its exact CAS readback."""
    ref = store.put_json(
        report,
        PutOptions(
            kind=report.ARTIFACT_KIND,
            media_type=report.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=report.ARTIFACT_SCHEMA_NAME, version=report.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=_model_input_compilation_inputs(report),
        ),
        return_selected_profile=True,
    )
    if _read_model_input_compilation_report(store, ref) != report:
        raise ValueError("model_input_compiler_report_readback_mismatch")
    return ref


def verify_model_input_compilation_report(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    expected_context: ModelInputContext,
    expected_interface_ref: ArtifactRef,
    expected_obligation_set_ref: ArtifactRef,
) -> ModelInputCompilationReport:
    """Reopen a selected compiler result and reconcile it to its producer inputs."""
    report = _read_model_input_compilation_report(store, ref)
    expected = DataRequirementCompiler.compile_model_input_obligations(
        store,
        obligation_set_ref=expected_obligation_set_ref,
        expected_context=expected_context,
        expected_interface_ref=expected_interface_ref,
    )
    if report != expected:
        raise ValueError("model_input_compiler_report_selection_mismatch")
    return report


def compile_data_requirements_for_scenario(
    scenario: Mapping[str, Any],
) -> DataRequirementCompilationReport:
    """Compile data requirements for a scenario mapping."""

    return DataRequirementCompiler().compile_for_scenario(scenario)


def compiled_requirements_for_world_slot(
    *,
    world_slot: str,
    specs: Sequence[DataRequirementSpec],
    capability_resolutions: Sequence[CapabilityRequirementResolution] | None,
) -> tuple[DataRequirementSpec, ...]:
    """Recompute candidate slot-to-need joins from actual compiler carriers.

    Only an exact owner spec/query/profile and digest-validated source asset
    declaration can join a world slot to a construct. An empty result means no
    established join; multiple spec occurrences are ambiguous. Source
    alternatives inside one discovery remain intact for later selected-digest
    admission. This lookup grants neither source nor claim authority.
    """

    if not isinstance(world_slot, str) or not world_slot.strip():
        raise ValueError("compiled_requirement_world_slot_invalid")
    rows = tuple(
        CapabilityRequirementResolution.model_validate(row.model_dump(mode="json"))
        for row in capability_resolutions or ()
    )
    matches: list[DataRequirementSpec] = []
    for original in specs:
        if type(original) is not DataRequirementSpec:
            continue
        spec = DataRequirementSpec.model_validate(original.model_dump(mode="json"))
        linked = tuple(row for row in rows if _world_slot_spec_query_matches(spec, row))
        if len(linked) != 1:
            continue
        resolution = linked[0]
        discovery = resolution.candidate_discovery
        binding = resolution.binding
        if (
            discovery is not None
            and binding is not None
            and any(
                candidate.construct_ref.removeprefix("construct:")
                == binding.construct_ref.removeprefix("construct:")
                and any(
                    _world_slot_source_asset_matches(
                        world_slot, spec, resolution, candidate.scope, asset
                    )
                    for asset in candidate.source_assets
                )
                for candidate in discovery.candidates
            )
        ):
            matches.append(original)
    return tuple(matches)


def _world_slot_spec_query_matches(
    spec: DataRequirementSpec,
    resolution: CapabilityRequirementResolution,
) -> bool:
    binding = resolution.binding
    discovery = resolution.candidate_discovery
    if binding is None or discovery is None or discovery.state != "candidates_returned":
        return False
    if (
        spec.metadata.get("capability_binding") != binding.model_dump(mode="json")
        or spec.metadata.get("construct_ref") != binding.construct_ref
        or spec.metadata.get("capability_index_ref") != discovery.capability_index_ref
        or spec.required_data_families != (resolution.query.source_family_alias,)
    ):
        return False
    raw_profile = spec.metadata.get("scope_profile")
    if not isinstance(raw_profile, Mapping) or raw_profile.get("unrepresented_fields"):
        return False
    try:
        profile = _parse_scenario_scope_profile(
            {key: value for key, value in raw_profile.items() if key != "unrepresented_fields"},
            source="compiled_requirement.scope_profile",
        )
    except ScenarioScopeProfileInputError:
        return False
    query = resolution.query
    return (
        not profile.unrepresented_fields
        and profile.profile_id == resolution.scope_profile_id
        and query.construct in profile.required_constructs
        and profile.population is not None
        and profile.entity_scope is not None
        and profile.jurisdiction is not None
        and profile.time_start is not None
        and profile.time_end is not None
        and profile.granularity is not None
        and profile.time_role == spec.scope.time_role == "observation_time"
        and query.entity_scope == profile.entity_scope
        and query.population_filter == {"type": profile.population}
        and query.geography == profile.jurisdiction == spec.scope.jurisdiction
        and spec.scope.population == profile.population
        and query.time_window.start == profile.time_start
        and query.time_window.end == profile.time_end
    )


def _world_slot_source_asset_matches(
    world_slot: str,
    spec: DataRequirementSpec,
    resolution: CapabilityRequirementResolution,
    source_scope: Mapping[str, Any],
    asset: Mapping[str, Any],
) -> bool:
    query = resolution.query
    metadata = asset.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("target_world_slot") != world_slot:
        return False
    if query.time_window.start is None or query.time_window.end is None:
        return False
    if any(
        source_scope.get(field) is not None
        and (not isinstance(source_scope[field], str) or not source_scope[field].strip())
        for field in (
            "geography",
            "jurisdiction",
            "entity_scope",
            "population",
            "time_start",
            "time_end",
        )
    ):
        return False
    fetch = metadata.get("catalog_fetch_binding")
    if (
        not isinstance(fetch, Mapping)
        or set(fetch) != {"metric_id", "connector_id", "dataset_id", "profile_id"}
        or any(
            not isinstance(fetch[field], str) or not fetch[field].strip()
            for field in ("metric_id", "connector_id", "dataset_id")
        )
        or (
            fetch["profile_id"] is not None
            and (not isinstance(fetch["profile_id"], str) or not fetch["profile_id"].strip())
        )
        or (
            metadata.get("indicator_id") is not None
            and metadata["indicator_id"] != fetch["dataset_id"]
        )
        or metadata.get("population_scope") != spec.scope.population
        or metadata.get("temporal_granularity") != spec.metadata["scope_profile"]["granularity"]
        or not isinstance(metadata.get("canonical_unit"), str)
        or not metadata["canonical_unit"].strip()
        or source_scope.get("entity_scope") != query.entity_scope
        or source_scope.get("population") != spec.scope.population
        or source_scope.get("geography") not in {query.geography, "global", "multi_context"}
        or source_scope.get("jurisdiction") not in {None, query.geography}
    ):
        return False
    time_refusal, _ = candidate_source_time_coverage(
        query_window=query.time_window,
        source_start=source_scope.get("time_start"),
        source_end=source_scope.get("time_end"),
    )
    return time_refusal is None


def _strict_report_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys before a versioned report is dispatched."""

    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_data_requirement_report_json_key:{key}")
        payload[key] = value
    return payload


def parse_data_requirement_compilation_report(
    report: (
        DataRequirementCompilationReport
        | DataRequirementCompilationReportV1
        | Mapping[str, Any]
        | bytes
        | str
    ),
) -> DataRequirementCompilationReport | DataRequirementCompilationReportV1:
    """Read one strict versioned compiler report without promoting legacy bytes."""

    if isinstance(report, DataRequirementCompilationReport | DataRequirementCompilationReportV1):
        return report

    original_bytes: bytes | None = None
    if isinstance(report, bytes):
        original_bytes = report
        payload = json.loads(report, object_pairs_hook=_strict_report_json_object)
    elif isinstance(report, str):
        original_bytes = report.encode("utf-8")
        payload = json.loads(report, object_pairs_hook=_strict_report_json_object)
    elif isinstance(report, Mapping):
        payload = dict(report)
    else:
        raise TypeError("data_requirement_report_input_type_invalid")

    if not isinstance(payload, Mapping):
        raise ValueError("data_requirement_report_payload_must_be_object")

    schema_version = payload.get("schema_version")
    if schema_version == DATA_REQUIREMENT_COMPILATION_V1_SCHEMA_VERSION:
        legacy = DataRequirementCompilationReportV1.model_validate(dict(payload))
        if original_bytes is not None:
            object.__setattr__(legacy, "_source_bytes", original_bytes)
        return legacy
    if schema_version == DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION:
        current = DataRequirementCompilationReport.model_validate(dict(payload))
        if original_bytes is not None:
            object.__setattr__(current, "_source_bytes", original_bytes)
        return current
    raise ValueError(f"unsupported_data_requirement_compilation_schema_version:{schema_version}")


def data_requirement_compilation_audit_surface(
    report: (
        DataRequirementCompilationReport
        | DataRequirementCompilationReportV1
        | Mapping[str, Any]
        | bytes
        | str
    ),
) -> dict[str, Any]:
    """Return an audit/API projection of compiled data requirements."""

    model = parse_data_requirement_compilation_report(report)
    payload = model.model_dump(
        mode="json",
        exclude_unset=isinstance(model, DataRequirementCompilationReportV1),
    )
    payload["requirement_basis"] = model.requirement_basis.model_dump(mode="json")
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
    report: (
        DataRequirementCompilationReport
        | DataRequirementCompilationReportV1
        | Mapping[str, Any]
        | bytes
        | str
    ),
    output_dir: str | Path,
) -> Path:
    """Persist immutable report bytes without rewriting an unchanged reader input.

    V2 report files are addressed by the digest of their exact serialized bytes.
    Historical V1 files retain their legacy run-based filename, but publication
    is write-once: exact existing bytes are reused and conflicting bytes refuse.
    """

    model = parse_data_requirement_compilation_report(report)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    source_bytes = model.original_bytes
    unchanged_source = source_bytes is not None and model.model_dump(
        mode="json"
    ) == parse_data_requirement_compilation_report(source_bytes).model_dump(mode="json")
    if unchanged_source:
        report_bytes = source_bytes
    else:
        payload = model.model_dump(
            mode="json",
            exclude_unset=isinstance(model, DataRequirementCompilationReportV1),
        )
        report_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")

    if isinstance(model, DataRequirementCompilationReportV1):
        path = directory / f"{_slug(model.run_id)}-data-requirements.json"
    else:
        digest = hashlib.sha256(report_bytes).hexdigest()
        path = directory / f"sha256-{digest}-data-requirements.json"

    from polisyos.core.artifacts import write_bytes_once

    created = write_bytes_once(path, report_bytes, durable_parent=True)
    if not created:
        if path.is_symlink() or not path.is_file():
            raise ValueError("data_requirement_report_content_conflict")
        try:
            existing_bytes = path.read_bytes()
        except OSError as exc:
            raise ValueError("data_requirement_report_content_conflict") from exc
        if existing_bytes != report_bytes:
            raise ValueError("data_requirement_report_content_conflict")
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
    return tuple(
        _claim_record_like(item, field_path=f"claims[{index}]")
        for index, item in enumerate(raw_claims or ())
    )


def _claim_record_like(claim: object, *, field_path: str = "claim") -> Any:
    if not isinstance(claim, Mapping):
        return claim
    for key in _CLAIM_CONSTRUCT_KEYS:
        if key in claim:
            raise ClaimConstructDeclarationInputError(
                "unsupported_top_level_construct_declaration", f"{field_path}.{key}"
            )
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
        metadata["scope_profile"] = _scenario_scope_profile_metadata(scope_profile)
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


def _scenario_scope_profile_metadata(
    scope_profile: _ScenarioScopeProfile,
) -> dict[str, Any]:
    """Project the admitted declaration without resolving it as an authority."""

    metadata: dict[str, Any] = {
        "profile_id": scope_profile.profile_id,
        "jurisdiction": scope_profile.jurisdiction,
        "time_window": {
            "start": scope_profile.time_start,
            "end": scope_profile.time_end,
        },
        "required_constructs": list(scope_profile.required_constructs),
        "candidate_construct_proposals": list(scope_profile.candidate_construct_proposals),
    }
    if scope_profile.time_role is not None:
        metadata["time_role"] = scope_profile.time_role
    if scope_profile.granularity is not None:
        metadata["granularity"] = scope_profile.granularity
    if scope_profile.population is not None:
        metadata["population"] = scope_profile.population
    if scope_profile.entity_scope is not None:
        metadata["entity_scope"] = scope_profile.entity_scope
    if scope_profile.unrepresented_fields:
        metadata["unrepresented_fields"] = list(scope_profile.unrepresented_fields)
    return metadata


def _minimal_spec(
    *,
    scenario_id: str,
    family: str,
    source_requirement_ref: str,
    scope_profile: _ScenarioScopeProfile | None = None,
) -> DataRequirementSpec:
    metadata = (
        {"scope_profile": _scenario_scope_profile_metadata(scope_profile)}
        if scope_profile is not None
        else {}
    )
    return DataRequirementSpec(
        requirement_id=f"data-requirement:scenario-{scenario_id}:{family}",
        claim_id=f"scenario:{scenario_id}:legacy-data-claim",
        claim_family="context_only",
        claim_type="source_quality",
        claim_use="decision_support",
        required_data_families=(family,),
        scope=DataRequirementScope(
            population=(
                scope_profile.population
                if scope_profile and scope_profile.population
                else "scenario_population"
            ),
            geography="scenario_geography",
            time="scenario_time",
            time_role=(
                scope_profile.time_role
                if scope_profile is not None and scope_profile.time_role is not None
                else "observation_time"
            ),
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
        metadata=metadata,
    )


def _capability_queries_for_requirements(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    obligation_graph: object | Mapping[str, Any] | None,
    scenario_id: str | None,
    scope: DataRequirementScope,
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows = (),
    scope_profile: _ScenarioScopeProfile | None = None,
    resolution_inputs: _ConstructResolutionInputs | None = None,
) -> tuple[RequirementToCapabilityQuery, ...]:
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
    return tuple(
        RequirementToCapabilityQuery(
            requirement_id=f"data-requirement:{_slug(scenario_id or 'run')}:{construct}",
            construct=construct,
            entity_scope=(
                scope_profile.entity_scope
                if scope_profile and scope_profile.entity_scope
                else _entity_scope_for_construct(construct)
            ),
            population_filter=(
                {"type": scope.population}
                if scope_profile and scope_profile.population
                else _population_filter_for_construct(construct, scope)
            ),
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
        for construct in inputs.required_constructs
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
    """Resolve required constructs through the existing binding-only adapter."""

    if resolver is None:
        return ()
    return tuple(
        resolver.resolve(query)
        for query in _capability_queries_for_requirements(
            facets=facets,
            claims=claims,
            obligation_graph=obligation_graph,
            scenario_id=scenario_id,
            scope=scope,
            scenario_family_construct_rows=scenario_family_construct_rows,
            scope_profile=scope_profile,
            resolution_inputs=resolution_inputs,
        )
    )


def _resolve_capability_requirements(
    *,
    facets: Sequence[Mapping[str, Any]],
    claims: Sequence[Any],
    obligation_graph: object | Mapping[str, Any] | None,
    scenario_id: str | None,
    scope: DataRequirementScope,
    resolver: CapabilityResolverPort | None,
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows = (),
    scope_profile: _ScenarioScopeProfile | None = None,
    resolution_inputs: _ConstructResolutionInputs | None = None,
) -> tuple[tuple[CapabilityBindingLike, ...], tuple[CapabilityRequirementResolution, ...]]:
    queries = _capability_queries_for_requirements(
        facets=facets,
        claims=claims,
        obligation_graph=obligation_graph,
        scenario_id=scenario_id,
        scope=scope,
        scenario_family_construct_rows=scenario_family_construct_rows,
        scope_profile=scope_profile,
        resolution_inputs=resolution_inputs,
    )
    bindings: list[CapabilityBindingLike] = []
    resolutions: list[CapabilityRequirementResolution] = []
    for query in queries:
        binding = resolver.resolve(query) if resolver is not None else None
        snapshot = _capability_binding_snapshot(binding) if binding is not None else None
        discover_sources = getattr(resolver, "discover_sources", None)
        discovery = None
        discovery_reasons: tuple[str, ...] = ()
        if callable(discover_sources):
            try:
                raw_discovery = discover_sources(query)
            except CapabilitySourceDiscoveryUnavailableError as exc:
                raw_discovery = None
                discovery_reasons = ("candidate_source_discovery_unavailable", exc.reason_code)
            if raw_discovery is None and not discovery_reasons:
                raise ValueError("candidate_source_discovery_result_missing")
            raw_payload = (
                raw_discovery.model_dump(mode="json")
                if isinstance(raw_discovery, CapabilitySourceDiscoveryResult)
                else raw_discovery
            )
            # Reparse wire fields: frozen/model_copy DTOs alone are not validation.
            discovery = (
                CapabilitySourceDiscoveryResult.model_validate(raw_payload)
                if raw_payload is not None
                else None
            )
            if discovery is not None and discovery.query != query:
                raise ValueError("candidate_source_discovery_original_query_mismatch")
            if (
                discovery is not None
                and snapshot is not None
                and snapshot.capability_index_ref is not None
                and discovery.capability_index_ref != snapshot.capability_index_ref
            ):
                raise ValueError("candidate_source_discovery_index_mismatch")
        resolutions.append(
            CapabilityRequirementResolution(
                scope_profile_id=scope_profile.profile_id if scope_profile else None,
                query=query,
                state="binding_returned" if snapshot is not None else "not_established",
                binding=snapshot,
                candidate_discovery=discovery,
                reason_codes=(
                    (() if snapshot is not None else ("capability_resolver_not_established",))
                    + discovery_reasons
                ),
            )
        )
        if binding is not None:
            bindings.append(binding)
    return tuple(bindings), tuple(resolutions)


def _capability_binding_snapshot(
    binding: CapabilityBindingLike,
) -> CapabilityBindingSnapshot:
    """Copy resolver-port fields into the versioned compilation carrier."""

    return CapabilityBindingSnapshot(
        schema_version=str(binding.schema_version),
        rule_version_ref=str(binding.rule_version_ref),
        requirement_id=str(binding.requirement_id or ""),
        status=str(binding.status),
        selected_capability_ref=binding.selected_capability_ref,
        construct_ref=str(binding.construct_ref or ""),
        capability_index_ref=binding.capability_index_ref,
        authority_level=str(binding.authority_level),
        authority_envelope_result=str(binding.authority_envelope_result),
        binding_reasons=tuple(binding.binding_reasons),
        blocked_reasons=tuple(binding.blocked_reasons),
        limitations=tuple(binding.limitations),
        acquisition_strategies=tuple(dict(item) for item in binding.acquisition_strategies),
        rejected_alternatives=tuple(dict(item) for item in binding.rejected_alternatives),
        conflict_markers=tuple(dict(item) for item in binding.conflict_markers),
    )


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
    required_constructs = tuple(dict.fromkeys((*graph_constructs, *explicit, *declared)))
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


def _capability_requirement_basis(
    *,
    producer_report_ref: str,
    subject_refs: tuple[str, ...],
    rule_version_refs: tuple[str, ...],
    capability_resolutions: tuple[CapabilityRequirementResolution, ...],
    family_rules: Sequence[str],
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows,
) -> DataRequirementBasisResolution:
    """Grade only the source basis actually emitted by the producer."""

    source_refs = [producer_report_ref, *subject_refs, *rule_version_refs]
    if capability_resolutions:
        source_refs.extend(
            f"capability-requirement:{item.query.requirement_id}" for item in capability_resolutions
        )
        source_refs.extend(
            f"capability-index:{item.binding.capability_index_ref}"
            for item in capability_resolutions
            if item.binding is not None and item.binding.capability_index_ref
        )
        source_refs.extend(
            f"resolver-rule:{item.binding.rule_version_ref}"
            for item in capability_resolutions
            if item.binding is not None
        )
        every_query_resolved_and_mapped = all(
            item.state == "binding_returned"
            and legacy_family_for_construct(
                item.query.construct, rows=scenario_family_construct_rows
            )
            for item in capability_resolutions
        )
        if family_rules and every_query_resolved_and_mapped:
            return DataRequirementBasisResolution(
                state="established",
                source="governed_capability_resolution",
                basis_grade="recomputed",
                reason_codes=("governed_capability_basis_resolved",),
                source_refs=tuple(dict.fromkeys(source_refs)),
            )
        return DataRequirementBasisResolution(
            state="not_established",
            source="governed_capability_resolution",
            basis_grade="not_established",
            reason_codes=("governed_capability_resolution_incomplete",),
            source_refs=tuple(dict.fromkeys(source_refs)),
        )
    return DataRequirementBasisResolution(
        state="not_established",
        source="not_established",
        basis_grade="not_established",
        reason_codes=("no_explicit_or_governed_data_basis",),
        source_refs=tuple(dict.fromkeys(source_refs)),
    )


def _bind_scenario_compilation_inputs(
    report: DataRequirementCompilationReport,
    *,
    scenario: Mapping[str, Any],
    domain_resolution: _ScenarioDomainResolution,
) -> DataRequirementCompilationReport:
    """Bind the scenario's declared candidate basis to its actual report."""

    scenario_id = _text(scenario.get("scenario_id")) or report.scenario_id or "scenario"
    families, declaration = _legacy_scenario_family_declaration(scenario)
    scenario_ref = f"scenario:{scenario_id}"
    declaration_ref = (
        f"scenario:{scenario_id}/expected_evidence_contract/admissible_data_source_families"
    )
    has_declaration_path = declaration != "not_supplied"
    subject_refs = tuple(
        dict.fromkeys(
            (
                *report.subject_refs,
                f"run:{report.run_id}",
                scenario_ref,
                *((declaration_ref,) if has_declaration_path else ()),
            )
        )
    )
    rule_version_refs = tuple(
        dict.fromkeys(
            (
                *report.rule_version_refs,
                "policyos.data_requirement.compiler.v2",
                _SCENARIO_DOMAIN_RULE_REF,
                *(spec.rule_version_ref for spec in report.specs),
                *(
                    item.binding.rule_version_ref
                    for item in report.capability_requirement_resolutions or ()
                    if item.binding is not None
                ),
                *(
                    item.candidate_discovery.rule_version_ref
                    for item in report.capability_requirement_resolutions or ()
                    if item.candidate_discovery is not None
                ),
            )
        )
    )
    input_content_hash = _sha256_json_value(
        {
            "compiler_input_content_hash": report.input_content_hash,
            "scenario_input": scenario,
            "scenario_domain_resolution": domain_resolution.metadata(),
        }
    )
    source_refs = list(report.requirement_basis.source_refs)
    source_refs.extend(
        (
            report.producer_report_ref or report.runtime_event_ref or "",
            *subject_refs,
            *rule_version_refs,
        )
    )
    if has_declaration_path:
        source_refs.append(declaration_ref)
    source_refs = list(dict.fromkeys(item for item in source_refs if item))

    if report.requirement_basis.state == "established":
        reasons = list(report.requirement_basis.reason_codes)
        if declaration == "declared" and families:
            reasons.append("explicit_scenario_family_declaration_candidate_only")
        elif declaration == "explicit_empty":
            reasons.append("explicit_empty_family_declaration_not_proof")
        basis = report.requirement_basis.model_copy(
            update={
                "reason_codes": tuple(dict.fromkeys(reasons)),
                "source_refs": tuple(source_refs),
            }
        )
    elif declaration == "declared" and families:
        basis = DataRequirementBasisResolution(
            state="established",
            source="explicit_scenario_family_declaration",
            basis_grade="consumer_asserted",
            reason_codes=("explicit_scenario_family_declaration_candidate_only",),
            source_refs=tuple(source_refs),
        )
    elif declaration == "explicit_empty":
        basis = DataRequirementBasisResolution(
            state="not_established",
            source="explicit_scenario_family_declaration",
            basis_grade="not_established",
            reason_codes=(
                "explicit_empty_family_declaration_not_proof",
                "empty_compilation_not_proof_of_no_data",
            ),
            source_refs=tuple(source_refs),
        )
    else:
        reasons = list(report.requirement_basis.reason_codes)
        if declaration == "explicit_empty":
            reasons.append("explicit_empty_family_declaration_not_proof")
        basis = report.requirement_basis.model_copy(
            update={
                "reason_codes": tuple(dict.fromkeys(reasons)),
                "source_refs": tuple(source_refs),
            }
        )

    payload = report.model_dump(mode="python")
    payload.update(
        {
            "requirement_basis": basis,
            "subject_refs": subject_refs,
            "rule_version_refs": rule_version_refs,
            "input_content_hash": input_content_hash,
            "metadata": {
                **report.metadata,
                "scenario_domain_resolution": domain_resolution.metadata(),
            },
        }
    )
    return DataRequirementCompilationReport.model_validate(payload)


def _data_requirement_subject_refs(
    *,
    run_id: str,
    scenario_id: str | None,
    claims: Sequence[Any],
    facets: Sequence[Mapping[str, Any]],
    obligation_graph: object | Mapping[str, Any] | None,
) -> tuple[str, ...]:
    refs = [f"run:{run_id}"]
    if scenario_id:
        refs.append(f"scenario:{scenario_id}")
    refs.extend(
        f"claim:{_text(getattr(claim, 'claim_id', None))}"
        for claim in claims
        if _text(getattr(claim, "claim_id", None))
    )
    refs.extend(
        f"facet:{_text(facet.get('facet_id'))}" for facet in facets if _text(facet.get("facet_id"))
    )
    refs.extend(f"obligation:{item}" for item in _data_obligation_refs(obligation_graph))
    return tuple(dict.fromkeys(refs))


def _data_requirement_rule_refs(
    *,
    specs: Sequence[DataRequirementSpec],
    capability_resolutions: Sequence[CapabilityRequirementResolution],
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows,
) -> tuple[str, ...]:
    refs = ["policyos.data_requirement.compiler.v2"]
    if any(
        isinstance(spec.metadata.get("scope_profile"), Mapping)
        and any(key in spec.metadata["scope_profile"] for key in ("population", "entity_scope"))
        for spec in specs
    ):
        refs.append("policyos.data_requirement.declared_scope.v1")
    refs.extend(spec.rule_version_ref for spec in specs)
    refs.extend(
        item.binding.rule_version_ref for item in capability_resolutions if item.binding is not None
    )
    refs.extend(
        item.candidate_discovery.rule_version_ref
        for item in capability_resolutions
        if item.candidate_discovery is not None
    )
    used_constructs = {item.query.construct for item in capability_resolutions}
    refs.extend(
        f"scenario-family-construct-row:{row.producer_ref}"
        for row in scenario_family_construct_rows
        if row.construct in used_constructs
    )
    return tuple(dict.fromkeys(refs))


def _data_requirement_input_content_hash(
    *,
    run_id: str,
    scenario_id: str | None,
    claims: Sequence[Any],
    facets: Sequence[Mapping[str, Any]],
    obligation_graph: object | Mapping[str, Any] | None,
    authority_profile_refs: Sequence[str],
    scope_profile: _ScenarioScopeProfile | None,
    resolution_inputs: _ConstructResolutionInputs,
    capability_resolutions: Sequence[CapabilityRequirementResolution],
    scenario_family_construct_rows: contracts.ScenarioFamilyConstructRows,
) -> str:
    """Hash the normalized source inputs and rules used by the compiler."""

    claim_fields = (
        "claim_id",
        "claim_family",
        "claim_type",
        "claim_use",
        "text",
        "facet_refs",
        "obligation_refs",
        "authority_profile_refs",
        "concept_spine_refs",
        "source_attribution",
        "metadata",
    )
    claim_rows = [
        {field: getattr(claim, field, None) for field in claim_fields} for claim in claims
    ]
    frontier = (
        getattr(obligation_graph, "blocking_frontier", None)
        if not isinstance(obligation_graph, Mapping)
        else obligation_graph.get("blocking_frontier")
    )
    obligation_rows = []
    for item in frontier or ():
        metadata = (
            item.get("metadata") if isinstance(item, Mapping) else getattr(item, "metadata", {})
        )
        bundle_key = (
            item.get("bundle_key")
            if isinstance(item, Mapping)
            else getattr(item, "bundle_key", None)
        )
        family = (
            bundle_key.get("family")
            if isinstance(bundle_key, Mapping)
            else getattr(bundle_key, "family", None)
        )
        obligation_rows.append(
            {
                "frontier_id": (
                    item.get("frontier_id")
                    if isinstance(item, Mapping)
                    else getattr(item, "frontier_id", None)
                ),
                "family": family,
                "metadata": metadata,
            }
        )
    scope = (
        {
            "profile_id": scope_profile.profile_id,
            "jurisdiction": scope_profile.jurisdiction,
            "time_start": scope_profile.time_start,
            "time_end": scope_profile.time_end,
            "time_role": scope_profile.time_role,
            "granularity": scope_profile.granularity,
            "population": scope_profile.population,
            "entity_scope": scope_profile.entity_scope,
            "unrepresented_fields": scope_profile.unrepresented_fields,
            "required_constructs": scope_profile.required_constructs,
            "candidate_construct_proposals": scope_profile.candidate_construct_proposals,
        }
        if scope_profile is not None
        else None
    )
    rows = [row.model_dump(mode="json", by_alias=True) for row in scenario_family_construct_rows]
    capability_rows = [
        item.model_dump(mode="json", by_alias=True) for item in capability_resolutions
    ]
    payload = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "claims": claim_rows,
        "facets": facets,
        "obligation_frontier": obligation_rows,
        "authority_profile_refs": authority_profile_refs,
        "scope_profile": scope,
        "required_constructs": resolution_inputs.required_constructs,
        "candidate_construct_proposals": resolution_inputs.candidate_construct_proposals,
        "capability_resolutions": capability_rows,
        "scenario_family_construct_rows": rows,
    }
    return _sha256_json_value(payload)


def _sha256_json_value(value: object) -> str:
    encoded = json.dumps(
        _json_binding_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _json_binding_value(value: object) -> object:
    """Convert typed compiler inputs to deterministic JSON without string fallback."""

    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_binding_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_binding_value(item) for item in value]
    if isinstance(value, set | frozenset):
        converted = [_json_binding_value(item) for item in value]
        return sorted(converted, key=lambda item: json.dumps(item, sort_keys=True))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_binding_value(model_dump(mode="json", by_alias=True))
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str | int | float | bool):
        return enum_value
    raise TypeError(f"unsupported_data_requirement_input_value:{type(value).__name__}")


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
    population = (
        scope_profile.population
        if scope_profile and scope_profile.population
        else _enum_text(by_type.get("population_predicate", {}).get("value")) or "population"
    )
    geography = _enum_text(by_type.get("geography_predicate", {}).get("value")) or "geography"
    time = _enum_text(by_type.get("time_predicate", {}).get("value")) or "time"
    return DataRequirementScope(
        population=population,
        geography=geography,
        time=time,
        time_role=(
            scope_profile.time_role
            if scope_profile is not None and scope_profile.time_role is not None
            else "observation_time"
        ),
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

    resolution = _problem_domain_for_scenario(scenario)
    return _ScenarioAdapterInput(
        scenario_id=_text(scenario.get("scenario_id")) or "scenario",
        text=_scenario_text(scenario),
        domain=resolution.domain,
        authority_type=_authority_type_for_scenario(scenario),
        domain_resolution=resolution,
        scope_profile=_scenario_scope_profile(scenario),
    )


def _legacy_scenario_family_declaration(
    scenario: Mapping[str, Any],
) -> tuple[tuple[str, ...], str]:
    """Keep a missing legacy family frontier distinct from an explicit empty one."""

    contract = scenario.get("expected_evidence_contract")
    if "expected_evidence_contract" not in scenario:
        return (), "not_supplied"
    if not isinstance(contract, Mapping):
        raise ScenarioFamilyDeclarationInputError(
            "family_contract_wrong_type", "expected_evidence_contract"
        )
    field = "admissible_data_source_families"
    if field not in contract:
        return (), "not_supplied"
    raw = contract[field]
    if isinstance(raw, str):
        values: tuple[object, ...] = (raw,)
    elif isinstance(raw, Sequence) and not isinstance(raw, bytes | bytearray):
        values = tuple(raw)
    else:
        raise ScenarioFamilyDeclarationInputError(
            "family_frontier_wrong_type", f"expected_evidence_contract.{field}"
        )
    families: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ScenarioFamilyDeclarationInputError(
                "family_name_invalid", f"expected_evidence_contract.{field}[{index}]"
            )
        family = value.strip()
        if family not in families:
            families.append(family)
    if families:
        return tuple(families), "declared"
    return (), "explicit_empty"


def _scenario_scope_profile(
    scenario: Mapping[str, Any],
) -> _ScenarioScopeProfile | None:
    """Join every supplied scope and required-construct source without promotion."""

    source_profiles: list[tuple[str, object]] = []
    for key in _SCENARIO_PROFILE_TOP_LEVEL_ALIASES:
        if key in scenario:
            source_profiles.append((key, scenario[key]))
    context = scenario.get("context")
    if isinstance(context, Mapping):
        for key in _SCENARIO_PROFILE_CONTEXT_ALIASES:
            if key in context:
                source_profiles.append((f"context.{key}", context[key]))

    parsed = tuple(
        _parse_scenario_scope_profile(raw_profile, source=source)
        for source, raw_profile in source_profiles
    )
    direct_required = tuple(
        dict.fromkeys(
            construct
            for key in _SCENARIO_DIRECT_REQUIRED_CONSTRUCT_ALIASES
            if key in scenario
            for construct in _scenario_profile_construct_aliases(
                {key: scenario[key]},
                source="scenario",
                aliases=(key,),
                conflict_code="scenario_direct_construct_alias_conflict",
            )
        )
    )
    direct_proposals = (
        tuple(
            dict.fromkeys(
                construct
                for key in _SCENARIO_DIRECT_CANDIDATE_CONSTRUCT_ALIASES
                if key in scenario
                for construct in _scenario_profile_construct_aliases(
                    {key: scenario[key]},
                    source="scenario",
                    aliases=(key,),
                    conflict_code="scenario_candidate_proposal_alias_conflict",
                )
            )
        )
        if any(key in scenario for key in _SCENARIO_DIRECT_CANDIDATE_CONSTRUCT_ALIASES)
        else ()
    )

    if not parsed:
        required = direct_required
        proposals = direct_proposals
        if not required and not proposals:
            return None
        return _ScenarioScopeProfile(
            profile_id=_text(scenario.get("scenario_id")) or "scenario",
            required_constructs=required,
            candidate_construct_proposals=proposals,
        )

    primary = parsed[0]
    primary_scope = (
        primary.profile_id,
        primary.jurisdiction,
        primary.time_start,
        primary.time_end,
        primary.time_role,
        primary.granularity,
        primary.population,
        primary.entity_scope,
    )
    if any(
        (
            profile.profile_id,
            profile.jurisdiction,
            profile.time_start,
            profile.time_end,
            profile.time_role,
            profile.granularity,
            profile.population,
            profile.entity_scope,
        )
        != primary_scope
        for profile in parsed[1:]
    ):
        raise ScenarioScopeProfileInputError(
            "profile_source_alias_conflict",
            ",".join(source for source, _ in source_profiles),
        )
    return _ScenarioScopeProfile(
        profile_id=primary.profile_id,
        jurisdiction=primary.jurisdiction,
        time_start=primary.time_start,
        time_end=primary.time_end,
        time_role=primary.time_role,
        granularity=primary.granularity,
        population=primary.population,
        entity_scope=primary.entity_scope,
        unrepresented_fields=tuple(
            sorted({field for profile in parsed for field in profile.unrepresented_fields})
        ),
        required_constructs=tuple(
            dict.fromkeys(
                construct
                for values in (
                    *(profile.required_constructs for profile in parsed),
                    direct_required,
                )
                for construct in values
            )
        ),
        candidate_construct_proposals=tuple(
            dict.fromkeys(
                proposal
                for values in (
                    *(profile.candidate_construct_proposals for profile in parsed),
                    direct_proposals,
                )
                for proposal in values
            )
        ),
    )


def _parse_scenario_scope_profile(
    raw_profile: object,
    *,
    source: str,
) -> _ScenarioScopeProfile:
    if not isinstance(raw_profile, Mapping):
        raise ScenarioScopeProfileInputError("profile_source_wrong_type", source)

    identity_values: list[tuple[str, str]] = []
    for key in ("profile_id", "profile_ref", "versioned_profile_id", "id", "name"):
        if key not in raw_profile:
            continue
        value = raw_profile[key]
        if not isinstance(value, str) or not value.strip():
            raise ScenarioScopeProfileInputError("profile_identity_invalid", f"{source}.{key}")
        identity_values.append((key, value.strip()))
    if not identity_values:
        raise ScenarioScopeProfileInputError("profile_identity_missing", source)
    profile_id = identity_values[0][1]
    if any(value != profile_id for _, value in identity_values[1:]):
        raise ScenarioScopeProfileInputError("profile_identity_alias_conflict", source)

    scope_value = raw_profile.get("scope", {})
    if "scope" in raw_profile and not isinstance(scope_value, Mapping):
        raise ScenarioScopeProfileInputError("profile_scope_wrong_type", f"{source}.scope")
    scope = scope_value if isinstance(scope_value, Mapping) else {}

    jurisdiction = _scenario_profile_text_alias(
        tuple(
            (path, mapping[key])
            for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
            for key in ("jurisdiction",)
            if key in mapping
        ),
        conflict_code="profile_jurisdiction_alias_conflict",
    )

    interval_sources: list[tuple[str, Mapping[str, Any]]] = []
    for path, mapping in ((source, raw_profile), (f"{source}.scope", scope)):
        for key in ("time_window", "temporal_interval"):
            if key not in mapping:
                continue
            interval = mapping[key]
            if not isinstance(interval, Mapping):
                raise ScenarioScopeProfileInputError("profile_interval_wrong_type", f"{path}.{key}")
            interval_sources.append((f"{path}.{key}", interval))

    start_values = [
        (f"{path}.{key}", mapping[key])
        for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
        for key in ("time_start", "start")
        if key in mapping
    ]
    start_values.extend(
        (f"{path}.{key}", interval[key])
        for path, interval in interval_sources
        for key in ("start", "from")
        if key in interval
    )
    time_start = _scenario_profile_text_alias(
        tuple(start_values),
        conflict_code="profile_time_start_alias_conflict",
    )

    end_values = [
        (f"{path}.{key}", mapping[key])
        for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
        for key in ("time_end", "end")
        if key in mapping
    ]
    end_values.extend(
        (f"{path}.{key}", interval[key])
        for path, interval in interval_sources
        for key in ("end", "to")
        if key in interval
    )
    time_end = _scenario_profile_text_alias(
        tuple(end_values),
        conflict_code="profile_time_end_alias_conflict",
    )
    time_role = _scenario_profile_text_alias(
        tuple(
            (f"{path}.time_role", mapping["time_role"])
            for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
            if "time_role" in mapping
        ),
        conflict_code="profile_time_role_alias_conflict",
    )
    if time_role is not None and time_role not in get_args(DataRequirementTimeRole):
        raise ScenarioScopeProfileInputError("profile_time_role_invalid", f"{source}.time_role")
    granularity = _scenario_profile_text_alias(
        tuple(
            (f"{path}.granularity", mapping["granularity"])
            for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
            if "granularity" in mapping
        ),
        conflict_code="profile_granularity_alias_conflict",
    )
    population = _scenario_profile_text_alias(
        tuple(
            (f"{path}.population", mapping["population"])
            for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
            if "population" in mapping
        ),
        conflict_code="profile_population_alias_conflict",
    )
    entity_scope = _scenario_profile_text_alias(
        tuple(
            (f"{path}.entity_scope", mapping["entity_scope"])
            for path, mapping in ((source, raw_profile), (f"{source}.scope", scope))
            if "entity_scope" in mapping
        ),
        conflict_code="profile_entity_scope_alias_conflict",
    )

    required_constructs = _scenario_profile_construct_aliases(
        raw_profile,
        source=source,
        aliases=_SCENARIO_PROFILE_REQUIRED_CONSTRUCT_ALIASES,
        conflict_code="profile_required_construct_alias_conflict",
    )
    candidate_construct_proposals = _scenario_profile_construct_aliases(
        raw_profile,
        source=source,
        aliases=_SCENARIO_PROFILE_CANDIDATE_CONSTRUCT_ALIASES,
        conflict_code="profile_candidate_construct_alias_conflict",
    )
    known_profile_fields = {
        "profile_id",
        "profile_ref",
        "versioned_profile_id",
        "id",
        "name",
        "scope",
        "jurisdiction",
        "time_window",
        "temporal_interval",
        "time_start",
        "start",
        "time_end",
        "end",
        "time_role",
        "granularity",
        "population",
        "entity_scope",
        *_SCENARIO_PROFILE_REQUIRED_CONSTRUCT_ALIASES,
        *_SCENARIO_PROFILE_CANDIDATE_CONSTRUCT_ALIASES,
    }
    unrepresented_fields = [
        f"{source}.{key}" for key in raw_profile if key not in known_profile_fields
    ]
    known_scope_fields = {
        "jurisdiction",
        "time_window",
        "temporal_interval",
        "time_start",
        "start",
        "time_end",
        "end",
        "time_role",
        "granularity",
        "population",
        "entity_scope",
    }
    unrepresented_fields.extend(
        f"{source}.scope.{key}" for key in scope if key not in known_scope_fields
    )
    for interval_path, interval in interval_sources:
        unrepresented_fields.extend(
            f"{interval_path}.{key}"
            for key in interval
            if key not in {"start", "from", "end", "to"}
        )
    return _ScenarioScopeProfile(
        profile_id=profile_id,
        jurisdiction=jurisdiction,
        time_start=time_start,
        time_end=time_end,
        time_role=time_role,
        granularity=granularity,
        population=population,
        entity_scope=entity_scope,
        unrepresented_fields=tuple(sorted(set(unrepresented_fields))),
        required_constructs=required_constructs,
        candidate_construct_proposals=candidate_construct_proposals,
    )


def _scenario_profile_text_alias(
    values: tuple[tuple[str, object], ...],
    *,
    conflict_code: str,
) -> str | None:
    normalized: list[tuple[str, str | None]] = []
    for path, value in values:
        if value is None:
            normalized.append((path, None))
        elif isinstance(value, str) and value.strip():
            normalized.append((path, value.strip()))
        else:
            raise ScenarioScopeProfileInputError("profile_text_invalid", path)
    if not normalized:
        return None
    first = normalized[0][1]
    if any(value != first for _, value in normalized[1:]):
        raise ScenarioScopeProfileInputError(
            conflict_code, ",".join(path for path, _ in normalized)
        )
    return first


def _scenario_profile_construct_aliases(
    raw_profile: Mapping[str, Any],
    *,
    source: str,
    aliases: tuple[str, ...],
    conflict_code: str,
) -> tuple[str, ...]:
    normalized: list[tuple[str, tuple[str, ...]]] = []
    for key in aliases:
        if key not in raw_profile:
            continue
        raw_value = raw_profile[key]
        if raw_value is None:
            raise ScenarioScopeProfileInputError("profile_constructs_wrong_type", f"{source}.{key}")
        elif isinstance(raw_value, str):
            values = (raw_value,)
        elif isinstance(raw_value, Sequence) and not isinstance(raw_value, bytes | bytearray):
            values = tuple(raw_value)
        else:
            raise ScenarioScopeProfileInputError("profile_constructs_wrong_type", f"{source}.{key}")
        refs: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ScenarioScopeProfileInputError("profile_construct_invalid", f"{source}.{key}")
            construct = value.strip().removeprefix("construct:")
            if not construct:
                raise ScenarioScopeProfileInputError("profile_construct_invalid", f"{source}.{key}")
            if construct not in refs:
                refs.append(construct)
        normalized.append((key, tuple(refs)))
    if not normalized:
        return ()
    first = normalized[0][1]
    if any(value != first for _, value in normalized[1:]):
        raise ScenarioScopeProfileInputError(
            conflict_code, f"{source}." + ",".join(key for key, _ in normalized)
        )
    return first


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


def _problem_domain_for_scenario(scenario: Mapping[str, Any]) -> _ScenarioDomainResolution:
    """Resolve exact declared vocabulary, never content or an opaque identifier."""

    def spelling(value: str) -> tuple[str, ...]:
        return tuple(value.casefold().replace("-", " ").replace("_", " ").split())

    aliases = {
        spelling(token): domain
        for domain in governance.ProblemDomain
        for token in (domain.name, domain.value)
    }
    # Explicit vocabulary aliases, not a token-presence or topic classifier.
    aliases.update(
        {
            ("health",): governance.ProblemDomain.HEALTHCARE,
            ("health", "care"): governance.ProblemDomain.HEALTHCARE,
            ("образование",): governance.ProblemDomain.EDUCATION,
        }
    )
    raw_inputs: list[tuple[str, str]] = []
    resolutions: list[tuple[tuple[str, ...], governance.ProblemDomain | None]] = []
    for key in ("domain", "domain_hint"):
        if key not in scenario:
            continue
        raw = scenario[key]
        if not isinstance(raw, str):
            raise ScenarioDomainInputError("domain_wrong_type", key)
        text = raw.value if isinstance(raw, governance.ProblemDomain) else str(raw)
        token = spelling(text)
        if not token:
            raise ScenarioDomainInputError("domain_empty", key)
        raw_inputs.append((key, text))
        base_token = token[:-1] if token[-1] == "policy" else token
        resolutions.append((token, aliases.get(base_token)))
    if not resolutions:
        return _ScenarioDomainResolution(
            governance.ProblemDomain.CUSTOM, (), "not_supplied", "domain_not_supplied"
        )
    first_token, first_domain = resolutions[0]
    if len(resolutions) == 2:
        second_token, second_domain = resolutions[1]
        compatible = (first_domain is not None and first_domain == second_domain) or (
            first_domain is None and second_domain is None and first_token == second_token
        )
        if not compatible:
            raise ScenarioDomainInputError("domain_alias_conflict", "domain_hint")
    return _ScenarioDomainResolution(
        first_domain or governance.ProblemDomain.CUSTOM,
        tuple(raw_inputs),
        "resolved" if first_domain is not None else "unresolved",
        "domain_vocabulary_resolved" if first_domain is not None else "domain_vocabulary_unknown",
    )


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
    text = str(value or "").strip().casefold()
    chars = [char if char.isalnum() else "-" for char in text]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug or "unknown"


__all__ = [
    "ClaimConstructDeclarationInputError",
    "DataRequirementCompiler",
    "ScenarioDomainInputError",
    "compile_data_requirements_for_scenario",
    "compiled_requirements_for_world_slot",
    "data_requirement_compilation_audit_surface",
    "parse_data_requirement_compilation_report",
    "write_data_requirement_compilation_report",
]
