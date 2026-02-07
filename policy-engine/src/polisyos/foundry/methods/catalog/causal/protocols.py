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
from polisyos.ir.causal import CausalEffectReport

if TYPE_CHECKING:
    import pandas as pd

    from polisyos.ir.uncertainty import UncertaintyEnvelope


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class PanelObservationalData(BaseModel):
    """Panel data used by SCM / DiD / Structural Time Series methods."""

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
        state: PanelObservationalData | RDDObservationalData,
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
    "RDDObservationalData",
    "CausalEstimator",
    "CausalEffectReport",
    "envelope_from_report",
]
