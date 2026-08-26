"""Public analytics cross graph module API."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.transportability import TransportMode
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    CompositionCertificateRef,
    CrossGraphEvidenceProfileRef,
    InterfaceMappingRef,
    SCMFragmentRef,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.ir.analytics.context import ContextProfile
else:
    from polisyos.ir.analytics.context import ContextProfile

_SCHEMA_NAME = "ir.cross_graph_evidence_profile"
_SCHEMA_VERSION = "2.1"
_SCM_FRAGMENT_SCHEMA_NAME = "ir.scm_fragment"
_SCM_FRAGMENT_SCHEMA_VERSION = "1.2"
_INTERFACE_MAPPING_SCHEMA_NAME = "ir.interface_mapping"
_INTERFACE_MAPPING_SCHEMA_VERSION = "1.0"
_COMPOSITION_CERTIFICATE_SCHEMA_NAME = "ir.composition_certificate"
_COMPOSITION_CERTIFICATE_SCHEMA_VERSION = "1.2"


class BenchmarkCausalEdge(BaseModel):
    """Neutral causal-edge descriptor used by an academic benchmark suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cause: str
    effect: str


class BenchmarkScholarQuery(BaseModel):
    """Neutral scholar-coverage query used by an academic benchmark suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cause: str
    effect: str
    min_trust: float = Field(default=0.5, ge=0.0, le=1.0)
    support_mode: str = "hybrid"
    min_results: int = 1


class BenchmarkCredibilityPolicy(BaseModel):
    """Evidence thresholds used when an academic benchmark evaluates a causal edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    min_unique_works: int = Field(default=2, ge=1)
    require_conflict_free: bool = True
    min_design_tier: int | None = Field(default=3, ge=1, le=4)
    max_evidence_age_years: int | None = Field(default=None, ge=1)


class AcademicBenchmarkScenario(BaseModel):
    """Neutral scenario definition used by an academic benchmark suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    title: str
    policy_domain: str = ""
    weight: float = Field(default=1.0, ge=0.1)
    credibility_policy: BenchmarkCredibilityPolicy = Field(
        default_factory=BenchmarkCredibilityPolicy
    )
    causal_edges: list[BenchmarkCausalEdge] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    scholar_queries: list[BenchmarkScholarQuery] = Field(default_factory=list)


class AcademicBenchmarkSuite(BaseModel):
    """Neutral, serializable suite definition for academic benchmark scenarios."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str = "academic_usefulness"
    scenarios: list[AcademicBenchmarkScenario] = Field(default_factory=list)


def load_benchmark_suite(path: Path) -> AcademicBenchmarkSuite:
    """Load an academic benchmark suite from its JSON representation."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "scenarios" in payload:
        return AcademicBenchmarkSuite.model_validate(payload)
    if isinstance(payload, list):
        return AcademicBenchmarkSuite(
            scenarios=[AcademicBenchmarkScenario.model_validate(item) for item in payload]
        )
    raise ValueError(f"Unsupported benchmark suite payload at {path}")


def write_need_backlog(path: Path, items: list[dict[str, Any]]) -> None:
    """Write cross-graph evidence needs as a JSONL producer artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


class InterfaceRole(str, Enum):
    """Interface role public type."""

    INPUT = "input"
    OUTPUT = "output"
    SHARED = "shared"


