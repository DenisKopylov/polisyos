from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi import Depends, FastAPI
    from fastapi.routing import APIRoute
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)


_HIGH_STAKES_OPERATIONS = {
    ("POST", "/api/v1/control/data/ingest"): "acquisition_approval",
    (
        "POST",
        "/api/v1/control/data/promotion/{promotion_id}/approve",
    ): "promotion",
    (
        "POST",
        "/api/v1/control/data/promotion/{promotion_id}/reject",
    ): "promotion",
    ("POST", "/api/v1/control/decision-validity/events"): "publication",
    ("POST", "/api/v1/control/runs/{run_id}/reissue"): "revocation",
    (
        "POST",
        "/api/v1/runs/{run_id}/production-approval",
    ): "production_approval",
    ("POST", "/api/v1/runs/{run_id}/human-decisions"): "human_decision",
}


def test_step_up_vocabulary_includes_human_decision_as_a_distinct_class() -> None:
    from polisyos.runtime.http.step_up import (
        HIGH_STAKES_PERMISSION_CLASSES,
        StepUpClass,
    )

    assert {member.value for member in StepUpClass} == {
        "promotion",
        "production_approval",
        "publication",
        "revocation",
        "acquisition_approval",
        "human_decision",
    }
    assert {
        permission.value: step_up_class.value
        for permission, step_up_class in HIGH_STAKES_PERMISSION_CLASSES.items()
    } == {
        "evidence.acquire": "acquisition_approval",
        "evidence.promotions.approve": "promotion",
        "evidence.promotions.reject": "promotion",
        "decisions.validity.publish": "publication",
        "runs.reissue": "revocation",
        "runs.production_approval.create": "production_approval",
        "runs.human_decisions.create": "human_decision",
    }


def test_human_decision_openapi_projects_distinct_step_up_class(runtime_api_env) -> None:
    schema = runtime_api_env["app"].openapi()

    operation = schema["paths"]["/api/v1/runs/{run_id}/human-decisions"]["post"]

    assert operation["x-polisyos-step-up-class"] == "human_decision"


def test_human_decision_requires_fresh_single_use_step_up(
    runtime_api_env,
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.http.step_up import StepUpAssertionVerification
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    now = int(time.time())

    class _Verifier:
        def verify(self, encoded_assertion: str, verification_context):
            assert encoded_assertion == "signed-human-decision-step-up"
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id="human-decision-single-use-jti",
                issuer="https://step-up.example",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    bearer = _fixture_bearer("human-decision-single-use")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-human-decision-single-use",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    existing_security = client.app.state.runtime_security
    assert isinstance(existing_security, RuntimeSecurityConfig)
    configured = replace(
        existing_security,
        step_up_verifier=_Verifier(),
        step_up_replay_store=ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "human-decision-step-up.sqlite3",
        ),
    )
    client.app.state.runtime_security = configured
    client.app.state.runtime_container.runtime_security = configured
    digest = "sha256:" + "a" * 64
    body = {
        "source_kind": "production_approval",
        "source_ref": digest,
        "decision_request_ref": digest,
        "decision_request_digest": digest,
        "basis_ref": digest,
        "basis_digest": digest,
        "action": "approve",
        "decision_mode": "ordinary",
        "accountability_statement": "I accept accountability for this exact action.",
        "dissent_statement": "No dissent was recorded.",
    }
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
        "X-PolicyOS-Step-Up": "signed-human-decision-step-up",
        "X-PolicyOS-Human-Decision-Exposure": "signed-exposure-session",
    }
    store = FileSystemCAS(runtime_api_env["cas_root"])

    def _record_ids() -> set[str]:
        return {
            str(artifact_id)
            for artifact_id in store.iter_artifact_ids()
            if store.get_manifest(artifact_id).kind == "runtime_quality.agent_action_human_decision"
        }

    before = _record_ids()
    first = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/human-decisions",
        headers=headers,
        json=body,
    )
    replay = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/human-decisions",
        headers=headers,
        json=body,
    )

    assert first.status_code == 503, first.text
    assert first.json()["code"] == "human_decision_service_unavailable"
    assert not str(first.json().get("code", "")).startswith("step_up_")
    assert replay.status_code == 403, replay.text
    assert replay.json()["code"] == "step_up_replayed"
    assert _record_ids() == before


