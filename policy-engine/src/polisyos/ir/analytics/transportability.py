"""Public analytics transportability module API."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence  # noqa: TC003
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation as _OwnedJSONRepresentation,
)
from polisyos.ir.analytics._owner_admission import declare_model_owner as _declare_model_owner
from polisyos.ir.analytics._owner_admission import owner_profile_for_spec as _owner_profile_for_spec
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.partial_identification import PartialIdentificationResult
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NativeValueEstimandBinding,
    OutputContractDeclaration,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    ValueUncertaintyProjectionKind,
    value_uncertainty_output_contract,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.artifacts._lineage import InputRefLike  # noqa: TC001
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _put_owned_json_artifact,
    _validate_return_selected_profile_flag,
)
from polisyos.ir.migrations.base import (
    CompatibilityMode as _CompatibilityMode,
)
from polisyos.ir.migrations.base import (
    IRRepresentationKey,
)
from polisyos.ir.migrations.base import (
    register_ir_representation as _register_ir_representation,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalGraphModelRef, TransportabilityResultRef

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.catalog import ProxyCandidate, PStarZResult
    from polisyos.ir.analytics.causal_graph import (
        CausalGraphModel,
        GraphType,
        PAGIdentificationPolicy,
    )
else:
    from polisyos.data_forge.read_api.catalog import ProxyCandidate, PStarZResult
    from polisyos.ir.analytics.causal_graph import (
        CausalGraphModel,
        GraphType,
        PAGIdentificationPolicy,
    )

CONTEXT_VARIABLE_SENSITIVITY: dict[str, list[str]] = {
    "institutional_quality": [
        "tax_compliance",
        "corruption_level",
        "policy_effectiveness",
        "contract_enforcement",
        "public_service_quality",
    ],
    "social_trust": [
        "collective_action_outcome",
        "cooperation_rate",
        "civic_participation",
        "social_capital",
        "compliance_voluntary",
    ],
    "income_level": [
        "consumption_response",
        "fiscal_multiplier",
        "human_capital_investment",
        "credit_access",
        "savings_rate",
    ],
    "economic_openness": [
        "trade_elasticity",
        "exchange_rate_pass_through",
        "capital_flow",
    ],
    "post_communist": [
        "institutional_quality",
        "state_capacity",
        "corruption_level",
        "market_competition",
        "property_rights",
    ],
    "post_conflict": [
        "state_capacity",
        "institutional_quality",
        "investment_rate",
        "human_capital",
        "migration_rate",
    ],
}

THRESHOLD_FOR_S_NODE = 0.2


class SNodeOrigin(str, Enum):
    """Classify why a selection node appears in a transportability diagram."""

    CONTEXT_DELTA = "context_delta"
    LEGAL = "legal"
    DATA_MISMATCH = "data_mismatch"
    PRIVACY = "privacy"


class SNodeRole(str, Enum):
    """Declare the causal role used when deciding whether an S-node is adjustable."""

    PRE_TREATMENT_COVARIATE = "pre_treatment_covariate"
    MEDIATOR = "mediator"
    COLLIDER = "collider"
    INSTRUMENT = "instrument"


class SNode(BaseModel):
    """S node implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    context_dimension: str
    source_value: float | str
    target_value: float | str
    delta: float
    severity: Literal["low", "medium", "high"]
    origin: SNodeOrigin = SNodeOrigin.CONTEXT_DELTA
    legal_constraint_id: str | None = None
    role: SNodeRole | None = None
    source_ref: str | None = Field(None, min_length=1)
    target_ref: str | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def _measured_refs_are_paired(self) -> SNode:
        if (self.source_ref is None) != (self.target_ref is None):
            raise ValueError("selection_node_measured_refs_incomplete")
        return self


class SelectionDiagram(BaseModel):
    """Selection diagram public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_graph: CausalGraphModel
    s_nodes: list[SNode] = Field(default_factory=list)
    source_context: ContextProfile
    target_context: ContextProfile
    context_distance: float = 0.0


# ---------------------------------------------------------------------------
# SigmaVariable — pure graph-theoretic σ-variable concept
# ---------------------------------------------------------------------------


class SigmaVariable(BaseModel):
    """Formal σ-variable (selection variable) for a mechanism shift between domains.

    Unlike :class:`SNode` which carries policy-domain context (ContextProfile,
    context dimensions, legal constraint IDs), ``SigmaVariable`` is a pure
    graph-theoretic concept: it names the variable whose generating mechanism
    differs between source and target domain, and tracks whether it has been
    resolved by adjustment.

    Use ``SigmaVariable.from_s_node()`` to convert an existing policy-specific
    ``SNode`` into this leaner graph-theoretic form.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable_name: str
    """The domain variable whose mechanism shifts (σ-variable in the formal sense)."""

    node_name: str
    """The S-node graph identifier, conventionally ``'S_' + variable_name``."""

    is_resolved: bool = False
    """True when the S-node has been eliminated by adjustment or transported."""

    resolving_adjustment_set: tuple[str, ...] = ()
    """Variables used to block this σ-variable's effect (empty when unresolved)."""

    origin: SNodeOrigin = SNodeOrigin.CONTEXT_DELTA

    @classmethod
    def from_s_node(cls, s_node: SNode) -> SigmaVariable:
        """Convert a policy-specific SNode to a graph-theoretic SigmaVariable."""
        return cls(
            variable_name=s_node.target_variable,
            node_name=f"S_{s_node.target_variable}",
            origin=s_node.origin,
        )


# ---------------------------------------------------------------------------
# SelectionDiagramBuilder — programmatic builder (no ContextProfile required)
# ---------------------------------------------------------------------------


class SelectionDiagramBuilder:
    """Fluent builder for :class:`SelectionDiagram` without requiring a ContextProfile.

    The existing :func:`build_selection_diagram` factory creates diagrams from
    context deltas.  This builder provides a programmatic API for constructing
    diagrams directly from variable names — useful for unit tests, algorithm
    development, and scenarios where the context difference is known structurally
    rather than via numeric ContextProfile attributes.

    Example::

        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X", severity="high")
            .add_sigma_variable("Z", role=SNodeRole.MEDIATOR)
            .build()
        )
    """

    def __init__(self, graph: CausalGraphModel) -> None:
        self._graph = graph
        self._s_nodes: list[SNode] = []
        self._sigma_vars: list[SigmaVariable] = []
        self._seen: set[str] = set()  # deduplicate by variable_name

    def add_sigma_variable(
        self,
        variable_name: str,
        *,
        context_dimension: str = "programmatic",
        severity: Literal["low", "medium", "high"] = "medium",
        role: SNodeRole | None = None,
    ) -> SelectionDiagramBuilder:
        """Add a σ-variable (selection/context-shift node) by variable name.

        Parameters
        ----------
        variable_name     : the domain variable whose mechanism shifts
        context_dimension : informal label for the dimension of shift (default "programmatic")
        severity          : "low" | "medium" | "high" (default "medium")
        role              : optional structural role (PRE_TREATMENT_COVARIATE, MEDIATOR, …)

        Returns self for chaining.
        """
        if variable_name in self._seen:
            return self
        self._seen.add(variable_name)
        sn = SNode(
            target_variable=variable_name,
            context_dimension=context_dimension,
            source_value=0.0,
            target_value=1.0,
            delta=1.0,
            severity=severity,
            role=role,
        )
        self._s_nodes.append(sn)
        self._sigma_vars.append(SigmaVariable.from_s_node(sn))
        return self

    def add_measured_sigma_variable(
        self,
        variable_name: str,
        *,
        source_value: float,
        target_value: float,
        severity: Literal["low", "medium", "high"],
        role: SNodeRole | None,
        source_ref: str,
        target_ref: str,
    ) -> SelectionDiagramBuilder:
        """Add a content-referenced mechanism shift measured in both contexts.

        The supplied row references are provenance only. They do not establish
        transportability or causal role; the transport solver remains the
        authority for those decisions.
        """

        if variable_name in self._seen:
            return self
        self._seen.add(variable_name)
        s_node = SNode(
            target_variable=variable_name,
            context_dimension=f"measured:{variable_name}",
            source_value=float(source_value),
            target_value=float(target_value),
            delta=abs(float(target_value) - float(source_value)),
            severity=severity,
            role=role,
            source_ref=source_ref,
            target_ref=target_ref,
        )
        self._s_nodes.append(s_node)
        self._sigma_vars.append(SigmaVariable.from_s_node(s_node))
        return self

    def build(
        self,
        source_context: ContextProfile | None = None,
        target_context: ContextProfile | None = None,
    ) -> SelectionDiagram:
        """Build and return an immutable :class:`SelectionDiagram`.

        Parameters
        ----------
        source_context : optional source ContextProfile; defaults to ``ContextProfile()``
        target_context : optional target ContextProfile; defaults to ``ContextProfile()``
        """
        sc = source_context if source_context is not None else ContextProfile()
        tc = target_context if target_context is not None else ContextProfile()
        return SelectionDiagram(
            base_graph=self._graph,
            s_nodes=list(self._s_nodes),
            source_context=sc,
            target_context=tc,
            context_distance=sc.distance_to(tc),
        )

    @property
    def sigma_variables(self) -> list[SigmaVariable]:
        """List of SigmaVariable objects added so far."""
        return list(self._sigma_vars)


# ---------------------------------------------------------------------------
# MultiSourceSelectionDiagram — multi-source mz-ID support
# ---------------------------------------------------------------------------


