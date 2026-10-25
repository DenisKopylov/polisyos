"""Real owner-attempt coverage for spawn transportability timeout wire."""

from __future__ import annotations

import json
import logging
import sys
import time
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    RunTransportabilityNode,
)
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _EngineInvocationBinding,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    _build_spawn_timeout_task,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.runner._activity_worker import (
    _build_timeout_worker_context,
)
from polisyos.scientist.orchestration.engine.runner.serialization import (
    _TIMEOUT_CONTEXT_WIRE_SCHEMA,
    _timeout_worker_params_match,
    serialize_timeout_context,
    worker_dispatch_sha256,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import (
    NodeInvocation,
    WorkflowSpec,
)

_COMPONENT_ID = "scientist.node_run_transportability@1.0.0"
_ALIAS = "run_transportability"
_PARAMS = {"profile_id": "controlled-test-v1", "selection_identity": "fixture-choice"}


def _task_supervisor_deadline(task):
    return float.fromhex(
        task.context_meta["engine_invocation"]["supervisor_deadline_monotonic_hex"]
    )


@pytest.fixture
def current_transport_attempt(tmp_path):
    tenant_id = "tenant-timeout-transport"
    cell_id = "cell-timeout-transport"
    run_id = "R_timeout_transport_wire"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        store = FileSystemCAS(
            tmp_path / "cas",
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        registry = build_default_registry_bundle(
            store,
            return_selected_profile=True,
        )
        run = RunContext.start(
            store=store,
            registry_bundle=registry.bundle_ref,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        workflow = WorkflowSpec(
            workflow_id="transport_wire",
            nodes=[
                NodeInvocation(
                    alias=_ALIAS,
                    node_id=_COMPONENT_ID,
                    params=_PARAMS,
                    timeout_s=120.0,
                )
            ],
        )
        workflow_ref = store.put_json(
            workflow.model_dump(mode="json"),
            PutOptions(
                kind="scientist.workflow_spec",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowSpec",
                    version="1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        state = ExperimentState(run_id=run_id)
        state.params = {
            "nested": {"count": 1, "enabled": True},
            "values": [1.0, 0.0],
        }
        state_ref = store.put_json(
            state.model_dump(mode="json"),
            PutOptions(
                kind="scientist.experiment_state",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.ExperimentState",
                    version=state.schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        attempt_id = str(uuid4())
        from polisyos.scientist.orchestration.engine.component_identity import (
            capture_engine_component_identity,
        )

        implementation_identity = capture_engine_component_identity(
            RunTransportabilityNode(),
            _COMPONENT_ID,
            _PARAMS,
        )
        assert implementation_identity is not None
        basis_ref = run._record_runtime_invocation_started(
            attempt_id=attempt_id,
            attempt_number=1,
            workflow_spec_ref=workflow_ref,
            node_alias=_ALIAS,
            component_id=_COMPONENT_ID,
            input_state_ref=state_ref,
            implementation_identity=implementation_identity,
        )
        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger("test.timeout_transport_wire"),
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt_id,
                basis_ref=basis_ref,
            ),
        )
        try:
            yield ctx, state, workflow, attempt_id, basis_ref
        finally:
            run.suspend_for_resume()


def test_transportability_spawn_wire_binds_and_revalidates_live_attempt(
    current_transport_attempt,
):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        serialize_state,
    )
    from polisyos.scientist.orchestration.engine.state_branching import branch_state

    ctx, state, _workflow, attempt_id, basis_ref = current_transport_attempt
    live_state = branch_state(state).state

    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        ctx,
        live_state,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
        timeout_s=30.0,
        supervisor_deadline_monotonic=time.monotonic() + 30.0,
    )

    attempt = ctx.run.read_runtime_invocation_attempts()[0]
    persisted_state = ExperimentState.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(attempt.basis.input_state_ref))
    )
    assert task.state_bytes == serialize_state(persisted_state)

    assert task.timeout_s is None
    assert task.context_meta["schema"] == "polisyos.scientist.timeout_context.v3"
    engine = task.context_meta["engine_invocation"]
    assert engine["attempt_id"] == attempt_id
    assert engine["basis_ref"] == basis_ref.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=False,
    )
    assert engine["declared_timeout_s_hex"] == (120.0).hex()
    assert 0.0 < float.fromhex(engine["effective_timeout_s_hex"]) <= 30.0
    assert engine["supervisor_deadline_monotonic_hex"] == time.monotonic().hex() or (
        float.fromhex(engine["supervisor_deadline_monotonic_hex"]) > time.monotonic()
    )

    worker = _build_timeout_worker_context(
        task.context_meta,
        invocation_id=task.worker_invocation_id,
        dispatch_sha256=task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=_PARAMS,
        expected_supervisor_deadline_monotonic=_task_supervisor_deadline(task),
        state=persisted_state,
    )
    assert worker._engine_invocation.attempt_id == attempt_id
    assert worker._engine_invocation.basis_ref == basis_ref
    attempt_records = worker.run.read_runtime_invocation_attempts()
    assert len(attempt_records) == 1
    assert attempt_records[0].basis.attempt_id == attempt_id
    assert attempt_records[0].outcome is None

    forged = {**task.context_meta, "engine_invocation": dict(engine)}
    forged["engine_invocation"]["attempt_id"] = str(uuid4())
    forged_digest = worker_dispatch_sha256(
        node_id=_COMPONENT_ID,
        alias=_ALIAS,
        params=_PARAMS,
        state_bytes=task.state_bytes,
        trace_carrier=task.trace_carrier,
        timeout_s=task.timeout_s,
        max_retries=0,
        context_meta=forged,
    )
    assert forged_digest != task.worker_dispatch_sha256
    with pytest.raises(ValueError, match="timeout_worker_engine_attempt_not_current"):
        _build_timeout_worker_context(
            forged,
            invocation_id=task.worker_invocation_id,
            dispatch_sha256=task.worker_dispatch_sha256,
            expected_component_id=_COMPONENT_ID,
            expected_alias=_ALIAS,
            expected_params=_PARAMS,
            expected_supervisor_deadline_monotonic=_task_supervisor_deadline(task),
            state=state,
        )

    stale_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=ctx.run.run_manifest.run_id,
            attempt_id=str(uuid4()),
            basis_ref=basis_ref,
        ),
    )
    with pytest.raises(ValueError, match="timeout_worker_engine_attempt_not_current"):
        _build_spawn_timeout_task(
            RunTransportabilityNode(),
            stale_ctx,
            state,
            alias=_ALIAS,
            dispatch_params=_PARAMS,
            timeout_s=30.0,
            supervisor_deadline_monotonic=time.monotonic() + 30.0,
        )

    with pytest.raises(ValueError, match="timeout_worker_engine_workflow_node_mismatch"):
        _build_spawn_timeout_task(
            RunTransportabilityNode(),
            ctx,
            state,
            alias=_ALIAS,
            dispatch_params=_PARAMS,
            timeout_s=121.0,
            supervisor_deadline_monotonic=time.monotonic() + 121.0,
        )


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS spawn timeout path")
def test_transportability_node_runs_through_spawn_worker(current_transport_attempt):
    ctx, state, _workflow, _attempt_id, _basis_ref = current_transport_attempt

    outcome = execute_with_retry_sync(
        RunTransportabilityNode(),
        ctx,
        state,
        retry_policy=RetryPolicy(max_retries=0),
        timeout_s=30.0,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
    )

    assert type(outcome) is NodeOutcome
    assert outcome.status in {"skip", "fail"}
    assert outcome.state.run_id == state.run_id
    trace_path = ctx.run.trace_path
    assert trace_path is not None
    durable_trace = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(item["event"] == "WORKER_INVOCATION_STARTED" for item in durable_trace) == 1
    assert sum(item["event"] == "WORKER_INVOCATION_COMPLETED" for item in durable_trace) == 1
    dispatches = [
        item.get("worker_dispatch_sha256")
        for item in durable_trace
        if item.get("worker_dispatch_sha256") is not None
    ]
    assert len(dispatches) == 2
    assert len(set(dispatches)) == 1


