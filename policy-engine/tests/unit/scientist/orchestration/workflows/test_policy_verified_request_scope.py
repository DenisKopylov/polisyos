"""The real verified-workflow wrapper preserves the caller's policy scope."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.scientist.nodes.builtins.planning.plan_policy_request import PlanPolicyRequestNode
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.workflows import builder
from polisyos.scientist.validation.policy_verified import load_policy_request_frame


@pytest.mark.parametrize("jurisdiction", [None, "synthetic"])
def test_verified_runner_passes_only_declared_scope_to_real_request_producer(
    tmp_path, monkeypatch, jurisdiction
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = store.put_json(
        {"synthetic": True},
        PutOptions(kind="core.registry_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    snapshot_ref = store.put_json(
        {"synthetic": True},
        PutOptions(kind="foundry.data_snapshot", media_type="application/json"),
        return_selected_profile=True,
    )
    params = {"policy_question": "Synthetic question?"}
    if jurisdiction is not None:
        params["policy_request_jurisdiction"] = jurisdiction
    state = ExperimentState(
        run_id=f"synthetic-runner-{jurisdiction}",
        inputs={"registry_bundle_ref": registry_ref, "data_snapshot_ref": snapshot_ref},
        params=params,
    )
    ctx = SimpleNamespace(
        store=store,
        run=SimpleNamespace(
            update_manifest=lambda **_: None, tenant_id="synthetic", cell_id="synthetic"
        ),
    )

    class RequestOnlyExecutor:
        def execute(self, _workflow, selected_state):
            return PlanPolicyRequestNode().execute(ctx, selected_state)

    monkeypatch.setattr(
        builder, "acquire_run_lock", lambda *_a, **_kw: SimpleNamespace(release=lambda: None)
    )
    monkeypatch.setattr(builder, "build_execution_context", lambda *_a, **_kw: ctx)
    monkeypatch.setattr(builder, "build_registry_with_builtin_nodes", lambda: object())
    monkeypatch.setattr(builder, "CASCheckpointHook", lambda *_a, **_kw: object())
    monkeypatch.setattr(builder, "WorkflowExecutor", lambda *_a, **_kw: RequestOnlyExecutor())
    outcome = builder.run_policy_verified_workflow(state, store=store, foundry=object())

    if jurisdiction is None:
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "policy_request_jurisdiction_not_established"
        assert outcome.state.policy_request_ref is None
    else:
        assert outcome.status == "ok" and outcome.state.policy_request_ref is not None
        assert (
            load_policy_request_frame(store, outcome.state.policy_request_ref).jurisdiction
            == jurisdiction
        )
    assert (
        "policy_request_jurisdiction" not in state.params
        if jurisdiction is None
        else state.params["policy_request_jurisdiction"] == jurisdiction
    )
