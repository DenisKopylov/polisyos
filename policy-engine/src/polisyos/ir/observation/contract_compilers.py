"""Compile normalized observation artifacts into Foundry/Scientist protocol bundles.

Each compiler consumes a typed observation contract, validates shape and
lineage, and emits a ``CompiledObservationArtifact`` plus a bundle manifest
that advertises which downstream runtime protocol can consume the payload.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._internal.validation import ensure_unique_ids
from polisyos.ir.analytics.microsim_calibration import build_microsim_calibration_report
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.observation.bundles import (
    BACKTEST_PLAN_TARGET,
    DYNAMIC_TREATMENT_TARGET,
    MULTIPLEX_NETWORK_TARGET,
    NETWORK_ANALYSIS_TARGET,
    NETWORK_DATA_TARGET,
    PANEL_ECONOMETRIC_TARGET,
    PANEL_OBSERVATIONAL_TARGET,
    PROXY_MEASUREMENT_TARGET,
    SURVEY_MICRODATA_TARGET,
    SURVIVAL_DATA_TARGET,
    BacktestPlanBundle,
    BoundsChannelSpec,
    BoundsEstimationBundle,
    BundleAxisSemantic,
    BundleLineageRef,
    CausalPanelBundleManifest,
    ContractCompatibilityTarget,
    DTRTreatmentSequenceBundleManifest,
    LeontiefIOBundle,
    MicrosimSurveyContractBundle,
    NetworkCausalContractBundle,
    NetworkContractBundle,
    ObservationContractArtifact,
    ObservationContractRoute,
    ObservationToContractManifest,
    PanelEconometricBundleManifest,
    ProxyChannelSpec,
    ProxyIdentificationBundle,
    RequiredArraySpec,
    RequiredColumnSpec,
    SpecificationCurveBundle,
    SpecificationCurveSource,
    SurvivalDataBundleManifest,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    MultiplexGraphLayerId,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
)
from polisyos.ir.observation.measurement import (
    IdentificationModeRouter,
    MeasurementRegistry,
    SchemaRegimeRegistry,
)
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date

    from polisyos.ir.analytics.causal_graph import CausalGraphModel
else:
    from datetime import date

    from polisyos.ir.analytics.causal_graph import CausalGraphModel

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class ObservationContractCompileError(ValueError):
    """Validation error raised while compiling observation contracts."""

    def __init__(
        self,
        message: str,
        *,
        compiler_id: str,
        field_name: str | None = None,
    ) -> None:
        self.compiler_id = compiler_id
        self.field_name = field_name
        suffix = f" [{field_name}]" if field_name else ""
        super().__init__(f"{compiler_id}: {message}{suffix}")


class ObservationContractLoadError(ValueError):
    """Load/parse error raised while reading serialized observation artifacts."""

    def __init__(
        self, message: str, *, artifact_path: str | None = None, field_name: str | None = None
    ) -> None:
        self.artifact_path = artifact_path
        self.field_name = field_name
        location = f" path={artifact_path}" if artifact_path else ""
        field = f" field={field_name}" if field_name else ""
        super().__init__(f"{message}{location}{field}")


class _MutableModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoundsEstimationInput(_MutableModel):
    """Dense payload consumed by partial-identification and bounds estimators."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    outcome: list[float] = Field(..., min_length=1)
    treatment: list[float] = Field(..., min_length=1)
    instrument: list[float] | None = None
    selected: list[float] | None = None
    miv_proxy: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shapes(self) -> BoundsEstimationInput:
        n_obs = len(self.outcome)
        if len(self.treatment) != n_obs:
            raise ValueError("treatment length must match outcome length")
        for name in ("instrument", "selected", "miv_proxy"):
            value = getattr(self, name)
            if value is not None and len(value) != n_obs:
                raise ValueError(f"{name} length must match outcome length")
        return self


class SpecificationCurveInput(_MutableModel):
    """Ordered estimates used to construct a specification curve."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    specification_ids: list[str] = Field(..., min_length=1)
    estimates: list[float] = Field(..., min_length=1)
    standard_errors: list[float] = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shapes(self) -> SpecificationCurveInput:
        n_specs = len(self.specification_ids)
        if len(self.estimates) != n_specs or len(self.standard_errors) != n_specs:
            raise ValueError("specification_ids, estimates, and standard_errors must align")
        return self


class LeontiefIOInput(_MutableModel):
    """Carry dense IO tables and axis labels into Leontief bundle compilation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    technical_coefficients: list[list[float]] = Field(..., min_length=1)
    final_demand: list[float] = Field(..., min_length=1)
    sector_names: list[str] = Field(..., min_length=1)
    regions: list[str] = Field(default_factory=list)
    value_added: list[float] = Field(default_factory=list)
    region_index_map: dict[str, int] = Field(default_factory=dict)
    sector_index_map: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shapes(self) -> LeontiefIOInput:
        n = len(self.technical_coefficients)
        if any(len(row) != n for row in self.technical_coefficients):
            raise ValueError("technical_coefficients must be square")
        if len(self.final_demand) != n:
            raise ValueError("final_demand length must match technical_coefficients shape")
        if len(self.sector_names) != n:
            raise ValueError("sector_names length must match technical_coefficients shape")
        if self.value_added and len(self.value_added) != n:
            raise ValueError("value_added length must match technical_coefficients shape")
        return self


class GraphEdge(KernelModel):
    """Represent one directed weighted edge in a network contract payload."""

    src_id: str = Field(..., min_length=1, max_length=128)
    dst_id: str = Field(..., min_length=1, max_length=128)
    weight: float = 1.0


class GraphBipartiteEdge(KernelModel):
    """Represent one treatment-to-outcome edge for bipartite exposure graphs."""

    treatment_node_id: str = Field(..., min_length=1, max_length=128)
    outcome_node_id: str = Field(..., min_length=1, max_length=128)


class GraphArtifacts(KernelModel):
    """Canonical multiplex graph payload used by network-oriented compilers.

    Stores node ids, per-layer edges, optional coordinates and clusters, and a
    dense index map so contract compilers can materialize adjacency structures
    reproducibly.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_id: str = Field(..., pattern=ID_PATTERN)
    node_ids: list[str] = Field(..., min_length=1)
    layer_edges: dict[MultiplexGraphLayerId, list[GraphEdge]] = Field(default_factory=dict)
    node_features: dict[str, dict[str, float]] = Field(default_factory=dict)
    node_states: dict[str, float] = Field(default_factory=dict)
    cluster_ids: dict[str, int] = Field(default_factory=dict)
    coordinates: dict[str, tuple[float, ...]] = Field(default_factory=dict)
    bipartite_edges: list[GraphBipartiteEdge] = Field(default_factory=list)
    index_map: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_graph(self) -> GraphArtifacts:
        ensure_unique_ids(self.node_ids, key_fn=lambda item: item, label="node_ids")
        unknown_nodes: set[str] = set()
        node_set = set(self.node_ids)
        for edges in self.layer_edges.values():
            for edge in edges:
                if edge.src_id not in node_set:
                    unknown_nodes.add(edge.src_id)
                if edge.dst_id not in node_set:
                    unknown_nodes.add(edge.dst_id)
        for edge in self.bipartite_edges:
            if edge.treatment_node_id not in node_set:
                unknown_nodes.add(edge.treatment_node_id)
            if edge.outcome_node_id not in node_set:
                unknown_nodes.add(edge.outcome_node_id)
        if unknown_nodes:
            raise ValueError(f"graph references unknown node ids: {sorted(unknown_nodes)}")
        if self.index_map:
            if set(self.index_map) != node_set:
                raise ValueError("index_map keys must match node_ids")
            if sorted(self.index_map.values()) != list(range(len(self.node_ids))):
                raise ValueError("index_map values must be a dense permutation starting at 0")
        return self


class FirmEventRecord(KernelModel):
    """Store one firm entry/exit or censoring event used by survival compilers."""

    firm_id: str = Field(..., min_length=1, max_length=128)
    entry_date: date
    exit_date: date | None = None
    censor_date: date | None = None
    event_type: str = Field(default="exit", min_length=1, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_event(self) -> FirmEventRecord:
        if self.exit_date is None and self.censor_date is None:
            raise ValueError("either exit_date or censor_date is required")
        end_date = self.exit_date or self.censor_date
        if end_date is not None and end_date < self.entry_date:
            raise ValueError("event/censor date must be >= entry_date")
        return self


class FirmEvents(KernelModel):
    """Observed firm lifecycle events used by survival compilers."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    event_set_id: str = Field(..., pattern=ID_PATTERN)
    records: list[FirmEventRecord] = Field(..., min_length=1)


class FirmPanelRow(KernelModel):
    """Store one firm-period metric row for panel and econometric compilers."""

    firm_id: str = Field(..., min_length=1, max_length=128)
    period_start: date
    period_end: date
    metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_row(self) -> FirmPanelRow:
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self


class FirmPanels(KernelModel):
    """Panel of firm-level metrics aligned by period."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    panel_id: str = Field(..., pattern=ID_PATTERN)
    rows: list[FirmPanelRow] = Field(..., min_length=1)


class RegionSectorFlowRow(KernelModel):
    """Store one inter-region/inter-sector flow used to assemble Leontief matrices."""

    from_region_code: str = Field(..., min_length=1, max_length=32)
    from_sector_id: str = Field(..., min_length=1, max_length=64)
    to_region_code: str = Field(..., min_length=1, max_length=32)
    to_sector_id: str = Field(..., min_length=1, max_length=64)
    technical_coefficient: float = 0.0
    final_demand: float = 0.0
    value_added: float = 0.0
    period_start: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegionSectorPanels(KernelModel):
    """Region-sector flow panel used to build Leontief IO bundles."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    panel_id: str = Field(..., pattern=ID_PATTERN)
    rows: list[RegionSectorFlowRow] = Field(..., min_length=1)


