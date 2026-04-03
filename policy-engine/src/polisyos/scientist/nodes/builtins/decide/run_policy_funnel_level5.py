"""Public decide run policy funnel level 5 module API."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.distributional import load_distributional_report
from polisyos.scientist.doe.stress_report import StressTestReport, Vulnerability, VulnerabilityType
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _is_policy_mode,
    _parse_model,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.policy_design.objectives import ConstraintStatus, PolicyEvaluationVector

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_policy_funnel_level5@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Policy Funnel Level 5",
    description="Assemble the Level 5 stress/governance packet for policy mode.",
    tags=["builtin", "decide", "policy_design", "level5"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.workflow_id",
        "params.policy_mode",
        "params.policy_evaluation",
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_STRESS_TEST_REPORT_REF}",
    ],
    state_writes=[
        "params.policy_level5_gate",
        f"artifacts_index.{ARTIFACT_STRESS_TEST_REPORT_REF}",
    ],
    produces=[ARTIFACT_STRESS_TEST_REPORT_REF],
)


@dataclass(frozen=True)
class RunPolicyFunnelLevel5Node:
    """Run policy funnel level 5 node implementation."""
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        if not _is_policy_mode(state):
            return NodeOutcome(status="skip", state=state)
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code=node_errors.ERROR_INVALID_INPUT,
                message=(
                    "run_policy_funnel_level5 is no longer supported. "
                    "Use run_policy_blueprint_runtime for the canonical L0-L6 Scientist runtime."
                ),
            ),
        )


def _build_vulnerabilities(
    *,
    evaluation: PolicyEvaluationVector | None,
    distributional,
    causal_report: CausalEffectReport | None,
    governance_report: GovernanceReport | None,
) -> list[Vulnerability]:
    vulnerabilities: list[Vulnerability] = []
    if evaluation is not None:
        for name, channel in evaluation.hard_constraints.items():
            if channel.status not in {ConstraintStatus.VIOLATED, ConstraintStatus.NEAR_BINDING}:
                continue
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id=f"constraint_{name}",
                    vulnerability_type=VulnerabilityType.CONSTRAINT_VIOLATION,
                    severity="critical" if channel.status is ConstraintStatus.VIOLATED else "high",
                    objective_value=channel.value,
                    constraint_violated=name,
                    description=(
                        f"Constraint '{name}' is {channel.status.value} at Level 5 review."
                    ),
                )
            )
    if distributional is not None:
        for entry in distributional.winners_losers.losers:
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id=f"distributional_{entry.cohort_id}",
                    vulnerability_type=VulnerabilityType.DISTRIBUTIONAL,
                    severity="high" if entry.is_vulnerable else "medium",
                    objective_value=entry.net_impact,
                    description=f"Negative subgroup impact detected for '{entry.cohort_label}'.",
                    affected_kpis=[entry.key_metric] if entry.key_metric else [],
                )
            )
    if causal_report is not None:
        for index, result in enumerate(causal_report.refutation_results):
            if result.passed:
                continue
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id=f"refutation_{index}",
                    vulnerability_type=VulnerabilityType.EXTREME_SENSITIVITY,
                    severity="high",
                    objective_value=result.refuted_estimate,
                    description=(
                        f"Refutation test '{result.test_type.value}' failed at Level 5 review."
                    ),
                )
            )
    if governance_report is not None and governance_report.verdict in {"reject", "human_gate"}:
        vulnerabilities.append(
            Vulnerability(
                vulnerability_id=f"governance_{governance_report.verdict}",
                vulnerability_type=VulnerabilityType.CONSTRAINT_VIOLATION,
                severity="critical",
                description=(
                    f"Governance verdict '{governance_report.verdict}' blocks promotion."
                ),
            )
        )
    return vulnerabilities


__all__ = ["RunPolicyFunnelLevel5Node"]