def test_timeout_wire_v3_cannot_omit_attempt_binding(current_transport_attempt):
    ctx, _state, _workflow, _attempt_id, _basis_ref = current_transport_attempt

    v2 = serialize_timeout_context(ctx, expected_run_id=ctx.run.run_manifest.run_id)
    assert v2["schema"] == _TIMEOUT_CONTEXT_WIRE_SCHEMA
    assert "engine_invocation" not in v2
    with pytest.raises(ValueError, match="timeout_worker_engine_invocation_required"):
        _build_timeout_worker_context(
            v2,
            expected_component_id=_COMPONENT_ID,
            expected_alias=_ALIAS,
            expected_params=_PARAMS,
            state=_state,
        )

    malformed = {
        **v2,
        "schema": "polisyos.scientist.timeout_context.v3",
        "engine_invocation": None,
    }
    with pytest.raises(ValueError, match="timeout_worker_engine_invocation"):
        _build_timeout_worker_context(malformed)


def _context_with_transport_parameters(ctx, state, parameters):
    """Persist a real owner workflow and current attempt for typed parameter probes."""
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert attempts
    workflow = WorkflowSpec(
        workflow_id="transport_parameter_identity",
        nodes=[
            NodeInvocation(
                alias=_ALIAS,
                node_id=_COMPONENT_ID,
                params=parameters,
                timeout_s=120.0,
            )
        ],
    )
    workflow_ref = ctx.store.put_json(
        workflow.model_dump(mode="json"),
        PutOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    attempt_id = str(uuid4())
    basis_ref = ctx.run._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias=_ALIAS,
        component_id=_COMPONENT_ID,
        input_state_ref=attempts[0].basis.input_state_ref,
    )
    return replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=state.run_id,
            attempt_id=attempt_id,
            basis_ref=basis_ref,
        ),
    )


