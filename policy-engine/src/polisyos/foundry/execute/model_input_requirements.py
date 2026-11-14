"""Replay exact ProgramGraph input facts for Runtime and actual Foundry intake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    CoreJSONArtifactStore,
    SchemaInfo,
    artifact_ref_identity_key,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    ExecPlan,
    ExecPlanRef,
    ModelInputContext,
    ModelInputObligation,
    ModelInputObligationSet,
    ModelInputPort,
    ModelInputPortDeclaration,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphInputDependency,
    ProgramGraphInputInvocation,
    ProgramGraphRef,
    ProgramNode,
    StateSnapshotRef,
    load_model_input_obligation_set,
    load_model_input_port_declaration,
    load_program_graph_input_interface,
    verify_model_input_port_semantics,
)
from polisyos.core.registry import RegistryBundleContent, load_registry_bundle_content
from polisyos.foundry.contracts.specs import get_mechanism_spec, validate_mechanism_params
from polisyos.ir.governance import ScheduleSpec, SelectorPredicate, schedule_range
from polisyos.ir.kernel import MergeRuleKind, SlotKind, SlotScope, SlotValueType
from polisyos.ir.kernel.units import MoneyUnit
from polisyos.ir.registry import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle, load_trinity_bundle_artifact


@dataclass(frozen=True)
class RecomputedProgramGraphInputs:
    """Actual prestate and complete obligation facts before any write."""

    prestate_ref: StateSnapshotRef
    supplied_initial_slots: tuple[str, ...]
    missing_obligations: tuple[ModelInputObligation, ...]


@dataclass(frozen=True)
class SelectedProgramGraphInputDeclaration:
    """The actual compiled model's opt-in port declaration and selected origin."""

    trinity_bundle_ref: ArtifactRef
    declaration_ref: ArtifactRef
    declaration: ModelInputPortDeclaration


def program_graph_declares_model_input_ports(
    store: CoreJSONArtifactStore, program_graph_ref: ArtifactRef | ArtifactID | str
) -> bool:
    """Detect the compiled model's opt-in before legacy graph execution."""
    graph = validate_core_model_json_artifact(ProgramGraph, store, program_graph_ref)
    bundle = _selected_model_input_bundle(store, graph)
    return bundle is not None and bundle.model_spec.model_input_port_declaration_ref is not None


def resolve_program_graph_input_declaration(
    store: CoreJSONArtifactStore,
    *,
    program_graph_ref: ProgramGraphRef,
    exec_plan_ref: ExecPlanRef,
    registry_bundle_ref: ArtifactRef,
    loaded_plan: ExecPlan | None = None,
) -> SelectedProgramGraphInputDeclaration | None:
    """Resolve a port declaration only through the actual compiled model owner.

    A readable legacy model without an opt-in keeps its original behavior.
    An opted-in model requires the selected compiler and Trinity lineage.
    The Foundry executor may supply its already-opened plan from this exact ref.
    """
    graph = validate_core_model_json_artifact(ProgramGraph, store, program_graph_ref)
    plan = loaded_plan or validate_core_model_json_artifact(ExecPlan, store, exec_plan_ref)
    if artifact_ref_identity_key(plan.program_ref) != artifact_ref_identity_key(program_graph_ref):
        raise ValueError("model_input_graph_execution_plan_mismatch")
    return _resolve_program_graph_input_declaration(
        store,
        graph=graph,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        registry_bundle_ref=registry_bundle_ref,
    )


