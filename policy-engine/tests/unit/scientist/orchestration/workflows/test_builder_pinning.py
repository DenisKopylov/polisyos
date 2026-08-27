from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.workflows.builder import (
    _artifact_ref_or_none,
    _resolve_store,
    build_execution_context,
    run_causal_full_workflow,
    run_default_workflow,
    run_discovery_workflow,
    run_policy_design_workflow,
    run_policy_verified_workflow,
)


def _ref(seed: str, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{seed * 64}"),
        kind=kind,
        media_type="application/json",
    )


def _stub_execution_context() -> SimpleNamespace:
    """Return the minimum complete workflow context used by runner fixtures."""

    return SimpleNamespace(
        run=SimpleNamespace(
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            run_manifest=SimpleNamespace(),
        ),
        claim_ledger_owner=object(),
    )


def test_policy_workflow_rejects_mismatched_graph_prior_refs_before_execution(tmp_path) -> None:
    state = ExperimentState(
        run_id="R_policy_pin_mismatch",
        params={
            "policy_mode": True,
            "graph_prior_bundle_ref": _ref("1", "scientist.graph_prior_bundle").model_dump(
                mode="json"
            ),
        },
        inputs={
            INPUT_GRAPH_PRIOR_BUNDLE_REF: _ref("2", "scientist.graph_prior_bundle"),
        },
    )

    with pytest.raises(ValueError, match="graph_prior_bundle_ref"):
        run_policy_design_workflow(
            state,
            store=FileSystemCAS(tmp_path),
        )


@pytest.mark.parametrize(
    ("runner", "workflow_id"),
    [
        (run_default_workflow, "scientist_default"),
        (run_policy_verified_workflow, "scientist_policy_verified"),
    ],
)
def test_non_policy_workflows_reject_mismatched_registry_refs_before_execution(
    tmp_path,
    runner,
    workflow_id: str,
) -> None:
    state = ExperimentState(
        run_id=f"R_{workflow_id}",
        params={
            "registry_bundle_ref": _ref("1", "core.registry_bundle").model_dump(mode="json"),
        },
        inputs={
            INPUT_REGISTRY_BUNDLE_REF: _ref("2", "core.registry_bundle"),
        },
    )

    with pytest.raises(ValueError, match="registry_bundle_ref"):
        runner(
            state,
            store=FileSystemCAS(tmp_path),
        )


def test_default_workflow_accepts_injected_store_factory_and_quota_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    state = ExperimentState(run_id="R_provider_builder")
    store = FileSystemCAS(tmp_path)
    registry_bundle_ref = _ref("a", "core.registry_bundle")
    enforcer = MagicMock()
    quota_registry = SimpleNamespace(get_enforcer=lambda tenant_id: enforcer)
    store_factory = MagicMock(return_value=store)
    lock = SimpleNamespace(release=MagicMock())
    execution_result = MagicMock(report=MagicMock(status="ok"), state=state)
    executor = MagicMock()
    executor.execute.return_value = execution_result

    import polisyos.scientist.orchestration.workflows.builder as builder

    def _unexpected_quota_registry():
        raise AssertionError("global quota registry fallback should not run")

    monkeypatch.setattr(builder, "_build_quota_registry", _unexpected_quota_registry)
    monkeypatch.setattr(builder, "build_default_registry", lambda _store: registry_bundle_ref)
    monkeypatch.setattr(builder, "_ensure_snapshot_bind", lambda _state: None)
    monkeypatch.setattr(builder, "acquire_run_lock", lambda *args, **kwargs: lock)
    monkeypatch.setattr(
        builder,
        "build_execution_context",
        lambda *args, **kwargs: _stub_execution_context(),
    )
    monkeypatch.setattr(builder, "build_registry_with_builtin_nodes", lambda: object())
    monkeypatch.setattr(builder, "CASCheckpointHook", lambda *args, **kwargs: object())
    monkeypatch.setattr(builder, "WorkflowExecutor", lambda *args, **kwargs: executor)
    monkeypatch.setattr(builder, "default_workflow_spec", lambda: object())
    monkeypatch.setattr(builder, "get_current_tenant_id_or_none", lambda: "tenant-fixture")

    result = run_default_workflow(
        state,
        store_factory=store_factory,
        quota_registry=quota_registry,
        foundry=object(),
    )

    assert result is execution_result
    store_factory.assert_called_once_with()
    enforcer.check_run_start.assert_called_once_with()
    enforcer.record_run_start.assert_called_once_with()
    enforcer.record_run_end.assert_called_once_with()
    lock.release.assert_called_once_with()


def test_build_execution_context_uses_access_scope_tenant_when_tenant_scope_absent(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    access_scope = AccessScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        principal_type="user",
        user_sub="alice",
        roles=frozenset({PolicyOSRole.ADMIN}),
        max_pii_tier=PIIAccessLevel.NONE,
        mfa_verified=True,
    )

    token = set_current_access_scope(access_scope)
    try:
        ctx = build_execution_context(
            store,
            _ref("a", "core.registry_bundle"),
            run_id="R_access_scope_tenant",
        )
    finally:
        reset_current_access_scope(token)

    assert ctx.run.tenant_id == "tenant-a"
    assert ctx.run.cell_id == "cell-a"
    assert ctx.run.run_manifest.tenant_id == "tenant-a"
    assert ctx.run.run_manifest.cell_id == "cell-a"


