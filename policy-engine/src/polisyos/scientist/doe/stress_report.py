"""Public doe stress report module API."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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

    schema_version: str = "1.0"
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
    decision_packet_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @property
    def is_robust(self) -> bool:
        return self.critical_count == 0 and self.high_count == 0
