from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Mapping, Protocol, runtime_checkable

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from polisyos.foundry.methods.base import MethodMetadata, MethodSignature
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.ir.analytics.parameters import ContextAdaptiveParameterBundle
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec

if TYPE_CHECKING:
    import pandas as pd

    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class PanelObservationalData(BaseModel):
    """Panel data used by SCM / DiD / Structural Time Series methods."""

    contract_id: ClassVar[str] = "foundry.causal.panel_observational_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any  # shape: (n_units, n_periods)
    treatment: Any  # shape: (n_units,)
    time_treatment: int = Field(..., ge=0)

    covariates: Any | None = None  # shape: (n_units, n_covariates)
    treatment_timing: Any | None = None  # shape: (n_units,)
    unit_ids: Any | None = None  # shape: (n_units,)
    time_index: Any | None = None  # shape: (n_periods,)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "outcome",
        "treatment",
        "covariates",
        "treatment_timing",
        "unit_ids",
        "time_index",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "PanelObservationalData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 2:
            raise ValueError("outcome must be a 2D numpy array: (n_units, n_periods)")

        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")

        n_units, n_periods = self.outcome.shape
        if n_units < 2:
            raise ValueError("panel outcome must contain at least 2 units")
        if n_periods < 2:
            raise ValueError("panel outcome must contain at least 2 periods")

        if not isinstance(self.treatment, np.ndarray) or self.treatment.ndim != 1:
            raise ValueError("treatment must be a 1D numpy array: (n_units,)")
        if self.treatment.shape[0] != n_units:
            raise ValueError(
                f"Shape mismatch: outcome has {n_units} units, "
                f"treatment has {self.treatment.shape[0]}"
            )
        if not np.isin(self.treatment, [0, 1]).all():
            raise ValueError("treatment vector must be binary (0/1)")

        if self.time_treatment >= n_periods:
            raise ValueError(
                f"time_treatment={self.time_treatment} is out of range for n_periods={n_periods}"
            )

        if self.covariates is not None:
            if not isinstance(self.covariates, np.ndarray) or self.covariates.ndim != 2:
                raise ValueError("covariates must be a 2D numpy array: (n_units, n_covariates)")
            if self.covariates.shape[0] != n_units:
                raise ValueError(
                    "Shape mismatch: covariates first dimension must equal outcome n_units"
                )
            if not np.isfinite(self.covariates).all():
                raise ValueError("covariates contains non-finite values")

        if self.treatment_timing is not None:
            if (
                not isinstance(self.treatment_timing, np.ndarray)
                or self.treatment_timing.ndim != 1
                or self.treatment_timing.shape[0] != n_units
            ):
                raise ValueError("treatment_timing must be a 1D array with length n_units")

        if self.unit_ids is not None:
            if (
                not isinstance(self.unit_ids, np.ndarray)
                or self.unit_ids.ndim != 1
                or self.unit_ids.shape[0] != n_units
            ):
                raise ValueError("unit_ids must be a 1D array with length n_units")

        if self.time_index is not None:
            if (
                not isinstance(self.time_index, np.ndarray)
                or self.time_index.ndim != 1
                or self.time_index.shape[0] != n_periods
            ):
                raise ValueError("time_index must be a 1D array with length n_periods")

        return self

    @field_serializer(
        "outcome",
        "treatment",
        "covariates",
        "treatment_timing",
        "unit_ids",
        "time_index",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_units(self) -> int:
        return int(self.outcome.shape[0])

    @property
    def n_periods(self) -> int:
        return int(self.outcome.shape[1])

    @property
    def pre_periods(self) -> int:
        return int(self.time_treatment)

    @property
    def post_periods(self) -> int:
        return int(self.n_periods - self.time_treatment)

    @classmethod
    def from_dataframe(
        cls,
        df: "pd.DataFrame",
        *,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treatment_col: str,
        time_treatment: int,
    ) -> "PanelObservationalData":
        frame = df.copy()
        frame = frame.sort_values([unit_col, time_col])
        panel = frame.pivot(index=unit_col, columns=time_col, values=outcome_col)
        units = panel.index.to_numpy()
        times = panel.columns.to_numpy()
        treatment = (
            frame.drop_duplicates(subset=[unit_col])
            .set_index(unit_col)[treatment_col]
            .reindex(units)
        )
        return cls(
            outcome=panel.to_numpy(dtype=float),
            treatment=treatment.to_numpy(dtype=int),
            time_treatment=time_treatment,
            unit_ids=units,
            time_index=times,
        )


class HTEObservationalData(BaseModel):
    """Cross-sectional observational data for HTE estimators."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any  # shape: (n_obs,)
    treatment: Any  # shape: (n_obs,)
    covariates: Any  # shape: (n_obs, n_features)
    confounders: Any | None = None  # shape: (n_obs, n_confounders)
    feature_names: list[str] | None = None
    confounder_names: list[str] | None = None
    sample_ids: Any | None = None  # shape: (n_obs,)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "outcome",
        "treatment",
        "covariates",
        "confounders",
        "sample_ids",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "HTEObservationalData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array")
        if not isinstance(self.treatment, np.ndarray) or self.treatment.ndim != 1:
            raise ValueError("treatment must be a 1D numpy array")
        if not isinstance(self.covariates, np.ndarray) or self.covariates.ndim != 2:
            raise ValueError("covariates must be a 2D numpy array")

        n_obs = self.outcome.shape[0]
        if self.treatment.shape[0] != n_obs:
            raise ValueError("treatment length must match outcome length")
        if self.covariates.shape[0] != n_obs:
            raise ValueError("covariates row count must match outcome length")
        if n_obs < 40:
            raise ValueError("HTE data requires at least 40 observations")
        if self.covariates.shape[1] < 1:
            raise ValueError("covariates must contain at least one feature")

        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")
        if not np.isin(self.treatment, [0, 1]).all():
            raise ValueError("treatment vector must be binary (0/1)")
        if not np.isfinite(self.covariates).all():
            raise ValueError("covariates contains non-finite values")

        if self.confounders is not None:
            if not isinstance(self.confounders, np.ndarray) or self.confounders.ndim != 2:
                raise ValueError("confounders must be a 2D numpy array")
            if self.confounders.shape[0] != n_obs:
                raise ValueError("confounders row count must match outcome length")
            if not np.isfinite(self.confounders).all():
                raise ValueError("confounders contains non-finite values")

        if self.feature_names is not None and len(self.feature_names) != self.covariates.shape[1]:
            raise ValueError("feature_names length must match covariates column count")

        if (
            self.confounders is not None
            and self.confounder_names is not None
            and len(self.confounder_names) != self.confounders.shape[1]
        ):
            raise ValueError("confounder_names length must match confounders column count")

        if self.sample_ids is not None:
            if not isinstance(self.sample_ids, np.ndarray) or self.sample_ids.ndim != 1:
                raise ValueError("sample_ids must be a 1D array")
            if self.sample_ids.shape[0] != n_obs:
                raise ValueError("sample_ids length must match outcome length")

        return self

    @field_serializer(
        "outcome",
        "treatment",
        "covariates",
        "confounders",
        "sample_ids",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.outcome.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.covariates.shape[1])


class TimeSeriesCausalData(BaseModel):
    """Time-series data contract for PCMCI/Tigramite discovery."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data: Any  # shape: (n_timesteps, n_variables)
    variable_names: list[str]
    time_index: Any | None = None  # shape: (n_timesteps,)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", "time_index", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "TimeSeriesCausalData":
        if not isinstance(self.data, np.ndarray) or self.data.ndim != 2:
            raise ValueError("data must be a 2D numpy array: (n_timesteps, n_variables)")
        if self.data.shape[0] < 3:
            raise ValueError("time-series data requires at least 3 timesteps")
        if self.data.shape[1] < 2:
            raise ValueError("time-series data requires at least 2 variables")
        if not np.isfinite(self.data).all():
            raise ValueError("data contains non-finite values")
        if len(self.variable_names) != self.data.shape[1]:
            raise ValueError("len(variable_names) must match data.shape[1]")
        if len(set(self.variable_names)) != len(self.variable_names):
            raise ValueError("variable_names must be unique")
        if any(not name for name in self.variable_names):
            raise ValueError("variable_names must not contain empty values")
        if self.time_index is not None:
            if not isinstance(self.time_index, np.ndarray) or self.time_index.ndim != 1:
                raise ValueError("time_index must be a 1D array")
            if self.time_index.shape[0] != self.data.shape[0]:
                raise ValueError("time_index length must match number of timesteps")
        return self

    @field_serializer("data", "time_index", mode="plain", when_used="json")
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_timesteps(self) -> int:
        return int(self.data.shape[0])

    @property
    def n_variables(self) -> int:
        return int(self.data.shape[1])


class TabularCausalDiscoveryData(BaseModel):
    """Cross-sectional data contract for PC/FCI/GES causal discovery."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data: Any  # shape: (n_samples, n_variables)
    variable_names: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "TabularCausalDiscoveryData":
        if not isinstance(self.data, np.ndarray) or self.data.ndim != 2:
            raise ValueError("data must be a 2D numpy array: (n_samples, n_variables)")
        if self.data.shape[0] < 2:
            raise ValueError("tabular discovery data requires at least 2 samples")
        if self.data.shape[1] < 2:
            raise ValueError("tabular discovery data requires at least 2 variables")
        if not np.isfinite(self.data).all():
            raise ValueError("data contains non-finite values")
        if len(self.variable_names) != self.data.shape[1]:
            raise ValueError("len(variable_names) must match data.shape[1]")
        if len(set(self.variable_names)) != len(self.variable_names):
            raise ValueError("variable_names must be unique")
        if any(not name for name in self.variable_names):
            raise ValueError("variable_names must not contain empty values")
        return self

    @field_serializer("data", mode="plain", when_used="json")
    def _serialize_data(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_samples(self) -> int:
        return int(self.data.shape[0])

    @property
    def n_variables(self) -> int:
        return int(self.data.shape[1])


class _GraphCausalDataBase(BaseModel):
    """Shared shape validation for graph-based causal inputs."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data: Any  # shape: (n_obs, n_features)
    column_names: list[str]
    treatment: str
    outcome: str
    graph_ref: str | None = None
    covariates: list[str] = Field(default_factory=list)

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate(self):
        if not isinstance(self.data, np.ndarray) or self.data.ndim != 2:
            raise ValueError("data must be a 2D numpy array")
        if self.data.shape[0] < 2:
            raise ValueError("graph causal data requires at least 2 observations")
        if self.data.shape[1] < 2:
            raise ValueError("graph causal data requires at least 2 columns")
        if not np.isfinite(self.data).all():
            raise ValueError("data contains non-finite values")
        if len(self.column_names) != self.data.shape[1]:
            raise ValueError("data columns != len(column_names)")
        if len(set(self.column_names)) != len(self.column_names):
            raise ValueError("column_names must be unique")
        if self.treatment not in self.column_names:
            raise ValueError(f"treatment '{self.treatment}' not in column_names")
        if self.outcome not in self.column_names:
            raise ValueError(f"outcome '{self.outcome}' not in column_names")
        unknown_covariates = sorted(set(self.covariates) - set(self.column_names))
        if unknown_covariates:
            raise ValueError(f"covariates not in column_names: {unknown_covariates}")
        return self

    @field_serializer("data", mode="plain", when_used="json")
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def sample_size(self) -> int:
        return int(self.data.shape[0])


class GraphCausalData(_GraphCausalDataBase):
    """Primary cross-sectional data contract for DoWhy v2+."""

    graph_dot: str | None = None

    @classmethod
    def from_causal_graph_model(
        cls,
        *,
        data: Any,
        column_names: list[str],
        treatment: str,
        outcome: str,
        graph: "CausalGraphModel",
        graph_ref: str | None = None,
        covariates: list[str] | None = None,
    ) -> "GraphCausalData":
        graph_dot = graph.to_dot() if hasattr(graph, "to_dot") else None
        return cls(
            data=data,
            column_names=column_names,
            treatment=treatment,
            outcome=outcome,
            graph_dot=graph_dot,
            graph_ref=graph_ref,
            covariates=list(covariates or []),
        )


class GraphCausalDataV1(_GraphCausalDataBase):
    """Legacy cross-sectional data contract for DoWhy v1."""

    graph_gml: str | None = None


class SCMFitData(BaseModel):
    """Cross-sectional data contract for structural causal mechanism fitting."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data: Any  # shape: (n_obs, n_features)
    column_names: list[str]
    graph: CausalGraphModel | dict[str, Any]
    graph_ref: str | None = None
    literature_priors: dict[str, dict[str, dict[str, float]]] = Field(default_factory=dict)
    skg_snapshot_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_validator("graph", mode="before")
    @classmethod
    def _coerce_graph(cls, value: Any) -> Any:
        if isinstance(value, CausalGraphModel):
            return value
        if isinstance(value, dict):
            return CausalGraphModel.model_validate(value)
        raise ValueError("graph must be CausalGraphModel or dict payload")

    @model_validator(mode="after")
    def _validate_payload(self) -> "SCMFitData":
        if not isinstance(self.data, np.ndarray) or self.data.ndim != 2:
            raise ValueError("data must be a 2D numpy array")
        if self.data.shape[0] < 2:
            raise ValueError("SCM fit data requires at least 2 observations")
        if self.data.shape[1] < 1:
            raise ValueError("SCM fit data requires at least 1 feature column")
        if not np.isfinite(self.data).all():
            raise ValueError("data contains non-finite values")
        if len(self.column_names) != self.data.shape[1]:
            raise ValueError("data columns != len(column_names)")
        if len(set(self.column_names)) != len(self.column_names):
            raise ValueError("column_names must be unique")

        graph_vars = set(self.graph.nodes)
        unknown_columns = sorted(set(self.column_names) - graph_vars)
        if unknown_columns:
            raise ValueError(f"column_names not present in graph nodes: {unknown_columns}")

        for target, per_parent in self.literature_priors.items():
            if target not in graph_vars:
                raise ValueError(f"literature prior target '{target}' not in graph nodes")
            if not isinstance(per_parent, dict):
                raise ValueError("literature_priors values must be dict[parent, prior]")
            for parent_name, stats in per_parent.items():
                if parent_name != "__intercept__" and parent_name not in graph_vars:
                    raise ValueError(
                        f"literature prior parent '{parent_name}' not in graph nodes"
                    )
                if not isinstance(stats, dict):
                    raise ValueError("literature prior stats must be dict with mean/std")
                mean = stats.get("mean")
                std = stats.get("std")
                if mean is not None and not np.isfinite(float(mean)):
                    raise ValueError("literature prior mean must be finite")
                if std is not None and not np.isfinite(float(std)):
                    raise ValueError("literature prior std must be finite")
        return self

    @field_serializer("data", mode="plain", when_used="json")
    def _serialize_data(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @field_serializer("graph", mode="plain", when_used="json")
    def _serialize_graph(self, value: CausalGraphModel | dict[str, Any]) -> Any:
        if isinstance(value, CausalGraphModel):
            return value.model_dump(mode="json")
        return value

    @property
    def sample_size(self) -> int:
        return int(self.data.shape[0])


class SCMQueryData(BaseModel):
    """Input contract for structural causal query execution."""

    model_config = ConfigDict(extra="forbid")

    scm_spec: StructuralCausalModelSpec | dict[str, Any]
    query: CausalQuery | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scm_spec", mode="before")
    @classmethod
    def _coerce_scm_spec(cls, value: Any) -> StructuralCausalModelSpec:
        if isinstance(value, StructuralCausalModelSpec):
            return value
        if isinstance(value, dict):
            return StructuralCausalModelSpec.model_validate(value)
        raise ValueError("scm_spec must be StructuralCausalModelSpec or dict payload")

    @field_validator("query", mode="before")
    @classmethod
    def _coerce_query(cls, value: Any) -> CausalQuery:
        if isinstance(value, CausalQuery):
            return value
        if isinstance(value, dict):
            return CausalQuery.model_validate(value)
        raise ValueError("query must be CausalQuery or dict payload")

    @model_validator(mode="after")
    def _validate_payload(self) -> "SCMQueryData":
        nodes = set(self.scm_spec.graph.nodes)
        if self.query.treatment_variable not in nodes:
            raise ValueError(
                f"query treatment variable '{self.query.treatment_variable}' not in SCM graph nodes"
            )
        if self.query.outcome_variable not in nodes:
            raise ValueError(
                f"query outcome variable '{self.query.outcome_variable}' not in SCM graph nodes"
            )
        unknown_condition = sorted(set(self.query.condition) - nodes)
        if unknown_condition:
            raise ValueError(
                f"query condition variables not in SCM graph nodes: {unknown_condition}"
            )
        return self


class ParameterTransferData(BaseModel):
    """Input contract for causal.structural.parameter_transfer."""

    model_config = ConfigDict(extra="forbid")

    parameter_bundle: ContextAdaptiveParameterBundle | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("parameter_bundle", mode="before")
    @classmethod
    def _coerce_parameter_bundle(cls, value: Any) -> ContextAdaptiveParameterBundle:
        if isinstance(value, ContextAdaptiveParameterBundle):
            return value
        if isinstance(value, dict):
            return ContextAdaptiveParameterBundle.model_validate(value)
        raise ValueError("parameter_bundle must be ContextAdaptiveParameterBundle or dict payload")


class LLMStructuralHint(BaseModel):
    """LLM-proposed structural edge hint for graph reconciliation."""

    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None
    source_method_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiteraturePriorBuildData(BaseModel):
    """Input contract for causal.prior.build_literature_prior."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str]
    skg_db_path: str | None = None
    skg_index_dir: str | None = None
    min_confidence: float = Field(default=0.2, ge=0.0, le=1.0)
    limit: int = Field(default=256, ge=1, le=10_000)
    domain: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_variables(self) -> "LiteraturePriorBuildData":
        if not self.variables:
            raise ValueError("variables must contain at least one variable name")
        if any(not str(item).strip() for item in self.variables):
            raise ValueError("variables must not contain empty names")
        return self


class GraphReconciliationData(BaseModel):
    """Input contract for causal.prior.reconcile_causal_graph."""

    model_config = ConfigDict(extra="forbid")

    data_graph: CausalGraphModel | dict[str, Any]
    literature_prior: LiteratureCausalPrior | dict[str, Any] | None = None
    llm_hints: list[LLMStructuralHint] = Field(default_factory=list)
    min_edge_confidence: float = Field(default=0.1, ge=0.0, le=1.0)
    max_lag_depth: int = Field(default=2, ge=0, le=8)
    max_lagged_edges: int = Field(default=10, ge=0, le=256)
    max_cycles_to_resolve: int = Field(default=8, ge=0, le=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data_graph", mode="before")
    @classmethod
    def _coerce_data_graph(cls, value: Any) -> CausalGraphModel:
        if isinstance(value, CausalGraphModel):
            return value
        if isinstance(value, dict):
            return CausalGraphModel.model_validate(value)
        raise ValueError("data_graph must be CausalGraphModel or dict payload")

    @field_validator("literature_prior", mode="before")
    @classmethod
    def _coerce_literature_prior(cls, value: Any) -> LiteratureCausalPrior | None:
        if value is None:
            return None
        if isinstance(value, LiteratureCausalPrior):
            return value
        if isinstance(value, dict):
            return LiteratureCausalPrior.model_validate(value)
        raise ValueError("literature_prior must be LiteratureCausalPrior, dict, or None")


class RDDObservationalData(BaseModel):
    """Cross-sectional data for Regression Discontinuity Design."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any  # shape: (n_obs,)
    running_variable: Any  # shape: (n_obs,)
    cutoff: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome", "running_variable", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "RDDObservationalData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array")
        if not isinstance(self.running_variable, np.ndarray) or self.running_variable.ndim != 1:
            raise ValueError("running_variable must be a 1D numpy array")
        if self.outcome.shape[0] != self.running_variable.shape[0]:
            raise ValueError("outcome and running_variable length mismatch")
        if self.outcome.shape[0] < 20:
            raise ValueError("RDD requires at least 20 observations")
        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")
        if not np.isfinite(self.running_variable).all():
            raise ValueError("running_variable contains non-finite values")
        if not np.isfinite(self.cutoff):
            raise ValueError("cutoff must be finite")
        return self

    @field_serializer("outcome", "running_variable", mode="plain", when_used="json")
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def sample_size(self) -> int:
        return int(self.outcome.shape[0])


@runtime_checkable
class CausalEstimator(Protocol):
    signature: ClassVar[MethodSignature]
    metadata: ClassVar[MethodMetadata]

    @staticmethod
    def pure_step(
        state: (
            PanelObservationalData
            | RDDObservationalData
            | HTEObservationalData
            | TimeSeriesCausalData
            | GraphCausalData
            | GraphCausalDataV1
        ),
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Expected output keys:
        - report: CausalEffectReport
        - envelope: UncertaintyEnvelope | None
        """
        ...


def envelope_from_report(report: CausalEffectReport) -> "UncertaintyEnvelope | None":
    return report.to_uncertainty_envelope()


__all__ = [
    "PanelObservationalData",
    "HTEObservationalData",
    "TimeSeriesCausalData",
    "TabularCausalDiscoveryData",
    "GraphCausalData",
    "GraphCausalDataV1",
    "SCMFitData",
    "SCMQueryData",
    "ParameterTransferData",
    "LLMStructuralHint",
    "LiteraturePriorBuildData",
    "GraphReconciliationData",
    "RDDObservationalData",
    "CausalEstimator",
    "CausalEffectReport",
    "envelope_from_report",
]
