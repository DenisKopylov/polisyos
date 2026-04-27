"""Contracts for dependent-input global sensitivity analysis.

The DC-SAFE contract makes the joint input distribution explicit and keeps the
three contribution modes together: full dependent, marginal-reference, and the
structural/dependence delta between them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.refs import ArtifactRefModel

CopulaFamily = Literal[
    "product",
    "gaussian",
    "student_t",
    "clayton",
    "gumbel",
    "frank",
    "vine",
    "empirical",
    "custom",
]
StructuralClaimLevel = Literal["distributional", "ordered_generating", "causal"]
ContributionMode = Literal[
    "full",
    "marginal_reference",
    "structural_delta",
    "edge_structural",
    "latent_innovation",
]
DependentEstimatorFamily = Literal[
    "dependent_shapley_copula",
    "dependent_sobol_copula",
    "copula_edge_shapley",
    "latent_morris",
    "latent_dgsm",
    "knn_shapley_data",
]


def _to_camel(value: str) -> str:
    parts = value.rstrip("_").split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


class DependentSensitivityModel(KernelModel):
    """Base model accepting both Pythonic snake_case and bundle camelCase keys."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        alias_generator=_to_camel,
    )


class Estimate(DependentSensitivityModel):
    """Scalar estimate with optional uncertainty metadata."""

    value: float
    normalized: float | None = None
    standard_error: float | None = None
    ci: tuple[float, float] | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Estimate:
        if self.ci is not None and self.ci[0] > self.ci[1]:
            raise ValueError("ci lower bound cannot exceed upper bound")
        return self


class InputMarginalSpec(DependentSensitivityModel):
    """Marginal distribution for one sensitivity input."""

    family: Literal[
        "empirical",
        "normal",
        "lognormal",
        "beta",
        "gamma",
        "uniform",
        "categorical",
        "custom",
    ]
    parameters: dict[str, float] = Field(default_factory=dict)
    empirical_sample_ref: str | None = None
    support: tuple[float, float] | list[str]
    transform: Literal["identity", "log", "logit", "rank_normal_score"] = "identity"

    @model_validator(mode="after")
    def validate_support(self) -> InputMarginalSpec:
        if isinstance(self.support, tuple):
            lower, upper = self.support
            if lower > upper:
                raise ValueError("numeric support lower bound cannot exceed upper bound")
        elif not self.support:
            raise ValueError("categorical support cannot be empty")
        return self


class InputVariableSpec(DependentSensitivityModel):
    """Input exposed to dependent sensitivity analysis."""

    name: str = Field(..., min_length=1, max_length=120)
    dtype: Literal["continuous", "ordinal", "categorical", "binary"]
    role: Literal["policy", "behavioral", "demographic", "economic", "technical"] | None = None
    group: str | None = Field(default=None, min_length=1, max_length=120)
    marginal: InputMarginalSpec
    missing_policy: Literal["error", "impute", "drop", "model"] = "error"


class PairCopulaSpec(DependentSensitivityModel):
    """Pair-copula entry for vine or graph-structured copulas."""

    left: str = Field(..., min_length=1, max_length=120)
    right: str = Field(..., min_length=1, max_length=120)
    family: CopulaFamily
    parameters: dict[str, float] = Field(default_factory=dict)


class CopulaParameterSpec(DependentSensitivityModel):
    """Copula parameter payload."""

    correlation_matrix: list[list[float]] | None = None
    degrees_of_freedom: float | None = Field(default=None, gt=0.0)
    pair_copulas: list[PairCopulaSpec] = Field(default_factory=list)
    rank_correlation_matrix: list[list[float]] | None = None
    tail_dependence: dict[str, float] = Field(default_factory=dict)


class CopulaFitSpec(DependentSensitivityModel):
    """How a copula was fixed or fit."""

    method: Literal["fixed", "mle", "pseudo_likelihood", "rank_inversion", "bayesian"] = "fixed"
    data_ref: str | None = None
    uncertainty: Literal["none", "bootstrap", "posterior"] = "none"


class CopulaSupportPolicy(DependentSensitivityModel):
    """Policy for reference draws outside the observed support."""

    allow_product_reference_outside_observed_support: bool = False
    invalid_point_policy: Literal["error", "reject", "project", "penalize", "user_sampler"] = (
        "error"
    )