class ProxyMap(KernelModel):
    """Mapping from latent treatment concepts to observed proxy variables."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    proxy_map_id: str = Field(..., pattern=ID_PATTERN)
    mapping: dict[str, str] = Field(..., min_length=1)
    measurement_model: Literal["known", "estimated", "unknown"] = "unknown"
    graph: CausalGraphModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_proxy_map(self) -> ProxyMap:
        ensure_unique_ids(
            self.mapping.values(),
            key_fn=lambda value: value,
            label="proxy_map.mapping value",
        )
        return self


class SurveyMicroDataCompileSpec(KernelModel):
    """Declare which household metrics become survey-microdata fields."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    income_metric_id: str = Field(..., min_length=1, max_length=120)
    weight_metric_id: str = Field(..., min_length=1, max_length=120)
    feature_metric_ids: list[str] = Field(default_factory=list)
    entity_scope: EntityScope = EntityScope.HOUSEHOLD
    reference_period: date | None = None


class NetworkContractCompileSpec(KernelModel):
    """Configure graph-layer ordering and dense/sparse materialization for network bundles."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    primary_layer: MultiplexGraphLayerId | None = None
    layer_order: list[MultiplexGraphLayerId] = Field(default_factory=list)
    node_feature_names: list[str] = Field(default_factory=list)
    dense_max_bytes: int = Field(default=32_000_000, ge=1)
    low_rank_rank: int | None = Field(default=None, ge=1)
    materialize_node_ids: list[str] = Field(default_factory=list)


class NetworkCausalCompileSpec(KernelModel):
    """Select outcome/treatment/covariate metrics for interference-aware network causal data."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    outcome_metric_id: str = Field(..., min_length=1, max_length=120)
    treatment_metric_id: str = Field(..., min_length=1, max_length=120)
    covariate_metric_ids: list[str] = Field(default_factory=list)
    reference_period: date | None = None
    treatment_threshold: float = 0.5
    structure_layer: MultiplexGraphLayerId | None = None


class PanelObservationalCompileSpec(KernelModel):
    """Select panel outcome/treatment/covariate metrics for causal panel compilation."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    outcome_metric_id: str = Field(..., min_length=1, max_length=120)
    treatment_metric_id: str = Field(..., min_length=1, max_length=120)
    covariate_metric_ids: list[str] = Field(default_factory=list)
    treatment_threshold: float = 0.5
    explicit_time_treatment: int | None = Field(default=None, ge=0)


class DynamicTreatmentCompileSpec(KernelModel):
    """Select metrics required to compile sequential treatment trajectories."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    outcome_metric_id: str = Field(..., min_length=1, max_length=120)
    treatment_metric_id: str = Field(..., min_length=1, max_length=120)
    covariate_metric_ids: list[str] = Field(..., min_length=1)
    treatment_threshold: float = 0.5
    behavior_policy_prob_metric_id: str | None = Field(None, min_length=1, max_length=120)


class SurvivalCompileSpec(KernelModel):
    """Select feature metrics used to compile survival-analysis tables."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    feature_metric_ids: list[str] = Field(..., min_length=1)


class PanelEconometricCompileSpec(KernelModel):
    """Select dependent, exogenous, and instrument columns for econometric panels."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    dependent_metric_id: str = Field(..., min_length=1, max_length=120)
    exog_metric_ids: list[str] = Field(..., min_length=1)
    instrument_metric_ids: list[str] = Field(default_factory=list)


class BoundsEstimationCompileSpec(KernelModel):
    """Select outcome/treatment and optional IV/selection/proxy channels for bounds input."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    outcome_metric_id: str = Field(..., min_length=1, max_length=120)
    treatment_metric_id: str = Field(..., min_length=1, max_length=120)
    instrument_metric_id: str | None = Field(None, min_length=1, max_length=120)
    selected_metric_id: str | None = Field(None, min_length=1, max_length=120)
    miv_proxy_metric_id: str | None = Field(None, min_length=1, max_length=120)


class ProxyMeasurementCompileSpec(KernelModel):
    """Declare proxy and validation metrics for latent-treatment measurement bundles."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    outcome_metric_id: str = Field(..., min_length=1, max_length=120)
    treatment_proxy_metric_id: str = Field(..., min_length=1, max_length=120)
    covariate_metric_ids: list[str] = Field(default_factory=list)
    validation_true_treatment_metric_id: str | None = Field(None, min_length=1, max_length=120)
    validation_proxy_metric_id: str | None = Field(None, min_length=1, max_length=120)
    error_variance: float | None = None
    error_rate_bound: float | None = None


class HistoricalValidationCompileSpec(KernelModel):
    """Specify holdout horizons and metric ids for backtest-plan compilation."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    metric_ids: list[str] = Field(..., min_length=1)
    intervention_date: str = Field(..., min_length=1, max_length=64)
    pre_intervention_periods: int = Field(..., ge=1)
    post_intervention_periods: int = Field(..., ge=1)
    historical_data_ref: str | None = Field(None, max_length=255)
    historical_data_path: str | None = Field(None, max_length=255)
    prediction_source: PredictionSource = PredictionSource.NAIVE
    jurisdiction: str = Field(default="", max_length=64)


class SpecificationCurveSourceSpec(KernelModel):
    """Describe one source/family combination to include in a specification curve."""

    source_combination_id: str = Field(..., min_length=1, max_length=120)
    included_metric_ids: list[str] = Field(..., min_length=1)
    included_families: list[ObservationFamily] = Field(default_factory=list)
    sensitivity_axes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SpecificationCurveCompileSpec(KernelModel):
    """Wrap the source combinations used to compile specification-curve inputs."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    source_specifications: list[SpecificationCurveSourceSpec] = Field(..., min_length=1)


class LeontiefIOCompileSpec(KernelModel):
    """Tag a region-sector panel compilation request for Leontief IO output."""

    spec_id: str = Field(..., pattern=ID_PATTERN)
    reference_period: date | None = None


@dataclass(frozen=True)
class CompiledObservationArtifact:
    """Bundle one compiler output contract together with its persisted manifest."""

    compiler_id: str
    artifact_key: str
    contract: BaseModel | dict[str, Any]
    bundle: KernelModel


@dataclass(frozen=True)
class HistoricalValidationCompilation:
    """Pair a generated backtest plan with the payload snapshot used to run it."""

    plans: list[HistoricalValidationPlan]
    historical_payloads: dict[str, dict[str, Any]]
    bundle: BacktestPlanBundle


@dataclass(frozen=True)
class ObservationContractSuiteResult:
    """Collect all compiled artifacts plus the observation-to-contract manifest."""

    artifacts: dict[str, CompiledObservationArtifact]
    backtest: HistoricalValidationCompilation | None
    manifest: ObservationToContractManifest


def _entity_locator(record: ObservationRecord) -> str:
    if record.entity_scope in {EntityScope.AGENT, EntityScope.FIRM, EntityScope.HOUSEHOLD}:
        if record.entity_id:
            return record.entity_id
    if record.entity_scope in {EntityScope.CELL, EntityScope.HOUSEHOLD_CELL}:
        if record.entity_id:
            return record.entity_id
        if record.cell_id:
            return record.cell_id
    if record.entity_scope == EntityScope.REGION and record.region_code:
        return record.region_code
    if record.entity_scope == EntityScope.SECTOR and record.sector_id:
        return record.sector_id
    return "global"


def _lineage_from_panel(panel: ObservationPanel) -> list[BundleLineageRef]:
    return [
        BundleLineageRef(
            source_artifact=f"{panel.panel_id}.observation_panel",
            source_family=panel.family,
        )
    ]


def _sorted_periods(
    records: Sequence[ObservationRecord], *, metric_ids: Sequence[str] | None = None
) -> list[date]:
    allowed = set(metric_ids or [])
    values = {
        record.period_start for record in records if not allowed or record.metric_id in allowed
    }
    return sorted(values)


def _panel_units(
    panel: ObservationPanel,
    *,
    entity_scope: EntityScope | None = None,
    metric_ids: Sequence[str] | None = None,
) -> list[str]:
    allowed = set(metric_ids or [])
    units = {
        _entity_locator(record)
        for record in panel.records
        if (entity_scope is None or record.entity_scope == entity_scope)
        and (not allowed or record.metric_id in allowed)
    }
    return sorted(units)


def _select_reference_period(
    panel: ObservationPanel,
    *,
    metric_id: str,
    reference_period: date | None,
    compiler_id: str,
) -> date:
    if reference_period is not None:
        return reference_period
    periods = _sorted_periods(panel.records, metric_ids=[metric_id])
    if not periods:
        raise ObservationContractCompileError(
            f"missing observations for metric '{metric_id}'",
            compiler_id=compiler_id,
            field_name=metric_id,
        )
    return periods[-1]


def _period_metric_map(
    panel: ObservationPanel,
    *,
    metric_id: str,
    period_start: date,
    units: Sequence[str],
    compiler_id: str,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for record in panel.records:
        if record.metric_id != metric_id or record.period_start != period_start:
            continue
        values[_entity_locator(record)] = float(record.observed_value)
    missing = sorted(set(units) - set(values))
    if missing:
        raise ObservationContractCompileError(
            f"missing metric '{metric_id}' for units {missing}",
            compiler_id=compiler_id,
            field_name=metric_id,
        )
    return values


def _panel_matrix(
    panel: ObservationPanel,
    *,
    metric_id: str,
    units: Sequence[str],
    periods: Sequence[date],
    compiler_id: str,
) -> np.ndarray:
    row_index = {unit_id: idx for idx, unit_id in enumerate(units)}
    col_index = {period: idx for idx, period in enumerate(periods)}
    matrix = np.full((len(units), len(periods)), np.nan, dtype=float)
    for record in panel.records:
        if record.metric_id != metric_id:
            continue
        unit_id = _entity_locator(record)
        if unit_id not in row_index or record.period_start not in col_index:
            continue
        matrix[row_index[unit_id], col_index[record.period_start]] = float(record.observed_value)
    if np.isnan(matrix).any():
        missing = np.argwhere(np.isnan(matrix))
        raise ObservationContractCompileError(
            f"incomplete panel for metric '{metric_id}' at {missing.tolist()}",
            compiler_id=compiler_id,
            field_name=metric_id,
        )
    return matrix


def _latest_metric_vector(
    panel: ObservationPanel,
    *,
    metric_id: str,
    units: Sequence[str],
    reference_period: date | None,
    compiler_id: str,
) -> tuple[np.ndarray, date]:
    period = _select_reference_period(
        panel,
        metric_id=metric_id,
        reference_period=reference_period,
        compiler_id=compiler_id,
    )
    mapping = _period_metric_map(
        panel,
        metric_id=metric_id,
        period_start=period,
        units=units,
        compiler_id=compiler_id,
    )
    return np.asarray([mapping[unit_id] for unit_id in units], dtype=float), period


def _baseline_covariates(
    panel: ObservationPanel,
    *,
    metric_ids: Sequence[str],
    units: Sequence[str],
    baseline_period: date,
    compiler_id: str,
) -> np.ndarray | None:
    if not metric_ids:
        return None
    columns = []
    for metric_id in metric_ids:
        mapping = _period_metric_map(
            panel,
            metric_id=metric_id,
            period_start=baseline_period,
            units=units,
            compiler_id=compiler_id,
        )
        columns.append([mapping[unit_id] for unit_id in units])
    return np.asarray(columns, dtype=float).T


def _finite_list(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values]


def _json_payload_value(value: Any) -> Any:
    """Normalize one neutral method payload value without importing its consumer DTO."""

    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_payload_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_payload_value(item) for item in value]
    if isinstance(value, list):
        return [_json_payload_value(item) for item in value]
    return value


