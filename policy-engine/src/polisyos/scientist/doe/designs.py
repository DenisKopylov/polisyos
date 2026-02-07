from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ScenarioSweep(BaseModel):
    scenarios: list[dict] = Field(default_factory=list)


class AblationPlan(BaseModel):
    targets: list[str] = Field(default_factory=list)


class SensitivityMethod(str, Enum):
    MORRIS = "morris"
    SOBOL = "sobol"
    FAST = "fast"


class ParameterDist(str, Enum):
    UNIFORM = "uniform"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    TRIANGULAR = "triangular"


class RunFailurePolicy(str, Enum):
    FAIL_FAST = "fail_fast"
    DROP_FAILED = "drop_failed"
    IMPUTE_BASELINE = "impute_baseline"


class ParameterSpec(BaseModel):
    name: str
    lower_bound: float
    upper_bound: float
    distribution: ParameterDist = ParameterDist.UNIFORM
    baseline: float | None = None
    description: str = ""
    num_levels: int = Field(default=4, ge=2)

    @model_validator(mode="after")
    def _validate_bounds(self) -> "ParameterSpec":
        if self.lower_bound >= self.upper_bound:
            raise ValueError(
                f"parameter '{self.name}' has invalid bounds: "
                f"{self.lower_bound} >= {self.upper_bound}"
            )
        if self.baseline is not None and not (self.lower_bound <= self.baseline <= self.upper_bound):
            raise ValueError(
                f"parameter '{self.name}' baseline {self.baseline} is outside bounds "
                f"[{self.lower_bound}, {self.upper_bound}]"
            )
        return self


class SensitivityPlan(BaseModel):
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

    @property
    def num_parameters(self) -> int:
        return len(self.parameter_specs)

    @property
    def estimated_runs(self) -> int:
        k = self.num_parameters
        if k == 0:
            return 0
        if self.method == SensitivityMethod.MORRIS:
            return self.n_trajectories * (k + 1)
        if self.method == SensitivityMethod.SOBOL:
            return self.n_trajectories * (2 * k + 2)
        if self.method == SensitivityMethod.FAST:
            return self.n_trajectories * k
        return 0

    @model_validator(mode="after")
    def _validate_plan(self) -> "SensitivityPlan":
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


class SensitivityResult(BaseModel):
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
    total_runs: int = Field(default=0, ge=0)
    successful_runs: int = Field(default=0, ge=0)
    failed_runs: int = Field(default=0, ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


class AdversarialStrategy(str, Enum):
    SEARCH_LOOP = "search_loop"
    GRID_EXTREME = "grid_extreme"
    RANDOM_TAIL = "random_tail"


class AdversarialPlan(BaseModel):
    parameter_specs: list[ParameterSpec] = Field(default_factory=list)
    strategy: AdversarialStrategy = AdversarialStrategy.SEARCH_LOOP
    max_iterations: int = Field(default=50, ge=1)
    vulnerability_threshold: float | None = None
    tail_percentile: float = Field(default=0.05, gt=0.0, lt=0.5)
    seed: int | None = None
    stop_on_first_vulnerability: bool = True
    collect_top_k: int = Field(default=20, ge=1)

    @property
    def num_parameters(self) -> int:
        return len(self.parameter_specs)

    @model_validator(mode="after")
    def _validate_specs(self) -> "AdversarialPlan":
        if not self.parameter_specs:
            raise ValueError("AdversarialPlan requires at least one parameter_spec")
        names = [item.name for item in self.parameter_specs]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate parameter names are not allowed in AdversarialPlan")
        return self
