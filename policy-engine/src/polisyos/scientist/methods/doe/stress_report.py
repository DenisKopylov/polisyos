"""Public doe stress report module API."""

from __future__ import annotations

from enum import Enum
from math import isfinite
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


def admit_objective_threshold(value: object) -> float | None:
    """Preserve absent thresholds and admit only finite physical numeric values."""
    if value is None:
        return None
    if type(value) not in {int, float}:
        raise ValueError("vulnerability_threshold must be a finite number, not a coerced value")
    try:
        threshold = float(cast("int | float", value))
    except (OverflowError, ValueError) as exc:
        raise ValueError("vulnerability_threshold must be finite") from exc
    if not isfinite(threshold):
        raise ValueError("vulnerability_threshold must be finite")
    return threshold


class StressScenarioEvidence(BaseModel):
    """Observed attempts before presentation grouping; no population probability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempted: StrictInt = Field(ge=0)
    finite_evaluated: StrictInt = Field(ge=0)
    violated_scenarios: StrictInt = Field(ge=0)
    unknown_or_nonfinite: StrictInt = Field(ge=0)
    planned_scenarios: StrictInt = Field(ge=0)
    critical_occurrences: StrictInt = Field(default=0, ge=0)
    high_occurrences: StrictInt = Field(default=0, ge=0)
    medium_occurrences: StrictInt = Field(default=0, ge=0)
    assessment_rule: Literal["objective_threshold", "component_assessments", "unavailable"]
    objective_direction: Literal["maximize", "minimize"] | None = None
    vulnerability_threshold: float | None = None

    _admit_threshold = field_validator("vulnerability_threshold", mode="before")(
        admit_objective_threshold
    )

    @model_validator(mode="after")
    def _validate_counts_and_rule(self) -> StressScenarioEvidence:
        if self.finite_evaluated + self.unknown_or_nonfinite != self.attempted:
            raise ValueError("finite and unknown outcomes must account for every attempt")
        if (
            self.attempted > self.planned_scenarios
            or self.violated_scenarios > self.finite_evaluated
        ):
            raise ValueError("scenario counts exceed their actual denominator")
        if self.assessment_rule == "objective_threshold" and (
            self.vulnerability_threshold is None or self.objective_direction is None
        ):
            raise ValueError("objective assessment requires its threshold and direction")
        if self.assessment_rule == "unavailable" and self.violated_scenarios:
            raise ValueError("unavailable assessment cannot establish violated scenarios")
        return self

    @property
    def complete(self) -> bool:
        return (
            self.assessment_rule != "unavailable"
            and self.planned_scenarios > 0
            and self.attempted == self.finite_evaluated == self.planned_scenarios
            and self.unknown_or_nonfinite == 0
        )

    @property
    def observed_fraction(self) -> float | None:
        if self.assessment_rule == "unavailable" or self.finite_evaluated == 0:
            return None
        return (self.finite_evaluated - self.violated_scenarios) / self.finite_evaluated

    def accounting_metadata(self) -> dict[str, object]:
        """Expose the same count basis to existing consumers of report metadata."""
        return {
            "attempted": self.attempted,
            "finite_evaluated": self.finite_evaluated,
            "violated_scenarios": self.violated_scenarios,
            "unknown_or_nonfinite": self.unknown_or_nonfinite,
            "planned_scenarios": self.planned_scenarios,
            "completeness": self.complete,
            "score_scope": (
                "observed_finite_scenarios"
                if self.assessment_rule != "unavailable"
                else "not_established"
            ),
            "score_formula": "(finite_evaluated-violated_scenarios)/finite_evaluated",
            "score_status": (
                "unavailable"
                if self.observed_fraction is None
                else "observed"
                if self.complete
                else "conditional"
            ),
            "population_probability": "not_established",
        }


class VulnerabilityType(str, Enum):
    """Vulnerability type public type."""

    CONSTRAINT_VIOLATION = "constraint_violation"
    NUMERICAL_INSTABILITY = "numerical_instability"
    OBJECTIVE_COLLAPSE = "objective_collapse"
    CONVERGENCE_FAILURE = "convergence_failure"
    EXTREME_SENSITIVITY = "extreme_sensitivity"
    DISTRIBUTIONAL = "distributional"
    COMBINATORIAL = "combinatorial"
    TEMPORAL = "temporal"


class Vulnerability(BaseModel):
    """Vulnerability public type."""

    model_config = ConfigDict(extra="forbid")

    vulnerability_id: str
    vulnerability_type: VulnerabilityType
    severity: str = "high"
    parameter_values: dict[str, float] = Field(default_factory=dict)
    objective_value: float | None = None
    description: str = ""
    affected_kpis: list[str] = Field(default_factory=list)
    constraint_violated: str | None = None
    mitigation: str = ""


class StressTestReport(BaseModel):
    """Summary of vulnerabilities, worst cases, and scenario evidence from adversarial stress testing."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.0"
    report_id: str

    total_scenarios_evaluated: int = 0
    adversarial_plan_ref: str | None = None
    fidelity_mode: str = "stress_preset"

    worst_case_parameters: dict[str, float] = Field(default_factory=dict)
    worst_case_objective: float | None = None

    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0

    robustness_score: float | None = None
    scenario_evidence: StressScenarioEvidence | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    scenario_evidence_components: dict[str, StressScenarioEvidence | None] = Field(
        default_factory=dict, exclude_if=lambda value: not value
    )
    set_adequacy_status: str | None = None
    coverage_empirical: float | None = Field(default=None, ge=0.0, le=1.0)
    coverage_target: float | None = Field(default=None, ge=0.0, le=1.0)
    inflation_mean: float | None = None
    inflation_budget: float | None = Field(default=None, ge=0.0)
    frontier_knee_rho: float | None = Field(default=None, ge=0.0)
    undercoverage_vulnerability: Vulnerability | None = None
    overconservatism_vulnerability: Vulnerability | None = None
    decision_packet_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _admit_schema_contract(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("schema_version", "1.0") == "1.0":
            if "scenario_evidence" in value or "scenario_evidence_components" in value:
                raise ValueError("scenario evidence requires StressTestReport schema 1.1")
        return value

    @model_validator(mode="after")
    def _validate_scenario_evidence(self) -> StressTestReport:
        evidence = self.scenario_evidence
        if evidence is None:
            if self.schema_version == "1.1" and (
                self.robustness_score is not None or self.set_adequacy_status != "partial"
            ):
                raise ValueError(
                    "schema 1.1 without scenario basis must be unavailable and partial"
                )
            return self
        if evidence.assessment_rule == "component_assessments":
            components = [
                item for item in self.scenario_evidence_components.values() if item is not None
            ]
            if not components or len(components) != len(self.scenario_evidence_components):
                raise ValueError("aggregate scenario evidence requires every component basis")
            for name in (
                "attempted",
                "finite_evaluated",
                "violated_scenarios",
                "unknown_or_nonfinite",
                "planned_scenarios",
                "critical_occurrences",
                "high_occurrences",
                "medium_occurrences",
            ):
                if getattr(evidence, name) != sum(getattr(item, name) for item in components):
                    raise ValueError("aggregate scenario counts disagree with their components")
            if any(item.assessment_rule == "unavailable" for item in components):
                raise ValueError("aggregate assessment cannot conceal unavailable components")
        if (
            self.total_scenarios_evaluated != evidence.finite_evaluated
            or self.robustness_score != evidence.observed_fraction
            or self.set_adequacy_status != ("complete" if evidence.complete else "partial")
            or self.critical_count != evidence.critical_occurrences
            or self.high_count != evidence.high_occurrences
            or self.medium_count != evidence.medium_occurrences
        ):
            raise ValueError("report score and adequacy disagree with observed scenario evidence")
        return self

    @property
    def is_robust(self) -> bool:
        evidence = self.scenario_evidence
        return (
            evidence is not None
            and evidence.complete
            and evidence.observed_fraction == self.robustness_score == 1.0
            and self.critical_count == 0
            and self.high_count == 0
        )
