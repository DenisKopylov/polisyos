"""Derive ordered compiler-owned input edges for selected graph and plan views."""

from __future__ import annotations

from polisyos.core.artifacts import ArtifactRef, InputRef, input_ref_from_artifact_ref
from polisyos.core.contracts import ExecutionPlanRef


def execution_plan_input_refs(
    *,
    program_graph_ref: ArtifactRef,
    treasury_plan_ref: ArtifactRef,
    method_metric_binding_set_ref: ArtifactRef | None,
) -> list[InputRef]:
    """Return the exact ordered input edges used by the compiler's ExecPlan writer.

    Args:
        program_graph_ref: The selected compiled graph.
        treasury_plan_ref: The selected graph-derived randomization plan.
        method_metric_binding_set_ref: Optional selected method-metric bindings.

    Returns:
        Ordered role-qualified input references. These edges record source
        identity and do not grant authority to any artifact or value.
    """
    inputs = [
        input_ref_from_artifact_ref(program_graph_ref, role="program_graph"),
        input_ref_from_artifact_ref(treasury_plan_ref, role="treasury_plan"),
    ]
    if method_metric_binding_set_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                method_metric_binding_set_ref, role="method_metric_bindings"
            )
        )
    return inputs


def program_graph_input_refs(
    *,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef | None,
    link_report_ref: ArtifactRef | None,
    lowered_ir_ref: ArtifactRef | None,
    params_refs: dict[str, ArtifactRef],
    method_execution_plan_ref: ExecutionPlanRef | None = None,
) -> list[InputRef]:
    """Return the compiler's ordered graph-input lineage for the supplied refs.

    Args:
        policy_ref: Selected Trinity policy input.
        registry_bundle_ref: Optional selected registry bundle.
        link_report_ref: Optional selected linker report.
        lowered_ir_ref: Optional selected lowered IR.
        params_refs: Selected node-parameter references keyed by node id.
        method_execution_plan_ref: Optional selected source method plan.

    Returns:
        Ordered role-qualified references without granting authority.
    """
    inputs = [input_ref_from_artifact_ref(policy_ref, role="ir")]
    if registry_bundle_ref is not None:
        inputs.append(input_ref_from_artifact_ref(registry_bundle_ref, role="registry_bundle"))
    if link_report_ref is not None:
        inputs.append(input_ref_from_artifact_ref(link_report_ref, role="link_report"))
    if lowered_ir_ref is not None:
        inputs.append(input_ref_from_artifact_ref(lowered_ir_ref, role="lowered_ir"))
    if method_execution_plan_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(method_execution_plan_ref, role="execution_plan_source")
        )
    for node_id, ref in sorted(params_refs.items()):
        inputs.append(input_ref_from_artifact_ref(ref, role=f"params:{node_id}"))
    return inputs
