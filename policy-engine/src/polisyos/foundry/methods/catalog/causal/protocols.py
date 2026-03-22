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


def _is_repeated_cross_section(metadata: Mapping[str, Any]) -> bool:
    shape = str(metadata.get("data_shape", "")).strip().lower()
    return shape in {"repeated_cross_section", "survey_repeated_cross_section", "survey_microdata"}


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
        if _is_repeated_cross_section(self.metadata):
            raise ValueError(
                "panel methods require dense panel data; received repeated cross-section/survey data. "
                "Route this payload to transport, survey, or HTE workflows instead."
            )
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


class TwinNetworkQueryData(BaseModel):
    """Input contract for causal.structural.twin_network.

    Specifies a Pearl twin-network query: given a factual observation of the
    system, compute the joint distribution of Y(x₀) and Y(x₁) by abducting
    the exogenous noise from the factual world and replaying under both
    interventions with the same noise realisation.
    """

    model_config = ConfigDict(extra="forbid")

    scm_spec: StructuralCausalModelSpec | dict[str, Any]
    """Fitted structural causal model (output of HybridSCMFit)."""

    factual_condition: dict[str, float] = Field(default_factory=dict)
    """Observed variable values used for abduction (the "factual world").

    Should include the treatment variable and any other observed variables.
    If empty, no abduction is performed and both arms sample fresh noise
    (equivalent to a purely interventional query).
    """

    treatment_variable: str
    """Name of the treatment node in the SCM graph."""

    factual_treatment_value: float
    """x₀ — the treatment value in the factual world (used for abduction)."""

    counterfactual_treatment_value: float
    """x₁ — the treatment value in the counterfactual world."""

    outcome_variable: str
    """Name of the outcome node whose ITE is computed: Y(x₁) − Y(x₀)."""

    n_samples: int = Field(default=2000, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scm_spec", mode="before")
    @classmethod
    def _coerce_scm_spec(cls, value: Any) -> StructuralCausalModelSpec:
        if isinstance(value, StructuralCausalModelSpec):
            return value
        if isinstance(value, dict):
            return StructuralCausalModelSpec.model_validate(value)
        raise ValueError("scm_spec must be StructuralCausalModelSpec or dict payload")

    @field_validator("treatment_variable", "outcome_variable")
    @classmethod
    def _validate_variable_name(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("variable names must be non-empty")
        return candidate

    @field_validator("factual_treatment_value", "counterfactual_treatment_value", mode="before")
    @classmethod
    def _coerce_treatment_value(cls, value: Any) -> Any:
        import math as _math
        casted = float(value)
        if not _math.isfinite(casted):
            raise ValueError("treatment values must be finite")
        return casted

    @field_validator("factual_condition", mode="before")
    @classmethod
    def _coerce_condition(cls, value: Any) -> Any:
        import math as _math
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("factual_condition must be a mapping")
        normalized: dict[str, float] = {}
        for key, raw in value.items():
            name = str(key).strip()
            if not name:
                raise ValueError("factual_condition keys must be non-empty")
            item = float(raw)
            if not _math.isfinite(item):
                raise ValueError("factual_condition values must be finite")
            normalized[name] = item
        return normalized

    @model_validator(mode="after")
    def _validate_payload(self) -> "TwinNetworkQueryData":
        nodes = set(self.scm_spec.graph.nodes)
        if self.treatment_variable not in nodes:
            raise ValueError(
                f"treatment_variable '{self.treatment_variable}' not in SCM graph nodes"
            )
        if self.outcome_variable not in nodes:
            raise ValueError(
                f"outcome_variable '{self.outcome_variable}' not in SCM graph nodes"
            )
        unknown = sorted(set(self.factual_condition) - nodes)
        if unknown:
            raise ValueError(
                f"factual_condition variables not in SCM graph nodes: {unknown}"
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


class UnifiedDiscoveryData(BaseModel):
    """Input contract for the unified causal discovery pipeline."""

    contract_id: ClassVar[str] = "foundry.causal.unified_discovery_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    data: Any  # shape: (n_obs, n_vars)
    variable_names: list[str]
    literature_prior: LiteratureCausalPrior | None = None
    llm_hints: list["LLMStructuralHint"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "UnifiedDiscoveryData":
        if not isinstance(self.data, np.ndarray) or self.data.ndim != 2:
            raise ValueError("data must be a 2D numpy array: (n_obs, n_vars)")
        if self.data.shape[0] < 2:
            raise ValueError("unified discovery data requires at least 2 observations")
        if self.data.shape[1] < 2:
            raise ValueError("unified discovery data requires at least 2 variables")
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


class NCMQueryData(BaseModel):
    """Input contract for NCMEngineMethod (causal.counterfactual.ncm_engine).

    Specifies an AAP (Abduction-Action-Prediction) counterfactual query:
    - ``evidence`` pins the factual world for abduction.
    - ``interventions`` is a list of K do(*) dicts defining K parallel worlds.
    - ``query_vars`` selects which variables to report in the output.

    When ``interventions`` is empty, one observational world is run.
    """

    model_config = ConfigDict(extra="forbid")

    ncm_spec: Any
    """Fitted or symbolic NCMSpec (output of NCM fit or manual construction).

    Accepts a :class:`~polisyos.ir.analytics.ncm.NCMSpec` instance or a
    JSON-serializable dict payload that will be coerced via the field validator.
    """

    evidence: dict[str, float] = Field(default_factory=dict)
    """Observed variable values used for abduction (the factual world).

    When empty, no abduction is performed and worlds sample fresh noise.
    """

    interventions: list[dict[str, float]] = Field(default_factory=list)
    """List of K intervention dicts {variable: value} — one per parallel world.

    E.g. ``[{"X": 0.0}, {"X": 1.0}]`` defines factual and counterfactual worlds.
    """

    query_vars: list[str] = Field(default_factory=list)
    """Variables to summarise in the output.  If empty, all variables are reported."""

    n_samples: int = Field(default=2000, ge=1)
    abduction_method: str = "exact"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ncm_spec", mode="before")
    @classmethod
    def _coerce_ncm_spec(cls, value: Any) -> Any:
        from polisyos.ir.analytics.ncm import NCMSpec as _NCMSpec
        if isinstance(value, _NCMSpec):
            return value
        if isinstance(value, dict):
            return _NCMSpec.model_validate(value)
        raise ValueError("ncm_spec must be NCMSpec or dict payload")

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, value: Any) -> dict[str, float]:
        import math as _math
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("evidence must be a mapping")
        out: dict[str, float] = {}
        for k, v in value.items():
            f = float(v)
            if not _math.isfinite(f):
                raise ValueError(f"evidence['{k}'] must be finite")
            out[str(k)] = f
        return out

    @model_validator(mode="after")
    def _validate_vars_in_spec(self) -> "NCMQueryData":
        from polisyos.ir.analytics.ncm import NCMSpec as _NCMSpec
        ncm = self.ncm_spec
        if not isinstance(ncm, _NCMSpec):
            return self

        # Build the set of known nodes
        known: set[str] = set(ncm.endogenous_vars)
        if ncm.scm_spec is not None:
            known |= set(ncm.scm_spec.graph.nodes)
        if not known:
            known = {eq.variable for eq in ncm.structural_equations}
            for eq in ncm.structural_equations:
                known.update(eq.parents)

        unknown_evidence = sorted(set(self.evidence) - known)
        if unknown_evidence and known:
            raise ValueError(
                f"NCMQueryData: evidence variables not in NCM: {unknown_evidence}"
            )

        for w_idx, interv in enumerate(self.interventions):
            unknown_interv = sorted(set(interv) - known)
            if unknown_interv and known:
                raise ValueError(
                    f"NCMQueryData: intervention[{w_idx}] variables not in NCM: {unknown_interv}"
                )
        return self


def envelope_from_report(report: CausalEffectReport) -> "UncertaintyEnvelope | None":
    return report.to_uncertainty_envelope()


class DynamicTreatmentData(BaseModel):
    """Data contract for time-varying treatment causal inference (g-methods, DTR, OPE).

    Represents an observational longitudinal dataset where each unit i is observed
    at T time points with time-varying binary treatment A_{i,t} and covariates L_{i,t}.

    Shapes:
        outcome              : (n_units,)                  — end-of-study Y_i
        treatment_sequence   : (n_units, n_periods)        — A_{i,0}, ..., A_{i,T-1}; binary
        covariate_sequence   : (n_units, n_periods, p)     — L_{i,t} at each period

    Used by: ParametricGFormula, ICEGFormula, LTMLEEstimator,
             StructuralNestedMeanModel, QLearningDTR, ALearningDTR,
             OutcomeWeightedLearning, DoublyRobustDTR, OffPolicyEvaluator, CausalBandit.
    """

    contract_id: ClassVar[str] = "foundry.causal.dynamic_treatment_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any  # shape: (n_units,)
    treatment_sequence: Any  # shape: (n_units, n_periods) — binary {0, 1}
    covariate_sequence: Any  # shape: (n_units, n_periods, n_covariates)

    time_ids: Any | None = None  # shape: (n_periods,)
    variable_names: list[str] | None = None  # names of covariate columns L_0, L_1, ...
    treatment_name: str = "A"
    outcome_name: str = "Y"
    # For OPE: observed action probabilities under behavior policy π_b
    behavior_policy_probs: Any | None = None  # shape: (n_units, n_periods)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "outcome",
        "treatment_sequence",
        "covariate_sequence",
        "time_ids",
        "behavior_policy_probs",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "DynamicTreatmentData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array: (n_units,)")
        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")

        n_units = self.outcome.shape[0]
        if n_units < 10:
            raise ValueError("DynamicTreatmentData requires at least 10 units")

        if (
            not isinstance(self.treatment_sequence, np.ndarray)
            or self.treatment_sequence.ndim != 2
        ):
            raise ValueError(
                "treatment_sequence must be a 2D numpy array: (n_units, n_periods)"
            )
        if self.treatment_sequence.shape[0] != n_units:
            raise ValueError(
                f"treatment_sequence has {self.treatment_sequence.shape[0]} units "
                f"but outcome has {n_units}"
            )
        n_periods = self.treatment_sequence.shape[1]
        if n_periods < 2:
            raise ValueError("DynamicTreatmentData requires at least 2 time periods")
        if not np.isin(self.treatment_sequence, [0, 1]).all():
            raise ValueError("treatment_sequence must be binary (0/1)")

        if (
            not isinstance(self.covariate_sequence, np.ndarray)
            or self.covariate_sequence.ndim != 3
        ):
            raise ValueError(
                "covariate_sequence must be a 3D numpy array: (n_units, n_periods, n_covariates)"
            )
        if self.covariate_sequence.shape[0] != n_units:
            raise ValueError(
                f"covariate_sequence has {self.covariate_sequence.shape[0]} units "
                f"but outcome has {n_units}"
            )
        if self.covariate_sequence.shape[1] != n_periods:
            raise ValueError(
                f"covariate_sequence has {self.covariate_sequence.shape[1]} periods "
                f"but treatment_sequence has {n_periods}"
            )
        if self.covariate_sequence.shape[2] < 1:
            raise ValueError("covariate_sequence must have at least 1 covariate")
        if not np.isfinite(self.covariate_sequence).all():
            raise ValueError("covariate_sequence contains non-finite values")

        if self.time_ids is not None:
            if not isinstance(self.time_ids, np.ndarray) or self.time_ids.ndim != 1:
                raise ValueError("time_ids must be a 1D array")
            if self.time_ids.shape[0] != n_periods:
                raise ValueError("time_ids length must match n_periods")

        if self.variable_names is not None:
            n_covariates = self.covariate_sequence.shape[2]
            if len(self.variable_names) != n_covariates:
                raise ValueError(
                    f"variable_names has {len(self.variable_names)} entries "
                    f"but covariate_sequence has {n_covariates} covariates"
                )

        if self.behavior_policy_probs is not None:
            if (
                not isinstance(self.behavior_policy_probs, np.ndarray)
                or self.behavior_policy_probs.ndim != 2
            ):
                raise ValueError(
                    "behavior_policy_probs must be a 2D array: (n_units, n_periods)"
                )
            if self.behavior_policy_probs.shape != (n_units, n_periods):
                raise ValueError(
                    f"behavior_policy_probs shape {self.behavior_policy_probs.shape} "
                    f"does not match ({n_units}, {n_periods})"
                )
            if not (
                np.all(self.behavior_policy_probs > 0)
                and np.all(self.behavior_policy_probs < 1)
            ):
                raise ValueError(
                    "behavior_policy_probs must be strictly in (0, 1)"
                )

        return self

    @field_serializer(
        "outcome",
        "treatment_sequence",
        "covariate_sequence",
        "time_ids",
        "behavior_policy_probs",
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
        return int(self.treatment_sequence.shape[1])

    @property
    def n_covariates(self) -> int:
        return int(self.covariate_sequence.shape[2])


class NetworkCausalData(BaseModel):
    """Causal data with explicit network structure for interference analysis.

    Supports adjacency matrix (Aronow & Samii style), cluster assignment
    (Hudgens & Halloran style), spatial coordinates, or bipartite edges.
    At least one of ``adjacency_matrix``, ``cluster_id``, ``coordinates``,
    or ``bipartite_edges`` must be provided.

    Shapes:
        outcome           : (n_units,)           — observed Y_i
        treatment         : (n_units,)            — binary {0, 1} A_i
        covariates        : (n_units, n_features) — optional pre-treatment X_i
        adjacency_matrix  : (n_units, n_units)    — W_ij = 1 if j is a neighbour of i
        cluster_id        : (n_units,)            — integer cluster membership
        coordinates       : (n_units, 2)          — spatial [x, y] or [lon, lat]
        bipartite_edges   : (n_edges, 2)          — [treatment_unit_idx, outcome_unit_idx]
        treatment_unit_ids: (n_treatment_units,)  — indices into outcome/treatment for tx units
    """

    contract_id: ClassVar[str] = "foundry.causal.network_causal_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any  # (n_units,)
    treatment: Any  # (n_units,) binary {0, 1}
    covariates: Any | None = None  # (n_units, n_features)

    adjacency_matrix: Any | None = None  # (n_units, n_units)
    cluster_id: Any | None = None  # (n_units,) int
    coordinates: Any | None = None  # (n_units, 2) or (n_units, 3)
    treatment_unit_ids: Any | None = None  # (n_treatment_units,) int
    bipartite_edges: Any | None = None  # (n_edges, 2) int

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome", "treatment", mode="before")
    @classmethod
    def _coerce_1d(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=float)

    @field_validator("covariates", "coordinates", "adjacency_matrix", mode="before")
    @classmethod
    def _coerce_2d_float(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=float)

    @field_validator("cluster_id", "treatment_unit_ids", "bipartite_edges", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=int)

    @model_validator(mode="after")
    def _validate_network_data(self) -> "NetworkCausalData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array: (n_units,)")
        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")

        n = self.outcome.shape[0]
        if n < 2:
            raise ValueError("NetworkCausalData requires at least 2 units")

        if not isinstance(self.treatment, np.ndarray) or self.treatment.ndim != 1:
            raise ValueError("treatment must be a 1D numpy array: (n_units,)")
        if self.treatment.shape[0] != n:
            raise ValueError(
                f"treatment length {self.treatment.shape[0]} does not match "
                f"outcome length {n}"
            )
        if not np.isin(self.treatment, [0.0, 1.0]).all():
            raise ValueError("treatment must be binary (0/1)")

        if self.covariates is not None:
            if self.covariates.ndim != 2:
                raise ValueError("covariates must be a 2D array: (n_units, n_features)")
            if self.covariates.shape[0] != n:
                raise ValueError(
                    f"covariates has {self.covariates.shape[0]} rows but "
                    f"outcome has {n} units"
                )

        if self.adjacency_matrix is not None:
            if self.adjacency_matrix.shape != (n, n):
                raise ValueError(
                    f"adjacency_matrix must be ({n}, {n}), "
                    f"got {self.adjacency_matrix.shape}"
                )

        if self.cluster_id is not None:
            if self.cluster_id.ndim != 1 or self.cluster_id.shape[0] != n:
                raise ValueError(
                    f"cluster_id must be a 1D array of length {n}"
                )

        if self.coordinates is not None:
            if self.coordinates.ndim != 2 or self.coordinates.shape[0] != n:
                raise ValueError(
                    f"coordinates must be (n_units, 2|3), got shape {self.coordinates.shape}"
                )
            if self.coordinates.shape[1] not in (2, 3):
                raise ValueError(
                    "coordinates second dimension must be 2 (2-D) or 3 (3-D)"
                )

        if self.bipartite_edges is not None:
            if self.bipartite_edges.ndim != 2 or self.bipartite_edges.shape[1] != 2:
                raise ValueError("bipartite_edges must be a 2D array of shape (n_edges, 2)")

        has_structure = any(
            x is not None
            for x in (
                self.adjacency_matrix,
                self.cluster_id,
                self.coordinates,
                self.bipartite_edges,
            )
        )
        if not has_structure:
            raise ValueError(
                "At least one of adjacency_matrix, cluster_id, coordinates, or "
                "bipartite_edges must be provided"
            )
        return self

    @field_serializer(
        "outcome",
        "treatment",
        "covariates",
        "adjacency_matrix",
        "cluster_id",
        "coordinates",
        "treatment_unit_ids",
        "bipartite_edges",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @property
    def n_units(self) -> int:
        return int(self.outcome.shape[0])

    @property
    def n_treated(self) -> int:
        return int(np.sum(self.treatment))

    @property
    def treatment_fraction(self) -> float:
        return float(np.mean(self.treatment))


# ---------------------------------------------------------------------------
# Phase-5: Extended protocol contracts
# ---------------------------------------------------------------------------


class StochasticInterventionData(BaseModel):
    """Data contract for stochastic and shift-intervention estimation.

    Supports both soft policies σ(X; π) (Correa & Bareinboim 2020) and
    modified treatment policies do(X + δ) (Díaz & van der Laan 2012).

    Shapes
    ------
    outcome          : (n_obs,)           — observed Y
    treatment        : (n_obs,)           — observed treatment A (continuous or discrete)
    covariates       : (n_obs, n_features) — pre-treatment covariates X
    policy_weights   : (n_obs,) optional  — pre-computed ratio π(A|X)/g(A|X)
    """

    contract_id: ClassVar[str] = "foundry.causal.stochastic_intervention_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any          # (n_obs,)
    treatment: Any        # (n_obs,)
    covariates: Any       # (n_obs, n_features)

    shift_delta: float | None = None
    """Additive shift δ for modified treatment policy A + δ."""

    policy_weights: Any | None = None
    """Pre-computed importance weights π(A|X)/g(A|X). Shape: (n_obs,).
    If provided, the estimation step uses these directly and skips GPS fitting."""

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome", "treatment", mode="before")
    @classmethod
    def _coerce_1d(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=float)

    @field_validator("covariates", mode="before")
    @classmethod
    def _coerce_2d(cls, v: Any) -> Any:
        if v is None:
            return v
        arr = np.asarray(v, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        return arr

    @field_validator("policy_weights", mode="before")
    @classmethod
    def _coerce_weights(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=float)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "StochasticInterventionData":
        outcome = np.asarray(self.outcome)
        treatment = np.asarray(self.treatment)
        covariates = np.asarray(self.covariates)

        if outcome.ndim != 1:
            raise ValueError("outcome must be 1D: (n_obs,)")
        n = len(outcome)
        if treatment.shape[0] != n:
            raise ValueError(
                f"treatment length {treatment.shape[0]} does not match outcome length {n}"
            )
        if covariates.shape[0] != n:
            raise ValueError(
                f"covariates first dimension {covariates.shape[0]} "
                f"does not match outcome length {n}"
            )
        if self.policy_weights is not None:
            pw = np.asarray(self.policy_weights)
            if pw.shape[0] != n:
                raise ValueError(
                    f"policy_weights length {pw.shape[0]} "
                    f"does not match outcome length {n}"
                )
        return self

    @field_serializer("outcome", "treatment", "covariates", "policy_weights")
    def _serialize_numpy(self, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @property
    def n_obs(self) -> int:
        return int(np.asarray(self.outcome).shape[0])


class ProxyMeasurementData(BaseModel):
    """Data contract for identification and estimation under measurement error.

    Used with :func:`identify_with_proxy` (graphical identification check)
    and with :class:`MeasurementErrorEstimator` (SIMEX / regression calibration).

    Shapes
    ------
    outcome                  : (n_obs,)             — observed Y
    treatment_proxy          : (n_obs,) or (n_obs, k) — proxy T* (mismeasured treatment)
    covariates               : (n_obs, p) optional   — additional covariates
    validation_true_treatment: (n_val,) optional     — T on a validation sub-sample
    validation_proxy         : (n_val,) optional     — T* on the same validation sub-sample
    """

    contract_id: ClassVar[str] = "foundry.causal.proxy_measurement_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any               # (n_obs,)
    treatment_proxy: Any       # (n_obs,) or (n_obs, k)
    covariates: Any | None = None           # (n_obs, p)
    validation_true_treatment: Any | None = None   # (n_val,)
    validation_proxy: Any | None = None    # (n_val,)

    error_variance: float | None = None
    """σ²_ε — known measurement error variance (for SIMEX)."""

    error_rate_bound: float | None = None
    """α — upper bound on classification error P(T* ≠ T) (for bounds method)."""

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome", "treatment_proxy", mode="before")
    @classmethod
    def _coerce_float(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=float)

    @field_validator(
        "covariates",
        "validation_true_treatment",
        "validation_proxy",
        mode="before",
    )
    @classmethod
    def _coerce_optional_float(cls, v: Any) -> Any:
        if v is None:
            return v
        return np.asarray(v, dtype=float)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "ProxyMeasurementData":
        Y = np.asarray(self.outcome)
        T_proxy = np.asarray(self.treatment_proxy)

        if Y.ndim != 1:
            raise ValueError("outcome must be 1D: (n_obs,)")
        n = len(Y)
        if T_proxy.shape[0] != n:
            raise ValueError(
                f"treatment_proxy first dimension {T_proxy.shape[0]} "
                f"does not match outcome length {n}"
            )
        if self.covariates is not None:
            cov = np.asarray(self.covariates)
            if cov.shape[0] != n:
                raise ValueError(
                    f"covariates first dimension {cov.shape[0]} "
                    f"does not match outcome length {n}"
                )
        if self.validation_true_treatment is not None:
            vt = np.asarray(self.validation_true_treatment)
            if vt.ndim != 1:
                raise ValueError("validation_true_treatment must be 1D")
        if self.error_variance is not None and self.error_variance < 0:
            raise ValueError("error_variance must be non-negative")
        if self.error_rate_bound is not None and not (0.0 <= self.error_rate_bound < 0.5):
            raise ValueError("error_rate_bound must be in [0, 0.5)")
        return self

    @field_serializer("outcome", "treatment_proxy", "covariates",
                      "validation_true_treatment", "validation_proxy")
    def _serialize_numpy(self, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @property
    def n_obs(self) -> int:
        return int(np.asarray(self.outcome).shape[0])

    @property
    def has_validation_data(self) -> bool:
        return self.validation_true_treatment is not None


# Resolve forward references for NCMQueryData (NCMSpec defined in separate module)
try:
    from polisyos.ir.analytics.ncm import NCMSpec as _NCMSpec  # noqa: F401
    NCMQueryData.model_rebuild()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Phase 6: Advanced Estimation — continuous / multi-valued treatment protocols
# ---------------------------------------------------------------------------


class ContinuousTreatmentData(BaseModel):
    """Data contract for continuous treatment dose-response estimation.

    Covers GPS (Hirano & Imbens 2004) and doubly-robust kernel
    dose-response (Kennedy et al. 2017).
    """

    contract_id: ClassVar[str] = "foundry.causal.continuous_treatment_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any          # ndarray (n_obs,)
    treatment: Any        # ndarray (n_obs,) — continuous float
    covariates: Any       # ndarray (n_obs, n_features)
    evaluation_points: Any | None = None  # ndarray (n_eval,) grid for β(t)
    feature_names: tuple[str, ...] | None = None

    @field_validator("outcome", "treatment", "covariates", "evaluation_points", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value, dtype=float)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "ContinuousTreatmentData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array")
        if not isinstance(self.treatment, np.ndarray) or self.treatment.ndim != 1:
            raise ValueError("treatment must be a 1D numpy array")
        if not isinstance(self.covariates, np.ndarray) or self.covariates.ndim != 2:
            raise ValueError("covariates must be a 2D numpy array")
        n = self.outcome.shape[0]
        if self.treatment.shape[0] != n:
            raise ValueError("treatment length must match outcome length")
        if self.covariates.shape[0] != n:
            raise ValueError("covariates row count must match outcome length")
        if n < 20:
            raise ValueError("continuous treatment data requires at least 20 observations")
        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")
        if not np.isfinite(self.treatment).all():
            raise ValueError("treatment contains non-finite values")
        if np.std(self.treatment) < 1e-10:
            raise ValueError("treatment has zero variance")
        if not np.isfinite(self.covariates).all():
            raise ValueError("covariates contains non-finite values")
        if self.evaluation_points is not None:
            ep = self.evaluation_points
            if not isinstance(ep, np.ndarray) or ep.ndim != 1:
                raise ValueError("evaluation_points must be a 1D array")
            if not np.isfinite(ep).all():
                raise ValueError("evaluation_points contains non-finite values")
        return self

    @field_serializer("outcome", "treatment", "covariates", "evaluation_points",
                      mode="plain", when_used="json")
    def _serialize_numpy(self, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @property
    def n_obs(self) -> int:
        return int(self.outcome.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.covariates.shape[1])


class DoseResponseResult(BaseModel):
    """Result of continuous treatment dose-response estimation.

    Contains β̂(t) = E[Y(t)] evaluated at a grid of treatment values.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    treatment_grid: Any       # ndarray (n_eval,)
    dose_response: Any        # ndarray (n_eval,) — β̂(t)
    confidence_band_lower: Any  # ndarray (n_eval,) — β̂(t) - 1.96·SE
    confidence_band_upper: Any  # ndarray (n_eval,) — β̂(t) + 1.96·SE
    standard_errors: Any      # ndarray (n_eval,)
    method: str
    n_obs: int
    bandwidth: float | None = None

    @field_validator("treatment_grid", "dose_response", "confidence_band_lower",
                     "confidence_band_upper", "standard_errors", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value, dtype=float)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "DoseResponseResult":
        n = self.treatment_grid.shape[0]
        for field_name, arr in [
            ("dose_response", self.dose_response),
            ("confidence_band_lower", self.confidence_band_lower),
            ("confidence_band_upper", self.confidence_band_upper),
            ("standard_errors", self.standard_errors),
        ]:
            if arr.shape[0] != n:
                raise ValueError(f"{field_name} length must match treatment_grid length")
        return self

    @field_serializer("treatment_grid", "dose_response", "confidence_band_lower",
                      "confidence_band_upper", "standard_errors",
                      mode="plain", when_used="json")
    def _serialize_numpy(self, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @property
    def n_eval(self) -> int:
        return int(self.treatment_grid.shape[0])


class MultiTreatmentData(BaseModel):
    """Data contract for multi-valued treatment estimation.

    Supports K >= 2 treatment arms (Imbens 2000, Cattaneo 2010).
    """

    contract_id: ClassVar[str] = "foundry.causal.multi_treatment_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any           # ndarray (n_obs,)
    treatment: Any         # ndarray (n_obs,) integer labels 0..K-1
    covariates: Any        # ndarray (n_obs, n_features)
    treatment_levels: tuple[int, ...] | None = None  # auto-detected if None
    reference_level: int = 0
    feature_names: tuple[str, ...] | None = None

    @field_validator("outcome", "covariates", mode="before")
    @classmethod
    def _coerce_float(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value, dtype=float)

    @field_validator("treatment", mode="before")
    @classmethod
    def _coerce_int(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value, dtype=int)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "MultiTreatmentData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array")
        if not isinstance(self.treatment, np.ndarray) or self.treatment.ndim != 1:
            raise ValueError("treatment must be a 1D numpy array")
        if not isinstance(self.covariates, np.ndarray) or self.covariates.ndim != 2:
            raise ValueError("covariates must be a 2D numpy array")
        n = self.outcome.shape[0]
        if self.treatment.shape[0] != n:
            raise ValueError("treatment length must match outcome length")
        if self.covariates.shape[0] != n:
            raise ValueError("covariates row count must match outcome length")
        if n < 20:
            raise ValueError("multi-treatment data requires at least 20 observations")
        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")
        if not np.isfinite(self.covariates).all():
            raise ValueError("covariates contains non-finite values")
        levels = sorted(int(x) for x in np.unique(self.treatment).tolist())
        if len(levels) < 2:
            raise ValueError("treatment must have at least 2 distinct levels")
        if self.treatment_levels is not None:
            unknown = set(levels) - set(self.treatment_levels)
            if unknown:
                raise ValueError(f"treatment contains levels not in treatment_levels: {unknown}")
        if self.reference_level not in levels:
            raise ValueError(
                f"reference_level {self.reference_level} not in treatment levels {levels}"
            )
        return self

    @field_serializer("outcome", "treatment", "covariates", mode="plain", when_used="json")
    def _serialize_numpy(self, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @property
    def n_obs(self) -> int:
        return int(self.outcome.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.covariates.shape[1])

    @property
    def levels(self) -> list[int]:
        if self.treatment_levels is not None:
            return sorted(self.treatment_levels)
        return sorted(int(x) for x in np.unique(self.treatment).tolist())


class MultiTreatmentResult(BaseModel):
    """Result of multi-valued treatment effect estimation.

    Contains arm-level potential outcome means, ATEs vs reference,
    and all pairwise contrasts.
    """

    model_config = ConfigDict(extra="forbid")

    levels: tuple[int | str, ...]
    arm_means: dict[str, float]                          # E[Y(k)] per arm
    ate_vs_reference: dict[str, float]                   # E[Y(k)] - E[Y(ref)]
    standard_errors: dict[str, float]
    confidence_intervals: dict[str, tuple[float, float]]  # 95% CI per arm
    pairwise_contrasts: dict[str, float]                 # "k1_vs_k2" → ATE
    n_obs_per_arm: dict[str, int]
    method: str


class FairnessObservationalData(BaseModel):
    """Observational data contract for causal fairness analysis.

    Used by:
    - ``TVFairnessDecomposer``: TV = DE + IE + SE decomposition
    - ``PathSpecificFairnessEstimator``: path-specific fairness criteria
    - ``CounterfactualFairnessEstimator``: counterfactual fairness test

    Fields
    ------
    outcome     : (n_obs,) — decision or label being audited (binary or continuous)
    protected   : (n_obs,) — sensitive/protected attribute (binary {0,1} or categorical)
    covariates  : (n_obs, n_features) — background context variables
    mediators   : (n_obs, n_mediators) — optional mediating variables on causal paths
    graph_dot   : DOT-format causal graph; required for path-specific and counterfactual methods
    """

    contract_id: ClassVar[str] = "foundry.causal.fairness_observational_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome: Any  # shape: (n_obs,)
    protected: Any  # shape: (n_obs,)
    covariates: Any  # shape: (n_obs, n_features)
    mediators: Any | None = None  # shape: (n_obs, n_mediators)
    graph_dot: str | None = None
    feature_names: list[str] | None = None
    mediator_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome", "protected", "covariates", "mediators", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "FairnessObservationalData":
        if not isinstance(self.outcome, np.ndarray) or self.outcome.ndim != 1:
            raise ValueError("outcome must be a 1D numpy array (n_obs,)")
        if not isinstance(self.protected, np.ndarray) or self.protected.ndim != 1:
            raise ValueError("protected must be a 1D numpy array (n_obs,)")
        if not isinstance(self.covariates, np.ndarray) or self.covariates.ndim != 2:
            raise ValueError("covariates must be a 2D numpy array (n_obs, n_features)")

        n_obs = self.outcome.shape[0]
        if n_obs < 30:
            raise ValueError(f"Fairness analysis requires at least 30 observations; got {n_obs}")
        if self.protected.shape[0] != n_obs:
            raise ValueError("protected length must match outcome length")
        if self.covariates.shape[0] != n_obs:
            raise ValueError("covariates row count must match outcome length")
        if self.covariates.shape[1] < 1:
            raise ValueError("covariates must contain at least one feature")

        if not np.isfinite(self.outcome).all():
            raise ValueError("outcome contains non-finite values")
        if not np.isfinite(self.covariates).all():
            raise ValueError("covariates contains non-finite values")

        if self.mediators is not None:
            if self.mediators.ndim == 1:
                object.__setattr__(self, "mediators", self.mediators.reshape(-1, 1))
            if self.mediators.shape[0] != n_obs:
                raise ValueError("mediators row count must match outcome length")
            if not np.isfinite(self.mediators).all():
                raise ValueError("mediators contains non-finite values")

        if (
            self.feature_names is not None
            and len(self.feature_names) != self.covariates.shape[1]
        ):
            raise ValueError("feature_names length must match covariates column count")

        if (
            self.mediator_names is not None
            and self.mediators is not None
            and len(self.mediator_names) != self.mediators.shape[1]
        ):
            raise ValueError("mediator_names length must match mediators column count")

        return self

    @field_serializer("outcome", "protected", "covariates", "mediators", mode="plain", when_used="json")
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

    @property
    def n_mediators(self) -> int:
        return int(self.mediators.shape[1]) if self.mediators is not None else 0


class MissingDataCausalData(BaseModel):
    """Input contract for missing data causal inference via M-graphs.

    Wraps the observed (incomplete) data matrix and the corresponding
    R-indicator matrix for use with the RecoverabilityEngine and
    ``CausalEngine.identify_with_missing_data()``.

    Phase-2/10 addition per Mohan & Pearl (2021).
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    contract_id: ClassVar[str] = "foundry.causal.missing_data_causal_data.v1"

    observed_data: np.ndarray
    """(n_obs, n_vars) float array with NaN for missing values."""

    missingness_indicators: np.ndarray
    """(n_obs, n_vars) binary int array: R[i,j]=1 if X_j is observed for unit i."""

    variable_names: tuple[str, ...]
    """Variable names corresponding to columns of observed_data."""

    treatment: str
    """Treatment variable name X."""

    outcome: str
    """Outcome variable name Y."""

    @model_validator(mode="after")
    def _check_shapes(self) -> "MissingDataCausalData":
        n, p = self.observed_data.shape
        if self.missingness_indicators.shape != (n, p):
            raise ValueError(
                f"missingness_indicators shape {self.missingness_indicators.shape} "
                f"must match observed_data shape ({n}, {p})"
            )
        if len(self.variable_names) != p:
            raise ValueError(
                f"variable_names length {len(self.variable_names)} must equal n_vars={p}"
            )
        return self

    @field_serializer("observed_data", "missingness_indicators", mode="plain", when_used="json")
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.observed_data.shape[0])

    @property
    def n_vars(self) -> int:
        return int(self.observed_data.shape[1])


__all__ = [
    "PanelObservationalData",
    "HTEObservationalData",
    "TimeSeriesCausalData",
    "TabularCausalDiscoveryData",
    "UnifiedDiscoveryData",
    "GraphCausalData",
    "GraphCausalDataV1",
    "SCMFitData",
    "SCMQueryData",
    "TwinNetworkQueryData",
    "ParameterTransferData",
    "LLMStructuralHint",
    "LiteraturePriorBuildData",
    "GraphReconciliationData",
    "RDDObservationalData",
    "CausalEstimator",
    "CausalEffectReport",
    "envelope_from_report",
    "NCMQueryData",
    "DynamicTreatmentData",
    "NetworkCausalData",
    # Phase-5 additions
    "StochasticInterventionData",
    "ProxyMeasurementData",
    # Phase-6 additions
    "ContinuousTreatmentData",
    "DoseResponseResult",
    "MultiTreatmentData",
    "MultiTreatmentResult",
    # Phase-8 additions
    "FairnessObservationalData",
    # Phase-9 additions
    "MultiStudyFusionData",
    "ExperimentDesignData",
    # Phase-10 additions
    "MissingDataCausalData",
]


# ---------------------------------------------------------------------------
# Phase-9: Data Fusion and Optimal Experimental Design protocols
# ---------------------------------------------------------------------------


class MultiStudyFusionData(BaseModel):
    """Input contract for multi-study data fusion.

    Wraps a list of FusionDataset descriptors and the shared causal graph
    for the ``DataFusionEngine`` foundry method.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    contract_id: ClassVar[str] = "foundry.causal.multi_study_fusion_data.v1"

    datasets: list[dict]
    """List of dicts matching the FusionDataset schema (dataset_ref, domain_id,
    n_obs, available_interventions, selection_bias_vars, quality_score)."""

    graph: CausalGraphModel
    """Base causal DAG shared across all source domains."""

    treatment: str
    """Treatment variable X for the target query P*(Y|do(X))."""

    outcome: str
    """Outcome variable Y for the target query."""


class ExperimentDesignData(BaseModel):
    """Input contract for optimal experimental design.

    Wraps the causal graph and cost information for the
    ``CausalExperimentDesigner`` foundry method.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    contract_id: ClassVar[str] = "foundry.causal.experiment_design_data.v1"

    graph: CausalGraphModel
    """Causal DAG for graphical design computations."""

    treatment: str
    """Treatment variable X."""

    outcome: str
    """Outcome variable Y."""

    available_interventions: dict[str, float] = Field(default_factory=dict)
    """Mapping variable_name → cost of intervening on that variable.
    Used for minimum-cost identification."""