def _dependency_calls(node: Any) -> Iterator[object]:
    for child in node.dependencies:
        yield child.call
        yield from _dependency_calls(child)


def _production_approval_test_context(
    runtime_api_env,
    *,
    suffix: str,
    opa_client: object | None = None,
    mfa_verified: bool = True,
) -> dict[str, Any]:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.security.identity import PolicyOSRole
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_payload = {
        "schema_version": "policyos.quality_scorecard.v1",
        "run_id": runtime_api_env["core_run_id"],
        "quality_status": "pass",
        "performance_status": "pass",
        "conflict_status": "pass",
        "approval_state": "approval_ready",
        "quality_gates": [],
        "evidence_refs": {},
    }
    scorecard_ref = store.put_json(
        scorecard_payload,
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    bearer = _fixture_bearer(suffix)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa_client if opa_client is not None else _AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.step_up",
    )
    claims = _claims(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        jti=f"jwt-{suffix}",
        roles=frozenset({PolicyOSRole.ADMIN}),
    )
    provider.put_claim(
        bearer,
        claims.model_copy(update={"mfa_verified": mfa_verified}),
    )
    return {
        "bearer": bearer,
        "client": client,
        "scorecard_ref": str(scorecard_ref.artifact_id),
        "scorecard_payload": scorecard_payload,
        "store": store,
    }


def _step_up_context():
    from polisyos.runtime.http.step_up import (
        StepUpClass,
        StepUpVerificationContext,
    )

    return StepUpVerificationContext(
        subject="user-1",
        tenant_id="tenant-a",
        method="POST",
        route_path="/api/v1/control/data/ingest",
        permission="evidence.acquire",
        resource_id="urn:polisyos:authorization-binding:v1:0123456789abcdef",
        resource_digest="sha256:" + "1" * 64,
        resource_kind="runtime.evidence.ingest.tenant_collection",
        binding_authority="tenant_collection",
        body_sha256="sha256:" + "2" * 64,
        step_up_class=StepUpClass.ACQUISITION_APPROVAL,
        scorecard_ref=None,
        scorecard_sha256=None,
    )


def _signed_step_up_token(
    context,
    *,
    issued_at: int,
    expires_at: int,
    assertion_id: str = "step-up-jti-1",
    permission: str | None = None,
    resource_digest: str | None = None,
    claim_overrides: dict[str, object] | None = None,
    signing_key: str = "ds20-test-step-up-key-with-at-least-32-bytes",
) -> str:
    pyjwt = pytest.importorskip("jwt")
    payload: dict[str, object] = {
        "iss": "https://step-up.example",
        "aud": "polisyos-runtime-step-up",
        "sub": context.subject,
        "tenant_id": context.tenant_id,
        "method": context.method,
        "route": context.route_path,
        "permission": permission or context.permission,
        "resource_id": context.resource_id,
        "resource_digest": resource_digest or context.resource_digest,
        "resource_kind": context.resource_kind,
        "binding_authority": context.binding_authority,
        "body_sha256": context.body_sha256,
        "step_up_class": context.step_up_class.value,
        "scorecard_ref": context.scorecard_ref,
        "scorecard_sha256": context.scorecard_sha256,
        "mfa_verified": True,
        "assurance": "fresh_mfa",
        "iat": issued_at,
        "exp": expires_at,
        "jti": assertion_id,
    }
    payload.update(claim_overrides or {})
    return pyjwt.encode(
        payload,
        signing_key,
        algorithm="HS256",
        headers={"kid": "ds20-test-key"},
    )


def _jwt_step_up_verifier(*, now: int):
    from polisyos.runtime.http.step_up import JWTStepUpAssertionVerifier

    return JWTStepUpAssertionVerifier(
        issuer="https://step-up.example",
        audience="polisyos-runtime-step-up",
        verification_key="ds20-test-step-up-key-with-at-least-32-bytes",
        algorithms=("HS256",),
        allowed_key_ids=frozenset({"ds20-test-key"}),
        maximum_age_seconds=300,
        clock_skew_seconds=10,
        clock=lambda: float(now),
    )


