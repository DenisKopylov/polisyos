from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Protocol, TypeGuard, cast

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi import Depends, FastAPI, Request
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import PromotionCandidate
from polisyos.core.contracts.runtime import ScenarioCreateRequest, ScenarioManifest
from polisyos.core.run.context import RunContext
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.delegation import DelegationTokenManager
from polisyos.core.security.exceptions import TokenValidationError
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import (
    _assert_runtime_security_middleware_order,
    create_runtime_api_app,
)
from polisyos.runtime.http.permissions import RuntimePermission


class _AllowOPA:
    async def check(self, authz_input):
        del authz_input
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _DenyOPA:
    async def check(self, authz_input):
        del authz_input
        return AuthzResult(
            decision=AuthzDecision.DENY,
            policy="polisyos/authz/decision",
            reasons=("DENY_TEST",),
        )


class _CaptureOPA:
    def __init__(self) -> None:
        self.inputs: list[Any] = []

    async def check(self, authz_input):
        self.inputs.append(authz_input)
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _InterleavingOPA(_CaptureOPA):
    def __init__(self) -> None:
        super().__init__()
        self.callback: Callable[[], None] | None = None

    async def check(self, authz_input):
        self.inputs.append(authz_input)
        callback = self.callback
        if callback is not None and str(authz_input.resource_kind).startswith(
            "runtime.run.scenario.candidate"
        ):
            self.callback = None
            callback()
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _BarrierOPA(_CaptureOPA):
    def __init__(self, barrier: threading.Barrier) -> None:
        super().__init__()
        self._barrier = barrier

    async def check(self, authz_input):
        self.inputs.append(authz_input)
        await asyncio.to_thread(self._barrier.wait, 10)
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _SelectiveReviewOPA:
    async def check(self, authz_input):
        kind = getattr(authz_input, "resource_kind", "")
        if str(kind).endswith("message.cursor.update"):
            return AuthzResult(
                decision=AuthzDecision.DENY,
                policy="polisyos/authz/decision",
                reasons=("MESSAGE_DENIED",),
            )
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _SlowOPA:
    async def check(self, authz_input):
        del authz_input
        await asyncio.sleep(0.2)
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _IdentityProvider:
    def __init__(self, claims_by_token: dict[str, UserIdentityClaims]) -> None:
        self._claims_by_token = claims_by_token

    def put_claim(self, token: str, claims: UserIdentityClaims) -> None:
        self._claims_by_token[token] = claims

    def extract_user_claims(self, jwt_token: str, *, expected_cell_id: str | None = None):
        claim = self._claims_by_token.get(jwt_token)
        if claim is None:
            raise TokenValidationError("invalid token")
        if expected_cell_id and claim.cell_id and claim.cell_id != expected_cell_id:
            raise TokenValidationError("cell binding mismatch")
        return claim


def _claims(
    *,
    tenant_id: str,
    cell_id: str,
    jti: str,
    roles: frozenset[PolicyOSRole] | None = None,
) -> UserIdentityClaims:
    return UserIdentityClaims(
        sub="user-1",
        email="user@example.com",
        tenant_id=tenant_id,
        cell_id=cell_id,
        roles=roles if roles is not None else frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss="https://idp.example/realms/polisyos",
        aud="polisyos-web",
        exp=9_999_999_999,
        iat=1,
        jti=jti,
    )


def _fixture_bearer(suffix: str) -> str:
    return f"token-{suffix}"


def _install_bound_test_step_up(client) -> str:
    """Install a test-only external verifier and atomic one-use store."""
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    class _Verifier:
        def verify(self, encoded_assertion: str, verification_context):
            now = int(time.time())
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id=hashlib.sha256(encoded_assertion.encode()).hexdigest(),
                issuer="https://step-up.test",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    class _ReplayStore:
        def __init__(self) -> None:
            self._consumed: set[str] = set()
            self._lock = threading.Lock()

        def consume_step_up_assertion(self, *, assertion_id: str, expires_at: int) -> bool:
            del expires_at
            with self._lock:
                if assertion_id in self._consumed:
                    return False
                self._consumed.add(assertion_id)
                return True

    container = client.app.state.runtime_container
    security = container.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    configured = replace(
        security,
        step_up_verifier=_Verifier(),
        step_up_replay_store=_ReplayStore(),
    )
    container.runtime_security = configured
    client.app.state.runtime_security = configured
    return "test-only-external-step-up"


_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_PATH_PARAMETER = re.compile(r"\{([^}]+)\}")
_ACTION_PERMISSION_MARKER = "__polisyos_action_permission__"
_EXPECTED_MUTATING_OPERATIONS = (
    ("POST", "/api/v1/analysis/attractors"),
    ("POST", "/api/v1/analysis/basin-map"),
    ("POST", "/api/v1/analysis/continuation"),
    ("POST", "/api/v1/analysis/lyapunov"),
    ("POST", "/api/v1/artifacts/batch"),
    ("POST", "/api/v1/artifacts/{packet_id}/render"),
    ("POST", "/api/v1/control/analytics/sae/causal-frontier"),
    ("POST", "/api/v1/control/capabilities/search"),
    ("POST", "/api/v1/control/data/discover"),
    ("POST", "/api/v1/control/data/ingest"),
    ("POST", "/api/v1/control/data/preview"),
    ("POST", "/api/v1/control/data/promotion/{promotion_id}/approve"),
    ("POST", "/api/v1/control/data/promotion/{promotion_id}/reject"),
    ("POST", "/api/v1/control/data/resolve"),
    ("POST", "/api/v1/control/decision-validity/epoch-batches"),
    ("POST", "/api/v1/control/decision-validity/events"),
    ("POST", "/api/v1/control/lex/search"),
    ("POST", "/api/v1/control/lex/trigger"),
    ("POST", "/api/v1/control/runs"),
    ("POST", "/api/v1/control/runs/nl"),
    ("POST", "/api/v1/control/runs/{run_id}/feedback/evaluate"),
    ("POST", "/api/v1/control/runs/{run_id}/reissue"),
    ("POST", "/api/v1/fabric/impact"),
    ("POST", "/api/v1/fabric/quality/batch"),
    ("POST", "/api/v1/fabric/trust/batch"),
    ("POST", "/api/v1/lineage/batch"),
    ("POST", "/api/v1/mobility/bounds"),
    ("POST", "/api/v1/mobility/estimate"),
    ("POST", "/api/v1/runs/batch"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"),
    ("POST", "/api/v1/runs/{run_id}/human-decisions"),
    ("POST", "/api/v1/runs/{run_id}/production-approval"),
    ("POST", "/api/v1/runs/{run_id}/scenarios"),
)
_EXPECTED_MUTATING_PERMISSIONS = {
    ("POST", "/api/v1/analysis/attractors"): RuntimePermission.ANALYSIS_EXECUTE,
    ("POST", "/api/v1/analysis/basin-map"): RuntimePermission.ANALYSIS_EXECUTE,
    ("POST", "/api/v1/analysis/continuation"): RuntimePermission.ANALYSIS_EXECUTE,
    ("POST", "/api/v1/analysis/lyapunov"): RuntimePermission.ANALYSIS_EXECUTE,
    ("POST", "/api/v1/artifacts/batch"): RuntimePermission.ARTIFACTS_BATCH_READ,
    (
        "POST",
        "/api/v1/artifacts/{packet_id}/render",
    ): RuntimePermission.ARTIFACTS_RENDER,
    (
        "POST",
        "/api/v1/control/analytics/sae/causal-frontier",
    ): RuntimePermission.EVIDENCE_SAE_ANALYZE,
    ("POST", "/api/v1/control/capabilities/search"): RuntimePermission.EVIDENCE_DISCOVER,
    ("POST", "/api/v1/control/data/discover"): RuntimePermission.EVIDENCE_DISCOVER,
    ("POST", "/api/v1/control/data/ingest"): RuntimePermission.EVIDENCE_ACQUIRE,
    ("POST", "/api/v1/control/data/preview"): RuntimePermission.EVIDENCE_PREVIEW,
    (
        "POST",
        "/api/v1/control/data/promotion/{promotion_id}/approve",
    ): RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
    (
        "POST",
        "/api/v1/control/data/promotion/{promotion_id}/reject",
    ): RuntimePermission.EVIDENCE_PROMOTIONS_REJECT,
    ("POST", "/api/v1/control/data/resolve"): RuntimePermission.EVIDENCE_RESOLVE,
    (
        "POST",
        "/api/v1/control/decision-validity/events",
    ): RuntimePermission.DECISIONS_VALIDITY_PUBLISH,
    (
        "POST",
        "/api/v1/control/decision-validity/epoch-batches",
    ): RuntimePermission.DECISIONS_VALIDITY_PUBLISH,
    ("POST", "/api/v1/control/lex/search"): RuntimePermission.KNOWLEDGE_SEARCH,
    ("POST", "/api/v1/control/lex/trigger"): RuntimePermission.KNOWLEDGE_TRIGGER,
    ("POST", "/api/v1/control/runs"): RuntimePermission.RUNS_LAUNCH,
    ("POST", "/api/v1/control/runs/nl"): RuntimePermission.RUNS_LAUNCH,
    (
        "POST",
        "/api/v1/control/runs/{run_id}/feedback/evaluate",
    ): RuntimePermission.RUNS_FEEDBACK_EVALUATE,
    ("POST", "/api/v1/control/runs/{run_id}/reissue"): RuntimePermission.RUNS_REISSUE,
    ("POST", "/api/v1/fabric/impact"): RuntimePermission.FABRIC_IMPACT_ANALYZE,
    ("POST", "/api/v1/fabric/quality/batch"): RuntimePermission.FABRIC_QUALITY_READ,
    ("POST", "/api/v1/fabric/trust/batch"): RuntimePermission.FABRIC_TRUST_READ,
    ("POST", "/api/v1/lineage/batch"): RuntimePermission.LINEAGE_BATCH_READ,
    ("POST", "/api/v1/mobility/bounds"): RuntimePermission.MOBILITY_ANALYZE,
    ("POST", "/api/v1/mobility/estimate"): RuntimePermission.MOBILITY_ANALYZE,
    ("POST", "/api/v1/runs/batch"): RuntimePermission.RUNS_BATCH_READ,
    (
        "POST",
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request",
    ): RuntimePermission.EVIDENCE_ACQUIRE,
    (
        "POST",
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute",
    ): RuntimePermission.EVIDENCE_ACQUIRE,
    (
        "POST",
        "/api/v1/runs/{run_id}/human-decisions",
    ): RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE,
    (
        "POST",
        "/api/v1/runs/{run_id}/production-approval",
    ): RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
    ("POST", "/api/v1/runs/{run_id}/scenarios"): RuntimePermission.SCENARIOS_CREATE,
}
_MUTATING_OPERATION_CASE_IDS = {
    ("POST", "/api/v1/analysis/attractors"): "analyze-attractors",
    ("POST", "/api/v1/analysis/basin-map"): "persist-basin-map",
    ("POST", "/api/v1/analysis/continuation"): "persist-continuation-branch",
    ("POST", "/api/v1/analysis/lyapunov"): "analyze-lyapunov",
    ("POST", "/api/v1/artifacts/batch"): "get-artifact-batch",
    ("POST", "/api/v1/artifacts/{packet_id}/render"): ("render-bureaucratic-artifact"),
    ("POST", "/api/v1/control/analytics/sae/causal-frontier"): ("estimate-causal-frontier-sae"),
    ("POST", "/api/v1/control/capabilities/search"): "search-capabilities",
    ("POST", "/api/v1/control/data/discover"): "discover-data-sources",
    ("POST", "/api/v1/control/data/ingest"): "ingest-data",
    ("POST", "/api/v1/control/data/preview"): "preview-fetch-plan",
    ("POST", "/api/v1/control/data/promotion/{promotion_id}/approve"): ("approve-data-promotion"),
    ("POST", "/api/v1/control/data/promotion/{promotion_id}/reject"): ("reject-data-promotion"),
    ("POST", "/api/v1/control/data/resolve"): "resolve-data-needs",
    ("POST", "/api/v1/control/decision-validity/events"): ("publish-decision-validity-event"),
    ("POST", "/api/v1/control/decision-validity/epoch-batches"): ("admit-epoch-validity-batch"),
    ("POST", "/api/v1/control/lex/search"): "search-lex-graph",
    ("POST", "/api/v1/control/lex/trigger"): "trigger-lex-pipeline",
    ("POST", "/api/v1/control/runs"): "launch-run",
    ("POST", "/api/v1/control/runs/nl"): "launch-nl-run",
    ("POST", "/api/v1/control/runs/{run_id}/feedback/evaluate"): ("evaluate-run-feedback"),
    ("POST", "/api/v1/control/runs/{run_id}/reissue"): "reissue-run",
    ("POST", "/api/v1/fabric/impact"): "analyze-fabric-impact",
    ("POST", "/api/v1/fabric/quality/batch"): "get-fabric-quality-batch",
    ("POST", "/api/v1/fabric/trust/batch"): "get-fabric-trust-batch",
    ("POST", "/api/v1/lineage/batch"): "get-lineage-batch",
    ("POST", "/api/v1/mobility/bounds"): "compute-mobility-bounds",
    ("POST", "/api/v1/mobility/estimate"): "estimate-mobility",
    ("POST", "/api/v1/runs/batch"): "get-runs-batch",
    (
        "POST",
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request",
    ): "request-run-acquisition-decision",
    (
        "POST",
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute",
    ): "execute-run-acquisition-route",
    ("POST", "/api/v1/runs/{run_id}/human-decisions"): ("create-run-human-decision"),
    ("POST", "/api/v1/runs/{run_id}/production-approval"): ("create-run-production-approval"),
    ("POST", "/api/v1/runs/{run_id}/scenarios"): "create-run-scenario",
}
_HIGH_STAKES_MUTATING_OPERATIONS = (
    ("POST", "/api/v1/control/data/ingest"),
    ("POST", "/api/v1/control/data/promotion/{promotion_id}/approve"),
    ("POST", "/api/v1/control/data/promotion/{promotion_id}/reject"),
    ("POST", "/api/v1/control/decision-validity/events"),
    ("POST", "/api/v1/control/decision-validity/epoch-batches"),
    ("POST", "/api/v1/control/runs/{run_id}/reissue"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request"),
    ("POST", "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"),
    ("POST", "/api/v1/runs/{run_id}/human-decisions"),
    ("POST", "/api/v1/runs/{run_id}/production-approval"),
)


def _mutation_operation_params() -> tuple[object, ...]:
    assert set(_MUTATING_OPERATION_CASE_IDS) == set(_EXPECTED_MUTATING_OPERATIONS)
    return tuple(
        pytest.param(operation, id=_MUTATING_OPERATION_CASE_IDS[operation])
        for operation in _EXPECTED_MUTATING_OPERATIONS
    )


def _high_stakes_mutation_params() -> tuple[object, ...]:
    assert set(_HIGH_STAKES_MUTATING_OPERATIONS).issubset(_MUTATING_OPERATION_CASE_IDS)
    return tuple(
        pytest.param(operation, id=_MUTATING_OPERATION_CASE_IDS[operation])
        for operation in _HIGH_STAKES_MUTATING_OPERATIONS
    )


class _ExecutableActionPermissionDependency(Protocol):
    __polisyos_action_permission__: object

    def __call__(self, *args: object, **kwargs: object) -> object: ...


def _live_mutating_operations(app) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (method, route.path)
            for route in app.routes
            if isinstance(route, APIRoute)
            for method in route.methods & _UNSAFE_METHODS
        )
    )