class SourceDomainSpec(BaseModel):
    """Specification for a single source domain in a multi-domain transport scenario.

    Provides a Pydantic IR representation of a source domain, analogous to the
    internal ``SourceDomain`` frozen dataclass in ``id_engine.py`` but living in
    the IR layer so it can be serialised, validated, and composed without
    importing algorithmic code.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain_id: str
    """Unique identifier for this source domain (e.g. ``"study_us_2010"``)."""

    s_nodes: tuple[SNode, ...] = ()
    """S-nodes (mechanism shifts) that affect this domain relative to the target."""

    z_interventions: tuple[str, ...] = ()
    """Variables for which experimental (Z-interventional) distributions are available."""

    dataset_ref: str | None = None
    """Reference key for the dataset from this domain."""

    source_context: ContextProfile | None = None
    """Optional context profile for this domain."""

    def to_selection_diagram(self, base_graph: CausalGraphModel) -> SelectionDiagram:
        """Project this domain spec to a standalone :class:`SelectionDiagram`."""
        sc = self.source_context if self.source_context is not None else ContextProfile()
        return SelectionDiagram(
            base_graph=base_graph,
            s_nodes=list(self.s_nodes),
            source_context=sc,
            target_context=ContextProfile(),
            context_distance=sc.distance_to(ContextProfile()),
        )


class MultiSourceSelectionDiagram(BaseModel):
    """Selection diagram for multi-source (mz-ID) transportability.

    Represents the scenario where a single target graph receives evidence from
    multiple source studies, each potentially having different mechanism shifts
    (S-nodes) and/or experimental distributions (Z-interventions).

    Foundry's ``mz_id_algorithm()`` accepts typed ``SourceDomainSpec`` values and
    owns conversion to its private algorithm descriptor.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_graph: CausalGraphModel
    """The shared target-domain causal graph."""

    domains: tuple[SourceDomainSpec, ...] = ()
    """Source domains contributing evidence."""

    target_context: ContextProfile
    """Context profile for the target domain."""

    def to_selection_diagram(self, domain_id: str) -> SelectionDiagram:
        """Project a single domain to a standalone :class:`SelectionDiagram`.

        Parameters
        ----------
        domain_id : the ``domain_id`` of the domain to project

        Raises
        ------
        KeyError
            If no domain with the given ``domain_id`` exists.
        """
        for spec in self.domains:
            if spec.domain_id == domain_id:
                return spec.to_selection_diagram(self.base_graph)
        raise KeyError(f"No domain with domain_id={domain_id!r} in MultiSourceSelectionDiagram")


class StratificationVariable(BaseModel):
    """Stratification variable public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: SNodeRole
    requires_conditional: bool
    condition_on_treatment: str | None = None


class TransportFormula(BaseModel):
    """Transport formula public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    formula_str: str
    stratification_variables: list[str] = Field(default_factory=list)
    stratification_details: list[StratificationVariable] = Field(default_factory=list)
    source_quantities: list[str] = Field(default_factory=list)
    target_quantities: list[str] = Field(default_factory=list)
    adjustment_type: str = "direct"

    def requires_target_data(self) -> bool:
        return bool(self.target_quantities)


class TransportabilityStatus(str, Enum):
    """Report whether transportability is identified, bounded, or blocked.

    Readiness gates and reporting code inspect this status to decide whether a
    transported estimate can proceed directly, requires partial-identification
    fallback, or must be treated as unsupported.
    """

    IDENTIFIED = "identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    BOUNDED_NON_IDENTIFIED = "bounded_non_identified"
    UNSUPPORTED = "unsupported"


class TransportMode(str, Enum):
    """Describe the execution path implied by a ``TransportabilityResult``."""

    DIRECT = "direct"
    TRANSPORT_FORMULA = "transport_formula"
    BOUNDS_ONLY = "bounds_only"
    NONE = "none"


class DataGap(BaseModel):
    """Data gap public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_variable: str
    required_context: str
    available_proxies: list[ProxyCandidate] = Field(default_factory=list)
    best_proxy_confidence: float = 0.0
    gap_impact: str
    suggested_action: str


class TransportabilityCandidateReasonV1(BaseModel):
    """Explain one candidate execution or member outcome without assigning authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,95}$")
    detail: str | None = Field(default=None, max_length=2000)


class TransportabilityCandidateRequestV1(BaseModel):
    """Strict caller intent for one registered conditional transport profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(min_length=1, max_length=160)
    profile_revision: str = Field(min_length=1, max_length=80)
    selection_identity: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _reject_blank_identity(self) -> TransportabilityCandidateRequestV1:
        if any(
            not value.strip()
            for value in (
                self.profile_id,
                self.profile_revision,
                self.selection_identity,
            )
        ):
            raise ValueError("candidate_request_identity_must_not_be_blank")
        return self


class TransportabilityCandidateProfileV1(BaseModel):
    """Identify the owner-resolved effective profile without a central profile allowlist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1, max_length=160)
    profile_revision: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _reject_blank_identity(self) -> TransportabilityCandidateProfileV1:
        if not self.profile_id.strip() or not self.profile_revision.strip():
            raise ValueError("candidate_profile_identity_must_not_be_blank")
        return self


class TransportabilityCandidateResourceResolutionV1(BaseModel):
    """Typed snapshot returned by the existing owner resource resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1"] = "1.1"
    policy_id: str = Field(min_length=1, max_length=160)
    policy_revision: str = Field(min_length=1, max_length=120)
    profile_id: str = Field(min_length=1, max_length=160)
    profile_revision: str = Field(min_length=1, max_length=80)
    selection_identity: str = Field(min_length=1, max_length=240)
    status: Literal["selected", "refused"]
    reason_code: str | None = Field(default=None, min_length=1, max_length=160)
    effective_limits: dict[str, StrictInt | StrictFloat] | None
    effective_limit_units: dict[str, str] | None
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _validate_owner_snapshot(self) -> TransportabilityCandidateResourceResolutionV1:
        for value in (
            self.policy_id,
            self.policy_revision,
            self.profile_id,
            self.profile_revision,
            self.selection_identity,
        ):
            if not value.strip():
                raise ValueError("candidate_resource_identity_must_not_be_blank")
        if self.status == "selected":
            if (
                self.reason_code is not None
                or not self.effective_limits
                or not self.effective_limit_units
                or set(self.effective_limits) != set(self.effective_limit_units)
            ):
                raise ValueError("selected_candidate_resource_requires_exact_limits_and_units")
        elif (
            self.reason_code is None
            or self.effective_limits is not None
            or self.effective_limit_units is not None
        ):
            raise ValueError("refused_candidate_resource_must_retain_reason_without_limits")
        if self.effective_limits is not None:
            if any(not key.strip() for key in self.effective_limits):
                raise ValueError("candidate_resource_limit_name_must_not_be_blank")
            if any(
                isinstance(value, bool) or not math.isfinite(float(value)) or value < 0
                for value in self.effective_limits.values()
            ):
                raise ValueError("candidate_resource_limit_must_be_finite_and_nonnegative")
        if self.effective_limit_units is not None and any(
            not key.strip() or not unit.strip() for key, unit in self.effective_limit_units.items()
        ):
            raise ValueError("candidate_resource_limit_unit_must_not_be_blank")
        payload = self.model_dump(mode="json", exclude={"sha256"})
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != self.sha256:
            raise ValueError("candidate_resource_snapshot_digest_mismatch")
        return self


class TransportabilityCandidateAttemptBindingV1(BaseModel):
    """Bind candidate computation to the engine-owned workflow attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=160)
    attempt_id: str = Field(min_length=1, max_length=160)
    attempt_number: int = Field(ge=1)
    node_alias: Literal["run_transportability"]
    component_id: str = Field(min_length=1, max_length=240)
    started_at: datetime
    dispatch_params_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    workflow_spec_ref: InputRef
    input_state_ref: InputRef
    basis_ref: InputRef

    @model_validator(mode="after")
    def _validate_attempt_binding(self) -> TransportabilityCandidateAttemptBindingV1:
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("candidate_attempt_started_at_must_be_timezone_aware")
        expected = (
            (self.basis_ref, "transportability_attempt_basis"),
            (self.workflow_spec_ref, "transportability_workflow_spec"),
            (self.input_state_ref, "transportability_input_state"),
        )
        for ref, role in expected:
            if ref.role != role or ref.manifest_profile_sha256 is None:
                raise ValueError("candidate_attempt_ref_role_or_selected_profile_invalid")
        return self