def test_high_stakes_routes_have_exactly_one_distinct_step_up_dependency(
    runtime_api_env,
) -> None:
    app = runtime_api_env["app"]
    actual: dict[tuple[str, str], str] = {}

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in set(route.methods) & {"POST", "PUT", "PATCH", "DELETE"}:
            key = (method, route.path)
            if key not in _HIGH_STAKES_OPERATIONS:
                continue
            step_up_calls = [
                call
                for call in _dependency_calls(route.dependant)
                if getattr(call, "__polisyos_step_up__", None) is not None
            ]
            assert len(step_up_calls) == 1, key
            step_up_class = step_up_calls[0].__polisyos_step_up__.step_up_class
            actual[key] = step_up_class.value

    assert actual == _HIGH_STAKES_OPERATIONS


def test_live_app_passes_high_stakes_step_up_contract(runtime_api_env) -> None:
    from polisyos.runtime.http import step_up

    gate = getattr(step_up, "assert_high_stakes_step_up_contract", None)
    assert callable(gate)
    gate(runtime_api_env["app"])


def test_replaced_route_app_cannot_bypass_executable_step_up_dependency(
    runtime_api_env,
) -> None:
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.authorization import (
        ResourceBindingSource,
        ResourceBindingSpec,
        require_action_permission,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.step_up import StepUpClass, require_step_up
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    action = require_action_permission(
        RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.replaced_route_app",
        ),
    )
    step_up = require_step_up(StepUpClass.PROMOTION)
    bearer = _fixture_bearer("replaced-route-app-step-up")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-replaced-route-app-step-up",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    app = client.app

    @app.post(
        "/api/v1/ds20/replaced-route-app-step-up",
        dependencies=[Depends(action), Depends(step_up)],
    )
    def _declared_handler() -> dict[str, bool]:
        raise AssertionError("the replaced route app must own this probe")

    route = next(
        candidate
        for candidate in app.routes
        if isinstance(candidate, APIRoute)
        and candidate.path == "/api/v1/ds20/replaced-route-app-step-up"
    )
    mutation_receipts: list[str] = []

    async def _replacement_route_app(scope, receive, send) -> None:
        del scope, receive
        mutation_receipts.append("mutated")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"mutated":true}',
            }
        )

    route.app = _replacement_route_app

    response = client.post(
        "/api/v1/ds20/replaced-route-app-step-up",
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "step_up_required"
    assert mutation_receipts == []


def test_openapi_projects_exact_high_stakes_step_up_classes(runtime_api_env) -> None:
    schema = runtime_api_env["app"].openapi()
    projected: dict[tuple[str, str], str] = {}

    for path, path_item in schema["paths"].items():
        for method in ("post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            step_up_class = operation.get("x-polisyos-step-up-class")
            if step_up_class is not None:
                projected[(method.upper(), path)] = step_up_class

    assert projected == _HIGH_STAKES_OPERATIONS


@pytest.mark.parametrize(
    "declaration_case",
    ["missing", "duplicate", "mismatched", "marker_only", "misordered"],
)
def test_high_stakes_step_up_contract_rejects_invalid_declaration(
    declaration_case: str,
) -> None:
    from polisyos.runtime.http.authorization import (
        ResourceBindingSource,
        ResourceBindingSpec,
        require_action_permission,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.step_up import (
        StepUpClass,
        StepUpRequirement,
        assert_high_stakes_step_up_contract,
        require_step_up,
    )

    action = require_action_permission(
        RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.step_up_contract",
        ),
    )
    correct = require_step_up(StepUpClass.PRODUCTION_APPROVAL)
    wrong = require_step_up(StepUpClass.PROMOTION)

    class _MarkerOnly:
        __polisyos_step_up__ = StepUpRequirement(StepUpClass.PRODUCTION_APPROVAL)

        def __call__(self) -> None:
            return None

    declarations: dict[str, list[Any]] = {
        "missing": [Depends(action)],
        "duplicate": [Depends(action), Depends(correct), Depends(correct)],
        "mismatched": [Depends(action), Depends(wrong)],
        "marker_only": [Depends(action), Depends(_MarkerOnly())],
        "misordered": [Depends(correct), Depends(action)],
    }
    app = FastAPI()

    @app.post(
        f"/ds20/step-up-contract/{declaration_case}",
        dependencies=declarations[declaration_case],
    )
    def _probe() -> dict[str, bool]:
        return {"mutated": True}

    with pytest.raises(RuntimeError, match="step-up"):
        assert_high_stakes_step_up_contract(app)


def test_step_up_dependency_cannot_replace_action_permission_dependency() -> None:
    from polisyos.runtime.http.authorization import (
        assert_mutating_route_authorization_contract,
    )
    from polisyos.runtime.http.step_up import StepUpClass, require_step_up

    app = FastAPI()

    @app.post(
        "/ds20/step-up-without-action",
        dependencies=[Depends(require_step_up(StepUpClass.PUBLICATION))],
    )
    def _probe() -> dict[str, bool]:
        return {"mutated": True}

    with pytest.raises(RuntimeError, match="ActionPermissionDependency"):
        assert_mutating_route_authorization_contract(app)


def test_runtime_app_construction_executes_high_stakes_step_up_gate(
    monkeypatch: pytest.MonkeyPatch,
    runtime_api_env,
) -> None:
    import polisyos.runtime.http.app as app_module

    inspected: list[object] = []

    def _capture_gate(app: object) -> None:
        inspected.append(app)

    monkeypatch.setattr(
        app_module,
        "assert_high_stakes_step_up_contract",
        _capture_gate,
        raising=False,
    )

    app = app_module.create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        allow_fixture_identity=True,
    )

    assert inspected == [app]


def test_high_stakes_action_permission_without_step_up_is_denied(
    runtime_api_env,
) -> None:
    context = _production_approval_test_context(
        runtime_api_env,
        suffix="missing-step-up",
    )
    store = context["store"]
    packets_before = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={"quality_scorecard_ref": context["scorecard_ref"]},
    )
    packets_after = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "step_up_required"
    assert packets_after == packets_before