def test_spawn_parameter_identity_is_canonical_and_recursive(current_transport_attempt):
    ctx, state, _workflow, _attempt_id, _basis_ref = current_transport_attempt
    owner_params = {
        "profile_id": "controlled-test-v1",
        "selection_identity": "fixture-choice",
        "optional_value": None,
        "controls": {
            "enabled": True,
            "max_samples": 1,
            "ratio": 1.0,
            "children": [
                {"kind": "bounded", "count": 2},
                {"kind": "optional", "count": 0},
            ],
        },
    }
    bound_ctx = _context_with_transport_parameters(ctx, state, owner_params)
    reordered = {
        "controls": {
            "children": [
                {"count": 2, "kind": "bounded"},
                {"count": 0, "kind": "optional"},
            ],
            "ratio": 1.0,
            "max_samples": 1,
            "enabled": True,
        },
        "selection_identity": "fixture-choice",
        "profile_id": "controlled-test-v1",
        "optional_value": None,
    }
    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        bound_ctx,
        state,
        alias=_ALIAS,
        dispatch_params=reordered,
        timeout_s=30.0,
        supervisor_deadline_monotonic=time.monotonic() + 30.0,
    )
    _build_timeout_worker_context(
        task.context_meta,
        invocation_id=task.worker_invocation_id,
        dispatch_sha256=task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=reordered,
        expected_supervisor_deadline_monotonic=_task_supervisor_deadline(task),
        state=state,
    )

    bool_as_int = deepcopy(owner_params)
    bool_as_int["controls"]["enabled"] = 1
    int_as_float = deepcopy(owner_params)
    int_as_float["controls"]["max_samples"] = 1.0
    nested_bool_as_int = deepcopy(owner_params)
    nested_bool_as_int["controls"]["children"][0]["count"] = True
    reordered_sequence = deepcopy(owner_params)
    reordered_sequence["controls"]["children"].reverse()
    bad_variants = [bool_as_int, int_as_float, nested_bool_as_int, reordered_sequence]

    for bad_params in bad_variants:
        with pytest.raises(
            ValueError,
            match="timeout_worker_engine_workflow_node_mismatch",
        ):
            _build_spawn_timeout_task(
                RunTransportabilityNode(),
                bound_ctx,
                state,
                alias=_ALIAS,
                dispatch_params=bad_params,
                timeout_s=30.0,
                supervisor_deadline_monotonic=time.monotonic() + 30.0,
            )
        with pytest.raises(
            ValueError,
            match="timeout_worker_engine_workflow_node_mismatch",
        ):
            _build_timeout_worker_context(
                task.context_meta,
                invocation_id=task.worker_invocation_id,
                dispatch_sha256=task.worker_dispatch_sha256,
                expected_component_id=_COMPONENT_ID,
                expected_alias=_ALIAS,
                expected_params=bad_params,
                expected_supervisor_deadline_monotonic=_task_supervisor_deadline(task),
                state=state,
            )
        bad_digest = worker_dispatch_sha256(
            node_id=task.node_id,
            alias=task.alias,
            params=bad_params,
            state_bytes=task.state_bytes,
            trace_carrier=task.trace_carrier,
            timeout_s=task.timeout_s,
            max_retries=0,
            context_meta=task.context_meta,
        )
        assert bad_digest != task.worker_dispatch_sha256

    unsupported = deepcopy(owner_params)
    unsupported["controls"]["children"][0]["new_value"] = object()
    with pytest.raises(
        ValueError,
        match="timeout_worker_engine_workflow_node_mismatch",
    ):
        _build_spawn_timeout_task(
            RunTransportabilityNode(),
            bound_ctx,
            state,
            alias=_ALIAS,
            dispatch_params=unsupported,
            timeout_s=30.0,
            supervisor_deadline_monotonic=time.monotonic() + 30.0,
        )


