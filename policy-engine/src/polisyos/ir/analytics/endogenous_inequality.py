"""IR contract for causal inequality decomposition with endogenous group composition.

The contract records counterfactual-law estimates of the form F^{d,d'} together
with the induced decomposition of an inequality functional into compositional
and structural channels. The v1 surface is intentionally scoped to Theil-T and
the generalized-entropy family because both admit sharp moment maps.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._internal.validation import ensure_confidence_interval, ensure_finite_numeric
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    DistributionalBoundsBundle,
    DistributionalFunctional,
    DistributionalFunctionalParameters,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import EndogenousGroupInequalityDecompositionRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate
    from polisyos.ir.analytics.partial_identification import BoundsBundle
else:
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate
    from polisyos.ir.analytics.partial_identification import BoundsBundle

ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA = "ir.endogenous_group_inequality_decomposition"
ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA_VERSION = "1.0"


class CounterfactualLawLabel(str, Enum):
    """Canonical labels for the four law-composition combinations used in v1."""

    F_00 = "F_00"
    F_10 = "F_10"
    F_11 = "F_11"
    F_01 = "F_01"


class EndogenousGroupDecompositionStatus(str, Enum):
    """Declare whether the decomposition is point-identified, trimmed, or bounded."""

    IDENTIFIED = "identified"
    TRIMMED = "trimmed"
    BOUNDED = "bounded"
    BLOCKED = "blocked"


class ReferencePopulation(str, Enum):
    """Reference covariate law used when integrating over X."""

    POOLED_OBSERVED_X = "pooled_observed_x"
    OVERLAP_TRIMMED_POOLED_X = "overlap_trimmed_pooled_x"


class ScalarEstimandEstimate(BaseModel):
    """One scalar decomposition estimand with uncertainty and provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    point_estimate: float
    standard_error: float | None = Field(default=None, ge=0.0)
    confidence_interval: tuple[float, float] | None = None
    estimand_formula: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_estimate(self) -> ScalarEstimandEstimate:
        ensure_finite_numeric(self.point_estimate, field_name="point_estimate")
        if self.standard_error is not None:
            ensure_finite_numeric(self.standard_error, field_name="standard_error")
        if self.confidence_interval is not None:
            ensure_confidence_interval(
                self.confidence_interval,
                label="confidence_interval",
                point_estimate=self.point_estimate,
            )
        return self


