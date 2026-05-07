"""Typed RKHS/kernel lowering contracts for distributional and operator-valued causal estimation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import (
    DataReadinessReportRef,
    EstimandASTRef,
    KernelEstimatorSpecRef,
    OperatorEffectBundleRef,
    ProofBundleRef,
)

_KERNEL_ESTIMATOR_SPEC_SCHEMA_NAME = "ir.kernel_estimator_spec"
_KERNEL_ESTIMATOR_SPEC_SCHEMA_VERSION = "1.0"
_OPERATOR_EFFECT_BUNDLE_SCHEMA_NAME = "ir.operator_effect_bundle"
_OPERATOR_EFFECT_BUNDLE_SCHEMA_VERSION = "1.0"


class KernelEstimatorTemplate(str, Enum):
    """Supported template-level RKHS lowerings."""

    BACKDOOR_CME = "backdoor_cme"
    FRONTDOOR_CME = "frontdoor_cme"
    TRANSPORT_CME = "transport_cme"
    DR_CME = "dr_cme"
    KIV = "kiv"
    PROXIMAL_MINIMAX = "proximal_minimax"


class KernelTargetRepresentation(str, Enum):
    """Which kernel object the lowering targets."""

    MEAN_EMBEDDING = "mean_embedding"
    EFFECT_OPERATOR = "effect_operator"
    DISTRIBUTION_DIFFERENCE = "distribution_difference"


class KernelRegularizationScheme(str, Enum):
    """Regularization family used by the kernel estimator."""

    RIDGE = "ridge"


class KernelRegularizationSelection(str, Enum):
    """How regularization strength is chosen."""

    CV = "cv"
    FIXED_SCHEDULE = "fixed_schedule"
    STABILITY_GUARDED_CV = "stability_guarded_cv"


class KernelConsistencyClaim(str, Enum):
    """Strength of the claim justified by the lowering configuration."""

    RKHS_NORM = "rkhs_norm"
    UNIFORM = "uniform"
    NONE = "none"


class OperatorEstimatorFamily(str, Enum):
    """Supported operator-valued estimator backends."""

    CME_KRR = "cme_krr"
    OPERATOR_R_LEARNER = "operator_r_learner"
    KIV = "kiv"
    PROXIMAL_MINIMAX = "proximal_minimax"


class OperatorConvergenceGuarantee(BaseModel):
    """Claim carried with an operator-valued estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    guarantee_type: str = Field(default="induced_operator", min_length=1)
    norm_kind: str = Field(default="hy_to_l2_pv", min_length=1)
    rate_symbol: str | None = None
    rate_statement: str | None = None
    theorem_family: str | None = None
    assumptions: tuple[str, ...] = ()
    notes: str | None = None


class OperatorProbeExport(BaseModel):
    """Finite probe application exported for audit and downstream replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_ref: str = Field(min_length=1)
    label: str | None = None
    evaluation_points_ref: str | None = None
    codomain_axis: tuple[str, ...] = ()
    values: tuple[float, ...] = ()
    summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shape(self) -> OperatorProbeExport:
        if self.codomain_axis and len(self.codomain_axis) != len(self.values):
            raise ValueError("operator probe export codomain_axis must align with values")
        return self


class KernelLoweringDisposition(str, Enum):
    """Whether lowering is fully supported, downgraded, or blocked."""

    READY = "ready"
    REPRESENTATION_ONLY = "representation_only"
    PROOF_ONLY = "proof_only"
    UNSUPPORTED = "unsupported_for_kernel_translation"


class KernelSpec(BaseModel):
    """Kernel semantics needed for causal distributional claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    characteristic: bool = True
    weak_metrizing: bool = False


class KernelRegularization(BaseModel):
    """Regularization policy for kernel estimators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scheme: KernelRegularizationScheme = KernelRegularizationScheme.RIDGE
    selection: KernelRegularizationSelection = KernelRegularizationSelection.STABILITY_GUARDED_CV
    lambda_value: float = Field(default=5.0e-2, gt=0.0)
    lambda_schedule: tuple[float, ...] = (5.0e-3, 5.0e-2, 5.0e-1)
    cross_fit_folds: int | None = Field(default=None, ge=2, le=20)

    @model_validator(mode="after")
    def _validate_schedule(self) -> KernelRegularization:
        schedule = tuple(float(value) for value in self.lambda_schedule)
        if not schedule:
            raise ValueError("kernel regularization requires a non-empty lambda_schedule")
        if any(value <= 0.0 for value in schedule):
            raise ValueError("kernel regularization lambda_schedule must be strictly positive")
        if self.lambda_value <= 0.0:
            raise ValueError("kernel regularization lambda_value must be strictly positive")
        return self


class KernelNuisanceSpec(BaseModel):
    """Nuisance component emitted by the kernel lowering pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1)
    method_hint: str = Field(min_length=1)
    required: bool = True
    diagnostics: tuple[str, ...] = ()