def _method_contract_payload(**values: Any) -> dict[str, Any]:
    """Return a deterministic JSON payload for upper-layer method materialization."""

    return {key: _json_payload_value(value) for key, value in values.items()}


class SparseDenseBridge:
    """Utility for converting sparse multiplex graphs into dense tensors.

    The bridge guards materialization by byte budget and can emit either a
    single adjacency matrix, a multiplex tensor, or low-rank factors for
    memory-constrained downstream contracts.
    """

    def estimate_dense_bytes(self, *, n_nodes: int, n_layers: int = 1) -> int:
        return int(n_layers * n_nodes * n_nodes * np.dtype(np.float64).itemsize)

    def guard_materialization(self, *, n_nodes: int, n_layers: int, max_bytes: int) -> None:
        required = self.estimate_dense_bytes(n_nodes=n_nodes, n_layers=n_layers)
        if required > max_bytes:
            raise MemoryError(
                f"dense materialization would require {required} bytes, limit is {max_bytes}"
            )

    def node_order(
        self,
        graph: GraphArtifacts,
        *,
        materialize_node_ids: Sequence[str] | None = None,
    ) -> list[str]:
        if materialize_node_ids:
            requested = list(materialize_node_ids)
            missing = sorted(set(requested) - set(graph.node_ids))
            if missing:
                raise ValueError(f"requested node ids not in graph: {missing}")
            return requested
        if graph.index_map:
            return [
                node_id for node_id, _ in sorted(graph.index_map.items(), key=lambda item: item[1])
            ]
        return sorted(graph.node_ids)

    def materialize_layer(
        self,
        graph: GraphArtifacts,
        *,
        layer_id: MultiplexGraphLayerId,
        materialize_node_ids: Sequence[str] | None = None,
        max_bytes: int = 32_000_000,
    ) -> tuple[np.ndarray, list[str], dict[str, int]]:
        node_order = self.node_order(graph, materialize_node_ids=materialize_node_ids)
        index_map = {node_id: idx for idx, node_id in enumerate(node_order)}
        self.guard_materialization(n_nodes=len(node_order), n_layers=1, max_bytes=max_bytes)
        adjacency = np.zeros((len(node_order), len(node_order)), dtype=float)
        for edge in graph.layer_edges.get(layer_id, []):
            if edge.src_id in index_map and edge.dst_id in index_map:
                adjacency[index_map[edge.src_id], index_map[edge.dst_id]] = float(edge.weight)
        return adjacency, node_order, index_map

    def materialize_multiplex(
        self,
        graph: GraphArtifacts,
        *,
        layer_order: Sequence[MultiplexGraphLayerId],
        materialize_node_ids: Sequence[str] | None = None,
        max_bytes: int = 32_000_000,
    ) -> tuple[np.ndarray, list[str], dict[str, int]]:
        node_order = self.node_order(graph, materialize_node_ids=materialize_node_ids)
        index_map = {node_id: idx for idx, node_id in enumerate(node_order)}
        self.guard_materialization(
            n_nodes=len(node_order),
            n_layers=len(layer_order),
            max_bytes=max_bytes,
        )
        layers = np.zeros((len(layer_order), len(node_order), len(node_order)), dtype=float)
        for layer_idx, layer_id in enumerate(layer_order):
            for edge in graph.layer_edges.get(layer_id, []):
                if edge.src_id in index_map and edge.dst_id in index_map:
                    layers[layer_idx, index_map[edge.src_id], index_map[edge.dst_id]] = float(
                        edge.weight
                    )
        return layers, node_order, index_map

    def low_rank_factors(self, adjacency: np.ndarray, *, rank: int) -> dict[str, list[list[float]]]:
        u, singular_values, vt = np.linalg.svd(adjacency, full_matrices=False)
        rank = min(rank, singular_values.shape[0])
        u_r = u[:, :rank] * singular_values[:rank]
        v_r = vt[:rank, :]
        return {
            "left": u_r.tolist(),
            "right": v_r.tolist(),
        }


class ObservationCompilerContext:
    """Shared registries and utilities used by observation contract compilers."""

    def __init__(
        self,
        *,
        measurement_registry: MeasurementRegistry | None = None,
        identification_router: IdentificationModeRouter | None = None,
        schema_regime_registry: SchemaRegimeRegistry | None = None,
        splitter: Any | None = None,
    ) -> None:
        self.measurement_registry = measurement_registry or MeasurementRegistry.default()
        self.identification_router = identification_router or IdentificationModeRouter(
            measurement_registry=self.measurement_registry
        )
        self.schema_regime_registry = schema_regime_registry or SchemaRegimeRegistry.default()
        self.splitter = splitter
        self.bridge = SparseDenseBridge()


class SurveyMicroDataCompiler:
    """Compile household survey panels into ``SurveyMicroData`` and a microsim-ready bundle.

    Downstream Foundry microsimulation runners consume the compiled contract
    after the bundle is persisted. Callers must provide one unit-aligned panel
    period with income, weights, and every requested feature metric present for
    each retained survey unit.
    """

    compiler_id = "observation.survey_microdata"

    def __init__(self, context: ObservationCompilerContext | None = None) -> None:
        self.context = context or ObservationCompilerContext()

    def compile(
        self,
        panel: ObservationPanel,
        spec: SurveyMicroDataCompileSpec,
    ) -> CompiledObservationArtifact:
        units = _panel_units(
            panel,
            entity_scope=spec.entity_scope,
            metric_ids=[spec.income_metric_id, spec.weight_metric_id, *spec.feature_metric_ids],
        )
        if not units:
            raise ObservationContractCompileError(
                "no survey units found",
                compiler_id=self.compiler_id,
            )
        income, period = _latest_metric_vector(
            panel,
            metric_id=spec.income_metric_id,
            units=units,
            reference_period=spec.reference_period,
            compiler_id=self.compiler_id,
        )
        weights_map = _period_metric_map(
            panel,
            metric_id=spec.weight_metric_id,
            period_start=period,
            units=units,
            compiler_id=self.compiler_id,
        )
        feature_matrix = None
        if spec.feature_metric_ids:
            feature_columns = []
            for metric_id in spec.feature_metric_ids:
                mapping = _period_metric_map(
                    panel,
                    metric_id=metric_id,
                    period_start=period,
                    units=units,
                    compiler_id=self.compiler_id,
                )
                feature_columns.append([mapping[unit_id] for unit_id in units])
            feature_matrix = np.asarray(feature_columns, dtype=float).T
        contract = _method_contract_payload(
            market_income=income,
            weights=np.asarray([weights_map[unit_id] for unit_id in units], dtype=float),
            household_ids=np.asarray(units),
            features=feature_matrix,
            feature_names=list(spec.feature_metric_ids) or None,
            period_id=None,
            cohort_id=None,
            region_id=None,
            policy_id=None,
            reform_id=None,
            instrument_z=None,
            schedule_segments=None,
            kink_points=None,
            notch_points=None,
            income_repeat_measure=None,
            taxrate_repeat_measure=None,
            microsim_calibration_report=build_microsim_calibration_report(
                compatibility_status="compatible",
                metadata={
                    "source": "observation.survey_microdata",
                    "compiler_id": self.compiler_id,
                },
            ).model_dump(mode="json"),
            microsim_calibration_report_ref=None,
            sample_design={},
            metadata={
                "data_shape": "survey_microdata",
                "panel_id": panel.panel_id,
                "period_start": period.isoformat(),
                "family": panel.family.value,
            },
        )
        bundle = MicrosimSurveyContractBundle(
            contract_target=SURVEY_MICRODATA_TARGET,
            required_fields=["market_income", "weights", "household_ids"],
            observation_families=[panel.family],
            contract_payload=contract,
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="survey_micro_data",
            contract=contract,
            bundle=bundle,
        )


