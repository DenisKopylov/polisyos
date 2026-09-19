"""Regression tests for bounded state branching hot paths."""

from __future__ import annotations

from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state, snapshot_state


class _BranchNestedModel(BaseModel):
    items: list[str]
    untouched: dict[str, list[str]]


class _BranchHolderModel(BaseModel):
    nested: _BranchNestedModel


def _artifact_ref(tag: str = "a") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{tag * 64}",
        kind="test.ref",
        media_type="application/json",
    )


def test_branch_state_isolates_declared_nested_write_path() -> None:
    shared_payload = {"stable": ["keep-shared"]}
    base_state = ExperimentState(
        run_id="R_branch",
        params={
            "shared": shared_payload,
            "nested": {"items": ["base"]},
        },
    )

    branch = branch_state(
        base_state,
        write_paths=("params.nested.items",),
    )
    branch_state_value = branch.state

    assert branch_state_value.params is not base_state.params
    assert branch_state_value.params["nested"] is not base_state.params["nested"]
    assert branch_state_value.params["nested"]["items"] is not base_state.params["nested"]["items"]
    assert branch_state_value.params["shared"] is base_state.params["shared"]
    assert branch.journal.isolated_paths == ("params.nested.items",)

    branch_state_value.params["nested"]["items"].append("branch")
    branch_state_value.params["branch_only"] = True

    assert base_state.params["nested"]["items"] == ["base"]
    assert "branch_only" not in base_state.params


def test_branch_state_uses_copy_on_write_overlay_for_nested_pydantic_models() -> None:
    holder = _BranchHolderModel(
        nested=_BranchNestedModel(
            items=["base"],
            untouched={"shared": ["keep-shared"]},
        )
    )
    base_state = ExperimentState.model_construct(
        run_id="R_model_overlay",
        params={"holder": holder},
    )

    branch = branch_state(
        base_state,
        write_paths=("params.holder.nested.items",),
    )
    branch_state_value = branch.state
    branch_holder = branch_state_value.params["holder"]
    base_holder = base_state.params["holder"]

    assert isinstance(branch_holder, _BranchHolderModel)
    assert isinstance(base_holder, _BranchHolderModel)
    assert branch_holder is not base_holder
    assert branch_holder.nested is not base_holder.nested
    assert branch_holder.nested.items is not base_holder.nested.items
    assert branch_holder.nested.untouched is base_holder.nested.untouched

    branch_holder.nested.items.append("branch")

    assert base_holder.nested.items == ["base"]
    assert base_holder.nested.untouched == {"shared": ["keep-shared"]}


# Production mutation caught: a declared mutable leaf must be deeply isolated
# so edits to nested elements cannot leak into the base or a sibling branch.
def test_branch_state_deeply_isolates_nested_elements_of_declared_leaf() -> None:
    base_state = ExperimentState(
        run_id="R_nested_leaf",
        params={"config": {"rows": [{"value": "base"}]}},
    )

    branch = branch_state(
        base_state,
        write_paths=("params.config.rows",),
    ).state
    branch.params["config"]["rows"][0]["value"] = "branch"

    assert branch.params["config"]["rows"] == [{"value": "branch"}]
    assert base_state.params["config"]["rows"] == [{"value": "base"}]


# Production mutation caught: declared top-level scalar/ref writes must be
# installed as journaled setters instead of being silently unobservable.
def test_branch_state_records_top_level_scalar_ref_assignment() -> None:
    base_state = ExperimentState(run_id="R_top_level_ref")
    branch = branch_state(base_state, write_paths=("preflight_report_ref",))
    report_ref = _artifact_ref()

    branch.state.preflight_report_ref = report_ref

    assert [(item.path, item.operation) for item in branch.journal.operations] == [
        ("preflight_report_ref", "set"),
    ]
    assert branch.journal.operations[0].value == report_ref


def test_snapshot_state_deep_clones_mutable_state_surfaces() -> None:
    base_state = ExperimentState(
        run_id="R_snapshot",
        params={"nested": {"items": ["base"]}},
        causal_method_params={"method": {"thresholds": [0.1]}},
    )

    snapshot = snapshot_state(base_state)
    snapshot.params["nested"]["items"].append("snapshot")
    snapshot.causal_method_params["method"]["thresholds"].append(0.2)

    assert base_state.params["nested"]["items"] == ["base"]
    assert base_state.causal_method_params["method"]["thresholds"] == [0.1]