def _resolve_program_graph_input_declaration(
    store: CoreJSONArtifactStore,
    *,
    graph: ProgramGraph,
    program_graph_ref: ProgramGraphRef,
    exec_plan_ref: ExecPlanRef,
    registry_bundle_ref: ArtifactRef,
) -> SelectedProgramGraphInputDeclaration | None:
    trinity_ref = graph.ir_ref
    bundle = _selected_model_input_bundle(store, graph)
    selected = None if bundle is None else bundle.model_spec.model_input_port_declaration_ref
    if selected is None:
        return None
    if (
        any(
            ref.manifest_profile_sha256 is None
            for ref in (program_graph_ref, exec_plan_ref, registry_bundle_ref, trinity_ref)
        )
        or graph.lowered_ir_ref is None
    ):
        raise ValueError("model_input_compiled_origin_unselected")
    declaration_ref = ArtifactRef.model_validate(selected.model_dump(mode="python"))
    trinity_manifest = store.get_manifest(trinity_ref)
    owner_bundle = load_trinity_bundle_artifact(
        ensure_ir_artifact_store(store),
        ArtifactRefModel.model_validate(trinity_ref.model_dump(mode="python")),
    )
    if owner_bundle != bundle:
        raise ValueError("model_input_trinity_owner_mismatch")
    _require_exact_compiler_edge(trinity_manifest, "model_input_port_declaration", declaration_ref)
    graph_manifest = store.get_manifest(program_graph_ref)
    _require_exact_compiler_edge(graph_manifest, "ir", trinity_ref)
    _require_exact_compiler_edge(graph_manifest, "registry_bundle", registry_bundle_ref)
    _require_exact_compiler_edge(graph_manifest, "lowered_ir", graph.lowered_ir_ref)
    for node in graph.nodes:
        if node.params_ref is not None:
            _require_exact_compiler_edge(graph_manifest, f"params:{node.node_id}", node.params_ref)
    _require_exact_compiler_edge(
        store.get_manifest(exec_plan_ref), "program_graph", program_graph_ref
    )
    return SelectedProgramGraphInputDeclaration(
        trinity_bundle_ref=trinity_ref,
        declaration_ref=declaration_ref,
        declaration=load_model_input_port_declaration(store, declaration_ref),
    )


def _selected_model_input_bundle(
    store: CoreJSONArtifactStore, graph: ProgramGraph
) -> TrinityBundle | None:
    if graph.ir_ref.kind != TrinityBundle.ARTIFACT_KIND:
        return None
    # Historical raw graph consumers can carry a policy anchor with no model.
    # Detect opt-in from the verified payload before applying its typed ABI.
    try:
        value = load_core_json_artifact(store, graph.ir_ref)
    except FileNotFoundError:
        if graph.ir_ref.manifest_profile_sha256 is None and _legacy_trinity_anchor_is_absent(
            store, graph.ir_ref
        ):
            return None
        raise
    model = value.get("model_spec") if isinstance(value, dict) else None
    if not isinstance(model, dict) or model.get("model_input_port_declaration_ref") is None:
        return None
    return validate_core_model_json_artifact(TrinityBundle, store, graph.ir_ref)


def _legacy_trinity_anchor_is_absent(store: CoreJSONArtifactStore, ref: ArtifactRef) -> bool:
    """Preserve only the old raw-graph case with no stored Trinity anchor."""
    try:
        store.get_manifest(ref)
    except FileNotFoundError:
        manifest_missing = True
    else:
        manifest_missing = False
    try:
        store.get_bytes(ref)
    except FileNotFoundError:
        payload_missing = True
    else:
        payload_missing = False
    return manifest_missing and payload_missing


def _require_exact_compiler_edge(manifest: ArtifactManifest, role: str, ref: ArtifactRef) -> None:
    if ref.manifest_profile_sha256 is None or [
        edge for edge in manifest.inputs if edge.role == role
    ] != [input_ref_from_artifact_ref(ref, role=role)]:
        raise ValueError("model_input_compiled_lineage_mismatch")


def verify_program_graph_input_preflight(
    store: CoreJSONArtifactStore,
    *,
    obligation_set_ref: ArtifactRef,
    expected_invocation: ProgramGraphInputInvocation,
) -> ModelInputObligationSet:
    """Replay the exact selected invocation and require the complete producer set.

    Runtime calls this before compiler admission using the current selected
    plan, candidate, input binding, and steps. No members or scheduler facts
    are taken from an unverified producer set to choose the replay basis.
    """
    obligation_set, members = load_model_input_obligation_set(store, obligation_set_ref)
    if obligation_set.invocation != expected_invocation:
        raise ValueError("model_input_preflight_invocation_mismatch")
    recomputed = recompute_program_graph_inputs(store, invocation=expected_invocation)
    if (
        artifact_ref_identity_key(obligation_set.prestate_ref)
        != artifact_ref_identity_key(recomputed.prestate_ref)
        or obligation_set.supplied_initial_slots != recomputed.supplied_initial_slots
        or members != recomputed.missing_obligations
    ):
        raise ValueError("model_input_preflight_replay_mismatch")
    return obligation_set