def test_spawn_parameter_identity_does_not_alias_core_tag_mapping(
    current_transport_attempt,
):
    ctx, state, _workflow, _attempt_id, _basis_ref = current_transport_attempt
    tag_mapping = {"_type": "float", "repr": "1"}
    nested_tag_mapping = {"payload": {"nested": tag_mapping}}

    assert _timeout_worker_params_match(nested_tag_mapping, nested_tag_mapping)
    assert not _timeout_worker_params_match(
        {"payload": {"nested": 1.0}},
        nested_tag_mapping,
    )
    assert not _timeout_worker_params_match(
        nested_tag_mapping,
        {"payload": {"nested": 1.0}},
    )
    assert not _timeout_worker_params_match({"payload": 0.0}, {"payload": -0.0})

    # Core decodes the nested reserved tag as float 1.0. NodeInvocation keeps
    # that nested Any value as float, so bind the decoded owner value; a literal
    # mapping dispatch must not alias it at capture or worker revalidation.
    bound_ctx = _context_with_transport_parameters(
        ctx,
        state,
        nested_tag_mapping,
    )
    owner_params = {"payload": {"nested": 1.0}}
    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        bound_ctx,
        state,
        alias=_ALIAS,
        dispatch_params=owner_params,
        timeout_s=30.0,
        supervisor_deadline_monotonic=time.monotonic() + 30.0,
    )
    _build_timeout_worker_context(
        task.context_meta,
        invocation_id=task.worker_invocation_id,
        dispatch_sha256=task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=owner_params,
        expected_supervisor_deadline_monotonic=_task_supervisor_deadline(task),
        state=state,
    )
    with pytest.raises(ValueError, match="timeout_worker_engine_workflow_node_mismatch"):
        _build_spawn_timeout_task(
            RunTransportabilityNode(),
            bound_ctx,
            state,
            alias=_ALIAS,
            dispatch_params=nested_tag_mapping,
            timeout_s=30.0,
            supervisor_deadline_monotonic=time.monotonic() + 30.0,
        )
    with pytest.raises(ValueError, match="timeout_worker_engine_workflow_node_mismatch"):
        _build_timeout_worker_context(
            task.context_meta,
            invocation_id=task.worker_invocation_id,
            dispatch_sha256=task.worker_dispatch_sha256,
            expected_component_id=_COMPONENT_ID,
            expected_alias=_ALIAS,
            expected_params=nested_tag_mapping,
            expected_supervisor_deadline_monotonic=_task_supervisor_deadline(task),
            state=state,
        )


def test_timeout_invocation_accepts_exact_engine_journaled_state(
    current_transport_attempt,
):
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        capture_timeout_worker_engine_invocation,
    )
    from polisyos.scientist.orchestration.engine.state_branching import (
        _owned_wire_model_origin,
        branch_state,
    )

    ctx, state, _workflow, attempt_id, basis_ref = current_transport_attempt
    journaled = branch_state(state).state
    assert type(journaled) is not ExperimentState
    assert _owned_wire_model_origin(journaled) is ExperimentState

    invocation = capture_timeout_worker_engine_invocation(
        ctx,
        expected_run_id=state.run_id,
        node_alias=_ALIAS,
        component_id=_COMPONENT_ID,
        dispatch_params=_PARAMS,
        timeout_s=30.0,
        supervisor_deadline_monotonic=time.monotonic() + 30.0,
        state=journaled,
    )

    assert invocation.attempt_id == attempt_id
    assert invocation.basis_ref == basis_ref
    attempt = ctx.run.read_runtime_invocation_attempts()[0]
    assert attempt.basis.attempt_id == attempt_id
    assert invocation.input_state_ref == attempt.basis.input_state_ref


def test_timeout_invocation_rejects_caller_subclass_and_changed_engine_state(
    current_transport_attempt,
):
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        capture_timeout_worker_engine_invocation,
    )
    from polisyos.scientist.orchestration.engine.state_branching import branch_state

    ctx, state, _workflow, _attempt_id, _basis_ref = current_transport_attempt

    class CallerExperimentState(ExperimentState):
        pass

    counterfeit = CallerExperimentState.model_validate(
        state.model_dump(mode="python", by_alias=True, exclude_none=False)
    )
    with pytest.raises(
        ValueError,
        match="timeout_worker_engine_invocation_run_mismatch",
    ):
        capture_timeout_worker_engine_invocation(
            ctx,
            expected_run_id=state.run_id,
            node_alias=_ALIAS,
            component_id=_COMPONENT_ID,
            dispatch_params=_PARAMS,
            timeout_s=30.0,
            supervisor_deadline_monotonic=time.monotonic() + 30.0,
            state=counterfeit,
        )

    changed = branch_state(state).state
    changed.params["forged"] = "same-run-but-not-the-persisted-input"
    with pytest.raises(
        ValueError,
        match="timeout_worker_engine_input_state_mismatch",
    ):
        capture_timeout_worker_engine_invocation(
            ctx,
            expected_run_id=state.run_id,
            node_alias=_ALIAS,
            component_id=_COMPONENT_ID,
            dispatch_params=_PARAMS,
            timeout_s=30.0,
            supervisor_deadline_monotonic=time.monotonic() + 30.0,
            state=changed,
        )


