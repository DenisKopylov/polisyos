"""Lower Trinity bundles into executable Foundry artifacts and compile reports.

This module is the concrete backend behind `polisyos.foundry.compile.api`.
It links the Trinity bundle against a registry bundle, lowers mechanisms,
materializes a `ProgramGraph`, derives an `ExecPlan`, and writes all derived
artifacts into CAS with explicit provenance edges.
"""

from __future__ import annotations

import hashlib
import inspect
import json

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import ArtifactStore, CoreJSONArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.compiler.report import (
    CompileReport,
    put_compile_report,
    put_link_report,
)
from polisyos.core.contracts.execution_plan import ExecutionPlan
from polisyos.core.contracts.foundry import (
    METHOD_METRIC_BINDING_LIMIT,
    CompileRequest,
    CompileResult,
    DerivedArtifact,
    ExecPlan,
    ExecPlanRef,
    ExecutionPlanRef,
    MethodMetricBinding,
    MethodMetricBindingRequest,
    MethodMetricBindingSet,
    MethodMetricBindingSetRef,
    ProgramGraph,
    ProgramGraphRef,
)
from polisyos.core.registry import (
    RegistryBundleContent,
    load_registry_bundle,
    load_registry_bundle_content,
)
from polisyos.foundry.compile.manifest_inputs import (
    execution_plan_input_refs,
    program_graph_input_refs,
)
from polisyos.foundry.compile.randomization import (
    TREASURY_SALTS_PROFILE,
    build_treasury_plan,
)
from polisyos.foundry.methods.base import SlotType
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.selection.cost_model import CostBudget, CostModel
from polisyos.foundry.validation.conflict_checker import CompileTimeConflictChecker
from polisyos.ir import build_slot_layout
from polisyos.ir.governance.problem_frame import ObjectiveSpec
from polisyos.ir.kernel.method_metrics import (
    METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
    METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION,
    MethodMetricSourceUnit,
    registered_method_metric_input_unit_contract,
    registered_method_metric_law_metadata,
    registered_method_metric_law_metadata_for,
    registered_method_metric_semantics_match,
    registered_method_metric_unit_adapter_metadata,
    resolve_registered_method_metric_unit_adapter,
)
from polisyos.ir.linker import link_trinity
from polisyos.ir.linker.reports import LinkSeverity
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle

from ._graph import build_exec_order, build_program_graph
from ._lowering import lower_trinity


def _require_bounded_method_metric_bindings(request: CompileRequest) -> None:
    """Reject an oversized selection before any compiler traversal."""
    selections = request.method_metric_bindings
    if not isinstance(selections, list):
        raise ValueError("method_metric_binding_inventory_not_a_list")
    if len(selections) > METHOD_METRIC_BINDING_LIMIT:
        raise ValueError("method_metric_binding_inventory_exceeds_capture_limit")


