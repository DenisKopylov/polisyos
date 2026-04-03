"""Public decide run translator compliance module API."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _is_policy_mode,
    _parse_model,
    _resolve_candidate,
    _resolve_readiness_contract,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
    _brief_required,
    _policy_build_input,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_DECISION_READINESS_CONTRACT_REF
from polisyos.scientist.policy_design.output import PolicyArtifactBuilder, PolicyBrief
from polisyos.scientist.policy_design.translator import (
    TranslatorCompliancePass,
    TranslatorComplianceResult,
)
from polisyos.scientist.search.judge_stack import PolicyPromotionResult

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_translator_compliance@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Translator Compliance",
    description="Apply anti-spin TranslatorCompliancePass to a generated PolicyBrief.",
    tags=["builtin", "decide", "policy_design", "translator"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.workflow_id",
        "params.policy_mode",
        "params.policy_brief",
        "params.policy_promotion_result",
        f"artifacts_index.{ARTIFACT_DECISION_READINESS_CONTRACT_REF}",
    ],
    state_writes=["params.translator_compliance"],
)


@dataclass(frozen=True)
class RunTranslatorComplianceNode:
    """Run translator compliance node implementation."""
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if not _is_policy_mode(state):
            return NodeOutcome(status="skip", state=state)

        readiness_ref = state.artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
        readiness = _resolve_readiness_contract(ctx, state, readiness_ref)
        if not _brief_required(readiness):
            return NodeOutcome(status="skip", state=state)

        brief = _parse_model(state.params.get("policy_brief"), PolicyBrief)
        if brief is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Translator compliance requires a translated PolicyBrief.",
                ),
            )

        promotion_result = _parse_model(
            state.params.get("policy_promotion_result"),
            PolicyPromotionResult,
        )
        candidate, candidate_ref = _resolve_candidate(ctx, state)
        if candidate is None or readiness is None or promotion_result is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Translator compliance requires candidate, readiness, and promotion inputs.",
                ),
            )

        build_input = _policy_build_input(ctx, state, candidate, candidate_ref, readiness, promotion_result)
        builder = PolicyArtifactBuilder()
        constraint_report = builder._build_constraint_report(build_input)  # noqa: SLF001
        subgroup_report = builder._build_subgroup_report(build_input)  # noqa: SLF001
        uncertainty_report = builder._build_uncertainty_report(build_input)  # noqa: SLF001
        transport_report = builder._build_transportability_report(build_input)  # noqa: SLF001
        gate_packet = builder._build_governance_gate_packet(build_input)  # noqa: SLF001
        implementation_plan = builder._build_implementation_plan(build_input)  # noqa: SLF001
        dossier = builder._build_dossier(  # noqa: SLF001
            source=build_input,
            constraint_report=constraint_report,
            subgroup_report=subgroup_report,
            uncertainty_report=uncertainty_report,
            transport_report=transport_report,
            gate_packet=gate_packet,
            implementation_plan=implementation_plan,
        )
        compliance = TranslatorCompliancePass().evaluate(
            brief,
            dossier=dossier,
            readiness_contract=readiness,
            constraint_report=constraint_report,
            subgroup_report=subgroup_report,
            uncertainty_report=uncertainty_report,
        )

        new_state = state.model_copy(deep=True)
        new_state.params["translator_compliance"] = compliance.model_dump(mode="json")
        return NodeOutcome(
            status="ok",
            state=new_state,
            events=[
                NodeEvent(
                    level="info" if compliance.passed else "warn",
                    message="Translator compliance evaluated.",
                    attrs={
                        "passed": compliance.passed,
                        "findings": len(compliance.findings),
                    },
                )
            ],
        )


__all__ = ["RunTranslatorComplianceNode", "TranslatorComplianceResult"]