def test_timeout_invocation_rejects_current_attempt_with_wrong_basis_ref(
    current_transport_attempt,
):
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        capture_timeout_worker_engine_invocation,
    )

    ctx, state, _workflow, attempt_id, basis_ref = current_transport_attempt
    wrong_basis_ref = basis_ref.model_copy(update={"artifact_id": "sha256:" + "f" * 64})
    wrong_ref_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=ctx.run.run_manifest.run_id,
            attempt_id=attempt_id,
            basis_ref=wrong_basis_ref,
        ),
    )

    with pytest.raises(
        ValueError,
        match="timeout_worker_engine_attempt_not_current",
    ):
        capture_timeout_worker_engine_invocation(
            wrong_ref_ctx,
            expected_run_id=state.run_id,
            node_alias=_ALIAS,
            component_id=_COMPONENT_ID,
            dispatch_params=_PARAMS,
            timeout_s=30.0,
            supervisor_deadline_monotonic=time.monotonic() + 30.0,
            state=state,
        )


def test_spawned_worker_context_accepts_reordered_state_but_rejects_typed_change(
    current_transport_attempt,
):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        _loads,
        _timeout_worker_states_match,
        _timeout_worker_wire_values_match,
        serialize_state,
    )

    ctx, state, _workflow, attempt_id, basis_ref = current_transport_attempt
    reordered = state.model_copy(deep=True)
    reordered.params = {
        "values": [1.0, 0.0],
        "nested": {"enabled": True, "count": 1},
    }

    basis_state = ExperimentState.model_validate(
        from_canonical_bytes(
            ctx.store.get_bytes(ctx.run.read_runtime_invocation_attempts()[0].basis.input_state_ref)
        )
    )
    assert basis_state.params == reordered.params
    assert serialize_state(basis_state) != serialize_state(reordered)
    assert _timeout_worker_wire_values_match(
        _loads(serialize_state(basis_state)),
        _loads(serialize_state(reordered)),
    )
    assert _timeout_worker_states_match(basis_state, reordered)

    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        ctx,
        reordered,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
        timeout_s=90.0,
        supervisor_deadline_monotonic=time.monotonic() + 120.0,
    )
    assert task.context_meta["engine_invocation"]["attempt_id"] == attempt_id
    assert task.context_meta["engine_invocation"]["basis_ref"] == basis_ref.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=False,
    )

    worker_args = {
        "invocation_id": task.worker_invocation_id,
        "dispatch_sha256": task.worker_dispatch_sha256,
        "expected_component_id": _COMPONENT_ID,
        "expected_alias": _ALIAS,
        "expected_params": _PARAMS,
        "expected_supervisor_deadline_monotonic": _task_supervisor_deadline(task),
    }
    worker = _build_timeout_worker_context(
        task.context_meta,
        **worker_args,
        state=reordered,
    )
    assert worker._engine_invocation.attempt_id == attempt_id
    assert worker._engine_invocation.basis_ref == basis_ref

    typed_change = reordered.model_copy(deep=True)
    typed_change.params["nested"]["count"] = True
    assert not _timeout_worker_states_match(basis_state, typed_change)
    with pytest.raises(
        ValueError,
        match="timeout_worker_engine_input_state_mismatch",
    ):
        _build_timeout_worker_context(
            task.context_meta,
            **worker_args,
            state=typed_change,
        )


def test_timeout_state_wire_identity_ignores_key_order_but_preserves_json_types():
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        _timeout_worker_wire_values_match,
    )

    left = {"nested": {"count": 1, "enabled": True}, "values": [1.0, 0.0]}
    reordered = {"values": [1.0, 0.0], "nested": {"enabled": True, "count": 1}}

    assert _timeout_worker_wire_values_match(left, reordered)
    assert not _timeout_worker_wire_values_match({"value": 1}, {"value": True})
    assert not _timeout_worker_wire_values_match({"value": 1}, {"value": 1.0})
    assert not _timeout_worker_wire_values_match({"value": -0.0}, {"value": 0.0})


