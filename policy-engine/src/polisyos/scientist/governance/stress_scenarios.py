"""Run deterministic C5b stress presets and persist stress-test audit artifacts.

Calibration validation uses this module to perturb baseline objectives and
metrics under canonical shock scenarios, classify deterioration severity, and
produce a persisted `StressTestReportRef` plus a compact robustness summary for
leaderboard scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import StressTestReportRef
from polisyos.scientist.methods.doe.stress_report import StressTestReport, Vulnerability, VulnerabilityType


class StressScenarioKind(str, Enum):
    """Canonical stress scenario required during calibration validation.

    The built-in presets represent budget contraction, procurement disruption,
    wage subsidy incidence shifts, FX volatility, trade disruption, and
    reimbursement tariff shocks.
    """

    BUDGET_CONTRACTION = "budget_contraction"
    PROCUREMENT_SHOCK = "procurement_shock"
    WAGE_SUBSIDY = "wage_subsidy"
    FX = "fx"
    TRADE_DISRUPTION = "trade_disruption"
    REIMBURSEMENT_TARIFF = "reimbursement_tariff"


@dataclass(frozen=True)
class _ScenarioPreset:
    objective_multiplier: float
    vulnerability_type: VulnerabilityType
    description: str


_SCENARIO_PRESETS: dict[StressScenarioKind, _ScenarioPreset] = {
    StressScenarioKind.BUDGET_CONTRACTION: _ScenarioPreset(
        objective_multiplier=0.88,
        vulnerability_type=VulnerabilityType.CONSTRAINT_VIOLATION,
        description="Budget headroom contracts and pushes the policy closer to fiscal limits.",
    ),
    StressScenarioKind.PROCUREMENT_SHOCK: _ScenarioPreset(
        objective_multiplier=0.84,
        vulnerability_type=VulnerabilityType.COMBINATORIAL,
        description="Procurement execution deteriorates under supplier disruption.",
    ),
    StressScenarioKind.WAGE_SUBSIDY: _ScenarioPreset(
        objective_multiplier=0.94,
        vulnerability_type=VulnerabilityType.DISTRIBUTIONAL,
        description="A wage subsidy perturbs incidence and subsidy targeting quality.",
    ),
    StressScenarioKind.FX: _ScenarioPreset(
        objective_multiplier=0.86,
        vulnerability_type=VulnerabilityType.NUMERICAL_INSTABILITY,
        description="FX volatility weakens imported-input channels and budget certainty.",
    ),
    StressScenarioKind.TRADE_DISRUPTION: _ScenarioPreset(
        objective_multiplier=0.82,
        vulnerability_type=VulnerabilityType.TEMPORAL,
        description="Trade disruption slows adaptation and increases exposure duration.",
    ),
    StressScenarioKind.REIMBURSEMENT_TARIFF: _ScenarioPreset(
        objective_multiplier=0.9,
        vulnerability_type=VulnerabilityType.OBJECTIVE_COLLAPSE,
        description="A reimbursement tariff shift erodes the policy objective surface.",
    ),
}


class StressScenarioComparison(BaseModel):
    """Comparison between baseline and stressed outcomes for one scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario: StressScenarioKind
    baseline_objective: float
    stressed_objective: float
    objective_delta: float
    relative_delta: float
    stressed_metrics: dict[str, float] = Field(default_factory=dict)
    severity: str = Field(pattern="^(critical|high|medium|low|none)$")
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StressScenarioResult(BaseModel):
    """Aggregate result of executing the full stress-scenario suite.

    `comparisons` keeps one baseline-vs-stress readout per scenario,
    `robustness_score` is the aggregate promotion metric, and
    `stress_test_report_ref` points at the persisted audit artifact.
    """

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1)
    stress_test_report_ref: StressTestReportRef | None = None
    comparisons: list[StressScenarioComparison] = Field(default_factory=list)
    robustness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    worst_scenario: StressScenarioKind | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StressScenarioRunner:
    """Runner that evaluates the built-in calibration stress presets.

    The runner perturbs objective values and metrics under each preset, creates
    a persisted `StressTestReport`, and summarizes robustness and worst-case
    exposure for promotion review.
    """

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def run(
        self,
        *,
        baseline_metrics: dict[str, float] | None = None,
        baseline_objective: float | None = None,
        scenario_objective_overrides: dict[StressScenarioKind, float] | None = None,
        scenario_metric_overrides: dict[StressScenarioKind, dict[str, float]] | None = None,
        inputs: list[InputRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StressScenarioResult:
        """Execute all configured stress scenarios and persist the resulting report."""

        resolved_metrics = {
            str(key): float(value)
            for key, value in (baseline_metrics or {"policy_value": 1.0}).items()
        }
        resolved_objective = float(
            baseline_objective
            if baseline_objective is not None
            else next(iter(resolved_metrics.values()), 1.0)
        )

        comparisons: list[StressScenarioComparison] = []
        vulnerabilities: list[Vulnerability] = []
        scenario_scores: list[tuple[StressScenarioKind, float]] = []
        objective_overrides = dict(scenario_objective_overrides or {})
        metric_overrides = dict(scenario_metric_overrides or {})

        for scenario in StressScenarioKind:
            preset = _SCENARIO_PRESETS[scenario]
            stressed_objective = float(
                objective_overrides.get(scenario, resolved_objective * preset.objective_multiplier)
            )
            stressed_metrics = {
                key: float(value)
                for key, value in metric_overrides.get(
                    scenario,
                    {
                        metric: value * preset.objective_multiplier
                        for metric, value in resolved_metrics.items()
                    },
                ).items()
            }
            objective_delta = stressed_objective - resolved_objective
            relative_delta = (
                objective_delta / abs(resolved_objective)
                if abs(resolved_objective) > 1e-12
                else 0.0
            )
            deterioration = max(0.0, -relative_delta)
            severity = _severity_for_deterioration(deterioration)
            comparisons.append(
                StressScenarioComparison(
                    scenario=scenario,
                    baseline_objective=resolved_objective,
                    stressed_objective=stressed_objective,
                    objective_delta=objective_delta,
                    relative_delta=relative_delta,
                    stressed_metrics=stressed_metrics,
                    severity=severity,
                    notes=[preset.description],
                    metadata={"objective_multiplier": preset.objective_multiplier},
                )
            )
            scenario_scores.append((scenario, max(0.0, 1.0 - min(deterioration, 1.0))))
            if severity in {"critical", "high", "medium"}:
                vulnerabilities.append(
                    Vulnerability(
                        vulnerability_id=f"{scenario.value}_{uuid4().hex[:8]}",
                        vulnerability_type=preset.vulnerability_type,
                        severity=severity,
                        parameter_values={"objective_multiplier": preset.objective_multiplier},
                        objective_value=stressed_objective,
                        description=preset.description,
                        affected_kpis=sorted(stressed_metrics.keys()),
                    )
                )

        report = StressTestReport(
            report_id=f"stress_{uuid4().hex[:12]}",
            total_scenarios_evaluated=len(comparisons),
            fidelity_mode="stress_preset",
            worst_case_parameters={
                "objective_multiplier": min(
                    _SCENARIO_PRESETS[scenario].objective_multiplier
                    for scenario in StressScenarioKind
                )
            },
            worst_case_objective=min(item.stressed_objective for item in comparisons),
            vulnerabilities=vulnerabilities,
            critical_count=sum(1 for item in vulnerabilities if item.severity == "critical"),
            high_count=sum(1 for item in vulnerabilities if item.severity == "high"),
            medium_count=sum(1 for item in vulnerabilities if item.severity == "medium"),
            robustness_score=sum(score for _, score in scenario_scores)
            / max(len(scenario_scores), 1),
            metadata={
                "stress_scenarios": [item.scenario.value for item in comparisons],
                **dict(metadata or {}),
            },
        )
        report_ref = persist_stress_test_report(self._store, report, inputs=inputs)
        report.cas_artifact_id = str(report_ref.artifact_id)
        worst_scenario = min(
            comparisons,
            key=lambda item: (item.stressed_objective, item.scenario.value),
        ).scenario
        return StressScenarioResult(
            report_id=report.report_id,
            stress_test_report_ref=report_ref,
            comparisons=comparisons,
            robustness_score=report.robustness_score,
            critical_count=report.critical_count,
            high_count=report.high_count,
            medium_count=report.medium_count,
            worst_scenario=worst_scenario,
            metadata={"baseline_metric_keys": sorted(resolved_metrics.keys())},
        )


def persist_stress_test_report(
    store: FileSystemCAS,
    report: StressTestReport,
    *,
    inputs: list[InputRef] | None = None,
) -> StressTestReportRef:
    """Persist a stress test report to the artifact store.

    Args:
        store: CAS backend used for durable report storage.
        report: Stress report generated by `StressScenarioRunner`.
        inputs: Optional provenance links to candidate artifacts.

    Returns:
        Typed ref to the stored stress-test report.
    """

    ref = store.put_json(
        report,
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.StressTestReport", version=report.schema_version
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StressTestReportRef.model_validate(ref.model_dump())


def load_stress_test_report(
    store: FileSystemCAS,
    ref: ArtifactRef | StressTestReportRef,
) -> StressTestReport:
    """Load a persisted stress test report from the artifact store.

    Args:
        store: CAS backend that stores the report payload.
        ref: Generic or typed artifact ref pointing at the stress report.

    Returns:
        Parsed `StressTestReport`.
    """

    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref.artifact_id
    payload = from_canonical_bytes(store.get_bytes(artifact_id))
    return StressTestReport.model_validate(payload)


def _severity_for_deterioration(deterioration: float) -> str:
    if deterioration >= 0.25:
        return "critical"
    if deterioration >= 0.15:
        return "high"
    if deterioration >= 0.05:
        return "medium"
    if deterioration > 0.0:
        return "low"
    return "none"


__all__ = [
    "StressScenarioComparison",
    "StressScenarioKind",
    "StressScenarioResult",
    "StressScenarioRunner",
    "load_stress_test_report",
    "persist_stress_test_report",
]