def compile_trinity(store: CoreJSONArtifactStore, request: CompileRequest) -> CompileResult:
    """Compile a Trinity bundle and persist the execution graph artifacts.

    Args:
        store: CAS used to read the Trinity bundle and registry artifacts and
            to persist all derived compile artifacts.
        request: Trinity compile request with validation flags and optional
            explicit `registry_bundle_ref` override.

    Returns:
        `CompileResult` whose `derived_refs` contain `lowered_ir`,
        `program_graph`, `exec_plan`, `link_report`, `slot_layout`, and
        `treasury_plan` refs when compilation succeeds.
    """
    _require_bounded_method_metric_bindings(request)

    from polisyos.core.artifacts import validate_core_model_json_artifact

    # Method metric bindings require complete selected-profile lineage for every
    # compiled reference they cross. Upgrade this compile call locally; the
    # caller's request remains unchanged.
    if (
        request.method_metric_bindings or request.method_execution_plan_ref is not None
    ) and not request.return_selected_profile:
        request = request.model_copy(update={"return_selected_profile": True})

    policy_ref = request.policy_ref
    method_plan: ExecutionPlan | None = None
    exact_method_plan_ref: ExecutionPlanRef | None = None
    if request.method_execution_plan_ref is not None:
        try:
            method_plan, exact_method_plan_ref = _load_selected_method_execution_plan(
                store,
                policy_ref=policy_ref,
                method_plan_ref=request.method_execution_plan_ref,
            )
        except Exception as exc:
            return _compile_error(
                store,
                ok=False,
                policy_ref=policy_ref,
                registry_bundle_ref=None,
                link_report_ref=None,
                notes=[_method_execution_plan_failure_note(exc)],
                lowered_ir_ref=None,
                semantic_closure_notes=[],
            )
    bundle = validate_core_model_json_artifact(TrinityBundle, store, policy_ref)

    registry_bundle_ref = _resolve_registry_bundle_ref(
        request.registry_bundle_ref, bundle.model_spec.registry_bundle_ref
    )
    if registry_bundle_ref is None:
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=None,
            link_report_ref=None,
            notes=["missing_registry_bundle"],
            lowered_ir_ref=None,
            semantic_closure_notes=[],
        )

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)

    registries = RegistryBundle(
        schema_version="1.0",
        mechanisms=registry_content.mechanism_registry,
        slots=registry_content.slot_registry,
        merge_rules=registry_content.merge_registry,
        constraints=registry_content.constraint_registry,
        selector_fields=registry_content.selector_field_registry,
        units=registry_content.units_registry,
        metrics=registry_content.metric_registry,
    )

    link_inputs = [
        input_ref_from_artifact_ref(policy_ref, role="ir"),
        input_ref_from_artifact_ref(registry_bundle_ref, role="registry_bundle"),
    ]
    linked_bundle, link_report = link_trinity(
        bundle,
        registries,
        allow_extra_params=request.validation_flags.allow_extra_params,
        strict=request.validation_flags.strict_link,
    )
    link_report_ref = put_link_report(
        store,
        link_report,
        inputs=link_inputs,
        return_selected_profile=request.return_selected_profile,
    )
    compile_notes = _link_warning_notes(link_report)

    if request.validation_flags.strict_link and not link_report.ok:
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=compile_notes + ["link_failed"],
            lowered_ir_ref=None,
            semantic_closure_notes=[],
        )

    try:
        lowered_ir_ref, lowered_ir, semantic_notes = lower_trinity(
            store,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            bundle=bundle,
            linked_bundle=linked_bundle,
            registry_content=registry_content,
            strict=request.validation_flags.strict_schema,
            return_selected_profile=request.return_selected_profile,
        )
    except Exception as exc:
        lowering_error = str(exc)
        lowering_notes = list(compile_notes)
        if lowering_error.startswith("missing_runtime_mechanism_support:"):
            lowering_notes.append(lowering_error)
        lowering_notes.append(f"semantic_lowering_failed:{lowering_error}")
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=lowering_notes,
            lowered_ir_ref=None,
            semantic_closure_notes=[],
        )

    try:
        program_graph, params_refs = build_program_graph(
            store,
            ir_ref=policy_ref,
            lowered_ir_ref=lowered_ir_ref,
            mechanisms=lowered_ir.mechanisms,
            constraint_ids=[item.constraint_id for item in lowered_ir.constraints],
            method_plan=method_plan,
        )
    except (TypeError, ValueError) as exc:
        if method_plan is None:
            raise
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=compile_notes + [_method_execution_plan_failure_note(exc)],
            lowered_ir_ref=lowered_ir_ref,
            semantic_closure_notes=semantic_notes,
        )

    conflict_checker = CompileTimeConflictChecker(
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        strict_mode=request.validation_flags.strict_conflict_check,
    )
    conflict_report = conflict_checker.check(program_graph)
    if not conflict_report.ok and request.validation_flags.strict_conflict_check:
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=compile_notes
            + [
                f"conflict_check_failed:{len(conflict_report.conflicts)}",
            ],
            lowered_ir_ref=lowered_ir_ref,
            semantic_closure_notes=semantic_notes,
        )

    cost_budget = _build_cost_budget(request)
    if cost_budget is not None:
        cost_model = CostModel()
        n_agents = (
            request.compile_config.estimate_n_agents
            if request.compile_config.estimate_n_agents is not None
            else 1000
        )
        time_steps = (
            request.compile_config.estimate_time_steps
            if request.compile_config.estimate_time_steps is not None
            else 100
        )
        estimate = cost_model.estimate(
            program_graph,
            n_agents=n_agents,
            time_steps=time_steps,
            budget=cost_budget,
        )
        if estimate.exceeds_budget:
            return _compile_error(
                store,
                ok=False,
                policy_ref=policy_ref,
                registry_bundle_ref=registry_bundle_ref,
                link_report_ref=link_report_ref,
                notes=compile_notes + ["cost_budget_exceeded"],
                lowered_ir_ref=lowered_ir_ref,
                semantic_closure_notes=semantic_notes,
            )

    program_inputs = program_graph_input_refs(
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        params_refs=params_refs,
        method_execution_plan_ref=exact_method_plan_ref,
    )
    program_ref = store.put_json(
        program_graph,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=program_inputs,
        ),
        return_selected_profile=request.return_selected_profile,
    )
    program_graph_ref = ProgramGraphRef.model_validate(program_ref.model_dump(mode="python"))

    method_metric_binding_set_ref: MethodMetricBindingSetRef | None = None
    capture_only_method_graph = (
        request.method_execution_plan_ref is not None
        and not request.method_metric_bindings
        and any(node.node_kind == "method" for node in program_graph.nodes)
    )
    if request.method_metric_bindings or capture_only_method_graph:
        try:
            method_metric_binding_set_ref = _compile_method_metric_binding_set(
                store,
                request=request,
                bundle=bundle,
                program_graph=program_graph,
                program_graph_ref=program_graph_ref,
                registry_bundle_ref=registry_bundle_ref,
                registry_content=registry_content,
            )
        except (TypeError, ValueError) as exc:
            reason = str(exc)
            return _compile_error(
                store,
                ok=False,
                policy_ref=policy_ref,
                registry_bundle_ref=registry_bundle_ref,
                link_report_ref=link_report_ref,
                notes=compile_notes
                + [
                    reason
                    if reason.startswith("method_metric_")
                    else "method_metric_binding_compile_failed"
                ],
                lowered_ir_ref=lowered_ir_ref,
                semantic_closure_notes=semantic_notes,
            )

    treasury_plan = build_treasury_plan(
        program_graph, root_seed=request.compile_config.random_seed or 0
    )
    treasury_plan_ref = store.put_json(
        treasury_plan,
        PutOptions(
            kind="foundry.treasury_plan",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.TreasuryPlan",
                version=treasury_plan.schema_version,
            ),
            inputs=[input_ref_from_artifact_ref(program_ref, role="program_graph")],
        ),
        return_selected_profile=request.return_selected_profile,
    )

    order = build_exec_order(program_graph)
    exec_plan = ExecPlan(
        program_ref=program_graph_ref,
        order=order,
        determinism_tier=request.compile_config.determinism_tier,
        random_seed=request.compile_config.random_seed,
        nan_guard_enabled=request.compile_config.nan_guard_enabled,
        policy_fidelity_level=lowered_ir.policy_fidelity_level,
        constraint_mode=lowered_ir.constraint_mode,
        mode=request.compile_config.mode,
        jit=request.compile_config.jit,
        max_steps=request.compile_config.max_steps,
        notes=_merge_notes(semantic_notes, [TREASURY_SALTS_PROFILE]),
    )
    exec_plan_payload_ref = store.put_json(
        exec_plan,
        PutOptions(
            kind=ExecPlan.ARTIFACT_KIND,
            media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ExecPlan.ARTIFACT_SCHEMA_NAME,
                version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=execution_plan_input_refs(
                program_graph_ref=program_ref,
                treasury_plan_ref=treasury_plan_ref,
                method_metric_binding_set_ref=method_metric_binding_set_ref,
            ),
        ),
        return_selected_profile=request.return_selected_profile,
    )
    exec_plan_ref = ExecPlanRef.model_validate(exec_plan_payload_ref.model_dump(mode="python"))

    slot_layout = build_slot_layout(registry_content.slot_registry)
    slot_layout_ref = store.put_json(
        slot_layout,
        PutOptions(
            kind="foundry.slot_layout",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.SlotLayout", version=slot_layout.schema_version
            ),
            inputs=[input_ref_from_artifact_ref(program_graph_ref, role="program_graph")],
        ),
        return_selected_profile=request.return_selected_profile,
    )

    compile_report = CompileReport(
        schema_version="1.0",
        ok=True,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        slot_layout_ref=slot_layout_ref,
        treasury_plan_ref=treasury_plan_ref,
        semantic_closure_notes=semantic_notes,
        notes=compile_notes,
    )
    compile_inputs = _compile_inputs(
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        slot_layout_ref=slot_layout_ref,
        treasury_plan_ref=treasury_plan_ref,
        method_metric_binding_set_ref=method_metric_binding_set_ref,
    )
    compile_report_ref = put_compile_report(
        store,
        compile_report,
        inputs=compile_inputs,
        return_selected_profile=request.return_selected_profile,
    )

    derived_refs = [
        DerivedArtifact(role="lowered_ir", ref=lowered_ir_ref),
        DerivedArtifact(role="program_graph", ref=program_graph_ref),
        DerivedArtifact(role="exec_plan", ref=exec_plan_ref),
        DerivedArtifact(role="link_report", ref=link_report_ref),
        DerivedArtifact(role="slot_layout", ref=slot_layout_ref),
        DerivedArtifact(role="treasury_plan", ref=treasury_plan_ref),
    ]
    if method_metric_binding_set_ref is not None:
        derived_refs.append(
            DerivedArtifact(role="method_metric_binding_set", ref=method_metric_binding_set_ref)
        )

    return CompileResult(
        schema_version="1.0",
        ok=True,
        exec_plan_ref=exec_plan_ref,
        compile_report_ref=compile_report_ref,
        derived_refs=derived_refs,
        notes=_merge_notes(compile_notes, semantic_notes),
    )