def test_missing_step_up_verifier_fails_closed(runtime_api_env) -> None:
    context = _production_approval_test_context(
        runtime_api_env,
        suffix="missing-step-up-verifier",
    )
    store = context["store"]
    packets_before = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": "signed-but-unverifiable",
        },
        json={"quality_scorecard_ref": context["scorecard_ref"]},
    )
    packets_after = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "step_up_verifier_unavailable"
    assert packets_after == packets_before


def test_missing_step_up_replay_store_fails_closed(runtime_api_env) -> None:
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    context = _production_approval_test_context(
        runtime_api_env,
        suffix="missing-step-up-replay-store",
    )
    now = int(time.time())

    class _Verifier:
        def verify(self, encoded_assertion: str, verification_context):
            assert encoded_assertion == "externally-signed-step-up"
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id="missing-replay-store-jti",
                issuer="https://step-up.example",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    security = context["client"].app.state.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    context["client"].app.state.runtime_security = replace(
        security,
        step_up_verifier=_Verifier(),
        step_up_replay_store=None,
    )

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": "externally-signed-step-up",
        },
        json={"quality_scorecard_ref": context["scorecard_ref"]},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "step_up_replay_store_unavailable"


@pytest.mark.parametrize(
    ("failure_case", "expected_code"),
    [
        ("verifier_exception", "step_up_verifier_failed"),
        ("invalid_verifier_proof", "step_up_verifier_contract_invalid"),
        ("replay_store_exception", "step_up_replay_store_failed"),
    ],
)
def test_step_up_collaborator_failures_deny_before_mutation(
    runtime_api_env,
    failure_case: str,
    expected_code: str,
) -> None:
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    context = _production_approval_test_context(
        runtime_api_env,
        suffix=f"collaborator-failure-{failure_case}",
    )
    now = int(time.time())
    verifier_calls: list[str] = []
    replay_calls: list[str] = []

    class _Verifier:
        def verify(self, encoded_assertion: str, verification_context):
            verifier_calls.append(encoded_assertion)
            if failure_case == "verifier_exception":
                raise OSError("external verifier unavailable")
            if failure_case == "invalid_verifier_proof":
                return object()
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id=f"collaborator-failure-{failure_case}-jti",
                issuer="https://step-up.example",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    class _ReplayStore:
        def consume_step_up_assertion(self, *, assertion_id: str, expires_at: int) -> bool:
            del expires_at
            replay_calls.append(assertion_id)
            raise OSError("durable replay store unavailable")

    security = context["client"].app.state.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    context["client"].app.state.runtime_security = replace(
        security,
        step_up_verifier=_Verifier(),
        step_up_replay_store=_ReplayStore(),
    )
    packets_before = {
        str(artifact_id)
        for artifact_id in context["store"].iter_artifact_ids()
        if context["store"].get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": "collaborator-failure-step-up",
        },
        json={"quality_scorecard_ref": context["scorecard_ref"]},
    )
    packets_after = {
        str(artifact_id)
        for artifact_id in context["store"].iter_artifact_ids()
        if context["store"].get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == expected_code
    assert verifier_calls == ["collaborator-failure-step-up"]
    assert replay_calls == (
        [f"collaborator-failure-{failure_case}-jti"]
        if failure_case == "replay_store_exception"
        else []
    )
    assert packets_after == packets_before


def test_user_without_base_mfa_cannot_satisfy_human_step_up_class(
    runtime_api_env,
) -> None:
    from polisyos.runtime.http.security import RuntimeSecurityConfig

    context = _production_approval_test_context(
        runtime_api_env,
        suffix="base-mfa-required",
        mfa_verified=False,
    )
    verifier_calls: list[str] = []
    replay_calls: list[str] = []

    class _Verifier:
        def verify(self, encoded_assertion: str, verification_context):
            del verification_context
            verifier_calls.append(encoded_assertion)
            raise AssertionError("base-MFA denial must precede assertion verification")

    class _ReplayStore:
        def consume_step_up_assertion(self, *, assertion_id: str, expires_at: int) -> bool:
            del expires_at
            replay_calls.append(assertion_id)
            raise AssertionError("base-MFA denial must precede replay consumption")

    security = context["client"].app.state.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    context["client"].app.state.runtime_security = replace(
        security,
        step_up_verifier=_Verifier(),
        step_up_replay_store=_ReplayStore(),
    )

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": "must-not-reach-verifier",
        },
        json={"quality_scorecard_ref": context["scorecard_ref"]},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "step_up_base_mfa_required"
    assert verifier_calls == []
    assert replay_calls == []