def recompute_program_graph_inputs(
    store: CoreJSONArtifactStore, *, invocation: ProgramGraphInputInvocation
) -> RecomputedProgramGraphInputs:
    """Reconcile external prestate reads against the actual selected graph ABI."""
    from polisyos.foundry.data_plane.bindings import (
        load_input_bindings,
        reconcile_explicit_initial_binding_slots,
    )

    interface_ref = invocation.interface_ref
    program_graph_ref = invocation.program_graph_ref
    exec_plan_ref = invocation.exec_plan_ref
    registry_bundle_ref = invocation.registry_bundle_ref
    input_bindings_ref = invocation.input_bindings_ref
    context = invocation.context
    parameter_override_bundle_ref = invocation.parameter_override_bundle_ref
    interface = load_program_graph_input_interface(store, interface_ref)
    if any(
        artifact_ref_identity_key(expected) != artifact_ref_identity_key(actual)
        for expected, actual in (
            (interface.program_graph_ref, program_graph_ref),
            (interface.exec_plan_ref, exec_plan_ref),
            (interface.registry_bundle_ref, registry_bundle_ref),
        )
    ):
        raise ValueError("model_input_selected_graph_mismatch")
    graph = validate_core_model_json_artifact(ProgramGraph, store, program_graph_ref)
    plan = validate_core_model_json_artifact(ExecPlan, store, exec_plan_ref)
    nodes = {node.node_id: node for node in graph.nodes}
    order = {node_id: index for index, node_id in enumerate(plan.order)}
    if (
        artifact_ref_identity_key(plan.program_ref) != artifact_ref_identity_key(program_graph_ref)
        or set(nodes) != set(order)
        or len(order) != len(plan.order)
        or any(
            edge.src not in order or edge.dst not in order or order[edge.src] >= order[edge.dst]
            for edge in graph.edges
        )
    ):
        raise ValueError("model_input_graph_execution_order_mismatch")
    selection = _resolve_program_graph_input_declaration(
        store,
        graph=graph,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        registry_bundle_ref=registry_bundle_ref,
    )
    if (
        selection is None
        or interface.declaration_ref is None
        or interface.trinity_bundle_ref is None
        or artifact_ref_identity_key(interface.declaration_ref)
        != artifact_ref_identity_key(selection.declaration_ref)
        or artifact_ref_identity_key(interface.trinity_bundle_ref)
        != artifact_ref_identity_key(selection.trinity_bundle_ref)
        or interface.ports != selection.declaration.ports
    ):
        raise ValueError("model_input_interface_not_selected_by_compiled_model")
    registry = load_registry_bundle_content(store, registry_bundle_ref)
    bindings = load_input_bindings(store, input_bindings_ref)
    if (
        input_bindings_ref.manifest_profile_sha256 is None
        or bindings.data_snapshot_ref.manifest_profile_sha256 is None
        or bindings.bound_state_snapshot_ref.manifest_profile_sha256 is None
        or not store.verify(bindings.bound_state_snapshot_ref).ok
        or artifact_ref_identity_key(bindings.registry_bundle_ref)
        != artifact_ref_identity_key(registry_bundle_ref)
    ):
        raise ValueError("model_input_bound_prestate_mismatch")
    if any(
        ref is not None and not store.verify(ref).ok
        for ref in (context.candidate_source_ref, context.context_job_ref)
    ):
        raise ValueError("model_input_selected_context_unreadable")
    overrides = _load_selected_overrides(
        store,
        ref=parameter_override_bundle_ref,
        context=context,
        program_graph_ref=program_graph_ref,
    )
    dependencies, graph_slots = _graph_input_dependencies(
        store,
        nodes=nodes,
        order=order,
        registry=registry,
        steps=invocation.steps,
        overrides=overrides,
    )

    execution_ports = {
        port.slot_id: port
        for port in interface.ports
        if port.purpose in {"initial_state", "simulation_input"}
    }
    if set(execution_ports).difference(graph_slots):
        raise ValueError("model_input_declared_port_not_read_by_graph")

    supplied_method_slots: set[str] = set()
    if bindings.schema_version == "1.4":
        from polisyos.foundry.data_plane.bindings import (
            reconcile_selected_method_input_bindings,
        )

        resolution = reconcile_selected_method_input_bindings(
            store,
            input_bindings_ref=input_bindings_ref,
        )
        records_by_slot = {record.slot_id: record for record in resolution.records}
        if len(records_by_slot) != len(resolution.records) or set(resolution.values) != set(
            records_by_slot
        ):
            raise ValueError("model_input_method_selected_inventory_duplicate")
        for slot_id, record in records_by_slot.items():
            port = execution_ports.get(slot_id)
            if (
                port is None
                or port.carrier != "method_input"
                or record.port_id != port.port_id
                or port.physical_encoding is None
                or record.dtype != port.physical_encoding.dtype
                or record.shape != port.physical_encoding.shape
            ):
                raise ValueError("model_input_method_selected_inventory_unexpected")
            selected_obligation = validate_core_model_json_artifact(
                ModelInputObligation, store, record.model_input_obligation_ref
            )
            if (
                selected_obligation.port != port
                or selected_obligation.schema_version != "1.1"
                or selected_obligation.context != context
                or selected_obligation.parameter_override_bundle_ref
                != parameter_override_bundle_ref
                or tuple(selected_obligation.dependencies) != tuple(dependencies[slot_id])
                or any(
                    artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected)
                    for actual, expected in (
                        (selected_obligation.interface_ref, interface_ref),
                        (selected_obligation.program_graph_ref, program_graph_ref),
                        (selected_obligation.exec_plan_ref, exec_plan_ref),
                        (selected_obligation.registry_bundle_ref, registry_bundle_ref),
                    )
                )
            ):
                raise ValueError("model_input_method_selected_obligation_mismatch")
            supplied_method_slots.add(slot_id)

    paths: dict[str, str] = {}
    for slot_id in sorted(graph_slots):
        slot = registry.slot_registry.slots.get(slot_id)
        if slot is None:
            raise ValueError("model_input_required_slot_unresolved")
        port = execution_ports.get(slot_id)
        if slot.state_path is None:
            if (
                port is None
                or port.carrier != "method_input"
                or not any(
                    dependency.kind == "method_read" for dependency in dependencies.get(slot_id, ())
                )
            ):
                raise ValueError("model_input_method_port_unresolved")
        elif port is not None and port.carrier == "method_input":
            raise ValueError("model_input_method_port_shadows_state_slot")
        if port is not None:
            representation = verify_model_input_port_semantics(store, port)
            if (
                port.state_path != slot.state_path
                or slot.unit is None
                or port.unit_id != slot.unit.unit_id
                or representation.quantity_kind != slot.kind.value
            ):
                raise ValueError("model_input_port_registry_mismatch")
            encoding = port.physical_encoding
            scalar_profile = (
                encoding is not None
                and not encoding.shape
                and slot.scope == SlotScope.GLOBAL
                and not slot.shape
            )
            singleton_flow_profile = (
                encoding is not None
                and encoding.shape == (1,)
                and slot.scope == SlotScope.PER_AGENT
                and slot.kind == SlotKind.FLOW
                and port.purpose == "simulation_input"
                and not slot.shape
            )
            if (
                encoding is None
                or not (scalar_profile or singleton_flow_profile)
                or slot.value_type != SlotValueType.DECIMAL
                or (slot.dtype is not None and slot.dtype != encoding.dtype)
            ):
                raise ValueError("model_input_port_physical_profile_unsupported")
            method_input_unit = (
                None
                if registry.units_registry is None
                else registry.units_registry.units.get(port.unit_id)
            )
            if port.carrier == "method_input" and (
                port.purpose != "simulation_input"
                or slot.state_path is not None
                or slot.scope != SlotScope.GLOBAL
                or slot.value_type != SlotValueType.DECIMAL
                or slot.kind != SlotKind.FLOW
                or slot.shape
                or encoding is None
                or encoding.shape
                or representation.time_support != "period_total"
                or representation.temporal_granularity != "annual"
                or representation.money_unit is None
                or not isinstance(method_input_unit, MoneyUnit)
                or representation.money_unit.currency != method_input_unit.currency
            ):
                raise ValueError("model_input_method_port_physical_profile_unsupported")
        if slot.state_path is not None:
            paths[slot_id] = slot.state_path

    method_input_ports = tuple(
        port for port in execution_ports.values() if port.carrier == "method_input"
    )
    if method_input_ports:
        _require_selected_method_input_period(
            store,
            graph=graph,
            ports=method_input_ports,
            steps=invocation.steps,
        )

    legacy_paths = {
        slot_id: paths[slot_id]
        for slot_id in dependencies
        if slot_id not in execution_ports and slot_id in paths
    }
    supplied: tuple[str, ...] = ()
    if legacy_paths:
        supplied = reconcile_explicit_initial_binding_slots(
            store,
            input_bindings_ref=input_bindings_ref,
            expected_state_paths=legacy_paths,
        )
    if set(supplied) != set(legacy_paths):
        raise ValueError("model_input_graph_dependency_unexplained")

    obligations = tuple(
        ModelInputObligation(
            context=context,
            interface_ref=interface_ref,
            program_graph_ref=program_graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=registry_bundle_ref,
            input_bindings_ref=input_bindings_ref,
            prestate_ref=bindings.bound_state_snapshot_ref,
            parameter_override_bundle_ref=parameter_override_bundle_ref,
            port=port,
            dependencies=tuple(dependencies[slot_id]),
            schema_version=(
                "1.1"
                if port.carrier == "method_input"
                or any(item.kind == "method_read" for item in dependencies[slot_id])
                else "1.0"
            ),
        )
        for slot_id, port in sorted(execution_ports.items())
        if slot_id in dependencies
        and not (port.carrier == "method_input" and slot_id in supplied_method_slots)
    )
    return RecomputedProgramGraphInputs(bindings.bound_state_snapshot_ref, supplied, obligations)