def _resolve_registry_bundle_ref(
    request_ref: ArtifactRef | None, model_spec_ref: str | None
) -> ArtifactRef | None:
    if request_ref is not None:
        return request_ref
    if model_spec_ref is None:
        return None
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(model_spec_ref),
        kind="core.registry_bundle",
        media_type="application/json",
    )


def _load_selected_method_execution_plan(
    store: CoreJSONArtifactStore,
    *,
    policy_ref: ArtifactRef,
    method_plan_ref: ExecutionPlanRef,
) -> tuple[ExecutionPlan, ExecutionPlanRef]:
    """Read one selected plan only when its manifest binds the exact candidate profile."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    if (
        policy_ref.kind != "ir.trinity_bundle"
        or policy_ref.media_type != "application/json"
        or policy_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("method_execution_plan_exact_candidate_ref_missing")
    if (
        method_plan_ref.kind != "scientist.execution_plan"
        or method_plan_ref.media_type != "application/json"
        or method_plan_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("method_execution_plan_exact_plan_ref_missing")
    exact_policy_ref = _selected_profile_ref(store, policy_ref)
    if artifact_ref_identity_key(exact_policy_ref) != artifact_ref_identity_key(policy_ref):
        raise ValueError("method_execution_plan_candidate_profile_mismatch")
    exact_plan_ref = _selected_profile_ref(store, method_plan_ref)
    if artifact_ref_identity_key(exact_plan_ref) != artifact_ref_identity_key(method_plan_ref):
        raise ValueError("method_execution_plan_selected_profile_mismatch")
    manifest = store.get_manifest(exact_plan_ref)
    if (
        manifest.kind != "scientist.execution_plan"
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != "polisyos.core.ExecutionPlan"
        or manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("method_execution_plan_manifest_schema_mismatch")
    candidate_edges = [item for item in manifest.inputs if item.role == "policy_candidate"]
    if len(candidate_edges) != 1:
        raise ValueError("method_execution_plan_requires_one_policy_candidate_edge")
    candidate_edge = candidate_edges[0]
    if (
        candidate_edge.artifact_id != exact_policy_ref.artifact_id
        or candidate_edge.manifest_profile_sha256 != exact_policy_ref.manifest_profile_sha256
    ):
        raise ValueError("method_execution_plan_policy_candidate_edge_mismatch")
    plan = validate_core_model_json_artifact(ExecutionPlan, store, exact_plan_ref)
    return plan, ExecutionPlanRef.model_validate(exact_plan_ref.model_dump(mode="python"))


def _method_execution_plan_failure_note(error: BaseException) -> str:
    """Keep selected-plan refusal reasons bounded and stable in compile output."""
    reason = str(error)
    allowed_prefixes = ("method_execution_plan_", "execution_plan_method_")
    if reason.startswith(allowed_prefixes):
        return reason[:256]
    return "method_execution_plan_invalid"


def _selected_profile_ref(store: CoreJSONArtifactStore, ref: ArtifactRef) -> ArtifactRef:
    """Bind a reference to the exact manifest profile currently read from CAS."""
    from polisyos.core.artifacts import artifact_ref_for_manifest

    manifest = store.get_manifest(ref)
    if manifest.artifact_id != ref.artifact_id or manifest.kind != ref.kind:
        raise ValueError("method_metric_source_ref_identity_mismatch")
    return artifact_ref_for_manifest(manifest)


def _compile_method_metric_binding_set(
    store: CoreJSONArtifactStore,
    *,
    request: CompileRequest,
    bundle: TrinityBundle,
    program_graph: ProgramGraph,
    program_graph_ref: ProgramGraphRef,
    registry_bundle_ref: ArtifactRef,
    registry_content: RegistryBundleContent,
) -> MethodMetricBindingSetRef:
    """Compile explicit scalar bindings or an exact empty capture-only binding set."""
    _require_bounded_method_metric_bindings(request)
    from polisyos.core.contracts.foundry import MethodMetricSemanticContract

    objectives_by_id: dict[str, list[ObjectiveSpec]] = {}
    for objective in bundle.problem_frame.objectives:
        objectives_by_id.setdefault(objective.objective_id, []).append(objective)
    nodes_by_id = {node.node_id: node for node in program_graph.nodes}
    if len(nodes_by_id) != len(program_graph.nodes):
        raise ValueError("method_metric_duplicate_program_graph_node_id")
    selection_keys = [
        (selection.objective_id, selection.node_id, selection.output_slot_id)
        for selection in request.method_metric_bindings
    ]
    if len(selection_keys) != len(set(selection_keys)):
        raise ValueError("method_metric_duplicate_binding_selection")
    selected_output_keys = [
        (selection.node_id, selection.output_slot_id)
        for selection in request.method_metric_bindings
    ]
    if len(selected_output_keys) != len(set(selected_output_keys)):
        raise ValueError("method_metric_duplicate_selected_output_slot")

    registry_bundle = load_registry_bundle(store, registry_bundle_ref)
    metric_registry_ref = registry_bundle.metric_registry
    units_registry_ref = registry_bundle.units_registry
    metric_registry = registry_content.metric_registry
    units_registry = registry_content.units_registry
    if metric_registry_ref is None or units_registry_ref is None:
        raise ValueError("method_metric_registry_member_missing")
    if metric_registry is None or units_registry is None:
        raise ValueError("method_metric_registry_payload_missing")

    method_registry = MethodRegistry.get_instance()
    default_law_id, default_law_version, default_law_digest = (
        registered_method_metric_law_metadata()
    )
    adapter_id, adapter_version, adapter_digest = registered_method_metric_unit_adapter_metadata()
    bindings: list[MethodMetricBinding] = []
    for selection in request.method_metric_bindings:
        objective_rows = objectives_by_id.get(selection.objective_id, [])
        if len(objective_rows) != 1:
            raise ValueError("method_metric_objective_not_unique")
        objective = objective_rows[0]
        node = nodes_by_id.get(selection.node_id)
        if node is None or node.node_kind != "method" or not node.method_fqn:
            raise ValueError("method_metric_selected_node_not_method")
        signature = method_registry.get_signature(node.method_fqn)
        if signature is None or signature.fqn != node.method_fqn:
            raise ValueError("method_metric_exact_method_signature_unavailable")
        if node.method_version is not None and node.method_version != signature.version:
            raise ValueError("method_metric_method_version_mismatch")
        slot = signature.get_output_slot(selection.output_slot_id)
        if slot is None:
            raise ValueError("method_metric_selected_output_slot_missing")
        metric_spec = metric_registry.metrics.get(objective.metric_id)
        if metric_spec is None:
            raise ValueError("method_metric_selected_metric_missing")
        if not metric_spec.unit_id or metric_spec.unit_id not in units_registry.units:
            raise ValueError("method_metric_selected_metric_unit_missing")
        target_unit = units_registry.units[metric_spec.unit_id]
        semantics = metric_spec.method_semantics
        law_metadata = registered_method_metric_law_metadata_for(
            signature.fqn,
            signature.version,
        )
        if law_metadata is None:
            law_id, law_version, law_digest = (
                default_law_id,
                default_law_version,
                default_law_digest,
            )
        else:
            law_id, law_version, law_digest = law_metadata
        ex_ante_semantics = registered_method_metric_semantics_match(law_id, semantics)
        registered_input_units = registered_method_metric_input_unit_contract(law_id, semantics)
        source_slot = slot
        if ex_ante_semantics:
            source_slot = next(
                (item for item in signature.input_slots if item.name == "baseline"),
                slot,
            )
        source_unit = MethodMetricSourceUnit(
            dimension=source_slot.unit.dimension,
            symbol=source_slot.unit.symbol,
            scale=float(source_slot.unit.scale),
        )
        adapter = resolve_registered_method_metric_unit_adapter(
            source_unit,
            target_unit,
            law_id=law_id if ex_ante_semantics else None,
            semantics=semantics if ex_ante_semantics else None,
        )
        output_shape = (
            "scalar" if ex_ante_semantics or slot.slot_type is SlotType.SCALAR else "non_scalar"
        )
        limitations: list[str] = []
        if semantics is None:
            limitations.append("metric_method_semantics_missing")
        elif any(
            role.method_input_slot_id
            not in {input_slot.name for input_slot in signature.input_slots}
            for role in semantics.input_roles
        ):
            if registered_input_units is None:
                raise ValueError("method_metric_semantic_input_role_slot_missing")
            limitations.append("registered_method_input_slot_set_mismatch")
        if registered_input_units is not None:
            expected_slots = {slot_id for _, slot_id, _ in registered_input_units}
            input_rows = tuple(signature.input_slots)
            input_slots_by_id = {item.name: item for item in input_rows}
            if (
                len(input_slots_by_id) != len(input_rows)
                or set(input_slots_by_id) != expected_slots
            ):
                limitations.append("registered_method_input_slot_set_mismatch")
            elif any(
                MethodMetricSourceUnit(
                    dimension=input_slots_by_id[slot_id].unit.dimension,
                    symbol=input_slots_by_id[slot_id].unit.symbol,
                    scale=float(input_slots_by_id[slot_id].unit.scale),
                )
                != expected_unit
                for _, slot_id, expected_unit in registered_input_units
            ):
                limitations.append("registered_method_input_unit_set_mismatch")
        if output_shape != "scalar":
            limitations.append("method_output_slot_not_scalar")
        if law_metadata is None:
            limitations.append("registered_method_metric_law_missing")
        elif not ex_ante_semantics:
            limitations.append("method_metric_law_semantics_not_registered")
        if (
            semantics is not None
            and not ex_ante_semantics
            and semantics.producer_contract_id != slot.contract_id
        ):
            limitations.append("method_output_contract_id_mismatch")
        if adapter.operation == "unsupported":
            limitations.append(adapter.limitation or "unit_relation_not_registered")
        try:
            method_class = method_registry.get(signature.fqn, version=signature.version)
            build_source = inspect.getsource(method_class).encode("utf-8")
            method_build_digest = "sha256:" + hashlib.sha256(build_source).hexdigest()
            method_build_digest_scope = "class_source_only"
        except (OSError, TypeError, UnicodeError, ValueError):
            method_build_digest = None
            method_build_digest_scope = "unavailable"
            limitations.append("method_class_source_unavailable")
        digest_payload = json.dumps(
            [selection.objective_id, selection.node_id, selection.output_slot_id],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        binding_id = "method.metric.binding." + hashlib.sha256(digest_payload).hexdigest()[:24]
        bindings.append(
            MethodMetricBinding(
                binding_id=binding_id,
                objective_id=objective.objective_id,
                metric_id=objective.metric_id,
                node_id=node.node_id,
                method_fqn=signature.fqn,
                method_version=signature.version,
                method_abi_digest=signature.abi_digest(),
                method_abi_digest_algorithm="blake2b",
                method_build_digest=method_build_digest,
                method_build_digest_scope=method_build_digest_scope,
                output_slot_id=selection.output_slot_id,
                output_value_path=(semantics.output_value_path if semantics is not None else ()),
                output_contract_id=slot.contract_id,
                output_shape=output_shape,
                semantics=semantics,
                source_unit=source_unit,
                target_unit=target_unit,
                law_id=law_id,
                law_version=law_version,
                law_code_digest=law_digest,
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                adapter_code_digest=adapter.code_digest or adapter_digest,
                conversion_operation=adapter.operation,
                conversion_factor_numerator=adapter.factor_numerator,
                conversion_factor_denominator=adapter.factor_denominator,
                availability="unavailable" if limitations else "available",
                limitation=";".join(dict.fromkeys(limitations)) or None,
            )
        )

    exact_program_ref = _selected_profile_ref(store, program_graph_ref)
    exact_policy_ref = _selected_profile_ref(store, request.policy_ref)
    exact_registry_ref = _selected_profile_ref(store, registry_bundle_ref)
    exact_metric_ref = _selected_profile_ref(store, metric_registry_ref)
    exact_units_ref = _selected_profile_ref(store, units_registry_ref)
    payload = MethodMetricBindingSet(
        program_graph_ref=ProgramGraphRef.model_validate(
            exact_program_ref.model_dump(mode="python")
        ),
        policy_ref=exact_policy_ref,
        registry_bundle_ref=exact_registry_ref,
        metric_registry_ref=exact_metric_ref,
        units_registry_ref=exact_units_ref,
        bindings=bindings,
    )
    artifact_ref = store.put_json(
        payload,
        PutOptions(
            kind=MethodMetricBindingSet.ARTIFACT_KIND,
            media_type=MethodMetricBindingSet.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
                version=MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(exact_program_ref, role="program_graph"),
                input_ref_from_artifact_ref(exact_policy_ref, role="policy"),
                input_ref_from_artifact_ref(exact_registry_ref, role="registry_bundle"),
                input_ref_from_artifact_ref(exact_metric_ref, role="metric_registry"),
                input_ref_from_artifact_ref(exact_units_ref, role="units_registry"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return MethodMetricBindingSetRef.model_validate(artifact_ref.model_dump(mode="python"))


def _compile_inputs(
    *,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef | None,
    link_report_ref: ArtifactRef | None,
    lowered_ir_ref: ArtifactRef | None,
    program_graph_ref: ArtifactRef | None,
    exec_plan_ref: ArtifactRef | None,
    slot_layout_ref: ArtifactRef | None,
    treasury_plan_ref: ArtifactRef | None,
    method_metric_binding_set_ref: ArtifactRef | None = None,
) -> list[InputRef]:
    inputs = [input_ref_from_artifact_ref(policy_ref, role="ir")]
    if registry_bundle_ref is not None:
        inputs.append(input_ref_from_artifact_ref(registry_bundle_ref, role="registry_bundle"))
    if link_report_ref is not None:
        inputs.append(input_ref_from_artifact_ref(link_report_ref, role="link_report"))
    if lowered_ir_ref is not None:
        inputs.append(input_ref_from_artifact_ref(lowered_ir_ref, role="lowered_ir"))
    if program_graph_ref is not None:
        inputs.append(input_ref_from_artifact_ref(program_graph_ref, role="program_graph"))
    if exec_plan_ref is not None:
        inputs.append(input_ref_from_artifact_ref(exec_plan_ref, role="exec_plan"))
    if slot_layout_ref is not None:
        inputs.append(input_ref_from_artifact_ref(slot_layout_ref, role="slot_layout"))
    if treasury_plan_ref is not None:
        inputs.append(input_ref_from_artifact_ref(treasury_plan_ref, role="treasury_plan"))
    if method_metric_binding_set_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                method_metric_binding_set_ref,
                role="method_metric_bindings",
            )
        )
    return inputs


def _compile_error(
    store: CoreJSONArtifactStore,
    *,
    ok: bool,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef | None,
    link_report_ref: ArtifactRef | None,
    lowered_ir_ref: ArtifactRef | None,
    semantic_closure_notes: list[str],
    notes: list[str],
) -> CompileResult:
    compile_report = CompileReport(
        schema_version="1.0",
        ok=ok,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        semantic_closure_notes=semantic_closure_notes,
        notes=notes,
    )
    compile_inputs = _compile_inputs(
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        program_graph_ref=None,
        exec_plan_ref=None,
        slot_layout_ref=None,
        treasury_plan_ref=None,
    )
    compile_report_ref = put_compile_report(store, compile_report, inputs=compile_inputs)

    derived_refs: list[DerivedArtifact] = []
    if lowered_ir_ref is not None:
        derived_refs.append(DerivedArtifact(role="lowered_ir", ref=lowered_ir_ref))
    if link_report_ref is not None:
        derived_refs.append(DerivedArtifact(role="link_report", ref=link_report_ref))
    return CompileResult(
        schema_version="1.0",
        ok=ok,
        exec_plan_ref=None,
        compile_report_ref=compile_report_ref,
        derived_refs=derived_refs,
        notes=notes,
    )


def _build_cost_budget(request: CompileRequest) -> CostBudget | None:
    config = request.compile_config
    if (
        config.cost_budget_max_total_ms is None
        and config.cost_budget_max_memory_mb is None
        and config.cost_budget_max_compile_ms is None
        and config.cost_budget_max_per_mechanism_ms is None
    ):
        return None
    defaults = CostBudget()
    return CostBudget(
        max_total_ms=(
            config.cost_budget_max_total_ms
            if config.cost_budget_max_total_ms is not None
            else defaults.max_total_ms
        ),
        max_memory_mb=(
            config.cost_budget_max_memory_mb
            if config.cost_budget_max_memory_mb is not None
            else defaults.max_memory_mb
        ),
        max_compile_ms=(
            config.cost_budget_max_compile_ms
            if config.cost_budget_max_compile_ms is not None
            else defaults.max_compile_ms
        ),
        max_per_mechanism_ms=(
            config.cost_budget_max_per_mechanism_ms
            if config.cost_budget_max_per_mechanism_ms is not None
            else defaults.max_per_mechanism_ms
        ),
    )


def _link_warning_notes(link_report) -> list[str]:
    notes: list[str] = []
    for issue in getattr(link_report, "issues", []):
        if issue.severity != LinkSeverity.WARNING:
            continue
        token = f"link_warning:{issue.code.value}"
        if token not in notes:
            notes.append(token)
    return notes


def _merge_notes(*note_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for notes in note_groups:
        for note in notes:
            if note not in merged:
                merged.append(note)
    return merged