def test_resolve_store_keeps_content_addressed_filesystem_cas_under_tenant_scope(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        resolved = _resolve_store(store)

    assert resolved is store


def test_resolve_store_keeps_guarded_content_addressed_filesystem_cas_under_tenant_scope(
    tmp_path,
) -> None:
    guarded_store = SimpleNamespace(_target=FileSystemCAS(tmp_path))

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        resolved = _resolve_store(guarded_store)

    assert resolved is guarded_store


def test_artifact_ref_or_none_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("artifact-ref-broken")

    import polisyos.scientist.orchestration.workflows.builder as builder

    monkeypatch.setattr(builder.ArtifactRef, "model_validate", _boom)

    with pytest.raises(AssertionError, match="artifact-ref-broken"):
        _artifact_ref_or_none({"artifact_id": "broken"})


@pytest.mark.parametrize(
    "runner",
    [
        run_default_workflow,
        run_policy_design_workflow,
        run_discovery_workflow,
        run_policy_verified_workflow,
        run_causal_full_workflow,
    ],
)
def test_workflow_runners_use_branch_local_snapshot_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    runner,
) -> None:
    state = ExperimentState(
        run_id="R_builder_snapshot",
        inputs={INPUT_REGISTRY_BUNDLE_REF: _ref("1", "core.registry_bundle")},
        params={"nested": {"value": "original"}},
    )
    execution_result = MagicMock(report=MagicMock(status="ok"))
    lock = SimpleNamespace(release=MagicMock())
    captured_state: dict[str, ExperimentState] = {}

    import polisyos.scientist.orchestration.workflows.builder as builder

    class _Executor:
        def execute(self, workflow, branch_state):
            del workflow
            captured_state["value"] = branch_state
            branch_state.params["mutated"] = True
            branch_state.params["nested"]["value"] = "updated"
            branch_state.inputs["branch_only"] = _ref("2", "scientist.test")
            return execution_result

    monkeypatch.setattr(builder, "_ensure_snapshot_bind", lambda _state: None)
    monkeypatch.setattr(builder, "acquire_run_lock", lambda *args, **kwargs: lock)
    monkeypatch.setattr(
        builder,
        "build_execution_context",
        lambda *args, **kwargs: _stub_execution_context(),
    )
    monkeypatch.setattr(builder, "build_registry_with_builtin_nodes", lambda: object())
    monkeypatch.setattr(builder, "CASCheckpointHook", lambda *args, **kwargs: object())
    monkeypatch.setattr(builder, "WorkflowExecutor", lambda *args, **kwargs: _Executor())
    monkeypatch.setattr(
        builder.WorkflowRunnerConfig,
        "from_env",
        staticmethod(lambda: SimpleNamespace(backend="local", max_parallelism=1)),
    )
    monkeypatch.setattr(builder, "default_workflow_spec", lambda: object())
    monkeypatch.setattr(builder, "policy_design_workflow_spec", lambda: object())
    monkeypatch.setattr(builder, "discovery_workflow_spec", lambda: object())
    monkeypatch.setattr(builder, "policy_verified_workflow_spec", lambda: object())
    monkeypatch.setattr(builder, "causal_full_workflow_spec", lambda: object())

    result = runner(state, store=FileSystemCAS(tmp_path), foundry=object())

    assert result is execution_result
    assert captured_state["value"] is not state
    assert state.params == {"nested": {"value": "original"}}
    assert state.inputs == {INPUT_REGISTRY_BUNDLE_REF: _ref("1", "core.registry_bundle")}
    assert captured_state["value"].params["nested"]["value"] == "updated"
    assert "branch_only" in captured_state["value"].inputs
    lock.release.assert_called_once_with()


def test_policy_workflow_requests_method_obligations_before_claim_drafting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    state = ExperimentState(
        run_id="R_policy_method_obligations",
        execution_profile="research",
        inputs={INPUT_REGISTRY_BUNDLE_REF: _ref("1", "core.registry_bundle")},
        params={
            "expected_method_expectations": [
                "distributional_evidence",
                "implementation_feasibility",
            ],
        },
    )
    store = FileSystemCAS(tmp_path)
    lock = SimpleNamespace(release=MagicMock())
    captured_state: dict[str, ExperimentState] = {}

    import polisyos.scientist.orchestration.workflows.builder as builder

    class _Executor:
        def execute(self, workflow, branch_state):
            del workflow
            captured_state["value"] = branch_state
            obligation_ref = branch_state.params["foundry_method_obligation_report_ref"]
            assert isinstance(obligation_ref, str)
            assert obligation_ref.startswith("sha256:")
            assert branch_state.params["foundry_method_obligations_requested_before_claims"] is True
            assert branch_state.params["foundry_method_obligation_report_status"] == "fail"
            assert branch_state.params[
                "foundry_method_obligation_expected_method_expectations"
            ] == [
                "distributional_evidence",
                "implementation_feasibility",
            ]
            assert branch_state.params["foundry_method_obligation_report_blocking_issue_count"] > 0
            assert (
                str(branch_state.reports_index["foundry_method_obligation_report"].artifact_id)
                == obligation_ref
            )
            return SimpleNamespace(report=MagicMock(status="ok"), state=branch_state)

    monkeypatch.setattr(builder, "_ensure_snapshot_bind", lambda _state: None)
    monkeypatch.setattr(builder, "acquire_run_lock", lambda *args, **kwargs: lock)
    monkeypatch.setattr(
        builder,
        "build_execution_context",
        lambda *args, **kwargs: _stub_execution_context(),
    )
    monkeypatch.setattr(builder, "build_registry_with_builtin_nodes", lambda: object())
    monkeypatch.setattr(builder, "CASCheckpointHook", lambda *args, **kwargs: object())
    monkeypatch.setattr(builder, "WorkflowExecutor", lambda *args, **kwargs: _Executor())
    monkeypatch.setattr(builder, "policy_design_workflow_spec", lambda: object())

    result = run_policy_design_workflow(
        state,
        store=store,
        foundry=object(),
    )

    assert result.state is captured_state["value"]
    assert "foundry_method_report_ref" in result.state.params
    lock.release.assert_called_once_with()
