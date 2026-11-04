"""Verify the optional candidate experiment bridge follows successful NL completion."""

from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.http.services.control.job_nl_execution import ControlNLJobExecutionMixin
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand


def _completion_service(
    *, templates: tuple[object, ...], tmp_path: Path
) -> tuple[Any, dict[str, Any]]:
    """Build the smallest service/context that exercises the production completion method."""
    state: dict[str, Any] = {"completion_calls": 0, "event_emitted": False}
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "not_established",
        "tenant_id": None,
        "cell_id": None,
        "actor_subject": None,
        "actor_authenticated": False,
        "actor_roles": [],
    }
    store.create_job(
        job_id="source-job",
        kind="natural_language_run",
        run_id="source-run",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref=None,
        payload_ref="sha256:fixture-payload",
        submitted_by=None,
        creation_event_payload={
            "job_id": "source-job",
            "run_id": "source-run",
            "job_kind": "natural_language_run",
            "pipeline_id": None,
            "payload_ref": "sha256:fixture-payload",
            "submitted_by": None,
            "requested_execution_profile": None,
            "effective_execution_profile": "dev",
            "policy_flags": {"candidate": True},
            "capability_manifest_ref": None,
            "execution_scope": scope,
        },
    )
    lease = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert lease is not None
    state["store"] = store
    state["lease"] = lease
    service = ControlNLJobExecutionMixin()
    service._registry_providers = SimpleNamespace(candidate_unpriced_policy_templates=templates)

    class ControlStore:
        def complete_job(self, **kwargs: Any) -> None:
            assert store.get_job("source-job").state == "running"
            assert kwargs["job_id"] == "source-job"
            state["completion_calls"] += 1
            store.complete_job(**kwargs)

        def get_job(self, job_id: str) -> Any:
            return store.get_job(job_id)

    def emit_diagnostic_event(**kwargs: Any) -> None:
        assert store.get_job("source-job").state == "completed"
        assert kwargs["job_id"] == "source-job"
        state["event_emitted"] = True

    artifact_ref = SimpleNamespace(
        artifact_id="compiled-artifact",
        model_dump=lambda **_: {"artifact_id": "compiled-artifact"},
    )
    service._control_store = ControlStore()
    service._completed_candidate_n5_output_refs = lambda _context, _compiled: ()
    service._put_json_artifact_ref = lambda *_args, **_kwargs: artifact_ref
    service._emit_runtime_diagnostic_event = emit_diagnostic_event

    context = SimpleNamespace(
        job=SimpleNamespace(
            job_id="source-job",
            run_id="source-run",
            effective_execution_profile="dev",
            kind="natural_language_run",
        ),
        payload={},
        execution_scope=SimpleNamespace(status="not_established", tenant_id=None, cell_id=None),
        capability_manifest_ref="capability-manifest",
        intent_band=ExecutionIntentBand.CANDIDATE_ONLY,
        core_run_id=None,
        core_run_context=None,
        cycle_substrate_context_job_ref=None,
        cycle_substrate_context_job_selected_ref=None,
    )
    compiled = SimpleNamespace(
        model_dump=lambda **_: {"status": "completed"}, recursive_budget_resolution=None
    )
    state["context"] = context
    state["compiled"] = compiled
    state["service"] = service
    return service, state


def _complete(service: Any, state: dict[str, Any]) -> None:
    """Run the production completion method under the store's real execution fence."""
    with state["store"].job_execution_fence(
        job_id="source-job", worker_id="worker-a", attempt=state["lease"].attempt
    ):
        service._complete_nl_simulation_result(state["context"], state["compiled"])


def test_empty_templates_skip_issuer_import(monkeypatch: Any, tmp_path: Path) -> None:
    service, state = _completion_service(templates=(), tmp_path=tmp_path)
    original_import = builtins.__import__
    issuer_imports: list[str] = []

    def track_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "polisyos.runtime.quality.candidate_experiment_policy_issuer":
            issuer_imports.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", track_import)
    _complete(service, state)

    assert state["store"].get_job("source-job").state == "completed"
    assert state["event_emitted"] is True
    assert issuer_imports == []


def test_configured_templates_call_issuer_after_completion_and_event(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    service, state = _completion_service(templates=(object(),), tmp_path=tmp_path)
    original_import = builtins.__import__
    observed: list[tuple[bool, bool, Any, str]] = []

    def issuer(*, control_service: Any, source_job_id: str) -> tuple[()]:
        observed.append(
            (
                state["store"].get_job("source-job").state == "completed",
                state["event_emitted"],
                control_service,
                source_job_id,
            )
        )
        return ()

    issuer_module = SimpleNamespace(prepare_candidate_experiment_policies_for_completed_job=issuer)

    def with_issuer_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "polisyos.runtime.quality.candidate_experiment_policy_issuer":
            return issuer_module
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", with_issuer_import)
    _complete(service, state)

    assert observed == [(True, True, service, "source-job")]
    assert state["completion_calls"] == 1


def test_issuer_exception_does_not_reopen_completed_job_or_repeat_nl_work(
    monkeypatch: Any,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    service, state = _completion_service(templates=(object(),), tmp_path=tmp_path)
    original_import = builtins.__import__
    issuer_calls = 0

    def issuer(*, control_service: Any, source_job_id: str) -> tuple[()]:
        nonlocal issuer_calls
        assert control_service is service
        assert source_job_id == "source-job"
        assert state["store"].get_job("source-job").state == "completed"
        assert state["event_emitted"] is True
        issuer_calls += 1
        raise RuntimeError("deliberately private failure detail")

    issuer_module = SimpleNamespace(prepare_candidate_experiment_policies_for_completed_job=issuer)

    def with_issuer_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "polisyos.runtime.quality.candidate_experiment_policy_issuer":
            return issuer_module
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", with_issuer_import)
    _complete(service, state)

    assert state["store"].get_job("source-job").state == "completed"
    assert state["completion_calls"] == 1
    assert state["event_emitted"] is True
    assert issuer_calls == 1
    assert "source-job" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "deliberately private failure detail" not in caplog.text