def _live_mutating_routes(app) -> tuple[APIRoute, ...]:
    return tuple(
        sorted(
            (
                route
                for route in app.routes
                if isinstance(route, APIRoute) and route.methods & _UNSAFE_METHODS
            ),
            key=lambda route: route.path,
        )
    )


def _walk_dependency_calls(dependant: Any) -> Iterator[object]:
    for child in dependant.dependencies:
        yield child.call
        yield from _walk_dependency_calls(child)


def _is_executable_action_permission_dependency(
    dependency: object,
) -> TypeGuard[_ExecutableActionPermissionDependency]:
    marker = getattr(dependency, _ACTION_PERMISSION_MARKER, None)
    return callable(dependency) and isinstance(
        getattr(marker, "permission", None),
        RuntimePermission,
    )


def _action_permission_dependencies(route: APIRoute) -> tuple[Callable[..., object], ...]:
    return tuple(
        dependency
        for dependency in _walk_dependency_calls(route.dependant)
        if _is_executable_action_permission_dependency(dependency)
    )


def _operation_path(path: str, runtime_api_env) -> str:
    values = {
        "packet_id": runtime_api_env["workflow_report_artifact_id"],
        "promotion_id": "promotion-ds20-authz-probe",
        "run_id": runtime_api_env["core_run_id"],
        "route_id": "sha256:" + "a" * 64,
    }
    return _PATH_PARAMETER.sub(
        lambda match: str(values.get(match.group(1), f"ds20-{match.group(1)}")),
        path,
    )


def _scenario_create_body(*, scenario_id: str, quantity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "policy_question": "Can an authorization-bound scenario slot be replaced?",
        "author": "ds20-security-test",
        "model_family": "operator-specified",
        "interventions": [
            {
                "field": "policy_cost",
                "operator": "set",
                "value": quantity,
                "baseline_value": quantity,
                "constraint_ids": [],
            }
        ],
        "assumptions": [
            {
                "id": "asm_ds20_binding",
                "label": "Authorization binding probe",
                "status": "operator_assumption",
                "lineage": {
                    "id": "scenario:ds20:assumption",
                    "status": "pending",
                    "freshness": "current",
                    "summary": {"source": "ds20-security-test"},
                },
            }
        ],
    }


def _align_decision_packet_owner(runtime_api_env, *, cell_id: str) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    store.record_artifact_owner(
        runtime_api_env["decision_packet_artifact_id"],
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell_id,
        writer="tests.ds20.authorized_matrix",
    )


def _create_production_scorecard(runtime_api_env, *, cell_id: str) -> str:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_ref = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "run_id": runtime_api_env["core_run_id"],
            "quality_status": "pass",
            "performance_status": "pass",
            "conflict_status": "pass",
            "approval_state": "approval_ready",
            "quality_gates": [],
            "evidence_refs": {},
        },
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell_id,
        writer="tests.ds20.authorized_matrix",
    )
    return str(scorecard_ref.artifact_id)


def _production_approval_required_input_refs() -> dict[str, str]:
    basis_ref = "sha256:" + "b" * 64
    decision_ref = "sha256:" + "c" * 64
    return {
        "production_basis_ref": basis_ref,
        "production_basis_digest": basis_ref,
        "human_decision_record_ref": decision_ref,
        "human_decision_record_digest": decision_ref,
    }


def _create_authorized_matrix_run(
    runtime_api_env,
    *,
    cell_id: str,
    run_id: str,
    execution_profile: str | None = None,
) -> str:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    registry_ref = store.put_json(
        {"registry": {}, "purpose": "ds20-authorized-operation-matrix"},
        ArtifactWriteOptions(
            kind="core.registry_bundle",
            media_type="application/json",
        ),
    )
    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=run_id,
        run_dir=runtime_api_env["cas_root"] / "runs" / run_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell_id,
    )
    run.run_manifest.execution_profile = execution_profile
    run.finalize()
    return run_id


def _causal_frontier_body() -> dict[str, Any]:
    return {
        "areas": [
            {
                "area_id": f"area_{index}",
                "direct_estimate": estimate,
                "direct_variance": 0.15,
                "policy_indicator": 1.0 if index >= 4 else 0.0,
                "covariates": {"trend": float(index) / 7.0},
            }
            for index, estimate in enumerate([0.8, 1.0, 1.2, 1.4, 2.8, 3.0, 3.2, 3.4])
        ],
        "edges": [
            {
                "src_area_id": f"area_{index}",
                "dst_area_id": f"area_{index + 1}",
                "weight": 1.0,
                "adjacency_type": "contiguity",
                "frontier_flag": index == 3,
                "frontier_type": "policy",
                "frontier_source": "ds20-authorization-matrix",
            }
            for index in range(7)
        ],
        "metadata": {
            "frontier_semantics": "declared_policy_frontier",
            "transportability_required": False,
        },
        "lambda_spatial": 20.0,
        "component_ridge": 1e-4,
        "persist_artifacts": False,
        "governance_profile": "strict",
    }


def _data_need() -> dict[str, Any]:
    return {
        "metric": "us.macro.gdp_nominal",
        "geography": "USA",
        "granularity": "annual",
        "quality_min": 0.6,
        "purpose": "ds20 authorization admission",
    }


def _fetch_plan() -> dict[str, Any]:
    return {
        "plan_id": "plan_ds20_authorized_matrix",
        "metric_id": "us.macro.gdp_nominal",
        "connector_id": "missing.connector",
        "dataset_id": "missing.dataset",
        "profile_id": None,
        "filters": {},
        "date_start": None,
        "date_end": None,
        "granularity": "annual",
        "quality_min": 0.6,
        "source_lane": "fastlane",
        "persist_payload": False,
        "max_preview_rows": 10,
        "fallbacks": [],
        "metadata": {},
    }


