"""Bounded checks for the server-sealed Control-to-Core DS9 run context."""

from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http import resource_binding
from polisyos.runtime.http.errors import RuntimeHTTPError


def probe_retained_control_run_owner(
    *,
    retained_root,
    control_run_id: str,
    control_job_id: str,
) -> dict[str, object]:
    """Exercise real retained-source binding and sealed reopen without DS9 creation."""
    import hashlib
    import json
    import os
    import sqlite3
    from pathlib import Path

    from fastapi import Request
    from fastapi.testclient import TestClient

    from polisyos.core.security import AccessScope, PIIAccessLevel, PolicyOSRole
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        principal_from_access_scope,
    )
    from polisyos.runtime.http.resource_binding import (
        _resolve_owned_run_for_binding,
        bind_authorization_resource,
        human_decision_create_owner_from_bound_request,
    )
    from polisyos.runtime.http.routes.human_decisions import (
        _CREATE_AUTHZ,
        HumanDecisionMutationRequest,
    )

    root = Path(retained_root).resolve(strict=True)
    cas_root = root / "cas"
    sqlite_path = root / ".polisyos" / "control_plane.sqlite3"
    if not cas_root.is_dir() or not sqlite_path.is_file():
        raise FileNotFoundError("retained source CAS or SQLite path is absent")

    env_names = (
        "POLISYOS_CONTROL_STATE_STORE_BACKEND",
        "POLISYOS_CONTROL_SQLITE_PATH",
        "POLISYOS_CONTROL_WORKER_BACKEND",
        "POLISYOS_EXECUTION_PROFILE",
    )
    previous_env = {name: os.environ.get(name) for name in env_names}

    def hashes(path: Path) -> dict[str, str]:
        return {
            str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
            for item in sorted(path.rglob("*"))
            if item.is_file()
        }

    def table_rows() -> dict[str, tuple[tuple[object, ...], ...]]:
        queries = {
            "control_jobs": "SELECT * FROM control_jobs",
            "control_job_events": "SELECT * FROM control_job_events",
            "control_pre_admission_attempt_events": (
                "SELECT * FROM control_pre_admission_attempt_events"
            ),
            "control_outbox_events": "SELECT * FROM control_outbox_events",
            "control_diagnostic_events": "SELECT * FROM control_diagnostic_events",
        }
        with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as connection:
            return {table: tuple(connection.execute(query)) for table, query in queries.items()}

    try:
        os.environ.update(
            {
                "POLISYOS_CONTROL_STATE_STORE_BACKEND": "sqlite",
                "POLISYOS_CONTROL_SQLITE_PATH": str(sqlite_path),
                "POLISYOS_CONTROL_WORKER_BACKEND": "external",
                "POLISYOS_EXECUTION_PROFILE": "dev",
            }
        )
        before_artifacts = hashes(cas_root / "artifacts")
        before_runs = hashes(cas_root / "runs")
        before_rows = table_rows()
        app = create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            authz_enforce=False,
            enable_security_middlewares=False,
        )
        with TestClient(app) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            ctx = container.runtime_api_context
            if control is None or ctx is None:
                raise AssertionError("runtime lifespan did not install canonical owners")
            if ctx.core_runs_root.resolve(strict=True) != (cas_root / "runs").resolve(strict=True):
                raise AssertionError("runtime context opened a different Core runs root")
            job = control._control_store.get_job(control_job_id)
            progress = getattr(job, "progress", {}) if job is not None else {}
            print(
                "retained_source_input="
                + json.dumps(
                    {
                        "control_run_id": control_run_id,
                        "control_job_id": control_job_id,
                        "job_found": job is not None,
                        "job_kind": getattr(job, "kind", None),
                        "job_state": getattr(job, "state", None),
                        "job_run_id": getattr(job, "run_id", None),
                        "attempt": getattr(job, "attempt", None),
                        "progress_core_run_id": progress.get("core_run_id"),
                        "progress_core_manifest_artifact_ref": progress.get(
                            "core_manifest_artifact_ref"
                        ),
                        "core_runs_root": str(ctx.core_runs_root),
                    },
                    sort_keys=True,
                )
            )
            if (
                job is None
                or job.kind != "natural_language_run"
                or job.state != "completed"
                or job.run_id != control_run_id
            ):
                raise AssertionError("retained completed Control source identity changed")
            historical_scope = control._control_store.historical_completed_job_execution_scope(
                job_id=control_job_id,
                expected_run_id=control_run_id,
            )
            print(
                "retained_source_scope="
                + json.dumps(
                    {
                        "status": historical_scope.status,
                        "actor_authenticated": historical_scope.actor_authenticated,
                        "tenant_id": historical_scope.tenant_id,
                        "cell_id": historical_scope.cell_id,
                    },
                    sort_keys=True,
                )
            )
            if (
                historical_scope.status != "established"
                or historical_scope.actor_authenticated is not True
                or not historical_scope.tenant_id
                or not historical_scope.cell_id
            ):
                raise AssertionError("retained completed source scope is not authenticated")
            scope = AccessScope(
                tenant_id=historical_scope.tenant_id,
                cell_id=historical_scope.cell_id,
                principal_type="user",
                user_sub="test-owned-binding-probe",
                roles=frozenset({PolicyOSRole.ANALYST}),
                max_pii_tier=PIIAccessLevel.HIGH,
                mfa_verified=True,
                jwt_jti="test-owned-binding-probe-jti",
            )
            subject, tenant, jwt_id, roles = principal_from_access_scope(scope)
            path = f"/api/v1/runs/{control_run_id}/human-decisions"
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "scheme": "http",
                    "server": ("testserver", 80),
                    "client": ("testclient", 50000),
                    "root_path": "",
                    "path": path,
                    "raw_path": path.encode(),
                    "query_string": b"",
                    "headers": [
                        (
                            b"x-policyos-human-decision-exposure",
                            ("sha256:" + "1" * 64).encode(),
                        )
                    ],
                    "path_params": {"run_id": control_run_id},
                    "app": client.app,
                }
            )
            request.state.authz_effective_scope = scope
            requirement = _CREATE_AUTHZ.requirement
            request.state.action_permission_verification = ActionPermissionVerification(
                requirement=requirement,
                subject=subject,
                tenant_id=tenant,
                jwt_id=jwt_id,
                roles=roles,
                authorization_source="test-owned-binding-component-probe",
                granted_permissions=(requirement.permission,),
            )
            mutation = HumanDecisionMutationRequest(
                source_kind="agent_action_authority",
                source_ref="sha256:" + "2" * 64,
                action_kind="runtime.evidence.acquisition.candidate_experiment.execute",
                action="approve",
                decision_mode="ordinary",
                accountability_statement="This component probe grants no DS9 decision.",
                dissent_statement="Only retained source ownership is under test.",
            )
            body_bytes = json.dumps(
                mutation.model_dump(mode="json", exclude_none=True),
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            resource_id, resource_tenant, source_binding = _resolve_owned_run_for_binding(
                request,
                ctx,
                scope,
                control_run_id,
            )
            print(
                "alias_resolution="
                + json.dumps(
                    {
                        "resource_id": resource_id,
                        "resource_tenant": resource_tenant,
                        "source_binding": (
                            source_binding.as_context() if source_binding is not None else None
                        ),
                    },
                    sort_keys=True,
                )
            )
            if source_binding is None:
                raise AssertionError("completed Control alias did not produce a source binding")
            if resource_id != control_run_id or resource_tenant != scope.tenant_id:
                raise AssertionError("binder normalized or changed the public Control run alias")
            bound = bind_authorization_resource(request, requirement, body_bytes)
            request.state.authz_bound_resource = bound
            context, reopened = human_decision_create_owner_from_bound_request(
                request,
                ctx=ctx,
                run_id=control_run_id,
            )
            owner = context.get("owned_run_binding")
            print(
                "sealed_owner_context="
                + json.dumps(
                    {
                        "context_keys": sorted(context),
                        "owned_run_binding": owner,
                        "bound_resource_digest": bound.resource_digest,
                        "reopened_run_id": reopened.run_id if reopened is not None else None,
                    },
                    sort_keys=True,
                )
            )
            expected_core_run_id = job.progress.get("core_run_id")
            expected_manifest_ref = job.progress.get("core_manifest_artifact_ref")
            if (
                not isinstance(owner, dict)
                or owner.get("control_run_id") != control_run_id
                or owner.get("core_run_id") != expected_core_run_id
                or owner.get("control_job_id") != control_job_id
                or owner.get("tenant_id") != scope.tenant_id
                or owner.get("cell_id") != scope.cell_id
                or owner.get("core_manifest_ref") != expected_manifest_ref
                or source_binding is None
                or reopened is None
                or reopened.run_id != expected_core_run_id
            ):
                raise AssertionError("sealed alias/Core owner facts differ from retained source")
            result = {
                "boundary": "ownership-resolution-only; no JWT/OPA/DS9 creation claim",
                "control_run_id": control_run_id,
                "core_run_id": owner["core_run_id"],
                "control_job_id": control_job_id,
                "tenant_id": owner["tenant_id"],
                "cell_id": owner["cell_id"],
                "core_manifest_ref": owner["core_manifest_ref"],
                "bound_resource_digest": bound.resource_digest,
                "retained_artifact_files": len(before_artifacts),
                "retained_core_run_files": len(before_runs),
                "retained_control_rows": sum(map(len, before_rows.values())),
            }
        if (
            hashes(cas_root / "artifacts") != before_artifacts
            or hashes(cas_root / "runs") != before_runs
            or table_rows() != before_rows
        ):
            raise AssertionError("owner probe changed retained CAS/Core/Control inputs")
    finally:
        for name, value in previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    result["preservation"] = "retained CAS, Core run files and five SQL tables unchanged"
    print(json.dumps(result, sort_keys=True))
    return result


def _binding() -> dict[str, object]:
    manifest_ref = artifacts.ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="core.run_manifest",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    return {
        "control_run_id": "R_control-alias",
        "core_run_id": "control-b0d37e26a07ece7bc3cb2447af8880dc6854136b14a4929a1dc6dff5b8935e0b",
        "control_job_id": "control-job-1",
        "tenant_id": "tenant-1",
        "cell_id": "cell-1",
        "core_manifest_ref": manifest_ref.model_dump(mode="json"),
    }


def test_control_alias_context_preserves_alias_and_exact_core_owner() -> None:
    binding = resource_binding._validate_owned_run_binding_context(
        _binding(), expected_control_run_id="R_control-alias"
    )

    assert binding.control_run_id == "R_control-alias"
    assert binding.core_run_id.startswith("control-b0d37e26")
    assert binding.control_run_id != binding.core_run_id
    assert binding.control_job_id == "control-job-1"
    assert binding.core_manifest_ref["kind"] == "core.run_manifest"


@pytest.mark.parametrize(
    "change",
    [
        {"control_run_id": "R_other-alias"},
        {"core_run_id": "control-other-core-run"},
        {"control_job_id": "control-other-job"},
        {"tenant_id": "tenant-other"},
        {"cell_id": "cell-other"},
        {"core_manifest_ref": None},
        {"unexpected": "caller-authored"},
    ],
)
def test_control_alias_context_rejects_changed_or_incomplete_owner(change, monkeypatch) -> None:
    binding = _binding()
    binding.update(change)

    resolved = resource_binding._validate_owned_run_binding_context(
        _binding(), expected_control_run_id="R_control-alias"
    )
    manifest_ref = artifacts.ArtifactRef.model_validate(resolved.core_manifest_ref)
    indexed = SimpleNamespace(
        run_id=resolved.core_run_id,
        details=SimpleNamespace(
            tenant_id=resolved.tenant_id,
            cell_id=resolved.cell_id,
            control_job_id=resolved.control_job_id,
            manifest_ref=manifest_ref,
        ),
    )

    class _RunIndex:
        def refresh(self, *, force: bool = False) -> None:
            assert force is True

        def get_run(self, run_id: str):
            if run_id != resolved.core_run_id:
                raise KeyError(run_id)
            return indexed

    monkeypatch.setattr(
        resource_binding,
        "_resolve_owned_run_for_binding",
        lambda _request, _ctx, current_scope, requested_run_id: (
            requested_run_id,
            current_scope.tenant_id,
            resolved,
        ),
    )

    with pytest.raises(RuntimeHTTPError):
        resource_binding._human_decision_create_control_alias_run_from_context(
            {"owned_run_binding": binding},
            request=object(),
            ctx=SimpleNamespace(run_index=_RunIndex()),
            scope=SimpleNamespace(tenant_id="tenant-1", cell_id="cell-1"),
            run_id="R_control-alias",
        )


def test_post_authorization_reopen_refuses_a_different_core_owner(monkeypatch) -> None:
    manifest_ref = artifacts.ArtifactRef.model_validate(_binding()["core_manifest_ref"])
    indexed = SimpleNamespace(
        run_id="control-other-core-run",
        details=SimpleNamespace(
            tenant_id="tenant-1",
            cell_id="cell-1",
            control_job_id="control-job-1",
            manifest_ref=manifest_ref,
        ),
    )

    class _RunIndex:
        def refresh(self, *, force: bool = False) -> None:
            assert force is True

        def get_run(self, run_id: str):
            assert run_id.startswith("control-b0d37e26")
            return indexed

    resolved = resource_binding._validate_owned_run_binding_context(
        _binding(), expected_control_run_id="R_control-alias"
    )
    monkeypatch.setattr(
        resource_binding,
        "_resolve_owned_run_for_binding",
        lambda _request, _ctx, current_scope, requested_run_id: (
            requested_run_id,
            current_scope.tenant_id,
            resolved,
        ),
    )

    with pytest.raises(RuntimeHTTPError):
        resource_binding._human_decision_create_control_alias_run_from_context(
            {"owned_run_binding": _binding()},
            request=object(),
            ctx=SimpleNamespace(run_index=_RunIndex()),
            scope=SimpleNamespace(tenant_id="tenant-1", cell_id="cell-1"),
            run_id="R_control-alias",
        )


def test_post_authorization_refuses_ambiguous_control_owner_swap(monkeypatch) -> None:
    control = _ControlOwner(job_error=ValueError("control_job_completion_ambiguous"))
    monkeypatch.setattr(resource_binding, "resolve_control_service", lambda _request: control)

    class _AliasMissIndex:
        def refresh(self, *, force: bool = False) -> None:
            assert force is True

        def get_run(self, run_id: str):
            assert run_id == "R_control-alias"
            raise KeyError(run_id)

    with pytest.raises(RuntimeHTTPError):
        resource_binding._human_decision_create_control_alias_run_from_context(
            {"owned_run_binding": _binding()},
            request=object(),
            ctx=SimpleNamespace(run_index=_AliasMissIndex()),
            scope=SimpleNamespace(tenant_id="tenant-1", cell_id="cell-1"),
            run_id="R_control-alias",
        )
    assert control.source_calls == 0


@pytest.mark.parametrize(
    "scope_change",
    [
        {"tenant_id": "tenant-other"},
        {"cell_id": "cell-other"},
        {"tenant_id": None},
        {"cell_id": None},
        {"actor_authenticated": False},
        {"status": "not_established"},
    ],
)
def test_control_alias_owner_scope_refusals(scope_change, monkeypatch) -> None:
    control = _ControlOwner(scope_change=scope_change)
    monkeypatch.setattr(resource_binding, "resolve_control_service", lambda _request: control)

    with pytest.raises(RuntimeHTTPError):
        resource_binding._resolve_completed_nl_control_alias(
            object(),
            SimpleNamespace(run_index=_UnusedRunIndex()),
            SimpleNamespace(tenant_id="tenant-1", cell_id="cell-1"),
            control_run_id="R_control-alias",
        )
    assert control.source_calls == 0


def test_control_alias_ambiguous_completed_job_refuses(monkeypatch) -> None:
    control = _ControlOwner(job_error=ValueError("control_job_completion_ambiguous"))
    monkeypatch.setattr(resource_binding, "resolve_control_service", lambda _request: control)

    with pytest.raises(RuntimeHTTPError):
        resource_binding._resolve_completed_nl_control_alias(
            object(),
            SimpleNamespace(run_index=_UnusedRunIndex()),
            SimpleNamespace(tenant_id="tenant-1", cell_id="cell-1"),
            control_run_id="R_control-alias",
        )
    assert control.source_calls == 0


@pytest.mark.parametrize("source_error", [ValueError("manifest missing"), None])
def test_control_alias_missing_or_changed_core_source_refuses(source_error, monkeypatch) -> None:
    control = _ControlOwner(source_error=source_error, missing_manifest=source_error is None)
    monkeypatch.setattr(resource_binding, "resolve_control_service", lambda _request: control)

    with pytest.raises(RuntimeHTTPError):
        resource_binding._resolve_completed_nl_control_alias(
            object(),
            SimpleNamespace(run_index=_SourceRunIndex(control.terminal)),
            SimpleNamespace(tenant_id="tenant-1", cell_id="cell-1"),
            control_run_id="R_control-alias",
        )


class _UnusedRunIndex:
    def refresh(self, *, force: bool = False) -> None:
        raise AssertionError("scope refusals must not inspect Core run rows")

    def get_run(self, _run_id: str):
        raise AssertionError("scope refusals must not inspect Core run rows")


class _SourceRunIndex:
    def __init__(self, terminal) -> None:
        self.terminal = terminal

    def refresh(self, *, force: bool = False) -> None:
        assert force is True

    def get_run(self, run_id: str):
        assert run_id == self.terminal.run_id
        return SimpleNamespace(
            run_id=run_id,
            details=SimpleNamespace(
                tenant_id=self.terminal.tenant_id,
                cell_id=self.terminal.cell_id,
                control_job_id=self.terminal.manifest.control_job_id,
                manifest_ref=self.terminal.manifest_ref,
            ),
        )


class _ControlOwner:
    """Refusal-boundary double; the real successful owner is covered by served integration."""

    def __init__(
        self,
        *,
        scope_change: dict[str, object] | None = None,
        job_error: Exception | None = None,
        source_error: Exception | None = None,
        missing_manifest: bool = False,
    ) -> None:
        self.job_error = job_error
        self.source_error = source_error
        self.missing_manifest = missing_manifest
        self.source_calls = 0
        self.job = SimpleNamespace(
            job_id="control-job-1",
            kind="natural_language_run",
            state="completed",
            run_id="R_control-alias",
        )
        self.scope = {
            "status": "established",
            "actor_authenticated": True,
            "tenant_id": "tenant-1",
            "cell_id": "cell-1",
            **(scope_change or {}),
        }
        self._control_store = self
        manifest_ref = None
        if not missing_manifest:
            manifest_ref = artifacts.ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="core.run_manifest",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "b" * 64,
            )
        self.terminal = SimpleNamespace(
            run_id="control-b0d37e26a07ece7bc3cb2447af8880dc6854136b14a4929a1dc6dff5b8935e0b",
            tenant_id="tenant-1",
            cell_id="cell-1",
            manifest=SimpleNamespace(
                run_id="control-b0d37e26a07ece7bc3cb2447af8880dc6854136b14a4929a1dc6dff5b8935e0b",
                control_job_id="control-job-1",
            ),
            manifest_ref=manifest_ref,
        )

    def get_unique_completed_job_by_run_and_kind(self, *, run_id: str, kind: str):
        assert run_id == "R_control-alias"
        assert kind == "natural_language_run"
        if self.job_error is not None:
            raise self.job_error
        return self.job

    def historical_completed_job_execution_scope(self, *, job_id: str, expected_run_id: str):
        assert job_id == "control-job-1"
        assert expected_run_id == "R_control-alias"
        return SimpleNamespace(**self.scope)

    def resolve_completed_control_job_core_run_source(self, *args, **kwargs):
        del args, kwargs
        self.source_calls += 1
        if self.source_error is not None:
            raise self.source_error
        return self.terminal
