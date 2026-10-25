"""Declared parent-scope composition for policy projection branches."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    BuildPolicyOutputBundleNode,
)
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportNode,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _CURRENT_POLICY_PROJECTION_WRITE_PATHS,
    project_policy_promotion_state,
)
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)


def _policy_state() -> ExperimentState:
    return ExperimentState(
        run_id="policy-projection-parent-scope",
        params={"workflow_id": "scientist_policy_design"},
    )


def _write_an_extra_declared_path(state: ExperimentState, paths: list[str]) -> None:
    extra = next(
        (path for path in paths if path not in _CURRENT_POLICY_PROJECTION_WRITE_PATHS),
        paths[0],
    )
    parts = extra.split(".")
    if parts[0] == "params":
        state.params[parts[1]] = {"continued": True}
    elif parts[0] == "artifacts_index":
        state.artifacts_index[parts[1]] = ArtifactRef(
            artifact_id=ArtifactID("sha256:" + "a" * 64),
            kind="scientist.projection_scope_probe",
            media_type="application/json",
        )
    elif parts[0] == "reports_index":
        state.reports_index[parts[1]] = ArtifactRef(
            artifact_id=ArtifactID("sha256:" + "b" * 64),
            kind="scientist.projection_scope_probe",
            media_type="application/json",
        )
    else:
        setattr(
            state,
            parts[0],
            ArtifactRef(
                artifact_id=ArtifactID("sha256:" + "c" * 64),
                kind="scientist.projection_scope_probe",
                media_type="application/json",
            ),
        )


@pytest.mark.parametrize(
    "write_paths",
    [
        RunGovernanceNode().spec.state_writes,
        BuildVerifiedPolicyReportNode().spec.state_writes,
        BuildPolicyOutputBundleNode().spec.state_writes,
    ],
    ids=["run-governance", "verified-policy-report", "policy-output-bundle"],
)
def test_projection_child_can_continue_within_declared_parent_node_scope(
    write_paths: list[str],
) -> None:
    assert set(_CURRENT_POLICY_PROJECTION_WRITE_PATHS) <= set(write_paths)
    base = _policy_state()
    parent = branch_state(base, write_paths=write_paths, enforce_write_scope=True).state

    projected = project_policy_promotion_state(parent, branch_write_paths=write_paths)
    journal = mutation_journal_for_state(projected)
    assert journal is not None
    assert set(journal.isolated_paths) == set(write_paths)
    assert projected.params["policy_promotion_projection_status"]["status"] == "reported_only"

    continued = branch_state(projected, write_paths=write_paths).state
    _write_an_extra_declared_path(continued, write_paths)
    assert base.params == {"workflow_id": "scientist_policy_design"}


def test_projection_child_keeps_its_narrow_default_and_refuses_missing_parent_grant() -> None:
    default_projection = project_policy_promotion_state(_policy_state())
    default_journal = mutation_journal_for_state(default_projection)
    assert default_journal is not None
    assert set(default_journal.isolated_paths) == set(_CURRENT_POLICY_PROJECTION_WRITE_PATHS)

    narrow_parent = branch_state(
        _policy_state(),
        write_paths=("params.validation_trace",),
        enforce_write_scope=True,
    ).state
    with pytest.raises(ValueError, match="undeclared state_writes"):
        project_policy_promotion_state(
            narrow_parent,
            branch_write_paths=("params.validation_trace",),
        )


def test_default_projection_inherits_active_enforced_parent_scope() -> None:
    write_paths = RunGovernanceNode().spec.state_writes
    assert set(_CURRENT_POLICY_PROJECTION_WRITE_PATHS) <= set(write_paths)
    base = _policy_state()
    parent = branch_state(base, write_paths=write_paths, enforce_write_scope=True).state
    parent_journal = mutation_journal_for_state(parent)
    assert parent_journal is not None
    parent_paths = set(parent_journal.isolated_paths)
    parent_only_paths = parent_paths - set(_CURRENT_POLICY_PROJECTION_WRITE_PATHS)
    assert parent_only_paths

    projected = project_policy_promotion_state(parent)
    journal = mutation_journal_for_state(projected)
    assert journal is not None
    assert journal.enforce_write_scope is True
    assert set(journal.isolated_paths) == parent_paths
    assert parent_only_paths <= set(journal.isolated_paths)

    continued = branch_state(projected, write_paths=parent_journal.isolated_paths).state
    _write_an_extra_declared_path(continued, write_paths)
    assert base.params == {"workflow_id": "scientist_policy_design"}


def test_default_projection_cannot_expand_a_narrow_enforced_parent_scope() -> None:
    narrow_parent = branch_state(
        _policy_state(),
        write_paths=("params.validation_trace",),
        enforce_write_scope=True,
    ).state
    with pytest.raises(ValueError, match="undeclared state_writes"):
        project_policy_promotion_state(narrow_parent)
    with pytest.raises(
        ValueError, match="nested branch cannot broaden active producer write scope"
    ):
        project_policy_promotion_state(
            narrow_parent,
            branch_write_paths=_CURRENT_POLICY_PROJECTION_WRITE_PATHS,
        )


def test_nested_journal_descriptor_does_not_supply_projection_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import BaseModel

    from polisyos.scientist.nodes.builtins.decide import policy_runtime_support
    from polisyos.scientist.orchestration.engine.state_branching import StateMutationJournal

    descriptor_calls: list[bool] = []
    nested_journal = StateMutationJournal(
        isolated_fields=(),
        isolated_paths=(*_CURRENT_POLICY_PROJECTION_WRITE_PATHS, "params.validation_trace"),
        enforce_write_scope=True,
    )

    class NestedJournalProbe(BaseModel):
        @property
        def _polisyos_mutation_journal(self) -> StateMutationJournal:
            descriptor_calls.append(True)
            return nested_journal

    state = _policy_state()
    state.params["nested_journal_probe"] = NestedJournalProbe()
    real_branch_state = policy_runtime_support.branch_state
    calls_at_projector_branch: list[int] = []

    def _capture_branch_state(base_state, *, write_paths=(), enforce_write_scope=None):
        calls_at_projector_branch.append(len(descriptor_calls))
        return real_branch_state(
            base_state,
            write_paths=write_paths,
            enforce_write_scope=enforce_write_scope,
        )

    monkeypatch.setattr(policy_runtime_support, "branch_state", _capture_branch_state)
    projected = policy_runtime_support.project_policy_promotion_state(state)
    journal = mutation_journal_for_state(projected)

    assert calls_at_projector_branch == [0]
    assert journal is not None
    assert "params.validation_trace" not in journal.isolated_paths
    with pytest.raises(
        ValueError, match="nested branch cannot broaden active producer write scope"
    ):
        branch_state(projected, write_paths=("params.validation_trace",))