def _authorized_mutation_request(
    operation: tuple[str, str],
    runtime_api_env,
    *,
    cell_id: str,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, dict[str, Any] | None]:
    case_id = _MUTATING_OPERATION_CASE_IDS[operation]
    run_id = runtime_api_env["core_run_id"]
    packet_id = runtime_api_env["decision_packet_artifact_id"]
    default_path = _operation_path(operation[1], runtime_api_env)

    if case_id == "analyze-attractors":
        return default_path, {
            "variable_ids": ["x"],
            "trajectory": [[0.0] for _ in range(10)],
            "persist_artifact": False,
        }
    if case_id == "persist-basin-map":
        return default_path, {
            "basin_id": "basin_ds20_authorized_matrix",
            "state_projection": {"variables": ["x"], "reduced_dimension": 1},
            "sampling_method": "authorization_fixture",
        }
    if case_id == "persist-continuation-branch":
        return default_path, {
            "branch_id": "branch_ds20_authorized_matrix",
            "branch_kind": "equilibrium",
        }
    if case_id == "analyze-lyapunov":
        return default_path, {
            "variable_ids": ["x"],
            "trajectory": [[0.0] for _ in range(10)],
            "largest_lyapunov_exponent": -0.1,
            "persist_artifact": False,
        }
    if case_id == "get-artifact-batch":
        _align_decision_packet_owner(runtime_api_env, cell_id=cell_id)
        return default_path, {"artifact_ids": [packet_id]}
    if case_id == "render-bureaucratic-artifact":
        _align_decision_packet_owner(runtime_api_env, cell_id=cell_id)
        return f"/api/v1/artifacts/{packet_id}/render", {"genre": "expert_vysnovok"}
    if case_id == "estimate-causal-frontier-sae":
        return default_path, _causal_frontier_body()
    if case_id == "search-capabilities":
        return default_path, {
            "search": {
                "request_id": "search:authz-matrix",
                "query_text": "generated capability",
                "construct_refs": ["construct:generated"],
                "intent": "capability_discovery",
                "required_layers": ["runtime_registry"],
                "authority_purpose": "review_capability_candidates",
                "allowed_modes": ["exact"],
                "budget": {"top_k": 5},
                "rule_version": "policyos.ds10.discovery.v1",
            },
            "resource_kinds": ["case"],
            "audience": "REVIEWER",
        }
    if case_id == "discover-data-sources":
        return default_path, {
            "data_needs": [_data_need()],
            "max_sources_per_query": 2,
            "max_discovery_calls_per_source": 3,
            "max_candidates_total": 5,
            "time_budget_ms": 1000,
            "cost_budget_usd": 0,
        }
    if case_id == "ingest-data":
        monkeypatch.setattr(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            lambda *args, **kwargs: None,
        )
        return default_path, {
            "datasets": [
                {
                    "connector_id": "worldbank.wdi",
                    "dataset_id": "NY.GDP.MKTP.CD",
                    "filters": {"country": ["USA"]},
                }
            ],
            "source": "ds20-authorization-matrix",
            "license_name": "open",
        }
    if case_id == "preview-fetch-plan":
        return default_path, {"fetch_plan": _fetch_plan(), "allow_fallback": True}
    if case_id in {"approve-data-promotion", "reject-data-promotion"}:
        promotion_id = f"promotion-ds20-{case_id}"
        retrieval = client.app.state._control_service._retrieval
        candidate = PromotionCandidate(
            promotion_id=promotion_id,
            metric_id="metric.ds20.authorized",
            connector_id="connector.ds20",
            dataset_id="dataset.ds20",
            confidence=0.9,
        )
        with retrieval._state_lock:
            retrieval._store_promotion_candidate_locked(candidate)
        return (
            default_path.replace("promotion-ds20-authz-probe", promotion_id),
            {"reason": "DS20 authorized operation proof"},
        )
    if case_id == "resolve-data-needs":
        return default_path, {
            "data_needs": [_data_need()],
            "mode": "hybrid",
            "allow_explore_fallback": True,
        }
    if case_id == "publish-decision-validity-event":
        return default_path, {
            "trigger_type": "source_invalidation",
            "status": "stale",
            "reason": "ds20_authorization_matrix",
            "dependency_keys": ["source::gazette::ds20"],
            "source_ref": "source://gazette/ds20",
            "payload": {
                "invalidation_domain": "source",
                "new_evidence_refs": ["sha256:" + "c" * 64],
                "change_reason": "DS20 authorized publication proof",
            },
        }
    if case_id == "admit-epoch-validity-batch":
        return default_path, {
            "transition_artifact_ref": {
                "artifact_id": runtime_api_env["root_artifact_id"],
                "kind": "chronology.epoch_transition",
                "media_type": "application/vnd.polisyos.chronology+json",
            },
            "requested_query_context_ref": "sha256:" + "d" * 64,
        }
    if case_id == "search-lex-graph":
        return default_path, {
            "query": "authorization",
            "top_k": 5,
            "output_dir": str(runtime_api_env["cas_root"] / "lex-ds20-search"),
        }
    if case_id == "trigger-lex-pipeline":
        return default_path, {
            "cards_path": str(runtime_api_env["cas_root"] / "lex-ds20-cards"),
            "texts_path": str(runtime_api_env["cas_root"] / "lex-ds20-texts"),
            "output_dir": str(runtime_api_env["cas_root"] / "lex-ds20-output"),
            "llm_model": "simulated-qwen",
        }
    if case_id == "launch-run":
        return default_path, {
            "mode": "workflow",
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "checkpoint_policy": "strict",
            "params": {"seed": 42},
        }
    if case_id == "launch-nl-run":
        return default_path, {
            "request": "Study healthcare policy effects",
            "llm_model": "claude-sonnet-4-5-20250929",
        }
    if case_id in {"evaluate-run-feedback", "reissue-run"}:
        synthetic_run_id = _create_authorized_matrix_run(
            runtime_api_env,
            cell_id=cell_id,
            run_id=f"R_ds20_{case_id.replace('-', '_')}",
        )
        client.app.state.runtime_container.runtime_api_context.run_index.refresh(force=True)
        if case_id == "evaluate-run-feedback":
            feedback = client.app.state.runtime_container.runtime_api_context.feedback
            monkeypatch.setattr(
                feedback,
                "evaluate_run_feedback",
                lambda run: (
                    None,
                    runtime_api_env["root_artifact_id"],
                    runtime_api_env["child_artifact_id"],
                    runtime_api_env["workflow_report_artifact_id"],
                ),
            )
        else:
            from polisyos.runtime.http.services.feedback import (
                FeedbackService,
                PreparedReissue,
            )

            monkeypatch.setattr(
                FeedbackService,
                "prepare_reissue",
                lambda service, run: PreparedReissue(
                    reissued_run_id="R_ds20_reissued",
                    state_payload={
                        "run_id": "R_ds20_reissued",
                        "inputs": {},
                        "params": {},
                        "budgets": {},
                        "execution_profile": None,
                    },
                    monitoring_report_ref=None,
                    compare_report_ref=None,
                    reissue_plan_ref=None,
                ),
            )
        suffix = "feedback/evaluate" if case_id == "evaluate-run-feedback" else "reissue"
        return f"/api/v1/control/runs/{synthetic_run_id}/{suffix}", None
    if case_id in {
        "analyze-fabric-impact",
        "get-fabric-quality-batch",
        "get-fabric-trust-batch",
        "get-lineage-batch",
    }:
        _align_decision_packet_owner(runtime_api_env, cell_id=cell_id)
        if case_id == "analyze-fabric-impact":
            return default_path, {
                "run_id": run_id,
                "lineage_ids": [f"artifact:{packet_id}"],
            }
        if case_id == "get-lineage-batch":
            return default_path, {"lineage_ids": [f"artifact:{packet_id}"]}
        return default_path, {"run_id": run_id}
    if case_id == "compute-mobility-bounds":
        return default_path, {
            "observed_joint_matrix": [[0.5, 0.0], [0.0, 0.5]],
            "row_marginals": [0.5, 0.5],
            "column_marginals": [0.5, 0.5],
            "persist_artifact": False,
        }
    if case_id == "estimate-mobility":
        return default_path, {
            "mode": "complete_case",
            "n_classes": 2,
            "origin_classes": [0, 1],
            "destination_classes": [0, 1],
            "persist_artifact": False,
        }
    if case_id == "get-runs-batch":
        return default_path, {"run_ids": [run_id]}
    if case_id in {
        "request-run-acquisition-decision",
        "execute-run-acquisition-route",
    }:
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionDecisionRequestResponse,
            AcquisitionExecutionResponse,
        )

        route_id = "sha256:" + "a" * 64
        authority_ref = "sha256:" + "9" * 64
        service = client.app.state.runtime_container.acquisition_action_service
        assert service is not None
        if case_id == "request-run-acquisition-decision":
            monkeypatch.setattr(
                service,
                "request_decision",
                lambda **kwargs: AcquisitionDecisionRequestResponse(
                    run_id=kwargs["run_id"],
                    route_id=kwargs["route_id"],
                    authority_decision_ref=authority_ref,
                    outcome="decision_required",
                ),
            )
        else:
            monkeypatch.setattr(
                service,
                "execute",
                lambda **kwargs: AcquisitionExecutionResponse(
                    run_id=kwargs["run_id"],
                    route_id=kwargs["route_id"],
                    job_id="job-ds20-acquisition-authorized",
                    authority_decision_ref=authority_ref,
                ),
            )
        return default_path, {
            "route_projection_hash": route_id,
            "planner_report_hash": "sha256:" + "b" * 64,
            "replay_pins": {
                "source_job_id": "job-ds20-acquisition-source",
                "compiled_ref": "sha256:" + "c" * 64,
                "compiled_content_hash": "sha256:" + "d" * 64,
                "terminal_event_id": "event-ds20-acquisition-terminal",
                "design_problem_ref": "sha256:" + "e" * 64,
                "cost_basis_hash": "sha256:" + "f" * 64,
            },
            "idempotency_key": case_id,
        }
    if case_id == "create-run-human-decision":
        digest = "sha256:" + "a" * 64
        return default_path, {
            "source_kind": "production_approval",
            "source_ref": digest,
            "decision_request_ref": digest,
            "decision_request_digest": digest,
            "basis_ref": digest,
            "basis_digest": digest,
            "action": "approve",
            "decision_mode": "ordinary",
            "accountability_statement": "I accept this exact decision authority.",
            "dissent_statement": "No dissent was recorded.",
        }
    if case_id == "create-run-production-approval":
        scorecard_ref = _create_production_scorecard(runtime_api_env, cell_id=cell_id)
        return default_path, {
            "quality_scorecard_ref": scorecard_ref,
            **_production_approval_required_input_refs(),
        }
    if case_id == "create-run-scenario":
        quantity_response = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/quantities")
        assert quantity_response.status_code == 200
        quantity = next(
            item
            for item in quantity_response.json()["quantities"]
            if item["metric_id"] == "policy_cost"
        )
        return default_path, _scenario_create_body(
            scenario_id="scn_ds20_authorized_matrix",
            quantity=quantity,
        )
    raise AssertionError(f"No authorized request fixture for {operation!r}")


def _is_action_permission_denial(response) -> bool:
    if response.status_code != 403:
        return False
    return _response_code(response) == "action_permission_denied"