def test_production_profile_requires_configured_step_up_verifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "production")

    with pytest.raises(RuntimeBootstrapError, match="step-up assertion verifier"):
        create_runtime_api_app(cas_root=tmp_path / ".polisyos")


def test_valid_signed_step_up_assertion_verifies_exact_context() -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        assertion_id="valid-signed-step-up-jti",
    )

    verification = _jwt_step_up_verifier(now=now).verify(token, context)

    assert type(verification) is StepUpAssertionVerification
    assert verification.context == context
    assert verification.assertion_id == "valid-signed-step-up-jti"
    assert verification.issuer == "https://step-up.example"
    assert verification.audience == "polisyos-runtime-step-up"
    assert verification.assurance == "fresh_mfa"


@pytest.mark.parametrize(
    ("case", "claim_overrides", "signing_key", "error_code"),
    [
        (
            "invalid_signature",
            {},
            "different-ds20-step-up-signing-key-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "wrong_issuer",
            {"iss": "https://attacker.invalid"},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "wrong_audience",
            {"aud": "different-runtime"},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "multi_audience_expected_first",
            {"aud": ["polisyos-runtime-step-up", "other-service"]},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "multi_audience_expected_second",
            {"aud": ["other-service", "polisyos-runtime-step-up"]},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "mfa_not_verified",
            {"mfa_verified": False},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_assurance_required",
        ),
        (
            "assurance_missing",
            {"assurance": ""},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_assurance_required",
        ),
        (
            "expired",
            {"iat": 1_799_999_900, "exp": 1_799_999_989},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_expired",
        ),
    ],
)
def test_signed_step_up_assertion_fails_closed_for_invalid_authenticity_or_assurance(
    case: str,
    claim_overrides: dict[str, object],
    signing_key: str,
    error_code: str,
) -> None:
    del case
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides=claim_overrides,
        signing_key=signing_key,
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == error_code


@pytest.mark.parametrize(
    ("claim_name", "wrong_value"),
    [
        ("sub", "different-subject"),
        ("tenant_id", "different-tenant"),
        ("method", "DELETE"),
        ("route", "/api/v1/different-route"),
        ("permission", "runs.launch"),
        ("resource_id", "urn:polisyos:different-resource"),
        ("resource_digest", "sha256:" + "9" * 64),
        ("resource_kind", "runtime.different-kind"),
        ("binding_authority", "request_composite"),
        ("body_sha256", "sha256:" + "8" * 64),
        ("step_up_class", "publication"),
    ],
)
def test_signed_step_up_assertion_denies_every_mismatched_request_binding(
    claim_name: str,
    wrong_value: str,
) -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides={claim_name: wrong_value},
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == "step_up_binding_mismatch"


