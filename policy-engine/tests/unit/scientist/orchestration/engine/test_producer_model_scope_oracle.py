"""Ordinary mutable models obey the actual producer grant before publication.

These are in-memory ordinary model-field operations, not custom descriptors,
private attributes, object.__setattr__, or a model-class wire reconstruction
contract. Runtime params assignment establishes the real model/alias premise;
user-facing ExperimentState ingestion is a separate boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutor,
    _merge_cached_outcome_state,
)
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _Leaf(BaseModel):
    count: int
    tag: str


class _Holder(BaseModel):
    leaf: _Leaf
    rows: list[_Leaf]


class _ValidatingHolder(_Holder):
    model_config = ConfigDict(validate_assignment=True)


_FIELD_VALUES = {"count": 23, "tag": "changed"}
_FIELDS = tuple(_Leaf.model_fields)


def _snapshot(value: Any) -> Any:
    """Enumerate the actual public model fields; never inspect private tracking."""
    if isinstance(value, BaseModel):
        return {name: _snapshot(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, dict):
        return {name: _snapshot(child) for name, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_snapshot(child) for child in value]
    return value


def _root_field_snapshot(state: ExperimentState) -> dict[str, Any]:
    """Use the ordinary public getter and actual declared state field membership."""
    name = "reports_index"
    assert name in ExperimentState.model_fields
    present = hasattr(state, name)
    return {
        "field": name,
        "present": present,
        "value": _snapshot(getattr(state, name)) if present else None,
    }


def _state(
    run_id: str, *, shared: bool = False, tag: str = "stable", validating: bool = False
) -> ExperimentState:
    leaf = _Leaf(count=3, tag=tag)
    model = _ValidatingHolder if validating else _Holder
    holder = model(leaf=leaf, rows=[leaf if shared else _Leaf(count=4, tag="row")])
    # Pydantic can normalize values independently on ingestion. These ordinary
    # runtime assignments establish genuine aliases before the producer branch.
    if shared:
        holder.rows[0] = holder.leaf
    state = ExperimentState(run_id=run_id, params={"untouched": {"number": 101}})
    state.params["holder"] = holder
    if shared:
        state.params["readonly"] = holder.leaf
        assert holder.leaf is holder.rows[0] is state.params["readonly"]
    return state


class _CompletionConsumer:
    """The actual executor completion callback physically persists its input."""

    def __init__(self, store: FileSystemCAS) -> None:
        self.store = store
        self.refs: list[ArtifactRef] = []

    def on_node_complete(self, *, state: ExperimentState, **_kwargs: Any) -> None:
        ref = self.store.put_json(
            _snapshot(state.params),
            PutOptions(kind="test.model_scope_completion", media_type="application/json"),
        )
        self.refs.append(ref)


class _ModelNode:
    def __init__(
        self,
        *,
        field: str,
        writes: list[str],
        shared: bool,
        append: bool = False,
        copy_alias: bool = False,
        replace_validated_rows: bool = False,
        delete_root_field: bool = False,
    ):
        self.field = field
        self.shared = shared
        self.append = append
        self.copy_alias = copy_alias
        self.replace_validated_rows = replace_validated_rows
        self.delete_root_field = delete_root_field
        self.trace_path: Path | None = None
        self.root_before: dict[str, Any] | None = None
        self.copy_observation: dict[str, bool] | None = None
        self.calls = 0
        self.view: ExperimentState | None = None
        self.before: Any = None
        self.effects: list[ArtifactRef] = []
        self.journal_after: list[dict[str, Any]] = []
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.independent_model_scope@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Ordinary model ownership consumer",
                description="Independent finite model field and live-alias oracle",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.holder"] + (["params.readonly"] if shared else []),
            state_writes=writes,
        )

    def _produce(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        self.view = state
        self.trace_path = ctx.run.trace_path
        self.before = _snapshot(state.params)
        self.root_before = _root_field_snapshot(state)
        holder = state.params["holder"]
        assert isinstance(holder, _Holder)
        assert isinstance(holder.leaf, _Leaf)
        if self.shared:
            assert holder.leaf is holder.rows[0] is state.params["readonly"]
        if self.copy_alias:
            copied = holder.model_copy(deep=False)
            self.copy_observation = {
                "copy_is_distinct": copied is not holder,
                "copy_shares_leaf": copied.leaf is holder.leaf,
                "copy_shares_list": copied.rows is holder.rows,
            }
            assert all(self.copy_observation.values())
            state.params["readonly_holder"] = copied
            # Parent assignment grants its descendants under the original
            # prefix law. Ordinary nested branching now attenuates that grant;
            # the copied holder becomes an actually undeclared live owner.
            narrowed = branch_state(state, write_paths=[f"params.holder.leaf.{self.field}"])
            state = narrowed.state
            holder = state.params["holder"]
            self.copy_observation["narrowed_shared_leaf"] = (
                holder.leaf is state.params["readonly_holder"].leaf
            )
            assert self.copy_observation["narrowed_shared_leaf"]
            self.view = state
            self.before = _snapshot(state.params)
        if self.delete_root_field:
            del state.reports_index
        elif self.replace_validated_rows:
            assert holder.model_config["validate_assignment"] is True
            holder.rows = [_Leaf(count=8, tag="assigned")]
            holder.rows.append(_Leaf(count=9, tag="appended"))
            holder.rows[0].count = 11
        elif self.append:
            holder.rows.append(_Leaf(count=7, tag="appended"))
        else:
            # setattr uses the ordinary model setter; it is not the explicitly
            # excluded object.__setattr__ bypass or an unknown field operation.
            setattr(holder.leaf, self.field, _FIELD_VALUES[self.field])
        journal = mutation_journal_for_state(state)
        self.journal_after = (
            [operation.model_dump(mode="json") for operation in journal.operations]
            if journal is not None
            else []
        )
        ref = ctx.store.put_json(
            _snapshot(state.params["holder"]),
            PutOptions(kind="test.model_scope_effect", media_type="application/json"),
        )
        self.effects.append(ref)
        return NodeOutcome(status="ok", state=state, artifacts=[ref])

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return self._produce(ctx, state)

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return self._produce(ctx, state)


def _execute(tmp_path: Path, *, mode: str, node: _ModelNode, state: ExperimentState):
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store, bundle, run_id=state.run_id)
    registry = NodeRegistry()
    registry.register(node)
    consumer = _CompletionConsumer(store)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("model-oracle"))
    workflow = WorkflowSpec(
        workflow_id="independent_model_scope",
        nodes=[NodeInvocation(alias="model", node_id=node.spec.metadata.component_id)],
    )
    executor = (
        WorkflowExecutor(ctx, registry, checkpoint_hook=consumer)
        if mode == "sync"
        else AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=consumer)
    )
    result = executor.execute(workflow, state)
    if mode == "async":
        result = asyncio.run(result)
    return store, run, consumer, result


def _measure(tmp_path: Path, *, store, node, state, before, consumer, result) -> dict[str, Any]:
    reopened = FileSystemCAS(store.root)
    measurements = {
        "actual_model_fields": list(_Leaf.model_fields),
        "base_before": before,
        "base_after": _snapshot(state.params),
        "producer_before": node.before,
        "producer_after": _snapshot(node.view.params) if node.view is not None else None,
        "producer_calls": node.calls,
        "root_before": node.root_before,
        "root_after": _root_field_snapshot(node.view) if node.view is not None else None,
        "base_root": _root_field_snapshot(state),
        "physical_cache_publications": [
            json.loads(line)
            for line in node.trace_path.read_text().splitlines()
            if json.loads(line).get("event") == "NODE_CACHE_STORE"
        ]
        if node.trace_path is not None
        else [],
        "producer_journal": node.journal_after,
        "shallow_copy_observation": node.copy_observation,
        "result_status": result.report.status,
        "physical_effects": [
            {
                "ref": ref.model_dump(mode="json"),
                "verified": reopened.verify(ref).ok,
                "payload": json.loads(reopened.get_bytes(ref)),
            }
            for ref in node.effects
        ],
        "physical_completion_callbacks": [
            {
                "ref": ref.model_dump(mode="json"),
                "verified": reopened.verify(ref).ok,
                "payload": json.loads(reopened.get_bytes(ref)),
            }
            for ref in consumer.refs
        ],
    }
    (tmp_path / "model-scope-measurements.json").write_text(
        json.dumps(measurements, sort_keys=True, indent=2) + "\n"
    )
    print("MODEL_SCOPE_MEASUREMENTS=" + json.dumps(measurements, sort_keys=True))
    return measurements


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("declared", [False, True])
def test_ordinary_model_fields_refuse_or_journal_before_real_completion(
    tmp_path: Path, mode: str, field: str, declared: bool
) -> None:
    state = _state("R_ordinary_model_scope")
    before = _snapshot(state.params)
    path = f"params.holder.leaf.{field}"
    node = _ModelNode(field=field, writes=[path] if declared else [], shared=False)
    store, run, consumer, result = _execute(tmp_path, mode=mode, node=node, state=state)
    observed = _measure(
        tmp_path,
        store=store,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
    )
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    if not declared:
        assert observed["result_status"] == "fail"
        assert observed["producer_after"] == observed["producer_before"]
        assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []
        return
    expected = deepcopy(before)
    expected["holder"]["leaf"][field] = _FIELD_VALUES[field]
    assert observed["result_status"] == "ok"
    assert _snapshot(result.state.params) == expected
    assert observed["physical_effects"][0]["payload"] == expected["holder"]
    assert observed["physical_completion_callbacks"][0]["payload"] == expected
    assert all(x["verified"] for x in observed["physical_effects"])
    assert any(
        row["path"] == path and row["value"] == _FIELD_VALUES[field]
        for row in observed["producer_journal"]
    )

    publications = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
    entry_event = next(row for row in publications if row["event"] == "NODE_CACHE_STORE")
    entry_ref = ArtifactRef.model_validate(entry_event["refs"]["outputs"][0])
    reopened = FileSystemCAS(store.root)
    entry = json.loads(reopened.get_bytes(entry_ref))
    reader = NodeResultCache(reopened, state.run_id)
    assert reader.load_entry(entry_ref)
    cached = reader.get(entry["idempotency_key"])
    assert cached is not None
    current = _state(state.run_id)
    # A cache intent applies to the current ordinary model without reconstructing
    # a user-defined Python class from the cached JSON outcome.
    neighbor = "tag" if field == "count" else "count"
    setattr(current.params["holder"].leaf, neighbor, "new-neighbor" if neighbor == "tag" else 99)
    current_before = _snapshot(current.params)
    applied = _merge_cached_outcome_state(
        alias="model", node=node, base_state=current, outcome=cached
    )
    expected_current = deepcopy(current_before)
    expected_current["holder"]["leaf"][field] = _FIELD_VALUES[field]
    assert _snapshot(applied.params) == expected_current
    assert _snapshot(current.params) == current_before
    assert node.calls == 1


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("field", _FIELDS)
def test_live_model_readonly_alias_refuses_before_any_shared_field_changes(
    tmp_path: Path, mode: str, field: str
) -> None:
    state = _state("R_model_readonly_alias", shared=True)
    before = _snapshot(state.params)
    node = _ModelNode(field=field, writes=[f"params.holder.leaf.{field}"], shared=True)
    store, _run, consumer, result = _execute(tmp_path, mode=mode, node=node, state=state)
    observed = _measure(
        tmp_path,
        store=store,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
    )
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    assert observed["producer_after"] == observed["producer_before"]
    assert observed["result_status"] == "fail"
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_model_owned_list_child_records_real_append_and_preserves_base(
    tmp_path: Path, mode: str
) -> None:
    state = _state("R_model_list_child")
    before = _snapshot(state.params)
    node = _ModelNode(field="count", writes=["params.holder.rows"], shared=False, append=True)
    store, _run, consumer, result = _execute(tmp_path, mode=mode, node=node, state=state)
    observed = _measure(
        tmp_path,
        store=store,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
    )
    expected = deepcopy(before)
    expected["holder"]["rows"].append({"count": 7, "tag": "appended"})
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    assert observed["result_status"] == "ok"
    assert _snapshot(result.state.params) == expected
    assert observed["physical_effects"][0]["payload"] == expected["holder"]
    assert observed["physical_completion_callbacks"][0]["payload"] == expected
    assert any(
        row["path"] == "params.holder.rows" and row["operation"] == "append"
        for row in observed["producer_journal"]
    )


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_ordinary_shallow_model_copy_retains_child_owner_after_scope_attenuation(
    tmp_path: Path, mode: str
) -> None:
    state = _state("R_model_copy_owner")
    before = _snapshot(state.params)
    node = _ModelNode(
        field="count",
        writes=["params.holder.leaf.count", "params.readonly_holder"],
        shared=False,
        copy_alias=True,
    )
    store, _run, consumer, result = _execute(tmp_path, mode=mode, node=node, state=state)
    observed = _measure(
        tmp_path,
        store=store,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
    )
    assert observed["producer_calls"] == 1
    assert observed["shallow_copy_observation"] == {
        "copy_is_distinct": True,
        "copy_shares_leaf": True,
        "copy_shares_list": True,
        "narrowed_shared_leaf": True,
    }
    assert observed["base_after"] == before
    assert observed["producer_after"] == observed["producer_before"]
    assert observed["result_status"] == "fail"
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_validating_model_stored_rows_preserve_all_subsequent_intents_on_reopen(
    tmp_path: Path, mode: str
) -> None:
    state = _state("R_validated_model_rows", validating=True)
    before = _snapshot(state.params)
    node = _ModelNode(
        field="count",
        writes=["params.holder.rows"],
        shared=False,
        replace_validated_rows=True,
    )
    store, run, consumer, result = _execute(tmp_path, mode=mode, node=node, state=state)
    observed = _measure(
        tmp_path,
        store=store,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
    )
    expected = deepcopy(before)
    expected["holder"]["rows"] = [
        {"count": 11, "tag": "assigned"},
        {"count": 9, "tag": "appended"},
    ]
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    assert observed["result_status"] == "ok"
    assert _snapshot(result.state.params) == expected
    assert observed["physical_effects"][0]["payload"] == expected["holder"]
    assert observed["physical_completion_callbacks"][0]["payload"] == expected
    intents = observed["producer_journal"]
    assert any(
        row["path"] == "params.holder.rows" and row["operation"] == "append" for row in intents
    )
    assert any(
        row["path"] == "params.holder.rows.0.count" and row["value"] == 11 for row in intents
    )
    publications = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
    entry_event = next(row for row in publications if row["event"] == "NODE_CACHE_STORE")
    ref = ArtifactRef.model_validate(entry_event["refs"]["outputs"][0])
    reopened = FileSystemCAS(store.root)
    entry = json.loads(reopened.get_bytes(ref))
    reader = NodeResultCache(reopened, state.run_id)
    assert reader.load_entry(ref)
    cached = reader.get(entry["idempotency_key"])
    assert cached is not None
    current = _state(state.run_id, tag="current-neighbor", validating=True)
    current_before = _snapshot(current.params)
    applied = _merge_cached_outcome_state(
        alias="model", node=node, base_state=current, outcome=cached
    )
    expected_current = deepcopy(current_before)
    expected_current["holder"]["rows"] = expected["holder"]["rows"]
    assert _snapshot(applied.params) == expected_current
    assert _snapshot(current.params) == current_before
    assert node.calls == 1


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_ordinary_root_field_deletion_refuses_before_real_publication(
    tmp_path: Path, mode: str
) -> None:
    state = _state("R_required_root_delete")
    before = _snapshot(state.params)
    root_before = _root_field_snapshot(state)
    assert root_before["present"]
    node = _ModelNode(field="count", writes=[], shared=False, delete_root_field=True)
    store, _run, consumer, result = _execute(tmp_path, mode=mode, node=node, state=state)
    observed = _measure(
        tmp_path,
        store=store,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
    )
    assert observed["producer_calls"] == 1
    assert observed["root_before"] == observed["root_after"] == observed["base_root"] == root_before
    assert observed["base_after"] == before
    assert observed["producer_after"] == observed["producer_before"]
    assert observed["result_status"] == "fail"
    assert observed["producer_journal"] == []
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []
    assert observed["physical_cache_publications"] == []