def _response_code(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "<no-code>"
    return str(payload.get("code", "<no-code>"))


def _build_secure_client(
    runtime_api_env,
    *,
    opa_client,
    claims_by_token: dict[str, UserIdentityClaims],
    raise_server_exceptions: bool = True,
    authz_enforce: bool = True,
    authz_shadow_mode: bool = False,
    delegation_manager: DelegationTokenManager | None = None,
    trusted_delegators: frozenset[str] = frozenset(),
    service_spiffe_id: str | None = None,
):
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    registry.register_cell(cell)

    for tenant_id in (runtime_api_env["tenant_a"], runtime_api_env["tenant_b"]):
        registry.register_tenant(
            TenantSpec(
                tenant_id=tenant_id,
                name=f"tenant-{tenant_id[:8]}",
                region="us-gov-west-1",
            ),
            cell.cell_id,
        )

    provider = _IdentityProvider(claims_by_token=claims_by_token)
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        enable_security_middlewares=True,
        identity_provider=provider,
        cell_registry=registry,
        opa_client=opa_client,
        authz_enforce=authz_enforce,
        authz_shadow_mode=authz_shadow_mode,
        delegation_manager=delegation_manager,
        trusted_delegators=trusted_delegators,
        service_spiffe_id=service_spiffe_id,
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), cell, provider


def _build_permissionless_client(runtime_api_env):
    claims_bearer = _fixture_bearer("permissionless")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=True,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-permissionless",
            roles=frozenset(),
        ),
    )
    return client, claims_bearer


class _AuthorizationAuditCapture:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)


def _install_authorization_audit_capture(client) -> _AuthorizationAuditCapture:
    audit = _AuthorizationAuditCapture()
    client.app.state.runtime_container.runtime_access_audit = audit
    client.app.state.runtime_access_audit = audit
    return audit


