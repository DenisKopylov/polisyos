"""Independent finite stored-model graph oracle (native execution pending).

The provider uses ordinary model assignment/copy. Validators deliberately alter
their returned public Pydantic field graph, including aliased children, without
external effects. This tests graph accounting/rollback, not a Python sandbox.
The unchanged earlier oracle supplies the real executor/CAS/cache consumers.
"""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, ClassVar, Self

import pytest
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutor,
    _merge_cached_outcome_state,
)
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import mutation_journal_for_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

from .test_producer_model_scope_oracle import (
    _CompletionConsumer,
    _Leaf,
    _ModelNode,
    _root_field_snapshot,
    _snapshot,
)


class _GraphShape(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    tag: str
    leaf: _Leaf
    rows: list[_Leaf]
    unchanged: str
    count: int


class _ChangingGraph(_GraphShape):
    @model_validator(mode="after")
    def stored_graph_result(self) -> Self:
        if self.count == 23:
            # Deliberate public Pydantic validator result, not a producer
            # reflection call. The selected profile must refuse this model
            # before the producer; there is no external callback effect.
            self.__dict__["tag"] = "validator-changed"
            self.leaf.__dict__["count"] = 31
        return self


class _BeforeGraph(_GraphShape):
    @model_validator(mode="before")
    @classmethod
    def incoming_graph_result(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("count") == 23:
            value["tag"] = "validator-changed"
        return value


class _SiblingFieldGraph(_GraphShape):
    reject_after: ClassVar[bool] = False

    @field_validator("count")
    @classmethod
    def field_result(cls, value: int, info: ValidationInfo) -> int:
        if value == 23:
            assert info.data is not None
            info.data["tag"] = "validator-changed"
            info.data["leaf"].__dict__["count"] = 31
            if cls.reject_after:
                raise ValueError("field validation rejected its changed graph")
        return value


class _AliasSplittingFieldGraph(_GraphShape):
    @field_validator("count")
    @classmethod
    def equal_values_different_alias(cls, value: int, info: ValidationInfo) -> int:
        if value == 23:
            assert info.data is not None
            info.data["rows"][0] = info.data["leaf"].model_copy(deep=True)
        return value


class _RejectingFieldGraph(_SiblingFieldGraph):
    reject_after: ClassVar[bool] = True


class _NormalizingGraph(_GraphShape):
    @field_validator("count")
    @classmethod
    def normalize_count(cls, value: int) -> int:
        return abs(value)


def _graph_state(
    run_id: str, model: type[_GraphShape], *, readonly: bool = False
) -> ExperimentState:
    leaf = _Leaf(count=4, tag="leaf-stable")
    holder = model(count=3, tag="stable", leaf=leaf, rows=[leaf], unchanged="keep")
    holder.rows[0] = holder.leaf
    state = ExperimentState(run_id=run_id, params={"untouched": {"number": 101}})
    state.params["holder"] = holder
    if readonly:
        state.params["readonly"] = holder.leaf
    assert holder.leaf is holder.rows[0]
    if readonly:
        assert holder.leaf is state.params["readonly"]
    return state


def _public_graph_paths(value: Any, path: str = "params") -> dict[str, Any]:
    """Enumerate every finite actual public model/container leaf path."""
    if isinstance(value, BaseModel):
        rows: dict[str, Any] = {}
        for name in type(value).model_fields:
            rows.update(_public_graph_paths(getattr(value, name), f"{path}.{name}"))
        return rows
    if isinstance(value, dict):
        rows = {}
        for name, child in value.items():
            rows.update(_public_graph_paths(child, f"{path}.{name}"))
        return rows
    if isinstance(value, (list, tuple)):
        rows = {}
        for index, child in enumerate(value):
            rows.update(_public_graph_paths(child, f"{path}.{index}"))
        return rows
    return {path: value}


class _ValidationNode(_ModelNode):
    def __init__(self, *, writes: list[str], readonly: bool, copy_first: bool = False):
        super().__init__(field="count", writes=writes, shared=readonly)
        self.copy_first = copy_first
        self.paths_before: dict[str, Any] | None = None
        self.paths_after: dict[str, Any] | None = None
        self.alias_before: dict[str, bool] | None = None
        self.alias_after: dict[str, bool] | None = None
        self.copy_shared: bool | None = None

    def _aliases(self, state: ExperimentState) -> dict[str, bool]:
        holder = state.params["holder"]
        aliases = {"list_child": holder.leaf is holder.rows[0]}
        if self.shared:
            aliases["readonly_child"] = holder.leaf is state.params["readonly"]
        return aliases

    def _produce(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        self.view = state
        self.trace_path = ctx.run.trace_path
        self.root_before = _root_field_snapshot(state)
        self.before = _snapshot(state.params)
        self.paths_before = _public_graph_paths(state.params)
        self.alias_before = self._aliases(state)
        holder = state.params["holder"]
        try:
            if self.copy_first:
                copied = holder.model_copy(deep=False)
                self.copy_shared = copied.leaf is holder.leaf
                holder = copied
            holder.count = -23 if isinstance(holder, _NormalizingGraph) else 23
        finally:
            self.paths_after = _public_graph_paths(state.params)
            self.alias_after = self._aliases(state)
            journal = mutation_journal_for_state(state)
            self.journal_after = (
                [operation.model_dump(mode="json") for operation in journal.operations]
                if journal is not None
                else []
            )
        ref = ctx.store.put_json(
            _snapshot(state.params["holder"]),
            PutOptions(kind="test.validation_graph_effect", media_type="application/json"),
        )
        self.effects.append(ref)
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


def _exercise(tmp_path: Path, *, mode: str, node, state):
    """Capture a synchronous typed refusal without losing the real consumers."""
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store, bundle, run_id=state.run_id)
    registry = NodeRegistry()
    registry.register(node)
    consumer = _CompletionConsumer(store)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("validation-oracle"))
    workflow = WorkflowSpec(
        workflow_id="independent_validation_graph",
        nodes=[NodeInvocation(alias="model", node_id=node.spec.metadata.component_id)],
    )
    executor = (
        WorkflowExecutor(ctx, registry, checkpoint_hook=consumer)
        if mode == "sync"
        else AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=consumer)
    )
    refusal = None
    result = None
    try:
        result = executor.execute(workflow, state)
        if mode == "async":
            result = asyncio.run(result)
    except TypeError as exc:
        refusal = {"type": type(exc).__name__, "message": str(exc)}
    return store, run, consumer, result, refusal