@pytest.mark.parametrize("claim_name", ["scorecard_ref", "scorecard_sha256"])
def test_signed_production_approval_denies_mismatched_scorecard_binding(
    claim_name: str,
) -> None:
    from dataclasses import replace as replace_dataclass

    from polisyos.runtime.http.step_up import (
        StepUpAssertionVerificationError,
        StepUpClass,
    )

    now = 1_800_000_000
    context = replace_dataclass(
        _step_up_context(),
        route_path="/api/v1/runs/{run_id}/production-approval",
        permission="runs.production_approval.create",
        step_up_class=StepUpClass.PRODUCTION_APPROVAL,
        scorecard_ref="sha256:" + "3" * 64,
        scorecard_sha256="sha256:" + "4" * 64,
    )
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides={claim_name: "sha256:" + "7" * 64},
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == "step_up_binding_mismatch"


@pytest.mark.parametrize("mismatch", ["action", "resource"])
def test_step_up_assertion_with_wrong_action_or_resource_is_denied(
    mismatch: str,
) -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        permission=("runs.launch" if mismatch == "action" else None),
        resource_digest=("sha256:" + "9" * 64 if mismatch == "resource" else None),
    )

    with pytest.raises(StepUpAssertionVerificationError, match="binding"):
        _jwt_step_up_verifier(now=now).verify(token, context)


def test_stale_step_up_assertion_is_denied() -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 301,
        expires_at=now + 60,
    )

    with pytest.raises(StepUpAssertionVerificationError, match="stale"):
        _jwt_step_up_verifier(now=now).verify(token, context)


def test_future_step_up_assertion_is_denied() -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now + 11,
        expires_at=now + 60,
    )

    with pytest.raises(StepUpAssertionVerificationError, match="future"):
        _jwt_step_up_verifier(now=now).verify(token, context)


def test_not_before_step_up_assertion_is_denied() -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 600,
        claim_overrides={"nbf": now + 300},
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == "step_up_not_yet_valid"


@pytest.mark.parametrize(
    ("claim_overrides", "error_code"),
    [
        pytest.param({"nbf": "later"}, "step_up_invalid", id="non-integer"),
        pytest.param(
            {"nbf": 1_799_999_998, "exp": 1_799_999_998},
            "step_up_expired",
            id="expires-at-not-before",
        ),
    ],
)
def test_not_before_step_up_assertion_rejects_invalid_claim_or_window(
    claim_overrides: dict[str, object],
    error_code: str,
) -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides=claim_overrides,
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == error_code


def test_not_before_step_up_assertion_accepts_exact_clock_skew_boundary() -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides={"nbf": now + 10},
    )

    verification = _jwt_step_up_verifier(now=now).verify(token, context)

    assert type(verification) is StepUpAssertionVerification
    assert verification.context == context