@pytest.mark.parametrize("operation", _mutation_operation_params())
def test_mutating_operation_without_permission_is_denied_403(
    operation: tuple[str, str],
    runtime_api_env,
) -> None:
    method, route_path = operation
    permission = _EXPECTED_MUTATING_PERMISSIONS[operation]
    opa = _CaptureOPA()
    bearer = _fixture_bearer(f"matrix-no-permission-{_MUTATING_OPERATION_CASE_IDS[operation]}")
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
            jti=f"jwt-no-permission-{_MUTATING_OPERATION_CASE_IDS[operation]}",
            roles=frozenset(),
        ),
    )
    audit = _install_authorization_audit_capture(client)

    response = client.request(
        method,
        _operation_path(route_path, runtime_api_env),
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "action_permission_denied"
    assert opa.inputs == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["outcome"] == "deny"
    assert audit.entries[0]["denial_reason"] == "action_permission_denied"
    assert audit.entries[0]["permission"] == permission.value


@pytest.mark.parametrize("operation", _mutation_operation_params())
def test_mutating_operation_without_identity_is_denied_401(
    operation: tuple[str, str],
    runtime_api_env,
) -> None:
    method, route_path = operation
    opa = _CaptureOPA()
    client, _cell, _provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    audit = _install_authorization_audit_capture(client)

    response = client.request(
        method,
        _operation_path(route_path, runtime_api_env),
        headers={"X-Tenant-ID": runtime_api_env["tenant_a"]},
        json={},
    )

    assert response.status_code == 401, response.json()
    assert response.json()["code"] == "missing_bearer_token"
    assert opa.inputs == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["outcome"] == "deny"
    assert audit.entries[0]["denial_reason"] == "missing_bearer_token"
    assert audit.entries[0]["subject"] == "anonymous"


@pytest.mark.parametrize("operation", _mutation_operation_params())
def test_mutating_operation_authorized_request_reaches_handler(
    operation: tuple[str, str],
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.step_up import HIGH_STAKES_PERMISSION_CLASSES

    method, _route_path = operation
    permission = _EXPECTED_MUTATING_PERMISSIONS[operation]
    case_id = _MUTATING_OPERATION_CASE_IDS[operation]
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    opa = _CaptureOPA()
    bearer = _fixture_bearer(f"matrix-authorized-{case_id}")
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
            jti=f"jwt-authorized-{case_id}",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }

    with client:
        audit = _install_authorization_audit_capture(client)
        request_path, body = _authorized_mutation_request(
            operation,
            runtime_api_env,
            cell_id=cell.cell_id,
            client=client,
            monkeypatch=monkeypatch,
        )
        expected_step_up = HIGH_STAKES_PERMISSION_CLASSES.get(permission)
        if expected_step_up is not None:
            headers["X-PolicyOS-Step-Up"] = _install_bound_test_step_up(client)
        if case_id == "create-run-human-decision":
            headers["X-PolicyOS-Human-Decision-Exposure"] = "sha256:" + "e" * 64
        request_options = {} if body is None else {"json": body}

        response = client.request(
            method,
            request_path,
            headers=headers,
            **request_options,
        )

    expected_status, expected_code = {
        "admit-epoch-validity-batch": (422, "verifier_not_configured"),
        "create-run-human-decision": (409, "DS9-DECISION-ARTIFACT-MISSING"),
        "create-run-production-approval": (503, "DS9-DECISION-PRODUCER-MISSING"),
    }.get(case_id, (200, None))
    assert response.status_code == expected_status, response.text
    if expected_code is not None:
        assert response.json()["code"] == expected_code
    assert isinstance(response.json(), dict)
    assert len(opa.inputs) == 1
    assert opa.inputs[0].request_method == method
    assert opa.inputs[0].resource_kind
    assert opa.inputs[0].resource_artifact_id
    authorization_events = [
        entry
        for entry in audit.entries
        if entry.get("event_type") == "runtime.authorization.decision"
    ]
    assert len(authorization_events) == 1
    event = authorization_events[0]
    assert event["outcome"] == "allow"
    assert event["permission"] == permission.value
    assert event["resource_id"] == opa.inputs[0].resource_artifact_id
    assert event["resource_digest"].startswith("sha256:")
    if expected_step_up is None:
        assert event["step_up_class"] == ""
        assert event["step_up_outcome"] == "not_required"
    else:
        assert event["step_up_class"] == expected_step_up.value
        assert event["step_up_outcome"] == "verified"


@pytest.mark.parametrize("operation", _high_stakes_mutation_params())
def test_high_stakes_mutating_operation_without_step_up_is_denied(
    operation: tuple[str, str],
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.step_up import HIGH_STAKES_PERMISSION_CLASSES

    method, _route_path = operation
    permission = _EXPECTED_MUTATING_PERMISSIONS[operation]
    expected_step_up = HIGH_STAKES_PERMISSION_CLASSES[permission]
    case_id = _MUTATING_OPERATION_CASE_IDS[operation]
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    opa = _CaptureOPA()
    bearer = _fixture_bearer(f"matrix-no-step-up-{case_id}")
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
            jti=f"jwt-no-step-up-{case_id}",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    with client:
        audit = _install_authorization_audit_capture(client)
        request_path, body = _authorized_mutation_request(
            operation,
            runtime_api_env,
            cell_id=cell.cell_id,
            client=client,
            monkeypatch=monkeypatch,
        )
        request_options = {} if body is None else {"json": body}
        request_headers = {
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        }
        if case_id == "create-run-human-decision":
            request_headers["X-PolicyOS-Human-Decision-Exposure"] = "sha256:" + "e" * 64
        response = client.request(
            method,
            request_path,
            headers=request_headers,
            **request_options,
        )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "step_up_required"
    assert len(opa.inputs) == 1
    authorization_events = [
        entry
        for entry in audit.entries
        if entry.get("event_type") == "runtime.authorization.decision"
    ]
    assert len(authorization_events) == 1
    event = authorization_events[0]
    assert event["outcome"] == "deny"
    assert event["denial_reason"] == "step_up_required"
    assert event["permission"] == permission.value
    assert event["step_up_class"] == expected_step_up.value
    assert event["step_up_outcome"] == "denied"


def test_mutating_routes_have_exactly_one_action_permission_dependency(
    runtime_api_env,
) -> None:
    client, claims_bearer = _build_permissionless_client(runtime_api_env)
    operations = _live_mutating_operations(client.app)
    mutating_routes = _live_mutating_routes(client.app)

    assert operations == _EXPECTED_MUTATING_OPERATIONS, (
        "live mutating-operation denominator drifted:\n" + "\n".join(map(str, operations))
    )
    assert tuple(route.path for route in mutating_routes) == tuple(
        path for _, path in _EXPECTED_MUTATING_OPERATIONS
    )
    structurally_uncovered: list[str] = []
    structurally_duplicated: list[str] = []
    for route in mutating_routes:
        dependencies = _action_permission_dependencies(route)
        methods = ",".join(sorted(route.methods & _UNSAFE_METHODS))
        if not dependencies:
            structurally_uncovered.append(f"{methods} {route.path}")
        elif len(dependencies) > 1:
            structurally_duplicated.append(
                f"{methods} {route.path} -> {len(dependencies)} dependencies"
            )

    behaviorally_uncovered: list[str] = []
    for method, route_path in operations:
        response = client.request(
            method,
            _operation_path(route_path, runtime_api_env),
            headers={
                "Authorization": f"Bearer {claims_bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json={},
        )
        if not _is_action_permission_denial(response):
            behaviorally_uncovered.append(
                f"{method} {route_path} -> {response.status_code} {_response_code(response)}"
            )

    assert not (structurally_uncovered or structurally_duplicated or behaviorally_uncovered), (
        f"{len(structurally_uncovered)} live mutating operations lack exactly one "
        "executable action-permission dependency:\n"
        + "\n".join(structurally_uncovered)
        + f"\n{len(structurally_duplicated)} live mutating operations duplicate the "
        "action-permission dependency:\n"
        + "\n".join(structurally_duplicated)
        + f"\n{len(behaviorally_uncovered)} live mutating operations lack an "
        "action-permission denial:\n" + "\n".join(behaviorally_uncovered)
    )

    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=["assert_mutating_route_authorization_contract"],
    )
    authorization.assert_mutating_route_authorization_contract(client.app)


def test_openapi_mutating_denominator_matches_live_router(runtime_api_env) -> None:
    client, _ = _build_permissionless_client(runtime_api_env)
    schema = client.app.openapi()
    openapi_operations = tuple(
        sorted(
            (method.upper(), path)
            for path, path_item in schema["paths"].items()
            for method in path_item
            if method.upper() in _UNSAFE_METHODS
        )
    )

    assert openapi_operations == _EXPECTED_MUTATING_OPERATIONS
    assert openapi_operations == _live_mutating_operations(client.app)


def test_each_mutating_operation_projects_action_permission_extension(
    runtime_api_env,
) -> None:
    client, _ = _build_permissionless_client(runtime_api_env)
    schema = client.app.openapi()

    for operation, expected_permission in _EXPECTED_MUTATING_PERMISSIONS.items():
        method, path = operation
        openapi_operation = schema["paths"][path][method.lower()]
        assert openapi_operation["x-polisyos-action-permission"] == (expected_permission.value), (
            operation
        )
        resource_binding = openapi_operation["x-polisyos-resource-binding"]
        assert resource_binding["source"]
        assert resource_binding["resource_kind"]


def test_capability_search_routes_share_one_safe_dependency_and_deny_before_handler(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST and compatibility GET must share the exact evidence-discovery gate."""
    client, bearer = _build_permissionless_client(runtime_api_env)
    with client:
        service = client.app.state._control_service
        monkeypatch.setattr(
            service,
            "search_capabilities",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("authorization denial must precede the handler")
            ),
        )
        responses = (
            client.post(
                "/api/v1/control/capabilities/search",
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "X-Tenant-ID": runtime_api_env["tenant_a"],
                },
                json={},
            ),
            client.get(
                "/api/v1/control/data/catalog/search?metric=gdp",
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "X-Tenant-ID": runtime_api_env["tenant_a"],
                },
            ),
        )

    assert [response.status_code for response in responses] == [403, 403]
    assert [response.json()["code"] for response in responses] == [
        "action_permission_denied",
        "action_permission_denied",
    ]

    schema = client.app.openapi()
    for method, path in (
        ("post", "/api/v1/control/capabilities/search"),
        ("get", "/api/v1/control/data/catalog/search"),
    ):
        operation = schema["paths"][path][method]
        assert operation["x-polisyos-action-permission"] == "evidence.discover"
        assert operation["x-polisyos-resource-binding"] == {
            "source": "tenant_collection",
            "resource_kind": "runtime.capability_discovery.search",
            "allow_empty_body": True,
        }


def test_resource_binding_contract_projects_required_selector_and_parent_invariants(
    runtime_api_env,
) -> None:
    client, _ = _build_permissionless_client(runtime_api_env)
    schema = client.app.openapi()

    basin_binding = schema["paths"]["/api/v1/analysis/basin-map"]["post"][
        "x-polisyos-resource-binding"
    ]
    quality_binding = schema["paths"]["/api/v1/fabric/quality/batch"]["post"][
        "x-polisyos-resource-binding"
    ]
    ingest_binding = schema["paths"]["/api/v1/control/data/ingest"]["post"][
        "x-polisyos-resource-binding"
    ]

    assert basin_binding["required_selector_fields"] == ["basin_id"]
    assert quality_binding["parent_required"] is True
    assert ingest_binding["required_selector_alternatives"] == [
        ["datasets"],
        ["fetch_plans"],
    ]


def test_binding_spec_rejects_required_selector_outside_declared_selectors() -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=["ResourceBindingSource", "ResourceBindingSpec"],
    )

    with pytest.raises(ValueError, match="required_selector_fields"):
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.REQUEST_COMPOSITE,
            resource_kind="runtime.ds20.synthetic",
            selector_fields=("declared",),
            required_selector_fields=("undeclared",),
        )

    with pytest.raises(ValueError, match="required_selector_alternatives"):
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.REQUEST_COMPOSITE,
            resource_kind="runtime.ds20.synthetic",
            selector_fields=("declared",),
            required_selector_alternatives=(("undeclared",),),
        )


def test_new_sibling_mutating_route_is_automatically_in_denominator(
    runtime_api_env,
) -> None:
    client, _ = _build_permissionless_client(runtime_api_env)
    app = cast("FastAPI", client.app)

    @app.post("/api/v1/ds20/synthetic-route-31")
    def _unguarded_mutation() -> dict[str, bool]:
        return {"mutated": True}

    operations = _live_mutating_operations(client.app)
    synthetic_route = next(
        route
        for route in _live_mutating_routes(client.app)
        if route.path == "/api/v1/ds20/synthetic-route-31"
    )
    assert ("POST", "/api/v1/ds20/synthetic-route-31") in operations

    dependencies = _action_permission_dependencies(synthetic_route)
    assert not dependencies

    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=["assert_mutating_route_authorization_contract"],
    )
    with pytest.raises(
        RuntimeError,
        match=r"POST /api/v1/ds20/synthetic-route-31",
    ):
        authorization.assert_mutating_route_authorization_contract(app)


def test_mutating_route_marker_without_executable_dependency_fails_app_contract() -> None:
    app = FastAPI()

    def _marker_only_dependency() -> None:
        return None

    setattr(
        _marker_only_dependency,
        _ACTION_PERMISSION_MARKER,
        SimpleNamespace(permission=RuntimePermission.RUNS_LAUNCH),
    )

    @app.post(
        "/api/v1/ds20/marker-only",
        dependencies=[Depends(_marker_only_dependency)],
    )
    def _marker_only_mutation() -> dict[str, bool]:
        return {"mutated": True}

    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=["assert_mutating_route_authorization_contract"],
    )
    with pytest.raises(
        RuntimeError,
        match=r"POST /api/v1/ds20/marker-only",
    ):
        authorization.assert_mutating_route_authorization_contract(app)


def test_mutating_route_without_action_permission_fails_app_contract() -> None:
    app = FastAPI()

    @app.post("/api/v1/ds20/unguarded")
    def _unguarded_mutation() -> dict[str, bool]:
        return {"mutated": True}

    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=["assert_mutating_route_authorization_contract"],
    )
    with pytest.raises(RuntimeError, match=r"POST /api/v1/ds20/unguarded"):
        authorization.assert_mutating_route_authorization_contract(app)


def test_guarded_safe_route_requires_explicit_empty_body_contract() -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "install_route_authorization_openapi_contract",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_REVIEW,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds9.guarded_safe",
        ),
    )
    app = FastAPI()

    @app.get(
        "/api/v1/ds9/guarded-safe",
        dependencies=[Depends(dependency)],
    )
    def _guarded_safe() -> dict[str, bool]:
        return {"guarded": True}

    with pytest.raises(
        RuntimeError,
        match=r"GET /api/v1/ds9/guarded-safe",
    ):
        authorization.install_route_authorization_openapi_contract(app)


def test_mutating_route_with_duplicate_action_permissions_fails_app_contract() -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "assert_mutating_route_authorization_contract",
            "require_action_permission",
        ],
    )
    binding = authorization.ResourceBindingSpec(
        source=authorization.ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.ds20.synthetic",
    )
    first = authorization.require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        resource_binding=binding,
    )
    second = authorization.require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        resource_binding=binding,
    )
    app = FastAPI()

    @app.post(
        "/api/v1/ds20/duplicated",
        dependencies=[Depends(first), Depends(second)],
    )
    def _duplicated_mutation() -> dict[str, bool]:
        return {"mutated": True}

    with pytest.raises(RuntimeError, match=r"POST /api/v1/ds20/duplicated"):
        authorization.assert_mutating_route_authorization_contract(app)


def test_route_requirement_rejects_unknown_permission() -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    binding = authorization.ResourceBindingSpec(
        source=authorization.ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.ds20.synthetic",
    )

    with pytest.raises(TypeError, match="RuntimePermission"):
        authorization.require_action_permission(
            cast("Any", "client.only.permission"),
            resource_binding=binding,
        )


def test_action_permission_dependency_is_load_bearing(runtime_api_env) -> None:
    client, claims_bearer = _build_permissionless_client(runtime_api_env)
    app = cast("FastAPI", client.app)
    route = next(
        route for route in _live_mutating_routes(app) if route.path == "/api/v1/analysis/attractors"
    )
    dependencies = _action_permission_dependencies(route)
    assert len(dependencies) == 1
    dependency = dependencies[0]
    app.dependency_overrides[dependency] = lambda: None

    response = client.post(
        route.path,
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert not _is_action_permission_denial(response), (
        "action_permission_denied remained after overriding the executable dependency; "
        "a global/marker-only guard is substituting for the route dependency"
    )


def test_owned_run_batch_is_bound_before_opa(runtime_api_env) -> None:
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("bound-run-batch")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-bound-run-batch",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )

    response = client.post(
        "/api/v1/runs/batch",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={"run_ids": [runtime_api_env["core_run_id"]]},
    )

    assert response.status_code == 200
    assert len(opa.inputs) == 1
    authz_input = opa.inputs[0]
    assert authz_input.resource_tenant_id == runtime_api_env["tenant_a"]
    assert authz_input.resource_kind == "runtime.run.batch.ownership_verified"
    assert authz_input.resource_artifact_id.startswith(
        "urn:polisyos:runtime-authorization-resource:v1:sha256:"
    )


def test_owned_batch_binding_is_order_independent_and_checks_every_id(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("batch-order")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-batch-order",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {claims_bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    run_ids = [
        runtime_api_env["core_run_id"],
        runtime_api_env["core_run_id_secondary"],
    ]

    forward = client.post("/api/v1/runs/batch", headers=headers, json={"run_ids": run_ids})
    reverse = client.post(
        "/api/v1/runs/batch",
        headers=headers,
        json={"run_ids": list(reversed(run_ids))},
    )
    cross_tenant = client.post(
        "/api/v1/runs/batch",
        headers=headers,
        json={
            "run_ids": [
                runtime_api_env["core_run_id"],
                runtime_api_env["cross_tenant_run_id"],
            ]
        },
    )

    assert forward.status_code == 200
    assert reverse.status_code == 200
    assert len(opa.inputs) == 2
    assert opa.inputs[0].resource_artifact_id == opa.inputs[1].resource_artifact_id
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["code"] == "authorization_binding_run_tenant_mismatch"
    assert len(opa.inputs) == 2


def test_authorization_resource_binds_query_semantics(runtime_api_env) -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.FABRIC_QUALITY_READ,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.REQUEST_COMPOSITE,
            resource_kind="runtime.ds20.query_binding",
            selector_fields=("target",),
            required_selector_fields=("target",),
        ),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("query-binding")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-query-binding",
        ),
    )
    headers = {
        "Authorization": f"Bearer {claims_bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    app = cast("FastAPI", client.app)

    @app.post("/api/v1/ds20/query-binding", dependencies=[Depends(dependency)])
    async def _query_binding(request: Request) -> dict[str, str]:
        return {"query": request.url.query}

    main = client.post(
        "/api/v1/ds20/query-binding",
        headers=headers,
        params={"branch": "main"},
        json={"target": "same"},
    )
    policy_draft = client.post(
        "/api/v1/ds20/query-binding",
        headers=headers,
        params={"branch": "policy-draft"},
        json={"target": "same"},
    )

    assert main.status_code == 200
    assert policy_draft.status_code == 200
    assert len(opa.inputs) == 2
    assert opa.inputs[0].resource_artifact_id != opa.inputs[1].resource_artifact_id


def test_authorization_body_is_replayed_byte_identically(runtime_api_env) -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.REQUEST_COMPOSITE,
            resource_kind="runtime.ds20.body_replay",
            selector_fields=("target",),
            required_selector_fields=("target",),
        ),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("body-replay")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-body-replay",
        ),
    )
    app = cast("FastAPI", client.app)

    @app.post("/api/v1/ds20/body-replay", dependencies=[Depends(dependency)])
    async def _body_replay(request: Request) -> dict[str, str]:
        delivered = await request.body()
        return {
            "sha256": hashlib.sha256(delivered).hexdigest(),
            "body": delivered.decode("utf-8"),
        }

    raw_body = b'{  "ignored" : [3, 2, 1], "target" : "exact" }\n'
    response = client.post(
        "/api/v1/ds20/body-replay",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "Content-Type": "application/json",
        },
        content=raw_body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "sha256": hashlib.sha256(raw_body).hexdigest(),
        "body": raw_body.decode("utf-8"),
    }
    assert len(opa.inputs) == 1


@pytest.mark.parametrize(
    ("raw_body", "extra_headers", "expected_status", "expected_code"),
    [
        (
            b'{"run_ids":["first"],"run_ids":["second"]}',
            {},
            400,
            "authorization_binding_body_invalid",
        ),
        (b"\xff\xfe", {}, 400, "authorization_binding_body_invalid"),
        (
            gzip.compress(b'{"run_ids":["compressed"]}'),
            {"Content-Encoding": "gzip"},
            415,
            "authorization_body_encoding_unsupported",
        ),
    ],
    ids=("duplicate-key", "invalid-utf8", "encoded-body"),
)
def test_malformed_or_encoded_authorization_body_denies_before_opa(
    runtime_api_env,
    raw_body: bytes,
    extra_headers: dict[str, str],
    expected_status: int,
    expected_code: str,
) -> None:
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("malformed-body")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-malformed-body",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )

    response = client.post(
        "/api/v1/runs/batch",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "Content-Type": "application/json",
            **extra_headers,
        },
        content=raw_body,
    )

    assert response.status_code == expected_status, response.json()
    assert response.json()["code"] == expected_code
    assert opa.inputs == []


def test_oversized_authorization_body_denies_before_opa(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_AUTHZ_MAX_BODY_BYTES", "32")
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("oversized-body")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-oversized-body",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )

    response = client.post(
        "/api/v1/runs/batch",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "Content-Type": "application/json",
        },
        content=b'{"run_ids":["' + (b"x" * 64) + b'"]}',
    )

    assert response.status_code == 413, response.json()
    assert response.json()["code"] == "authorization_body_too_large"
    assert opa.inputs == []


def test_production_approval_cross_run_scorecard_denies_before_opa(
    runtime_api_env,
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_ref = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "run_id": runtime_api_env["cross_tenant_run_id"],
            "quality_status": "pass",
            "performance_status": "pass",
            "conflict_status": "pass",
            "approval_state": "approval_ready",
            "quality_gates": [],
            "evidence_refs": {},
        },
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("cross-run-scorecard")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.authz",
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-cross-run-scorecard",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={"quality_scorecard_ref": str(scorecard_ref.artifact_id)},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "authorization_binding_scorecard_run_mismatch"
    assert opa.inputs == []


def test_production_approval_scorecard_without_run_denies_before_opa(
    runtime_api_env,
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_ref = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "quality_status": "pass",
            "performance_status": "pass",
            "conflict_status": "pass",
            "approval_state": "approval_ready",
            "quality_gates": [],
            "evidence_refs": {},
        },
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("scorecard-without-run")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.authz",
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-scorecard-without-run",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    packets_before = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={"quality_scorecard_ref": str(scorecard_ref.artifact_id)},
    )
    packets_after = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "authorization_binding_scorecard_run_unbound"
    assert opa.inputs == []
    assert packets_after == packets_before


@pytest.mark.parametrize(
    "schema_version",
    [
        pytest.param(None, id="absent"),
        pytest.param("client.asserted.scorecard.v1", id="wrong"),
    ],
)
def test_production_approval_invalid_scorecard_schema_denies_before_opa_and_persistence(
    runtime_api_env,
    schema_version: str | None,
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_payload = {
        "run_id": runtime_api_env["core_run_id"],
        "quality_status": "pass",
        "performance_status": "pass",
        "conflict_status": "pass",
        "approval_state": "approval_ready",
        "quality_gates": [],
        "evidence_refs": {},
    }
    if schema_version is not None:
        scorecard_payload["schema_version"] = schema_version
    scorecard_ref = store.put_json(
        scorecard_payload,
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer(f"scorecard-schema-{schema_version or 'absent'}")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.authz",
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-scorecard-schema-{schema_version or 'absent'}",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    packets_before = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={"quality_scorecard_ref": str(scorecard_ref.artifact_id)},
    )
    packets_after = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "authorization_binding_scorecard_schema_invalid"
    assert opa.inputs == []
    assert packets_after == packets_before


def test_production_approval_wrong_artifact_kind_denies_before_opa(
    runtime_api_env,
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_ref = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "run_id": runtime_api_env["core_run_id"],
            "quality_status": "pass",
            "performance_status": "pass",
            "conflict_status": "pass",
            "approval_state": "approval_ready",
            "quality_gates": [],
            "evidence_refs": {},
        },
        ArtifactWriteOptions(
            kind="runtime.client_asserted_json",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("scorecard-wrong-kind")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.authz",
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-scorecard-wrong-kind",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={"quality_scorecard_ref": str(scorecard_ref.artifact_id)},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "authorization_binding_scorecard_kind_invalid"
    assert opa.inputs == []


def test_production_approval_ignores_client_overlay_output_path(
    runtime_api_env,
    tmp_path,
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    scorecard_ref = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "run_id": runtime_api_env["core_run_id"],
            "execution_status": "completed",
            "quality_status": "pass",
            "performance_status": "pass",
            "conflict_status": "pass",
            "approval_state": "approval_ready",
            "quality_gates": [],
            "blocking_quality_failures": [],
            "evidence_refs": {},
        },
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("scorecard-overlay-path")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.authz",
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-scorecard-overlay-path",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    attacker_path = tmp_path / "attacker-controlled-evidence"
    step_up_assertion = _install_bound_test_step_up(client)

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": step_up_assertion,
        },
        json={
            "quality_scorecard": {
                "quality_scorecard_ref": str(scorecard_ref.artifact_id),
                "quality_evidence_bundle_path": str(attacker_path),
            },
            **_production_approval_required_input_refs(),
        },
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "DS9-DECISION-PRODUCER-MISSING"
    assert not attacker_path.exists()
    assert len(opa.inputs) == 1


def test_production_approval_never_executes_persisted_scorecard_output_path(
    runtime_api_env,
    tmp_path,
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    attacker_path = tmp_path / "artifact-authored-host-write" / "approval.json"
    scorecard_ref = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "run_id": runtime_api_env["core_run_id"],
            "execution_status": "completed",
            "quality_status": "pass",
            "performance_status": "pass",
            "conflict_status": "pass",
            "approval_state": "approval_ready",
            "quality_gates": [],
            "blocking_quality_failures": [],
            "evidence_refs": {},
            "quality_evidence_bundle_path": str(attacker_path),
        },
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("persisted-scorecard-output-path")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    store.record_artifact_owner(
        scorecard_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds20.authz",
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-persisted-scorecard-output-path",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    step_up_assertion = _install_bound_test_step_up(client)

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": step_up_assertion,
        },
        json={
            "quality_scorecard_ref": str(scorecard_ref.artifact_id),
            **_production_approval_required_input_refs(),
        },
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "DS9-DECISION-PRODUCER-MISSING"
    assert not attacker_path.exists()
    assert len(opa.inputs) == 1


def test_scenario_id_collision_across_runs_denies_before_opa(runtime_api_env) -> None:
    opa = _CaptureOPA()
    tenant_b_bearer = _fixture_bearer("scenario-owner")
    tenant_a_bearer = _fixture_bearer("scenario-collision")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        tenant_b_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-scenario-owner",
        ),
    )
    provider.put_claim(
        tenant_a_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-scenario-collision",
        ),
    )
    tenant_b_headers = {
        "Authorization": f"Bearer {tenant_b_bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_b"],
    }
    tenant_a_headers = {
        "Authorization": f"Bearer {tenant_a_bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    assert quantity_response.status_code == 200
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = _scenario_create_body(
        scenario_id="scn_ds20_cross_run_collision",
        quantity=quantity,
    )
    with client:
        created = client.post(
            f"/api/v1/runs/{runtime_api_env['cross_tenant_run_id']}/scenarios",
            headers=tenant_b_headers,
            json=body,
        )
        assert created.status_code == 200, created.json()
        opa.inputs.clear()

        collision = client.post(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios",
            headers=tenant_a_headers,
            json=body,
        )

    assert collision.status_code == 403, collision.json()
    assert collision.json()["code"] == "authorization_binding_scenario_parent_mismatch"
    assert opa.inputs == []


def test_scenario_write_rechecks_authorized_revision(runtime_api_env) -> None:
    opa = _InterleavingOPA()
    claims_bearer = _fixture_bearer("scenario-revision-race")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-scenario-revision-race",
        ),
    )
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    assert quantity_response.status_code == 200
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = _scenario_create_body(
        scenario_id="scn_ds20_revision_race",
        quantity=quantity,
    )
    scenario_request = ScenarioCreateRequest.model_validate(body)
    with client:
        ctx = client.app.state.runtime_container.runtime_api_context
        run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
        opa.callback = lambda: ctx.scenarios.create_for_run(
            run=run,
            request=scenario_request,
            temporal_scope=None,
        )

        response = client.post(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios",
            headers={
                "Authorization": f"Bearer {claims_bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )

    assert response.status_code == 409, response.json()
    assert response.json()["code"] == "scenario_authorization_binding_changed"
    assert len(opa.inputs) == 1


def test_scenario_mutation_without_durable_head_store_denies_before_opa(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    bearer = _fixture_bearer("scenario-head-store-unavailable")
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
            jti="jwt-scenario-head-store-unavailable",
        ),
    )
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = _scenario_create_body(
        scenario_id="scn_ds20_head_store_unavailable",
        quantity=quantity,
    )

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios",
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json=body,
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "scenario_head_store_unavailable"
    assert opa.inputs == []


def test_scenario_authorization_binding_two_apps_same_revision_allows_one_mutation(
    runtime_api_env,
) -> None:
    barrier = threading.Barrier(2)
    first_opa = _BarrierOPA(barrier)
    second_opa = _BarrierOPA(barrier)
    bearer = _fixture_bearer("scenario-two-app-race")
    first_client, first_cell, first_provider = _build_secure_client(
        runtime_api_env,
        opa_client=first_opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    second_client, second_cell, second_provider = _build_secure_client(
        runtime_api_env,
        opa_client=second_opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    first_provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=first_cell.cell_id,
            jti="jwt-scenario-two-app-first",
        ),
    )
    second_provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=second_cell.cell_id,
            jti="jwt-scenario-two-app-second",
        ),
    )
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    first_body = _scenario_create_body(
        scenario_id="scn_ds20_two_app_race",
        quantity=quantity,
    )
    first_body["policy_question"] = "First contender"
    second_body = _scenario_create_body(
        scenario_id="scn_ds20_two_app_race",
        quantity=quantity,
    )
    second_body["policy_question"] = "Second contender"
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"

    def _post(client: TestClient, cell_id: str, body: dict[str, Any]):
        del cell_id
        return client.post(
            path,
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )

    with first_client, second_client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                _post,
                first_client,
                first_cell.cell_id,
                first_body,
            )
            second_future = executor.submit(
                _post,
                second_client,
                second_cell.cell_id,
                second_body,
            )
            responses = [first_future.result(), second_future.result()]
        heads = [
            client.app.state._control_service.scenario_head_store.get_scenario_head(
                "scn_ds20_two_app_race"
            )
            for client in (first_client, second_client)
        ]

    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["code"] == "scenario_authorization_binding_changed"
    assert heads[0] is not None and heads[0] == heads[1]
    assert heads[0].revision == 1
    assert heads[0].manifest_hash == winner.json()["scenario"]["manifest_hash"]
    assert len(first_opa.inputs) == 1
    assert len(second_opa.inputs) == 1


def test_persisted_default_scenario_head_wins_list_projection(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    path = f"/api/v1/runs/{run_id}/scenarios"
    quantity_response = client.get(f"/api/v1/runs/{run_id}/quantities")
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )

    initial = client.get(path)
    assert initial.status_code == 200, initial.json()
    default_id = initial.json()["scenarios"][0]["id"]
    body = _scenario_create_body(
        scenario_id=default_id,
        quantity=quantity,
    )
    body["policy_question"] = "Persisted default-slot authority"
    created = client.post(path, json=body)
    listed = client.get(path)

    assert created.status_code == 200, created.json()
    assert listed.status_code == 200, listed.json()
    authoritative = [
        scenario for scenario in listed.json()["scenarios"] if scenario["id"] == default_id
    ]
    assert len(authoritative) == 1
    assert authoritative[0]["policy_question"] == body["policy_question"]
    assert authoritative[0]["manifest_hash"] == created.json()["scenario"]["manifest_hash"]
    assert authoritative[0]["revision"] == 1


def test_scenario_head_content_mismatch_denies_before_opa(runtime_api_env) -> None:
    opa = _CaptureOPA()
    bearer = _fixture_bearer("scenario-head-content-mismatch")
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
            jti="jwt-scenario-head-content-mismatch",
        ),
    )
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = _scenario_create_body(
        scenario_id="scn_ds20_head_content_mismatch",
        quantity=quantity,
    )
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"

    with client:
        created = client.post(
            path,
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )
        assert created.status_code == 200, created.json()
        opa.inputs.clear()
        sqlite_path = runtime_api_env["cas_root"] / "control_plane.sqlite3"
        with sqlite3.connect(sqlite_path) as connection:
            connection.execute(
                "UPDATE runtime_scenario_heads SET manifest_hash = ? WHERE scenario_id = ?",
                ("sha256:corrupted-head", body["id"]),
            )
            connection.commit()

        response = client.post(
            path,
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "scenario_head_content_mismatch"
    assert opa.inputs == []


def test_scenario_head_change_during_binding_denies_before_opa(
    monkeypatch: pytest.MonkeyPatch,
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    bearer = _fixture_bearer("scenario-head-binding-race")
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
            jti="jwt-scenario-head-binding-race",
        ),
    )
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = _scenario_create_body(
        scenario_id="scn_ds20_head_binding_race",
        quantity=quantity,
    )
    scenario_request = ScenarioCreateRequest.model_validate(body)
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"

    with client:
        created = client.post(
            path,
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )
        assert created.status_code == 200, created.json()
        opa.inputs.clear()
        ctx = client.app.state.runtime_container.runtime_api_context
        run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
        original_resolve = ctx.scenarios.get_persisted_manifest_for_head
        interleaved = False

        def _interleave_head_update(head):
            nonlocal interleaved
            if not interleaved:
                interleaved = True
                ctx.scenarios.create_for_run(
                    run=run,
                    request=scenario_request,
                    temporal_scope=None,
                )
            return original_resolve(head)

        monkeypatch.setattr(
            ctx.scenarios,
            "get_persisted_manifest_for_head",
            _interleave_head_update,
        )
        response = client.post(
            path,
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )

    assert response.status_code == 409, response.json()
    assert response.json()["code"] == "scenario_authorization_binding_changed"
    assert opa.inputs == []


def test_unheaded_scenario_candidate_artifact_is_never_selected(runtime_api_env) -> None:
    from polisyos.runtime.http.services.scenarios import _finalize_manifest_hash

    bearer = _fixture_bearer("scenario-unheaded-candidate")
    first_client, first_cell, first_provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    first_provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=first_cell.cell_id,
            jti="jwt-scenario-unheaded-first",
        ),
    )
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    body = _scenario_create_body(
        scenario_id="scn_ds20_unheaded_candidate",
        quantity=quantity,
    )
    body["policy_question"] = "Authoritative winner"
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"

    with first_client:
        created = first_client.post(
            path,
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json=body,
        )
        assert created.status_code == 200, created.json()
        winner = ScenarioManifest.model_validate(created.json()["scenario"])
        head = first_client.app.state._control_service.scenario_head_store.get_scenario_head(
            winner.id
        )
        assert head is not None

    unheaded = _finalize_manifest_hash(
        winner.model_copy(update={"policy_question": "Unheaded losing candidate"})
    )
    store = FileSystemCAS(runtime_api_env["cas_root"])
    unheaded_ref = store.put_json(
        unheaded.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="runtime.scenario_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.runtime.scenario_manifest", version="1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert str(unheaded_ref.artifact_id) != head.artifact_ref

    second_client, second_cell, second_provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    second_provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=second_cell.cell_id,
            jti="jwt-scenario-unheaded-second",
        ),
    )
    with second_client:
        fetched = second_client.get(
            f"/api/v1/scenarios/{winner.id}",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )

    assert fetched.status_code == 200, fetched.json()
    assert fetched.json()["scenario"]["policy_question"] == "Authoritative winner"
    assert fetched.json()["scenario"]["manifest_hash"] == head.manifest_hash


def test_resolved_promotion_selector_never_claims_caller_tenant(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("unscoped-promotion")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-unscoped-promotion",
        ),
    )
    step_up_assertion = _install_bound_test_step_up(client)
    with client:
        control = client.app.state._control_service
        retrieval = control._retrieval
        candidate = PromotionCandidate(
            promotion_id="promotion-ds20-unscoped",
            metric_id="metric.ds20",
            connector_id="connector.ds20",
            dataset_id="dataset.ds20",
            confidence=0.9,
        )
        with retrieval._state_lock:
            retrieval._store_promotion_candidate_locked(candidate)

        response = client.post(
            f"/api/v1/control/data/promotion/{candidate.promotion_id}/approve",
            headers={
                "Authorization": f"Bearer {claims_bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": step_up_assertion,
            },
            json={"reason": "verify limited authority"},
        )

    assert response.status_code == 200
    assert len(opa.inputs) == 1
    assert opa.inputs[0].resource_tenant_id == ""
    assert opa.inputs[0].resource_kind.endswith(".content_resolved_unscoped")


def test_missing_alternative_resource_selectors_are_denied_before_opa(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("missing-selector-alternative")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-missing-selector-alternative",
        ),
    )

    response = client.post(
        "/api/v1/control/data/ingest",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "authorization_binding_selector_alternative_required"
    assert opa.inputs == []


def test_guarded_human_decision_get_binds_owned_run_and_exact_path_before_opa(
    runtime_api_env,
) -> None:
    """Safe authority reads must not reach OPA on an ambient tenant-only resource."""

    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_REVIEW,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.OWNED_EXISTING_PATH,
            resource_kind="runtime.run.human_decision_record",
            path_parameter="run_id",
            query_selector_parameters=("record_ref",),
            allow_empty_body=True,
        ),
    )
    opa = _CaptureOPA()
    bearer = _fixture_bearer("guarded-human-decision-get")
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
            jti="jwt-guarded-human-decision-get",
        ),
    )
    app = cast("FastAPI", client.app)

    @app.get(
        "/api/v1/ds9/runs/{run_id}/human-decisions",
        dependencies=[Depends(dependency)],
    )
    def _guarded_human_decision_get(
        request: Request,
        run_id: str,
        record_ref: str,
    ) -> dict[str, str]:
        proof = dependency(request)
        return {
            "proof_type": type(proof).__name__,
            "run_id": run_id,
            "record_ref": record_ref,
        }

    response = client.get(
        f"/api/v1/ds9/runs/{runtime_api_env['core_run_id']}/human-decisions",
        params={"record_ref": "sha256:" + "a" * 64},
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    changed_selector = client.get(
        f"/api/v1/ds9/runs/{runtime_api_env['core_run_id']}/human-decisions",
        params={"record_ref": "sha256:" + "b" * 64},
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 200, response.json()
    assert changed_selector.status_code == 200, changed_selector.json()
    assert response.json()["proof_type"] == "BoundActionPermissionVerification"
    assert len(opa.inputs) == 2
    assert opa.inputs[0].resource_tenant_id == runtime_api_env["tenant_a"]
    assert opa.inputs[0].resource_kind.endswith(".ownership_verified")
    assert opa.inputs[0].resource_artifact_id.startswith(
        "urn:polisyos:runtime-authorization-resource:v1:sha256:"
    )
    assert opa.inputs[0].resource_artifact_id != opa.inputs[1].resource_artifact_id


def test_all_human_decision_gets_declare_exact_owned_run_bindings(
    runtime_api_env,
) -> None:
    from polisyos.runtime.http.authorization import (
        get_route_authorization_requirement,
    )

    expected = {
        "/api/v1/runs/{run_id}/human-decision-gate": (
            "runtime.run.human_decision_gate",
            (),
            ("source_kind",),
        ),
        "/api/v1/runs/{run_id}/human-decisions": (
            "runtime.run.human_decision_record",
            (),
            ("record_ref",),
        ),
        "/api/v1/runs/{run_id}/human-decisions/review-effectiveness": (
            "runtime.run.human_decision_review_effectiveness",
            (),
            (),
        ),
        "/api/v1/runs/{run_id}/human-decision-evidence/{artifact_id}/content": (
            "runtime.run.human_decision_evidence",
            ("artifact_id",),
            (),
        ),
    }
    routes = {
        route.path: route
        for route in runtime_api_env["app"].routes
        if isinstance(route, APIRoute) and route.methods == {"GET"}
    }

    for path, (resource_kind, path_selectors, query_selectors) in expected.items():
        requirement = get_route_authorization_requirement(cast("Any", routes[path]))
        binding = requirement.resource_binding
        assert requirement.permission is RuntimePermission.RUNS_REVIEW
        assert binding.resource_kind == resource_kind
        assert binding.path_parameter == "run_id"
        assert binding.path_selector_parameters == path_selectors
        assert binding.query_selector_parameters == query_selectors


def test_late_unguarded_mutation_is_denied_before_opa_and_handler(runtime_api_env) -> None:
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("late-unguarded")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-late-unguarded",
        ),
    )
    app = cast("FastAPI", client.app)
    mutation = {"executed": False}

    @app.post("/api/v1/ds20/late-unguarded")
    def _late_unguarded_mutation() -> dict[str, bool]:
        mutation["executed"] = True
        return {"mutated": True}

    response = client.post(
        "/api/v1/ds20/late-unguarded",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "authorization_contract_violation"
    assert opa.inputs == []
    assert mutation == {"executed": False}


@pytest.mark.parametrize(
    ("authz_enforce", "authz_shadow_mode"),
    [
        pytest.param(False, False, id="enforcement-disabled"),
        pytest.param(True, True, id="shadow-mode"),
    ],
)
def test_unsafe_mutation_cannot_shadow_or_disable_opa_deny(
    runtime_api_env,
    authz_enforce: bool,
    authz_shadow_mode: bool,
) -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.opa_deny_probe",
            allow_empty_body=True,
        ),
    )
    claims_bearer = _fixture_bearer(f"unsafe-opa-deny-{authz_enforce}-{authz_shadow_mode}")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_DenyOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
        authz_enforce=authz_enforce,
        authz_shadow_mode=authz_shadow_mode,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-unsafe-opa-deny-{authz_enforce}-{authz_shadow_mode}",
        ),
    )
    app = cast("FastAPI", client.app)
    mutation = {"executed": False}

    @app.post(
        f"/api/v1/ds20/unsafe-opa-deny-{authz_enforce}-{authz_shadow_mode}",
        dependencies=[Depends(dependency)],
    )
    def _unsafe_opa_deny_probe() -> dict[str, bool]:
        mutation["executed"] = True
        return {"mutated": True}

    response = client.post(
        f"/api/v1/ds20/unsafe-opa-deny-{authz_enforce}-{authz_shadow_mode}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "authorization_denied"
    assert mutation == {"executed": False}


def test_delegated_effective_scope_governs_binding_and_execution_policy(
    monkeypatch: pytest.MonkeyPatch,
    runtime_api_env,
) -> None:
    import polisyos.runtime.http.authz_middleware as authz_middleware_module
    from polisyos.core.security.tenant_context import get_current_access_scope_or_none
    from polisyos.runtime.http.step_up import StepUpClass, require_step_up

    class _ScopeCaptureOPA:
        def __init__(self) -> None:
            self.scopes: list[AccessScope | None] = []

        async def check(self, authz_input):
            del authz_input
            self.scopes.append(get_current_access_scope_or_none())
            return AuthzResult(
                decision=AuthzDecision.ALLOW,
                policy="polisyos/authz/decision",
            )

    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.delegation_probe",
        ),
    )
    admin_only_dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.delegation_admin_probe",
        ),
    )
    admin_only_step_up = require_step_up(StepUpClass.PRODUCTION_APPROVAL)
    manager = DelegationTokenManager(
        signing_key="ds20-delegation-secret-at-least-32-bytes",
        ttl_seconds=60,
    )
    delegator = "spiffe://polisyos.test/delegator"
    audience = "spiffe://polisyos.test/runtime-api"
    claims_bearer = _fixture_bearer("delegated-admin")
    opa = _ScopeCaptureOPA()
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=True,
        delegation_manager=manager,
        trusted_delegators=frozenset({delegator}),
        service_spiffe_id=audience,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-original-admin",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    delegated_scope = AccessScope(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        principal_type="user",
        user_sub="delegated-analyst",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.LOW,
        mfa_verified=True,
        jwt_jti="jwt-delegated-analyst",
    )
    delegation_token = manager.issue_token(
        scope=delegated_scope,
        issuer=delegator,
        audience=audience,
    )
    headers = {
        "Authorization": f"Bearer {claims_bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
        "X-PolicyOS-Context": delegation_token,
        "l5d-client-id": delegator,
    }
    observed_binding_scopes: list[AccessScope | None] = []
    original_bind = authz_middleware_module.bind_authorization_resource

    def _capture_binding_scope(*args, **kwargs):
        observed_binding_scopes.append(get_current_access_scope_or_none())
        return original_bind(*args, **kwargs)

    monkeypatch.setattr(
        authz_middleware_module,
        "bind_authorization_resource",
        _capture_binding_scope,
    )
    app = cast("FastAPI", client.app)
    admin_only_mutation = {"executed": False}

    @app.post(
        "/api/v1/ds20/delegation-binding-probe",
        dependencies=[Depends(dependency)],
    )
    def _delegation_binding_probe() -> dict[str, bool]:
        return {"mutated": True}

    @app.post(
        "/api/v1/ds20/delegation-admin-only-probe",
        dependencies=[Depends(admin_only_dependency), Depends(admin_only_step_up)],
    )
    def _delegation_admin_only_probe() -> dict[str, bool]:
        admin_only_mutation["executed"] = True
        return {"mutated": True}

    with client:
        binding_response = client.post(
            "/api/v1/ds20/delegation-binding-probe",
            headers=headers,
            json={},
        )
        binding_count = len(observed_binding_scopes)
        opa_count = len(opa.scopes)
        admin_only_response = client.post(
            "/api/v1/ds20/delegation-admin-only-probe",
            headers=headers,
            json={},
        )
        assert admin_only_response.status_code == 403, admin_only_response.json()
        assert admin_only_response.json()["code"] == "action_permission_denied"
        assert len(observed_binding_scopes) == binding_count
        assert len(opa.scopes) == opa_count
        assert admin_only_mutation == {"executed": False}
        execution_response = client.post(
            "/api/v1/control/runs/nl",
            headers=headers,
            json={
                "request": "Verify delegated execution-policy authority",
                "policy_flags": {"allow_mock_fallback": True},
            },
        )

    assert binding_response.status_code == 200, binding_response.json()
    assert observed_binding_scopes
    assert all(scope is not None for scope in observed_binding_scopes)
    assert all(scope.user_sub == "delegated-analyst" for scope in observed_binding_scopes if scope)
    assert all(
        scope.roles == frozenset({PolicyOSRole.ANALYST})
        for scope in observed_binding_scopes
        if scope
    )
    assert opa.scopes
    assert all(scope is not None for scope in opa.scopes)
    assert all(scope.user_sub == "delegated-analyst" for scope in opa.scopes if scope)
    assert execution_response.status_code == 403, execution_response.json()
    assert execution_response.json()["code"] == "policy_flag_forbidden"
    audit_path = runtime_api_env["cas_root"] / "runtime" / "audit" / "mutations.jsonl"
    audit_entries = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    execution_audits = [
        entry for entry in audit_entries if entry["endpoint"] == "/api/v1/control/runs/nl"
    ]
    assert execution_audits
    assert execution_audits[-1]["actor"] == "delegated-analyst"
    assert execution_audits[-1]["outcome"] == "rejected"


def test_handler_cannot_replace_frozen_authorization_resource(runtime_api_env) -> None:
    authorization = __import__(
        "polisyos.runtime.http.authorization",
        fromlist=[
            "ResourceBindingSource",
            "ResourceBindingSpec",
            "require_action_permission",
        ],
    )
    dependency = authorization.require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        authorization.ResourceBindingSpec(
            source=authorization.ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.rebind_probe",
        ),
    )
    opa = _CaptureOPA()
    claims_bearer = _fixture_bearer("malicious-rebind")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-malicious-rebind",
        ),
    )
    app = cast("FastAPI", client.app)

    @app.post(
        "/api/v1/ds20/malicious-rebind",
        dependencies=[Depends(dependency)],
    )
    def _malicious_rebind(request: Request) -> dict[str, bool]:
        request.state.authz_bound_resource = object()
        return {"mutated": True}

    response = client.post(
        "/api/v1/ds20/malicious-rebind",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
        json={},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "authorization_binding_integrity_violation"
    assert len(opa.inputs) == 1


def test_runtime_api_allows_tenant_scoped_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 200


def test_runtime_api_denies_cross_tenant_run_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("b")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-b",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    payload = response.json()
    assert payload["code"] == "run_tenant_mismatch"


def test_runtime_api_authz_deny_blocks_endpoint(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_DenyOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-deny",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["error"] == "authorization_denied"


def test_runtime_api_authz_timeout_returns_gateway_timeout(
    monkeypatch: pytest.MonkeyPatch,
    runtime_api_env,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_OPA_TIMEOUT_SECONDS", "0.05")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_SlowOPA(),
        claims_by_token={},
    )
    claims_bearer = _fixture_bearer("a-timeout")
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-timeout",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 504
    assert response.json()["code"] == "authz_dependency_timeout"


def test_runtime_api_denies_cross_tenant_artifact_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("b")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-b-artifact",
        ),
    )

    response = client.get(
        f"/api/v1/artifacts/{runtime_api_env['workflow_report_artifact_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["code"] == "artifact_tenant_mismatch"


def test_runtime_api_denies_unscoped_artifact_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-unscoped-artifact",
        ),
    )

    response = client.get(
        f"/api/v1/artifacts/{runtime_api_env['root_artifact_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["code"] == "artifact_tenant_unscoped"


def test_runtime_api_rejects_missing_claims_fail_closed(runtime_api_env) -> None:
    client, _, _ = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={"X-Tenant-ID": runtime_api_env["tenant_a"]},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "missing_bearer_token"


def test_runtime_api_auth_me_requires_claims_without_explicit_fixture_flag(runtime_api_env) -> None:
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        allow_fixture_identity=False,
    )
    client = TestClient(app)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "missing_access_scope"


def test_runtime_api_cross_tenant_compare_requires_explicit_capability(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-compare",
        ),
    )

    response = client.get(
        (
            f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}"
            f"/compare/{runtime_api_env['cross_tenant_run_id']}"
        ),
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "cross_tenant_compare_forbidden"


def test_runtime_security_middleware_order_guard_detects_reordering(runtime_api_env) -> None:
    client, _, _ = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    app = client.app

    _assert_runtime_security_middleware_order(
        app,
        security_middlewares_enabled=True,
    )

    app.user_middleware[0], app.user_middleware[1] = app.user_middleware[1], app.user_middleware[0]
    with pytest.raises(RuntimeError):
        _assert_runtime_security_middleware_order(
            app,
            security_middlewares_enabled=True,
        )


def test_review_websocket_rejects_anonymous_connect(runtime_api_env) -> None:
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        allow_fixture_identity=False,
    )
    client = TestClient(app)

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(
            f"/api/v1/review/live?channel=review.presence&review_id=run:{runtime_api_env['core_run_id']}:governance"
        ),
    ):
        pass

    assert exc.value.code == 4401


def test_review_websocket_rechecks_message_authorization(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_SelectiveReviewOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-review",
        ),
    )

    with client.websocket_connect(
        (
            f"/api/v1/review/live?channel=review.cursor"
            f"&review_id=run:{runtime_api_env['core_run_id']}:governance"
        ),
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    ) as websocket:
        assert websocket.receive_json()["type"] == "cursor.snapshot"
        websocket.send_json({"type": "cursor.update", "x": 0.2, "y": 0.4})
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_json()

    assert exc.value.code == 4403