class NetworkContractCompiler:
    """Compile ``GraphArtifacts`` into network-analysis bundles for Foundry methods.

    Downstream network runners consume the emitted ``NetworkData`` and
    ``MultiplexNetworkData`` payloads. Callers must supply a graph whose nodes,
    layers, optional features, and requested materialization settings can all
    be resolved consistently under the configured size limits.
    """

    compiler_id = "observation.network_contract"

    def __init__(self, context: ObservationCompilerContext | None = None) -> None:
        self.context = context or ObservationCompilerContext()

    def compile(
        self,
        graph: GraphArtifacts,
        spec: NetworkContractCompileSpec,
    ) -> dict[str, CompiledObservationArtifact]:
        layer_order = list(
            spec.layer_order or sorted(graph.layer_edges, key=lambda layer: layer.value)
        )
        if not layer_order:
            raise ObservationContractCompileError(
                "graph has no layers to compile",
                compiler_id=self.compiler_id,
            )
        node_features = self._node_features(graph, spec)
        node_states = self._node_states(graph)
        primary_layer = spec.primary_layer or layer_order[0]
        adjacency, node_order, index_map = self.context.bridge.materialize_layer(
            graph,
            layer_id=primary_layer,
            materialize_node_ids=spec.materialize_node_ids,
            max_bytes=spec.dense_max_bytes,
        )
        network_contract = _method_contract_payload(
            adjacency=adjacency,
            node_features=node_features,
            node_states=node_states,
            node_ids=node_order,
            metadata={
                "graph_artifact_id": graph.artifact_id,
                "primary_layer": primary_layer.value,
                "node_index_map": index_map,
            },
        )
        multiplex_layers, multiplex_order, multiplex_index_map = (
            self.context.bridge.materialize_multiplex(
                graph,
                layer_order=layer_order,
                materialize_node_ids=spec.materialize_node_ids,
                max_bytes=spec.dense_max_bytes,
            )
        )
        multiplex_contract = _method_contract_payload(
            adjacency_layers=multiplex_layers,
            node_features=node_features,
            node_ids=multiplex_order,
            metadata={
                "graph_artifact_id": graph.artifact_id,
                "layer_order": [layer.value for layer in layer_order],
                "node_index_map": multiplex_index_map,
            },
        )
        low_rank: dict[str, dict[str, list[list[float]]]] = {}
        if spec.low_rank_rank is not None:
            for layer_id in layer_order:
                dense_layer, _, _ = self.context.bridge.materialize_layer(
                    graph,
                    layer_id=layer_id,
                    materialize_node_ids=spec.materialize_node_ids,
                    max_bytes=spec.dense_max_bytes,
                )
                low_rank[layer_id.value] = self.context.bridge.low_rank_factors(
                    dense_layer,
                    rank=spec.low_rank_rank,
                )
        sparse_edges = {
            layer_id.value: [
                edge.model_dump(mode="json") for edge in graph.layer_edges.get(layer_id, [])
            ]
            for layer_id in layer_order
        }
        bundle = NetworkContractBundle(
            contract_targets=[
                NETWORK_ANALYSIS_TARGET,
                MULTIPLEX_NETWORK_TARGET,
            ],
            graph_layers=list(layer_order),
            source_artifacts=[graph.artifact_id],
            node_order=node_order,
            node_index_map=index_map,
            sparse_edges=sparse_edges,
            slice_settings={"materialize_node_ids": list(spec.materialize_node_ids)},
            low_rank_factors=low_rank,
            contract_payloads={
                "network_data": network_contract,
                "multiplex_network_data": multiplex_contract,
            },
        )
        return {
            "network_data": CompiledObservationArtifact(
                compiler_id=self.compiler_id,
                artifact_key="network_data",
                contract=network_contract,
                bundle=bundle,
            ),
            "multiplex_network_data": CompiledObservationArtifact(
                compiler_id=self.compiler_id,
                artifact_key="multiplex_network_data",
                contract=multiplex_contract,
                bundle=bundle,
            ),
        }

    def _node_features(
        self, graph: GraphArtifacts, spec: NetworkContractCompileSpec
    ) -> np.ndarray | None:
        feature_names = list(spec.node_feature_names)
        if not feature_names:
            union_names = {name for values in graph.node_features.values() for name in values}
            feature_names = sorted(union_names)
        if not feature_names:
            return None
        ordered_nodes = self.context.bridge.node_order(
            graph,
            materialize_node_ids=spec.materialize_node_ids,
        )
        matrix = np.zeros((len(ordered_nodes), len(feature_names)), dtype=float)
        for row_idx, node_id in enumerate(ordered_nodes):
            values = graph.node_features.get(node_id, {})
            for col_idx, name in enumerate(feature_names):
                matrix[row_idx, col_idx] = float(values.get(name, 0.0))
        return matrix

    def _node_states(self, graph: GraphArtifacts) -> np.ndarray | None:
        if not graph.node_states:
            return None
        ordered_nodes = self.context.bridge.node_order(graph)
        return np.asarray(
            [graph.node_states.get(node_id, 0.0) for node_id in ordered_nodes], dtype=float
        )


class NetworkCausalDataCompiler:
    """Compile a panel plus graph into ``NetworkCausalData`` for interference-aware estimators.

    Downstream network-causal runners consume the adjacency, treatments, and
    covariates captured in the emitted bundle. Callers must align panel unit ids
    with graph nodes and provide outcome/treatment values for every retained
    node at the chosen reference period.
    """

    compiler_id = "observation.network_causal"

    def __init__(self, context: ObservationCompilerContext | None = None) -> None:
        self.context = context or ObservationCompilerContext()

    def compile(
        self,
        panel: ObservationPanel,
        graph: GraphArtifacts,
        spec: NetworkCausalCompileSpec,
    ) -> CompiledObservationArtifact:
        node_order = self.context.bridge.node_order(graph)
        outcome, reference_period = _latest_metric_vector(
            panel,
            metric_id=spec.outcome_metric_id,
            units=node_order,
            reference_period=spec.reference_period,
            compiler_id=self.compiler_id,
        )
        treatment_map = _period_metric_map(
            panel,
            metric_id=spec.treatment_metric_id,
            period_start=reference_period,
            units=node_order,
            compiler_id=self.compiler_id,
        )
        treatment = np.asarray(
            [
                1.0 if treatment_map[node_id] >= spec.treatment_threshold else 0.0
                for node_id in node_order
            ],
            dtype=float,
        )
        covariates = _baseline_covariates(
            panel,
            metric_ids=spec.covariate_metric_ids,
            units=node_order,
            baseline_period=reference_period,
            compiler_id=self.compiler_id,
        )
        chosen_layer = (
            spec.structure_layer or sorted(graph.layer_edges, key=lambda item: item.value)[0]
        )
        adjacency, _, index_map = self.context.bridge.materialize_layer(
            graph,
            layer_id=chosen_layer,
            max_bytes=32_000_000,
        )
        cluster_id = None
        if graph.cluster_ids:
            cluster_id = np.asarray(
                [graph.cluster_ids.get(node_id, -1) for node_id in node_order], dtype=int
            )
        coordinates = None
        if graph.coordinates:
            coordinates = np.asarray(
                [graph.coordinates[node_id] for node_id in node_order], dtype=float
            )
        bipartite_edges = None
        if graph.bipartite_edges:
            bipartite_edges = np.asarray(
                [
                    [index_map[edge.treatment_node_id], index_map[edge.outcome_node_id]]
                    for edge in graph.bipartite_edges
                ],
                dtype=int,
            )
        contract = _method_contract_payload(
            outcome=outcome,
            treatment=treatment,
            covariates=covariates,
            adjacency_matrix=adjacency,
            cluster_id=cluster_id,
            coordinates=coordinates,
            treatment_unit_ids=None,
            bipartite_edges=bipartite_edges,
            metadata={
                "panel_id": panel.panel_id,
                "graph_artifact_id": graph.artifact_id,
                "reference_period": reference_period.isoformat(),
                "structure_layer": chosen_layer.value,
                "node_index_map": index_map,
            },
        )
        bundle = NetworkCausalContractBundle(
            contract_target=NETWORK_DATA_TARGET,
            supported_layers=[chosen_layer],
            contract_payload=contract,
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="network_causal_data",
            contract=contract,
            bundle=bundle,
        )


