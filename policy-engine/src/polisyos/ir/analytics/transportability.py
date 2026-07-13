"""Public analytics transportability module API."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.partial_identification import PartialIdentificationResult
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import TransportabilityResultRef

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.catalog import ProxyCandidate, PStarZResult
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, PAGIdentificationPolicy
else:
    from polisyos.data_forge.read_api.catalog import ProxyCandidate, PStarZResult
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, PAGIdentificationPolicy

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

    def to_source_domain(self) -> Any:
        """Convert to ``id_engine.SourceDomain`` for algorithmic use.

        Uses a lazy import to avoid foundry→IR circular imports.
        """
        from polisyos.foundry.methods.catalog.causal.id_engine import SourceDomain

        return SourceDomain(
            domain_id=self.domain_id,
            s_nodes=frozenset(sn.target_variable for sn in self.s_nodes),
            z_interventions=frozenset(self.z_interventions),
            dataset_ref=self.dataset_ref,
        )

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

    Use ``to_source_domains()`` to convert to the list expected by
    ``mz_id_algorithm()`` in ``id_engine.py``.
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

    def to_source_domains(self) -> list[Any]:
        """Convert all domains to ``id_engine.SourceDomain`` objects."""
        return [spec.to_source_domain() for spec in self.domains]


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


class TransportabilityResult(BaseModel):
    """Persist the transportability decision, formula, and fallback diagnostics.

    Readiness gates and reporting layers inspect ``status`` and
    ``transport_mode`` to decide whether a query can be transported directly,
    requires a transport formula, falls back to bounds, or is unsupported. The
    model also upgrades legacy payload aliases so older persisted artifacts can
    still be read during migration. Normalization happens before instance
    creation so validated models no longer rewrite their own fields.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    query: str = ""

    status: TransportabilityStatus = TransportabilityStatus.IDENTIFIED
    transport_mode: TransportMode = TransportMode.DIRECT
    transport_formula: TransportFormula | None = None
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
        payload: Any,
    ) -> Any:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: Any) -> Any:
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
        if str(payload.get("schema_version", "")).strip() in {"", "1.0"}:
            payload["schema_version"] = "2.0"
        return _normalize_transportability_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TransportabilityResult:
        """Construct a result after applying explicit compatibility normalization."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def _validate_contract(self) -> TransportabilityResult:
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
        return self

    def is_identified(self) -> bool:
        return self.status in {
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
        }


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


def persist_transportability_result(
    store: ArtifactStore,
    result: TransportabilityResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.transportability_result",
    schema_version: str = "1.0",
) -> TransportabilityResultRef:
    """Persist transportability result helper."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.transportability_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TransportabilityResultRef.model_validate(ref)


def load_transportability_result(
    store: ArtifactStore,
    ref: TransportabilityResultRef,
) -> TransportabilityResult:
    """Load transportability result."""
    payload = get_json_artifact(store, ref.artifact_id)
    return TransportabilityResult.model_validate(payload)


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


def _dedupe_str_items(items: Any) -> list[str]:
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
    "TransportabilityResult",
    "TransportabilityStatus",
    "build_selection_diagram",
    "load_transportability_result",
    "measured_transport_severity",
    "persist_transportability_result",
]