class TransportabilityCandidateModelPlanRelationV1(BaseModel):
    """Content-bound named model/plan relation used instead of a selection diagram."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str = Field(min_length=1, max_length=240)
    revision: str = Field(min_length=1, max_length=80)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class TransportabilityCandidateInputBindingV1(BaseModel):
    """Bind the computation to exact graph, query, contexts, and persisted inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_ref: CausalGraphModelRef
    graph_type: GraphType
    graph_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selection_diagram_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    model_plan_relation: TransportabilityCandidateModelPlanRelationV1 | None = None
    query_treatment: str = Field(min_length=1, max_length=240)
    query_outcome: str = Field(min_length=1, max_length=240)
    query_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_context_id: str = Field(min_length=1, max_length=240)
    source_context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_context_id: str = Field(min_length=1, max_length=240)
    target_context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    lineage_refs: tuple[InputRef, ...]

    @model_validator(mode="after")
    def _validate_input_binding(self) -> TransportabilityCandidateInputBindingV1:
        if (self.selection_diagram_sha256 is None) == (self.model_plan_relation is None):
            raise ValueError("candidate_input_requires_exactly_one_diagram_or_model_plan_relation")
        if self.graph_ref.manifest_profile_sha256 is None:
            raise ValueError("candidate_graph_ref_requires_selected_manifest_profile")
        if self.query_sha256 != transportability_candidate_query_sha256(
            self.query_treatment, self.query_outcome
        ):
            raise ValueError("candidate_query_digest_mismatch")
        expected_roles = (
            "transportability_attempt_basis",
            "transportability_workflow_spec",
            "transportability_input_state",
            "selected_causal_graph",
            "causal_effect_report",
        )
        if tuple(ref.role for ref in self.lineage_refs) != expected_roles:
            raise ValueError("candidate_lineage_roles_missing_reordered_or_unexpected")
        if any(ref.manifest_profile_sha256 is None for ref in self.lineage_refs):
            raise ValueError("candidate_lineage_ref_requires_selected_manifest_profile")
        if self.lineage_refs[3].artifact_id != self.graph_ref.artifact_id:
            raise ValueError("candidate_graph_lineage_mismatch")
        return self


class TransportabilityCandidateBudgetMeasureV1(BaseModel):
    """Record one effective resource limit or observed consumption measurement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource: str = Field(min_length=1, max_length=120)
    value: StrictInt | StrictFloat = Field(ge=0.0)
    unit: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _finite_value(self) -> TransportabilityCandidateBudgetMeasureV1:
        if not self.resource.strip() or not self.unit.strip():
            raise ValueError("candidate_budget_resource_and_unit_must_not_be_blank")
        if not math.isfinite(self.value):
            raise ValueError("candidate_budget_measure_must_be_finite")
        return self


class TransportabilityCandidatePhaseBudgetV1(BaseModel):
    """Record owner admission, resolved limits, use, and termination for one phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: Literal["generation", "evaluation"]
    selection_identity: str = Field(min_length=1, max_length=240)
    admission: Literal["admitted", "refused", "not_established", "not_required"]
    admission_source: Literal[
        "existing_compute_permit",
        "bounded_execution_policy",
        "owner_refusal",
        "not_established",
        "not_required",
    ]
    admission_ref: InputRef | None = None
    admission_policy_id: str | None = Field(default=None, min_length=1, max_length=160)
    effective_limits: tuple[TransportabilityCandidateBudgetMeasureV1, ...] = ()
    consumed: tuple[TransportabilityCandidateBudgetMeasureV1, ...] = ()
    termination: Literal[
        "not_started",
        "completed",
        "budget_exhausted",
        "cancelled",
        "error",
        "unsupported",
        "not_required",
    ]
    reason: TransportabilityCandidateReasonV1 | None = None
    elapsed_seconds: StrictInt | StrictFloat | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _validate_phase_budget(self) -> TransportabilityCandidatePhaseBudgetV1:
        if self.elapsed_seconds is not None and not math.isfinite(self.elapsed_seconds):
            raise ValueError("candidate_budget_elapsed_must_be_finite")
        limit_resources = [item.resource for item in self.effective_limits]
        if len(limit_resources) != len(set(limit_resources)):
            raise ValueError("candidate_budget_effective_resources_must_be_unique")
        consumed_resources = [item.resource for item in self.consumed]
        if len(consumed_resources) != len(set(consumed_resources)):
            raise ValueError("candidate_budget_consumed_resources_must_be_unique")
        limits_by_resource = {item.resource: item for item in self.effective_limits}
        if not set(consumed_resources).issubset(limits_by_resource):
            raise ValueError("candidate_budget_consumption_missing_resolved_limit")
        if any(item.unit != limits_by_resource[item.resource].unit for item in self.consumed):
            raise ValueError("candidate_budget_consumption_unit_must_match_resolved_limit")
        exceeded = any(
            item.value > limits_by_resource[item.resource].value for item in self.consumed
        )
        if exceeded and (
            self.termination not in {"budget_exhausted", "error"} or self.reason is None
        ):
            raise ValueError("candidate_budget_overrun_requires_truthful_non_success_termination")
        if self.elapsed_seconds is not None:
            elapsed_limits = [
                limit.value
                for limit in self.effective_limits
                if limit.resource == "max_elapsed_seconds" and limit.unit == "seconds"
            ]
            if (
                elapsed_limits
                and self.elapsed_seconds > min(elapsed_limits)
                and (self.termination not in {"budget_exhausted", "error"} or self.reason is None)
            ):
                raise ValueError(
                    "candidate_elapsed_overrun_requires_truthful_non_success_termination"
                )
        if self.admission == "admitted":
            if self.admission_source not in {
                "existing_compute_permit",
                "bounded_execution_policy",
            }:
                raise ValueError("candidate_budget_admission_source_not_authoritative")
            if not self.effective_limits or self.termination in {
                "not_started",
                "not_required",
            }:
                raise ValueError("candidate_budget_admitted_without_effective_execution_bound")
            if self.admission_source == "existing_compute_permit" and self.admission_ref is None:
                raise ValueError("candidate_permit_admission_requires_selected_permit_ref")
            if (
                self.admission_source == "bounded_execution_policy"
                and self.admission_policy_id is None
            ):
                raise ValueError("candidate_policy_admission_requires_policy_identity")
            if self.termination == "completed" and self.reason is not None:
                raise ValueError("completed_candidate_budget_must_not_carry_refusal_reason")
            if self.termination != "completed" and self.reason is None:
                raise ValueError("noncompleted_candidate_budget_requires_termination_reason")
        elif self.admission == "not_required":
            if (
                self.admission_source != "not_required"
                or self.termination != "not_required"
                or self.effective_limits
                or self.consumed
                or self.reason is not None
            ):
                raise ValueError("candidate_budget_not_required_shape_invalid")
        else:
            if self.admission_source not in {"owner_refusal", "not_established"}:
                raise ValueError("candidate_budget_nonadmission_source_invalid")
            if self.termination != "not_started" or not self.reason:
                raise ValueError("candidate_budget_nonadmission_must_explain_not_started")
            if self.consumed:
                raise ValueError("candidate_budget_nonadmission_cannot_report_consumption")
            if self.effective_limits:
                raise ValueError("candidate_budget_nonadmission_cannot_claim_effective_limits")
        return self