def _observed(tmp_path: Path, *, store, run, node, state, before, consumer, result, refusal):
    reopened = FileSystemCAS(store.root)
    events = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
    observed = {
        "actual_holder_fields": list(type(state.params["holder"]).model_fields),
        "base_before": before,
        "base_after": _snapshot(state.params),
        "producer_before": node.before,
        "producer_after": _snapshot(node.view.params) if node.view is not None else None,
        "producer_calls": node.calls,
        "full_paths_before": node.paths_before,
        "full_paths_after": node.paths_after,
        "alias_before": node.alias_before,
        "alias_after": node.alias_after,
        "copy_shared": node.copy_shared,
        "producer_journal": node.journal_after,
        "result_status": result.report.status if result is not None else "fail",
        "public_refusal": refusal,
        "physical_cache_publications": [
            row for row in events if row.get("event") == "NODE_CACHE_STORE"
        ],
        "physical_effects": [
            {
                "verified": reopened.verify(ref).ok,
                "ref": ref.model_dump(mode="json"),
                "payload": json.loads(reopened.get_bytes(ref)),
            }
            for ref in node.effects
        ],
        "physical_completion_callbacks": [
            {
                "verified": reopened.verify(ref).ok,
                "ref": ref.model_dump(mode="json"),
                "payload": json.loads(reopened.get_bytes(ref)),
            }
            for ref in consumer.refs
        ],
    }
    (tmp_path / "validation-graph-measurements.json").write_text(
        json.dumps(observed, sort_keys=True, indent=2) + "\n"
    )
    print("VALIDATION_GRAPH_MEASUREMENTS=" + json.dumps(observed, sort_keys=True))
    return observed


