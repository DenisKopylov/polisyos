from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.datasets.knowledge.proxy_resolver import ProxyCandidate
from polisyos.datasets.knowledge.types import PStarZResult
from polisyos.ir.analytics.causal_graph import CausalGraphModel, PAGIdentificationPolicy
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.partial_identification import PartialIdentificationResult
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import TransportabilityResultRef

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
    CONTEXT_DELTA = "context_delta"
    LEGAL = "legal"
    DATA_MISMATCH = "data_mismatch"


class SNodeRole(str, Enum):
    PRE_TREATMENT_COVARIATE = "pre_treatment_covariate"
    MEDIATOR = "mediator"
    COLLIDER = "collider"
    INSTRUMENT = "instrument"


class SNode(BaseModel):
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


class SelectionDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_graph: CausalGraphModel
    s_nodes: list[SNode] = Field(default_factory=list)
    source_context: ContextProfile
    target_context: ContextProfile
    context_distance: float = 0.0


class StratificationVariable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: SNodeRole
    requires_conditional: bool
    condition_on_treatment: str | None = None


class TransportFormula(BaseModel):
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
    DIRECT = "direct"
    TRANSPORTABLE = "transportable"
    NON_TRANSPORTABLE = "non_transportable"


class DataGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_variable: str
    required_context: str
    available_proxies: list[ProxyCandidate] = Field(default_factory=list)
    best_proxy_confidence: float = 0.0
    gap_impact: str
    suggested_action: str


class TransportabilityResult(BaseModel):
    """Phase 12 transportability contract (backward compatible with Phase 8A fields)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query: str = ""

    status: TransportabilityStatus = TransportabilityStatus.DIRECT
    transport_formula: TransportFormula | None = None
    blocking_s_nodes: list[SNode] = Field(default_factory=list)

    base_confidence: float = 1.0
    context_distance_penalty: float = 0.0
    data_availability_penalty: float = 0.0
    final_confidence: float = 1.0

    algorithm_version: str = "simplified_tr_v2"
    identification_engine: str = "simplified"
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

    # Phase 12 advanced: partial identification fallback for non-transportable cases.
    partial_identification_result: PartialIdentificationResult | None = None

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
        if not isinstance(payload, dict):
            return payload
        if "transport_formula" not in payload and "formula" in payload:
            payload = dict(payload)
            payload["transport_formula"] = payload.get("formula")
        if "formula" in payload:
            payload = dict(payload)
            payload.pop("formula", None)
        return payload

    @model_validator(mode="after")
    def _normalize_contract(self) -> "TransportabilityResult":

        self.base_confidence = _clamp01(self.base_confidence)
        self.context_distance_penalty = _clamp01(self.context_distance_penalty)
        self.data_availability_penalty = _clamp01(self.data_availability_penalty)
        self.final_confidence = _clamp01(self.final_confidence)
        self.lagged_edges_in_query = bool(self.lagged_edge_count > 0)
        if self.lagged_edges_in_query:
            self.assumes_time_stationarity = True
        if self.lagged_edges_in_query and not self.time_stationarity_warning:
            self.time_stationarity_warning = (
                "Lagged transport path detected; assumes_time_stationarity=True."
            )
        if self.outer_search_truncated:
            self.search_budget_exhausted = True
        if self.search_budget_exhausted and "search_budget_exhausted" not in self.search_events:
            self.search_events = [*self.search_events, "search_budget_exhausted"]
        if self.outer_search_truncated and "outer_search_truncated" not in self.search_events:
            self.search_events = [*self.search_events, "outer_search_truncated"]
        if self.id_confidence_under_pag is not None:
            self.id_confidence_under_pag = _clamp01(self.id_confidence_under_pag)
        if (
            self.pag_dag_sample_size is not None
            and self.pag_transportable_count is not None
            and self.pag_transportable_count > self.pag_dag_sample_size
        ):
            raise ValueError("pag_transportable_count cannot exceed pag_dag_sample_size")
        return self


def build_selection_diagram(
    source_context: ContextProfile,
    target_context: ContextProfile,
    causal_graph: CausalGraphModel,
) -> SelectionDiagram:
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
        except Exception:
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


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


__all__ = [
    "CONTEXT_VARIABLE_SENSITIVITY",
    "THRESHOLD_FOR_S_NODE",
    "SNodeOrigin",
    "SNodeRole",
    "SNode",
    "SelectionDiagram",
    "StratificationVariable",
    "TransportFormula",
    "TransportabilityStatus",
    "DataGap",
    "TransportabilityResult",
    "build_selection_diagram",
    "persist_transportability_result",
    "load_transportability_result",
]
