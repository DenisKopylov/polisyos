from __future__ import annotations

from statistics import NormalDist
from typing import TYPE_CHECKING, Any, ClassVar, Mapping, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from polisyos.foundry.methods.base import MethodMetadata, MethodSignature
from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

if TYPE_CHECKING:
    import pandas as pd


_FLOAT_EPS = 1e-12


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class PanelData(BaseModel):
    """Validated panel data input for classical econometric estimators."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    dependent: Any  # shape: (n_obs,)
    exog: Any  # shape: (n_obs, n_features)
    entity_ids: Any  # shape: (n_obs,)
    time_ids: Any  # shape: (n_obs,)
    instrument_ids: Any | None = None  # shape: (n_obs, n_instruments)
    feature_names: list[str] | None = None
    instrument_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dependent", "exog", "entity_ids", "time_ids", "instrument_ids", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "PanelData":
        if not isinstance(self.dependent, np.ndarray) or self.dependent.ndim != 1:
            raise ValueError("dependent must be a 1D numpy array")
        if not isinstance(self.exog, np.ndarray) or self.exog.ndim != 2:
            raise ValueError("exog must be a 2D numpy array")
        if not isinstance(self.entity_ids, np.ndarray) or self.entity_ids.ndim != 1:
            raise ValueError("entity_ids must be a 1D numpy array")
        if not isinstance(self.time_ids, np.ndarray) or self.time_ids.ndim != 1:
            raise ValueError("time_ids must be a 1D numpy array")

        n_obs = self.dependent.shape[0]
        if self.exog.shape[0] != n_obs:
            raise ValueError("exog row count must match dependent length")
        if self.entity_ids.shape[0] != n_obs:
            raise ValueError("entity_ids length must match dependent length")
        if self.time_ids.shape[0] != n_obs:
            raise ValueError("time_ids length must match dependent length")
        if n_obs < 8:
            raise ValueError("panel data requires at least 8 observations")
        if self.exog.shape[1] < 1:
            raise ValueError("exog must contain at least one feature")

        if not np.isfinite(self.dependent).all() or not np.isfinite(self.exog).all():
            raise ValueError("dependent/exog contain non-finite values")

        n_entities = np.unique(self.entity_ids).size
        n_periods = np.unique(self.time_ids).size
        if n_entities < 2:
            raise ValueError("panel data requires at least 2 entities")
        if n_periods < 2:
            raise ValueError("panel data requires at least 2 time periods")

        if self.instrument_ids is not None:
            if not isinstance(self.instrument_ids, np.ndarray) or self.instrument_ids.ndim != 2:
                raise ValueError("instrument_ids must be a 2D numpy array")
            if self.instrument_ids.shape[0] != n_obs:
                raise ValueError("instrument_ids row count must match dependent length")
            if self.instrument_ids.shape[1] < 1:
                raise ValueError("instrument_ids must contain at least one instrument")
            if not np.isfinite(self.instrument_ids).all():
                raise ValueError("instrument_ids contain non-finite values")

        if self.feature_names is not None and len(self.feature_names) != self.exog.shape[1]:
            raise ValueError("feature_names length must match exog column count")
        if (
            self.instrument_ids is not None
            and self.instrument_names is not None
            and len(self.instrument_names) != self.instrument_ids.shape[1]
        ):
            raise ValueError("instrument_names length must match instrument_ids column count")

        return self

    @field_serializer("dependent", "exog", "entity_ids", "time_ids", "instrument_ids", mode="plain", when_used="json")
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.dependent.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.exog.shape[1])

    @property
    def n_entities(self) -> int:
        return int(np.unique(self.entity_ids).size)

    @property
    def n_periods(self) -> int:
        return int(np.unique(self.time_ids).size)

    @classmethod
    def from_dataframe(
        cls,
        df: "pd.DataFrame",
        *,
        dependent_col: str,
        exog_cols: list[str],
        entity_col: str,
        time_col: str,
        instrument_cols: list[str] | None = None,
    ) -> "PanelData":
        frame = df.copy()
        frame = frame.sort_values([entity_col, time_col])
        return cls(
            dependent=frame[dependent_col].to_numpy(dtype=float),
            exog=frame[exog_cols].to_numpy(dtype=float),
            entity_ids=frame[entity_col].to_numpy(),
            time_ids=frame[time_col].to_numpy(),
            instrument_ids=frame[instrument_cols].to_numpy(dtype=float)
            if instrument_cols
            else None,
            feature_names=list(exog_cols),
            instrument_names=list(instrument_cols or []),
        )


class TimeSeriesData(BaseModel):
    """Validated time-series input for ARIMA/VAR estimators."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    endog: Any  # shape: (T,) or (T, k)
    exog: Any | None = None  # shape: (T, m)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("endog", "exog", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "TimeSeriesData":
        if not isinstance(self.endog, np.ndarray) or self.endog.ndim not in {1, 2}:
            raise ValueError("endog must be 1D or 2D numpy array")
        if self.endog.shape[0] < 8:
            raise ValueError("time-series requires at least 8 observations")
        if not np.isfinite(self.endog).all():
            raise ValueError("endog contains non-finite values")

        if self.exog is not None:
            if not isinstance(self.exog, np.ndarray) or self.exog.ndim != 2:
                raise ValueError("exog must be a 2D numpy array")
            if self.exog.shape[0] != self.endog.shape[0]:
                raise ValueError("exog row count must match endog observations")
            if not np.isfinite(self.exog).all():
                raise ValueError("exog contains non-finite values")

        return self

    @field_serializer("endog", "exog", mode="plain", when_used="json")
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.endog.shape[0])