class PanelObservationalCompiler:
    """Compile longitudinal panels into ``PanelObservationalData`` for causal panel methods.

    Downstream panel-effect runners consume the contract payload plus the
    tabular manifest rows. Callers must provide at least two units and two
    periods, with outcome, treatment, and requested covariates available on a
    common panel grid.
    """

    compiler_id = "observation.panel_observational"

    def __init__(self, context: ObservationCompilerContext | None = None) -> None:
        self.context = context or ObservationCompilerContext()

    def compile(
        self,
        panel: ObservationPanel,
        spec: PanelObservationalCompileSpec,
    ) -> CompiledObservationArtifact:
        units = _panel_units(
            panel,
            metric_ids=[
                spec.outcome_metric_id,
                spec.treatment_metric_id,
                *spec.covariate_metric_ids,
            ],
        )
        periods = _sorted_periods(
            panel.records,
            metric_ids=[spec.outcome_metric_id, spec.treatment_metric_id],
        )
        if len(units) < 2 or len(periods) < 2:
            raise ObservationContractCompileError(
                "panel compilation requires at least 2 units and 2 periods",
                compiler_id=self.compiler_id,
            )
        outcome = _panel_matrix(
            panel,
            metric_id=spec.outcome_metric_id,
            units=units,
            periods=periods,
            compiler_id=self.compiler_id,
        )
        treatment_panel = _panel_matrix(
            panel,
            metric_id=spec.treatment_metric_id,
            units=units,
            periods=periods,
            compiler_id=self.compiler_id,
        )
        treated_panel = treatment_panel >= spec.treatment_threshold
        if spec.explicit_time_treatment is not None:
            time_treatment = spec.explicit_time_treatment
        else:
            treated_periods = np.where(treated_panel.any(axis=0))[0]
            if treated_periods.size == 0:
                raise ObservationContractCompileError(
                    "treatment metric never crosses threshold",
                    compiler_id=self.compiler_id,
                    field_name=spec.treatment_metric_id,
                )
            time_treatment = int(treated_periods[0])
        treatment = treated_panel[:, time_treatment:].any(axis=1).astype(int)
        treatment_timing = np.asarray(
            [int(np.where(row)[0][0]) if row.any() else len(periods) for row in treated_panel],
            dtype=int,
        )
        baseline_period = periods[max(0, min(time_treatment - 1, len(periods) - 1))]
        covariates = _baseline_covariates(
            panel,
            metric_ids=spec.covariate_metric_ids,
            units=units,
            baseline_period=baseline_period,
            compiler_id=self.compiler_id,
        )
        contract = _method_contract_payload(
            outcome=outcome,
            treatment=treatment,
            time_treatment=time_treatment,
            covariates=covariates,
            treatment_timing=treatment_timing,
            unit_ids=np.asarray(units),
            time_index=np.asarray([period.isoformat() for period in periods]),
            metadata={
                "data_shape": "panel",
                "panel_id": panel.panel_id,
                "family": panel.family.value,
                "baseline_period": baseline_period.isoformat(),
            },
        )
        rows = self._rows(
            units=units,
            periods=periods,
            outcome=outcome,
            treated_panel=treated_panel.astype(int),
            covariate_metric_ids=spec.covariate_metric_ids,
            panel=panel,
        )
        bundle = CausalPanelBundleManifest(
            contract_target=PANEL_OBSERVATIONAL_TARGET,
            required_columns=[
                RequiredColumnSpec(name="unit_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="treatment", dtype="int"),
                RequiredColumnSpec(name="outcome", dtype="float"),
            ],
            lineage=_lineage_from_panel(panel),
            table_rows=rows,
            contract_payload=contract,
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="panel_observational_data",
            contract=contract,
            bundle=bundle,
        )

    def _rows(
        self,
        *,
        units: Sequence[str],
        periods: Sequence[date],
        outcome: np.ndarray,
        treated_panel: np.ndarray,
        covariate_metric_ids: Sequence[str],
        panel: ObservationPanel,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        covariate_values: dict[tuple[str, str], dict[str, float]] = {}
        for metric_id in covariate_metric_ids:
            matrix = _panel_matrix(
                panel,
                metric_id=metric_id,
                units=units,
                periods=periods,
                compiler_id=self.compiler_id,
            )
            for unit_idx, unit_id in enumerate(units):
                for period_idx, period in enumerate(periods):
                    covariate_values.setdefault((unit_id, period.isoformat()), {})[metric_id] = (
                        float(matrix[unit_idx, period_idx])
                    )
        for unit_idx, unit_id in enumerate(units):
            for period_idx, period in enumerate(periods):
                row = {
                    "unit_id": unit_id,
                    "period_id": period.isoformat(),
                    "treatment": int(treated_panel[unit_idx, period_idx]),
                    "outcome": float(outcome[unit_idx, period_idx]),
                }
                row.update(covariate_values.get((unit_id, period.isoformat()), {}))
                rows.append(row)
        return rows


class DynamicTreatmentCompiler:
    """Compile sequential treatment trajectories for dynamic-regime execution.

    Downstream dynamic-treatment runners consume the emitted
    ``DynamicTreatmentData`` bundle after readiness gates approve it. Callers
    must provide a common unit-by-period panel with every covariate layer
    present and a treatment series that can be thresholded into a sequence.
    """

    compiler_id = "observation.dynamic_treatment"

    def __init__(self, context: ObservationCompilerContext | None = None) -> None:
        self.context = context or ObservationCompilerContext()

    def compile(
        self,
        panel: ObservationPanel,
        spec: DynamicTreatmentCompileSpec,
    ) -> CompiledObservationArtifact:
        units = _panel_units(
            panel,
            metric_ids=[
                spec.outcome_metric_id,
                spec.treatment_metric_id,
                *spec.covariate_metric_ids,
            ],
        )
        periods = _sorted_periods(
            panel.records,
            metric_ids=[
                spec.outcome_metric_id,
                spec.treatment_metric_id,
                *spec.covariate_metric_ids,
            ],
        )
        outcome_matrix = _panel_matrix(
            panel,
            metric_id=spec.outcome_metric_id,
            units=units,
            periods=periods,
            compiler_id=self.compiler_id,
        )
        treatment_values = _panel_matrix(
            panel,
            metric_id=spec.treatment_metric_id,
            units=units,
            periods=periods,
            compiler_id=self.compiler_id,
        )
        treatment_sequence = (treatment_values >= spec.treatment_threshold).astype(int)
        covariate_layers = []
        for metric_id in spec.covariate_metric_ids:
            covariate_layers.append(
                _panel_matrix(
                    panel,
                    metric_id=metric_id,
                    units=units,
                    periods=periods,
                    compiler_id=self.compiler_id,
                )
            )
        covariate_sequence = np.stack(covariate_layers, axis=2)
        behavior_probs = None
        if spec.behavior_policy_prob_metric_id is not None:
            behavior_probs = _panel_matrix(
                panel,
                metric_id=spec.behavior_policy_prob_metric_id,
                units=units,
                periods=periods,
                compiler_id=self.compiler_id,
            )
            behavior_probs = np.clip(behavior_probs, 1e-3, 1.0 - 1e-3)
        contract = _method_contract_payload(
            outcome=outcome_matrix[:, -1],
            treatment_sequence=treatment_sequence,
            covariate_sequence=covariate_sequence,
            time_ids=np.asarray([period.isoformat() for period in periods]),
            variable_names=list(spec.covariate_metric_ids),
            treatment_name="A",
            outcome_name="Y",
            behavior_policy_probs=behavior_probs,
            metadata={
                "data_shape": "dynamic_treatment",
                "panel_id": panel.panel_id,
                "family": panel.family.value,
            },
        )
        bundle = DTRTreatmentSequenceBundleManifest(
            contract_target=DYNAMIC_TREATMENT_TARGET,
            required_arrays=[
                RequiredArraySpec(name="outcome", axes=["unit"], dtype="float64"),
                RequiredArraySpec(
                    name="treatment_sequence", axes=["unit", "period"], dtype="int64"
                ),
                RequiredArraySpec(
                    name="covariate_sequence", axes=["unit", "period", "covariate"], dtype="float64"
                ),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="unit", description="Treatment unit axis"),
                BundleAxisSemantic(axis="period", description="Temporal intervention axis"),
                BundleAxisSemantic(axis="covariate", description="Time-varying confounder axis"),
            ],
            lineage=_lineage_from_panel(panel),
            contract_payload=contract,
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="dynamic_treatment_data",
            contract=contract,
            bundle=bundle,
        )


class SurvivalDataCompiler:
    """Compile firm event logs and baseline panels into survival-analysis bundles.

    Downstream time-to-event runners consume the feature matrix, durations, and
    event flags carried by ``SurvivalData``. Callers must supply one baseline
    feature row for every firm in the event set plus valid entry/exit or censor
    dates.
    """

    compiler_id = "observation.survival"

    def compile(
        self,
        firm_events: FirmEvents,
        firm_panels: FirmPanels,
        spec: SurvivalCompileSpec,
    ) -> CompiledObservationArtifact:
        features_by_firm = self._baseline_features(firm_panels, spec)
        feature_rows = []
        durations = []
        events = []
        rows = []
        for record in sorted(firm_events.records, key=lambda item: item.firm_id):
            if record.firm_id not in features_by_firm:
                raise ObservationContractCompileError(
                    f"missing baseline firm panel row for firm '{record.firm_id}'",
                    compiler_id=self.compiler_id,
                    field_name=record.firm_id,
                )
            feature_vector = features_by_firm[record.firm_id]
            end_date = record.exit_date or record.censor_date
            if end_date is None:
                raise ObservationContractCompileError(
                    "firm event record must carry exit_date or censor_date",
                    compiler_id=self.compiler_id,
                    field_name=record.firm_id,
                )
            duration = float((end_date - record.entry_date).days)
            feature_rows.append(feature_vector)
            durations.append(max(duration, 1.0))
            events.append(1 if record.exit_date is not None else 0)
            row = {
                "firm_id": record.firm_id,
                "duration": max(duration, 1.0),
                "event": 1 if record.exit_date is not None else 0,
            }
            for metric_name, metric_value in zip(
                spec.feature_metric_ids, feature_vector, strict=False
            ):
                row[metric_name] = metric_value
            rows.append(row)
        contract = _method_contract_payload(
            features=np.asarray(feature_rows, dtype=float),
            durations=np.asarray(durations, dtype=float),
            events=np.asarray(events, dtype=int),
            feature_names=list(spec.feature_metric_ids),
            metadata={"event_set_id": firm_events.event_set_id, "panel_id": firm_panels.panel_id},
        )
        bundle = SurvivalDataBundleManifest(
            contract_target=SURVIVAL_DATA_TARGET,
            required_columns=[
                RequiredColumnSpec(name="firm_id", dtype="string"),
                RequiredColumnSpec(name="duration", dtype="float"),
                RequiredColumnSpec(name="event", dtype="int"),
            ],
            lineage=[
                BundleLineageRef(source_artifact=f"{firm_events.event_set_id}.events"),
                BundleLineageRef(source_artifact=f"{firm_panels.panel_id}.firm_panels"),
            ],
            table_rows=rows,
            contract_payload=contract,
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="survival_data",
            contract=contract,
            bundle=bundle,
        )

    def _baseline_features(
        self,
        firm_panels: FirmPanels,
        spec: SurvivalCompileSpec,
    ) -> dict[str, list[float]]:
        grouped: dict[str, FirmPanelRow] = {}
        for row in sorted(firm_panels.rows, key=lambda item: (item.firm_id, item.period_start)):
            grouped.setdefault(row.firm_id, row)
        output: dict[str, list[float]] = {}
        for firm_id, row in grouped.items():
            output[firm_id] = [
                float(row.metrics[metric_id]) for metric_id in spec.feature_metric_ids
            ]
        return output


class PanelEconometricCompiler:
    """Compile firm-period panels into econometric tables for regression or IV methods.

    Downstream econometric runners consume the emitted ``PanelData`` contract
    and table manifest. Callers must provide a fully populated firm-period
    panel for the dependent, exogenous, and optional instrument metrics because
    missing metric lookups fail compilation.
    """

    compiler_id = "observation.panel_econometric"

    def compile(
        self,
        firm_panels: FirmPanels,
        spec: PanelEconometricCompileSpec,
    ) -> CompiledObservationArtifact:
        rows = sorted(firm_panels.rows, key=lambda item: (item.firm_id, item.period_start))
        dependent = np.asarray([row.metrics[spec.dependent_metric_id] for row in rows], dtype=float)
        exog = np.asarray(
            [[row.metrics[metric_id] for metric_id in spec.exog_metric_ids] for row in rows],
            dtype=float,
        )
        instruments = None
        if spec.instrument_metric_ids:
            instruments = np.asarray(
                [
                    [row.metrics[metric_id] for metric_id in spec.instrument_metric_ids]
                    for row in rows
                ],
                dtype=float,
            )
        contract = _method_contract_payload(
            dependent=dependent,
            exog=exog,
            entity_ids=np.asarray([row.firm_id for row in rows]),
            time_ids=np.asarray([row.period_start.isoformat() for row in rows]),
            instrument_ids=instruments,
            feature_names=list(spec.exog_metric_ids),
            instrument_names=list(spec.instrument_metric_ids) or None,
            metadata={"data_shape": "panel", "panel_id": firm_panels.panel_id},
        )
        bundle_rows = []
        for row in rows:
            payload = {
                "firm_id": row.firm_id,
                "period_id": row.period_start.isoformat(),
                "dependent": float(row.metrics[spec.dependent_metric_id]),
            }
            for metric_id in spec.exog_metric_ids:
                payload[metric_id] = float(row.metrics[metric_id])
            for metric_id in spec.instrument_metric_ids:
                payload[metric_id] = float(row.metrics[metric_id])
            bundle_rows.append(payload)
        bundle = PanelEconometricBundleManifest(
            contract_target=PANEL_ECONOMETRIC_TARGET,
            required_columns=[
                RequiredColumnSpec(name="firm_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="dependent", dtype="float"),
            ],
            lineage=[BundleLineageRef(source_artifact=f"{firm_panels.panel_id}.firm_panels")],
            table_rows=bundle_rows,
            contract_payload=contract,
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="panel_econometric_data",
            contract=contract,
            bundle=bundle,
        )


class BoundsInputCompiler:
    """Compile a panel slice into dense arrays for partial-identification estimators.

    Downstream bounds runners consume the ``BoundsEstimationInput`` payload and
    its channel manifest. Callers must provide one reference-period value per
    retained unit for the requested outcome, treatment, and any optional
    IV/selection/MIV metrics.
    """

    compiler_id = "observation.bounds_input"

    def compile(
        self,
        panel: ObservationPanel,
        spec: BoundsEstimationCompileSpec,
    ) -> CompiledObservationArtifact:
        units = _panel_units(
            panel,
            metric_ids=[
                spec.outcome_metric_id,
                spec.treatment_metric_id,
                *(
                    item
                    for item in [
                        spec.instrument_metric_id,
                        spec.selected_metric_id,
                        spec.miv_proxy_metric_id,
                    ]
                    if item
                ),
            ],
        )
        outcome, period = _latest_metric_vector(
            panel,
            metric_id=spec.outcome_metric_id,
            units=units,
            reference_period=None,
            compiler_id=self.compiler_id,
        )
        treatment_map = _period_metric_map(
            panel,
            metric_id=spec.treatment_metric_id,
            period_start=period,
            units=units,
            compiler_id=self.compiler_id,
        )
        instrument = None
        if spec.instrument_metric_id is not None:
            mapping = _period_metric_map(
                panel,
                metric_id=spec.instrument_metric_id,
                period_start=period,
                units=units,
                compiler_id=self.compiler_id,
            )
            instrument = _finite_list([mapping[unit_id] for unit_id in units])
        selected = None
        if spec.selected_metric_id is not None:
            mapping = _period_metric_map(
                panel,
                metric_id=spec.selected_metric_id,
                period_start=period,
                units=units,
                compiler_id=self.compiler_id,
            )
            selected = _finite_list([mapping[unit_id] for unit_id in units])
        miv_proxy = None
        if spec.miv_proxy_metric_id is not None:
            mapping = _period_metric_map(
                panel,
                metric_id=spec.miv_proxy_metric_id,
                period_start=period,
                units=units,
                compiler_id=self.compiler_id,
            )
            miv_proxy = _finite_list([mapping[unit_id] for unit_id in units])
        contract = BoundsEstimationInput(
            outcome=_finite_list(outcome.tolist()),
            treatment=_finite_list([treatment_map[unit_id] for unit_id in units]),
            instrument=instrument,
            selected=selected,
            miv_proxy=miv_proxy,
            metadata={"panel_id": panel.panel_id, "period_start": period.isoformat()},
        )
        bundle = BoundsEstimationBundle(
            channels=[
                BoundsChannelSpec(
                    family=panel.family,
                    bound_strategy="manski_bounds",
                    fallback_reason="compiler_output",
                )
            ],
            contract_payload=contract.model_dump(mode="json"),
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="bounds_estimation_input",
            contract=contract,
            bundle=bundle,
        )


class ProxyMeasurementCompiler:
    """Compile proxy-treatment evidence into proxy-identification bundles.

    Downstream proxy-aware causal runners consume the outcome, proxy,
    covariates, and optional validation channels packed into
    ``ProxyMeasurementData``. Callers must supply a proxy map whose
    latent-to-proxy entries match panel metrics available on the same reference
    period.
    """

    compiler_id = "observation.proxy_measurement"

    def compile(
        self,
        panel: ObservationPanel,
        proxy_map: ProxyMap,
        spec: ProxyMeasurementCompileSpec,
    ) -> CompiledObservationArtifact:
        units = _panel_units(
            panel,
            metric_ids=[
                spec.outcome_metric_id,
                spec.treatment_proxy_metric_id,
                *spec.covariate_metric_ids,
                *(
                    item
                    for item in [
                        spec.validation_true_treatment_metric_id,
                        spec.validation_proxy_metric_id,
                    ]
                    if item
                ),
            ],
        )
        outcome, period = _latest_metric_vector(
            panel,
            metric_id=spec.outcome_metric_id,
            units=units,
            reference_period=None,
            compiler_id=self.compiler_id,
        )
        proxy_values = _period_metric_map(
            panel,
            metric_id=spec.treatment_proxy_metric_id,
            period_start=period,
            units=units,
            compiler_id=self.compiler_id,
        )
        covariates = None
        if spec.covariate_metric_ids:
            covariate_columns = []
            for metric_id in spec.covariate_metric_ids:
                mapping = _period_metric_map(
                    panel,
                    metric_id=metric_id,
                    period_start=period,
                    units=units,
                    compiler_id=self.compiler_id,
                )
                covariate_columns.append([mapping[unit_id] for unit_id in units])
            covariates = np.asarray(covariate_columns, dtype=float).T
        validation_true = None
        if spec.validation_true_treatment_metric_id is not None:
            mapping = _period_metric_map(
                panel,
                metric_id=spec.validation_true_treatment_metric_id,
                period_start=period,
                units=units,
                compiler_id=self.compiler_id,
            )
            validation_true = np.asarray([mapping[unit_id] for unit_id in units], dtype=float)
        validation_proxy = None
        if spec.validation_proxy_metric_id is not None:
            mapping = _period_metric_map(
                panel,
                metric_id=spec.validation_proxy_metric_id,
                period_start=period,
                units=units,
                compiler_id=self.compiler_id,
            )
            validation_proxy = np.asarray([mapping[unit_id] for unit_id in units], dtype=float)
        contract = _method_contract_payload(
            outcome=outcome,
            treatment_proxy=np.asarray([proxy_values[unit_id] for unit_id in units], dtype=float),
            covariates=covariates,
            validation_true_treatment=validation_true,
            validation_proxy=validation_proxy,
            error_variance=spec.error_variance,
            error_rate_bound=spec.error_rate_bound,
            metadata={
                "panel_id": panel.panel_id,
                "period_start": period.isoformat(),
                "proxy_map_id": proxy_map.proxy_map_id,
            },
        )
        proxy_channels = [
            ProxyChannelSpec(
                family=panel.family,
                proxy_variable=proxy_name,
                latent_variable=latent_name,
                target_contract=PROXY_MEASUREMENT_TARGET,
            )
            for latent_name, proxy_name in sorted(proxy_map.mapping.items())
        ]
        bundle = ProxyIdentificationBundle(
            contract_target=PROXY_MEASUREMENT_TARGET,
            proxy_channels=proxy_channels,
            contract_payload=contract,
            proxy_map=dict(proxy_map.mapping),
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="proxy_measurement_data",
            contract=contract,
            bundle=bundle,
        )


class HistoricalValidationPlanCompiler:
    """Compile panel history into backtest plans for Scientist validation runners.

    Downstream historical-validation and governance flows consume the emitted
    ``HistoricalValidationPlan`` records plus frozen ground-truth series.
    Callers must provide enough ordered periods to cover the requested
    pre/post-intervention window for every requested metric.
    """

    compiler_id = "observation.historical_validation"

    def compile(
        self,
        panel: ObservationPanel,
        spec: HistoricalValidationCompileSpec,
    ) -> HistoricalValidationCompilation:
        periods = _sorted_periods(panel.records, metric_ids=spec.metric_ids)
        if len(periods) < spec.pre_intervention_periods + spec.post_intervention_periods:
            raise ObservationContractCompileError(
                "insufficient periods for requested historical validation window",
                compiler_id=self.compiler_id,
            )
        ground_truth = {
            metric_id: self._aggregate_metric(panel, metric_id=metric_id, periods=periods)
            for metric_id in spec.metric_ids
        }
        historical_payload = {
            "panel_id": panel.panel_id,
            "family": panel.family.value,
            "time_index": [period.isoformat() for period in periods],
            "series": dict(ground_truth),
        }
        plan = HistoricalValidationPlan(
            plan_id=spec.spec_id,
            plan_label=f"{panel.panel_id}_backtest",
            historical_data_ref=spec.historical_data_ref
            or f"compiled://{panel.panel_id}/{spec.spec_id}",
            historical_data_path=spec.historical_data_path,
            intervention_date=spec.intervention_date,
            intervention_step=spec.pre_intervention_periods,
            pre_intervention_periods=spec.pre_intervention_periods,
            post_intervention_periods=spec.post_intervention_periods,
            ground_truth_outcomes=ground_truth,
            target_metrics=list(spec.metric_ids),
            prediction_source=spec.prediction_source,
            jurisdiction=spec.jurisdiction,
            metadata={"panel_id": panel.panel_id},
        )
        bundle = BacktestPlanBundle(
            contract_target=BACKTEST_PLAN_TARGET,
            required_fields=["historical_data_ref", "ground_truth_outcomes", "target_metrics"],
            holdout_windows=[
                f"{periods[-spec.post_intervention_periods].isoformat()}:{periods[-1].isoformat()}"
            ],
            plans=[plan],
            historical_payloads={plan.plan_id: historical_payload},
        )
        return HistoricalValidationCompilation(
            plans=[plan],
            historical_payloads={plan.plan_id: historical_payload},
            bundle=bundle,
        )

    def _aggregate_metric(
        self,
        panel: ObservationPanel,
        *,
        metric_id: str,
        periods: Sequence[date],
    ) -> list[float]:
        values_by_period: dict[date, list[float]] = defaultdict(list)
        for record in panel.records:
            if record.metric_id == metric_id:
                values_by_period[record.period_start].append(float(record.observed_value))
        return [float(np.mean(values_by_period[period])) for period in periods]


class SpecificationCurveCompiler:
    """Compile robustness specifications into a specification-curve input bundle.

    Downstream specification-curve analyzers consume the ordered estimates and
    standard errors from the emitted bundle. Callers must provide at least two
    periods for every included metric in each source specification so effect
    deltas can be computed.
    """

    compiler_id = "observation.specification_curve"

    def compile(
        self,
        panel: ObservationPanel,
        spec: SpecificationCurveCompileSpec,
    ) -> CompiledObservationArtifact:
        estimates: list[float] = []
        standard_errors: list[float] = []
        bundle_sources: list[SpecificationCurveSource] = []
        for source in spec.source_specifications:
            estimate, standard_error = self._estimate_specification(panel, source)
            estimates.append(estimate)
            standard_errors.append(standard_error)
            bundle_sources.append(
                SpecificationCurveSource(
                    source_combination_id=source.source_combination_id,
                    included_families=list(source.included_families or [panel.family]),
                    sensitivity_axes=list(source.sensitivity_axes),
                    notes=list(source.notes),
                )
            )
        contract = SpecificationCurveInput(
            specification_ids=[
                source.source_combination_id for source in spec.source_specifications
            ],
            estimates=estimates,
            standard_errors=standard_errors,
            metadata={"panel_id": panel.panel_id, "family": panel.family.value},
        )
        bundle = SpecificationCurveBundle(
            source_specifications=bundle_sources,
            specification_ids=list(contract.specification_ids),
            estimates=list(contract.estimates),
            standard_errors=list(contract.standard_errors),
            contract_payload=contract.model_dump(mode="json"),
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="specification_curve_input",
            contract=contract,
            bundle=bundle,
        )

    def _estimate_specification(
        self,
        panel: ObservationPanel,
        source: SpecificationCurveSourceSpec,
    ) -> tuple[float, float]:
        periods = _sorted_periods(panel.records, metric_ids=source.included_metric_ids)
        if len(periods) < 2:
            raise ObservationContractCompileError(
                "specification curve needs at least 2 periods per source specification",
                compiler_id=self.compiler_id,
                field_name=source.source_combination_id,
            )
        per_metric_effects = []
        for metric_id in source.included_metric_ids:
            first_period_values = [
                float(record.observed_value)
                for record in panel.records
                if record.metric_id == metric_id and record.period_start == periods[0]
            ]
            last_period_values = [
                float(record.observed_value)
                for record in panel.records
                if record.metric_id == metric_id and record.period_start == periods[-1]
            ]
            if not first_period_values or not last_period_values:
                raise ObservationContractCompileError(
                    f"missing values for metric '{metric_id}'",
                    compiler_id=self.compiler_id,
                    field_name=metric_id,
                )
            first_mean = float(np.mean(first_period_values))
            last_mean = float(np.mean(last_period_values))
            per_metric_effects.append(last_mean - first_mean)
        estimate = float(np.mean(per_metric_effects))
        standard_error = (
            float(np.std(per_metric_effects, ddof=1) / max(len(per_metric_effects), 1) ** 0.5)
            if len(per_metric_effects) > 1
            else 0.1
        )
        return estimate, max(standard_error, 1e-6)


class LeontiefIOCompiler:
    """Compile region-sector flow panels into Leontief IO bundles for downstream solvers.

    Downstream IO or general-equilibrium runners consume the technical
    coefficients, final demand, and value-added vectors. Callers must provide a
    consistent region/sector flow table whose rows aggregate into a square
    coefficient matrix.
    """

    compiler_id = "observation.leontief_io"

    def compile(
        self,
        panels: RegionSectorPanels,
        spec: LeontiefIOCompileSpec,
    ) -> CompiledObservationArtifact:
        del spec
        node_keys = sorted(
            {f"{row.from_region_code}:{row.from_sector_id}" for row in panels.rows}
            | {f"{row.to_region_code}:{row.to_sector_id}" for row in panels.rows}
        )
        index_map = {key: idx for idx, key in enumerate(node_keys)}
        matrix = np.zeros((len(node_keys), len(node_keys)), dtype=float)
        final_demand = np.zeros(len(node_keys), dtype=float)
        value_added = np.zeros(len(node_keys), dtype=float)
        for row in panels.rows:
            src_key = f"{row.from_region_code}:{row.from_sector_id}"
            dst_key = f"{row.to_region_code}:{row.to_sector_id}"
            matrix[index_map[src_key], index_map[dst_key]] += float(row.technical_coefficient)
            final_demand[index_map[dst_key]] += float(row.final_demand)
            value_added[index_map[src_key]] += float(row.value_added)
        regions = sorted(
            {row.from_region_code for row in panels.rows}
            | {row.to_region_code for row in panels.rows}
        )
        sectors = sorted(
            {row.from_sector_id for row in panels.rows} | {row.to_sector_id for row in panels.rows}
        )
        sector_index_map = {name: idx for idx, name in enumerate(node_keys)}
        contract = LeontiefIOInput(
            technical_coefficients=matrix.tolist(),
            final_demand=final_demand.tolist(),
            sector_names=list(node_keys),
            regions=regions,
            value_added=value_added.tolist(),
            region_index_map={region: idx for idx, region in enumerate(regions)},
            sector_index_map=sector_index_map,
            metadata={"panel_id": panels.panel_id},
        )
        bundle = LeontiefIOBundle(
            regions=regions,
            sectors=sectors,
            technical_coefficients=matrix.tolist(),
            final_demand=final_demand.tolist(),
            value_added=value_added.tolist(),
            sector_names=list(node_keys),
            region_index_map={region: idx for idx, region in enumerate(regions)},
            sector_index_map=sector_index_map,
            contract_payload=contract.model_dump(mode="json"),
        )
        return CompiledObservationArtifact(
            compiler_id=self.compiler_id,
            artifact_key="leontief_io_input",
            contract=contract,
            bundle=bundle,
        )


def write_json_bundle(bundle: KernelModel, path: str | Path) -> Path:
    """Write a canonical JSON bundle payload to disk and return the destination path."""
    destination = Path(path)
    payload = bundle.model_dump(mode="json")
    destination.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return destination


def load_json_bundle(path: str | Path, model_cls: type[KernelModel]) -> KernelModel:
    """Load json bundle."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return model_cls.model_validate(payload)


def write_npz_payload(payload: Mapping[str, Any], path: str | Path) -> Path:
    """Write array and JSON-compatible payload values into an ``.npz`` container."""
    destination = Path(path)
    arrays: dict[str, np.ndarray] = {}
    for key, value in payload.items():
        array = np.asarray(value)
        if array.dtype == object:
            arrays[key] = np.asarray(
                json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            )
        else:
            arrays[key] = array
    np.savez(destination, **arrays)
    return destination


def load_npz_payload(path: str | Path) -> dict[str, Any]:
    """Load npz payload."""
    source = Path(path)
    with np.load(source, allow_pickle=False) as loaded:
        payload: dict[str, Any] = {}
        for key in loaded.files:
            value = loaded[key]
            if value.dtype.kind in {"U", "S"} and value.ndim == 0:
                raw_value = value.item()
                if isinstance(raw_value, bytes):
                    try:
                        raw = raw_value.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise ObservationContractLoadError(
                            "failed to decode scalar payload as UTF-8",
                            artifact_path=str(source),
                            field_name=key,
                        ) from exc
                else:
                    raw = str(raw_value)
                stripped = raw.strip()
                if stripped.startswith(("{", "[", '"')):
                    try:
                        payload[key] = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise ObservationContractLoadError(
                            "failed to parse JSON-encoded scalar payload",
                            artifact_path=str(source),
                            field_name=key,
                        ) from exc
                else:
                    payload[key] = raw
            else:
                payload[key] = value
        return payload


def write_parquet_rows(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    """Write tabular contract rows to Parquet with deterministic row ordering."""
    destination = Path(path)
    frame = pd.DataFrame(list(rows))
    sort_columns = [
        column for column in ("unit_id", "firm_id", "period_id") if column in frame.columns
    ]
    if sort_columns:
        frame = frame.sort_values(sort_columns)
    frame.to_parquet(destination, index=False)
    return destination


def load_parquet_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load parquet rows."""
    frame = pd.read_parquet(Path(path))
    return frame.to_dict(orient="records")


class ObservationContractCompilerSuite:
    """Facade that compiles observation evidence into all supported contracts.

    The suite orchestrates the survey, network, panel, dynamic-treatment,
    survival, bounds, proxy, backtest, specification-curve, and Leontief
    compilers, then emits a single observation-to-contract manifest.
    """

    def __init__(self, context: ObservationCompilerContext | None = None) -> None:
        self.context = context or ObservationCompilerContext()
        self.survey = SurveyMicroDataCompiler(self.context)
        self.network = NetworkContractCompiler(self.context)
        self.network_causal = NetworkCausalDataCompiler(self.context)
        self.panel = PanelObservationalCompiler(self.context)
        self.dynamic = DynamicTreatmentCompiler(self.context)
        self.survival = SurvivalDataCompiler()
        self.panel_econometric = PanelEconometricCompiler()
        self.bounds = BoundsInputCompiler()
        self.proxy = ProxyMeasurementCompiler()
        self.historical_validation = HistoricalValidationPlanCompiler()
        self.specification_curve = SpecificationCurveCompiler()
        self.leontief = LeontiefIOCompiler()

    def compile_all(
        self,
        *,
        observation_panel: ObservationPanel | None = None,
        graph_artifacts: GraphArtifacts | None = None,
        firm_events: FirmEvents | None = None,
        firm_panels: FirmPanels | None = None,
        region_sector_panels: RegionSectorPanels | None = None,
        proxy_map: ProxyMap | None = None,
        survey_spec: SurveyMicroDataCompileSpec | None = None,
        network_spec: NetworkContractCompileSpec | None = None,
        network_causal_spec: NetworkCausalCompileSpec | None = None,
        panel_spec: PanelObservationalCompileSpec | None = None,
        dynamic_treatment_spec: DynamicTreatmentCompileSpec | None = None,
        survival_spec: SurvivalCompileSpec | None = None,
        panel_econometric_spec: PanelEconometricCompileSpec | None = None,
        bounds_spec: BoundsEstimationCompileSpec | None = None,
        proxy_spec: ProxyMeasurementCompileSpec | None = None,
        historical_validation_spec: HistoricalValidationCompileSpec | None = None,
        specification_curve_spec: SpecificationCurveCompileSpec | None = None,
        leontief_spec: LeontiefIOCompileSpec | None = None,
    ) -> ObservationContractSuiteResult:
        artifacts: dict[str, CompiledObservationArtifact] = {}
        manifest_artifacts: list[ObservationContractArtifact] = []
        routes: dict[
            tuple[ObservationFamily, IdentificationMode, str], ObservationContractRoute
        ] = {}
        backtest_result: HistoricalValidationCompilation | None = None

        def _register(
            artifact: CompiledObservationArtifact, *, family: ObservationFamily | None
        ) -> None:
            artifacts[artifact.artifact_key] = artifact
            target_contract = self._target_contract_for_artifact(artifact)
            route_mode = self._route_mode_for_artifact(artifact)
            manifest_artifacts.append(
                ObservationContractArtifact(
                    compiler_id=artifact.compiler_id,
                    artifact_name=artifact.bundle.artifact_name,
                    target_contract=target_contract,
                    status="compiled",
                    lineage=list(getattr(artifact.bundle, "lineage", [])),
                )
            )
            if family is not None and target_contract is not None:
                route_key = (family, route_mode, target_contract.contract_id)
                routes.setdefault(
                    route_key,
                    ObservationContractRoute(
                        family=family,
                        identification_mode=route_mode,
                        target_contract=target_contract,
                    ),
                )

        if observation_panel is not None and survey_spec is not None:
            _register(
                self.survey.compile(observation_panel, survey_spec), family=observation_panel.family
            )
        if graph_artifacts is not None and network_spec is not None:
            for artifact in self.network.compile(graph_artifacts, network_spec).values():
                _register(artifact, family=None)
        if (
            observation_panel is not None
            and graph_artifacts is not None
            and network_causal_spec is not None
        ):
            _register(
                self.network_causal.compile(
                    observation_panel, graph_artifacts, network_causal_spec
                ),
                family=observation_panel.family,
            )
        if observation_panel is not None and panel_spec is not None:
            _register(
                self.panel.compile(observation_panel, panel_spec), family=observation_panel.family
            )
        if observation_panel is not None and dynamic_treatment_spec is not None:
            _register(
                self.dynamic.compile(observation_panel, dynamic_treatment_spec),
                family=observation_panel.family,
            )
        if firm_events is not None and firm_panels is not None and survival_spec is not None:
            _register(
                self.survival.compile(firm_events, firm_panels, survival_spec),
                family=ObservationFamily.FIRM_FUNDAMENTALS,
            )
        if firm_panels is not None and panel_econometric_spec is not None:
            _register(
                self.panel_econometric.compile(firm_panels, panel_econometric_spec),
                family=ObservationFamily.FIRM_FUNDAMENTALS,
            )
        if observation_panel is not None and bounds_spec is not None:
            _register(
                self.bounds.compile(observation_panel, bounds_spec), family=observation_panel.family
            )
        if observation_panel is not None and proxy_map is not None and proxy_spec is not None:
            _register(
                self.proxy.compile(observation_panel, proxy_map, proxy_spec),
                family=observation_panel.family,
            )
        if observation_panel is not None and historical_validation_spec is not None:
            backtest_result = self.historical_validation.compile(
                observation_panel, historical_validation_spec
            )
            manifest_artifacts.append(
                ObservationContractArtifact(
                    compiler_id=self.historical_validation.compiler_id,
                    artifact_name=backtest_result.bundle.artifact_name,
                    target_contract=BACKTEST_PLAN_TARGET,
                    status="compiled",
                )
            )
            routes.setdefault(
                (
                    observation_panel.family,
                    IdentificationMode.POINT_IDENTIFIED,
                    BACKTEST_PLAN_TARGET.contract_id,
                ),
                ObservationContractRoute(
                    family=observation_panel.family,
                    identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    target_contract=BACKTEST_PLAN_TARGET,
                ),
            )
        if observation_panel is not None and specification_curve_spec is not None:
            _register(
                self.specification_curve.compile(observation_panel, specification_curve_spec),
                family=observation_panel.family,
            )
        if region_sector_panels is not None and leontief_spec is not None:
            _register(
                self.leontief.compile(region_sector_panels, leontief_spec),
                family=ObservationFamily.TRADE_EXPOSURE,
            )

        if not routes:
            routes[
                (
                    ObservationFamily.MACRO_STATE,
                    IdentificationMode.POINT_IDENTIFIED,
                    SURVEY_MICRODATA_TARGET.contract_id,
                )
            ] = ObservationContractRoute(
                family=ObservationFamily.MACRO_STATE,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=SURVEY_MICRODATA_TARGET,
                notes=["placeholder route generated because compile_all had no active compilers"],
            )
        manifest = ObservationToContractManifest(
            routes=list(routes.values()),
            artifacts=manifest_artifacts,
        )
        return ObservationContractSuiteResult(
            artifacts=artifacts,
            backtest=backtest_result,
            manifest=manifest,
        )

    def _target_contract_for_artifact(
        self,
        artifact: CompiledObservationArtifact,
    ) -> ContractCompatibilityTarget | None:
        if artifact.artifact_key == "survey_micro_data":
            return SURVEY_MICRODATA_TARGET
        if artifact.artifact_key == "network_data":
            return NETWORK_ANALYSIS_TARGET
        if artifact.artifact_key == "multiplex_network_data":
            return MULTIPLEX_NETWORK_TARGET
        if artifact.artifact_key == "network_causal_data":
            return NETWORK_DATA_TARGET
        if artifact.artifact_key == "panel_observational_data":
            return PANEL_OBSERVATIONAL_TARGET
        if artifact.artifact_key == "dynamic_treatment_data":
            return DYNAMIC_TREATMENT_TARGET
        if artifact.artifact_key == "survival_data":
            return SURVIVAL_DATA_TARGET
        if artifact.artifact_key == "panel_econometric_data":
            return PANEL_ECONOMETRIC_TARGET
        if artifact.artifact_key == "bounds_estimation_input":
            return ContractCompatibilityTarget(
                contract_id="foundry.causal.bounds_estimation_input.v1",
                contract_fqn="polisyos.ir.observation.contract_compilers.BoundsEstimationInput",
            )
        if artifact.artifact_key == "proxy_measurement_data":
            return PROXY_MEASUREMENT_TARGET
        if artifact.artifact_key == "specification_curve_input":
            return ContractCompatibilityTarget(
                contract_id="foundry.sensitivity.specification_curve_input.v1",
                contract_fqn="polisyos.ir.observation.contract_compilers.SpecificationCurveInput",
            )
        if artifact.artifact_key == "leontief_io_input":
            return ContractCompatibilityTarget(
                contract_id="foundry.optimization.leontief_io_input.v1",
                contract_fqn="polisyos.ir.observation.contract_compilers.LeontiefIOInput",
            )
        return None

    def _route_mode_for_artifact(self, artifact: CompiledObservationArtifact) -> IdentificationMode:
        if artifact.artifact_key == "dynamic_treatment_data":
            return IdentificationMode.SEQUENTIAL
        if artifact.artifact_key == "bounds_estimation_input":
            return IdentificationMode.BOUNDS_ONLY
        if artifact.artifact_key == "proxy_measurement_data":
            return IdentificationMode.PROXY_IDENTIFIED
        if artifact.artifact_key == "network_causal_data":
            return IdentificationMode.INTERFERENCE_AWARE
        return IdentificationMode.POINT_IDENTIFIED


__all__ = [
    "BoundsEstimationCompileSpec",
    "BoundsEstimationInput",
    "BoundsInputCompiler",
    "CompiledObservationArtifact",
    "DynamicTreatmentCompileSpec",
    "DynamicTreatmentCompiler",
    "FirmEventRecord",
    "FirmEvents",
    "FirmPanelRow",
    "FirmPanels",
    "GraphArtifacts",
    "GraphBipartiteEdge",
    "GraphEdge",
    "HistoricalValidationCompilation",
    "HistoricalValidationCompileSpec",
    "HistoricalValidationPlanCompiler",
    "LeontiefIOCompileSpec",
    "LeontiefIOCompiler",
    "LeontiefIOInput",
    "NetworkCausalCompileSpec",
    "NetworkCausalDataCompiler",
    "NetworkContractCompileSpec",
    "NetworkContractCompiler",
    "ObservationCompilerContext",
    "ObservationContractCompileError",
    "ObservationContractCompilerSuite",
    "ObservationContractLoadError",
    "ObservationContractSuiteResult",
    "PanelEconometricCompileSpec",
    "PanelEconometricCompiler",
    "PanelObservationalCompileSpec",
    "PanelObservationalCompiler",
    "ProxyMap",
    "ProxyMeasurementCompileSpec",
    "ProxyMeasurementCompiler",
    "RegionSectorFlowRow",
    "RegionSectorPanels",
    "SparseDenseBridge",
    "SpecificationCurveCompileSpec",
    "SpecificationCurveCompiler",
    "SpecificationCurveInput",
    "SpecificationCurveSourceSpec",
    "SurveyMicroDataCompileSpec",
    "SurveyMicroDataCompiler",
    "SurvivalCompileSpec",
    "SurvivalDataCompiler",
    "load_json_bundle",
    "load_npz_payload",
    "load_parquet_rows",
    "write_json_bundle",
    "write_npz_payload",
    "write_parquet_rows",
]