class KernelEstimatorSpec(BaseModel):
    """Compilation-time contract for RKHS-backed causal estimation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    estimand_hash: str = Field(min_length=8)
    estimand_ref: EstimandASTRef | None = None
    proof_bundle_ref: ProofBundleRef | None = None
    template: KernelEstimatorTemplate
    target_representation: KernelTargetRepresentation
    lowering_disposition: KernelLoweringDisposition = KernelLoweringDisposition.READY
    output_kernel: KernelSpec
    input_kernels: dict[str, KernelSpec] = Field(default_factory=dict)
    regularization: KernelRegularization = Field(default_factory=KernelRegularization)
    variable_roles: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    required_side_conditions: tuple[str, ...] = ()
    nuisance_plan: tuple[KernelNuisanceSpec, ...] = ()
    diagnostics_plan: tuple[str, ...] = ()
    consistency_claim: KernelConsistencyClaim = KernelConsistencyClaim.RKHS_NORM
    blocking_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_blocking_consistency(self) -> KernelEstimatorSpec:
        if self.lowering_disposition is KernelLoweringDisposition.READY and self.blocking_reasons:
            raise ValueError("ready kernel lowering cannot carry blocking_reasons")
        if (
            self.lowering_disposition is not KernelLoweringDisposition.READY
            and not self.blocking_reasons
        ):
            raise ValueError("non-ready kernel lowering must explain blocking_reasons")
        if (
            self.target_representation
            in {
                KernelTargetRepresentation.MEAN_EMBEDDING,
                KernelTargetRepresentation.DISTRIBUTION_DIFFERENCE,
            }
            and not self.output_kernel.characteristic
            and self.lowering_disposition is KernelLoweringDisposition.READY
        ):
            raise ValueError(
                "distributional kernel lowering requires characteristic output_kernel or a downgraded disposition"
            )
        if "treatment" not in self.variable_roles or "outcome" not in self.variable_roles:
            raise ValueError("kernel lowering requires treatment and outcome variable roles")
        return self


class OperatorEffectBundle(BaseModel):
    """Persisted artifact describing an operator-valued causal effect estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    operator_ref: str = Field(min_length=1)
    estimand_hash: str = Field(min_length=8)
    estimand_ref: EstimandASTRef | None = None
    proof_bundle_ref: ProofBundleRef | None = None
    data_readiness_ref: DataReadinessReportRef | None = None
    probe_space_ref: str = Field(min_length=1)
    codomain_space_ref: str = Field(min_length=1)
    estimator_family: OperatorEstimatorFamily
    regularization: KernelRegularization = Field(default_factory=KernelRegularization)
    probe_basis: tuple[str, ...] = ()
    codomain_axis: tuple[str, ...] = ()
    operator_matrix: tuple[tuple[float, ...], ...] = ()
    operator_norm_error_bound: float | None = Field(default=None, ge=0.0)
    convergence_guarantee: OperatorConvergenceGuarantee | None = None
    applied_probe_exports: tuple[OperatorProbeExport, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_matrix(self) -> OperatorEffectBundle:
        if self.operator_matrix and not self.codomain_axis:
            raise ValueError(
                "operator effect bundle requires codomain_axis when operator_matrix is set"
            )
        if self.operator_matrix and not self.probe_basis:
            raise ValueError(
                "operator effect bundle requires probe_basis when operator_matrix is set"
            )
        if self.operator_matrix and len(self.operator_matrix) != len(self.codomain_axis):
            raise ValueError("operator_matrix row count must match codomain_axis length")
        expected_width = len(self.probe_basis)
        if self.operator_matrix and any(len(row) != expected_width for row in self.operator_matrix):
            raise ValueError("operator_matrix column count must match probe_basis length")
        export_probe_refs = [item.probe_ref for item in self.applied_probe_exports]
        if len(export_probe_refs) != len(set(export_probe_refs)):
            raise ValueError("applied_probe_exports must have unique probe_ref values")
        for export in self.applied_probe_exports:
            if (
                self.codomain_axis
                and export.codomain_axis
                and export.codomain_axis != self.codomain_axis
            ):
                raise ValueError("probe export codomain_axis must match bundle codomain_axis")
        return self


def persist_kernel_estimator_spec(
    store: ArtifactStore,
    spec: KernelEstimatorSpec,
    *,
    inputs: list[InputRef] | None = None,
) -> KernelEstimatorSpecRef:
    """Persist a ``KernelEstimatorSpec`` and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        spec.model_dump(mode="json"),
        kind="ir.kernel_estimator_spec",
        schema_name=_KERNEL_ESTIMATOR_SPEC_SCHEMA_NAME,
        schema_version=_KERNEL_ESTIMATOR_SPEC_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return KernelEstimatorSpecRef.model_validate(ref)


def load_kernel_estimator_spec(
    store: ArtifactStore,
    ref: KernelEstimatorSpecRef,
) -> KernelEstimatorSpec:
    """Load a persisted ``KernelEstimatorSpec``."""

    payload = get_json_artifact(store, ref.artifact_id)
    return KernelEstimatorSpec.model_validate(payload)


def persist_operator_effect_bundle(
    store: ArtifactStore,
    bundle: OperatorEffectBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> OperatorEffectBundleRef:
    """Persist an ``OperatorEffectBundle`` and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.operator_effect_bundle",
        schema_name=_OPERATOR_EFFECT_BUNDLE_SCHEMA_NAME,
        schema_version=_OPERATOR_EFFECT_BUNDLE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return OperatorEffectBundleRef.model_validate(ref)


def load_operator_effect_bundle(
    store: ArtifactStore,
    ref: OperatorEffectBundleRef,
) -> OperatorEffectBundle:
    """Load a persisted ``OperatorEffectBundle``."""

    payload = get_json_artifact(store, ref.artifact_id)
    return OperatorEffectBundle.model_validate(payload)


__all__ = [
    "KernelConsistencyClaim",
    "KernelEstimatorSpec",
    "KernelEstimatorTemplate",
    "KernelLoweringDisposition",
    "KernelNuisanceSpec",
    "KernelRegularization",
    "KernelRegularizationScheme",
    "KernelRegularizationSelection",
    "KernelSpec",
    "KernelTargetRepresentation",
    "OperatorConvergenceGuarantee",
    "OperatorEffectBundle",
    "OperatorEstimatorFamily",
    "OperatorProbeExport",
    "load_kernel_estimator_spec",
    "load_operator_effect_bundle",
    "persist_kernel_estimator_spec",
    "persist_operator_effect_bundle",
]
