"""Physical Engine input ports retain hidden state only at the owning merge."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine import component_identity, input_ports
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _load_engine_owned_invocation_input_state,
)
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.input_ports import NodeInputBasis, NodeInputPortError
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeInputContract,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_COMPONENT = "scientist.node_restricted_input_probe@1.0.0"
_SEEN: list[dict[str, object]] = []
_MODE = "ok"
_VALIDATED_CACHE: list[dict[str, object]] = []
_SPEC = InputAwareNodeSpec(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse(_COMPONENT),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Restricted input probe",
        description="Synthetic selected implementation for actual Engine boundary tests.",
        capabilities=Capability.SCIENTIST_NODE,
    ),
    # Deliberately narrower metadata: the port, not this hint, must bind visible.
    state_reads=["run_id"],
    state_writes=["params.result"],
    input_contract=NodeInputContract(
        contract_id="test.selected_input.v1",
        component_id=_COMPONENT,
        state_paths=("schema_version", "run_id", "execution_profile", "params.visible"),
    ),
)


def _observe(state: ExperimentState) -> None:
    assert set(state.params) == ({"visible", "metadata"} if _MODE == "refs" else {"visible"})
    assert set(state.inputs) == ({"selected"} if _MODE == "refs" else set())
    assert state.artifacts_index == state.reports_index == {}
    assert state.verified_policy_report_ref is None
    _SEEN.append(state.model_dump(mode="python"))


@dataclass(frozen=True, kw_only=True)
class _CallerContext(ExecutionContext):
    undeclared_capability: object


class _Probe:
    @property
    def spec(self) -> InputAwareNodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        _observe(state)
        assert not hasattr(ctx, "undeclared_capability")
        assert all(
            getattr(ctx, field) is None
            for field in (
                "fabric",
                "foundry",
                "scholar",
                "lex",
                "memory",
                "prepared_skg_read",
                "audit",
                "metrics",
                "tracer",
            )
        )
        for field in ("run_manifest", "trace_path", "access_scope"):
            with pytest.raises(AttributeError):
                getattr(ctx.run, field)
        for method in (
            "read_runtime_invocation_attempts",
            "read_runtime_owner_output_refs",
            "read_runtime_workflow_finalization_ref",
        ):
            with pytest.raises(AttributeError):
                getattr(ctx.run, method)()
        consumed = _load_engine_owned_invocation_input_state(ctx, state)
        assert consumed is not None and consumed.params == state.params
        selected = input_ports.read_input_port_basis(ctx, state)
        manifest = ctx.store.get_manifest(selected.input_state_ref)
        hidden_basis = next(edge for edge in manifest.inputs if edge.role == "node_input_basis")
        from polisyos.core.artifacts import ArtifactRef

        hidden_ref = ArtifactRef(
            artifact_id=hidden_basis.artifact_id,
            kind="scientist.node_input_basis",
            media_type="application/json",
            manifest_profile_sha256=hidden_basis.manifest_profile_sha256,
        )
        with pytest.raises(NodeInputPortError, match="scoped_attempt_mismatch"):
            input_ports.read_input_port_basis(
                replace(ctx, _node_input_selection=replace(selected, attempt_id="foreign-attempt")),
                state,
            )
        changed_input = ExperimentState.model_validate(state.model_dump(mode="python"))
        changed_input.params["visible"] = "changed-after-persistence"
        with pytest.raises(NodeInputPortError, match="port_state_changed"):
            input_ports.read_input_port_basis(ctx, changed_input)
        if _MODE == "refs":
            selected_artifact = state.inputs["selected"]
            assert ctx.store.get_bytes(selected_artifact) == b'{"selected":true}'
            foreign = ArtifactRef.model_validate(state.params["metadata"]["foreign"])
            with pytest.raises(NodeInputPortError, match="read_not_selected"):
                ctx.store.get_bytes(foreign)
            hidden = ArtifactRef.model_validate(state.params["metadata"]["buried"])
            with pytest.raises(NodeInputPortError, match="read_not_selected"):
                ctx.store.get_bytes(hidden)
        expected_ids = {str(selected.input_state_ref.artifact_id)}
        if _MODE == "refs":
            expected_ids.add(str(state.inputs["selected"].artifact_id))
        for node_store in (ctx.store, ctx.run.store):
            assert {str(aid) for aid in node_store.iter_artifact_ids()} == expected_ids
            with pytest.raises(NodeInputPortError, match="read_not_selected"):
                node_store.get_bytes(hidden_ref)
            with pytest.raises(AttributeError):
                _ = node_store.root
        state.params["result"] = f"seen:{state.params['visible']}"
        if _MODE == "retry" and len(_SEEN) == 1:
            return NodeOutcome(
                status="fail", state=state, error=NodeError(code="test.retry", message="retry")
            )
        if _MODE == "outside":
            return NodeOutcome(
                status="ok", state=ExperimentState(run_id=state.run_id, params={"smuggled": True})
            )
        return NodeOutcome(status="ok", state=state)

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if _MODE == "timeout":
            _observe(state)
            await asyncio.sleep(2)
        return self.execute(ctx, state)

    def validate_cache_hit(self, ctx, state, cached_outcome):
        assert ctx._engine_invocation is None
        assert ctx.prepared_skg_read is None
        assert not hasattr(ctx, "undeclared_capability")
        del cached_outcome
        assert set(state.params) == {"visible"}
        assert state.reports_index == {}
        _VALIDATED_CACHE.append(state.model_dump())
        return True


class _ChangeVisible:
    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=_SPEC.metadata.model_copy(
                update={"component_id": ComponentId.parse("scientist.node_change_visible@1.0.0")}
            ),
            state_writes=["params.visible"],
        )

    def execute(self, ctx, state):
        del ctx
        state.params["visible"] = "second"
        return NodeOutcome(status="ok", state=state)


@pytest.fixture(autouse=True)
def _selected_test_owner(monkeypatch):
    _SEEN.clear()
    _VALIDATED_CACHE.clear()
    monkeypatch.setattr(__import__(__name__, fromlist=["_MODE"]), "_MODE", "ok")
    # Explicit test-only bootstrap; production accepts only its held builtin owners.
    monkeypatch.setitem(component_identity._OWNERS, _COMPONENT, component_identity._owner(_Probe))


def _context(tmp_path: Path):
    # Test behavior globals are selected before this explicit test-only bootstrap.
    component_identity._OWNERS[_COMPONENT] = component_identity._owner(_Probe)
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(
        store=store, return_selected_profile=True
    ).bundle_ref
    run_id = "port-" + uuid4().hex
    run = RunContext.start(store, registry_ref, run_id=run_id)
    ctx = _CallerContext(
        undeclared_capability={"secret": "unselected subclass capability"},
        store=store,
        run=run,
        logger=logging.getLogger("test.input-port"),
        prepared_skg_read=SimpleNamespace(secret="unselected graph connection"),
        memory={"secret": "unselected memory"},
    )
    hidden = store.put_json(
        {"hidden": True},
        ArtifactWriteOptions(kind="test.hidden", media_type="application/json"),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id=run_id,
        execution_profile="port-test",
        params={"visible": "first", "secret": "unavailable", "archive": {"judge": "old"}},
        reports_index={"old_governance": hidden},
        artifacts_index={"old_internal": hidden},
        verified_policy_report_ref=hidden,
    )
    registry = NodeRegistry()
    registry.register(_Probe())
    registry.register(_ChangeVisible())
    return ctx, registry, state


def _run(ctx, registry, state, *, route, workflow=None):
    if workflow is None:
        workflow = WorkflowSpec(
            workflow_id="input_port", nodes=[NodeInvocation(alias="probe", node_id=_COMPONENT)]
        )
    if route == "sync":
        return WorkflowExecutor(ctx, registry).execute(workflow, state)
    return asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, state))


def _basis(ctx, attempt):
    manifest = ctx.store.get_manifest(attempt.basis.input_state_ref)
    edge = next(edge for edge in manifest.inputs if edge.role == "node_input_basis")
    from polisyos.core.artifacts import ArtifactRef

    ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind="scientist.node_input_basis",
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    return NodeInputBasis.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))


@pytest.mark.parametrize("route", ["sync", "async"])
def test_actual_engine_projects_input_binds_predecessor_and_preserves_hidden_state(tmp_path, route):
    ctx, registry, state = _context(tmp_path)
    before = state.model_dump()
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "ok"
    assert len(_SEEN) == 1
    assert result.state.params == {**before["params"], "result": "seen:first"}
    assert result.state.reports_index["old_governance"] == state.reports_index["old_governance"]
    assert result.state.artifacts_index["old_internal"] == state.artifacts_index["old_internal"]
    assert result.state.verified_policy_report_ref == state.verified_policy_report_ref
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert len(attempts) == 1 and attempts[0].outcome.status == "ok"
    bound = _basis(ctx, attempts[0])
    predecessor = ExperimentState.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(bound.predecessor_state_ref))
    )
    assert predecessor.model_dump() == before
    assert bound.attempt_id == attempts[0].basis.attempt_id
    assert bound.contract.contract_id == "test.selected_input.v1"
    assert bound.execution_kind == "producer"
    assert state.model_dump() == before


@pytest.mark.parametrize("route", ["sync", "async"])
def test_cache_replay_has_restricted_input_and_fresh_predecessor_binding(tmp_path, route):
    ctx, registry, state = _context(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="input_cache",
        nodes=[
            NodeInvocation(alias="one", node_id=_COMPONENT),
            NodeInvocation(alias="two", node_id=_COMPONENT, depends_on=["one"]),
        ],
    )
    result = _run(ctx, registry, state, route=route, workflow=workflow)
    assert result.report.status == "ok"
    assert len(_SEEN) == 1 and len(_VALIDATED_CACHE) == 1
    assert result.state.params["secret"] == "unavailable"
    assert result.state.params["archive"] == {"judge": "old"}
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert len(attempts) == 2
    first, replay = (_basis(ctx, attempt) for attempt in attempts)
    assert first.execution_kind == "producer"
    assert replay.execution_kind == "cache_replay" and replay.source_cache_entry_ref is not None
    assert replay.attempt_id != first.attempt_id
    assert replay.predecessor_state_ref != first.predecessor_state_ref


@pytest.mark.parametrize("route", ["sync", "async"])
def test_cache_identity_uses_physical_port_beyond_state_reads_hint(tmp_path, route):
    ctx, registry, state = _context(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="input_change",
        nodes=[
            NodeInvocation(alias="one", node_id=_COMPONENT),
            NodeInvocation(
                alias="change", node_id="scientist.node_change_visible@1.0.0", depends_on=["one"]
            ),
            NodeInvocation(alias="two", node_id=_COMPONENT, depends_on=["change"]),
        ],
    )
    result = _run(ctx, registry, state, route=route, workflow=workflow)
    assert result.report.status == "ok"
    assert [seen["params"]["visible"] for seen in _SEEN] == ["first", "second"]
    assert result.state.params["result"] == "seen:second"
    assert result.state.params["secret"] == "unavailable"


@pytest.mark.parametrize("route", ["sync", "async"])
def test_retry_reprojects_each_attempt_without_failed_writes_or_hidden_state(
    tmp_path, monkeypatch, route
):
    monkeypatch.setattr(__import__(__name__, fromlist=["_MODE"]), "_MODE", "retry")
    ctx, registry, state = _context(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="input_retry",
        nodes=[
            NodeInvocation(
                alias="probe",
                node_id=_COMPONENT,
                retry=RetryPolicy(max_retries=1, backoff_base_s=0.1, retry_on=["test.retry"]),
            )
        ],
    )
    result = _run(ctx, registry, state, route=route, workflow=workflow)
    assert result.report.status == "ok"
    assert len(_SEEN) == 2 and all(set(item["params"]) == {"visible"} for item in _SEEN)
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert [attempt.outcome.status for attempt in attempts] == ["fail", "ok"]
    assert [_basis(ctx, attempt).attempt_number for attempt in attempts] == [1, 2]


@pytest.mark.parametrize("route", ["sync", "async"])
def test_unappointed_or_changed_input_contract_refuses_before_node(tmp_path, monkeypatch, route):
    ctx, registry, state = _context(tmp_path)
    monkeypatch.delitem(component_identity._OWNERS, _COMPONENT)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert _SEEN == [] and "result" not in result.state.params


def test_input_port_projection_removal_exposes_hidden_state_in_real_engine(tmp_path, monkeypatch):
    ctx, registry, state = _context(tmp_path)
    monkeypatch.setattr(input_ports, "_project", lambda full, _contract: full)
    result = _run(ctx, registry, state, route="sync")
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.exception"
    assert _SEEN == []


def test_async_timeout_keeps_full_predecessor_and_never_publishes_partial_write(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(__import__(__name__, fromlist=["_MODE"]), "_MODE", "timeout")
    ctx, registry, state = _context(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="input_timeout",
        nodes=[NodeInvocation(alias="probe", node_id=_COMPONENT, timeout_s=1)],
    )
    result = _run(ctx, registry, state, route="async", workflow=workflow)
    assert result.report.status == "fail"
    assert len(_SEEN) == 1 and "result" not in result.state.params
    assert result.state.params["secret"] == "unavailable"
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert len(attempts) == 1 and attempts[0].outcome.status == "unknown"


@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize(
    "corruption", ["attempt", "contract", "source_profile", "missing_basis", "dependencies"]
)
def test_real_attempt_refuses_corrupt_input_basis_before_callback(
    tmp_path, monkeypatch, route, corruption
):
    ctx, registry, state = _context(tmp_path)
    put = ctx.store.put_json

    def corrupt(obj, opts, canon_spec=None, *, return_selected_profile=False):
        if opts.kind == "scientist.node_input_basis":
            if corruption == "attempt":
                obj = obj.model_copy(update={"attempt_id": "foreign-attempt"})
            elif corruption == "contract":
                obj = obj.model_copy(
                    update={
                        "contract": obj.contract.model_copy(update={"contract_id": "foreign.v1"})
                    }
                )
            elif corruption == "dependencies":
                obj = obj.model_copy(update={"implementation_dependencies_sha256": "0" * 64})
            elif corruption == "source_profile":
                ref = obj.predecessor_state_ref.model_copy(
                    update={"manifest_profile_sha256": "sha256:" + "f" * 64}
                )
                obj = obj.model_copy(update={"predecessor_state_ref": ref})
        elif opts.kind == "scientist.experiment_state" and corruption == "missing_basis":
            if any(edge.role == "node_input_basis" for edge in opts.inputs or []):
                opts = replace(opts, inputs=[])
        return put(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )

    monkeypatch.setattr(ctx.store, "put_json", corrupt)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail" and _SEEN == []
    assert result.state.params["secret"] == "unavailable"
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert len(attempts) == 1 and attempts[0].outcome.status == "unknown"


@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize("method", ["execute", "execute_async", "validate_cache_hit"])
def test_changed_selected_callable_refuses_before_any_callback(
    tmp_path, monkeypatch, route, method
):
    ctx, registry, state = _context(tmp_path)
    monkeypatch.setattr(_Probe, method, lambda *_args: None)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert _SEEN == []


@pytest.mark.parametrize("route", ["sync", "async"])
def test_unknown_input_version_cannot_fall_back_to_full_state(tmp_path, monkeypatch, route):
    ctx, registry, state = _context(tmp_path)
    invalid = _SPEC.model_copy(
        update={"input_contract": _SPEC.input_contract.model_copy(update={"schema_version": "2.0"})}
    )
    monkeypatch.setattr(__import__(__name__, fromlist=["_SPEC"]), "_SPEC", invalid)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert _SEEN == []


@pytest.mark.parametrize("route", ["sync", "async"])
def test_ref_roles_pin_selected_profile_and_do_not_enroll_inline_metadata(
    tmp_path, monkeypatch, route
):
    monkeypatch.setattr(__import__(__name__, fromlist=["_MODE"]), "_MODE", "refs")
    contract = _SPEC.input_contract.model_copy(
        update={
            "state_paths": (
                *_SPEC.input_contract.state_paths,
                "inputs.selected",
                "params.metadata",
            ),
            "artifact_ref_paths": ("inputs.selected",),
        }
    )
    monkeypatch.setattr(
        __import__(__name__, fromlist=["_SPEC"]),
        "_SPEC",
        _SPEC.model_copy(update={"input_contract": contract}),
    )
    monkeypatch.setitem(component_identity._OWNERS, _COMPONENT, component_identity._owner(_Probe))
    ctx, registry, state = _context(tmp_path)
    selected = ctx.store.put_json(
        {"selected": True},
        ArtifactWriteOptions(
            kind="test.selected",
            media_type="application/json",
            schema=SchemaInfo(name="test.selected", version="1"),
        ),
        return_selected_profile=True,
    )
    foreign = ctx.store.put_json(
        {"selected": True},
        ArtifactWriteOptions(
            kind="test.selected",
            media_type="application/json",
            schema=SchemaInfo(name="test.selected", version="2"),
        ),
        return_selected_profile=True,
    )
    assert selected.artifact_id == foreign.artifact_id and selected != foreign
    state.inputs["selected"] = selected
    state.params["metadata"] = {
        "foreign": foreign.model_dump(mode="json"),
        "buried": state.verified_policy_report_ref.model_dump(mode="json"),
    }
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "ok" and len(_SEEN) == 1
    assert result.state.params["secret"] == "unavailable"


def test_sync_timed_worker_refuses_unsupported_port_without_exposing_input(tmp_path):
    ctx, registry, state = _context(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="input_worker",
        nodes=[NodeInvocation(alias="probe", node_id=_COMPONENT, timeout_s=5)],
    )
    result = _run(ctx, registry, state, route="sync", workflow=workflow)
    assert result.report.status == "fail" and _SEEN == []
    assert result.report.nodes[0].error.code == "node.timeout_worker_unsupported"
    assert "result" not in result.state.params
    assert result.state.params["secret"] == "unavailable"
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert len(attempts) == 1 and attempts[0].outcome.status == "unknown"
    assert _basis(ctx, attempts[0]).contract.contract_id == "test.selected_input.v1"


@pytest.mark.parametrize("route", ["sync", "async"])
def test_outside_contract_result_never_completes_as_success(tmp_path, monkeypatch, route):
    monkeypatch.setattr(__import__(__name__, fromlist=["_MODE"]), "_MODE", "outside")
    ctx, registry, state = _context(tmp_path)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert "smuggled" not in result.state.params
    assert result.state.params["secret"] == "unavailable"
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert len(attempts) == 1 and attempts[0].outcome.status == "unknown"


@pytest.mark.parametrize("route", ["sync", "async"])
def test_interrupted_cache_replay_has_no_successful_completion(tmp_path, monkeypatch, route):
    ctx, registry, state = _context(tmp_path)
    put = ctx.store.put_json

    def interrupted(obj, opts, canon_spec=None, *, return_selected_profile=False):
        if (
            opts.kind == "scientist.experiment_state"
            and not opts.inputs
            and isinstance(obj, dict)
            and obj.get("params") == {"visible": "first", "result": "seen:first"}
        ):
            attempts = ctx.run.read_runtime_invocation_attempts()
            if len(attempts) == 2 and attempts[-1].outcome is None:
                raise OSError("interrupted replay publication")
        return put(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )

    monkeypatch.setattr(ctx.store, "put_json", interrupted)
    workflow = WorkflowSpec(
        workflow_id="input_interrupted_replay",
        nodes=[
            NodeInvocation(alias="one", node_id=_COMPONENT),
            NodeInvocation(alias="two", node_id=_COMPONENT, depends_on=["one"]),
        ],
    )
    with pytest.raises(OSError, match="interrupted replay publication"):
        _run(ctx, registry, state, route=route, workflow=workflow)
    attempts = ctx.run.read_runtime_invocation_attempts()
    assert [attempt.outcome.status for attempt in attempts] == ["ok", "unknown"]
    assert len(_SEEN) == 1


@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize("rename", [False, True])
def test_protected_class_cannot_remove_port_by_renaming_component(
    tmp_path, monkeypatch, route, rename
):
    ctx, registry, state = _context(tmp_path)
    metadata = _SPEC.metadata
    if rename:
        metadata = metadata.model_copy(
            update={"component_id": ComponentId.parse("scientist.node_disguised_probe@1.0.0")}
        )
    removed = NodeSpec(metadata=metadata, state_writes=["params.result"])
    monkeypatch.setattr(__import__(__name__, fromlist=["_SPEC"]), "_SPEC", removed)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert _SEEN == []


@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize("callback", ["bind", "spec"])
def test_changed_definition_refuses_before_spec_or_bind_callback(
    tmp_path, monkeypatch, route, callback
):
    ctx, registry, state = _context(tmp_path)
    calls = []
    if callback == "bind":

        def changed(self, params):
            calls.append(params)
            return self

        monkeypatch.setattr(_Probe, "bind", changed, raising=False)
        params = {"not_permitted": "unadmitted"}
    else:

        def changed(self):
            calls.append(True)
            return _SPEC

        monkeypatch.setattr(_Probe, "spec", property(changed))
        params = {}
    workflow = WorkflowSpec(
        workflow_id="changed_prebind",
        nodes=[NodeInvocation(alias="probe", node_id=_COMPONENT, params=params)],
    )
    result = _run(ctx, registry, state, route=route, workflow=workflow)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert calls == [] and _SEEN == []


_GRAPH_PATH = None
_PREPARER_CALLS = []


class _PreparedProbe(_Probe):
    def prepare_cache_input(self, ctx, state):
        from polisyos.data_forge.read_api.academic import SKGQuery

        assert ctx.prepared_skg_read is None
        _PREPARER_CALLS.append(state.run_id)
        return SKGQuery.prepare_read(db_path=_GRAPH_PATH, index_dir=_GRAPH_PATH.parent)


def test_real_prepared_graph_is_not_passed_to_restricted_cache_validator(tmp_path, monkeypatch):
    import duckdb

    from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
    from polisyos.scientist.orchestration.engine.state_branching import branch_state

    ctx, registry, state = _context(tmp_path)
    source = tmp_path / "selected.duckdb"
    connection = duckdb.connect(str(source))
    connection.execute("CREATE TABLE private_graph(value VARCHAR)")
    connection.execute("INSERT INTO private_graph VALUES ('unselected graph value')")
    connection.close()
    monkeypatch.setattr(__import__(__name__, fromlist=["_GRAPH_PATH"]), "_GRAPH_PATH", source)
    _PREPARER_CALLS.clear()
    registry.register(_PreparedProbe(), override=True)
    monkeypatch.setitem(
        component_identity._OWNERS, _COMPONENT, component_identity._owner(_PreparedProbe)
    )
    original_get = NodeResultCache.get
    seeded_refs = []

    def cache_hit(cache, key, **kwargs):
        if not seeded_refs:
            projected = ExperimentState(
                run_id=state.run_id,
                execution_profile=state.execution_profile,
                params={"visible": "first"},
            )
            branch = branch_state(
                projected, write_paths=["params.result"], enforce_write_scope=True
            )
            branch.state.params["result"] = "seen:first"
            seeded_refs.append(
                cache.put(key, _COMPONENT, NodeOutcome(status="ok", state=branch.state))
            )
        return original_get(cache, key, **kwargs)

    monkeypatch.setattr(NodeResultCache, "get", cache_hit)
    result = _run(ctx, registry, state, route="sync")
    assert result.report.status == "ok"
    assert len(_VALIDATED_CACHE) == 1
    assert len(_PREPARER_CALLS) == 1 and len(seeded_refs) == 1
    assert ctx.store.verify(seeded_refs[0]).ok
    assert result.state.params["secret"] == "unavailable"


_BIND_CALLS = []


class _BoundProbe(_Probe):
    def __init__(self, factor=0):
        self.factor = factor

    def bind(self, params):
        _BIND_CALLS.append(dict(params))
        return type(self)(factor=params["factor"])

    def execute(self, ctx, state):
        outcome = super().execute(ctx, state)
        outcome.state.params["result"] += f":{self.factor}"
        return outcome

    async def execute_async(self, ctx, state):
        return self.execute(ctx, state)


@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize("allowed", [False, True])
def test_held_bind_keys_precede_real_binder_and_bound_state_is_reconciled(
    tmp_path, monkeypatch, route, allowed
):
    contract = _SPEC.input_contract.model_copy(update={"bind_param_keys": ("factor",)})
    monkeypatch.setattr(
        __import__(__name__, fromlist=["_SPEC"]),
        "_SPEC",
        _SPEC.model_copy(update={"input_contract": contract}),
    )
    ctx, registry, state = _context(tmp_path)
    registry.register(_BoundProbe(), override=True)
    monkeypatch.setitem(
        component_identity._OWNERS, _COMPONENT, component_identity._owner(_BoundProbe)
    )
    _BIND_CALLS.clear()
    params = {"factor": 7} if allowed else {"not_permitted": "unadmitted"}
    workflow = WorkflowSpec(
        workflow_id="held_binding",
        nodes=[NodeInvocation(alias="probe", node_id=_COMPONENT, params=params)],
    )
    result = _run(ctx, registry, state, route=route, workflow=workflow)
    if allowed:
        assert result.report.status == "ok"
        assert _BIND_CALLS and all(call == {"factor": 7} for call in _BIND_CALLS)
        assert result.state.params["result"] == "seen:first:7"
    else:
        assert result.report.status == "fail"
        assert result.report.nodes[0].error.code == "node.input_port_refused"
        assert _BIND_CALLS == [] and _SEEN == []


@pytest.mark.parametrize("route", ["sync", "async"])
def test_direct_helper_code_change_refuses_before_unchanged_execute(tmp_path, monkeypatch, route):
    ctx, registry, state = _context(tmp_path)

    def counterfeit(state):
        raise AssertionError("changed helper must not run")

    monkeypatch.setattr(_observe, "__code__", counterfeit.__code__)
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert _SEEN == []


_INVALID_SPEC = None
_SPEC_READS = []


class _UnsupportedVersionProbe(_Probe):
    @property
    def spec(self):
        _SPEC_READS.append(True)
        return _INVALID_SPEC


@pytest.mark.parametrize("route", ["sync", "async"])
def test_even_an_invalid_held_version_refuses_before_spec_callback(tmp_path, monkeypatch, route):
    ctx, registry, state = _context(tmp_path)
    invalid = _SPEC.model_copy(
        update={"input_contract": _SPEC.input_contract.model_copy(update={"schema_version": "2.0"})}
    )
    monkeypatch.setattr(__import__(__name__, fromlist=["_INVALID_SPEC"]), "_INVALID_SPEC", invalid)
    registry.register(_UnsupportedVersionProbe(), override=True)
    monkeypatch.setitem(
        component_identity._OWNERS, _COMPONENT, component_identity._owner(_UnsupportedVersionProbe)
    )
    _SPEC_READS.clear()
    result = _run(ctx, registry, state, route=route)
    assert result.report.status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert _SPEC_READS == [] and _SEEN == []