class TransportabilityCandidateProposalV1(BaseModel):
    """Final disposition of one generated finite-family proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=0)
    assignment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    disposition: Literal[
        "admitted",
        "duplicate",
        "invalid",
        "unsupported",
        "validation_incomplete",
    ]
    member_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    duplicate_of: int | None = Field(default=None, ge=0)
    reason: TransportabilityCandidateReasonV1 | None = None

    @model_validator(mode="after")
    def _validate_proposal(self) -> TransportabilityCandidateProposalV1:
        if self.disposition == "admitted":
            if (
                self.member_sha256 is None
                or self.duplicate_of is not None
                or self.reason is not None
            ):
                raise ValueError("admitted_proposal_requires_only_member_identity")
        elif self.disposition == "duplicate":
            if (
                self.member_sha256 is not None
                or self.duplicate_of is None
                or self.reason is not None
            ):
                raise ValueError("duplicate_proposal_requires_only_duplicate_target")
        elif self.member_sha256 is not None or self.duplicate_of is not None or self.reason is None:
            raise ValueError("rejected_proposal_requires_reason_and_no_member_identity")
        return self


class TransportabilityCandidateSolverOutcomeV1(BaseModel):
    """Retain the complete typed result returned by the existing solver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result: TransportabilityResult
    result_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    query_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    algorithm_version: str = Field(min_length=1, max_length=160)
    identification_engine: str = Field(min_length=1, max_length=160)
    status: TransportabilityStatus
    transport_mode: TransportMode
    feasible: bool
    transport_formula: TransportFormula | None = None
    identified_region: dict[str, Any] | None = None
    partial_identification_result: PartialIdentificationResult | None = None
    identification_trace: tuple[str, ...] = ()
    unsupported_reason: str | None = None

    @model_validator(mode="after")
    def _validate_solver_outcome(self) -> TransportabilityCandidateSolverOutcomeV1:
        if self.result.candidate_diagnostics is not None:
            raise ValueError("candidate_member_solver_result_must_not_nest_candidate_diagnostic")
        query_digest = hashlib.sha256(self.result.query.encode("utf-8")).hexdigest()
        if not self.result.query or query_digest != self.query_sha256:
            raise ValueError("candidate_solver_result_query_binding_mismatch")
        encoded = json.dumps(
            self.result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != self.result_sha256:
            raise ValueError("candidate_solver_full_result_digest_mismatch")
        if (
            self.algorithm_version != self.result.algorithm_version
            or self.identification_engine != self.result.identification_engine
            or self.status is not self.result.status
            or self.transport_mode is not self.result.transport_mode
            or self.feasible is not self.result.feasible
            or self.transport_formula != self.result.transport_formula
            or self.identified_region != self.result.identified_region
            or self.partial_identification_result != self.result.partial_identification_result
            or self.identification_trace != tuple(self.result.identification_trace)
            or self.unsupported_reason != self.result.unsupported_reason
        ):
            raise ValueError("candidate_solver_projection_must_match_full_result")
        if self.status is TransportabilityStatus.IDENTIFIED:
            if self.transport_mode is TransportMode.NONE:
                raise ValueError("identified_candidate_member_cannot_have_none_mode")
            if (
                self.transport_mode is TransportMode.TRANSPORT_FORMULA
                and self.transport_formula is None
            ):
                raise ValueError("candidate_formula_mode_requires_actual_formula")
        elif self.status is TransportabilityStatus.PARTIALLY_IDENTIFIED:
            if self.transport_mode is TransportMode.NONE:
                raise ValueError("partial_candidate_member_cannot_have_none_mode")
            if (
                self.transport_formula is None
                and self.identified_region is None
                and self.partial_identification_result is None
            ):
                raise ValueError("partial_candidate_member_requires_actual_result_basis")
        elif self.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED:
            if (
                self.transport_mode is not TransportMode.BOUNDS_ONLY
                or self.partial_identification_result is None
                or self.transport_formula is not None
            ):
                raise ValueError("bounded_candidate_member_requires_typed_bounds_only")
        else:
            if (
                self.transport_mode is not TransportMode.NONE
                or self.transport_formula is not None
                or self.identified_region is not None
                or self.partial_identification_result is not None
                or not self.unsupported_reason
            ):
                raise ValueError("unsupported_candidate_member_must_retain_exact_refusal")
        return self

    @classmethod
    def from_result(
        cls,
        result: TransportabilityResult,
        *,
        query_sha256: str,
    ) -> TransportabilityCandidateSolverOutcomeV1:
        """Bind a nested member result to the exact serialized existing solver output."""
        if result.candidate_diagnostics is not None:
            raise ValueError("candidate_member_solver_result_must_not_nest_candidate_diagnostic")
        expected_query_digest = hashlib.sha256(result.query.encode("utf-8")).hexdigest()
        if not result.query or query_sha256 != expected_query_digest:
            raise ValueError("candidate_solver_result_query_binding_mismatch")
        encoded = json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return cls(
            result=result,
            result_sha256=hashlib.sha256(encoded).hexdigest(),
            query_sha256=query_sha256,
            algorithm_version=result.algorithm_version,
            identification_engine=result.identification_engine,
            status=result.status,
            transport_mode=result.transport_mode,
            feasible=result.feasible,
            transport_formula=result.transport_formula,
            identified_region=result.identified_region,
            partial_identification_result=result.partial_identification_result,
            identification_trace=tuple(result.identification_trace),
            unsupported_reason=result.unsupported_reason,
        )


class TransportabilityCandidateMemberEvaluationV1(BaseModel):
    """One and only one evaluation disposition for an admitted member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    member_graph_ref: CausalGraphModelRef
    disposition: Literal["not_started", "interrupted", "completed", "error"]
    outcome: TransportabilityCandidateSolverOutcomeV1 | None = None
    reason: TransportabilityCandidateReasonV1 | None = None

    @model_validator(mode="after")
    def _validate_evaluation(self) -> TransportabilityCandidateMemberEvaluationV1:
        if self.member_graph_ref.manifest_profile_sha256 is None:
            raise ValueError("candidate_member_graph_ref_requires_selected_manifest_profile")
        if self.disposition == "completed":
            if self.outcome is None or self.reason is not None:
                raise ValueError("completed_candidate_evaluation_requires_only_solver_outcome")
        elif self.outcome is not None or self.reason is None:
            raise ValueError("incomplete_candidate_evaluation_requires_reason_without_outcome")
        return self


def _decimal_add_small(decimal_text: str, value: int) -> str:
    """Add a bounded nonnegative count to an arbitrary-size decimal string."""
    if value < 0:
        raise ValueError("candidate_count_addend_must_be_nonnegative")
    digits = list(decimal_text)
    index = len(digits) - 1
    carry = value
    while index >= 0 and carry:
        total = int(digits[index]) + carry
        digits[index] = str(total % 10)
        carry = total // 10
        index -= 1
    if carry:
        digits.insert(0, str(carry))
    return "".join(digits)


class TransportabilityCandidateDiagnosticV1(BaseModel):
    """Persist a source-bound candidate diagnostic that cannot promote authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    candidate_request: TransportabilityCandidateRequestV1
    resource_resolution: TransportabilityCandidateResourceResolutionV1
    effective_profile: TransportabilityCandidateProfileV1 | None
    disposition: Literal["not_run", "completed", "partial", "unsupported", "error"]
    reason: TransportabilityCandidateReasonV1 | None = None
    attempt: TransportabilityCandidateAttemptBindingV1
    inputs: TransportabilityCandidateInputBindingV1
    graph_provenance: Literal["manual", "fitted", "generated", "unknown"]
    algorithm_id: str = Field(min_length=1, max_length=160)
    algorithm_revision: str = Field(min_length=1, max_length=120)
    implementation_revision: str = Field(min_length=1, max_length=160)
    backend_id: str = Field(min_length=1, max_length=160)
    backend_revision: str = Field(min_length=1, max_length=120)
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    assumptions: tuple[str, ...] = ()
    unresolved_predicates: tuple[str, ...] = ()
    generation_budget: TransportabilityCandidatePhaseBudgetV1
    evaluation_budget: TransportabilityCandidatePhaseBudgetV1
    proposals: tuple[TransportabilityCandidateProposalV1, ...] = ()
    evaluations: tuple[TransportabilityCandidateMemberEvaluationV1, ...] = ()
    identified_member_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    assignment_space_size: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]*)$")
    unattempted_proposals: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]*)$")
    generation_coverage: Literal[
        "declared_attempt_budget",
        "finite_endpoint_assignment_space_complete",
        "not_established",
    ]
    evaluated_at: datetime
    source_currentness: Literal["unknown"] = "unknown"
    candidate_scope: Literal["candidate_only"] = "candidate_only"
    interpretation_limit: Literal[
        "selected_family_member_outcomes_do_not_establish_whole_pag_class_probability_calibration_legal_applicability_or_protected_eligibility"
    ] = (
        "selected_family_member_outcomes_do_not_establish_who"
        "le_pag_class_probability_calibration_legal_applicabi"
        "lity_or_protected_eligibility"
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_identified_fraction(cls, payload: object) -> object:
        if not isinstance(payload, dict):
            return payload
        payload = dict(payload)
        evaluations = payload.get("evaluations", ())
        completed_statuses: list[object] = []
        for row in evaluations:
            if isinstance(row, dict):
                disposition = row.get("disposition")
                outcome = row.get("outcome")
                status = outcome.get("status") if isinstance(outcome, dict) else None
            else:
                disposition = getattr(row, "disposition", None)
                outcome = getattr(row, "outcome", None)
                status = getattr(outcome, "status", None)
            if disposition == "completed" and status is not None:
                completed_statuses.append(status)
        fraction = None
        if completed_statuses:
            identified_statuses = {
                TransportabilityStatus.IDENTIFIED,
                TransportabilityStatus.IDENTIFIED.value,
            }
            identified_count = sum(
                1 for status in completed_statuses if status in identified_statuses
            )
            fraction = identified_count / len(completed_statuses)
        declared = payload.get("identified_member_fraction", fraction)
        if declared != fraction:
            raise ValueError("candidate_identified_fraction_must_be_derived_from_member_rows")
        payload["identified_member_fraction"] = fraction
        return payload

    def _derive_execution_disposition(
        self,
    ) -> Literal["not_run", "completed", "partial", "unsupported", "error"]:
        """Reconcile execution status from admitted phases and retained source rows.

        A reason explains a disposition but cannot select it. Completion requires
        every required phase to succeed, exact assignment/member partitions, and
        at least one complete solver result. PAG coverage is scoped to the
        owner-selected finite family or declared attempt budget; it never implies
        whole-class probability, calibration, or population coverage.
        """
        phases = (self.generation_budget, self.evaluation_budget)
        phase_success = all(
            (phase.admission == "not_required" and phase.termination == "not_required")
            or (phase.admission == "admitted" and phase.termination == "completed")
            for phase in phases
        )
        has_attempt_evidence = bool(self.proposals or self.evaluations)
        pag = self.inputs.graph_type is GraphType.PAG
        if pag:
            assignment_partition_complete = (
                self.assignment_space_size is not None
                and self.unattempted_proposals is not None
                and self.assignment_space_size
                == _decimal_add_small(self.unattempted_proposals, len(self.proposals))
                and self.generation_budget.admission == "admitted"
                and self.generation_budget.termination == "completed"
                and self.generation_coverage
                in {"declared_attempt_budget", "finite_endpoint_assignment_space_complete"}
                and not any(
                    proposal.disposition == "validation_incomplete" for proposal in self.proposals
                )
            )
            admitted_members = {
                proposal.member_sha256
                for proposal in self.proposals
                if proposal.disposition == "admitted"
            }
            evaluated_members = {row.member_sha256 for row in self.evaluations}
            member_partition_complete = evaluated_members == admitted_members
        else:
            assignment_partition_complete = (
                self.assignment_space_size is None
                and self.unattempted_proposals is None
                and not self.proposals
            )
            member_partition_complete = (
                len(self.evaluations) == 1
                and self.evaluations[0].member_sha256 == self.inputs.graph_sha256
                and self.evaluations[0].member_graph_ref == self.inputs.graph_ref
            )
        solver_outputs_complete = bool(self.evaluations) and all(
            row.disposition == "completed" and row.outcome is not None for row in self.evaluations
        )
        if (
            phase_success
            and assignment_partition_complete
            and member_partition_complete
            and solver_outputs_complete
        ):
            return "completed"
        if has_attempt_evidence:
            return "partial"
        if self.resource_resolution.status == "refused" or any(
            phase.admission == "refused" or phase.termination == "unsupported" for phase in phases
        ):
            return "unsupported"
        if any(
            phase.admission == "admitted"
            and phase.termination in {"budget_exhausted", "cancelled", "error"}
            for phase in phases
        ):
            return "error"
        if all(
            phase.admission not in {"admitted", "refused"}
            and phase.termination in {"not_started", "not_required"}
            for phase in phases
        ):
            return "not_run"
        raise ValueError("candidate_execution_state_has_no_reconciled_disposition")

    @model_validator(mode="after")
    def _validate_diagnostic(self) -> TransportabilityCandidateDiagnosticV1:
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("candidate_evaluated_at_must_be_timezone_aware")
        if self.generation_budget.phase != "generation":
            raise ValueError("candidate_generation_budget_phase_mismatch")
        if self.evaluation_budget.phase != "evaluation":
            raise ValueError("candidate_evaluation_budget_phase_mismatch")
        resolution = self.resource_resolution
        if self.effective_profile is None:
            if resolution.status != "refused":
                raise ValueError("unresolved_candidate_profile_requires_owner_refusal")
            if (
                self.generation_budget.admission == "admitted"
                or self.evaluation_budget.admission == "admitted"
                or self.proposals
                or self.evaluations
            ):
                raise ValueError("unresolved_candidate_profile_cannot_claim_admitted_execution")
        if (
            self.candidate_request.profile_id != resolution.profile_id
            or self.candidate_request.profile_revision != resolution.profile_revision
            or self.candidate_request.selection_identity != resolution.selection_identity
        ):
            raise ValueError("candidate_request_must_match_owner_resource_resolution")
        if resolution.status == "selected":
            expected_profile = TransportabilityCandidateProfileV1(
                profile_id=resolution.profile_id,
                profile_revision=resolution.profile_revision,
            )
            if self.effective_profile != expected_profile:
                raise ValueError("selected_candidate_profile_must_match_owner_resolution")
        elif self.effective_profile is not None:
            raise ValueError("refused_candidate_resource_cannot_claim_effective_profile")
        for phase_budget in (self.generation_budget, self.evaluation_budget):
            if phase_budget.selection_identity != resolution.selection_identity:
                raise ValueError("candidate_budget_selection_identity_mismatch")
            if phase_budget.admission == "admitted":
                if resolution.status != "selected" or resolution.effective_limits is None:
                    raise ValueError("candidate_budget_admission_lacks_selected_owner_resource")
                if (
                    phase_budget.admission_source == "bounded_execution_policy"
                    and phase_budget.admission_policy_id
                    != f"{resolution.policy_id}@{resolution.policy_revision}"
                ):
                    raise ValueError("candidate_budget_policy_must_match_owner_resource")
                if resolution.effective_limit_units is None:
                    raise ValueError("candidate_budget_owner_units_not_established")
                for limit in phase_budget.effective_limits:
                    resolved = resolution.effective_limits.get(limit.resource)
                    resolved_unit = resolution.effective_limit_units.get(limit.resource)
                    if (
                        resolved is None
                        or float(resolved) != limit.value
                        or resolved_unit != limit.unit
                    ):
                        raise ValueError(
                            "candidate_phase_limit_must_match_owner_resource_value_and_unit"
                        )
        selection_identity = self.candidate_request.selection_identity
        if (
            self.generation_budget.selection_identity != selection_identity
            or self.evaluation_budget.selection_identity != selection_identity
        ):
            raise ValueError("candidate_budget_selection_identity_mismatch")
        if self.inputs.query_sha256 != transportability_candidate_query_sha256(
            self.inputs.query_treatment, self.inputs.query_outcome
        ):
            raise ValueError("candidate_query_binding_mismatch")
        expected_attempt_refs = (
            self.attempt.basis_ref,
            self.attempt.workflow_spec_ref,
            self.attempt.input_state_ref,
        )
        for lineage_ref, attempt_ref in zip(
            self.inputs.lineage_refs[:3], expected_attempt_refs, strict=True
        ):
            if (
                lineage_ref.artifact_id != attempt_ref.artifact_id
                or lineage_ref.manifest_profile_sha256 != attempt_ref.manifest_profile_sha256
            ):
                raise ValueError("candidate_attempt_lineage_ref_mismatch")
        if any(not value.strip() for value in (*self.assumptions, *self.unresolved_predicates)):
            raise ValueError("candidate_assumptions_and_predicates_must_be_nonblank")
        ordinals = [proposal.ordinal for proposal in self.proposals]
        if ordinals != list(range(len(ordinals))):
            raise ValueError("candidate_proposal_ordinals_must_be_contiguous")
        admitted_by_member: dict[str, TransportabilityCandidateProposalV1] = {}
        for proposal in self.proposals:
            if proposal.disposition == "admitted":
                member_sha256 = proposal.member_sha256
                if member_sha256 is None:
                    raise ValueError("candidate_admitted_proposal_requires_member_sha256")
                if member_sha256 in admitted_by_member:
                    raise ValueError("candidate_admitted_member_must_be_unique")
                admitted_by_member[member_sha256] = proposal
            elif proposal.disposition == "duplicate":
                duplicate_of = proposal.duplicate_of
                if duplicate_of is None:
                    raise ValueError("candidate_duplicate_requires_target_ordinal")
                if duplicate_of >= proposal.ordinal:
                    raise ValueError("candidate_duplicate_must_target_prior_proposal")
                target = self.proposals[duplicate_of]
                if (
                    target.disposition != "admitted"
                    or target.assignment_sha256 != proposal.assignment_sha256
                ):
                    raise ValueError("candidate_duplicate_target_not_matching_admitted_proposal")
        if self.inputs.graph_type is GraphType.PAG:
            if self.assignment_space_size is None or self.unattempted_proposals is None:
                raise ValueError("pag_candidate_requires_exact_assignment_accounting")
            attempted_count = len(self.proposals)
            reconciled_count = _decimal_add_small(
                self.unattempted_proposals,
                attempted_count,
            )
            if self.assignment_space_size != reconciled_count:
                raise ValueError("pag_candidate_assignment_count_does_not_reconcile")
            proposal_limit = next(
                (
                    measure.value
                    for measure in self.generation_budget.consumed
                    if measure.resource == "max_proposals" and measure.unit == "count"
                ),
                None,
            )
            if proposal_limit is not None and proposal_limit != attempted_count:
                raise ValueError("pag_candidate_proposal_rows_must_match_actual_attempt_count")
            if self.generation_budget.admission == "not_required":
                raise ValueError("pag_candidate_requires_generation_budget_admission")
            if (
                self.generation_budget.termination != "completed"
                and self.generation_coverage != "not_established"
            ):
                raise ValueError("early_stopped_pag_generation_has_unknown_family_coverage")
            exhausted_pag_family = (
                self.generation_budget.termination == "completed"
                and self.generation_coverage
                in {"not_established", "finite_endpoint_assignment_space_complete"}
            )
            if exhausted_pag_family:
                if self.unattempted_proposals != "0" or self.assignment_space_size != str(
                    attempted_count
                ):
                    raise ValueError("completed_pag_exhaustion_requires_exact_partition")
                if any(
                    proposal.disposition == "validation_incomplete" for proposal in self.proposals
                ):
                    raise ValueError(
                        "completed_pag_exhaustion_cannot_include_validation_incomplete"
                    )
            if (
                self.generation_budget.termination == "completed"
                and self.generation_coverage == "not_established"
            ):
                zero_member_full_search = (
                    attempted_count > 0
                    and not any(proposal.disposition == "admitted" for proposal in self.proposals)
                    and not self.evaluations
                    and self.identified_member_fraction is None
                    and self.reason is not None
                    and self.reason.code == "zero_admitted_members_not_established"
                )
                if not zero_member_full_search:
                    raise ValueError(
                        "completed_unknown_pag_coverage_requires_zero_admitted_full_search"
                    )
            if self.generation_coverage == "finite_endpoint_assignment_space_complete":
                if self.generation_budget.termination != "completed":
                    raise ValueError("complete_pag_coverage_requires_producer_proven_exhaustion")
                if not admitted_by_member:
                    raise ValueError("complete_pag_coverage_requires_positive_admission")
        else:
            if self.assignment_space_size is not None or self.unattempted_proposals is not None:
                raise ValueError("resolved_graph_candidate_cannot_claim_pag_assignment_accounting")
            if self.proposals:
                raise ValueError("resolved_graph_candidate_cannot_claim_generated_family_proposals")
            if (
                self.generation_budget.admission != "not_required"
                or self.generation_coverage != "not_established"
            ):
                raise ValueError("resolved_graph_candidate_cannot_claim_family_generation")
        admitted_members = set(admitted_by_member)
        evaluation_members = [row.member_sha256 for row in self.evaluations]
        if len(evaluation_members) != len(set(evaluation_members)):
            raise ValueError("candidate_member_evaluation_must_be_unique")
        if self.inputs.graph_type is GraphType.PAG:
            if set(evaluation_members) != admitted_members:
                raise ValueError("candidate_evaluations_must_partition_admitted_members")
        elif self.evaluations:
            if evaluation_members != [self.inputs.graph_sha256]:
                raise ValueError("resolved_graph_evaluation_must_bind_selected_graph")
            if self.evaluations[0].member_graph_ref != self.inputs.graph_ref:
                raise ValueError("resolved_graph_evaluation_ref_must_match_selected_graph_ref")
        if self.evaluation_budget.termination == "completed" and (
            not self.evaluations or any(row.disposition != "completed" for row in self.evaluations)
        ):
            raise ValueError("completed_evaluation_phase_requires_only_completed_solver_rows")
        if self.evaluation_budget.termination == "not_required" and self.evaluations:
            raise ValueError("not_required_evaluation_phase_cannot_carry_member_rows")
        for evaluation in self.evaluations:
            if evaluation.disposition == "completed":
                outcome = evaluation.outcome
                if outcome is None:
                    raise ValueError("completed_candidate_evaluation_requires_outcome")
                if (
                    outcome.query_sha256 != self.inputs.query_sha256
                    or outcome.result.query
                    != f"P*({self.inputs.query_outcome}|do({self.inputs.query_treatment}))"
                ):
                    raise ValueError("candidate_solver_query_binding_mismatch")
        completed = [row for row in self.evaluations if row.disposition == "completed"]
        denominator = len(completed)
        derived_fraction = None
        if denominator:
            derived_fraction = (
                sum(
                    row.outcome is not None
                    and row.outcome.status is TransportabilityStatus.IDENTIFIED
                    for row in completed
                )
                / denominator
            )
        if self.identified_member_fraction != derived_fraction:
            raise ValueError("candidate_identified_fraction_must_match_completed_rows")
        started_evaluations = [
            row
            for row in self.evaluations
            if row.disposition in {"interrupted", "completed", "error"}
        ]
        if started_evaluations and self.evaluation_budget.admission != "admitted":
            raise ValueError("candidate_evaluation_requires_actual_budget_admission")
        if (
            not self.evaluations
            and self.inputs.graph_type is GraphType.PAG
            and not admitted_members
            and self.evaluation_budget.admission == "admitted"
        ):
            raise ValueError("candidate_without_valid_members_cannot_admit_solver_execution")
        if self.proposals and self.generation_budget.admission != "admitted":
            raise ValueError("candidate_generation_rows_require_actual_budget_admission")

        expected_disposition = self._derive_execution_disposition()
        if self.disposition != expected_disposition:
            raise ValueError("candidate_disposition_must_match_reconciled_execution_state")
        if (expected_disposition == "completed") != (self.reason is None):
            raise ValueError("candidate_disposition_reason_must_match_reconciled_execution_state")
        return self

    @property
    def proposal_counts(self) -> dict[str, int]:
        """Derive generation counts from the complete persisted proposal rows."""
        counts = {
            "admitted": 0,
            "duplicate": 0,
            "invalid": 0,
            "unsupported": 0,
            "validation_incomplete": 0,
        }
        for row in self.proposals:
            counts[row.disposition] += 1
        return counts

    @property
    def evaluation_counts(self) -> dict[str, int]:
        """Derive visible evaluation counts from the immutable member rows."""
        counts = {
            "not_started": 0,
            "interrupted": 0,
            "completed": 0,
            "error": 0,
            "identified": 0,
            "partially_identified": 0,
            "bounded_non_identified": 0,
            "unsupported": 0,
        }
        for row in self.evaluations:
            counts[row.disposition] += 1
            if row.outcome is not None:
                counts[row.outcome.status.value] += 1
        return counts


def transportability_candidate_query_sha256(
    query_treatment: str,
    query_outcome: str,
) -> str:
    """Hash the canonical query expression used by candidate transport solvers."""
    treatment = query_treatment.strip()
    outcome = query_outcome.strip()
    if not treatment or not outcome or treatment != query_treatment or outcome != query_outcome:
        raise ValueError("candidate_query_terms_must_be_nonblank_and_canonical")
    query = f"P*({outcome}|do({treatment}))"
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


class TransportabilityResult(BaseModel):
    """Persist the transportability decision, formula, and fallback diagnostics.

    Readiness gates and reporting layers inspect ``status`` and
    ``transport_mode`` to decide whether a query can be transported directly,
    requires a transport formula, falls back to bounds, or is unsupported. The
    model also upgrades legacy payload aliases so older persisted artifacts can
    still be read during migration. Normalization happens before instance
    creation so validated models no longer rewrite their own fields.
    """

    contract_id: ClassVar[str] = "ir.transportability_result.v2"
    output_contract_declaration: ClassVar[OutputContractDeclaration] = (
        value_uncertainty_output_contract(
            contract_id,
            projection_kind=ValueUncertaintyProjectionKind.TRANSPORT,
        )
    )
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("2.2", pattern=r"^\d+\.\d+$")
    query: str = ""

    status: TransportabilityStatus = TransportabilityStatus.IDENTIFIED
    transport_mode: TransportMode = TransportMode.DIRECT
    transport_formula: TransportFormula | None = None
    candidate_diagnostics: TransportabilityCandidateDiagnosticV1 | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    identified_region: dict[str, Any] | None = None
    blocking_s_nodes: list[SNode] = Field(default_factory=list)

    base_confidence: float = 1.0
    context_distance_penalty: float = 0.0
    data_availability_penalty: float = 0.0
    final_confidence: float = 1.0

    algorithm_version: str = "trso_v2"
    identification_engine: str = "simplified_legacy"
    identification_trace: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    unsupported_cases: list[str] = Field(default_factory=list)
    pag_identification_policy: PAGIdentificationPolicy | None = None
    id_confidence_under_pag: float | None = None
    pag_dag_sample_size: int | None = Field(default=None, ge=0)
    pag_transportable_count: int | None = Field(default=None, ge=0)

    feasible: bool = True
    hard_legal_constraints: list[str] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    p_star_values: dict[str, PStarZResult] = Field(default_factory=dict)
    legal_s_nodes: list[SNode] = Field(default_factory=list)
    resolution_rounds: int = Field(default=1, ge=1)
    proxy_penalties: dict[str, float] = Field(default_factory=dict)

    warnings: list[str] = Field(default_factory=list)
    required_target_data: list[str] = Field(default_factory=list)

    selection_diagram_ref: str = ""
    source_graph_type: GraphType | None = None
    source_graph_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_context_id: str = ""
    target_context_id: str = ""

    # Phase 12: temporal stationarity (DOD-141).
    assumes_time_stationarity: bool = True
    lagged_edge_count: int = Field(default=0, ge=0)
    temporal_distance_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    lagged_edges_in_query: bool = False
    time_stationarity_warning: str | None = None

    # Phase 12 advanced: bounded outer-search runtime signals (DOD-139/140).
    outer_search_truncated: bool = False
    search_budget_exhausted: bool = False
    outer_search_configs_evaluated: int = Field(default=0, ge=0)
    outer_search_best_score: float | None = None
    search_events: list[str] = Field(default_factory=list)

    # Phase 12 advanced: proxy validity checklist and expert review escalation.
    requires_expert_review: bool = False
    expert_review_reasons: list[str] = Field(default_factory=list)
    proxy_validity: dict[str, dict[str, Any]] = Field(default_factory=dict)

    # Phase 12 advanced: partial identification fallback for non-identified cases.
    partial_identification_result: PartialIdentificationResult | None = None

    # Pearl-Bareinboim ID engine: structured EstimandAST (dict for circular-import safety).
    # Consumers: EstimandAST.model_validate(result.estimand_ast)
    estimand_ast: dict[str, Any] | None = Field(default=None)

    # Backward-compatible Phase 8A fields.
    sutva_assumed: bool = True
    sutva_violation_risk: Literal["high", "medium", "low"] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_formula_alias(
        cls,
        payload: object,
    ) -> object:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: object) -> object:
        """Return a normalized transportability payload without mutating input.

        This is the explicit compatibility boundary for legacy aliases
        (``formula``), legacy statuses, v1.0 schema stamps, and derived runtime
        signals. It is also used by the validation shim so re-parsing old
        artifacts remains deterministic.
        """
        if not isinstance(payload, dict):
            return payload
        payload = dict(payload)
        if "transport_formula" not in payload and "formula" in payload:
            payload["transport_formula"] = payload.get("formula")
        if "formula" in payload:
            payload.pop("formula", None)
        status_raw = str(payload.get("status", "")).strip().lower()
        if status_raw in {"direct", "transportable", "non_transportable"}:
            mapped_status, mapped_mode = _map_legacy_status_payload(payload)
            payload["status"] = mapped_status.value
            payload.setdefault("transport_mode", mapped_mode.value)
        elif "transport_mode" not in payload:
            payload["transport_mode"] = _derive_transport_mode(payload).value
        payload["identification_engine"] = _normalize_identification_engine(payload)
        version = payload.get("schema_version")
        if isinstance(version, str) and version.strip() == "1.0":
            payload["schema_version"] = "2.0"
        return _normalize_transportability_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TransportabilityResult:
        """Construct a result after applying explicit compatibility normalization."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def _validate_contract(self) -> TransportabilityResult:
        if self.schema_version != "2.2" and "candidate_diagnostics" in self.model_fields_set:
            raise ValueError("candidate_diagnostic_field_conflicts_with_historical_result_version")
        if (self.source_graph_type is None) != (self.source_graph_sha256 is None):
            raise ValueError("source graph type and content digest must be supplied together")
        if (
            self.pag_dag_sample_size is not None
            and self.pag_transportable_count is not None
            and self.pag_transportable_count > self.pag_dag_sample_size
        ):
            raise ValueError("pag_transportable_count cannot exceed pag_dag_sample_size")
        if self.status is TransportabilityStatus.IDENTIFIED:
            if self.transport_mode is TransportMode.NONE:
                raise ValueError(
                    "identified transportability result cannot use transport_mode=none"
                )
            if (
                self.transport_mode is TransportMode.TRANSPORT_FORMULA
                and self.transport_formula is None
            ):
                raise ValueError("transport_mode=transport_formula requires transport_formula")
        if self.status is TransportabilityStatus.PARTIALLY_IDENTIFIED:
            if self.transport_mode is TransportMode.NONE:
                raise ValueError(
                    "partially_identified transportability result cannot use transport_mode=none"
                )
            if self.transport_formula is None and self.identified_region is None:
                raise ValueError(
                    "partially_identified requires transport_formula or identified_region"
                )
        if self.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED:
            if self.partial_identification_result is None:
                raise ValueError("bounded_non_identified requires partial_identification_result")
            if self.transport_mode is not TransportMode.BOUNDS_ONLY:
                raise ValueError("bounded_non_identified requires transport_mode=bounds_only")
            if self.transport_formula is not None:
                raise ValueError("bounded_non_identified must not include transport_formula")
        if self.status is TransportabilityStatus.UNSUPPORTED:
            if not self.unsupported_reason:
                raise ValueError("unsupported transportability result requires unsupported_reason")
            if self.transport_mode is not TransportMode.NONE:
                raise ValueError("unsupported transportability result must use transport_mode=none")
            if self.transport_formula is not None:
                raise ValueError(
                    "unsupported transportability result must not include transport_formula"
                )
        if self.candidate_diagnostics is not None:
            if self.schema_version != "2.2":
                raise ValueError("candidate_diagnostic_requires_transport_result_schema_2_2")
            if (
                self.status is not TransportabilityStatus.UNSUPPORTED
                or self.transport_mode is not TransportMode.NONE
                or self.feasible
                or not self.unsupported_reason
                or not self.requires_expert_review
                or self.unsupported_reason not in self.expert_review_reasons
            ):
                raise ValueError("candidate_diagnostic_must_preserve_exact_outer_legal_refusal")
            expected_query = (
                f"P*({self.candidate_diagnostics.inputs.query_outcome}|do("
                f"{self.candidate_diagnostics.inputs.query_treatment}))"
            )
            if (
                self.query != expected_query
                or self.source_graph_type is not self.candidate_diagnostics.inputs.graph_type
                or self.source_graph_sha256 != self.candidate_diagnostics.inputs.graph_sha256
                or self.source_context_id != self.candidate_diagnostics.inputs.source_context_id
                or self.target_context_id != self.candidate_diagnostics.inputs.target_context_id
            ):
                raise ValueError("candidate_diagnostic_outer_input_binding_mismatch")
            if (
                self.base_confidence != 0.0
                or self.final_confidence != 0.0
                or self.transport_formula is not None
                or self.identified_region is not None
                or self.partial_identification_result is not None
                or self.estimand_ast is not None
                or self.id_confidence_under_pag is not None
                or self.pag_dag_sample_size is not None
                or self.pag_transportable_count is not None
            ):
                raise ValueError("candidate_diagnostic_must_not_populate_outer_candidate_fields")
        return self

    @property
    def has_admissible_partial_bounds(self) -> bool:
        """Return whether the declared result tuple authorizes bound projections."""
        return (
            self.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED
            and self.transport_mode is TransportMode.BOUNDS_ONLY
            and self.transport_formula is None
            and self.partial_identification_result is not None
        )

    def is_identified(self) -> bool:
        return self.status in {
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
        }

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> UncertaintyEnvelope | None:
        """Project transport bounds only when the query identity is explicit."""

        estimand_id = str(getattr(estimand, "estimand_id", "") or "")
        if not self.query or estimand_id != self.query:
            return None
        if (
            projection_binding.native_contract_id != self.contract_id
            or not projection_binding.matches(estimand)
        ):
            return None
        if not self.has_admissible_partial_bounds:
            return None
        bounds = self.partial_identification_result
        if bounds is None:
            return None
        lower = float(bounds.lower_bound)
        upper = float(bounds.upper_bound)
        return UncertaintyEnvelope(
            point_estimate=(lower + upper) / 2.0,
            confidence_interval=(lower, upper),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            gate_eligible=bool(bounds.is_informative),
            metadata={
                "query": self.query,
                "transport_status": self.status.value,
                "transport_mode": self.transport_mode.value,
                "bounds_method": bounds.method.value,
                "value_estimand_binding_content_hash": (projection_binding.content_hash),
                "value_estimand_binding_native_contract_id": (
                    projection_binding.native_contract_id
                ),
                "value_estimand_binding_producer_method_fqn": (
                    projection_binding.producer_method_fqn
                ),
            },
        )


TransportabilityCandidateSolverOutcomeV1.model_rebuild()


def build_selection_diagram(
    source_context: ContextProfile,
    target_context: ContextProfile,
    causal_graph: CausalGraphModel,
) -> SelectionDiagram:
    """Build selection diagram."""
    graph_variables = set(causal_graph.nodes)
    s_nodes: list[SNode] = []

    for dim, affected_variables in CONTEXT_VARIABLE_SENSITIVITY.items():
        if dim in {"post_communist", "post_conflict"}:
            continue
        src_val = _get_context_numeric(source_context, dim)
        tgt_val = _get_context_numeric(target_context, dim)
        if src_val is None or tgt_val is None:
            continue
        delta = abs(src_val - tgt_val)
        if delta < THRESHOLD_FOR_S_NODE:
            continue
        severity = _severity_from_delta(delta)
        for var in affected_variables:
            if var not in graph_variables:
                continue
            s_nodes.append(
                SNode(
                    target_variable=var,
                    context_dimension=dim,
                    source_value=float(src_val),
                    target_value=float(tgt_val),
                    delta=float(delta),
                    severity=severity,
                )
            )

    for bool_dim in ("post_communist", "post_conflict"):
        src_val = bool(getattr(source_context, bool_dim, False))
        tgt_val = bool(getattr(target_context, bool_dim, False))
        if src_val == tgt_val:
            continue
        for var in CONTEXT_VARIABLE_SENSITIVITY.get(bool_dim, []):
            if var not in graph_variables:
                continue
            s_nodes.append(
                SNode(
                    target_variable=var,
                    context_dimension=bool_dim,
                    source_value=str(src_val),
                    target_value=str(tgt_val),
                    delta=1.0,
                    severity="high",
                )
            )

    distance = source_context.distance_to(target_context)
    return SelectionDiagram(
        base_graph=causal_graph,
        s_nodes=s_nodes,
        source_context=source_context,
        target_context=target_context,
        context_distance=distance,
    )


_TRANSPORTABILITY_RESULT_WIRE_POLICY = "ir.analytics.transportability_result.wire-law"
_TRANSPORTABILITY_RESULT_OWNER_REF = "ir.analytics.ir.transportability_result.owner.v2"
_TRANSPORTABILITY_RESULT_DTO_FQN = "polisyos.ir.analytics.transportability.TransportabilityResult"
_TRANSPORTABILITY_RESULT_REGISTRY_KEY = "transportability_result"

# Register source rows before the current row so its direct-read relation can
# name exact readable tuples in the same registry snapshot.
_register_ir_representation(
    registry_key=_TRANSPORTABILITY_RESULT_REGISTRY_KEY,
    owner_ref=_TRANSPORTABILITY_RESULT_OWNER_REF,
    dto_abi=_TRANSPORTABILITY_RESULT_DTO_FQN,
    wire_policy_ref=_TRANSPORTABILITY_RESULT_WIRE_POLICY,
    wire_policy_revision="1",
    schema_name="ir.transportability_result",
    schema_version="2.2",
    payload_version="2.0",
    profile_ref=None,
    readable=True,
    writable=False,
    current=False,
    default_write=False,
)
_register_ir_representation(
    registry_key=_TRANSPORTABILITY_RESULT_REGISTRY_KEY,
    owner_ref=_TRANSPORTABILITY_RESULT_OWNER_REF,
    dto_abi=_TRANSPORTABILITY_RESULT_DTO_FQN,
    wire_policy_ref=_TRANSPORTABILITY_RESULT_WIRE_POLICY,
    wire_policy_revision="1",
    schema_name="ir.transportability_result",
    schema_version="2.0",
    payload_version="2.0",
    profile_ref=None,
    readable=True,
    writable=True,
    current=False,
    default_write=False,
)

_TRANSPORTABILITY_RESULT_OWNER = _declare_model_owner(
    TransportabilityResult,
    contract_id=_TRANSPORTABILITY_RESULT_OWNER_REF,
    dto_fqn=_TRANSPORTABILITY_RESULT_DTO_FQN,
    abi_key="ir.analytics.ir.transportability_result.owner.v2.dto-abi.v1",
    registry_key=_TRANSPORTABILITY_RESULT_REGISTRY_KEY,
    kind="ir.transportability_result",
    media_type="application/json",
    purpose="transportability_result",
    policy_revision="ir.analytics.ir.transportability_result.owner.v2.admission.v1",
    accepted_wire_policies=((_TRANSPORTABILITY_RESULT_WIRE_POLICY, "1"),),
    payload_version_field="schema_version",
    validate_profile=_owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        _OwnedJSONRepresentation(
            schema_name="ir.transportability_result",
            schema_version="2.2",
            payload_version="2.2",
            wire_policy_ref=_TRANSPORTABILITY_RESULT_WIRE_POLICY,
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=_CompatibilityMode.NONE,
            notes=("TransportabilityResult 2.2 is the current owner-bound JSON representation.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(
                IRRepresentationKey("ir.transportability_result", "2.2", "2.0"),
                IRRepresentationKey("ir.transportability_result", "2.0", "2.0"),
            ),
        ),
    ),
)


def persist_transportability_result(
    store: ArtifactStore,
    result: TransportabilityResult,
    *,
    inputs: Sequence[InputRefLike] | None = None,
    schema_name: str = "ir.transportability_result",
    schema_version: str = "2.2",
    return_selected_profile: bool = True,
) -> TransportabilityResultRef:
    """Persist a transportability result through its exact owner representation.

    The writer binds manifest and embedded versions before the CAS boundary.
    ``return_selected_profile=False`` preserves the legacy profileless reference
    projection while the write itself still captures its exact selected profile.
    """
    return_selected_profile = _validate_return_selected_profile_flag(return_selected_profile)
    ref = _put_owned_json_artifact(
        store,
        result.model_dump(mode="json"),
        owner=_TRANSPORTABILITY_RESULT_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_ref = TransportabilityResultRef.from_selected_write(ref)
    if not return_selected_profile:
        return selected_ref.model_copy(update={"manifest_profile_sha256": None})
    return selected_ref


def load_transportability_result(
    store: ArtifactStore,
    ref: TransportabilityResultRef,
) -> TransportabilityResult:
    """Load transportability result."""
    return _get_owned_json_artifact(store, ref, owner=_TRANSPORTABILITY_RESULT_OWNER)


def _get_context_numeric(ctx: ContextProfile, dim: str) -> float | None:
    if dim == "income_level":
        order = {
            IncomeLevel.LOW: 0.0,
            IncomeLevel.LOWER_MIDDLE: 0.33,
            IncomeLevel.UPPER_MIDDLE: 0.67,
            IncomeLevel.HIGH: 1.0,
            IncomeLevel.NON_HIGH: 0.5,
            IncomeLevel.UNKNOWN: 0.5,
        }
        value = ctx.income_level
        try:
            return order[IncomeLevel(value)]
        except (KeyError, ValueError):
            return 0.5
    raw = getattr(ctx, dim, None)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _severity_from_delta(delta: float) -> Literal["low", "medium", "high"]:
    if delta > 0.5:
        return "high"
    if delta > 0.3:
        return "medium"
    return "low"


def measured_transport_severity(
    source_value: float,
    target_value: float,
) -> Literal["low", "medium", "high"]:
    """Classify a measured source/target delta using the transport owner rule."""

    return _severity_from_delta(abs(float(target_value) - float(source_value)))


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _normalize_transportability_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for field_name in (
        "base_confidence",
        "context_distance_penalty",
        "data_availability_penalty",
        "final_confidence",
        "temporal_distance_penalty",
    ):
        if field_name in normalized and normalized[field_name] is not None:
            normalized[field_name] = _clamp01(float(normalized[field_name]))
    if normalized.get("id_confidence_under_pag") is not None:
        normalized["id_confidence_under_pag"] = _clamp01(
            float(normalized["id_confidence_under_pag"])
        )

    lagged_edge_count = int(normalized.get("lagged_edge_count", 0) or 0)
    normalized["lagged_edge_count"] = lagged_edge_count
    normalized["lagged_edges_in_query"] = lagged_edge_count > 0
    if normalized["lagged_edges_in_query"]:
        normalized["assumes_time_stationarity"] = True
        if not str(normalized.get("time_stationarity_warning") or "").strip():
            normalized["time_stationarity_warning"] = (
                "Lagged transport path detected; assumes_time_stationarity=True."
            )

    outer_search_truncated = bool(normalized.get("outer_search_truncated"))
    normalized["outer_search_truncated"] = outer_search_truncated
    normalized["search_budget_exhausted"] = (
        bool(normalized.get("search_budget_exhausted")) or outer_search_truncated
    )
    search_events = _dedupe_str_items(normalized.get("search_events"))
    if normalized["search_budget_exhausted"]:
        search_events = _append_unique(search_events, "search_budget_exhausted")
    if outer_search_truncated:
        search_events = _append_unique(search_events, "outer_search_truncated")
    normalized["search_events"] = search_events

    status_raw = (
        str(normalized.get("status", TransportabilityStatus.IDENTIFIED.value)).strip().lower()
    )
    if status_raw == TransportabilityStatus.BOUNDED_NON_IDENTIFIED.value:
        normalized["transport_mode"] = TransportMode.BOUNDS_ONLY.value
        normalized["transport_formula"] = None
    elif status_raw == TransportabilityStatus.UNSUPPORTED.value:
        normalized["transport_mode"] = TransportMode.NONE.value
        normalized["transport_formula"] = None
        if not str(normalized.get("unsupported_reason") or "").strip():
            normalized["unsupported_reason"] = "transport_unsupported"
    return normalized


def _derive_transport_mode(payload: dict[str, Any]) -> TransportMode:
    if payload.get("partial_identification_result") is not None:
        return TransportMode.BOUNDS_ONLY
    formula = payload.get("transport_formula")
    if formula is not None:
        if hasattr(formula, "model_dump"):
            formula_payload = formula.model_dump(mode="json")
        elif isinstance(formula, dict):
            formula_payload = formula
        else:
            formula_payload = {}
        target_quantities = formula_payload.get("target_quantities", [])
        if target_quantities:
            return TransportMode.TRANSPORT_FORMULA
    status_raw = str(payload.get("status", "")).strip().lower()
    if status_raw in {"identified", "partially_identified"}:
        return TransportMode.DIRECT
    return TransportMode.DIRECT


def _map_legacy_status_payload(
    payload: dict[str, Any],
) -> tuple[TransportabilityStatus, TransportMode]:
    status_raw = str(payload.get("status", "")).strip().lower()
    if status_raw == "direct":
        return TransportabilityStatus.IDENTIFIED, TransportMode.DIRECT
    if status_raw == "transportable":
        return TransportabilityStatus.IDENTIFIED, TransportMode.TRANSPORT_FORMULA
    partial = payload.get("partial_identification_result")
    if isinstance(partial, dict):
        try:
            parsed = PartialIdentificationResult.model_validate(partial)
        except (ValueError, TypeError):
            parsed = None
        if parsed is not None and parsed.is_informative:
            return (
                TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
                TransportMode.BOUNDS_ONLY,
            )
    return TransportabilityStatus.UNSUPPORTED, TransportMode.NONE


def _normalize_identification_engine(payload: dict[str, Any]) -> str:
    raw = str(payload.get("identification_engine", "") or "").strip().lower()
    trace = [str(item) for item in payload.get("identification_trace", [])]
    if raw in {"", "simplified"}:
        return "simplified_legacy"
    if raw == "bounds_only":
        return "bounds_only"
    if raw in {"r", "r_causaleffect"}:
        return "r_causaleffect"
    if raw in {"y0", "symbolic_y0"}:
        return "y0"
    if raw in {"symbolic", "symbolic_r", "full_auto"}:
        joined = " ".join(trace)
        if "symbolic_backend_selected:r" in joined or "symbolic_backend_requested:r" in joined:
            return "r_causaleffect"
        if (
            "symbolic_backend_selected:y0" in joined
            or "symbolic_backend_requested:y0" in joined
            or "symbolic_backend_requested:full_auto" in joined
        ):
            return "y0"
        return "y0"
    return raw


def _append_unique(items: list[str], value: str) -> list[str]:
    if value in items:
        return items
    return [*items, value]


def _dedupe_str_items(items: object) -> list[str]:
    if not isinstance(items, (list, tuple)):
        return []
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


__all__ = [
    "CONTEXT_VARIABLE_SENSITIVITY",
    "THRESHOLD_FOR_S_NODE",
    "DataGap",
    "MultiSourceSelectionDiagram",
    "SNode",
    "SNodeOrigin",
    "SNodeRole",
    "SelectionDiagram",
    "SelectionDiagramBuilder",
    "SigmaVariable",
    "SourceDomainSpec",
    "StratificationVariable",
    "TransportFormula",
    "TransportMode",
    "TransportabilityCandidateAttemptBindingV1",
    "TransportabilityCandidateBudgetMeasureV1",
    "TransportabilityCandidateDiagnosticV1",
    "TransportabilityCandidateInputBindingV1",
    "TransportabilityCandidateMemberEvaluationV1",
    "TransportabilityCandidateModelPlanRelationV1",
    "TransportabilityCandidatePhaseBudgetV1",
    "TransportabilityCandidateProfileV1",
    "TransportabilityCandidateProposalV1",
    "TransportabilityCandidateReasonV1",
    "TransportabilityCandidateRequestV1",
    "TransportabilityCandidateResourceResolutionV1",
    "TransportabilityCandidateSolverOutcomeV1",
    "TransportabilityResult",
    "TransportabilityStatus",
    "build_selection_diagram",
    "load_transportability_result",
    "measured_transport_severity",
    "persist_transportability_result",
    "transportability_candidate_query_sha256",
]