def test_ir_reference_wire_uses_strict_shared_selector_projection():
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.ir.registry.refs import CausalCapabilityContractRef
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        _decode_wire_value,
        _encode_wire_value,
        _wire_ir_artifact_ref_types,
        deserialize_state,
        serialize_state,
    )

    profile = "sha256:" + "b" * 64
    ref = CausalCapabilityContractRef(
        artifact_id="sha256:" + "a" * 64,
        manifest_profile_sha256=profile,
    )
    assert type(ref) in _wire_ir_artifact_ref_types()

    state = ExperimentState(run_id="typed-ir-ref-wire")
    state.causal_capability_contract_ref = ref
    state.artifacts_index["causal_capability_contract_ref"] = ref
    payload = serialize_state(state)
    decoded = deserialize_state(payload)
    assert type(decoded.causal_capability_contract_ref) is ArtifactRef
    assert decoded.causal_capability_contract_ref.kind == "ir.causal_capability_contract"
    assert decoded.causal_capability_contract_ref.manifest_profile_sha256 == profile
    assert decoded.artifacts_index["causal_capability_contract_ref"].kind == (
        "ir.causal_capability_contract"
    )
    assert (
        decoded.artifacts_index["causal_capability_contract_ref"].manifest_profile_sha256 == profile
    )

    direct = _decode_wire_value(_encode_wire_value(ref))
    assert type(direct) is ArtifactRef
    assert direct.kind == ref.kind
    assert direct.manifest_profile_sha256 == profile

    class UnregisteredCapabilityRef(CausalCapabilityContractRef):
        pass

    counterfeit = UnregisteredCapabilityRef(
        artifact_id="sha256:" + "a" * 64,
        manifest_profile_sha256=profile,
    )
    with pytest.raises(TypeError, match="Unsupported model on runner wire"):
        _encode_wire_value(counterfeit)


def test_run_transportability_component_identity_is_exact_and_param_bound(monkeypatch):
    from polisyos.scientist.orchestration.engine.component_identity import (
        capture_engine_component_identity,
        matches_engine_component_identity,
    )

    node = RunTransportabilityNode()
    identity = capture_engine_component_identity(node, _COMPONENT_ID, _PARAMS)

    assert identity is not None
    assert identity.component_id == _COMPONENT_ID
    assert matches_engine_component_identity(identity, _COMPONENT_ID, _PARAMS)
    assert not matches_engine_component_identity(
        identity,
        _COMPONENT_ID,
        {**_PARAMS, "profile_id": "different-profile"},
    )
    assert (
        capture_engine_component_identity(
            node,
            "scientist.node_fake@1.0.0",
            _PARAMS,
        )
        is None
    )

    class SameIdReplacement(RunTransportabilityNode):
        pass

    assert (
        capture_engine_component_identity(
            SameIdReplacement(),
            _COMPONENT_ID,
            _PARAMS,
        )
        is None
    )

    execute = RunTransportabilityNode.execute
    monkeypatch.setattr(
        execute,
        "__code__",
        (lambda self, _ctx, _state: None).__code__,
    )
    assert capture_engine_component_identity(node, _COMPONENT_ID, _PARAMS) is None


def test_spawned_worker_identity_recomputes_stable_parent_attempt_and_live_deadline(
    current_transport_attempt,
    monkeypatch,
):
    from polisyos.scientist.orchestration.engine.component_identity import (
        matches_spawned_timeout_worker_component_identity,
    )

    ctx, state, _workflow, _attempt_id, _basis_ref = current_transport_attempt
    deadline = time.monotonic() + 180.0
    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        ctx,
        state,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
        timeout_s=120.0,
        supervisor_deadline_monotonic=deadline,
    )
    worker = _build_timeout_worker_context(
        task.context_meta,
        invocation_id=task.worker_invocation_id,
        dispatch_sha256=task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=_PARAMS,
        expected_supervisor_deadline_monotonic=deadline,
        state=state,
    )
    identity = worker.run.read_runtime_invocation_attempts()[0].basis.implementation_identity
    assert identity is not None
    assert worker._engine_invocation.effective_timeout_s == 120.0
    assert worker._engine_invocation.supervisor_deadline_monotonic == deadline

    # These parent-process tokens are intentionally stale in the spawned child.
    import polisyos.scientist.orchestration.engine.component_identity as component_identity

    monkeypatch.setattr(component_identity, "_PROCESS_ID", identity.runtime_process_id + 1)
    monkeypatch.setattr(component_identity, "_PROCESS_NONCE", "f" * 32)
    assert matches_spawned_timeout_worker_component_identity(
        worker,
        identity,
        _COMPONENT_ID,
        _ALIAS,
        _PARAMS,
    )

    forged = identity.model_copy(update={"execute_code_sha256": "0" * 64})
    assert not matches_spawned_timeout_worker_component_identity(
        worker,
        forged,
        _COMPONENT_ID,
        _ALIAS,
        _PARAMS,
    )
    assert not matches_spawned_timeout_worker_component_identity(
        worker,
        identity,
        _COMPONENT_ID,
        _ALIAS,
        {**_PARAMS, "profile_id": "forged"},
    )

    short_deadline = time.monotonic() + 75.0
    short_task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        ctx,
        state,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
        timeout_s=120.0,
        supervisor_deadline_monotonic=short_deadline,
    )
    short_worker = _build_timeout_worker_context(
        short_task.context_meta,
        invocation_id=short_task.worker_invocation_id,
        dispatch_sha256=short_task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=_PARAMS,
        expected_supervisor_deadline_monotonic=short_deadline,
        state=state,
    )
    short_identity = short_worker.run.read_runtime_invocation_attempts()[
        0
    ].basis.implementation_identity
    assert short_identity is not None
    assert matches_spawned_timeout_worker_component_identity(
        short_worker,
        short_identity,
        _COMPONENT_ID,
        _ALIAS,
        _PARAMS,
    )

    tampered = dict(task.context_meta)
    tampered["engine_invocation"] = dict(task.context_meta["engine_invocation"])
    tampered["engine_invocation"]["supervisor_deadline_monotonic_hex"] = (
        time.monotonic() + 121.0
    ).hex()
    with pytest.raises(
        ValueError,
        match="timeout_worker_engine_supervisor_deadline_mismatch",
    ):
        _build_timeout_worker_context(
            tampered,
            invocation_id=task.worker_invocation_id,
            dispatch_sha256=task.worker_dispatch_sha256,
            expected_component_id=_COMPONENT_ID,
            expected_alias=_ALIAS,
            expected_params=_PARAMS,
            expected_supervisor_deadline_monotonic=deadline,
            state=state,
        )