def _cached_current_result(store, run, node, state, model):
    events = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
    event = next(row for row in events if row["event"] == "NODE_CACHE_STORE")
    ref = ArtifactRef.model_validate(event["refs"]["outputs"][0])
    reopened = FileSystemCAS(store.root)
    entry = json.loads(reopened.get_bytes(ref))
    reader = NodeResultCache(reopened, state.run_id)
    assert reader.load_entry(ref)
    cached = reader.get(entry["idempotency_key"])
    assert cached is not None
    current = _graph_state(state.run_id, model)
    current.params["holder"].unchanged = "current-unrelated"
    current.params["holder"].leaf.tag = "current-leaf-tag"
    current_before = _snapshot(current.params)
    applied = _merge_cached_outcome_state(
        alias="model", node=node, base_state=current, outcome=cached
    )
    return current, current_before, applied


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_supported_validator_normalization_reopens_cache_intent(tmp_path: Path, mode: str):
    state = _graph_state("R_validator_normalization", _NormalizingGraph)
    before = _snapshot(state.params)
    node = _ValidationNode(writes=["params.holder.count"], readonly=False)
    store, run, consumer, result, refusal = _exercise(tmp_path, mode=mode, node=node, state=state)
    observed = _observed(
        tmp_path,
        store=store,
        run=run,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
        refusal=refusal,
    )
    expected = deepcopy(before)
    expected["holder"]["count"] = 23
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    assert observed["result_status"] == "ok"
    assert _snapshot(result.state.params) == expected
    assert observed["alias_before"] == observed["alias_after"] == {"list_child": True}
    assert observed["physical_effects"][0]["verified"]
    assert observed["physical_effects"][0]["payload"] == expected["holder"]
    assert observed["physical_completion_callbacks"][0]["payload"] == expected
    current, current_before, applied = _cached_current_result(
        store, run, node, state, _NormalizingGraph
    )
    expected_current = deepcopy(current_before)
    expected_current["holder"]["count"] = 23
    assert _snapshot(applied.params) == expected_current
    assert _snapshot(current.params) == current_before


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("model", [_BeforeGraph, _ChangingGraph], ids=["before", "after"])
def test_model_level_assignment_callbacks_refuse_before_producer(
    tmp_path: Path, mode: str, model: type[_GraphShape]
):
    state = _graph_state("R_model_validator_profile", model)
    before = _snapshot(state.params)
    node = _ValidationNode(writes=["params.holder"], readonly=False)
    store, run, consumer, result, refusal = _exercise(tmp_path, mode=mode, node=node, state=state)
    observed = _observed(
        tmp_path,
        store=store,
        run=run,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
        refusal=refusal,
    )
    assert observed["producer_calls"] == 0
    assert observed["base_after"] == before
    assert observed["result_status"] == "fail"
    if refusal is not None:
        assert "model" in refusal["message"].lower()
    assert observed["producer_journal"] == []
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []
    assert observed["physical_cache_publications"] == []


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "model", [_SiblingFieldGraph, _AliasSplittingFieldGraph], ids=["values", "alias-only"]
)
def test_field_validator_sibling_delta_refuses_before_publication(
    tmp_path: Path, mode: str, model: type[_GraphShape]
):
    state = _graph_state("R_field_validator_sibling", model)
    before = _snapshot(state.params)
    node = _ValidationNode(writes=["params.holder.count"], readonly=False)
    store, run, consumer, result, refusal = _exercise(tmp_path, mode=mode, node=node, state=state)
    observed = _observed(
        tmp_path,
        store=store,
        run=run,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
        refusal=refusal,
    )
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    assert observed["result_status"] == "fail"
    assert observed["alias_before"] == observed["alias_after"] == {"list_child": True}
    assert observed["full_paths_after"] == observed["full_paths_before"]
    assert observed["producer_after"] == observed["producer_before"]
    assert observed["producer_journal"] == []
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []
    assert observed["physical_cache_publications"] == []


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_validator_readonly_alias_is_not_hidden_by_copy(tmp_path: Path, mode: str):
    state = _graph_state("R_validator_readonly_alias", _SiblingFieldGraph, readonly=True)
    before = _snapshot(state.params)
    node = _ValidationNode(writes=["params.holder"], readonly=True, copy_first=True)
    store, run, consumer, result, refusal = _exercise(tmp_path, mode=mode, node=node, state=state)
    observed = _observed(
        tmp_path,
        store=store,
        run=run,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
        refusal=refusal,
    )
    assert observed["producer_calls"] == 1
    assert (
        observed["alias_before"]
        == observed["alias_after"]
        == {"list_child": True, "readonly_child": True}
    )
    assert observed["copy_shared"] is True
    assert observed["base_after"] == before
    assert observed["result_status"] == "fail"
    assert observed["full_paths_after"] == observed["full_paths_before"]
    assert observed["producer_after"] == observed["producer_before"]
    assert observed["producer_journal"] == []
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []
    assert observed["physical_cache_publications"] == []


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_validator_exception_restores_entire_public_graph(tmp_path: Path, mode: str):
    state = _graph_state("R_validator_exception", _RejectingFieldGraph)
    before = _snapshot(state.params)
    node = _ValidationNode(writes=["params.holder"], readonly=False)
    store, run, consumer, result, refusal = _exercise(tmp_path, mode=mode, node=node, state=state)
    observed = _observed(
        tmp_path,
        store=store,
        run=run,
        node=node,
        state=state,
        before=before,
        consumer=consumer,
        result=result,
        refusal=refusal,
    )
    assert observed["producer_calls"] == 1
    assert observed["base_after"] == before
    assert observed["result_status"] == "fail"
    assert observed["alias_before"] == observed["alias_after"] == {"list_child": True}
    assert observed["full_paths_after"] == observed["full_paths_before"]
    assert observed["producer_after"] == observed["producer_before"]
    assert observed["producer_journal"] == []
    assert observed["physical_effects"] == observed["physical_completion_callbacks"] == []
    assert observed["physical_cache_publications"] == []
