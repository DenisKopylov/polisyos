"""Design-of-experiments models for sensitivity studies, adversarial sweeps, and stress inputs."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .stress_report import admit_objective_threshold
from .uncertainty import SensitivityUncertaintyBundle, SensitivityUncertaintyConfig


class ScenarioSweep(BaseModel):
    """Scenario sweep public type."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[dict[Any, Any]] = Field(default_factory=list)


class AblationPlan(BaseModel):
    """List of mechanisms or components to remove when running ablation comparisons."""

    model_config = ConfigDict(extra="forbid")

    targets: list[str] = Field(default_factory=list)


class SensitivityMethod(StrEnum):
    """Sensitivity method public type."""

    MORRIS = "morris"
    SOBOL = "sobol"
    FAST = "fast"


class ParameterDist(StrEnum):
    """Parameter dist public type."""

    UNIFORM = "uniform"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    TRIANGULAR = "triangular"


class _DistributionSpecBase(BaseModel):
    """Version marker shared by typed SALib distribution specifications."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"


class UniformDistributionSpecV1(_DistributionSpecBase):
    """Explicit uniform distribution specification."""

    kind: Literal["uniform"] = "uniform"


class NormalDistributionSpecV1(_DistributionSpecBase):
    """Finite-support normal distribution specification."""

    kind: Literal["normal"] = "normal"
    mean: float
    std: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _validate_finite_parameters(self) -> NormalDistributionSpecV1:
        if not math.isfinite(self.mean) or not math.isfinite(self.std):
            raise ValueError("normal distribution mean and std must be finite")
        return self


class LognormalDistributionSpecV1(_DistributionSpecBase):
    """Log-space parameters reserved for a future bounded adapter."""

    kind: Literal["lognormal"] = "lognormal"
    log_mean: float
    log_std: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _validate_finite_parameters(self) -> LognormalDistributionSpecV1:
        if not math.isfinite(self.log_mean) or not math.isfinite(self.log_std):
            raise ValueError("lognormal log_mean and log_std must be finite")
        return self


class TriangularDistributionSpecV1(_DistributionSpecBase):
    """Finite-support triangular distribution specification."""

    kind: Literal["triangular"] = "triangular"
    mode_fraction: float = Field(ge=0.0, le=1.0)


DistributionSpecV1 = Annotated[
    UniformDistributionSpecV1
    | NormalDistributionSpecV1
    | LognormalDistributionSpecV1
    | TriangularDistributionSpecV1,
    Field(discriminator="kind"),
]


class RunFailurePolicy(StrEnum):
    """Policy for handling failed simulator runs inside a DOE batch."""

    FAIL_FAST = "fail_fast"
    DROP_FAILED = "drop_failed"
    IMPUTE_BASELINE = "impute_baseline"


class ParameterSpec(BaseModel):
    """Search-space definition for one tunable parameter in sensitivity or adversarial analysis."""

    model_config = ConfigDict(extra="forbid")

    name: str
    lower_bound: float
    upper_bound: float
    distribution: ParameterDist = ParameterDist.UNIFORM
    distribution_spec: DistributionSpecV1 | None = None
    baseline: float | None = None
    description: str = ""
    num_levels: int = Field(default=4, ge=2)

    @model_validator(mode="after")
    def _validate_bounds(self) -> ParameterSpec:
        if self.lower_bound >= self.upper_bound:
            raise ValueError(
                f"parameter '{self.name}' has invalid bounds: "
                f"{self.lower_bound} >= {self.upper_bound}"
            )
        if self.baseline is not None and not (
            self.lower_bound <= self.baseline <= self.upper_bound
        ):
            raise ValueError(
                f"parameter '{self.name}' baseline {self.baseline} is outside bounds "
                f"[{self.lower_bound}, {self.upper_bound}]"
            )
        if (
            self.distribution_spec is not None
            and self.distribution_spec.kind != self.distribution.value
        ):
            raise ValueError(
                f"parameter '{self.name}' distribution '{self.distribution.value}' does not match "
                f"distribution_spec.kind '{self.distribution_spec.kind}'"
            )
        return self


class SensitivityPlan(BaseModel):
    """Execution plan for Morris, Sobol, or FAST sensitivity analysis with runtime guardrails."""

    model_config = ConfigDict(extra="forbid")

    # Legacy field preserved for backward compatibility.
    parameters: list[str] = Field(default_factory=list)

    method: SensitivityMethod = SensitivityMethod.MORRIS
    parameter_specs: list[ParameterSpec] = Field(default_factory=list)
    n_trajectories: int = Field(default=10, ge=1)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    seed: int | None = None

    # Guardrails for expensive batches.
    max_estimated_runs: int = Field(default=1000, ge=1)
    allow_large_run: bool = False
    max_wall_time_sec: int | None = Field(default=None, ge=1)

    # Failure handling for partially failed simulations.
    run_failure_policy: RunFailurePolicy = RunFailurePolicy.FAIL_FAST
    min_success_rate: float = Field(default=0.9, gt=0.0, le=1.0)
    uncertainty: SensitivityUncertaintyConfig = Field(
        default_factory=SensitivityUncertaintyConfig,
    )

    @property
    def num_parameters(self) -> int:
        return len(self.parameter_specs)

    def estimated_runs_for(self, n_trajectories: int) -> int:
        """Estimate runs for a candidate trajectory count."""
        if n_trajectories < 1:
            raise ValueError("n_trajectories must be at least 1")
        k = self.num_parameters
        if k == 0:
            return 0
        if self.method == SensitivityMethod.MORRIS:
            return n_trajectories * (k + 1)
        if self.method == SensitivityMethod.SOBOL:
            return n_trajectories * (2 * k + 2)
        if self.method == SensitivityMethod.FAST:
            return n_trajectories * k
        return 0

    @property
    def estimated_runs(self) -> int:
        return self.estimated_runs_for(self.n_trajectories)

    @model_validator(mode="after")
    def _validate_plan(self) -> SensitivityPlan:
        if not self.parameter_specs and self.parameters:
            self.parameter_specs = [
                ParameterSpec(name=name, lower_bound=0.0, upper_bound=1.0)
                for name in self.parameters
            ]

        if not self.parameter_specs:
            raise ValueError("SensitivityPlan requires parameter_specs or legacy parameters")

        names = [item.name for item in self.parameter_specs]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate parameter names are not allowed in SensitivityPlan")

        if self.estimated_runs > self.max_estimated_runs and not self.allow_large_run:
            raise ValueError(
                "SensitivityPlan estimated_runs exceeds max_estimated_runs. "
                "Increase max_estimated_runs or set allow_large_run=true to override."
            )

        return self


def _derive_backend_seed(seed: int | None, stream: str) -> int | None:
    """Derive a stable backend seed for one logical DOE stream.

    A plan seed identifies the reproducible request.  Backend calls receive
    separate derived seeds so sampling and analyzer resampling do not consume
    a shared process-global stream or depend on call order.
    """
    if seed is None:
        return None
    payload = f"polisyos-doe-seed-v1:{seed}:{stream}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little") % (2**32)


_DOE_DISTRIBUTION_SCHEMA_VERSION = "doe-distribution-v1"
_SALIB_BACKEND_ID = "SALib@1.5.2"


def _salib_parameter_mapping(
    parameter: ParameterSpec,
) -> tuple[str, list[float]]:
    """Resolve one parameter to the pinned SALib distribution contract."""
    if not math.isfinite(parameter.lower_bound) or not math.isfinite(parameter.upper_bound):
        raise ValueError(f"parameter '{parameter.name}' requires finite physical bounds for SALib")

    lower = parameter.lower_bound
    upper = parameter.upper_bound
    spec = parameter.distribution_spec

    if parameter.distribution == ParameterDist.UNIFORM:
        return "unif", [lower, upper]

    if parameter.distribution == ParameterDist.NORMAL:
        if not isinstance(spec, NormalDistributionSpecV1):
            raise ValueError(
                f"parameter '{parameter.name}' uses legacy NORMAL bounds; "
                "an explicit DistributionSpecV1 with finite mean/std is required"
            )
        return "truncnorm", [lower, upper, spec.mean, spec.std]

    if parameter.distribution == ParameterDist.TRIANGULAR:
        if not isinstance(spec, TriangularDistributionSpecV1):
            raise ValueError(
                f"parameter '{parameter.name}' uses legacy TRIANGULAR bounds; "
                "an explicit DistributionSpecV1 with mode_fraction is required"
            )
        return "triang", [lower, upper, spec.mode_fraction]

    if parameter.distribution == ParameterDist.LOGNORMAL:
        if spec is None:
            raise ValueError(
                f"parameter '{parameter.name}' uses ambiguous legacy LOGNORMAL bounds; "
                "an explicit DistributionSpecV1 is required, and the bounded adapter is "
                "compatibility_pending"
            )
        raise ValueError(
            f"parameter '{parameter.name}' bounded LOGNORMAL sampling is compatibility_pending; "
            "no bounded adapter is admitted"
        )

    raise ValueError(f"Unsupported parameter distribution: {parameter.distribution}")


def _build_salib_problem(plan: SensitivityPlan) -> tuple[dict[str, object], str]:
    """Build the canonical bounded SALib problem and its mapping fingerprint."""
    names = [item.name for item in plan.parameter_specs]
    bounds: list[list[float]] = []
    dists: list[str] = []
    fingerprint_parameters: list[dict[str, object]] = []

    for parameter in plan.parameter_specs:
        salib_distribution, salib_bounds = _salib_parameter_mapping(parameter)
        bounds.append(salib_bounds)
        dists.append(salib_distribution)
        fingerprint_parameters.append(
            {
                "name": parameter.name,
                "distribution": parameter.distribution.value,
                "distribution_spec": (
                    parameter.distribution_spec.model_dump(mode="json")
                    if parameter.distribution_spec is not None
                    else None
                ),
                "salib_distribution": salib_distribution,
                "salib_bounds": salib_bounds,
            }
        )

    problem: dict[str, object] = {
        "num_vars": len(plan.parameter_specs),
        "names": names,
        "bounds": bounds,
    }
    if any(distribution != "unif" for distribution in dists):
        problem["dists"] = dists

    fingerprint_payload = {
        "schema_version": _DOE_DISTRIBUTION_SCHEMA_VERSION,
        "backend": _SALIB_BACKEND_ID,
        "method": plan.method.value,
        "parameters": fingerprint_parameters,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return problem, fingerprint


class SensitivityResult(BaseModel):
    """Sensitivity-analysis output containing ranked effects, confidence bands, and run accounting."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    method: SensitivityMethod
    parameter_names: list[str]

    mu_star: dict[str, float] = Field(default_factory=dict)
    sigma: dict[str, float] = Field(default_factory=dict)
    mu_star_conf: dict[str, list[float]] = Field(default_factory=dict)

    s1: dict[str, float] = Field(default_factory=dict)
    st: dict[str, float] = Field(default_factory=dict)
    s1_conf: dict[str, list[float]] = Field(default_factory=dict)
    st_conf: dict[str, list[float]] = Field(default_factory=dict)
    s2: dict[str, dict[str, float]] = Field(default_factory=dict)

    ranking: list[str] = Field(default_factory=list)
    top_interactions: list[tuple[str, str, float]] = Field(default_factory=list)
    uncertainty: SensitivityUncertaintyBundle | None = None
    total_runs: int = Field(default=0, ge=0)
    successful_runs: int = Field(default=0, ge=0)
    failed_runs: int = Field(default=0, ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


class AdversarialStrategy(StrEnum):
    """Sampling strategy used to generate adversarial stress scenarios."""

    SEARCH_LOOP = "search_loop"
    GRID_EXTREME = "grid_extreme"
    RANDOM_TAIL = "random_tail"


class AdversarialPlan(BaseModel):
    """Runtime plan for adversarial sweeps over vulnerable parameter regions."""

    model_config = ConfigDict(extra="forbid")

    parameter_specs: list[ParameterSpec] = Field(default_factory=list)
    strategy: AdversarialStrategy = AdversarialStrategy.SEARCH_LOOP
    max_iterations: int = Field(default=50, ge=1)
    vulnerability_threshold: float | None = None
    tail_percentile: float = Field(default=0.05, gt=0.0, lt=0.5)
    seed: int | None = None
    stop_on_first_vulnerability: bool = True
    collect_top_k: int = Field(default=20, ge=1)

    _admit_threshold = field_validator("vulnerability_threshold", mode="before")(
        admit_objective_threshold
    )

    @property
    def num_parameters(self) -> int:
        return len(self.parameter_specs)

    @model_validator(mode="after")
    def _validate_specs(self) -> AdversarialPlan:
        if not self.parameter_specs:
            raise ValueError("AdversarialPlan requires at least one parameter_spec")
        names = [item.name for item in self.parameter_specs]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate parameter names are not allowed in AdversarialPlan")
        return self