def test_spawned_worker_identity_recomputes_parent_attempt_and_deadline(
    monkeypatch, current_transport_attempt
):
    from polisyos.scientist.orchestration.engine import component_identity
    from polisyos.scientist.orchestration.engine.retry import (
        _AttemptAuthority,
        _build_attempt_context,
        _node_facing_context,
    )
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        _TIMEOUT_CONTEXT_ENGINE_INVOCATION_NODE_ID,
    )

    ctx, state, _workflow, attempt_id, basis_ref = current_transport_attempt
    deadline = time.monotonic() + 100.0
    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        ctx,
        state,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
        timeout_s=100.0,
        supervisor_deadline_monotonic=deadline,
    )
    worker = _build_timeout_worker_context(
        task.context_meta,
        invocation_id=task.worker_invocation_id,
        dispatch_sha256=task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=_PARAMS,
        expected_supervisor_deadline_monotonic=deadline,
        state=state,
    )
    node_ctx = _node_facing_context(_build_attempt_context(worker, _AttemptAuthority(deadline)))
    attempt = worker.run.read_runtime_invocation_attempts()[0]
    identity = attempt.basis.implementation_identity
    assert identity is not None
    assert attempt.basis.attempt_id == attempt_id
    assert attempt.basis_ref == basis_ref
    assert worker.run.dispatch_binding is not None

    # A fresh spawned child has a different PID and process nonce. Stable owner
    # code/spec/params are recomputed; the parent's persisted identity stays exact.
    monkeypatch.setattr(component_identity, "_PROCESS_ID", identity.runtime_process_id + 1)
    monkeypatch.setattr(component_identity, "_PROCESS_NONCE", "a" * 32)
    check = component_identity.matches_spawned_timeout_worker_component_identity
    assert check(node_ctx, identity, _COMPONENT_ID, _ALIAS, _PARAMS)

    forged_identity = identity.model_copy(
        update={"runtime_process_id": identity.runtime_process_id + 1}
    )
    assert not check(node_ctx, forged_identity, _COMPONENT_ID, _ALIAS, _PARAMS)
    assert not check(node_ctx, identity, _COMPONENT_ID, _ALIAS, {**_PARAMS, "extra": "forged"})
    assert not check(node_ctx, identity, "scientist.node_fake@1.0.0", _ALIAS, _PARAMS)

    wrong_attempt_ctx = replace(
        node_ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=state.run_id,
            attempt_id=str(uuid4()),
            basis_ref=basis_ref,
            effective_timeout_s=100.0,
            supervisor_deadline_monotonic=deadline,
        ),
    )
    assert not check(wrong_attempt_ctx, identity, _COMPONENT_ID, _ALIAS, _PARAMS)

    short_timeout_ctx = replace(
        node_ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=state.run_id,
            attempt_id=attempt_id,
            basis_ref=basis_ref,
            effective_timeout_s=75.0,
            supervisor_deadline_monotonic=deadline,
        ),
    )
    # Custody identity is valid independently of work-budget admission. The
    # candidate node enforces the live phase budget before starting solver work.
    assert check(short_timeout_ctx, identity, _COMPONENT_ID, _ALIAS, _PARAMS)

    with pytest.raises(ValueError, match="timeout_worker_engine_supervisor_deadline_mismatch"):
        _build_timeout_worker_context(
            task.context_meta,
            invocation_id=task.worker_invocation_id,
            dispatch_sha256=task.worker_dispatch_sha256,
            expected_component_id=_COMPONENT_ID,
            expected_alias=_ALIAS,
            expected_params=_PARAMS,
            expected_supervisor_deadline_monotonic=deadline + 1.0,
            state=state,
        )

    changed_meta = deepcopy(task.context_meta)
    changed_meta["engine_invocation"]["supervisor_deadline_monotonic_hex"] = (deadline + 1.0).hex()
    changed_digest = worker_dispatch_sha256(
        node_id=task.node_id,
        alias=task.alias,
        params=task.params,
        state_bytes=task.state_bytes,
        trace_carrier=task.trace_carrier,
        timeout_s=task.timeout_s,
        max_retries=0,
        context_meta=changed_meta,
    )
    assert changed_digest != task.worker_dispatch_sha256
    with pytest.raises(ValueError, match="timeout_worker_engine_supervisor_deadline_mismatch"):
        _build_timeout_worker_context(
            changed_meta,
            invocation_id=task.worker_invocation_id,
            dispatch_sha256=changed_digest,
            expected_component_id=_COMPONENT_ID,
            expected_alias=_ALIAS,
            expected_params=_PARAMS,
            expected_supervisor_deadline_monotonic=deadline,
            state=state,
        )

    monkeypatch.setattr(
        component_identity,
        "_module_source_digest",
        lambda _node_type: "f" * 64,
    )
    assert not check(node_ctx, identity, _COMPONENT_ID, _ALIAS, _PARAMS)
    assert _TIMEOUT_CONTEXT_ENGINE_INVOCATION_NODE_ID == _COMPONENT_ID