class CopulaSpec(DependentSensitivityModel):
    """Declared copula for a dependent-input sensitivity bundle."""

    id: str = Field(..., pattern=ID_PATTERN)
    family: CopulaFamily
    parameters: CopulaParameterSpec = Field(default_factory=CopulaParameterSpec)
    fit: CopulaFitSpec = Field(default_factory=CopulaFitSpec)
    support_policy: CopulaSupportPolicy = Field(default_factory=CopulaSupportPolicy)


class ReferenceCopulaSpec(CopulaSpec):
    """Reference dependence structure used for marginal-reference contribution."""

    reference_role: Literal["marginal_reference", "edge_baseline", "support_preserving"] = (
        "marginal_reference"
    )


class ConditionalSamplerSpec(DependentSensitivityModel):
    """Conditional sampler declared by the joint distribution contract."""

    type: Literal[
        "analytic_gaussian",
        "analytic_t",
        "inverse_rosenblatt",
        "inverse_nataf",
        "vine_h_function",
        "mcmc",
        "knn_empirical",
    ]
    exact: bool
    supports_coalitions: bool
    supports_groups: bool = False


class StructuralGraphEdgeSpec(DependentSensitivityModel):
    """One structural dependence edge in a graph or vine declaration."""

    from_: str | None = Field(default=None, alias="from", min_length=1, max_length=120)
    to: str | None = Field(default=None, min_length=1, max_length=120)
    undirected: tuple[str, str] | None = None
    copula_parameter_ref: str | None = None
    baseline: Literal["independence", "zero_correlation", "user_defined"] = "independence"

    @model_validator(mode="after")
    def validate_endpoint_mode(self) -> StructuralGraphEdgeSpec:
        directed = self.from_ is not None or self.to is not None
        if directed and not (self.from_ and self.to):
            raise ValueError("directed structural edges require both from and to")
        if directed == (self.undirected is not None):
            raise ValueError("structural edge must declare exactly one directed or undirected mode")
        return self


class StructuralGraphSpec(DependentSensitivityModel):
    """Optional graph giving stronger semantics to dependence claims."""

    claim_level: StructuralClaimLevel = "distributional"
    nodes: list[str] = Field(default_factory=list)
    edges: list[StructuralGraphEdgeSpec] = Field(default_factory=list)
    order: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=2000)


class JointInputDistributionSpec(DependentSensitivityModel):
    """Observed and reference copulas plus their conditional sampler."""

    observed_copula: CopulaSpec
    reference_copulas: list[ReferenceCopulaSpec] = Field(..., min_length=1)
    conditional_sampler: ConditionalSamplerSpec
    structural_graph: StructuralGraphSpec | None = None

    @model_validator(mode="after")
    def validate_reference_ids(self) -> JointInputDistributionSpec:
        ids = [copula.id for copula in self.reference_copulas]
        if len(ids) != len(set(ids)):
            raise ValueError("reference copula ids must be unique")
        return self


class DependentEstimatorBudgetSpec(DependentSensitivityModel):
    """Computation budget for dependent-input estimators."""

    joint_samples: int | None = Field(default=None, ge=1)
    conditional_pairs: int | None = Field(default=None, ge=1)
    inner_samples: int | None = Field(default=None, ge=1)
    permutations: int | None = Field(default=None, ge=1)
    bootstrap_replicates: int | None = Field(default=None, ge=0)
    qmc: bool = False


class DependentEstimatorUncertaintySpec(DependentSensitivityModel):
    """Uncertainty policy for one dependent estimator."""

    interval: Literal["none", "bootstrap", "asymptotic", "bayesian"] = "none"
    level: float = Field(default=0.95, gt=0.0, lt=1.0)
    include_copula_parameter_uncertainty: bool = False


class DependentEstimatorComputationalOptions(DependentSensitivityModel):
    """Execution options for dependent sensitivity estimators."""

    batching: bool = True
    cache_model_evaluations: bool = True
    common_random_numbers: bool = True
    surrogate: Literal["none", "gaussian_process", "random_forest", "pce"] = "none"