def test_replayed_step_up_assertion_is_denied(runtime_api_env, tmp_path: Path) -> None:
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    context = _production_approval_test_context(
        runtime_api_env,
        suffix="valid-one-use-step-up",
    )
    now = int(time.time())

    class _Verifier:
        def __init__(self) -> None:
            self.contexts: list[Any] = []

        def verify(self, encoded_assertion: str, verification_context):
            assert encoded_assertion == "externally-signed-step-up"
            self.contexts.append(verification_context)
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id="valid-one-use-step-up-jti",
                issuer="https://step-up.example",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    verifier = _Verifier()
    existing_security = context["client"].app.state.runtime_security
    assert isinstance(existing_security, RuntimeSecurityConfig)
    context["client"].app.state.runtime_security = replace(
        existing_security,
        step_up_verifier=verifier,
        step_up_replay_store=ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "valid-step-up.sqlite3",
        ),
    )
    headers = {
        "Authorization": f"Bearer {context['bearer']}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
        "X-PolicyOS-Step-Up": "externally-signed-step-up",
    }
    body = {"quality_scorecard_ref": context["scorecard_ref"]}

    packets_before = {
        str(artifact_id)
        for artifact_id in context["store"].iter_artifact_ids()
        if context["store"].get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }
    first = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers=headers,
        json=body,
    )
    packets_after_first = {
        str(artifact_id)
        for artifact_id in context["store"].iter_artifact_ids()
        if context["store"].get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }
    replay = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers=headers,
        json=body,
    )
    packets_after_replay = {
        str(artifact_id)
        for artifact_id in context["store"].iter_artifact_ids()
        if context["store"].get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert first.status_code == 200, first.json()
    assert packets_after_first > packets_before
    assert replay.status_code == 403, replay.json()
    assert replay.json()["code"] == "step_up_replayed"
    assert packets_after_replay == packets_after_first
    assert len(verifier.contexts) == 2
    verified_context = verifier.contexts[0]
    assert verified_context.subject == "user-1"
    assert verified_context.tenant_id == runtime_api_env["tenant_a"]
    assert verified_context.method == "POST"
    assert verified_context.route_path == ("/api/v1/runs/{run_id}/production-approval")
    assert verified_context.permission == "runs.production_approval.create"
    assert verified_context.step_up_class.value == "production_approval"
    assert verified_context.scorecard_ref == context["scorecard_ref"]
    assert verified_context.scorecard_sha256.startswith("sha256:")
    assert verified_context.body_sha256.startswith("sha256:")


def test_production_approval_binds_persisted_scorecard_in_step_up(
    runtime_api_env,
) -> None:
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    context = _production_approval_test_context(
        runtime_api_env,
        suffix="exact-production-scorecard-binding",
    )
    now = int(time.time())

    class _Verifier:
        def __init__(self) -> None:
            self.contexts: list[Any] = []

        def verify(self, encoded_assertion: str, verification_context):
            assert encoded_assertion == "exact-scorecard-step-up"
            self.contexts.append(verification_context)
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id="exact-scorecard-step-up-jti",
                issuer="https://step-up.example",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    class _ReplayStore:
        def consume_step_up_assertion(self, *, assertion_id: str, expires_at: int) -> bool:
            assert assertion_id == "exact-scorecard-step-up-jti"
            assert expires_at == now + 60
            return True

    verifier = _Verifier()
    security = context["client"].app.state.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    context["client"].app.state.runtime_security = replace(
        security,
        step_up_verifier=verifier,
        step_up_replay_store=_ReplayStore(),
    )
    raw_body = json.dumps(
        {"quality_scorecard_ref": context["scorecard_ref"]},
        separators=(",", ":"),
    ).encode("utf-8")

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": "exact-scorecard-step-up",
            "Content-Type": "application/json",
        },
        content=raw_body,
    )

    assert response.status_code == 200, response.json()
    assert len(verifier.contexts) == 1
    verified_context = verifier.contexts[0]
    normalized_scorecard = dict(context["scorecard_payload"])
    normalized_scorecard["evidence_refs"] = {"quality_scorecard": context["scorecard_ref"]}
    normalized_scorecard.update(
        {
            "quality_scorecard_ref": context["scorecard_ref"],
            "authoritative_scorecard_ref": context["scorecard_ref"],
            "scorecard_identity_ref": context["scorecard_ref"],
            "scorecard_identity_verified": True,
            "scorecard_ref_source": "runtime_cas",
            "run_id": runtime_api_env["core_run_id"],
        }
    )
    expected_scorecard_sha256 = (
        "sha256:"
        + hashlib.sha256(
            to_canonical_bytes(
                normalized_scorecard,
                spec=CanonSpec(forbid_floats=False),
            )
        ).hexdigest()
    )
    expected_body_sha256 = "sha256:" + hashlib.sha256(raw_body).hexdigest()
    assert verified_context.scorecard_ref == context["scorecard_ref"]
    assert verified_context.scorecard_sha256 == expected_scorecard_sha256
    assert verified_context.body_sha256 == expected_body_sha256


