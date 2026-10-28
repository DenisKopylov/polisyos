"""Fresh bounded source-use projection for one restricted Foundry execution."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.canonical_profile import read_core_manifest_profile_bounded
from polisyos.core.artifacts.manifest import artifact_ref_identity_key, input_ref_from_artifact_ref
from polisyos.core.contracts.decision_validity import (
    RegisteredSQLAdmissionBinding,
    RegisteredSQLUseContract,
    source_admission_basis_digest,
)
from polisyos.core.contracts.fabric import DataSnapshotOwnerBound
from polisyos.core.contracts.foundry import (
    FoundryInputBindings,
    MethodExecutionBundle,
    ProgramGraph,
)
from polisyos.core.contracts.runtime import ExAnteSourceUseDebugView, GraphMethodExecutionSelection
from polisyos.core.security import AccessScope, get_current_access_scope_or_none, tenant_scope
from polisyos.ir.kernel.slots import SlotRegistry
from polisyos.runtime.http.resilience import _require_runtime_ambient_ownership

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.contracts.foundry import FoundryExecutionInputBasis
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.runtime.http.services.run_index import IndexedRunRecord
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _ProjectionReadBudget,
        _VerifiedRestrictedExAnteCall,
    )


def _unknown(reason: str) -> ExAnteSourceUseDebugView:
    return ExAnteSourceUseDebugView(
        status="unknown", method_replay_status="verification_missing", limitations=(reason,)
    )


def _same(left: ArtifactRef, right: ArtifactRef) -> bool:
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


def _is_supported_restricted_graph(graph: ProgramGraph, *, method_node_id: str) -> bool:
    """Admit the compiler-derived empty housekeeping closure for one method.

    The completed-score owner separately replays the complete canonical graph
    and plan. This check narrows that graph to a method that cannot depend on a
    hidden mechanism, constraint, additional input or operation. The compiler
    owns housekeeping names and collision handling.
    """
    from polisyos.foundry.compile._graph import _build_op_nodes

    if len(graph.nodes) != 3:
        return False
    method = graph.nodes[0]
    housekeeping, edges = _build_op_nodes([method], [])
    return (
        method.node_id == method_node_id
        and method.node_kind == "method"
        and method.mechanism_type is None
        and method.op is None
        and method.params_ref is None
        and len(method.inputs) == 2
        and set(method.inputs) == {"baseline", "scenario"}
        and method.outputs == []
        and graph.nodes == [method, *housekeeping]
        and graph.entrypoints == [method_node_id]
        and graph.edges == edges
    )


def _require_bound_blob(
    store: ArtifactStore, *, state_ref: ArtifactRef, expected: bytes, budget: _ProjectionReadBudget
) -> None:
    """Check the actual selected state bytes under one measured aggregate allowance."""
    remaining = budget.remaining_bytes
    manifest_limit = min(budget.max_manifest_bytes, remaining // 4)
    if manifest_limit < 1 or len(expected) > remaining - 2 * manifest_limit:
        raise ValueError("registered_sql_bound_state_budget_exceeded")
    selected = read_core_manifest_profile_bounded(
        store, state_ref, max_manifest_bytes=manifest_limit
    )
    measured = selected.observed_source_bytes
    if type(measured) is not int or measured < 0:
        raise ValueError("registered_sql_bound_state_usage_unavailable")
    budget.account_execution_source_bytes(measured)
    if (
        selected.effective_ref != state_ref
        or selected.manifest.kind != "foundry.state_blob"
        or selected.manifest.media_type != "application/x-npz"
        or selected.manifest.byte_size != len(expected)
    ):
        raise ValueError("registered_sql_bound_state_manifest_mismatch")
    remaining = budget.remaining_bytes
    if len(expected) > remaining - manifest_limit:
        raise ValueError("registered_sql_bound_state_budget_exceeded")
    with store.open_member_bounded(
        state_ref,
        "blob",
        max_manifest_bytes=manifest_limit,
        expected_manifest_sha256=hashlib.sha256(selected.raw_manifest_bytes).hexdigest(),
        max_member_bytes=remaining - manifest_limit,
    ) as member:
        if member.member_size_bytes != len(expected):
            raise ValueError("registered_sql_bound_state_size_mismatch")
        offset = 0
        while offset < len(expected):
            part = member.read(min(1024 * 1024, len(expected) - offset))
            if not part or part != expected[offset : offset + len(part)]:
                raise ValueError("registered_sql_bound_state_bytes_mismatch")
            offset += len(part)
        if member.read(1):
            raise ValueError("registered_sql_bound_state_size_mismatch")
    manifest_bytes = member.observed_manifest_verification_bytes
    payload_bytes = member.observed_payload_bytes
    if (
        type(manifest_bytes) is not int
        or type(payload_bytes) is not int
        or manifest_bytes < 0
        or payload_bytes != len(expected)
        or member.payload_integrity_verified is not True
    ):
        raise ValueError("registered_sql_bound_state_integrity_not_established")
    budget.account_execution_source_bytes(manifest_bytes + payload_bytes)


def _reconcile_selected_sql_inputs(
    store: ArtifactStore,
    *,
    basis: FoundryExecutionInputBasis,
    call: _VerifiedRestrictedExAnteCall,
    budget: _ProjectionReadBudget,
) -> None:
    """Replay the consumed rows and compare the real captured method arrays."""
    import numpy as np

    from polisyos.core.contracts.foundry import StateSnapshot
    from polisyos.foundry.data_plane.bindings import _recompute_registered_sql_state
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        MAX_METHOD_METRIC_SOURCE_BYTES,
        _BoundedExecutionSourceReader,
        _read_bounded_method_metric_artifact,
        _selected_ref,
    )

    reader = _BoundedExecutionSourceReader(cast("Any", store), budget)
    _, bindings, _, _ = reader.read_typed_model(FoundryInputBindings, basis.input_bindings_ref)
    _, snapshot, _, _ = reader.read_typed_model(DataSnapshotOwnerBound, basis.data_snapshot_ref)
    slot_ref = basis.binding_registry_members.slot_registry
    slot_manifest, slots, _, _ = reader.read_typed_model(SlotRegistry, slot_ref)
    if (
        slot_ref.kind != "ir.slot_registry"
        or slot_manifest.artifact_schema
        != SchemaInfo(name="polisyos.ir.kernel.SlotRegistry", version="1.0")
        or not _same(bindings.data_snapshot_ref, basis.data_snapshot_ref)
        or not _same(bindings.bound_state_snapshot_ref, basis.bound_state_snapshot_ref)
    ):
        raise ValueError("registered_sql_replay_input_identity_mismatch")
    payload_ref = _selected_ref(snapshot.data_ref, kind="fabric.tabular_payload")
    payload = _read_bounded_method_metric_artifact(
        cast("Any", store),
        ref=payload_ref,
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=budget,
    )
    if payload.manifest.kind != "fabric.tabular_payload":
        raise ValueError("registered_sql_replay_payload_mismatch")
    encoded, entry_count = _recompute_registered_sql_state(
        cast("Any", store),
        snapshot=snapshot,
        payload=payload.value,
        slot_registry=slots,
        rules=bindings.rules,
    )
    state_manifest, state, _, _ = reader.read_typed_model(
        StateSnapshot, basis.bound_state_snapshot_ref
    )
    expected_inputs = [
        input_ref_from_artifact_ref(basis.data_snapshot_ref, role="input.data_snapshot_ref"),
        input_ref_from_artifact_ref(basis.binding_registry_ref, role="input.registry_bundle_ref"),
        input_ref_from_artifact_ref(state.state_ref, role="state_blob"),
    ]
    if (
        state.schema_version != "2.2"
        or state.checksum_sha256 != hashlib.sha256(encoded).hexdigest()
        or state.state_ref.artifact_id.hex != state.checksum_sha256
        or state.entry_count != entry_count
        or state.lineage_inputs != expected_inputs
        or state_manifest.inputs != expected_inputs
    ):
        raise ValueError("registered_sql_replay_state_mismatch")
    _require_bound_blob(store, state_ref=state.state_ref, expected=encoded, budget=budget)
    captured = call.input_values
    if tuple(item.slot_id for item in captured) != ("baseline", "scenario") or not {
        "baseline",
        "scenario",
    }.issubset({rule.target_slot_id for rule in bindings.rules}):
        raise ValueError("registered_sql_replay_input_inventory_mismatch")
    with np.load(BytesIO(encoded), allow_pickle=False) as state_arrays:
        for item in captured:
            slot = slots.slots.get(item.slot_id)
            path = slot.state_path if slot is not None else None
            if not path or path not in state_arrays:
                raise ValueError("registered_sql_replay_input_path_missing")
            value = state_arrays[path]
            if (
                value.dtype.str != item.dtype
                or tuple(value.shape) != item.shape
                or value.tobytes(order="C")
                != np.asarray(item.values, dtype=value.dtype).reshape(item.shape).tobytes(order="C")
            ):
                raise ValueError("registered_sql_replay_method_input_mismatch")


def read_registered_sql_source_use(
    *,
    store: ArtifactStore,
    control: ControlPlaneService,
    run: IndexedRunRecord,
    simulation_ref: ArtifactRef,
) -> ExAnteSourceUseDebugView:
    """Recompute one profile and query the installed C105 owner at every read."""
    from polisyos.runtime.http.services.adapters.core_run import _terminal_workflow_output_refs
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _admit_execution_source_candidate,
        _BoundedExecutionSourceReader,
        _MethodMetricSourceTuple,
        _ProjectionReadBudget,
    )

    tenant, cell = run.details.tenant_id, run.details.cell_id
    scope = get_current_access_scope_or_none()
    if (
        not isinstance(scope, AccessScope)
        or not tenant
        or not cell
        or (scope.tenant_id, scope.cell_id) != (tenant, cell)
    ):
        return _unknown("registered_sql_caller_scope_not_established")
    owner = control._decision_validity_service
    if not tenant or not cell or owner is None or owner._store is not store:
        return _unknown("registered_sql_owner_or_scope_not_established")
    try:
        _require_runtime_ambient_ownership(store)
        with tenant_scope(None, tenant_id=tenant, cell_id=cell):
            manifest_ref = run.details.manifest_ref
            if manifest_ref is None:
                raise ValueError("terminal_manifest_missing")
            final_state, report, unscoped = _terminal_workflow_output_refs(
                store=store,
                run_dir=run.run_dir,
                run_id=run.run_id,
                tenant_id=tenant,
                cell_id=cell,
                expected_manifest_ref=manifest_ref,
            )
            if (
                unscoped
                or run.experiment_state_ref is None
                or run.workflow_report_ref is None
                or not _same(final_state, run.experiment_state_ref)
                or not _same(report, run.workflow_report_ref)
            ):
                raise ValueError("terminal_finalization_not_established")
            selection = control.get_method_execution_selection(
                run_id=run.run_id, tenant_id=tenant, cell_id=cell
            )
            if (
                type(selection) is not GraphMethodExecutionSelection
                or not _same(selection.source_experiment_state_ref, final_state)
                or not _same(selection.simulation_result_ref, simulation_ref)
            ):
                raise ValueError("registered_sql_method_selection_not_established")
            calls: list[Any] = []
            score = control.read_current_completed_ex_ante_candidate_score(
                run_id=run.run_id,
                tenant_id=tenant,
                cell_id=cell,
                require_restricted_exante_call_witness=True,
                restricted_exante_call_collector=calls,
            )
            if score.status != "selected" or len(calls) != 1:
                raise ValueError("registered_sql_method_replay_not_established")
            call = calls[0]
            source = _MethodMetricSourceTuple(
                job_id=selection.job_id,
                run_id=selection.run_id,
                attempt=selection.attempt,
                method_result_ref=None,
                simulation_result_ref=selection.simulation_result_ref,
                method_execution_bundle_ref=selection.method_execution_bundle_ref,
                method_metric_binding_set_ref=selection.method_metric_binding_set_ref,
            )
            budget = _ProjectionReadBudget()
            bases: list[Any] = []
            _admit_execution_source_candidate(
                cast("Any", store),
                source_tuple=source,
                read_budget=budget,
                comparison_basis_collector=bases,
            )
            if len(bases) != 1 or bases[0].registered_sql_admission_ref is None:
                raise ValueError("registered_sql_selected_basis_missing")
            basis = bases[0]
            reader = _BoundedExecutionSourceReader(cast("Any", store), budget)
            _, graph, _, _ = reader.read_typed_model(ProgramGraph, basis.program_graph_ref)
            _, bundle, _, _ = reader.read_typed_model(
                MethodExecutionBundle, selection.method_execution_bundle_ref
            )
            if (
                len(bundle.occurrences) != 1
                or bundle.occurrences[0] != call.occurrence
                or not _is_supported_restricted_graph(graph, method_node_id=call.occurrence.node_id)
                or call.occurrence.dispatch is None
                or call.occurrence.dispatch.input_state_source_ref is None
                or not _same(
                    call.occurrence.dispatch.input_state_source_ref, basis.base_state_snapshot_ref
                )
            ):
                raise ValueError("registered_sql_restricted_graph_not_established")
            _reconcile_selected_sql_inputs(store, basis=basis, call=call, budget=budget)
            source_ref = basis.registered_sql_admission_ref
            _, binding, _, _ = reader.read_typed_model(RegisteredSQLAdmissionBinding, source_ref)
            materialization = binding.materialization
            carrier = binding.receipt.carrier
            if (
                carrier is None
                or (carrier.tenant_id, carrier.cell_id) != (tenant, cell)
                or not _same(materialization.snapshot_ref, basis.data_snapshot_ref)
                or not _same(carrier.snapshot_ref, basis.data_snapshot_ref)
            ):
                raise ValueError("registered_sql_carrier_basis_mismatch")
            _, use, _, _ = reader.read_typed_model(
                RegisteredSQLUseContract, materialization.registration.use_contract_ref
            )
            if (
                use.use_key != RegisteredSQLUseContract.FOUNDRY_SELECTED_BASIS_USE_KEY
                or use.selection_mode != "any_active"
            ):
                raise ValueError("registered_sql_use_not_supported")
            original = owner.resolve_source_materialization_history(
                carrier, event_id=binding.receipt.event_id
            )
            if original != (binding.receipt, materialization, binding.expected_predecessor):
                raise ValueError("registered_sql_original_history_mismatch")
            projection = owner.read_source_current_use((carrier,), require_selected=False)
            if (
                projection.status not in {"current", "withdrawn"}
                or projection.selection_checked
                or projection.basis_digest
                != source_admission_basis_digest((carrier,), require_selected=False)
                or (
                    projection.status == "current"
                    and projection.predicate_provenance != "recomputed"
                )
            ):
                raise ValueError("registered_sql_current_use_not_established")
            if (
                control.get_method_execution_selection(
                    run_id=run.run_id, tenant_id=tenant, cell_id=cell
                )
                != selection
            ):
                raise ValueError("registered_sql_selection_changed_during_read")
            return ExAnteSourceUseDebugView(
                status=projection.status,
                method_replay_status="verified",
                source_basis_ref=source_ref,
                method_execution_bundle_ref=selection.method_execution_bundle_ref,
                input_capture_ref=call.input_capture_ref,
                owner_current_use=projection,
                recomputed_mean_change=(
                    float(call.output_payload.value) if projection.status == "current" else None
                ),
            )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return _unknown("registered_sql_source_use_not_established")