class DependentEstimatorSpec(DependentSensitivityModel):
    """Estimator requested by a dependent sensitivity bundle."""

    id: str = Field(..., pattern=ID_PATTERN)
    family: DependentEstimatorFamily
    target: Literal["variance", "mean", "quantile", "tail_probability", "welfare_loss", "custom"] = (
        "variance"
    )
    contribution_modes: list[ContributionMode] = Field(default_factory=lambda: ["full"])
    coalition_mode: Literal["inputs", "groups", "edges"] = "inputs"
    reference_copula_id: str | None = Field(default=None, pattern=ID_PATTERN)
    budget: DependentEstimatorBudgetSpec = Field(default_factory=DependentEstimatorBudgetSpec)
    uncertainty: DependentEstimatorUncertaintySpec = Field(
        default_factory=DependentEstimatorUncertaintySpec
    )
    computational_options: DependentEstimatorComputationalOptions = Field(
        default_factory=DependentEstimatorComputationalOptions
    )


class IdentifiabilityAssumptionSpec(DependentSensitivityModel):
    """Machine-readable identifiability posture for the bundle."""

    marginals_declared: bool = True
    observed_copula_declared: bool = True
    reference_copula_declared: bool = True
    conditional_sampler_declared: bool = True
    structural_claim_level: StructuralClaimLevel = "distributional"
    warnings: list[str] = Field(default_factory=list)


class DiagnosticSpec(DependentSensitivityModel):
    """Static diagnostics requested or already attached to a bundle."""

    copula_fit: dict[str, Any] = Field(default_factory=dict)
    dependence_matrix: list[list[float]] | None = None
    tail_dependence: dict[str, float] = Field(default_factory=dict)
    support_violations: int = Field(default=0, ge=0)
    conditional_sampler_checks: list[dict[str, Any]] = Field(default_factory=list)
    convergence: dict[str, Any] = Field(default_factory=dict)


class ReproducibilitySpec(DependentSensitivityModel):
    """Reproducibility metadata for a dependent sensitivity run."""

    seed: int = 42
    estimator_version: str = "dc-safe-linear-gaussian-1.0"
    model_hash: str | None = None
    input_distribution_hash: str | None = None
    run_timestamp: str | None = None