def test_concurrent_replay_allows_exactly_one_step_up_consumer(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    path = tmp_path / "step-up-replays.sqlite3"
    stores = (
        ControlPlaneStore(backend="sqlite", sqlite_path=path),
        ControlPlaneStore(backend="sqlite", sqlite_path=path),
    )
    expires_at = int(time.time()) + 60
    barrier = threading.Barrier(2)

    def _consume(store: ControlPlaneStore) -> bool:
        barrier.wait(timeout=10)
        return store.consume_step_up_assertion(
            assertion_id="concurrent-one-use-jti",
            expires_at=expires_at,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(_consume, stores))

    assert sorted(results) == [False, True]


def test_late_high_stakes_route_without_step_up_fails_before_opa(
    runtime_api_env,
) -> None:
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.authorization import (
        ResourceBindingSource,
        ResourceBindingSpec,
        require_action_permission,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _build_secure_client,
        _CaptureOPA,
        _claims,
        _fixture_bearer,
    )

    opa = _CaptureOPA()
    bearer = _fixture_bearer("late-high-stakes-missing-step-up")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-late-high-stakes-missing-step-up",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    executed: list[bool] = []
    action = require_action_permission(
        RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.late_high_stakes",
        ),
    )

    @client.app.post(
        "/api/v1/ds20/late-high-stakes",
        dependencies=[Depends(action)],
    )
    def _late_probe() -> dict[str, bool]:
        executed.append(True)
        return {"mutated": True}

    response = client.post(
        "/api/v1/ds20/late-high-stakes",
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "authorization_contract_violation"
    assert executed == []
    assert opa.inputs == []


def _assert_production_override_denied(
    *,
    reviewer_identity: str,
    signature: str | None,
    expected_code: str,
    runtime_api_env,
) -> None:
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _CaptureOPA,
        _install_bound_test_step_up,
    )

    opa = _CaptureOPA()
    context = _production_approval_test_context(
        runtime_api_env,
        suffix=f"override-authority-{expected_code}",
        opa_client=opa,
    )
    store = context["store"]
    packets_before = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }
    assertion = _install_bound_test_step_up(context["client"])
    override = {
        "reviewer_identity": reviewer_identity,
        "reason": "Exceptional reviewer decision",
        "scope": f"run:{runtime_api_env['core_run_id']}",
        "expires_at": "2099-01-01T00:00:00Z",
        "evidence_refs": [context["scorecard_ref"]],
    }
    if signature is not None:
        override["signature"] = signature

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": assertion,
        },
        json={
            "quality_scorecard_ref": context["scorecard_ref"],
            "override": override,
        },
    )
    packets_after = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == expected_code
    assert opa.inputs == []
    assert packets_after == packets_before


def test_production_approval_override_identity_must_equal_verified_subject(
    runtime_api_env,
) -> None:
    _assert_production_override_denied(
        reviewer_identity="self-asserted-reviewer",
        signature=None,
        expected_code="production_approval_override_identity_mismatch",
        runtime_api_env=runtime_api_env,
    )


def test_production_approval_rejects_client_asserted_signature(
    runtime_api_env,
) -> None:
    _assert_production_override_denied(
        reviewer_identity="user-1",
        signature="client-authored-signature",
        expected_code="production_approval_client_signature_forbidden",
        runtime_api_env=runtime_api_env,
    )


def test_service_principal_cannot_satisfy_human_step_up_class(
    runtime_api_env,
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.delegation import DelegationTokenManager
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.authorization import (
        ResourceBindingSource,
        ResourceBindingSpec,
        require_action_permission,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.step_up import StepUpClass, require_step_up
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    manager = DelegationTokenManager(
        signing_key="ds20-service-delegation-key-at-least-32-bytes",
        ttl_seconds=60,
    )
    delegator = "spiffe://polisyos.test/delegator"
    audience = "spiffe://polisyos.test/runtime-api"
    bearer = _fixture_bearer("service-human-step-up")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
        delegation_manager=manager,
        trusted_delegators=frozenset({delegator}),
        service_spiffe_id=audience,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-service-human-step-up",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    service_scope = AccessScope.for_service(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        spiffe_id="spiffe://polisyos.test/worker",
    )
    delegation_token = manager.issue_token(
        scope=service_scope,
        issuer=delegator,
        audience=audience,
    )
    action = require_action_permission(
        RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.service_step_up",
        ),
    )
    step_up = require_step_up(StepUpClass.PROMOTION)
    executed: list[bool] = []

    @client.app.post(
        "/api/v1/ds20/service-human-step-up",
        dependencies=[Depends(action), Depends(step_up)],
    )
    def _probe() -> dict[str, bool]:
        executed.append(True)
        return {"mutated": True}

    response = client.post(
        "/api/v1/ds20/service-human-step-up",
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Context": delegation_token,
            "l5d-client-id": delegator,
            "X-PolicyOS-Step-Up": "must-not-help-a-service-principal",
        },
        json={},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "step_up_human_principal_required"
    assert executed == []