class CounterfactualLawEstimate(BaseModel):
    """Estimated sharp moments and induced inequality value for one F^{d,d'} law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    law: CounterfactualLawLabel
    structure_from: Literal[0, 1]
    composition_from: Literal[0, 1]
    mean_estimate: float = Field(gt=0.0)
    transformed_moment_estimate: float
    inequality_estimate: float
    standard_error: float | None = Field(default=None, ge=0.0)
    confidence_interval: tuple[float, float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_law(self) -> CounterfactualLawEstimate:
        ensure_finite_numeric(self.mean_estimate, field_name="mean_estimate")
        ensure_finite_numeric(
            self.transformed_moment_estimate,
            field_name="transformed_moment_estimate",
        )
        ensure_finite_numeric(self.inequality_estimate, field_name="inequality_estimate")
        if self.standard_error is not None:
            ensure_finite_numeric(self.standard_error, field_name="standard_error")
        if self.confidence_interval is not None:
            ensure_confidence_interval(
                self.confidence_interval,
                label="confidence_interval",
                point_estimate=self.inequality_estimate,
            )
        if int(self.structure_from) != int(self.law.value[2]):
            raise ValueError("structure_from must match the first law index")
        if int(self.composition_from) != int(self.law.value[3]):
            raise ValueError("composition_from must match the second law index")
        return self


class EndogenousGroupInequalityDecompositionResult(BaseModel):
    """Typed result for decomposition of inequality under endogenous groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    theorem_family: str = Field(
        default="interventional_endogenous_group_decomposition_v1",
        min_length=1,
    )
    functional: DistributionalFunctional
    functional_parameters: DistributionalFunctionalParameters | None = None
    reference_population: ReferencePopulation = ReferencePopulation.POOLED_OBSERVED_X
    status: EndogenousGroupDecompositionStatus
    laws: tuple[CounterfactualLawEstimate, ...] = ()
    total_effect: ScalarEstimandEstimate | None = None
    compositional_effect: ScalarEstimandEstimate | None = None
    structural_effect: ScalarEstimandEstimate | None = None
    shapley_compositional_effect: ScalarEstimandEstimate | None = None
    shapley_structural_effect: ScalarEstimandEstimate | None = None
    overlap_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    retained_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    assumption_cards: tuple[CausalAssumptionCard, ...] = ()
    bounds_bundle: BoundsBundle | None = None
    distributional_bounds_bundle: DistributionalBoundsBundle | None = None
    negative_certificate: NegativeCertificate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_result(self) -> EndogenousGroupInequalityDecompositionResult:
        allowed_functionals = {
            DistributionalFunctional.THEIL_T,
            DistributionalFunctional.GENERALIZED_ENTROPY,
        }
        if self.functional not in allowed_functionals:
            raise ValueError(
                "functional must be one of {theil_t, generalized_entropy} for this contract"
            )
        if self.functional is DistributionalFunctional.GENERALIZED_ENTROPY and (
            self.functional_parameters is None
            or self.functional_parameters.generalized_entropy_alpha is None
        ):
            raise ValueError(
                "generalized_entropy requires functional_parameters.generalized_entropy_alpha"
            )

        law_labels = [law.law for law in self.laws]
        if len(set(law_labels)) != len(law_labels):
            raise ValueError("laws must not contain duplicate labels")

        if self.status in {
            EndogenousGroupDecompositionStatus.IDENTIFIED,
            EndogenousGroupDecompositionStatus.TRIMMED,
        }:
            required_laws = {
                CounterfactualLawLabel.F_00,
                CounterfactualLawLabel.F_10,
                CounterfactualLawLabel.F_11,
            }
            if not required_laws.issubset(set(law_labels)):
                raise ValueError("identified/trimmed results require F_00, F_10, and F_11")
            if (
                self.total_effect is None
                or self.compositional_effect is None
                or self.structural_effect is None
            ):
                raise ValueError(
                    "identified/trimmed results require total, compositional, and structural effects"
                )
        if (
            self.shapley_compositional_effect is not None
            or self.shapley_structural_effect is not None
        ) and CounterfactualLawLabel.F_01 not in set(law_labels):
            raise ValueError("Shapley effects require the F_01 counterfactual law")
        if self.status is EndogenousGroupDecompositionStatus.BOUNDED:
            if (
                self.bounds_bundle is None
                and self.distributional_bounds_bundle is None
                and self.negative_certificate is None
            ):
                raise ValueError(
                    "bounded results require bounds_bundle, distributional_bounds_bundle, or negative_certificate"
                )
        if (
            self.status is EndogenousGroupDecompositionStatus.BLOCKED
            and self.negative_certificate is None
        ):
            raise ValueError("blocked results require negative_certificate")
        return self


def persist_endogenous_group_inequality_decomposition_result(
    store: ArtifactStore,
    result: EndogenousGroupInequalityDecompositionResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA,
    schema_version: str = ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA_VERSION,
) -> EndogenousGroupInequalityDecompositionRef:
    """Persist an endogenous-group inequality decomposition as a typed JSON artifact."""

    ref = put_json_artifact(
        store,
        result.model_dump(mode="json", round_trip=True),
        kind=ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EndogenousGroupInequalityDecompositionRef.model_validate(ref)


def load_endogenous_group_inequality_decomposition_result(
    store: ArtifactStore,
    ref: EndogenousGroupInequalityDecompositionRef,
) -> EndogenousGroupInequalityDecompositionResult:
    """Load an endogenous-group inequality decomposition from artifact storage."""

    payload = get_json_artifact(store, ref.artifact_id)
    return EndogenousGroupInequalityDecompositionResult.model_validate(payload)


__all__ = [
    "ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA",
    "ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION_SCHEMA_VERSION",
    "CounterfactualLawEstimate",
    "CounterfactualLawLabel",
    "EndogenousGroupDecompositionStatus",
    "EndogenousGroupInequalityDecompositionResult",
    "ReferencePopulation",
    "ScalarEstimandEstimate",
    "load_endogenous_group_inequality_decomposition_result",
    "persist_endogenous_group_inequality_decomposition_result",
]