class InterfaceVariableSchema(BaseModel):
    """Interface variable schema data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable_name: str = Field(min_length=1)
    role: InterfaceRole = InterfaceRole.SHARED
    observed: bool = True
    definition: str = ""
    unit: str | None = None
    measurement_model_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FragmentInterfaceSchema(BaseModel):
    """Fragment interface schema data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1)
    semantic_namespace: str = Field(min_length=1)
    variables: list[InterfaceVariableSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_variables(self) -> FragmentInterfaceSchema:
        names = [variable.variable_name for variable in self.variables]
        if len(set(names)) != len(names):
            raise ValueError("FragmentInterfaceSchema variables must be unique")
        return self


AllowedAlignmentType = Literal["exact", "scale_linked", "proxy", "latent_bridge", "incompatible"]
_DEFAULT_ACYCLIC_ALIGNMENT_TYPES: tuple[AllowedAlignmentType, ...] = (
    "exact",
    "scale_linked",
    "proxy",
    "latent_bridge",
    "incompatible",
)
_DEFAULT_CYCLIC_ALIGNMENT_TYPES: tuple[AllowedAlignmentType, ...] = (
    "exact",
    "scale_linked",
)


class CycleType(str, Enum):
    """Declared cycle semantics for one SCM fragment."""

    ACYCLIC = "acyclic"
    SIMPLE_CYCLIC = "simple_cyclic"
    EQUILIBRIUM_CONTRACTIVE = "equilibrium_contractive"
    EQUILIBRIUM_LINEAR_STABLE = "equilibrium_linear_stable"
    DSCM_SEMANTICS = "dscm_semantics"
    FINITE_P_SEPARATION = "finite_p_separation"
    UNSUPPORTED = "unsupported"


class CycleScope(str, Enum):
    """Where cyclic structure appears relative to the fragment boundary."""

    NONE = "none"
    INTERNAL_SCC = "internal_scc"
    CROSS_FRAGMENT_SCC = "cross_fragment_scc"


class SolverKind(str, Enum):
    """Witness family used to justify well-posedness for a cyclic SCC."""

    CLOSED_FORM = "closed_form"
    LINEAR_SOLVE = "linear_solve"
    CONTRACTIVE_FIXED_POINT = "contractive_fixed_point"
    ODE_EQUILIBRIUM = "ode_equilibrium"


class UniquenessScope(str, Enum):
    """Declared uniqueness scope for a cycle witness."""

    SCC = "scc"
    ALL_SCC = "all_scc"
    EVERY_SUBSET = "every_subset"


class InterventionalClosure(str, Enum):
    """How much of the declared intervention family preserves the witness class."""

    FULL = "full"
    INTERFACE_ONLY = "interface_only"
    OBSERVED_ONLY = "observed_only"
    NONE = "none"


class MarkovSemantics(str, Enum):
    """Graphical Markov semantics associated with the cycle witness."""

    D_SEPARATION = "d_separation"
    SIGMA_SEPARATION = "sigma_separation"
    P_SEPARATION = "p_separation"
    NONE = "none"


class GraphAuditGuarantee(str, Enum):
    """Strength of the graphical audit claim carried by the fragment."""

    NONE = "none"
    SEMANTIC_ONLY = "semantic_only"
    LATENT_PROJECTION_RESPECTED = "latent_projection_respected"


class CompositionPolicy(str, Enum):
    """Declared automation policy for fragment composition."""

    ALLOW = "allow"
    ALLOW_BOUNDS_ONLY = "allow_bounds_only"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    BLOCK = "block"


class CycleWitness(BaseModel):
    """Machine-auditable witness for one cyclic SCC."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scc_id: str = Field(min_length=1)
    solver_kind: SolverKind
    uniqueness_scope: UniquenessScope
    interventional_closure: InterventionalClosure
    markov_semantics: MarkovSemantics
    initial_condition_dependent: bool = False
    existence_conditions: list[str] = Field(default_factory=list)
    uniqueness_conditions: list[str] = Field(default_factory=list)
    audit_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_lists(self) -> CycleWitness:
        for field_name, values in (
            ("existence_conditions", self.existence_conditions),
            ("uniqueness_conditions", self.uniqueness_conditions),
            ("audit_refs", self.audit_refs),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain empty strings")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must be unique")
        return self


class SCMFragment(BaseModel):
    """SCM fragment public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.2", pattern=r"^\d+\.\d+$")
    fragment_id: str = Field(min_length=1)
    graph_ref: str = Field(min_length=1)
    semantic_namespace: str = Field(min_length=1)
    interface_variables: list[str] = Field(default_factory=list)
    exposed_inputs: list[str] = Field(default_factory=list)
    exposed_outputs: list[str] = Field(default_factory=list)
    latent_summary: dict[str, str] = Field(default_factory=dict)
    measurement_models: dict[str, str] = Field(default_factory=dict)
    variable_definitions: dict[str, str] = Field(default_factory=dict)
    variable_units: dict[str, str] = Field(default_factory=dict)
    variable_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)
    cycle_type: CycleType = CycleType.ACYCLIC
    cycle_scope: CycleScope = CycleScope.NONE
    cycle_witnesses: list[CycleWitness] = Field(default_factory=list)
    allowed_alignment_types: list[AllowedAlignmentType] = Field(default_factory=list)
    graph_audit_guarantee: GraphAuditGuarantee = GraphAuditGuarantee.NONE
    composition_policy: CompositionPolicy = CompositionPolicy.ALLOW

    @model_validator(mode="before")
    @classmethod
    def _backfill_cycle_contract_defaults(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        cycle_type = str(normalized.get("cycle_type", CycleType.ACYCLIC.value)).strip().lower()
        if not cycle_type:
            cycle_type = CycleType.ACYCLIC.value

        if "allowed_alignment_types" not in normalized or not normalized["allowed_alignment_types"]:
            normalized["allowed_alignment_types"] = list(
                _DEFAULT_CYCLIC_ALIGNMENT_TYPES
                if cycle_type != CycleType.ACYCLIC.value
                else _DEFAULT_ACYCLIC_ALIGNMENT_TYPES
            )

        if "composition_policy" not in normalized or normalized["composition_policy"] in (None, ""):
            normalized["composition_policy"] = (
                CompositionPolicy.ALLOW.value
                if cycle_type == CycleType.ACYCLIC.value
                else CompositionPolicy.BLOCK.value
            )
        return normalized

    @model_validator(mode="after")
    def _validate_interfaces(self) -> SCMFragment:
        interface_set = set(self.interface_variables)
        if len(interface_set) != len(self.interface_variables):
            raise ValueError("interface_variables must be unique")
        if any(not value.strip() for value in self.interface_variables):
            raise ValueError("interface_variables must not contain empty names")

        for field_name, values in (
            ("exposed_inputs", self.exposed_inputs),
            ("exposed_outputs", self.exposed_outputs),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must be unique")
            unknown = sorted(set(values) - interface_set)
            if unknown:
                raise ValueError(f"{field_name} must be a subset of interface_variables: {unknown}")

        for field_name, mapping in (
            ("measurement_models", self.measurement_models),
            ("variable_definitions", self.variable_definitions),
            ("variable_units", self.variable_units),
            ("variable_metadata", self.variable_metadata),
        ):
            unknown = sorted(set(mapping) - interface_set)
            if unknown:
                raise ValueError(
                    f"{field_name} keys must be a subset of interface_variables: {unknown}"
                )

        if len(set(self.allowed_alignment_types)) != len(self.allowed_alignment_types):
            raise ValueError("allowed_alignment_types must be unique")
        if not self.allowed_alignment_types:
            raise ValueError("allowed_alignment_types must not be empty")

        witness_ids = [witness.scc_id for witness in self.cycle_witnesses]
        if len(set(witness_ids)) != len(witness_ids):
            raise ValueError("cycle_witnesses must have unique scc_id values")

        if self.cycle_type is CycleType.ACYCLIC:
            if self.cycle_scope is not CycleScope.NONE:
                raise ValueError("acyclic fragments must declare cycle_scope='none'")
            if self.cycle_witnesses:
                raise ValueError("acyclic fragments must not declare cycle_witnesses")
        else:
            if self.cycle_scope is CycleScope.NONE:
                raise ValueError("cyclic fragments must declare a non-empty cycle_scope")
            if not self.cycle_witnesses:
                raise ValueError("cyclic fragments must declare at least one cycle witness")
            if (
                self.cycle_type
                in {
                    CycleType.DSCM_SEMANTICS,
                    CycleType.FINITE_P_SEPARATION,
                    CycleType.UNSUPPORTED,
                }
                and self.composition_policy is CompositionPolicy.ALLOW
            ):
                raise ValueError("research-only or unsupported cycle types cannot auto-compose")
            if (
                self.cycle_scope is CycleScope.CROSS_FRAGMENT_SCC
                and self.composition_policy is CompositionPolicy.ALLOW
            ):
                raise ValueError("cross-fragment cycles cannot auto-compose")
            if (
                any(witness.initial_condition_dependent for witness in self.cycle_witnesses)
                and self.composition_policy is CompositionPolicy.ALLOW
            ):
                raise ValueError("initial-condition-dependent cycles cannot auto-compose")
            if self.composition_policy is CompositionPolicy.ALLOW and any(
                witness.interventional_closure is InterventionalClosure.NONE
                for witness in self.cycle_witnesses
            ):
                raise ValueError("cyclic auto-composition requires interventional closure")
            if self.composition_policy is CompositionPolicy.ALLOW and any(
                witness.markov_semantics is not MarkovSemantics.SIGMA_SEPARATION
                for witness in self.cycle_witnesses
            ):
                raise ValueError("cyclic auto-composition requires sigma-separation witnesses")
            if self.composition_policy is CompositionPolicy.ALLOW and any(
                alignment_type not in _DEFAULT_CYCLIC_ALIGNMENT_TYPES
                for alignment_type in self.allowed_alignment_types
            ):
                raise ValueError(
                    "cyclic auto-composition only supports exact or scale_linked interfaces"
                )
        return self

    def to_interface_schema(self) -> FragmentInterfaceSchema:
        input_set = set(self.exposed_inputs)
        output_set = set(self.exposed_outputs)
        latent_set = set(self.latent_summary)
        variables: list[InterfaceVariableSchema] = []
        for variable_name in self.interface_variables:
            if variable_name in input_set and variable_name in output_set:
                role = InterfaceRole.SHARED
            elif variable_name in input_set:
                role = InterfaceRole.INPUT
            elif variable_name in output_set:
                role = InterfaceRole.OUTPUT
            else:
                role = InterfaceRole.SHARED
            variables.append(
                InterfaceVariableSchema(
                    variable_name=variable_name,
                    role=role,
                    observed=variable_name not in latent_set,
                    definition=self.variable_definitions.get(variable_name, ""),
                    unit=self.variable_units.get(variable_name),
                    measurement_model_ref=self.measurement_models.get(variable_name),
                    metadata=dict(self.variable_metadata.get(variable_name, {})),
                )
            )
        return FragmentInterfaceSchema(
            fragment_id=self.fragment_id,
            semantic_namespace=self.semantic_namespace,
            variables=variables,
        )


class InterfaceVariableBinding(BaseModel):
    """Interface variable binding public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1)
    variable_name: str = Field(min_length=1)
    observed: bool = True
    measurement_model_ref: str | None = None
    definition: str = ""
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterfaceMappingEntry(BaseModel):
    """Interface mapping entry data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    interface_id: str = Field(min_length=1)
    canonical_node_id: str = Field(min_length=1)
    bindings: list[InterfaceVariableBinding] = Field(default_factory=list)
    observed: bool = True
    alignment_type: Literal["exact", "scale_linked", "proxy", "latent_bridge", "incompatible"] = (
        "exact"
    )
    reviewer: Literal["automated", "pending_review", "human_verified"] = "automated"
    assumptions_introduced: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bindings(self) -> InterfaceMappingEntry:
        if len(self.bindings) < 2:
            raise ValueError("InterfaceMappingEntry must contain at least two bindings")
        keys = [(item.fragment_id, item.variable_name) for item in self.bindings]
        if len(set(keys)) != len(keys):
            raise ValueError("InterfaceMappingEntry bindings must be unique")
        return self


class InterfaceMapping(BaseModel):
    """Interface mapping public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fragment_ids: list[str] = Field(default_factory=list)
    entries: list[InterfaceMappingEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_entries(self) -> InterfaceMapping:
        if len(set(self.fragment_ids)) != len(self.fragment_ids):
            raise ValueError("fragment_ids must be unique")
        entry_ids = [entry.interface_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("InterfaceMapping entry interface_id values must be unique")
        node_ids = [entry.canonical_node_id for entry in self.entries]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("InterfaceMapping canonical_node_id values must be unique")
        return self


class QueryPreservationCertificate(BaseModel):
    """Machine-checkable per-query preservation verdict for composed graphs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["preserved", "broken", "unknown"]
    reason_code: str = Field(min_length=1)
    query_semantics: str = ""
    source_fragment_id: str | None = None
    witness_fragment_ids: list[str] = Field(default_factory=list)
    source_witness_kind: str = ""
    assumption_boundary: str | None = None
    theorem_family: str | None = None
    identification_status: str | None = None
    identification_method: str | None = None
    identification_trace: list[str] = Field(default_factory=list)
    obligations_checked: list[dict[str, Any]] = Field(default_factory=list)
    latent_projection_signature: dict[str, Any] | None = None
    latent_projection_ref: str | None = None
    identifying_estimand: dict[str, Any] | None = None
    required_distributions: list[dict[str, Any]] = Field(default_factory=list)
    positive_witness: dict[str, Any] | None = None
    hedge_witness: dict[str, Any] | None = None
    negative_certificate_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


_COMPLETENESS_SCOPE_V1 = "exact_observed_dag_adjustment_v1"
_COMPLETENESS_BASIS_V1: tuple[str, ...] = (
    "structured_cospan_composition",
    "dag_adjustment_complete",
)
_NON_COMPLETENESS_REASON_DEFAULT = "engine_checks_only_backdoor_adjustment"


def completeness_scope_for_composition(
    *,
    graph_type_value: str,
    alignment_types: Sequence[str],
    binding_observed_flags: Sequence[bool] = (),
    reviewers: Sequence[str],
    review_status: Literal["clear", "pending_review"],
    structure_status: Literal["valid", "invalid"],
    cycle_semantics_mode: str | None = None,
    directed_cycle_present: bool = False,
) -> dict[str, Any]:
    """Classify whether a certificate falls inside the in-scope completeness subclass.

    Returns a dict with the keys
    ``completeness_scope`` / ``completeness_basis`` / ``non_completeness_reason``
    suitable for merging into ``CompositionCertificate.metadata``. The classifier
    tracks the research scope described on :class:`CompositionCertificate`:
    exact or human-verified interface alignments, DAG fragments, observed
    bindings, and cleared review status. Any departure is marked out of scope
    with a reason code that mirrors ``non_completeness_reason`` vocabulary.
    """

    reasons: list[str] = []
    normalized_alignment_types = tuple(str(entry) for entry in alignment_types)
    normalized_reviewers = tuple(str(entry) for entry in reviewers)
    normalized_observed_flags = tuple(bool(flag) for flag in binding_observed_flags)

    if structure_status != "valid":
        reasons.append("structure_invalid")
    if review_status != "clear":
        reasons.append("pending_review")
    if graph_type_value != "dag":
        reasons.append("non_dag_composition")
    if directed_cycle_present or (
        cycle_semantics_mode is not None and cycle_semantics_mode not in {"", "acyclic", "none"}
    ):
        reasons.append("cyclic_or_sigma_semantics")
    if any(not observed for observed in normalized_observed_flags):
        reasons.append("unobserved_interface_binding")

    allowed_alignment = {"exact", "scale_linked"}
    for alignment_type in normalized_alignment_types:
        if alignment_type in allowed_alignment:
            continue
        if alignment_type == "proxy":
            reasons.append("proxy_alignment")
        elif alignment_type == "latent_bridge":
            reasons.append("latent_bridge_alignment")
        elif alignment_type == "incompatible":
            reasons.append("incompatible_alignment")
        else:
            reasons.append(f"unsupported_alignment_type:{alignment_type}")

    for reviewer in normalized_reviewers:
        if reviewer == "pending_review":
            reasons.append("pending_review_alignment")

    deduped_reasons: list[str] = []
    for reason in reasons:
        if reason not in deduped_reasons:
            deduped_reasons.append(reason)

    if not deduped_reasons:
        return {
            "completeness_scope": _COMPLETENESS_SCOPE_V1,
            "completeness_basis": list(_COMPLETENESS_BASIS_V1),
            "non_completeness_reason": None,
        }

    return {
        "completeness_scope": None,
        "completeness_basis": list(_COMPLETENESS_BASIS_V1),
        "non_completeness_reason": ";".join(deduped_reasons),
    }


class CompositionCertificate(BaseModel):
    """Composition certificate public type.

    Category-theoretic completeness scope
    -------------------------------------
    This certificate is complete only for the subclass
    ``exact_observed_dag_adjustment_v1``:

      * fragment graphs are DAGs (``graph_type == "dag"``);
      * interface alignments are ``exact`` or human-verified ``exact``
        (``scale_linked`` is also admissible);
      * no ``proxy`` and no ``latent_bridge`` alignments;
      * all interface bindings are observed;
      * no alignment entry is ``pending_review``;
      * no directed cycle (``cycle_semantics_mode`` is ``acyclic``);
      * checked queries are single-world ``INTERVENTIONAL`` or
        ``SOFT_INTERVENTION`` queries represented as
        ``(treatment, outcome, conditioning_set)`` whose source identification
        is via covariate adjustment.

    Completeness claim
    ~~~~~~~~~~~~~~~~~~
    Within this scope, the certificate is complete for
    *adjustment-identifiability preservation*: if ``status == "preserved"``
    and the query fingerprint is in-scope, then the recorded conditioning set
    remains a valid adjustment set for ``P(Y | do(X))`` in the composed DAG
    — iff. Conversely, if the conditioning set is preserved as an adjustment
    set after composition, the certificate must return ``preserved``.

    Out of scope
    ~~~~~~~~~~~~
    Any of the following puts the certificate outside the completeness scope:

      * front-door-identifiable or general ID-identifiable effects that are
        not adjustment-identifiable;
      * counterfactual, nested-counterfactual, or path-specific queries;
      * proxy or latent-bridge alignments, pending-review alignments;
      * ADMG, PAG, cyclic, or non-DAG compositions;
      * global identifiability claims beyond adjustment preservation.

    Rationale
    ~~~~~~~~~
    The current query-preservation engine checks only backdoor-adjustment
    style obligations via descendant exclusion plus d-/m-separation on
    mutilated relevant subgraphs. Adjustment completeness (Perković et al.)
    is strictly weaker than full identifiability completeness
    (Shpitser–Pearl ID with hedge counter-examples); therefore no certificate
    limited to local ``backdoor_adjustment`` obligations can be complete for
    all identifiable interventional queries.

    Metadata keys
    ~~~~~~~~~~~~~
    The composition pipeline records the classification verdict under
    :attr:`metadata`:

      * ``completeness_scope`` — either ``"exact_observed_dag_adjustment_v1"``
        when the case is in scope, or ``None`` when out of scope.
      * ``completeness_basis`` — list of proof pillars the scope relies on;
        currently ``["structured_cospan_composition", "dag_adjustment_complete"]``.
      * ``non_completeness_reason`` — ``None`` inside the scope, otherwise a
        ``;``-joined list of reason codes explaining which assumption
        dropped (e.g. ``proxy_alignment``, ``latent_bridge_alignment``,
        ``non_dag_composition``, ``pending_review``).

    See :func:`completeness_scope_for_composition` for the classifier used by
    the fragment-composition method.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.2", pattern=r"^\d+\.\d+$")
    structure_status: Literal["valid", "invalid"] = "valid"
    review_status: Literal["clear", "pending_review"] = "clear"
    status: Literal["preserved", "deferred", "broken", "unknown"] = "unknown"
    composed_graph_ref: str | None = None
    interface_mapping_ref: str = Field(min_length=1)
    alignment_report_ref: str = Field(min_length=1)
    checked_queries: dict[str, Literal["preserved", "broken", "unknown"]] = Field(
        default_factory=dict
    )
    query_certificates: dict[str, QueryPreservationCertificate] = Field(default_factory=dict)
    newly_required_assumptions: list[str] = Field(default_factory=list)
    structural_assumptions: list[str] = Field(default_factory=list)
    alignment_assumptions: list[str] = Field(default_factory=list)
    source_fragment_refs: dict[str, str] = Field(default_factory=dict)
    source_fragment_graph_refs: dict[str, str] = Field(default_factory=dict)
    failure_card_bundle_ref: str | None = None
    witness_ref: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _backfill_status_fields(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        status = str(normalized.get("status", "unknown")).strip().lower()
        blocking_reasons = normalized.get("blocking_reasons", [])
        blocking_present = bool(blocking_reasons)
        if "structure_status" not in normalized:
            normalized["structure_status"] = (
                "invalid"
                if status == "broken" or (status == "unknown" and blocking_present)
                else "valid"
            )
        if "review_status" not in normalized:
            normalized["review_status"] = "pending_review" if status == "deferred" else "clear"
        return normalized


class ConceptKind(str, Enum):
    """Concept kind public type."""

    METRIC = "metric"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    LEGAL_CONCEPT = "legal_concept"
    LEGAL_CONSTRAINT = "legal_constraint"
    DATASET = "dataset"
    DATASET_VARIABLE = "dataset_variable"
    SCHOLAR_CLAIM = "scholar_claim"
    CONTEXT_DIMENSION = "context_dimension"


class BridgeRelation(str, Enum):
    """Bridge relation public type."""

    METRIC_TO_VARIABLE = "metric_to_variable"
    PARAMETER_TO_VARIABLE = "parameter_to_variable"
    LEGAL_TO_METRIC = "legal_to_metric"
    LEGAL_TO_VARIABLE = "legal_to_variable"
    DATASET_VAR_TO_VARIABLE = "dataset_var_to_variable"
    CLAIM_TO_VARIABLE = "claim_to_variable"
    CLAIM_TO_EDGE = "claim_to_edge"
    CONTEXT_DIMENSION_TO_VARIABLE = "context_dimension_to_variable"


class EvidenceNeedType(str, Enum):
    """Evidence need type public type."""

    OBJECTIVE_METRIC = "objective_metric"
    KPI_METRIC = "kpi_metric"
    SUCCESS_CRITERION_METRIC = "success_criterion_metric"
    CONSTRAINT_METRIC_OR_SLOT = "constraint_metric_or_slot"
    PARAMETER_NEED = "parameter_need"
    MECHANISM_NEED = "mechanism_need"
    LEGAL_APPLICABILITY_NEED = "legal_applicability_need"
    CAUSAL_EDGE_NEED = "causal_edge_need"


class LegalStatus(str, Enum):
    """Legal status public type."""

    ALLOWED = "allowed"
    CONSTRAINED = "constrained"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


class ObservabilityStatus(str, Enum):
    """Observability status public type."""

    DIRECT = "direct"
    PROXY_ONLY = "proxy_only"
    MISSING = "missing"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    """Evidence status public type."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"
    UNSUPPORTED = "unsupported"


class TransportStatus(str, Enum):
    """Transport status public type."""

    IDENTIFIED = "identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    BOUNDED_NON_IDENTIFIED = "bounded_non_identified"
    UNSUPPORTED = "unsupported"


class EvidenceSourceKind(str, Enum):
    """Evidence source kind public type."""

    ACADEMIC = "academic"
    DATASETS = "datasets"
    LEGAL = "legal"
    BENCHMARK = "benchmark"


class EvidenceSourceState(str, Enum):
    """Evidence source state data model."""

    AVAILABLE = "available"
    MISSING_CONFIG = "missing_config"
    MISSING_PATH = "missing_path"
    INIT_FAILED = "init_failed"
    QUERY_FAILED = "query_failed"
    DISABLED = "disabled"


class CanonicalConcept(BaseModel):
    """Canonical concept public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_id: str
    concept_kind: ConceptKind
    label: str = ""
    join_keys: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConceptBridge(BaseModel):
    """Concept bridge public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    src_system: str
    src_kind: str
    src_id: str
    dst_concept_id: str
    relation: BridgeRelation
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: list[str] = Field(default_factory=list)


class EvidenceNeed(BaseModel):
    """Evidence need public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    need_id: str
    need_type: EvidenceNeedType
    source_path: str = ""
    metric_id: str | None = None
    kpi_id: str | None = None
    criterion_id: str | None = None
    parameter_name: str | None = None
    param_path: str | None = None
    intervention_id: str | None = None
    intervention_kind: str | None = None
    constraint_id: str | None = None
    slot_id: str | None = None
    jurisdiction: str | None = None
    policy_domain: str | None = None
    geography: str | None = None
    time_window: str | None = None
    target_context_id: str | None = None
    cause: str | None = None
    effect: str | None = None
    labels: list[str] = Field(default_factory=list)


class CrossGraphDiagnostic(BaseModel):
    """Cross graph diagnostic public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: str = "warn"
    need_id: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceNeedAssessment(BaseModel):
    """Evidence need assessment public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    need: EvidenceNeed
    resolved_concept_ids: list[str] = Field(default_factory=list)
    legal_status: LegalStatus = LegalStatus.UNKNOWN
    observability_status: ObservabilityStatus = ObservabilityStatus.UNKNOWN
    evidence_status: EvidenceStatus = EvidenceStatus.INSUFFICIENT
    transport_status: TransportStatus = TransportStatus.UNSUPPORTED
    transport_mode: TransportMode = TransportMode.NONE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_expert_review: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    diagnostics: list[CrossGraphDiagnostic] = Field(default_factory=list)


class CrossGraphEvidenceSummary(BaseModel):
    """Cross graph evidence summary data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = "ok"
    total_needs: int = 0
    requires_expert_review_count: int = 0
    blocking_need_ids: list[str] = Field(default_factory=list)
    legal_status_counts: dict[str, int] = Field(default_factory=dict)
    observability_status_counts: dict[str, int] = Field(default_factory=dict)
    evidence_status_counts: dict[str, int] = Field(default_factory=dict)
    transport_status_counts: dict[str, int] = Field(default_factory=dict)


class CrossGraphSourceRefs(BaseModel):
    """Cross graph source refs public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    academic_db_path: str | None = None
    academic_index_dir: str | None = None
    datasets_db_path: str | None = None
    legal_db_path: str | None = None


class EvidenceSourceStatus(BaseModel):
    """Evidence source status public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: EvidenceSourceKind
    configured: bool = False
    status: EvidenceSourceState = EvidenceSourceState.MISSING_CONFIG
    path: str | None = None
    detail: str | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)


class CrossGraphEvidenceProfile(BaseModel):
    """Cross graph evidence profile data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("2.1", pattern=r"^\d+\.\d+$")
    summary: CrossGraphEvidenceSummary
    needs: list[EvidenceNeedAssessment] = Field(default_factory=list)
    diagnostics: list[CrossGraphDiagnostic] = Field(default_factory=list)
    ontology_snapshot: list[CanonicalConcept] = Field(default_factory=list)
    bridges: list[ConceptBridge] = Field(default_factory=list)
    source_refs: CrossGraphSourceRefs = Field(default_factory=CrossGraphSourceRefs)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    benchmark_summary: dict[str, Any] = Field(default_factory=dict)
    target_context: ContextProfile | None = None
    notes: list[str] = Field(default_factory=list)


def build_evidence_need_id(
    need_type: EvidenceNeedType,
    *,
    source_path: str,
    payload: dict[str, Any],
) -> str:
    """Build evidence need id."""
    normalized = json.dumps(
        {
            "need_type": need_type.value,
            "source_path": source_path,
            "payload": payload,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{need_type.value}:{digest}"


def persist_scm_fragment(
    store: ArtifactStore,
    fragment: SCMFragment,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SCM_FRAGMENT_SCHEMA_NAME,
    schema_version: str = _SCM_FRAGMENT_SCHEMA_VERSION,
) -> SCMFragmentRef:
    """Persist scm fragment helper."""
    ref = put_json_artifact(
        store,
        fragment.model_dump(mode="json"),
        kind=_SCM_FRAGMENT_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SCMFragmentRef.model_validate(ref)


def load_scm_fragment(
    store: ArtifactStore,
    ref: SCMFragmentRef,
) -> SCMFragment:
    """Load scm fragment."""
    payload = get_json_artifact(store, ref.artifact_id)
    return SCMFragment.model_validate(payload)


def persist_interface_mapping(
    store: ArtifactStore,
    mapping: InterfaceMapping,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _INTERFACE_MAPPING_SCHEMA_NAME,
    schema_version: str = _INTERFACE_MAPPING_SCHEMA_VERSION,
) -> InterfaceMappingRef:
    """Persist interface mapping helper."""
    ref = put_json_artifact(
        store,
        mapping.model_dump(mode="json"),
        kind=_INTERFACE_MAPPING_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InterfaceMappingRef.model_validate(ref)


def load_interface_mapping(
    store: ArtifactStore,
    ref: InterfaceMappingRef,
) -> InterfaceMapping:
    """Load interface mapping."""
    payload = get_json_artifact(store, ref.artifact_id)
    return InterfaceMapping.model_validate(payload)


def persist_composition_certificate(
    store: ArtifactStore,
    certificate: CompositionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _COMPOSITION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _COMPOSITION_CERTIFICATE_SCHEMA_VERSION,
) -> CompositionCertificateRef:
    """Persist composition certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind=_COMPOSITION_CERTIFICATE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CompositionCertificateRef.model_validate(ref)


def load_composition_certificate(
    store: ArtifactStore,
    ref: CompositionCertificateRef,
) -> CompositionCertificate:
    """Load composition certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CompositionCertificate.model_validate(payload)


def persist_cross_graph_evidence_profile(
    store: ArtifactStore,
    profile: CrossGraphEvidenceProfile,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION,
) -> CrossGraphEvidenceProfileRef:
    """Persist cross graph evidence profile helper."""
    ref = put_json_artifact(
        store,
        profile.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CrossGraphEvidenceProfileRef.model_validate(ref)


def load_cross_graph_evidence_profile(
    store: ArtifactStore,
    ref: CrossGraphEvidenceProfileRef,
) -> CrossGraphEvidenceProfile:
    """Load cross graph evidence profile."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CrossGraphEvidenceProfile.model_validate(payload)


__all__ = [
    "AllowedAlignmentType",
    "BridgeRelation",
    "CanonicalConcept",
    "CompositionCertificate",
    "CompositionPolicy",
    "ConceptBridge",
    "ConceptKind",
    "CrossGraphDiagnostic",
    "CrossGraphEvidenceProfile",
    "CrossGraphEvidenceSummary",
    "CrossGraphSourceRefs",
    "CycleScope",
    "CycleType",
    "CycleWitness",
    "EvidenceNeed",
    "EvidenceNeedAssessment",
    "EvidenceNeedType",
    "EvidenceSourceKind",
    "EvidenceSourceState",
    "EvidenceSourceStatus",
    "EvidenceStatus",
    "FragmentInterfaceSchema",
    "GraphAuditGuarantee",
    "InterfaceMapping",
    "InterfaceMappingEntry",
    "InterfaceRole",
    "InterfaceVariableBinding",
    "InterfaceVariableSchema",
    "InterventionalClosure",
    "LegalStatus",
    "MarkovSemantics",
    "ObservabilityStatus",
    "QueryPreservationCertificate",
    "SCMFragment",
    "SolverKind",
    "TransportStatus",
    "UniquenessScope",
    "build_evidence_need_id",
    "completeness_scope_for_composition",
    "load_composition_certificate",
    "load_cross_graph_evidence_profile",
    "load_interface_mapping",
    "load_scm_fragment",
    "persist_composition_certificate",
    "persist_cross_graph_evidence_profile",
    "persist_interface_mapping",
    "persist_scm_fragment",
]