def _load_selected_overrides(
    store: CoreJSONArtifactStore,
    *,
    ref: ParameterOverrideBundleRef | None,
    context: ModelInputContext,
    program_graph_ref: ProgramGraphRef,
) -> dict[str, dict[str, object]]:
    if ref is None:
        return {}
    if ref.manifest_profile_sha256 is None or context.candidate_source_ref is None:
        raise ValueError("model_input_override_owner_unselected")
    expected_inputs = (
        input_ref_from_artifact_ref(program_graph_ref, role="selected_program_graph"),
        input_ref_from_artifact_ref(context.candidate_source_ref, role="selected_candidate_source"),
    )
    inputs = store.get_manifest(ref).inputs
    if any(item not in inputs for item in expected_inputs):
        raise ValueError("model_input_override_owner_mismatch")
    return validate_core_model_json_artifact(ParameterOverrideBundle, store, ref).overrides


def _graph_input_dependencies(
    store: CoreJSONArtifactStore,
    *,
    nodes: dict[str, ProgramNode],
    order: dict[str, int],
    registry: RegistryBundleContent,
    steps: tuple[int, ...],
    overrides: dict[str, dict[str, object]],
) -> tuple[dict[str, list[ProgramGraphInputDependency]], set[str]]:
    dependencies: dict[str, list[ProgramGraphInputDependency]] = {}
    graph_slots: set[str] = set()
    mechanism_nodes: set[str] = set()
    method_fqns: set[str] = set()
    method_writes: dict[str, set[str]] = {}
    method_reads: dict[str, set[str]] = {}
    for node_id in order:
        node = nodes[node_id]
        op = node.op
        if node.node_kind == "method":
            if op is not None or node.mechanism_type is not None or not node.method_fqn:
                raise ValueError("model_input_graph_method_unresolved")
            if node.method_fqn in method_fqns:
                raise ValueError("model_input_graph_method_instance_duplicate")
            method_fqns.add(node.method_fqn)
            if node.method_version is None:
                raise ValueError("model_input_method_version_unselected")
            try:
                from polisyos.foundry.methods.registry import MethodRegistry

                method_class = MethodRegistry.get_instance().get(
                    node.method_fqn, version=node.method_version
                )
            except Exception as exc:
                raise ValueError("model_input_method_registry_unresolved") from exc
            from polisyos.foundry.methods.types import validate_registered_method_input

            signature = method_class.signature
            if signature.fqn != node.method_fqn or signature.version != node.method_version:
                raise ValueError("model_input_method_registry_mismatch")
            method_abi_digest = signature.abi_digest()
            signature_inputs = {slot.name: slot for slot in signature.input_slots}
            if set(node.inputs) != set(signature_inputs):
                raise ValueError("model_input_method_abi_join_not_exact")
            if signature.patch_targets:
                from polisyos.foundry.methods.patch_contracts import (
                    validate_method_patch_targets,
                )

                try:
                    validate_method_patch_targets(
                        signature,
                        params=node.method_params,
                        declared_outputs=node.outputs,
                        registry=registry,
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("model_input_method_patch_target_mismatch") from exc
            elif node.outputs:
                raise ValueError("model_input_method_patch_target_contract_missing")
            if len(node.inputs) != len(set(node.inputs)) or len(node.outputs) != len(
                set(node.outputs)
            ):
                raise ValueError("model_input_method_abi_join_not_exact")
            method_reads[node_id] = set(node.inputs)
            method_writes[node_id] = set(node.outputs)
            method_step = steps[0]
            for slot_id in node.inputs:
                slot = registry.slot_registry.slots.get(slot_id)
                if slot is None:
                    raise ValueError("model_input_method_slot_unregistered")
                if slot.state_path is None:
                    try:
                        validate_registered_method_input(
                            signature,
                            input_slot_id=slot_id,
                            registered_slot_id=slot_id,
                            registry=registry,
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError("model_input_method_slot_profile_unsupported") from exc
                dependencies.setdefault(slot_id, []).append(
                    ProgramGraphInputDependency(
                        node_id=node_id,
                        kind="method_read",
                        first_required_step=method_step,
                        method_abi_digest=method_abi_digest,
                    )
                )
            for slot_id in node.outputs:
                target = registry.slot_registry.slots.get(slot_id)
                if target is None or not target.state_path:
                    raise ValueError("model_input_method_write_slot_unresolved")
                _require_additive_prestate(registry, slot_id, target.merge_rule.rule_id)
                dependencies.setdefault(slot_id, []).append(
                    ProgramGraphInputDependency(
                        node_id=node_id,
                        kind="additive_prestate",
                        first_required_step=method_step,
                    )
                )
            graph_slots.update(node.inputs)
            graph_slots.update(node.outputs)
            continue
        if node.node_kind != "op" or op is None:
            raise ValueError("model_input_graph_operation_unsupported")
        if op.op_kind == "make_mask":
            _require_structural_selector(op.params.get("selector"))
            continue
        if (op.op_kind == "merge_state" and not op.params) or (
            op.op_kind == "check_constraints" and op.params == {"constraint_ids": []}
        ):
            continue
        if op.op_kind != "apply_mechanism" or node.mechanism_type is None:
            raise ValueError("model_input_graph_operation_unsupported")
        mechanism_nodes.add(node_id)
        mechanism = registry.mechanism_registry.mechanisms.get(node.mechanism_type)
        runtime_spec = get_mechanism_spec(node.mechanism_type)
        if (
            mechanism is None
            or sorted(node.inputs) != sorted(mechanism.reads_slots)
            or sorted(node.outputs) != sorted(mechanism.writes_slots)
            or sorted(mechanism.reads_slots) != sorted(runtime_spec.reads_slots)
            or sorted(mechanism.writes_slots) != sorted(runtime_spec.writes_slots)
            or mechanism.default_merge != runtime_spec.default_merge
        ):
            raise ValueError("model_input_mechanism_registry_mismatch")
        payload = _load_mechanism_payload(store, node)
        mask_id = op.params.get("mask_id")
        if mask_id is None:
            _require_structural_selector(payload.get("selector"))
        elif (
            not isinstance(mask_id, str)
            or mask_id not in order
            or order[mask_id] >= order[node_id]
            or nodes[mask_id].op is None
            or nodes[mask_id].op.op_kind != "make_mask"
        ):
            raise ValueError("model_input_mechanism_selector_unresolved")

        params = payload.get("params")
        if not isinstance(params, dict):
            raise ValueError("model_input_mechanism_params_unresolved")
        validate_mechanism_params(
            node.mechanism_type,
            {**params, **overrides.get(node_id, {})},
            mechanism_spec=mechanism,
        )
        start, end = schedule_range(ScheduleSpec.model_validate(payload.get("schedule")))
        first_step = next((step for step in steps if start <= step <= end), None)
        for slot_id in mechanism.writes_slots:
            _require_additive_prestate(registry, slot_id, mechanism.default_merge.get(slot_id))
        graph_slots.update(mechanism.reads_slots)
        graph_slots.update(mechanism.writes_slots)
        if first_step is not None:
            for slot_id in mechanism.reads_slots:
                dependencies.setdefault(slot_id, []).append(
                    ProgramGraphInputDependency(
                        node_id=node_id, kind="mechanism_read", first_required_step=first_step
                    )
                )
            for slot_id in mechanism.writes_slots:
                dependencies.setdefault(slot_id, []).append(
                    ProgramGraphInputDependency(
                        node_id=node_id, kind="additive_prestate", first_required_step=first_step
                    )
                )
    for writer_node, writes in method_writes.items():
        if any(
            reader_node != writer_node and writes.intersection(reads)
            for reader_node, reads in method_reads.items()
        ):
            raise ValueError("model_input_method_internal_dataflow_unsupported")
    if set(overrides).difference(mechanism_nodes):
        raise ValueError("model_input_override_node_unresolved")
    return dependencies, graph_slots


def _require_selected_method_input_period(
    store: CoreJSONArtifactStore,
    *,
    graph: ProgramGraph,
    ports: tuple[ModelInputPort, ...],
    steps: tuple[int, ...],
) -> None:
    """Bind scalar method input values to one explicit annual model transition."""
    if len(steps) != 1:
        raise ValueError("model_input_method_multi_step_reuse_unsupported")
    bundle = _selected_model_input_bundle(store, graph)
    semantics = None if bundle is None else bundle.model_spec.time_semantics
    if semantics is None or semantics.frequency.value != "Y":
        raise ValueError("model_input_method_time_semantics_not_established")
    step = steps[0]
    if semantics.step_count is not None and step >= semantics.step_count:
        raise ValueError("model_input_method_step_outside_model_horizon")
    try:
        period_start = semantics.date_for_step(step)
        period_end = semantics.date_for_step(step + 1) - timedelta(days=1)
    except (OverflowError, ValueError) as exc:
        raise ValueError("model_input_method_time_semantics_not_established") from exc
    if semantics.end_date is not None and period_end > date.fromisoformat(semantics.end_date):
        raise ValueError("model_input_method_step_outside_model_horizon")
    for port in ports:
        scope = port.scope
        if scope.period_basis not in {"calendar_year", "fiscal_year"}:
            raise ValueError("model_input_method_period_basis_not_established")
        if scope.period_basis == "calendar_year" and (
            period_start.month != 1
            or period_start.day != 1
            or period_end.month != 12
            or period_end.day != 31
        ):
            raise ValueError("model_input_method_calendar_year_mismatch")
        if scope.period_start != period_start or scope.period_end != period_end:
            raise ValueError("model_input_method_transition_period_mismatch")


def _load_mechanism_payload(store: CoreJSONArtifactStore, node: ProgramNode) -> dict[str, object]:
    ref = node.params_ref
    if ref is None or ref.manifest_profile_sha256 is None:
        raise ValueError("model_input_mechanism_payload_ref_unselected")
    manifest = store.get_manifest(ref)
    if (
        manifest.kind != "foundry.lowered_mechanism_payload"
        or manifest.artifact_schema
        != SchemaInfo(name="polisyos.foundry.LoweredMechanismPayload", version="0.2.0")
    ):
        raise ValueError("model_input_mechanism_payload_profile_mismatch")
    payload = load_core_json_artifact(store, ref)
    if not isinstance(payload, dict) or payload.get("mechanism_id") != node.mechanism_type:
        raise ValueError("model_input_mechanism_payload_unresolved")
    return payload


def _require_structural_selector(payload: object) -> None:
    selector = SelectorPredicate.model_validate(payload)
    if (
        selector.field not in {"id", "agent_id"}
        or not isinstance(selector.value, str)
        or selector.value.strip().casefold() not in {"all", "any"}
    ):
        raise ValueError("model_input_data_dependent_selector_unsupported")


def _require_additive_prestate(
    registry: RegistryBundleContent, slot_id: str, declared_merge_id: str | None
) -> None:
    slot = registry.slot_registry.slots.get(slot_id)
    if slot is None or slot.merge_rule.rule_id != declared_merge_id:
        raise ValueError("model_input_additive_prestate_unresolved")
    merge_rule = registry.merge_registry.rules.get(slot.merge_rule.rule_id)
    if merge_rule is None or merge_rule.kind != MergeRuleKind.SUM:
        raise ValueError("model_input_additive_prestate_unresolved")