class OutputSpec(DependentSensitivityModel):
    """Scalar output target requested by a dependent sensitivity bundle."""

    name: str = Field(..., min_length=1, max_length=120)
    target: Literal["variance", "mean", "quantile", "tail_probability", "welfare_loss", "custom"] = (
        "variance"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependentSensitivityAnalysisBundle(DependentSensitivityModel):
    """First-class bundle contract for dependent and correlated inputs."""

    contract_version: Literal["2.0"] = "2.0"
    kind: Literal["dependent_copula_sensitivity"] = "dependent_copula_sensitivity"
    model: dict[str, Any] = Field(default_factory=dict)
    inputs: list[InputVariableSpec] = Field(..., min_length=1)
    joint_distribution: JointInputDistributionSpec
    estimators: list[DependentEstimatorSpec] = Field(..., min_length=1)
    outputs: list[OutputSpec] = Field(..., min_length=1)
    assumptions: IdentifiabilityAssumptionSpec = Field(
        default_factory=IdentifiabilityAssumptionSpec
    )
    diagnostics: DiagnosticSpec = Field(default_factory=DiagnosticSpec)
    reproducibility: ReproducibilitySpec = Field(default_factory=ReproducibilitySpec)

    @model_validator(mode="after")
    def validate_bundle_references(self) -> DependentSensitivityAnalysisBundle:
        input_names = [item.name for item in self.inputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError("input names must be unique")
        reference_ids = {copula.id for copula in self.joint_distribution.reference_copulas}
        for estimator in self.estimators:
            if estimator.reference_copula_id is not None and (
                estimator.reference_copula_id not in reference_ids
            ):
                raise ValueError(
                    f"unknown reference_copula_id: {estimator.reference_copula_id!r}"
                )
        return self


class DependentSensitivityIndex(DependentSensitivityModel):
    """Per-input dependent sensitivity result."""

    input: str
    group: str | None = None
    full: dict[str, Estimate] = Field(default_factory=dict)
    marginal_reference: dict[str, Any] = Field(default_factory=dict)
    structural_delta: dict[str, Any] = Field(default_factory=dict)
    latent_innovation: dict[str, Estimate] = Field(default_factory=dict)


class EdgeContribution(DependentSensitivityModel):
    """Edge-level structural dependence contribution."""

    edge: str
    contribution: Estimate
    normalized_contribution: Estimate
    interpretation: Literal["amplifies_variance", "dampens_variance", "near_zero"]


class DependentSensitivityResult(DependentSensitivityModel):
    """Result schema emitted by DC-SAFE estimators."""

    contract_version: Literal["2.0"] = "2.0"
    kind: Literal["dependent_copula_sensitivity"] = "dependent_copula_sensitivity"
    estimator_family: DependentEstimatorFamily = "dependent_shapley_copula"
    bundle_id: str | None = None
    output_name: str
    variance: dict[str, Any]
    indices: list[DependentSensitivityIndex]
    edge_contributions: list[EdgeContribution] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    identifiability: dict[str, Any] = Field(default_factory=dict)
    reproducibility: ReproducibilitySpec = Field(default_factory=ReproducibilitySpec)


class DependentSensitivityAnalysisBundleRef(ArtifactRefModel):
    """Stable handle for a persisted dependent sensitivity bundle."""

    kind: Literal["ir.dependent_sensitivity_bundle"] = "ir.dependent_sensitivity_bundle"
    media_type: Literal["application/json"] = "application/json"


class DependentSensitivityResultRef(ArtifactRefModel):
    """Stable handle for a persisted dependent sensitivity result."""

    kind: Literal["ir.dependent_sensitivity_result"] = "ir.dependent_sensitivity_result"
    media_type: Literal["application/json"] = "application/json"


def persist_dependent_sensitivity_bundle(
    store: ArtifactStore,
    bundle: DependentSensitivityAnalysisBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.dependent_sensitivity_bundle",
    schema_version: str = "2.0",
) -> DependentSensitivityAnalysisBundleRef:
    """Persist a dependent sensitivity bundle contract."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json", by_alias=True),
        kind="ir.dependent_sensitivity_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DependentSensitivityAnalysisBundleRef.model_validate(ref)


def load_dependent_sensitivity_bundle(
    store: ArtifactStore,
    ref: DependentSensitivityAnalysisBundleRef,
) -> DependentSensitivityAnalysisBundle:
    """Load a persisted dependent sensitivity bundle contract."""

    payload = get_json_artifact(store, ref.artifact_id)
    return DependentSensitivityAnalysisBundle.model_validate(payload)


def persist_dependent_sensitivity_result(
    store: ArtifactStore,
    result: DependentSensitivityResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.dependent_sensitivity_result",
    schema_version: str = "2.0",
) -> DependentSensitivityResultRef:
    """Persist a dependent sensitivity result."""

    ref = put_json_artifact(
        store,
        result.model_dump(mode="json", by_alias=True),
        kind="ir.dependent_sensitivity_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DependentSensitivityResultRef.model_validate(ref)


def load_dependent_sensitivity_result(
    store: ArtifactStore,
    ref: DependentSensitivityResultRef,
) -> DependentSensitivityResult:
    """Load a persisted dependent sensitivity result."""

    payload = get_json_artifact(store, ref.artifact_id)
    return DependentSensitivityResult.model_validate(payload)


__all__ = [
    "ConditionalSamplerSpec",
    "ContributionMode",
    "CopulaFamily",
    "CopulaFitSpec",
    "CopulaParameterSpec",
    "CopulaSpec",
    "CopulaSupportPolicy",
    "DependentEstimatorBudgetSpec",
    "DependentEstimatorComputationalOptions",
    "DependentEstimatorFamily",
    "DependentEstimatorSpec",
    "DependentEstimatorUncertaintySpec",
    "DependentSensitivityAnalysisBundle",
    "DependentSensitivityAnalysisBundleRef",
    "DependentSensitivityIndex",
    "DependentSensitivityModel",
    "DependentSensitivityResult",
    "DependentSensitivityResultRef",
    "DiagnosticSpec",
    "EdgeContribution",
    "Estimate",
    "IdentifiabilityAssumptionSpec",
    "InputMarginalSpec",
    "InputVariableSpec",
    "JointInputDistributionSpec",
    "OutputSpec",
    "PairCopulaSpec",
    "ReferenceCopulaSpec",
    "ReproducibilitySpec",
    "StructuralClaimLevel",
    "StructuralGraphEdgeSpec",
    "StructuralGraphSpec",
    "load_dependent_sensitivity_bundle",
    "load_dependent_sensitivity_result",
    "persist_dependent_sensitivity_bundle",
    "persist_dependent_sensitivity_result",
]