class EconometricResult(BaseModel):
    """Common output contract for econometric methods."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method_name: str
    params: dict[str, float] = Field(default_factory=dict)
    std_errors: dict[str, float] = Field(default_factory=dict)
    t_stats: dict[str, float] = Field(default_factory=dict)
    p_values: dict[str, float] = Field(default_factory=dict)
    confidence_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)

    r_squared: float | None = None
    adj_r_squared: float | None = None
    f_statistic: float | None = None
    f_pvalue: float | None = None
    n_obs: int = 0
    n_entities: int | None = None
    n_periods: int | None = None

    diagnostics: dict[str, Any] = Field(default_factory=dict)
    model_info: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_numerics(self) -> "EconometricResult":
        for bucket_name, bucket in (
            ("params", self.params),
            ("std_errors", self.std_errors),
            ("t_stats", self.t_stats),
            ("p_values", self.p_values),
        ):
            for key, value in bucket.items():
                if not np.isfinite(value):
                    raise ValueError(f"{bucket_name}.{key} must be finite")

        for key, interval in self.confidence_intervals.items():
            lo, hi = interval
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError(f"confidence_intervals.{key} must be finite")
            if lo > hi:
                raise ValueError(f"confidence_intervals.{key} lower must be <= upper")

        return self

    def to_uncertainty_envelope(
        self,
        param_name: str | None = None,
    ) -> UncertaintyEnvelope | None:
        if not self.params:
            return None

        name = param_name
        if name is None:
            non_const = [candidate for candidate in self.params if candidate.lower() != "const"]
            name = non_const[0] if non_const else next(iter(self.params))
        if name not in self.params:
            return None

        point = float(self.params[name])
        interval = self.confidence_intervals.get(name)
        if interval is None:
            se = self.std_errors.get(name)
            if se is None or se <= _FLOAT_EPS:
                return None
            z = NormalDist().inv_cdf((1.0 + self.confidence_level) / 2.0)
            interval = (point - z * se, point + z * se)

        lo, hi = float(interval[0]), float(interval[1])
        if lo > hi:
            lo, hi = hi, lo
        if point < lo:
            lo = point
        if point > hi:
            hi = point

        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(lo, hi),
            confidence_level=self.confidence_level,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=self.n_obs if self.n_obs > 0 else None,
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "econometric_method": self.method_name,
                "param_name": name,
                "r_squared": self.r_squared,
                "std_error": self.std_errors.get(name),
                "p_value": self.p_values.get(name),
            },
        )


@runtime_checkable
class EconometricEstimator(Protocol):
    signature: ClassVar[MethodSignature]
    metadata: ClassVar[MethodMetadata]

    @staticmethod
    def pure_step(
        state: PanelData | TimeSeriesData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Expected output keys:
        - result: EconometricResult
        - envelope: UncertaintyEnvelope | None
        """
        ...


__all__ = [
    "EconometricEstimator",
    "EconometricResult",
    "PanelData",
    "TimeSeriesData",
]
