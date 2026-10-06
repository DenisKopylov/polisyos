"""Actual producer/cache/reopened consumers retain live list descendant ownership."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CASES = {
    "no_shift": [{"id": "b", "v": 5}, {"id": "c", "v": 2}],
    "insert_existing": [{"id": "new", "v": 0}, {"id": "b", "v": 5}, {"id": "c", "v": 2}],
    "insert_new": [{"id": "new", "v": 5}, {"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "pop_shift": [{"id": "c", "v": 5}],
    "remove_shift": [{"id": "c", "v": 5}],
    "delete_slice": [{"id": "c", "v": 5}],
    "set_slice": [{"id": "new", "v": 0}, {"id": "extra", "v": 0}, {"id": "c", "v": 5}],
    "reverse": [{"id": "c", "v": 2}, {"id": "b", "v": 5}],
    "sort": [{"id": "c", "v": 2}, {"id": "b", "v": 5}],
    "repeat_alias": [
        {"id": "b", "v": 5},
        {"id": "c", "v": 2},
        {"id": "b", "v": 5},
        {"id": "c", "v": 2},
    ],
    "negative_set": [{"id": "b", "v": 1}, {"id": "new", "v": 5}],
    "sparse_null_delete": [{"id": "b", "v": None}, {"id": "c"}],
    "orphan": [{"id": "c", "v": 2}],
    "reinsert": [{"id": "c", "v": 2}, {"id": "b", "v": 5}],
    "append_alias": [{"id": "b", "v": 5}, {"id": "c", "v": 2}, {"id": "b", "v": 5}],
    "reparent_alias": [{"id": "b", "v": 5}, {"id": "c", "v": 2}],
    "unauthorized_alias": [{"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "cycle_refusal": [{"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "custom_mutable_refusal": [{"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "numeric_dict": [{"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "initial_dict_alias": [{"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "initial_list_alias": [{"id": "b", "v": 5}, {"id": "c", "v": 2}, {"id": "new", "v": 3}],
    "initial_list_alias_pop": [{"id": "c", "v": 5}],
    "dict_reparent_alias": [{"id": "c", "v": 2}],
}


class _ListNode:
    def __init__(self, case):
        self.case = case
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.native_list_intent@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Live list journal consumer",
                description="Mutate actual list members after structural edits",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.x", "params.rows"]
            + (
                ["params.others"]
                if case in {"reparent_alias", "initial_list_alias", "initial_list_alias_pop"}
                else []
            ),
            state_writes=["params.rows"]
            + (
                ["params.others"]
                if case in {"reparent_alias", "initial_list_alias", "initial_list_alias_pop"}
                else []
            )
            + (["params.numeric"] if case == "numeric_dict" else [])
            + (["params.left", "params.right"] if case == "initial_dict_alias" else [])
            + (["params.slot"] if case == "dict_reparent_alias" else []),
        )

    def execute(self, ctx, state):
        raise AssertionError("Native async method required")

    async def execute_async(self, ctx, state):
        self.calls += 1
        journal = mutation_journal_for_state(state)
        assert journal is not None and journal.enforce_write_scope
        nested = branch_state(state, write_paths=self.spec.state_writes)
        assert nested.journal.enforce_write_scope
        rows = state.params["rows"]
        first, second = rows
        match self.case:
            case "no_shift":
                first["v"] = 5
            case "insert_existing":
                rows.insert(0, {"id": "new", "v": 0})
                first["v"] = 5
            case "insert_new":
                rows.insert(0, {"id": "new", "v": 0})
                rows[0]["v"] = 5
            case "pop_shift":
                rows.pop(0)
                second["v"] = 5
            case "remove_shift":
                rows.remove(first)
                second["v"] = 5
            case "delete_slice":
                del rows[:1]
                second["v"] = 5
            case "set_slice":
                rows[:1] = [{"id": "new", "v": 0}, {"id": "extra", "v": 0}]
                second["v"] = 5
            case "reverse":
                rows.reverse()
                first["v"] = 5
            case "sort":
                rows.sort(key=lambda row: row["id"], reverse=True)
                first["v"] = 5
            case "repeat_alias":
                rows *= 2
                first["v"] = 5
            case "negative_set":
                rows[-1] = {"id": "new", "v": 0}
                rows[-1]["v"] = 5
            case "sparse_null_delete":
                first["v"] = None
                del second["v"]
            case "orphan":
                removed = rows.pop(0)
                removed["v"] = 99
            case "reinsert":
                removed = rows.pop(0)
                rows.append(removed)
                assert rows[-1] is removed
                removed["v"] = 5
            case "append_alias":
                rows.append(first)
                assert rows[-1] is first
                first["v"] = 5
            case "reparent_alias":
                state.params["others"].append(first)
                assert state.params["others"][0] is first
                first["v"] = 5
            case "unauthorized_alias":
                before = state.model_dump(mode="json")
                with pytest.raises(ValueError, match="undeclared state_writes"):
                    state.params["neighbor_alias"] = first
                assert state.model_dump(mode="json") == before
            case "numeric_dict":
                state.params["numeric"]["0"]["v"] = 4
            case "initial_dict_alias":
                assert state.params["left"] is state.params["right"]
                state.params["left"]["v"] = 5
            case "initial_list_alias":
                assert rows is state.params["others"]
                rows.append({"id": "new", "v": 3})
                first["v"] = 5
            case "initial_list_alias_pop":
                assert rows is state.params["others"]
                rows.pop(0)
                second["v"] = 5
            case "dict_reparent_alias":
                removed = rows.pop(0)
                state.params["slot"] = removed
                assert state.params["slot"] is removed
                removed["v"] = 5
            case "custom_mutable_refusal":
                before = state.model_dump(mode="json")
                with pytest.raises(TypeError, match="finite JSON container graph"):
                    rows.append({1, 2})
                assert state.model_dump(mode="json") == before
            case "cycle_refusal":
                before = state.model_dump(mode="json")
                with pytest.raises(ValueError, match="cyclic state mutation"):
                    rows.append(rows)
                with pytest.raises(ValueError, match="cyclic state mutation"):
                    first["cycle"] = rows
                assert state.model_dump(mode="json") == before
        ref = ctx.store.put_json(
            {
                "case": self.case,
                "rows": rows,
                "others": state.params["others"],
                "aliases": {
                    key: state.params[key]
                    for key in ("left", "right", "slot")
                    if key in state.params
                },
            },
            PutOptions(kind="scientist.native_list_effect", media_type="application/json"),
        )
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


@pytest.mark.asyncio
@pytest.mark.parametrize("case", list(_CASES))
async def test_structural_list_intents_reopen_and_preserve_exact_native_rows(tmp_path, case):
    cas = tmp_path / "cas"
    store = FileSystemCAS(cas)
    bundle = build_default_registry_bundle(store).bundle_ref
    node = _ListNode(case)
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="native_list_ownership",
        nodes=[NodeInvocation(alias="list", node_id=node.spec.metadata.component_id)],
    )
    expected = _CASES[case]
    for warm in (False, True):
        reopened = FileSystemCAS(cas)
        run = RunContext.start(reopened, bundle, run_id="R_list_ownership")
        initial_rows = [{"id": "b", "v": 1}, {"id": "c", "v": 2}]
        shared_dict = {"v": 1}
        state = ExperimentState(
            run_id="R_list_ownership",
            params={
                "x": 2,
                "rows": initial_rows,
                "unrelated": "new" if warm else "old",
                "others": initial_rows if case == "initial_list_alias" else [],
                "numeric": {"0": {"v": 9}},
                **(
                    {"left": shared_dict, "right": shared_dict}
                    if case == "initial_dict_alias"
                    else {}
                ),
            },
            budgets={"neighbor_reserved_usd": Decimal("11") if warm else Decimal("7")},
        )
        # The DTO validates top-level dict/list values independently.  These
        # native assignments establish the actual supported in-memory aliases
        # before the executor branch, rather than assuming validation kept them.
        if case == "initial_dict_alias":
            state.params["left"] = state.params["right"] = shared_dict
            assert state.params["left"] is state.params["right"]
        if case in {"initial_list_alias", "initial_list_alias_pop"}:
            state.params["others"] = state.params["rows"]
            assert state.params["rows"] is state.params["others"]
        before = state.model_dump(mode="json")
        result = await AsyncWorkflowExecutor(
            ExecutionContext(store=reopened, run=run, logger=logging.getLogger("list-owner")),
            registry,
        ).execute(workflow, state)
        assert result.report.status == "ok"
        assert result.state.params["rows"] == expected
        expected_others = (
            expected
            if case in {"initial_list_alias", "initial_list_alias_pop"}
            else ([{"id": "b", "v": 5}] if case == "reparent_alias" else [])
        )
        expected_aliases = (
            {"left": {"v": 5}, "right": {"v": 5}}
            if case == "initial_dict_alias"
            else {"slot": {"id": "b", "v": 5}}
            if case == "dict_reparent_alias"
            else {}
        )
        assert result.state.params["others"] == expected_others
        assert "neighbor_alias" not in result.state.params
        assert result.state.params["numeric"] == {"0": {"v": 4 if case == "numeric_dict" else 9}}
        assert result.state.params["unrelated"] == state.params["unrelated"]
        assert (
            result.state.budgets["neighbor_reserved_usd"] == state.budgets["neighbor_reserved_usd"]
        )
        assert state.model_dump(mode="json") == before
        assert node.calls == 1
        effect = result.report.nodes[0].artifacts[0]
        assert reopened.verify(effect).ok
        assert json.loads(reopened.get_bytes(effect)) == {
            "case": case,
            "rows": expected,
            "others": expected_others,
            "aliases": expected_aliases,
        }
        assert reopened.verify(result.run_ref).ok
        records = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
        stores = [event for event in records if event["event"] == "NODE_CACHE_STORE"]
        assert len(stores) == 1
        cache_ref = ArtifactRef.model_validate(stores[0]["refs"]["outputs"][0])
        assert reopened.verify(cache_ref).ok
        entry = json.loads(reopened.get_bytes(cache_ref))
        assert entry["outcome_payload"]["state"]["params"]["rows"] == expected
        assert len([event for event in records if event["event"] == "NODE_CACHE_HIT"]) == int(warm)
        public_journal = mutation_journal_for_state(result.state)
        assert public_journal is None or not public_journal.enforce_write_scope
        before_cache_bytes = reopened.get_bytes(cache_ref)
        result.state.params["post"] = {"values": [3]}
        result.state.params["post"]["values"].append(4)
        public_ref = reopened.put_json(
            result.state.model_dump(mode="json"),
            PutOptions(kind="test.public_result", media_type="application/json"),
        )
        assert reopened.verify(public_ref).ok
        assert json.loads(reopened.get_bytes(public_ref))["params"]["post"] == {"values": [3, 4]}
        assert reopened.get_bytes(cache_ref) == before_cache_bytes


def test_narrow_list_descendant_refuses_structural_write_before_mutation(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    retained = store.put_json(
        {"evidence": "retained"}, PutOptions(kind="test", media_type="application/json")
    )
    state = ExperimentState(run_id="R_narrow", params={"rows": [{"v": 1}, {"v": 2}]})
    branch = branch_state(state, write_paths=["params.rows.0.v"], enforce_write_scope=True)
    branch_before = branch.state.model_dump(mode="json")
    base_before = state.model_dump(mode="json")
    evidence_before = store.get_bytes(retained)
    with pytest.raises(ValueError, match="undeclared state_writes"):
        branch.state.params["rows"].insert(0, {"v": 0})
    assert branch.state.model_dump(mode="json") == branch_before
    assert state.model_dump(mode="json") == base_before
    assert store.get_bytes(retained) == evidence_before
    assert store.verify(retained).ok
    assert branch.journal.operations == []
    branch.state.params["rows"][0]["v"] = 5
    assert branch.state.params["rows"][0]["v"] == 5
    assert state.params["rows"][0]["v"] == 1


@pytest.mark.parametrize("ordinal", [0, 1, 2, 3, 4])
def test_retained_actual_v1_list_journals_are_misses_and_scalar_intents_stay_readable(
    tmp_path, ordinal
):
    from pathlib import Path
    from types import SimpleNamespace

    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.scientist.orchestration.engine.executor import _merge_cached_outcome_state
    from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache

    retained = json.loads(
        (Path(__file__).parent / "fixtures/list-journal-v1-cache.json").read_text()
    )
    assert retained["producer_sha"] == "1bd1fd11b683bbade5411a71b02706ea206b149d"
    row = retained["cases"][ordinal]
    payload = row["payload_bytes"].encode()
    manifest = row["manifest"]
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind=manifest["kind"],
            media_type=manifest["media_type"],
            schema=SchemaInfo.model_validate(manifest["artifact_schema"]),
            producer=ProducerInfo.model_validate(manifest["producer"]),
        ),
    )
    assert ref == ArtifactRef.model_validate(row["cache_ref"])
    assert store.verify(ref).ok
    assert store.get_bytes(ref) == payload
    entry = json.loads(payload)
    assert entry["state_mutations_version"] == ("1.1" if ordinal == 3 else "1.0")
    reader = NodeResultCache(FileSystemCAS(store.root), entry["run_id"])
    admitted = reader.load_entry(ref)
    loaded = reader.get(entry["idempotency_key"])
    if ordinal in {0, 1, 3, 4}:
        assert not admitted
        assert loaded is None
        assert reader.size == 0
        assert store.get_bytes(ref) == payload
        return
    assert admitted
    assert loaded is not None
    node = SimpleNamespace(
        spec=_ListNode("no_shift").spec.model_copy(update={"state_writes": ["params"]})
    )
    current = ExperimentState(
        run_id=entry["run_id"],
        params={"x": 2, "y": 9, "stale": 1, "nullable": "current", "untouched": "new"},
        budgets={"neighbor_reserved_usd": Decimal("11")},
    )
    applied = _merge_cached_outcome_state(
        alias="producer", node=node, base_state=current, outcome=loaded
    )
    assert applied.params == {"x": 2, "y": 4, "nullable": None, "untouched": "new"}
    assert applied.budgets["neighbor_reserved_usd"] == Decimal("11")
    assert current.params["y"] == 9
    assert current.params["stale"] == 1


def test_initial_alias_and_nested_neighbor_refuse_before_changing_any_owned_bytes(tmp_path):
    shared = {"v": 1}
    state = ExperimentState(
        run_id="R_alias_scope",
        params={"owned": shared, "neighbor": shared, "separate": {"v": 2}},
    )
    state.params["owned"] = state.params["neighbor"] = shared
    store = FileSystemCAS(tmp_path / "cas")
    retained = store.put_json(
        state.model_dump(mode="json"), PutOptions(kind="test", media_type="application/json")
    )
    retained_bytes = store.get_bytes(retained)
    before = state.model_dump(mode="json")
    branch = branch_state(state, write_paths=["params.owned.v"], enforce_write_scope=True)
    assert branch.state.params["owned"] is branch.state.params["neighbor"]
    for key in ("owned", "neighbor", "separate"):
        with pytest.raises(ValueError, match="undeclared state_writes"):
            branch.state.params[key]["v"] = 5
        assert branch.state.model_dump(mode="json") == before
        assert state.model_dump(mode="json") == before
        assert store.get_bytes(retained) == retained_bytes
        assert store.verify(retained).ok
        assert branch.journal.operations == []


def test_initial_cycle_is_refused_before_branch_or_base_can_change():
    cyclic = []
    cyclic.append(cyclic)
    state = ExperimentState(run_id="R_cycle", params={"cyclic": cyclic})
    before = state.params["cyclic"]
    with pytest.raises(ValueError, match="cyclic state mutation"):
        branch_state(state, write_paths=["params"], enforce_write_scope=True)
    assert state.params["cyclic"] is before
    assert cyclic[0] is cyclic


def test_independent_branch_scope_is_neutral_but_nested_producer_inherits_guard():
    base = ExperimentState(run_id="R_lifetime", params={"owned": {"v": 1}, "other": {"v": 2}})
    neutral = branch_state(base, write_paths=["params.owned"])
    assert not neutral.journal.enforce_write_scope
    neutral.state.params["post"] = {"values": [3]}
    neutral.state.params["post"]["values"].append(4)
    assert neutral.state.params["post"] == {"values": [3, 4]}
    producer = branch_state(base, write_paths=["params.owned"], enforce_write_scope=True)
    nested = branch_state(producer.state, write_paths=["params.owned"])
    assert nested.journal.enforce_write_scope
    before = nested.state.model_dump(mode="json")
    with pytest.raises(ValueError, match="undeclared state_writes"):
        nested.state.params["other"]["v"] = 5
    assert nested.state.model_dump(mode="json") == before
    assert base.params["other"] == {"v": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["append", "pop"])
@pytest.mark.parametrize("current_alias", [True, False])
async def test_reopened_grouped_list_intents_preserve_current_rows_and_apply_once_per_target(
    tmp_path, operation, current_alias
):
    from polisyos.scientist.orchestration.engine.executor import _merge_cached_outcome_state
    from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache

    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store, bundle, run_id="R_list_ownership")
    node = _ListNode("initial_list_alias" if operation == "append" else "initial_list_alias_pop")
    registry = NodeRegistry()
    registry.register(node)
    state = ExperimentState(
        run_id="R_list_ownership",
        params={"x": 2, "rows": [{"id": "b", "v": 1}, {"id": "c", "v": 2}], "others": []},
    )
    state.params["others"] = state.params["rows"]
    assert state.params["rows"] is state.params["others"]
    result = await AsyncWorkflowExecutor(
        ExecutionContext(store=store, run=run, logger=logging.getLogger("grouped-list")), registry
    ).execute(
        WorkflowSpec(
            workflow_id="list_group",
            nodes=[NodeInvocation(alias="list", node_id=node.spec.metadata.component_id)],
        ),
        state,
    )
    assert result.report.status == "ok"
    records = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
    publication = next(event for event in records if event["event"] == "NODE_CACHE_STORE")
    ref = ArtifactRef.model_validate(publication["refs"]["outputs"][0])
    assert store.verify(ref).ok
    entry = json.loads(store.get_bytes(ref))
    groups = [
        mutation for mutation in entry["state_mutations"] if mutation["operation"] == operation
    ]
    assert len(groups) == 2
    assert groups[0]["operation_group"] == groups[1]["operation_group"]
    assert groups[0]["operation_group"] is not None
    expected = (
        [{"id": "b", "v": 5}, {"id": "c", "v": 2}, {"id": "current", "v": 9}, {"id": "new", "v": 3}]
        if operation == "append"
        else [{"id": "c", "v": 5}, {"id": "current", "v": 9}]
    )
    # This is replay into the state at merge time, which may include another
    # already-applied intent after the producer's read snapshot was captured.
    for profile in ("fresh", "reopened"):
        reader = NodeResultCache(FileSystemCAS(store.root), state.run_id)
        assert reader.load_entry(ref)
        outcome = reader.get(entry["idempotency_key"])
        assert outcome is not None
        current = ExperimentState(
            run_id=state.run_id,
            params={
                "x": 2,
                "rows": [{"id": "b", "v": 1}, {"id": "c", "v": 2}, {"id": "current", "v": 9}],
                "unrelated": "new",
            },
            budgets={"neighbor_reserved_usd": Decimal("11")},
        )
        current.params["others"] = (
            current.params["rows"]
            if current_alias
            else [dict(row) for row in current.params["rows"]]
        )
        assert (current.params["rows"] is current.params["others"]) is current_alias
        before = current.model_dump(mode="json")
        applied = _merge_cached_outcome_state(
            alias="list", node=node, base_state=current, outcome=outcome
        )
        assert applied.params["rows"] == applied.params["others"] == expected
        assert current.model_dump(mode="json") == before
        assert applied.params["unrelated"] == "new"
        assert applied.budgets["neighbor_reserved_usd"] == Decimal("11")
        physical = store.put_json(
            applied.model_dump(mode="json"),
            PutOptions(kind=f"test.grouped.{profile}", media_type="application/json"),
        )
        assert store.verify(physical).ok
        assert json.loads(store.get_bytes(physical))["params"]["rows"] == expected
        assert node.calls == 1
