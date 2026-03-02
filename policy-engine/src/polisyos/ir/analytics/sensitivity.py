from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CausalSensitivityResultRef


class EValueResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_effect: float
    rr_equivalent: float = Field(gt=0.0)
    method: str = Field(min_length=1)
    ci_rr: tuple[float, float] | None = None
    ci_crosses_null: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> "EValueResult":
        if not math.isfinite(self.raw_effect):
            raise ValueError("raw_effect must be finite")
        if not math.isfinite(self.rr_equivalent):
            raise ValueError("rr_equivalent must be finite")
        if self.ci_rr is not None:
            lo, hi = self.ci_rr
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise ValueError("ci_rr bounds must be finite")
            if lo <= 0 or hi <= 0:
                raise ValueError("ci_rr bounds must be > 0")
            if lo > hi:
                raise ValueError("ci_rr lower bound cannot exceed upper bound")
        return self


class SensitivityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    e_value: float | None = None
    e_value_ci_lower: float | None = None
    conversion_method: str | None = None
    e_value_result: EValueResult | None = None

    robustness_value: float | None = None
    partial_r2_treatment: float | None = None

    rosenbaum_gamma: float | None = None
    rosenbaum_p_value: float | None = None

    interpretation: str = ""
    is_robust: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> "SensitivityResult":
        for field in (
            "e_value",
            "e_value_ci_lower",
            "robustness_value",
            "partial_r2_treatment",
            "rosenbaum_gamma",
            "rosenbaum_p_value",
        ):
            value = getattr(self, field)
            if value is None:
                continue
            if not math.isfinite(value):
                raise ValueError(f"{field} must be finite")

        if self.e_value is not None and self.e_value < 1.0:
            raise ValueError("E-value must be >= 1.0")
        if self.e_value_ci_lower is not None and self.e_value_ci_lower < 1.0:
            raise ValueError("E-value CI lower must be >= 1.0")
        if self.partial_r2_treatment is not None and not (0.0 <= self.partial_r2_treatment <= 1.0):
            raise ValueError("partial_r2_treatment must be in [0,1]")
        if self.rosenbaum_p_value is not None and not (0.0 <= self.rosenbaum_p_value <= 1.0):
            raise ValueError("rosenbaum_p_value must be in [0,1]")
        return self


def persist_sensitivity_result(
    store: ArtifactStore,
    result: SensitivityResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.sensitivity_result",
    schema_version: str = "1.0",
) -> CausalSensitivityResultRef:
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.sensitivity_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalSensitivityResultRef.model_validate(ref)


def load_sensitivity_result(
    store: ArtifactStore,
    ref: CausalSensitivityResultRef,
) -> SensitivityResult:
    payload = get_json_artifact(store, ref.artifact_id)
    return SensitivityResult.model_validate(payload)


__all__ = [
    "EValueResult",
    "SensitivityResult",
    "persist_sensitivity_result",
    "load_sensitivity_result",
]