def test_spawned_worker_identity_accepts_bounded_exact_nested_facades_and_rejects_cycles(
    current_transport_attempt,
):
    from polisyos.scientist.orchestration.engine import component_identity
    from polisyos.scientist.orchestration.engine.retry import (
        _AttemptAuthority,
        _AttemptRunFacade,
        _build_attempt_context,
        _node_facing_context,
    )

    ctx, state, _workflow, _attempt_id, _basis_ref = current_transport_attempt
    deadline = time.monotonic() + 180.0
    task = _build_spawn_timeout_task(
        RunTransportabilityNode(),
        ctx,
        state,
        alias=_ALIAS,
        dispatch_params=_PARAMS,
        timeout_s=120.0,
        supervisor_deadline_monotonic=deadline,
    )
    worker = _build_timeout_worker_context(
        task.context_meta,
        invocation_id=task.worker_invocation_id,
        dispatch_sha256=task.worker_dispatch_sha256,
        expected_component_id=_COMPONENT_ID,
        expected_alias=_ALIAS,
        expected_params=_PARAMS,
        expected_supervisor_deadline_monotonic=deadline,
        state=state,
    )
    identity = worker.run.read_runtime_invocation_attempts()[0].basis.implementation_identity
    assert identity is not None
    check = component_identity.matches_spawned_timeout_worker_component_identity

    for depth in (1, 2, 5):
        layered_context = worker
        for _ in range(depth):
            layered_context = _build_attempt_context(
                layered_context,
                _AttemptAuthority(deadline),
            )
        assert check(
            _node_facing_context(layered_context),
            identity,
            _COMPONENT_ID,
            _ALIAS,
            _PARAMS,
        )

    too_deep_context = worker
    for _ in range(9):
        too_deep_context = _build_attempt_context(
            too_deep_context,
            _AttemptAuthority(deadline),
        )
    assert not check(
        _node_facing_context(too_deep_context),
        identity,
        _COMPONENT_ID,
        _ALIAS,
        _PARAMS,
    )

    class SiblingAttemptRunFacade(_AttemptRunFacade):
        pass

    sibling_facade = SiblingAttemptRunFacade(worker.run, _AttemptAuthority(deadline), worker.store)
    sibling_context = replace(worker, run=sibling_facade)
    assert not check(
        _node_facing_context(sibling_context),
        identity,
        _COMPONENT_ID,
        _ALIAS,
        _PARAMS,
    )

    cyclic_context = _build_attempt_context(worker, _AttemptAuthority(deadline))
    cyclic_facade = cyclic_context.run
    object.__setattr__(cyclic_facade, "_target", cyclic_facade)
    assert not check(
        _node_facing_context(cyclic_context),
        identity,
        _COMPONENT_ID,
        _ALIAS,
        _PARAMS,
    )
