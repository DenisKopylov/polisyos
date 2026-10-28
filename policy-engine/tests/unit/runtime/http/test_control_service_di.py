from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import copyfile
from threading import Condition, Event
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
from polisyos.common.async_tools import get_shared_executor
from polisyos.core import canon
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import (
    IngestRequest,
    NaturalLanguageRunRequest,
    WorkflowRunRequest,
)
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.tenant_context import (
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.execution_policy import (
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
)
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyAdmissionVerifier,
    EvaluationSafetyPersistenceService,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_registry_providers import (
    ControlRegistryProviders,
    resolve_control_registry_providers,
)
from polisyos.runtime.http.services.task_runner import TaskRunner
from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyConsumerAdmissionReceipt,
    EvaluationExecutionContext,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import (
    N4GenerationPort,
    simulation_value_execution_context,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    build_default_recursive_generation_cycle_controller,
)
from polisyos.scientist.evidence.claims.head_index import UnappointedClaimLedgerOwner
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import (
    _build_control_service,
    _build_registry_providers,
    _NoOpRetrievalService,
)
from tests.unit.runtime.http.control_service_test_support import (
    bound_nl_authorization_proof,
)

try:  # pragma: no cover - optional runtime dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


class _NeverCalledEvalSafetyVerifier:
    def require_admission(
        self,
        context: EvaluationExecutionContext,
        challenge: EvalSafetyAdmissionChallenge,
    ) -> EvalSafetyConsumerAdmissionReceipt:
        del context, challenge
        raise AssertionError("simulation-only control fixture called EvalSafety verifier")


def _explicit_simulation_execution_context(problem: object) -> EvaluationExecutionContext:
    from tests.unit.runtime.quality.test_value_gate import (
        _candidate,
        _simulation,
        _world_record,
    )

    candidate = _candidate()
    return simulation_value_execution_context(
        candidate=candidate,
        simulation=_simulation(_world_record()),
        problem=problem,
    )


def _fixture_claims() -> UserIdentityClaims:
    return UserIdentityClaims(
        sub="user-fixture",
        email="fixture@example.test",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        roles=frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss="https://idp.example/realms/polisyos",
        aud="polisyos-web",
        exp=9_999_999_999,
        iat=1,
        jti="jwt-fixture",
    )


def _install_fixture_tenant_lifespan(app: Any) -> None:
    """Keep the fixture's declared owner active in the API lifespan task."""
    from contextlib import asynccontextmanager

    from polisyos.core.security.tenant_context import tenant_scope

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def fixture_tenant_lifespan(application: Any) -> AsyncIterator[Any]:
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            async with original_lifespan(application) as lifespan_state:
                yield lifespan_state

    app.router.lifespan_context = fixture_tenant_lifespan


def test_runtime_api_defaults_core_runs_root_to_cas_runs(tmp_path) -> None:
    cas_root = tmp_path / ".polisyos" / "cas"

    app = create_runtime_api_app(cas_root=cas_root)

    assert app.state.runtime_api_ctx.core_runs_root == cas_root / "runs"
    assert app.state.runtime_container.config.core_runs_root == cas_root / "runs"
    assert app.state.runtime_container.config.catalog_run_profile is None
    assert app.state.runtime_container.control_registry_providers.catalog_run_profile is None
    cache_root = tmp_path / "runtime-http-cache"
    assert os.environ["POLISYOS_CACHE_HOME"] == cache_root.as_posix()
    catalog_graph = app.state.runtime_container.control_registry_providers.gy_catalog_graph
    assert catalog_graph is not None
    assert catalog_graph._store._db_path.is_relative_to(cache_root)


def test_runtime_api_preserves_explicit_catalog_run_profile(tmp_path) -> None:
    app = create_runtime_api_app(
        cas_root=tmp_path / "configured-profile" / "cas",
        catalog_run_profile="prod_core_blocking",
    )

    assert app.state.runtime_container.config.catalog_run_profile == "prod_core_blocking"
    assert (
        app.state.runtime_container.control_registry_providers.catalog_run_profile
        == "prod_core_blocking"
    )


def test_data_resolve_uses_server_profile_and_refuses_conflict(tmp_path) -> None:
    from types import SimpleNamespace

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest

    service = _build_control_service(tmp_path, catalog_run_profile="prod_full")
    observed: list[str | None] = []

    class RecordingRetrieval:
        def resolve(self, request, *, run_profile=None):
            observed.append(run_profile)
            return SimpleNamespace(
                mode=request.mode,
                fetch_plans=[],
                candidates=[],
                warnings=[],
            )

        def close(self) -> None:
            return None

    service._retrieval = RecordingRetrieval()
    try:
        service.data_resolve(DataResolveRequest(data_needs=[DataNeed(metric="fixture.metric")]))
        assert observed == ["prod_full"]

        with pytest.raises(RuntimeHTTPError) as conflict_error:
            service.data_resolve(
                DataResolveRequest(
                    data_needs=[DataNeed(metric="fixture.metric")],
                    catalog_run_profile="rest_backfill",
                )
            )
        assert conflict_error.value.status_code == 422
        assert conflict_error.value.code == "catalog_run_profile_conflict"
        assert observed == ["prod_full"]
    finally:
        service.close()


@pytest.mark.asyncio
async def test_control_service_forwards_catalog_profile_to_recursive_http_bridge(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path, catalog_run_profile="prod_full")
    observed: dict[str, object] = {}

    async def record_bridge_arguments(**kwargs: object) -> object:
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(
        generation_cycle_service,
        "compile_and_run_recursive_generation_cycle",
        record_bridge_arguments,
    )
    try:
        result = await service.compile_and_run_recursive_generation_cycle(
            raw_request="controlled profile bridge request",
            context={},
            model_name="fixture-model",
            compiler_gateway=None,
            budget_state=object(),  # type: ignore[arg-type]
            recursive_budget=RecursiveCycleBudget(
                max_depth=0,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
        )

        assert observed["catalog_run_profile"] == "prod_full"
        assert result is not None
    finally:
        service.close()


def test_runtime_container_exposes_one_promotion_owner_runtime(tmp_path) -> None:
    app = create_runtime_api_app(cas_root=tmp_path / ".polisyos" / "cas")

    assert app.state.promotion_runtime is app.state.runtime_container.promotion_runtime
    assert app.state.promotion_runtime.resolver is (
        app.state.runtime_container.promotion_runtime.resolver
    )


@pytest.mark.parametrize(
    ("override_name", "failure_code"),
    [
        ("decision_validity_service", "decision_validity_owner_invalid"),
        ("control_service", "control_service_owner_invalid"),
    ],
)
def test_runtime_container_types_malformed_owner_overrides(
    tmp_path,
    override_name: str,
    failure_code: str,
) -> None:
    overrides = RuntimeContainerOverrides(**{override_name: object()})  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=failure_code):
        create_runtime_api_app(
            cas_root=tmp_path / ".polisyos" / "cas",
            container_overrides=overrides,
        )


def test_control_service_types_malformed_promotion_runtime(tmp_path) -> None:
    store = FileSystemCAS(
        tmp_path / ".polisyos",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        ownership_enforced=True,
    )
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )

    with pytest.raises(ValueError, match="promotion_runtime_owner_invalid"):
        ControlPlaneService(
            cas_root=tmp_path / ".polisyos",
            core_runs_root=tmp_path / ".polisyos" / "runs",
            artifact_store=store,
            retrieval_service=_NoOpRetrievalService(),
            policy_resolver=resolver,
            registry_providers=_build_registry_providers(),
            promotion_runtime=object(),  # type: ignore[arg-type]
        )


def test_control_service_binds_one_durable_llm_settlement_owner(tmp_path) -> None:
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    service = _build_control_service(tmp_path)
    first = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(tmp_path / "llm-ledger-one.json"),
    )
    second = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(tmp_path / "llm-ledger-two.json"),
    )
    try:
        assert service.llm_producer_settlement_store is None
        service.bind_llm_producer_settlement_store(first)
        assert service.llm_producer_settlement_store is first
        service.bind_llm_producer_settlement_store(first)
        with pytest.raises(ValueError, match="llm_producer_settlement_store_already_bound"):
            service.bind_llm_producer_settlement_store(second)
        with pytest.raises(
            TypeError, match="llm_producer_settlement_store_must_be_budget_middleware"
        ):
            service.bind_llm_producer_settlement_store(object())
        with pytest.raises(ValueError, match="llm_producer_settlement_store_must_be_durable"):
            service.bind_llm_producer_settlement_store(BudgetMiddleware(BudgetState()))
    finally:
        service.close()


def test_control_service_owns_one_eval_safety_service_verifier_and_store(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    try:
        persistence = service._evaluation_safety_persistence_service
        verifier = service._evaluation_safety_admission_verifier

        assert isinstance(persistence, EvaluationSafetyPersistenceService)
        assert isinstance(verifier, EvaluationSafetyAdmissionVerifier)
        assert persistence._artifact_store is service._artifact_store
        assert persistence._event_log is service._diagnostic_event_log
        assert verifier._persistence_service is persistence
        assert verifier._current_state_resolver is service._evaluation_safety_state_resolver
        assert verifier._authority_resolver is service._evaluation_safety_authority_resolver
        assert verifier._appointment_resolver is service._evaluation_safety_appointment_resolver
        assert verifier._verifier_registry is service._evaluation_safety_verifier_registry
    finally:
        service.close()


def test_control_service_accepts_exact_eval_safety_persistence_owner(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=store,
    )
    persistence = EvaluationSafetyPersistenceService(
        artifact_store=store,
        event_log=event_log,
    )
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=str(tmp_path / "control.sqlite3"),
        postgres_dsn=None,
    )
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        artifact_store=store,
        control_store=control_store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=_build_registry_providers(),
        evaluation_safety_persistence_service=persistence,
    )
    try:
        assert service._diagnostic_event_log is event_log
        assert service._evaluation_safety_persistence_service is persistence
        assert service._evaluation_safety_admission_verifier._persistence_service is persistence
    finally:
        service.close()


def test_control_service_rejects_foreign_eval_safety_persistence_store(tmp_path) -> None:
    owner = _build_control_service(tmp_path / "owner")
    foreign = EvaluationSafetyPersistenceService(
        artifact_store=FileSystemCAS(tmp_path / "foreign" / "cas"),
        event_log=owner._diagnostic_event_log,
    )
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    try:
        with pytest.raises(ValueError, match="evaluation_safety_persistence_owner_mismatch"):
            ControlPlaneService(
                cas_root=tmp_path / "target" / ".polisyos",
                core_runs_root=tmp_path / "target" / ".polisyos" / "runs",
                artifact_store=FileSystemCAS(tmp_path / "target" / "cas"),
                retrieval_service=_NoOpRetrievalService(),
                policy_resolver=resolver,
                registry_providers=_build_registry_providers(),
                evaluation_safety_persistence_service=foreign,
            )
    finally:
        owner.close()


def test_control_service_rejects_foreign_promotion_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "owner-cas")
    decision_validity = DecisionValidityService(store)
    foreign_runtime = PromotionRuntime(
        store=FileSystemCAS(tmp_path / "foreign-cas"),
        completed_epoch_batches=decision_validity,
    )
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )

    with pytest.raises(ValueError, match="promotion_runtime_decision_validity_owner_mismatch"):
        ControlPlaneService(
            cas_root=tmp_path / ".polisyos",
            core_runs_root=tmp_path / ".polisyos" / "runs",
            artifact_store=store,
            retrieval_service=_NoOpRetrievalService(),
            policy_resolver=resolver,
            registry_providers=_build_registry_providers(),
            decision_validity_service=decision_validity,
            promotion_runtime=foreign_runtime,
        )


def test_control_service_does_not_trust_injected_store_backend_labels(tmp_path) -> None:
    direct_store = FileSystemCAS(tmp_path / "direct-cas")
    direct_service = _build_control_service(
        tmp_path / "direct-service",
        artifact_store=direct_store,
    )
    assert direct_service._artifact_store_backend == "filesystem"
    assert direct_service._promotion_runtime.signature_verifier is not None
    assert direct_service._promotion_runtime.signature_verifier.guarded_store is direct_store

    class ClaimedFilesystemStore:
        backend = "filesystem"

        def __init__(self, store: FileSystemCAS) -> None:
            self._store = store

        def __getattr__(self, name: str) -> Any:
            return getattr(self._store, name)

    claimed_store = ClaimedFilesystemStore(FileSystemCAS(tmp_path / "claimed-cas"))
    claimed_service = _build_control_service(
        tmp_path / "claimed-service",
        artifact_store=claimed_store,  # type: ignore[arg-type]
    )
    assert claimed_service._artifact_store_backend is None
    assert claimed_service._promotion_runtime.signature_verifier is None

    from polisyos.runtime.http.resilience import (
        build_guarded_signature_verifier,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _injected_artifact_store_backend,
    )

    unrelated_verifier = build_guarded_signature_verifier(
        backend="filesystem",
        guarded_store=direct_store,
    )
    assert unrelated_verifier is not None
    with pytest.raises(ValueError, match="control_signature_verifier_store_mismatch"):
        _injected_artifact_store_backend(
            artifact_store=claimed_store,  # type: ignore[arg-type]
            signature_verifier=unrelated_verifier,
        )


@pytest.mark.asyncio
async def test_runtime_container_exposes_one_decision_validity_owner(tmp_path) -> None:
    app = create_runtime_api_app(cas_root=tmp_path / ".polisyos" / "cas")

    await app.state.runtime_container.startup(app)
    try:
        runtime_context = app.state.runtime_container.runtime_api_context
        control_service = app.state._control_service
        assert control_service._artifact_store is runtime_context.store
        assert runtime_context.signature_verifier is not None
        assert runtime_context.signature_verifier.guarded_store is runtime_context.store
        assert control_service._artifact_store_backend == "filesystem"
        assert control_service._promotion_runtime.signature_verifier is (
            runtime_context.signature_verifier
        )
        assert app.state._control_service._decision_validity_service is (
            app.state.runtime_container.decision_validity_service
        )
        assert app.state._control_service._promotion_runtime is (
            app.state.runtime_container.promotion_runtime
        )
        assert (
            app.state.runtime_container.promotion_runtime.epoch_n9_evidence_resolver._completed_batches
            is app.state.runtime_container.decision_validity_service
        )
        assert app.state._control_service._epoch_claim_lifecycle_bridge is (
            app.state.runtime_container.epoch_claim_lifecycle_bridge
        )
        assert app.state.runtime_container.epoch_claim_lifecycle_bridge.completed_batches is (
            app.state.runtime_container.decision_validity_service
        )
        assert app.state.runtime_container.epoch_claim_lifecycle_bridge.claim_owner is (
            app.state.runtime_container.claim_ledger_owner
        )
        assert isinstance(
            app.state.runtime_container.claim_ledger_owner,
            UnappointedClaimLedgerOwner,
        )
        assert app.state.runtime_container.claim_ledger_owner.store is (
            app.state.runtime_container.runtime_api_context.store
        )
    finally:
        await app.state.runtime_container.shutdown(app)


@pytest.mark.asyncio
async def test_recursive_http_without_container_promotion_runtime_fails_closed() -> None:
    with pytest.raises(
        DesignProblemAuthorityError,
        match="promotion_runtime_not_established",
    ):
        await generation_cycle_service.compile_and_run_recursive_generation_cycle(
            raw_request="This request must not be compiled.",
            context={},
            model_name="fixture-model",
            compiler_gateway=object(),  # type: ignore[arg-type]
            budget_state=object(),  # type: ignore[arg-type]
            recursive_budget=object(),  # type: ignore[arg-type]
            promotion_runtime=None,
        )


@pytest.mark.asyncio
async def test_recursive_http_eval_safety_inputs_fail_typed_before_compilation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "promotion-cas"))
    verifier = _NeverCalledEvalSafetyVerifier()
    compile_calls = 0

    async def compiler_must_not_run(**kwargs):
        nonlocal compile_calls
        del kwargs
        compile_calls += 1
        raise AssertionError("invalid EvalSafety input reached the compiler")

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compiler_must_not_run,
    )
    common = {
        "raw_request": "This request must not be compiled.",
        "context": {},
        "model_name": "fixture-model",
        "compiler_gateway": object(),
        "budget_state": object(),
        "recursive_budget": object(),
        "promotion_runtime": runtime,
    }
    cases = (
        ({"eval_safety_verifier": verifier}, "eval_safety_execution_context_not_established"),
        (
            {"root_evaluation_context": object()},
            "eval_safety_verifier_not_established",
        ),
        (
            {
                "root_evaluation_context": object(),
                "eval_safety_verifier": verifier,
            },
            "eval_safety_execution_context_not_canonical",
        ),
    )
    for supplied, expected_code in cases:
        with pytest.raises(DesignProblemAuthorityError) as exc_info:
            await generation_cycle_service.compile_and_run_recursive_generation_cycle(
                **common,
                **supplied,
            )
        assert exc_info.value.code == expected_code
    assert compile_calls == 0

    from tests.unit.runtime.quality.test_generation_cycle import _problem

    problem = _problem(f"foreign_eval_safety_verifier_{uuid4().hex}")

    async def compile_problem(**kwargs):
        nonlocal compile_calls
        del kwargs
        compile_calls += 1
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )
    owner_verifier = _NeverCalledEvalSafetyVerifier()
    foreign_verifier = _NeverCalledEvalSafetyVerifier()
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=runtime,
        eval_safety_verifier=owner_verifier,
    )
    foreign_common = {
        **common,
        "raw_request": problem.nl_provenance.raw_request,
    }
    with pytest.raises(DesignProblemAuthorityError) as exc_info:
        await generation_cycle_service.compile_and_run_recursive_generation_cycle(
            **foreign_common,
            root_evaluation_context=_explicit_simulation_execution_context(problem),
            eval_safety_verifier=foreign_verifier,
            controller=controller,
        )
    assert exc_info.value.code == "recursive_controller_eval_safety_verifier_mismatch"
    assert compile_calls == 1


@pytest.mark.asyncio
async def test_plain_http_request_reaches_cycle_compiler_without_python_eval_context(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain request reaches proposal-only N4 without caller-built EvalSafety state."""

    from polisyos.runtime.http.services.control.generation_cycle import (
        N4CandidateProposalExecution,
    )
    from polisyos.runtime.quality import intervention_substrate
    from polisyos.runtime.quality.design_generation import DesignGenerationOrganRun
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _budget,
        _problem,
    )

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "promotion-cas"))
    problem = _problem(f"plain_http_without_python_context_{uuid4().hex}")
    compiler_calls = 0

    async def compile_problem(**kwargs):
        nonlocal compiler_calls
        assert kwargs["nl_request"] == problem.nl_provenance.raw_request
        assert kwargs["context"] == {}
        compiler_calls += 1
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        lambda **_kwargs: None,
    )

    def forbid_eager_world_build(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ordinary_candidate_eager_world_build")

    monkeypatch.setattr(
        intervention_substrate,
        "production_composed_world_model_record",
        forbid_eager_world_build,
    )

    # This is the ordinary HTTP candidate boundary: no CycleSubstrateContext or
    # EvaluationExecutionContext is supplied by the caller. The canonical N4
    # owner is attempted, and its unavailable result must stay typed.
    compiled = await generation_cycle_service.compile_and_run_recursive_generation_cycle(
        raw_request=problem.nl_provenance.raw_request,
        context={},
        model_name="fixture-model",
        compiler_gateway=object(),  # type: ignore[arg-type]
        budget_state=_budget(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
        promotion_runtime=runtime,
        eval_safety_verifier=_NeverCalledEvalSafetyVerifier(),
        root_evaluation_context=None,
        repo_root=REPO_ROOT,
    )

    assert compiler_calls == 1
    assert isinstance(compiled, N4CandidateProposalExecution)
    assert isinstance(compiled.proposal, DesignGenerationOrganRun)
    assert compiled.design_problem == problem
    assert compiled.proposal.result.status == "generation_unavailable"
    assert compiled.proposal.result.candidates == ()


@pytest.mark.asyncio
async def test_direct_recursive_http_and_replay_share_one_owner_context_ref(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject the old direct N4 fixture before it can mint protected epoch evidence.

    Keep the pre-existing node ID for the 40/41 file replay. The former positive
    assertion used an injected N4 port without a worker-issued VerifiedNLJobScope;
    the served owner-bound N4→N5 positive lives in
    ``test_served_simulate_only_replays_admitted_fixture_context_into_n5``.
    """
    from tests.unit.runtime.quality.test_generation_cycle import _problem

    app = create_runtime_api_app(cas_root=tmp_path / ".polisyos" / "cas")
    from polisyos.runtime.quality import promotion_sequence as promotion_sequence_module

    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = app.state.runtime_container.promotion_runtime
    problem = _problem(f"http_shared_open_world_context_{uuid4().hex}")
    verifier = _NeverCalledEvalSafetyVerifier()
    compile_calls = 0
    n4_calls = 0

    async def compile_problem(**kwargs):
        nonlocal compile_calls
        del kwargs
        compile_calls += 1
        return problem

    class _CanonicalFixtureN4Port(N4GenerationPort):
        def __init__(self) -> None:
            super().__init__(model_id="fixture-model")

        async def __call__(self, problem, *, cycle_index):
            nonlocal n4_calls
            del problem, cycle_index
            n4_calls += 1
            raise AssertionError("N4 must not run without owner-bound context")

    def refuse_controller(**_kwargs):
        pytest.fail("recursive controller was built without owner-bound context")

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )
    monkeypatch.setattr(
        generation_cycle_service,
        "build_default_recursive_generation_cycle_controller",
        refuse_controller,
    )
    try:
        with pytest.raises(DesignProblemAuthorityError) as exc_info:
            await generation_cycle_service.compile_and_run_recursive_generation_cycle(
                raw_request=problem.nl_provenance.raw_request,
                context={},
                model_name="fixture-model",
                compiler_gateway=object(),  # type: ignore[arg-type]
                budget_state=object(),  # type: ignore[arg-type]
                recursive_budget=RecursiveCycleBudget(
                    max_depth=0,
                    max_nodes=1,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=1,
                ),
                root_n4_generation_port=_CanonicalFixtureN4Port(),
                promotion_runtime=runtime,
                root_evaluation_context=_explicit_simulation_execution_context(problem),
                eval_safety_verifier=verifier,
            )

        assert exc_info.value.code == "cycle_substrate_context_not_established"
        assert compile_calls == 1
        assert n4_calls == 0
        subject_kind = "runtime.promotion.pre_n9_epoch_validity_subject"
        subject_ids = tuple(
            artifact_id
            for artifact_id in runtime.store.iter_artifact_ids()
            if runtime.store.get_manifest(artifact_id).kind == subject_kind
        )
        assert subject_ids == ()
    finally:
        await app.state.runtime_container.shutdown(app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        pytest.param("blocked", id="blocked-writer-refusal"),
        pytest.param("stop", id="completed-stop-n9-projection"),
    ],
)
async def test_generation_cycle_projection_respects_n6_status(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    """Exercise blocked refusal and the completed-stop N9 projection path."""

    from pydantic import ValidationError

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleRun,
        PendingN8ValuePort,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveGenerationCycleRun,
    )
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _budget,
        _CounterexampleAwareGenerator,
        _CurrentValidGrounding,
        _problem,
    )

    problem = _problem(f"served_r11_n9_projection_{uuid4().hex}")
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "promotion-cas"))
    verifier = _NeverCalledEvalSafetyVerifier()
    grafted_payload = {"receipt": "adversarially-grafted"}
    parsed_payloads: list[object] = []
    projection_inputs: list[dict[str, object]] = []
    parsed_receipt = object()

    def parse_receipt(payload: object) -> object:
        parsed_payloads.append(payload)
        return parsed_receipt

    def project_receipt(**kwargs: object) -> None:
        projection_inputs.append(kwargs)
        return None

    monkeypatch.setattr(
        generation_cycle_service,
        "CanonicalPromotionReceipt",
        SimpleNamespace(model_validate=parse_receipt),
    )
    monkeypatch.setattr(
        generation_cycle_service,
        "project_pre_n9_open_world_limitations",
        lambda **_kwargs: (),
    )
    monkeypatch.setattr(
        generation_cycle_service,
        "project_promotion_open_world_limitation",
        project_receipt,
    )

    async def compile_problem(**kwargs):
        del kwargs
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )

    async def compile_served_projection(action: str):
        reason = "explicit_voi_block" if action == "blocked" else "ordinary_scheduler_stop"
        recursive = build_default_recursive_generation_cycle_controller(
            promotion_runtime=runtime,
            eval_safety_verifier=verifier,
            repo_root=REPO_ROOT,
            model_id="fixture-model",
        )

        class _ActionController(GenerationCycleController):
            def decide_next_action(self, **kwargs):
                decision = super().decide_next_action(**kwargs)
                return decision.model_copy(update={"next_action": action, "reason": reason})

        recursive._cycle_controller_factory = lambda _node_ref, _problem: _ActionController(
            generation_port=_CounterexampleAwareGenerator(),
            grounding_port=_CurrentValidGrounding(),
            value_port=PendingN8ValuePort(),
            repo_root=REPO_ROOT,
            promotion_runtime=runtime,
        )
        owner_run = recursive.run

        async def run_with_grafted_receipt(*args, **kwargs):
            produced = await owner_run(*args, **kwargs)
            leaf = produced.leaf_nodes[0]
            assert leaf.cycle_run is not None
            expected_terminal_status = "blocked" if action == "blocked" else "completed"
            assert leaf.cycle_run.terminal_status == expected_terminal_status
            assert leaf.cycle_run.promotion_port.receipts == ()
            assert leaf.cycle_run.source_custody_limitation is None

            # Treat the served projection input as a re-hashed persisted artifact:
            # its real owner N6 run is preserved while an N9 receipt is grafted.
            payload = produced.model_dump(mode="json")
            payload.pop("content_hash")
            graft_count = 0
            for node in payload["nodes"]:
                cycle_run = node.get("cycle_run")
                if cycle_run is None:
                    continue
                cycle_run["promotion_port"]["receipts"] = [grafted_payload]
                graft_count += 1
            assert graft_count == 1
            payload["content_hash"] = gy_content_hash(payload)
            return RecursiveGenerationCycleRun.model_validate(payload)

        monkeypatch.setattr(recursive, "run", run_with_grafted_receipt)
        return await generation_cycle_service.compile_and_run_recursive_generation_cycle(
            raw_request=problem.nl_provenance.raw_request,
            context={},
            model_name="fixture-model",
            compiler_gateway=object(),  # type: ignore[arg-type]
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            execution_intent="simulate_only",
            promotion_runtime=runtime,
            eval_safety_verifier=verifier,
            root_evaluation_context=None,
            controller=recursive,
            repo_root=REPO_ROOT,
        )

    if action == "blocked":
        with pytest.raises(
            ValidationError,
            match="blocked_generation_cycle_n9_admission_mismatch",
        ):
            await compile_served_projection(action)
        assert parsed_payloads == []
        assert projection_inputs == []
        return

    compiled = await compile_served_projection(action)
    assert isinstance(compiled, generation_cycle_service.CompiledRecursiveGenerationCycleRun)
    stop_cycle = compiled.recursive_run.leaf_nodes[0].cycle_run
    assert stop_cycle is not None
    assert stop_cycle.terminal_status == "completed"
    assert stop_cycle.cycles[-1].voi_decision.next_action == "stop"
    assert parsed_payloads == [grafted_payload]
    assert len(projection_inputs) == 1
    assert projection_inputs[0]["receipt"] is parsed_receipt
    n9_source = projection_inputs[0]["n9_source"]
    assert type(n9_source.run) is GenerationCycleRun
    assert n9_source.run.run_id == stop_cycle.run_id


def test_control_service_exposes_one_narrow_human_decision_sink(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    try:
        sink = service.human_decision_sink

        assert sink is service.human_decision_sink
        assert not hasattr(sink, "artifact_store")
        assert not hasattr(sink, "event_log")
        assert not hasattr(sink, "reservation_store")
        assert callable(sink.reserve_action)
        assert callable(sink.write_authority_artifact)
        assert callable(sink.verify_artifact_signature)
    finally:
        service.close()


def test_control_service_exposes_one_narrow_acquisition_route_sink(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    try:
        sink = service.acquisition_route_sink

        assert sink is service.acquisition_route_sink
        assert sink._artifact_store is service._artifact_store
        assert sink._event_log is service._diagnostic_event_log
        assert sink._control_store is service._control_store
        assert callable(sink.get_head)
        assert callable(sink.persist_phase)
        assert callable(sink.persist_terminal)
        assert not hasattr(sink, "world_store")
        assert not hasattr(sink, "overlay")
        assert not hasattr(sink, "passport_store")
    finally:
        service.close()


def test_runtime_principal_preserves_cell_id_in_policy_actor() -> None:
    principal = RuntimePrincipal.from_user_claims(_fixture_claims())
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )

    policy = resolver.resolve(
        requested_profile="dev",
        policy_flags=None,
        principal=principal,
    )

    assert principal.tenant_id == "tenant-fixture"
    assert principal.cell_id == "cell-fixture"
    assert policy.actor["tenant_id"] == "tenant-fixture"
    assert policy.actor["cell_id"] == "cell-fixture"


@pytest.mark.asyncio
async def test_launch_nl_run_persists_tenant_scope_in_queued_payload(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Check tenant propagation",
            llm_model="simulated-qwen",
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        payload = service._load_payload_ref(
            str(record.payload_ref), kind="runtime.control_job_payload.natural_language_run"
        )

        assert payload["tenant_id"] == "tenant-fixture"
        assert payload["cell_id"] == "cell-fixture"
    finally:
        service.close()


def test_legacy_workflow_maps_admitted_runtime_scope_at_scientist_boundary(
    tmp_path, monkeypatch
) -> None:
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    service = _build_control_service(tmp_path)
    principal = RuntimePrincipal(
        subject="user-fixture",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        roles=frozenset({"analyst"}),
        authenticated=True,
    )
    observed: dict[str, object] = {}

    def capture_scientist_state(payload, **_kwargs):
        state = ExperimentState.model_validate(payload)
        observed["state"] = state
        observed["raw_payload"] = dict(payload)
        observed["scope"] = (
            get_current_tenant_id_or_none(),
            get_current_cell_id(),
        )
        return {"status": "success"}

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", capture_scientist_state)
    try:
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": "sha256:" + "a" * 64},
                params={"control_plane_transition": "legacy_shadow"},
            ),
            principal=principal,
        )
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )

        job = service._control_store.get_job(launch.job_id)
        assert job is not None
        assert job.state == "completed"
        state = observed["state"]
        assert isinstance(state, ExperimentState)
        assert state.run_id == launch.run_id
        assert state.control_job_id == launch.job_id
        assert observed["scope"] == ("tenant-fixture", "cell-fixture")
        raw_payload = observed["raw_payload"]
        assert isinstance(raw_payload, dict)
        assert not {"job_id", "tenant_id", "cell_id"}.intersection(raw_payload)
    finally:
        service.close()


def test_legacy_workflow_rejects_foreign_persisted_owner_scope_before_scientist(
    tmp_path, monkeypatch
) -> None:
    service = _build_control_service(tmp_path)
    principal = RuntimePrincipal(
        subject="user-fixture",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        roles=frozenset({"analyst"}),
        authenticated=True,
    )
    scientist_called = False

    def capture_scientist_state(*_args, **_kwargs):
        nonlocal scientist_called
        scientist_called = True

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", capture_scientist_state)
    try:
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": "sha256:" + "b" * 64},
                params={"control_plane_transition": "legacy_shadow"},
            ),
            principal=principal,
        )
        job = service._control_store.get_job(launch.job_id)
        assert job is not None and job.payload_ref is not None
        load_payload_ref = service._load_payload_ref

        def load_foreign_owner_payload(payload_ref: str, *, kind: str) -> dict[str, object]:
            loaded = load_payload_ref(payload_ref, kind=kind)
            if payload_ref == job.payload_ref:
                loaded["tenant_id"] = "tenant-foreign"
            return loaded

        monkeypatch.setattr(service, "_load_payload_ref", load_foreign_owner_payload)
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )

        failed = service._control_store.get_job(launch.job_id)
        assert failed is not None
        assert failed.state == "failed"
        assert failed.error_message == "control_job_payload_owner_scope_mismatch"
        assert scientist_called is False
    finally:
        service.close()


@pytest.fixture(scope="module")
def controlled_recursive_result(tmp_path_factory):
    """Build one owner-bound result used only to probe candidate-intent rejection."""
    with pytest.MonkeyPatch.context() as patches:
        fixture = asyncio.run(
            _run_controlled_simulate_only_job_fixture(
                patches,
                tmp_path_factory.mktemp("candidate-only-rejection-source"),
            )
        )
        try:
            return generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
                canon.from_canonical_bytes(fixture.compiled_payload)
            )
        finally:
            fixture.service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("normative_mode", ["missing", "authorized", "wrong_role", "wrong_source"])
async def test_process_nl_job_enters_persisted_tenant_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    normative_mode: str,
    controlled_recursive_result,
) -> None:
    """Candidate intent keeps tenant scope and cannot turn request evidence into S8."""
    compiled_fixture = controlled_recursive_result
    service = _build_control_service(tmp_path)
    try:
        context = {}
        if normative_mode != "missing":
            context["normative_evidence"] = _signed_generation_evidence(
                service,
                compiled_fixture,
                fault=normative_mode,
            )
        request = NaturalLanguageRunRequest(
            request=compiled_fixture.design_problem.nl_provenance.raw_request,
            llm_model="simulated-qwen",
            context=context,
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        async def return_recursive_result(**kwargs):
            assert get_current_tenant_id_or_none() == "tenant-fixture"
            assert get_current_cell_id() == "cell-fixture"
            assert kwargs["raw_request"] == request.request
            assert kwargs["execution_intent"] == "candidate_only"
            assert service._promotion_runtime.store is service._artifact_store
            return compiled_fixture

        def refuse_s8(**_kwargs):
            pytest.fail("candidate-only compiled result entered the S8 resolver")

        def refuse_publication(**_kwargs):
            pytest.fail("candidate-only compiled result entered generation publication")

        monkeypatch.setattr(
            service, "compile_and_run_recursive_generation_cycle", return_recursive_result
        )
        monkeypatch.setattr(service, "resolve_generation_value_choices", refuse_s8)
        monkeypatch.setattr(service, "_publish_generation_run", refuse_publication)

        dispatch_one_control_job(
            store=service._control_store,  # noqa: SLF001
            handler=service._process_control_job,  # noqa: SLF001
            expected_job_id=launch.job_id,
        )

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None and completed.state == "completed"
        progress = completed.progress
        assert progress["status"] == "not_established"
        assert progress["execution_band"] == "candidate"
        assert progress["execution_intent_band"] == "candidate_only"
        assert progress["candidate_computation_status"] == "not_established"
        assert progress["limitation_code"] == "candidate_only_compiled_result_not_admitted"
        assert progress["n5_status"] == "not_run"
        assert progress["n8_status"] == "not_run"
        assert progress["n9_status"] == "not_run"
        assert progress["s8_status"] == "not_run"
        assert progress["publication_status"] == "not_run"
        assert "compiled_recursive_generation_cycle_ref" not in progress
        assert "normative_disposition_ref" not in progress
        assert "manifest_ref" not in progress
        assert "core_run_id" not in progress
        assert "core_manifest_artifact_ref" not in progress
    finally:
        service.close()


def _signed_generation_evidence(service, compiled, *, fault: str):
    """Explicit fixture principals permit selection only; this is no governed promotion."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8
    from tests.unit.runtime.quality.test_design_axes_value_choice_provenance import (
        _authorized_schedule_payload,
        _pareto_archive_payload,
    )

    now = datetime.now(UTC)
    claimant_key, authorizer_key = artifacts.KeyPair.generate(), artifacts.KeyPair.generate()
    claimant, authorizer = "fixture:claimant", "fixture:authorizer"
    case_id = compiled.design_problem.design_problem_id
    scope_ref = "fixture:explicit-value-scope"
    mandate_ref = "fixture:mandate"
    store = service._artifact_store

    def put_signed(payload, kind, schema, *, key, identity):
        ref = store.put_json(
            payload,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=kind, version=schema),
            ),
        )
        store.sign_artifact(
            ref.artifact_id, artifacts.Ed25519Signer(key.private_key), signer_identity=identity
        )
        return str(ref.artifact_id)

    compiled_ref = service._put_json_artifact(
        compiled.model_dump(mode="json"),
        kind="runtime.compiled_recursive_generation_cycle",
        schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
    )
    bindings = generation_cycle_service._normative_generation_sources(
        store, compiled_ref, persist=True
    )
    node_ref, binding = next(iter(bindings.items()))
    leaf = compiled.recursive_run.leaf_nodes[0].cycle_run
    assert leaf is not None
    candidates = tuple(dict.fromkeys(row.candidate_id for row in leaf.candidate_summaries))
    assert candidates
    schedule = s8.build_authorized_value_schedule(
        **_authorized_schedule_payload(
            case_id=case_id,
            mandate_record_ref=mandate_ref,
            principal_refs=[authorizer],
            effective_at=now - timedelta(days=1),
        )
    )
    schedule_ref = put_signed(
        schedule.model_dump(mode="json"),
        s8.NORMATIVE_SCHEDULE_KIND,
        s8.LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
        key=claimant_key,
        identity=claimant,
    )
    frontier = s8.build_pareto_archive(
        **_pareto_archive_payload(
            case_id=case_id,
            ranking_mode="unranked_frontier_only",
            archive_status="frontier_available",
            value_schedule_ref=None,
            nondominated_alternative_ids=candidates,
            rejected_nondominated_alternative_ids=[],
            frontier_refs=[
                "sha256:" + "f" * 64 if fault == "wrong_frontier_source" else binding.source_run_ref
            ],
        )
    )
    frontier_ref = put_signed(
        frontier.model_dump(mode="json"),
        s8.NORMATIVE_FRONTIER_KIND,
        s8.LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
        key=claimant_key,
        identity=claimant,
    )
    if fault == "wrong_source":
        binding = binding.model_copy(update={"source_run_ref": "sha256:" + "e" * 64})
    authorization = s8.NormativeAuthorizationRecordV2(
        authorizer_identity=authorizer,
        authority_purpose="value_schedule_for_ranking",
        case_id=case_id,
        scope_ref=scope_ref,
        mandate_ref=mandate_ref,
        decision_class_id="value_authorization",
        decision_role="legal_reviewer" if fault == "wrong_role" else "principal",
        source_schedule_ref=schedule_ref,
        frontier_ref=frontier_ref,
        selected_alternative_id=candidates[0],
        effective_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
        rule_version_ref=s8.LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
        generation_binding=binding,
    )
    authorization_ref = put_signed(
        authorization.model_dump(mode="json"),
        s8.NORMATIVE_AUTHORIZATION_KIND,
        s8.NORMATIVE_GENERATION_AUTHORIZATION_SCHEMA_VERSION,
        key=authorizer_key,
        identity=authorizer,
    )
    # The deployment slot is populated explicitly by this fixture, never by context evidence.
    service._normative_authority_trust = s8.NormativeAuthorityTrust(
        epoch="explicit-test-deployment",
        principals=(
            s8.NormativeAuthorityPrincipal(
                identity=claimant,
                public_key_pem=claimant_key.public_pem().decode(),
            ),
            s8.NormativeAuthorityPrincipal(
                identity=authorizer,
                public_key_pem=authorizer_key.public_pem().decode(),
                decision_roles=("principal",),
                authority_purposes=("value_schedule_for_ranking",),
                case_ids=(case_id,),
                scope_refs=(scope_ref,),
                mandate_refs=(mandate_ref,),
            ),
        ),
    )
    return {
        "by_node": {
            node_ref: {
                "frontier_ref": frontier_ref,
                "authorization_ref": authorization_ref,
                "scope_ref": scope_ref,
            }
        }
    }


def test_registry_bundle_preserves_injected_capability_owner_seams() -> None:
    """Composition must preserve independent discovery, operation, and verifier owners."""
    discovery_provider = SimpleNamespace(resource_kind="method")
    operation_registry = SimpleNamespace()
    conformance_verifier = SimpleNamespace()
    base = _build_registry_providers()

    providers = ControlRegistryProviders(
        connectors=base.connectors,
        source_profiles=base.source_profiles,
        binding_profiles=base.binding_profiles,
        model_profiles=base.model_profiles,
        capability_discovery_providers=(discovery_provider,),
        capability_live_operation_registry=operation_registry,
        capability_conformance_verifier=conformance_verifier,
    )

    assert providers.capability_discovery_providers == (discovery_provider,)
    assert providers.capability_live_operation_registry is operation_registry
    assert providers.capability_conformance_verifier is conformance_verifier


def test_control_service_uses_injected_registry_providers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    providers = _build_registry_providers()
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    service = ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=providers,
    )

    def _unexpected(cls, *args, **kwargs):
        del cls, args, kwargs
        raise AssertionError("singleton lookup should not be used")

    from polisyos.fabric.connectors.bindings.registry import BindingProfileRegistry
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.scientist.orchestration.llm.profiles.registry import (
        ModelProfileRegistry,
    )

    monkeypatch.setattr(SourceProfileRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(BindingProfileRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(ConnectorRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(ModelProfileRegistry, "get_instance", classmethod(_unexpected))

    connectors = service.list_connectors()
    source_profiles = service.list_source_profiles()
    binding_profiles = service.list_binding_profiles()
    model_profiles = service.list_model_profiles()

    assert connectors.connectors[0].connector_id == "fixture.family.connector"
    assert connectors.connectors[0].available_profiles == ["fixture_profile"]
    assert source_profiles.profiles[0].profile_id == "fixture_profile"
    assert source_profiles.profiles[0].connector_available is True
    assert binding_profiles.profiles[0].profile_id == "fixture_binding"
    assert model_profiles.profiles[0].profile_id == "fixture_model"

    connection_config = object()

    def _run_orchestrated_ingestion(**kwargs):
        assert kwargs["connection_config"] is connection_config
        return SimpleNamespace(
            evidence_bundle_ref=None,
            data_snapshot_ref=None,
            datasets_fetched=1,
            warnings=[],
            cursor_ref=None,
            mode_effective=None,
        )

    monkeypatch.setattr(
        "polisyos.fabric.connectors.profiles.resolver.resolve_connection_config",
        lambda profile: connection_config if profile.profile_id == "fixture_profile" else None,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
        _run_orchestrated_ingestion,
    )

    response = service.run_data_ingestion(
        IngestRequest.model_validate(
            {
                "datasets": [
                    {
                        "connector_id": "fixture.family.connector",
                        "dataset_id": "fixture.dataset",
                    }
                ],
                "connection_profile": "fixture_profile",
            }
        )
    )

    assert response.status == "completed"
    assert response.datasets_fetched == 1
    assert response.mode_effective == "batch_full"
    service.close()


def test_resolve_control_registry_providers_uses_factory_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = _build_registry_providers()

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_connectors",
        lambda: (_ for _ in ()).throw(AssertionError("global connectors should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_source_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global source profiles should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_binding_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global binding profiles should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_model_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global model profiles should not be used")),
    )

    resolved = resolve_control_registry_providers(
        connectors_factory=lambda: providers.connectors,
        source_profiles_factory=lambda: providers.source_profiles,
        binding_profiles_factory=lambda: providers.binding_profiles,
        model_profiles_factory=lambda: providers.model_profiles,
    )

    assert resolved == providers


def test_control_service_builds_retrieval_with_injected_provider_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    providers = _build_registry_providers()
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    seen: dict[str, object] = {}

    class _FakeRetrievalService:
        def __init__(
            self, *, curated_dir, artifact_store, dataset_catalog, providers=None, **kwargs
        ) -> None:
            del curated_dir, kwargs
            seen["artifact_store"] = artifact_store
            seen["dataset_catalog"] = dataset_catalog
            seen["providers"] = providers

        def list_promotion_candidates(self):
            return []

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService",
        _FakeRetrievalService,
    )

    service = ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        policy_resolver=resolver,
        registry_providers=providers,
    )

    assert seen["artifact_store"] is store
    assert seen["dataset_catalog"] is service._retrieval_catalog
    retrieval_providers = seen["providers"]
    assert retrieval_providers.registry is providers.connectors
    assert retrieval_providers.profiles is providers.source_profiles
    assert retrieval_providers.tracer is service._tracer
    assert retrieval_providers.metrics is service._metrics
    service.close()


@pytest.mark.parametrize("injected", [False, True])
def test_control_service_preserves_real_catalog_ownership(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    injected: bool,
) -> None:
    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_service_catalog import (
        _actual_scope_catalog,
        _install_builtin_worldbank_profile_scope,
    )

    profile_registry = _install_builtin_worldbank_profile_scope(monkeypatch)
    catalog = _actual_scope_catalog(tmp_path, profile_registry=profile_registry)
    database_path = catalog.database_path
    overlay_path = catalog.overlay_path
    monkeypatch.setattr(
        "polisyos.runtime.quality.substrate_registry.default_substrate_catalog_paths",
        lambda _root: SimpleNamespace(l1_dcat_path=database_path),
    )
    monkeypatch.setattr(
        "polisyos.data_forge.read_api.catalog.default_acquisition_overlay_path",
        lambda _root: overlay_path,
    )

    graph = catalog if injected else None
    retrieval = None
    if graph is not None:
        retrieval = RetrievalService(
            curated_dir=tmp_path / "catalog_only",
            cas_root=tmp_path / "cas",
            dataset_catalog=graph,
            profiles=profile_registry,
        )
    else:
        catalog.close()

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        artifact_store=FileSystemCAS(tmp_path / "cas"),
        retrieval_service=retrieval,
        registry_providers=resolve_control_registry_providers(
            source_profiles=profile_registry,
        ),
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        ),
    )
    selected = service._retrieval._dataset_catalog
    assert selected is not None
    if injected:
        assert selected is graph
        assert service._retrieval is retrieval
        assert service._retrieval_catalog is None
    else:
        assert selected is service._retrieval_catalog
        assert service._retrieval.artifact_store is service._artifact_store
    assert selected.database_path.resolve() == database_path.resolve()

    # This catalog was published by the canonical batch producer with the actual
    # header-free built-in WDI profile scoped in the producer and reader registries.
    response = service.data_resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
            catalog_run_profile="prod_full",
        )
    )
    assert len(response.fetch_plans) == 1
    plan = response.fetch_plans[0]
    assert (plan.connector_id, plan.dataset_id, plan.profile_id) == (
        "worldbank.wdi",
        "scope_dataset",
        "worldbank_wdi",
    )
    assert not any(
        warning.startswith("catalog_source_not_established:") for warning in response.warnings
    )

    with pytest.raises(RuntimeHTTPError) as unselected_profile:
        service.data_resolve(
            DataResolveRequest(
                data_needs=[
                    DataNeed(
                        metric="scope_metric",
                        geography="DEU",
                        time_start="2025",
                        time_end="2025",
                    )
                ],
                mode="fastlane",
                allow_explore_fallback=False,
            )
        )
    assert unselected_profile.value.status_code == 422
    assert unselected_profile.value.code == "catalog_run_profile_unresolved"
    closed: list[bool] = []
    close = selected.close

    def observed_close() -> None:
        closed.append(True)
        close()

    monkeypatch.setattr(selected, "close", observed_close)
    service.close()
    assert closed == ([] if injected else [True])
    if injected:
        selected.close()


def test_control_service_accepts_injected_observability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    providers = _build_registry_providers()
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    metrics = object()
    tracer = object()

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control._default_runtime_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control._default_runtime_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=providers,
        metrics=metrics,
        tracer=tracer,
    )

    assert service._metrics is metrics
    assert service._tracer is tracer
    service.close()


def test_task_runner_uses_shared_executor_by_default() -> None:
    runner = TaskRunner()

    assert runner._executor is get_shared_executor()
    assert runner._owns_executor is False

    runner.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_runtime_container_passes_control_registry_provider_override(tmp_path) -> None:
    providers = _build_registry_providers()
    app = create_runtime_api_app(
        cas_root=tmp_path / ".polisyos",
        allow_fixture_identity=True,
        container_overrides=RuntimeContainerOverrides(
            control_registry_providers=providers,
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        service = app.state._control_service
        assert service._registry_providers is providers
        discovery = service._capability_discovery_service
        assert discovery is not None
        assert discovery._composer._providers == {}
        assert discovery._composer._execution_resolver._operation_registry is None
        assert discovery._composer._execution_resolver._conformance_verifier is None


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_scope_field", [None, "tenant_id", "cell_id"])
async def test_served_nl_job_persists_real_candidate_proposal_without_n6_or_s8(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    missing_scope_field: str | None,
) -> None:
    """Served N4 preserves unknown cell as candidate and rejects altered tenant custody."""
    from polisyos.runtime.http.services.adapters.core_run import (
        load_terminal_core_run_source,
    )
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _design_problem_tool_args,
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
        _intent_context,
    )
    from tests.unit.runtime.quality.test_design_generation import (
        RecordedClientWithCatalog,
        _recording_with_successful_first_response,
    )

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap."
    )
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=_design_problem_tool_args(),
    )
    compiler_gateway.arguments["nl_provenance"]["source_context"]["runtime_identity"] = {
        "tenant_id": "tenant-llm-runtime-foreign",
        "cell_id": "cell-llm-runtime-foreign",
        "job_id": "job-llm-runtime-foreign",
        "run_id": "run-llm-runtime-foreign",
    }
    generation_gateway = RecordedClientWithCatalog(recording, model_ids=[model_id])
    original_compiler = nl_pipeline.build_design_problem_from_nl_request
    compiler_contexts: list[dict[str, object]] = []
    compiled_problems = []

    async def run_real_compiler(**kwargs):
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        compiler_contexts.append(dict(kwargs["context"]))
        problem = await original_compiler(**kwargs)
        compiled_problems.append(problem)
        return problem

    monkeypatch.setattr(
        generation_cycle_service, "build_design_problem_from_nl_request", run_real_compiler
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        lambda **_kwargs: generation_gateway,
    )

    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request=raw_request,
            llm_model=model_id,
            context=_intent_context(
                as_of="2026-05-12",
                runtime_identity={
                    "tenant_id": "tenant-request-runtime-foreign",
                    "cell_id": "cell-request-runtime-foreign",
                    "job_id": "job-request-runtime-foreign",
                    "run_id": "run-request-runtime-foreign",
                },
            ),
        )
        claims = _fixture_claims()
        if missing_scope_field == "cell_id":
            claims = claims.model_copy(update={"cell_id": None})
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        if missing_scope_field is not None:
            load_payload_ref = service._load_payload_ref

            def load_without_scope(payload_ref: str, *, kind: str) -> dict[str, object]:
                loaded = load_payload_ref(payload_ref, kind=kind)
                loaded.pop(missing_scope_field, None)
                return loaded

            monkeypatch.setattr(service, "_load_payload_ref", load_without_scope)

        def reject_s8(**_kwargs):
            pytest.fail("candidate-only N4 proposal reached the S8 resolver")

        def reject_n6(**_kwargs):
            pytest.fail("candidate-only N4 proposal entered the recursive N6 owner")

        monkeypatch.setattr(service, "resolve_generation_value_choices", reject_s8)
        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            reject_n6,
        )
        dispatch_one_control_job(
            store=service._control_store,  # noqa: SLF001
            handler=service._process_control_job,  # noqa: SLF001
            expected_job_id=launch.job_id,
        )

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None
        if missing_scope_field is not None:
            # The authenticated tenant was established at enqueue; deleting it
            # from the persisted payload is a custody mismatch, not unknown scope.
            assert completed.state == "failed"
            assert completed.error_message == (
                "control_job_payload_owner_scope_mismatch"
                if missing_scope_field == "tenant_id"
                else "nl_job_execution_intent_not_established"
            )
            assert compiler_gateway.generate_calls == []
            assert generation_gateway._cursor == 0
            proposals = [
                path
                for path in service._artifact_store.base.rglob("*.manifest.json")
                if "runtime.quality.n4_candidate_proposal" in path.read_text()
            ]
            assert not proposals
            return
        assert completed.state == "completed"
        assert compiler_gateway.generate_calls
        assert generation_gateway._cursor > 0
        if missing_scope_field is not None:
            assert compiled_problems
            assert compiler_contexts
            compiled_context = compiler_contexts[0]
            assert "runtime_identity" not in compiled_context
            candidate_context = compiled_context["candidate_context"]
            assert isinstance(candidate_context, dict)
            assert not set(candidate_context).intersection(
                {"tenant_id", "cell_id", "job_id", "run_id", "runtime_identity"}
            )
            source_context = compiled_problems[0].nl_provenance.source_context
            assert "runtime_identity" not in source_context
            if missing_scope_field == "cell_id":
                assert "cell_id" not in compiled_context
                assert source_context["tenant_id"] == "tenant-fixture"
                assert "cell_id" not in source_context
                assert "cell-default" not in source_context.values()
                assert source_context["job_id"] == record.job_id
                assert source_context["run_id"] == str(record.run_id)
                assert completed.progress["target_world_scope_status"] == "not_established"
                stored_request = service._load_payload_ref(
                    str(record.payload_ref),
                    kind="runtime.control_job_payload.natural_language_run",
                )
                assert (
                    stored_request["context"]["runtime_identity"]["cell_id"]
                    == "cell-request-runtime-foreign"
                )
            assert completed.progress["state"] == "completed"
            assert completed.progress["execution_band"] == "candidate"
            assert completed.progress["status"] == "not_established"
            assert completed.progress["candidate_computation_status"] == "completed"
            assert completed.progress["proposal_persistence_status"] == "not_established"
            assert completed.progress["limitation_code"] == (
                "candidate_proposal_owner_scope_not_established"
            )
            assert completed.progress["runtime_diagnostic_event_status"] == "not_established"
            assert completed.progress["candidate_proposal_ref"] is None
            assert completed.progress["n5_status"] == "not_run"
            assert completed.progress["n8_status"] == "not_run"
            assert completed.progress["n9_status"] == "not_run"
            assert completed.progress["s8_status"] == "not_run"
            proposals = [
                path
                for path in service._artifact_store.base.rglob("*.manifest.json")
                if "runtime.quality.n4_candidate_proposal" in path.read_text()
            ]
            assert not proposals
            return
        assert completed.progress["status"] == "candidate_limited"
        assert completed.progress["execution_band"] == "candidate"
        assert completed.progress["n5_status"] == "not_run"
        assert completed.progress["n8_status"] == "not_run"
        assert completed.progress["n9_status"] == "not_run"
        assert completed.progress["s8_status"] == "not_run"
        assert "compiled_recursive_generation_cycle_ref" not in completed.progress
        assert "normative_disposition_ref" not in completed.progress
        proposal_locator = completed.progress["candidate_proposal_ref"]
        assert proposal_locator["schema_version"] == (
            "policyos.runtime.quality.n4_candidate_proposal_locator.v1"
        )
        assert proposal_locator["artifact_ref"]["kind"] == ("runtime.quality.n4_candidate_proposal")
        assert proposal_locator["artifact_ref"]["media_type"] == "application/json"
        repository = GenerationSourceRepository(service._artifact_store)
        proposal = repository.load_candidate_proposal_for_served_job(
            proposal_locator,
            job_id=launch.job_id,
            run_id=str(record.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            raw_request=raw_request,
        )
        assert proposal.problem.nl_provenance.raw_request == raw_request
        assert proposal.proposal.trinity_bundle.policy_spec.interventions
        assert proposal.proposal.limitation_code == "cycle_substrate_context_unavailable"
        assert proposal.authority_purpose == "candidate_proposal"
        assert proposal.status == "candidate_limited"
        assert proposal.execution_band == "candidate"
        assert proposal.stage == "n4_proposal_only"
        assert (
            proposal.n5_status,
            proposal.n8_status,
            proposal.n9_status,
            proposal.s8_status,
        ) == ("not_run", "not_run", "not_run", "not_run")

        # Core finalization owns the N4 artifact root for ordinary run readers;
        # its run-level manifest is not a policy-promotion signal.
        core_run_id = str(completed.progress["core_run_id"])
        core_source = load_terminal_core_run_source(
            store=service._artifact_store,  # noqa: SLF001
            core_runs_root=service._core_runs_root,  # noqa: SLF001
            run_id=core_run_id,
        )
        assert core_source.manifest.run_id == core_run_id
        assert proposal.core_run_id == core_run_id
        assert proposal.control_job_attempt == completed.attempt
        assert len(core_source.manifest.outputs) == 1
        assert core_source.manifest.outputs[0].kind == ("runtime.quality.n4_candidate_proposal")
        assert (
            core_source.manifest.outputs[0].model_dump(mode="json")
            == proposal_locator["artifact_ref"]
        )
        assert (
            core_source.manifest_ref.model_dump(mode="json")
            == completed.progress["core_manifest_artifact_ref"]
        )
        assert str(core_source.manifest_ref.artifact_id) == completed.progress["manifest_ref"]
        assert service._promotion_runtime.store is service._artifact_store
    finally:
        service.close()


async def _run_controlled_simulate_only_job_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    *,
    proposal_source_persistence_failure: bool = False,
    local_sibling_mechanism_witness: bool = False,
    root_input_factory: Callable[[Any], None] | None = None,
    registered_ncm_outcome: bool = True,
    source_repo_root: Path | None = None,
) -> SimpleNamespace:
    """Run the controlled candidate N5 path; sibling mode is local mechanism only.

    The local sibling mode duplicates the root problem under test-only node refs
    to exercise persisted partial-checkpoint and fresh-GET behavior. Those refs
    are not source-derived child designs and establish no V6 source-positive.
    """
    from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
    from polisyos.core.security import (
        get_current_access_scope_or_none,
        tenant_scope,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextOffer,
        CandidateSimulationN5InputV5,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextOwnerError,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        derive_recursive_design_graph,
    )
    from polisyos.runtime.quality.design_generation import (
        N4CandidateScenarioProposalCandidate,
        N4CandidateScenarioProposalRun,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        JointSimulationPort,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveLeafContextOwner,
    )
    from tests._helpers.controlled_candidate_profile import (
        _build_configured_procurement_profile,
        _configured_procurement_profile,
        _controlled_procurement_recording,
        _controlled_registered_tax_recording,
        _current_compiler_problem,
    )
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.quality.test_generation_cycle import REPO_ROOT
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    recording_id = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
    recording_matches = tuple(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == recording_id
    )
    assert len(recording_matches) == 1
    recording = recording_matches[0]
    original_problem = _current_compiler_problem(recording)
    problem_payload = original_problem.model_dump(mode="python")
    problem_payload["outcome_of_interest"] = {
        **original_problem.outcome_of_interest.model_dump(mode="python"),
        "target_variable": "government.balance",
        # Keep the captured metric id. No source contract binds it to this
        # changed target, so the empirical consumer must retain not_established.
    }
    if registered_ncm_outcome:
        candidate_levers = list(original_problem.candidate_lever_space.candidate_levers)
    else:
        candidate_levers = [
            lever.model_copy(update={"target_slot": "cells.distress_score"})
            for lever in original_problem.candidate_lever_space.candidate_levers
        ]
    problem_payload.update(
        {
            "problem_statement": "Exercise a registered NCM outcome in a controlled served fixture.",
            "candidate_lever_space": original_problem.candidate_lever_space.model_copy(
                update={"candidate_levers": candidate_levers}
            ).model_dump(mode="python"),
        }
    )
    # Revalidation through the current union owner materializes the strict v3
    # qualified outcome type required for a dotted canonical target.
    problem = type(original_problem).model_validate(problem_payload)
    outcome_variable = problem.outcome_of_interest.target_variable
    if registered_ncm_outcome:
        controlled_recording = _controlled_registered_tax_recording(
            recording,
            outcome_variable=outcome_variable,
            rate=0,
        )
    else:
        controlled_recording = _controlled_procurement_recording(
            recording,
            outcome_variable=outcome_variable,
        )
    # Scope the CAS before profile, source, and context writes so the fresh
    # tenant-scoped reader resolves the same owner-bound artifacts.
    store = FileSystemCAS(tmp_path / ".polisyos").for_tenant(
        "tenant-fixture",
        "cell-fixture",
    )
    profile_args = {
        "recorded_problem": problem,
        "tmp_path": tmp_path,
        "artifact_store": store,
        "tenant_id": "tenant-fixture",
        "cell_id": "cell-fixture",
        "repo_root": REPO_ROOT,
    }
    if registered_ncm_outcome:
        profile, model_declaration, _ = _build_configured_procurement_profile(
            **profile_args,
            rule_operator_kind="tax_relief_rate",
            rule_parameter_id="rate",
            rule_target_world_slot="global.tax_rate",
            rule_unit_id="ratio",
            rule_minimum=0,
            rule_maximum=0,
            target_baseline=0.25,
        )
    else:
        profile, model_declaration = _configured_procurement_profile(**profile_args)
    assert profile.profile_selection_ref == cycle_job_profile_selection_ref(problem)
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        service = _build_control_service(
            tmp_path,
            artifact_store=store,
            candidate_simulation_profiles=(profile,),
            candidate_simulation_model_declarations=(model_declaration,),
            repo_root=source_repo_root,
        )
    assert service._artifact_store is store
    source_owner = service._cycle_substrate_context_admission_owner
    assert type(source_owner) is ConfiguredCandidateSimulationContextAdmissionOwner
    assert source_owner.store is service._artifact_store
    problem_ref = cycle_job_design_problem_ref(problem)
    admission_observations: list[tuple[dict[str, object], object]] = []
    admission_attempts: list[tuple[object, dict[str, object]]] = []
    original_admit = ConfiguredCandidateSimulationContextAdmissionOwner.admit_context

    def record_admission(owner, **kwargs):
        admission_attempts.append((owner, dict(kwargs)))
        offer = original_admit(owner, **kwargs)
        if owner is source_owner:
            admission_observations.append((dict(kwargs), offer))
        return offer

    monkeypatch.setattr(
        ConfiguredCandidateSimulationContextAdmissionOwner,
        "admit_context",
        record_admission,
    )
    owner_refs = []
    owner_replays = []
    owner_replay_refs = []
    owner_replay_calls = []
    owner_replay_currentness_refusals = []
    verified_scope_observations = []
    n5_port_observations = []
    n5_engine_requests = []
    compiler_calls = []
    compiled_runs = []
    n4_organ_runs = []
    n4_port_attempts = []
    n4_proposal_ports = []
    execution_order: list[tuple[str, str]] = []
    started_core_contexts = []

    from polisyos.core.run.context import RunContext
    from polisyos.core.trace import TraceRecord

    original_core_start = RunContext.start

    def record_core_start(cls, *args, **kwargs):
        context = original_core_start(*args, **kwargs)
        trace_path = context.trace_path
        assert trace_path is not None
        records = [
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        assert records[0].event == "RUN_STARTED"
        assert records[0].run_id == context.run_manifest.run_id
        execution_order.append(("RUN_STARTED", records[0].run_id))
        started_core_contexts.append(context)
        if root_input_factory is not None:
            root_input_factory(context)
        return context

    monkeypatch.setattr(RunContext, "start", classmethod(record_core_start))

    original_n4_port = N4GenerationPort.__call__

    async def record_n4_port(port, problem_for_cycle, *, cycle_index):
        execution_order.append(("N4_ENTER", ""))
        n4_port_attempts.append((port, problem_for_cycle, cycle_index))
        return await original_n4_port(
            port,
            problem_for_cycle,
            cycle_index=cycle_index,
        )

    monkeypatch.setattr(N4GenerationPort, "__call__", record_n4_port)

    original_n5_port = JointSimulationPort.__call__
    original_n5_engine = JointSimulationHorizonController.run

    def record_n5_port(port, *, candidate, problem, cycle_index, **kwargs):
        execution_order.append(("N5_ENTER", ""))
        observation = original_n5_port(
            port,
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
            **kwargs,
        )
        n5_port_observations.append(
            SimpleNamespace(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
                context=port._cycle_substrate_context,
                observation=observation,
                input_record=kwargs.get("candidate_simulation_input"),
                input_ref=kwargs.get("candidate_simulation_input_ref"),
            )
        )
        return observation

    def record_n5_engine(controller, request):
        n5_engine_requests.append(request)
        return original_n5_engine(controller, request)

    monkeypatch.setattr(JointSimulationPort, "__call__", record_n5_port)
    monkeypatch.setattr(JointSimulationHorizonController, "run", record_n5_engine)

    async def compile_fixture_problem(**kwargs):
        compiler_calls.append(kwargs)
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_fixture_problem,
    )

    context_persist_attempts = []
    original_context_persist = CycleSubstrateContextArtifactOwner.persist_for_current_job

    def record_context_persist_attempt(owner, context, *, problem, verified_nl_job_scope=None):
        context_persist_attempts.append((context, problem, verified_nl_job_scope))
        return original_context_persist(
            owner,
            context,
            problem=problem,
            verified_nl_job_scope=verified_nl_job_scope,
        )

    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner,
        "persist_for_current_job",
        record_context_persist_attempt,
    )

    # Rebind the profile to a different active outcome while preserving all
    # self-hashes. The exact configured owner must reject the mismatched model
    # declaration before it persists a context or reaches N4/N5.
    probe_outcome_variable = f"{outcome_variable}_negative_control"
    probe_problem = problem.model_copy(
        update={
            "outcome_of_interest": problem.outcome_of_interest.model_copy(
                update={"target_variable": probe_outcome_variable}
            )
        }
    )
    probe_profile_fields = profile.model_dump(mode="json", exclude={"content_hash"})
    probe_profile_fields["profile_selection_ref"] = cycle_job_profile_selection_ref(probe_problem)
    probe_profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **probe_profile_fields,
            "content_hash": generation_cycle_service.gy_content_hash(probe_profile_fields),
        }
    )
    probe_declaration_fields = model_declaration.model_dump(mode="json", exclude={"content_hash"})
    probe_declaration_fields.update(
        {
            "profile_config_ref": candidate_simulation_profile_ref(probe_profile),
            "profile_content_hash": probe_profile.content_hash,
            "profile_selection_ref": probe_profile.profile_selection_ref,
        }
    )
    probe_declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **probe_declaration_fields,
            "content_hash": generation_cycle_service.gy_content_hash(probe_declaration_fields),
        }
    )
    probe_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(probe_profile,),
        model_declarations=(probe_declaration,),
        store=service._artifact_store,
    )
    with pytest.raises(CycleSubstrateContextOwnerError) as mismatch:
        probe_owner.admit_context(
            problem=probe_problem,
            job_id="negative-control-job",
            run_id="negative-control-run",
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
        )
    assert mismatch.value.code == "candidate_simulation_model_outcome_problem_mismatch"
    assert len(admission_attempts) == 1
    assert admission_attempts[0][0] is probe_owner
    assert admission_attempts[0][1]["problem"] is probe_problem
    assert admission_observations == []
    assert context_persist_attempts == []
    assert owner_refs == owner_replays == owner_replay_refs == verified_scope_observations == []
    assert n5_port_observations == n5_engine_requests == []
    assert n4_port_attempts == []
    assert compiler_calls == compiled_runs == n4_organ_runs == []

    recorded_n4_client = n4_contract.RecordedGenerationReplayClient(controlled_recording)
    source_persistence_failures: list[str] = []
    if proposal_source_persistence_failure:

        def refuse_n4_source_persist(repository, *, source_record):
            source_persistence_failures.append(type(source_record).__name__)
            raise OSError("controlled_fixture_source_persistence_failure")

        monkeypatch.setattr(
            GenerationSourceRepository,
            "persist_candidate_scenario_source_v2",
            refuse_n4_source_persist,
        )

    original_persist = CycleSubstrateContextArtifactOwner.persist_for_current_job
    original_resolve = CycleSubstrateContextArtifactOwner.resolve_for_current_job

    def record_persist(owner, context, *, problem, verified_nl_job_scope=None):
        assert owner._store is service._artifact_store
        assert verified_nl_job_scope is not None
        assert get_current_access_scope_or_none() is None
        for changed_scope in (
            verified_nl_job_scope.model_copy(update={"tenant_id": "foreign-tenant"}),
            verified_nl_job_scope.model_copy(update={"attempt": verified_nl_job_scope.attempt + 1}),
            verified_nl_job_scope.model_copy(update={"actor_subject": "foreign-actor"}),
        ):
            assert changed_scope._was_issued_by_verified_nl_execution_owner
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_job_verified_scope_mismatch",
            ):
                original_persist(
                    owner,
                    context,
                    problem=problem,
                    verified_nl_job_scope=changed_scope,
                )
        verified_scope_observations.append(verified_nl_job_scope)
        ref = original_persist(
            owner,
            context,
            problem=problem,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        owner_refs.append(ref)
        return ref

    def record_resolve(
        owner,
        ref,
        *,
        problem,
        repo_root: Path | None = None,
        verified_nl_job_scope=None,
    ):
        assert owner._store is service._artifact_store
        assert get_current_access_scope_or_none() is None
        assert repo_root == REPO_ROOT
        assert verified_nl_job_scope is not None
        verified_scope_observations.append(verified_nl_job_scope)
        if local_sibling_mechanism_witness:
            for changed_scope in (
                verified_nl_job_scope.model_copy(update={"tenant_id": "foreign-tenant"}),
                verified_nl_job_scope.model_copy(
                    update={"attempt": verified_nl_job_scope.attempt + 1}
                ),
                verified_nl_job_scope.model_copy(update={"actor_subject": "foreign-actor"}),
            ):
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_verified_scope_mismatch",
                ):
                    original_resolve(
                        owner,
                        ref,
                        problem=problem,
                        repo_root=repo_root,
                        verified_nl_job_scope=changed_scope,
                    )
        if not owner_replay_currentness_refusals:
            # The same persisted artifact must reject changed job scope, problem
            # basis, and source root; valid CAS bytes and markers are insufficient.
            changed_scope = verified_nl_job_scope.model_copy(
                update={"attempt": verified_nl_job_scope.attempt + 1}
            )
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_job_verified_scope_mismatch",
            ):
                original_resolve(
                    owner,
                    ref,
                    problem=problem,
                    repo_root=repo_root,
                    verified_nl_job_scope=changed_scope,
                )
            owner_replay_currentness_refusals.append("issued_scope_mismatch_refused")
            changed_problem = problem.model_copy(
                update={
                    "problem_statement": (
                        problem.problem_statement + " [currentness basis negative control]"
                    )
                }
            )
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_job_binding_mismatch",
            ):
                original_resolve(
                    owner,
                    ref,
                    problem=changed_problem,
                    repo_root=repo_root,
                    verified_nl_job_scope=verified_nl_job_scope,
                )
            owner_replay_currentness_refusals.append("changed_problem_basis_refused")
            unrelated_source_root = tmp_path / "empty-current-source-root"
            unrelated_source_root.mkdir()
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="candidate_cycle_source_profile_resolve_owner_refused",
            ):
                original_resolve(
                    owner,
                    ref,
                    problem=problem,
                    repo_root=unrelated_source_root,
                    verified_nl_job_scope=verified_nl_job_scope,
                )
            owner_replay_currentness_refusals.append("unrelated_source_root_refused")
        artifact = original_resolve(
            owner,
            ref,
            problem=problem,
            repo_root=repo_root,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        owner_replay_calls.append((owner, ref, problem, repo_root, verified_nl_job_scope))
        owner_replays.append(artifact)
        owner_replay_refs.append(ref)
        return artifact

    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner,
        "persist_for_current_job",
        record_persist,
    )
    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner,
        "resolve_for_current_job",
        record_resolve,
    )

    original_controller_builder = (
        generation_cycle_service.build_default_recursive_generation_cycle_controller
    )

    def build_fixture_recursive_controller(**kwargs):
        recursive = original_controller_builder(**kwargs)
        original_run = recursive.run
        assert recursive._cycle_controller_factory is None

        async def run_with_fixture_generation(*args, **run_kwargs):
            contexts = run_kwargs["cycle_substrate_contexts_by_node"]
            handoffs = run_kwargs["candidate_simulation_handoffs_by_node"]
            currentness_resolvers = run_kwargs["candidate_simulation_currentness_resolvers_by_node"]
            assert contexts is not None and len(contexts) == 1
            assert handoffs is not None and len(handoffs) == 1
            assert currentness_resolvers is not None and len(currentness_resolvers) == 1
            node_ref = next(iter(contexts))
            resolved_context = contexts[node_ref]
            handoff = handoffs[node_ref]
            currentness_resolver = currentness_resolvers[node_ref]
            assert callable(currentness_resolver)
            assert handoff.context == resolved_context
            assert handoff.profile == profile
            assert handoff.model_declaration == model_declaration

            class _ControlledN4GenerationPort(N4GenerationPort):
                async def __call__(self, problem_for_cycle, *, cycle_index):
                    proposal_run = await super().__call__(
                        problem_for_cycle,
                        cycle_index=cycle_index,
                    )
                    n4_organ_runs.append(proposal_run)
                    return proposal_run

            generator = _ControlledN4GenerationPort(
                model_id=str(recording["model_id"]),
                llm_client=recorded_n4_client,
                repo_root=kwargs["repo_root"],
                cycle_substrate_context=resolved_context,
                candidate_simulation_handoff=handoff,
            )
            n4_proposal_ports.append(generator)
            run_args = list(args)
            if local_sibling_mechanism_witness:
                graph = run_args[0]
                root_ref = graph.root_design_ref
                first_ref = f"{root_ref}#local-mechanism-successful-sibling"
                second_ref = f"{root_ref}#local-mechanism-failed-sibling"
                root_problem = run_kwargs["problems_by_node"][root_ref]
                child_graph = derive_recursive_design_graph(
                    design_ref=root_ref,
                    module_refs=(first_ref, second_ref),
                    parent_child_edges=(
                        (root_ref, first_ref),
                        (root_ref, second_ref),
                    ),
                    rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
                )
                run_args[0] = child_graph
                run_kwargs["problems_by_node"] = {
                    root_ref: root_problem,
                    first_ref: root_problem,
                    second_ref: root_problem,
                }
                contexts.clear()
                contexts.update({first_ref: resolved_context, second_ref: resolved_context})
                handoffs.clear()
                handoffs.update({first_ref: handoff, second_ref: handoff})
                currentness_resolvers.clear()
                intents = run_kwargs["execution_intents_by_node"]
                intents.clear()
                intents.update({first_ref: "simulate_only", second_ref: "simulate_only"})
                run_kwargs["leaf_context_owner"] = RecursiveLeafContextOwner(
                    store=service._artifact_store,
                    context_owner=CycleSubstrateContextArtifactOwner(
                        store=service._artifact_store,
                        control_store=service._control_store,
                    ),
                    admission_owner=source_owner,
                    verified_nl_job_scope=verified_scope_observations[0],
                )

                class _FailingSiblingN4Port(N4GenerationPort):
                    async def __call__(self, problem_for_cycle, *, cycle_index):
                        del problem_for_cycle, cycle_index
                        raise GenerationCycleError(
                            "controlled_second_sibling_failure",
                            "later child failed after its earlier sibling completed",
                        )

                failed_generator = _FailingSiblingN4Port(
                    model_id=str(recording["model_id"]),
                    repo_root=kwargs["repo_root"],
                    cycle_substrate_context=resolved_context,
                    candidate_simulation_handoff=handoff,
                )
                run_kwargs["n4_generation_ports_by_node"] = {
                    first_ref: generator,
                    second_ref: failed_generator,
                }
            else:
                run_kwargs["n4_generation_ports_by_node"] = {node_ref: generator}
            compiled = await original_run(*run_args, **run_kwargs)
            compiled_runs.append(compiled)
            return compiled

        recursive.run = run_with_fixture_generation
        return recursive

    monkeypatch.setattr(
        generation_cycle_service,
        "build_default_recursive_generation_cycle_controller",
        build_fixture_recursive_controller,
    )

    if local_sibling_mechanism_witness:
        original_compile = generation_cycle_service.compile_and_run_recursive_generation_cycle

        async def compile_with_sibling_budget(**kwargs):
            budget = kwargs["recursive_budget"]
            kwargs["recursive_budget"] = budget.model_copy(update={"max_depth": 1, "max_nodes": 3})
            resolution = kwargs["recursive_budget_resolution"]
            if resolution is not None:
                kwargs["recursive_budget_resolution"] = resolution.model_copy(
                    update={
                        "recursive_budget": resolution.recursive_budget.model_copy(
                            update={"max_depth": 1, "max_nodes": 3}
                        ),
                        "requested_candidate_children": 2,
                        "effective_candidate_children": 2,
                        "child_budget_profile": "candidate-lever-exploration-at-most-2.v1",
                    }
                )
            return await original_compile(**kwargs)

        monkeypatch.setattr(
            generation_cycle_service,
            "compile_and_run_recursive_generation_cycle",
            compile_with_sibling_budget,
        )

    service_transferred = False
    try:
        context_payload = {
            "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                mode="json"
            )
        }
        request = NaturalLanguageRunRequest(
            request=problem.nl_provenance.raw_request,
            llm_model=str(recording["model_id"]),
            context=context_payload,
            max_iterations=1,
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        job = service._control_store.get_job(launch.job_id)
        assert job is not None and job.run_id is not None
        leased = service._control_store.lease_next_job(
            worker_id="r1-fixture-worker",
            lease_seconds=60,
        )
        assert leased is not None and leased.job_id == launch.job_id
        assert leased.attempt == 1
        with (
            n4_contract._recorded_runtime_environment(recording),
            service._control_store.job_execution_fence(
                job_id=leased.job_id,
                worker_id=leased.lease_owner,
                attempt=leased.attempt,
            ),
        ):
            service._process_control_job(leased)

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None and completed.state == "completed"
        progress = completed.progress
        if proposal_source_persistence_failure:
            assert source_persistence_failures
            assert progress["execution_band"] == "candidate"
            assert progress["status"] == "not_established"
            assert progress["candidate_computation_status"] == "not_established"
            assert progress["limitation_code"] == (
                "candidate_scenario_source_persistence_not_established"
            )
            assert progress["proposal_persistence_status"] == "not_established"
            assert progress["candidate_proposal_ref"] is None
            assert progress["n5_status"] == "not_run"
            assert progress["n8_status"] == "not_run"
            assert progress["n9_status"] == "not_admitted"
            assert progress["s8_status"] == "blocked"
            assert "n9_receipt_ref" not in progress
            assert "compiled_recursive_generation_cycle_artifact_ref" not in progress
            assert "normative_disposition_ref" not in progress
            assert progress["core_terminal_status"] == "error"
            assert len(started_core_contexts) == 1
            labels = [label for label, _ in execution_order]
            assert labels.index("RUN_STARTED") < labels.index("N4_ENTER")
            assert "N5_ENTER" not in labels
            assert n5_port_observations == n5_engine_requests == []
            assert len(n4_port_attempts) == 2
            assert len(n4_proposal_ports) == 1
            assert n4_port_attempts[0][0] is not n4_proposal_ports[0]
            assert n4_port_attempts[1][0] is n4_proposal_ports[0]
            assert n4_port_attempts[0][1] is problem
            assert n4_port_attempts[1][1] is problem

            from polisyos.runtime.http.services.adapters.core_run import (
                derive_control_job_core_run_id,
                load_completed_control_job_core_run_source,
                load_terminal_core_run_source,
            )

            expected_core_id = derive_control_job_core_run_id(
                job_id=completed.job_id,
                control_run_id=str(completed.run_id),
                attempt=completed.attempt,
            )
            terminal = load_terminal_core_run_source(
                store=service._artifact_store,
                core_runs_root=service._core_runs_root,
                run_id=expected_core_id,
            )
            assert terminal.manifest.status == "error"
            assert terminal.manifest.outputs == []
            assert terminal.manifest.control_job_id == completed.job_id
            with pytest.raises(ValueError, match="control_job_core_run_terminal_binding_mismatch"):
                load_completed_control_job_core_run_source(
                    store=service._artifact_store,
                    core_runs_root=service._core_runs_root,
                    job=completed,
                    expected_control_run_id=str(completed.run_id),
                    tenant_id="tenant-fixture",
                    cell_id="cell-fixture",
                )
            service_transferred = True
            return SimpleNamespace(service=service, job=completed, terminal=terminal)

        assert progress["status"] == "simulation_only"
        assert progress["execution_intent_band"] == "simulate_only_attempt"
        assert progress["s8_status"] == "not_run"
        assert progress["publication_status"] == "not_run"
        from polisyos.runtime.http.services.adapters.core_run import (
            derive_control_job_core_run_id,
        )

        assert len(started_core_contexts) == 1
        started_context = started_core_contexts[0]
        assert started_context.run_manifest.control_job_id == launch.job_id
        assert started_context.run_manifest.run_id == derive_control_job_core_run_id(
            job_id=launch.job_id,
            control_run_id=str(completed.run_id),
            attempt=leased.attempt,
        )
        ordered_labels = [label for label, _ in execution_order]
        assert ordered_labels.index("RUN_STARTED") < ordered_labels.index("N4_ENTER")
        assert ordered_labels.index("N4_ENTER") < ordered_labels.index("N5_ENTER")
        assert progress["core_run_id"] == started_context.run_manifest.run_id
        assert progress["core_run_attempt"] == leased.attempt
        assert progress["core_manifest_artifact_ref"]["artifact_id"] == progress["manifest_ref"]
        assert (
            progress["compiled_recursive_generation_cycle_artifact_ref"]["artifact_id"]
            == (progress["compiled_recursive_generation_cycle_ref"])
        )
        from dataclasses import replace

        from polisyos.runtime.http.services.adapters.core_run import (
            load_completed_control_job_core_run_source,
        )

        selected_core = load_completed_control_job_core_run_source(
            store=service._artifact_store,
            core_runs_root=service._core_runs_root,
            job=completed,
            expected_control_run_id=str(completed.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
        )
        assert selected_core.run_id == started_context.run_manifest.run_id
        assert selected_core.manifest.control_job_id == completed.job_id
        with pytest.raises(ValueError, match="control_job_core_run_attempt_pointer_mismatch"):
            load_completed_control_job_core_run_source(
                store=service._artifact_store,
                core_runs_root=service._core_runs_root,
                job=replace(
                    completed,
                    progress={
                        **progress,
                        "core_run_id": "control-" + "0" * 64,
                    },
                ),
                expected_control_run_id=str(completed.run_id),
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
            )
        with pytest.raises(ValueError, match="control_job_core_run_source_not_completed"):
            load_completed_control_job_core_run_source(
                store=service._artifact_store,
                core_runs_root=service._core_runs_root,
                job=replace(
                    completed,
                    progress={**progress, "core_run_attempt": True},
                ),
                expected_control_run_id=str(completed.run_id),
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
            )
        assert progress["cycle_substrate_context_job_ref"]
        assert len(compiler_calls) == 1
        assert compiler_calls[0]["nl_request"] == problem.nl_provenance.raw_request
        # A currentness callback and a separate artifact read are distinct
        # owner operations; they need not create one profile admission per read.
        # Each successful read is recorded only after the owner validates the
        # persisted job artifact, current source basis, and issued scope.
        assert len(owner_replays) >= 2
        assert owner_replay_currentness_refusals == [
            "issued_scope_mismatch_refused",
            "changed_problem_basis_refused",
            "unrelated_source_root_refused",
        ]
        assert len(owner_replay_calls) == len(owner_replays)
        assert all(
            type(owner) is CycleSubstrateContextArtifactOwner
            and owner._store is service._artifact_store
            and artifact_ref_identity_key(ref) == artifact_ref_identity_key(owner_refs[0])
            and replay_problem is problem
            and cycle_job_design_problem_ref(replay_problem) == problem_ref
            and replay_repo_root == REPO_ROOT
            and verified_scope is verified_scope_observations[0]
            and verified_scope._was_issued_by_verified_nl_execution_owner
            and (verified_scope.job_id, verified_scope.run_id) == (launch.job_id, str(job.run_id))
            and (verified_scope.tenant_id, verified_scope.cell_id)
            == ("tenant-fixture", "cell-fixture")
            for owner, ref, replay_problem, replay_repo_root, verified_scope in owner_replay_calls
        )
        assert admission_observations
        admitted_offer = admission_observations[0][1]
        assert type(source_owner) is ConfiguredCandidateSimulationContextAdmissionOwner
        assert source_owner.store is service._artifact_store
        assert all(
            type(offer) is CandidateSimulationContextOffer for _, offer in admission_observations
        )
        assert all(
            type(call["problem"]) is type(problem)
            and cycle_job_design_problem_ref(call["problem"]) == problem_ref
            and call["job_id"] == launch.job_id
            and call["run_id"] == str(job.run_id)
            and call["tenant_id"] == "tenant-fixture"
            and call["cell_id"] == "cell-fixture"
            for call, _ in admission_observations
        )
        assert all(
            offer.profile == profile
            and offer.model_declaration == model_declaration
            and offer.context.design_problem_ref == problem_ref
            for _, offer in admission_observations
        )
        assert len(owner_refs) == 1
        assert len(owner_replay_refs) == len(owner_replays)
        assert all(
            artifact_ref_identity_key(ref) == artifact_ref_identity_key(owner_refs[0])
            for ref in owner_replay_refs
        )
        assert len(context_persist_attempts) == 4
        assert context_persist_attempts[-1][1] is problem
        assert context_persist_attempts[-1][2] is verified_scope_observations[0]
        assert len(verified_scope_observations) == len(owner_replays) + 1
        assert all(scope is verified_scope_observations[0] for scope in verified_scope_observations)
        assert verified_scope_observations[0]._was_issued_by_verified_nl_execution_owner
        assert verified_scope_observations[0].job_id == launch.job_id
        assert verified_scope_observations[0].run_id == str(job.run_id)
        assert verified_scope_observations[0].tenant_id == "tenant-fixture"
        assert verified_scope_observations[0].cell_id == "cell-fixture"
        assert verified_scope_observations[0].worker_id == leased.lease_owner
        assert verified_scope_observations[0].attempt == leased.attempt
        assert str(owner_refs[0].artifact_id) == progress["cycle_substrate_context_job_ref"]

        # Use the last live N5-bound owner replay; it verified the current
        # artifact schema, CAS bytes, and full job scope before simulation.
        context_artifact = owner_replays[-1]
        assert context_artifact.job_id == launch.job_id
        assert context_artifact.run_id == str(job.run_id)
        assert context_artifact.tenant_id == "tenant-fixture"
        assert context_artifact.cell_id == "cell-fixture"
        assert context_artifact.problem == problem
        assert all(
            replay.job_id == launch.job_id
            and replay.run_id == str(job.run_id)
            and replay.tenant_id == "tenant-fixture"
            and replay.cell_id == "cell-fixture"
            and replay.problem == problem
            and replay.context.content_hash == context_artifact.context.content_hash
            for replay in owner_replays
        )
        assert all(
            offer.context.content_hash == context_artifact.context.content_hash
            and offer.profile_config_ref == admitted_offer.profile_config_ref
            and offer.model_declaration_ref == admitted_offer.model_declaration_ref
            and offer.ncm_ref == admitted_offer.ncm_ref
            for _, offer in admission_observations
        )
        assert context_artifact.profile_admission_status == "not_established"
        assert context_artifact.s8_status == "blocked"
        assert context_artifact.context.world_model_record.authority_status == "limited"
        assert context_artifact.context.world_model_record.simulation_model_ref.calibrated is False
        assert n5_port_observations
        assert len(n4_organ_runs) == 1
        # The served simulate-only route runs a persisted root N4 source before
        # the ordinary N4 proposal leaf. Keep both real N4 calls in the count.
        assert len(n4_port_attempts) == 2
        assert len(n4_proposal_ports) == 1
        assert n4_port_attempts[0][0] is not n4_proposal_ports[0]
        assert n4_port_attempts[1][0] is n4_proposal_ports[0]
        assert n4_port_attempts[0][1] is problem
        proposal_run = n4_organ_runs[0]
        assert type(proposal_run) is N4CandidateScenarioProposalRun
        proposal_problem_ref = generation_cycle_service.gy_content_hash(
            problem.model_dump(mode="json")
        )
        assert proposal_run.proposal.design_problem_ref == proposal_problem_ref
        assert proposal_run.proposal.trinity_bundle is not None
        assert n5_engine_requests
        for request in n5_engine_requests:
            assert request.world_model_record.content_hash == (
                context_artifact.context.world_model_record.content_hash
            )
        for observed in n5_port_observations:
            assert type(observed.candidate) is N4CandidateScenarioProposalCandidate
            assert observed.problem == problem
            assert observed.context.content_hash == context_artifact.context.content_hash
            assert observed.observation.candidate_id == observed.candidate.candidate_id
            assert observed.observation.status == "joint_simulated"
            assert type(observed.input_record) is CandidateSimulationN5InputV5
            assert type(observed.input_ref) is ArtifactRef
            assert observed.input_record.context_job_ref == owner_refs[0]
            assert observed.input_record.profile_config_ref == admitted_offer.profile_config_ref
            assert (
                observed.input_record.model_declaration_ref == admitted_offer.model_declaration_ref
            )
            assert observed.input_record.ncm_ref == admitted_offer.ncm_ref
            assert observed.input_record.materialization.operator_kind == profile.rule.operator_kind
            assert observed.input_record.materialization.parameter_id == profile.rule.parameter_id
            assert (
                observed.input_record.materialization.target_world_slot
                == profile.rule.target_world_slot
            )
            assert observed.input_record.materialization.unit_id == profile.rule.unit_id
            assert observed.input_record.materialization.value == profile.rule.maximum
            if observed.observation.world_model_record is not None:
                assert observed.observation.world_model_record.content_hash == (
                    context_artifact.context.world_model_record.content_hash
                )
        assert len(compiled_runs) == 1
        recursive_run = compiled_runs[0]
        assert len(recursive_run.leaf_nodes) == 1
        leaf_run = recursive_run.leaf_nodes[0].cycle_run
        assert leaf_run is not None
        assert leaf_run.cycles
        assert leaf_run.promotion_port.status == "not_promoted"
        assert leaf_run.promotion_port.certified_candidate_ids == ()
        assert leaf_run.promotion_port.receipts == ()
        assert leaf_run.fronts.decision.candidate_ids == ()
        assert all(not summary.certified_by_n9 for summary in leaf_run.candidate_summaries)
        assert "n9_receipt_ref" not in progress
        assert progress["normative_disposition_status"] == "not_run"
        assert progress["s8_status"] == "not_run"
        assert progress["publication_status"] == "not_run"

        # Candidate-scenario N4 uses its own typed source record; this is not
        # the ordinary GenerationSource handoff path. Resolve the exact source
        # named by the N5 input and bind its proposal, selected atom, profile,
        # context, model declaration, numeric materialization, and result.
        repository = GenerationSourceRepository(service._artifact_store)
        assert len(n5_port_observations) == 1
        observed = n5_port_observations[0]
        candidate = observed.candidate
        input_record = observed.input_record
        assert type(candidate) is N4CandidateScenarioProposalCandidate
        assert type(input_record) is CandidateSimulationN5InputV5
        selected_source = repository.load_candidate_scenario_source_for_n5(
            input_record.n4_source_ref,
            expected_run_id=str(completed.run_id),
            expected_job_id=completed.job_id,
            expected_tenant_id="tenant-fixture",
            expected_cell_id="cell-fixture",
        )
        assert type(selected_source) is N4CandidateScenarioSourceRecordV3
        assert selected_source.origin_source_ref is None
        assert selected_source.profile == profile
        assert selected_source.candidate.candidate_id == candidate.candidate_id
        assert selected_source.candidate.atom.content_hash == candidate.atom.content_hash
        assert selected_source.candidate.atom.content_hash == input_record.original_n4_atom_hash
        assert selected_source.context_hash == context_artifact.context.content_hash
        assert selected_source.world_model_record_hash == (
            context_artifact.context.world_model_record.content_hash
        )
        selected_v2_source = selected_source.source_record
        selected_v1_source = selected_v2_source.source_record
        assert selected_v1_source.profile == profile
        assert selected_v1_source.problem == problem
        assert selected_v1_source.proposal.design_problem_ref == proposal_problem_ref
        assert selected_v1_source.cycle_problem_ref == problem_ref
        assert selected_v1_source.k_ref_limitation_code in {
            "historical_l2_confidence_withheld",
            "full_credal_reference_not_established",
        }
        assert (selected_v1_source.l2_confidence_vintage is not None) is (
            selected_v1_source.k_ref_limitation_code == "historical_l2_confidence_withheld"
        )
        assert selected_v1_source.l2_confidence_forwarded is False
        assert selected_v1_source.credal_reference_payload is None
        assert selected_v2_source.model_declaration == model_declaration
        assert selected_v2_source.model_declaration_ref == input_record.model_declaration_ref
        assert selected_v2_source.ncm_ref == input_record.ncm_ref
        assert selected_v2_source.world_model_record_id == (
            context_artifact.context.world_model_record.world_model_record_id
        )

        full_interventions = selected_v1_source.proposal.trinity_bundle.policy_spec.interventions
        selected_interventions = tuple(
            intervention
            for intervention in full_interventions
            if intervention.intervention_id == candidate.intervention_id
        )
        assert len(selected_interventions) == 1
        selected_intervention = selected_interventions[0]
        assert selected_intervention.kind == profile.rule.operator_kind
        assert selected_intervention.params == {profile.rule.parameter_id: profile.rule.maximum}
        assert candidate.atom.target_world_slots == (profile.rule.target_world_slot,)
        assert candidate.atom.direct_effect_bundle.params == selected_intervention.params
        assert input_record.materialization.operator_kind == selected_intervention.kind
        assert input_record.materialization.parameter_id == profile.rule.parameter_id
        assert input_record.materialization.value == profile.rule.maximum
        assert input_record.materialization.target_world_slot == profile.rule.target_world_slot
        assert input_record.materialization.unit_id == profile.rule.unit_id

        context_world = context_artifact.context.world_model_record
        assert context_world.simulation_model_ref.calibrated is False
        assert str(input_record.ncm_ref.artifact_id) in context_world.simulation_model_ref.ncm_refs
        problem_slot_ids = {
            lever.target_slot for lever in problem.candidate_lever_space.candidate_levers
        }
        context_slot_ids = {binding.slot_id for binding in context_world.policy_slot_map}
        assert problem_slot_ids <= context_slot_ids
        assert any(
            item.get("declaration_content_hash") == model_declaration.content_hash
            and item.get("status") == "candidate_only_not_empirically_grounded"
            for item in context_world.simulation_model_ref.assumptions
        )
        from polisyos.ir.analytics.ncm import load_ncm_spec_selected_view

        selected_ncm = load_ncm_spec_selected_view(
            _ensure_ir_artifact_store(service._artifact_store),
            input_record.ncm_ref,
            expected_tenant_id="tenant-fixture",
            expected_cell_id="cell-fixture",
            expected_declaration_ref=input_record.model_declaration_ref,
        )
        expected_ncm_variables = {
            model_declaration.target_world_slot,
            model_declaration.outcome_variable,
        }
        assert set(selected_ncm.endogenous_vars) == expected_ncm_variables
        assert {
            specification.associated_endogenous for specification in selected_ncm.exogenous_specs
        } == expected_ncm_variables
        assert {equation.variable for equation in selected_ncm.structural_equations} == (
            expected_ncm_variables
        )
        outcome_equation = next(
            equation
            for equation in selected_ncm.structural_equations
            if equation.variable == model_declaration.outcome_variable
        )
        assert outcome_equation.parents == [model_declaration.target_world_slot]
        assert outcome_equation.equation_params["coefficients"] == {
            model_declaration.target_world_slot: model_declaration.outcome_per_target_unit
        }
        assert outcome_equation.equation_params["intercept"] == (
            model_declaration.outcome_baseline
            - model_declaration.outcome_per_target_unit * model_declaration.target_baseline
        )
        assert input_record.outcome_variable == model_declaration.outcome_variable
        assert input_record.outcome_variable == problem.outcome_of_interest.target_variable
        target_baseline = profile.n5.baseline_state[model_declaration.target_world_slot]
        outcome_baseline = profile.n5.baseline_state[model_declaration.outcome_variable]
        assert (
            target_baseline
            == model_declaration.target_baseline
            == (profile.n5.baseline_state[profile.rule.target_world_slot])
        )
        assert outcome_baseline == model_declaration.outcome_baseline == 0.0
        assert model_declaration.outcome_variable == outcome_variable
        assert model_declaration.target_unit_id == profile.rule.unit_id
        outcome_binding = context_world.slot_binding(model_declaration.outcome_variable)
        assert outcome_binding is not None
        assert model_declaration.outcome_unit_id == outcome_binding.unit

        observation = observed.observation
        assert observation.status == "joint_simulated"
        assert observation.uncertainty_kind == "K_sim"
        assert observation.k_world_ref_before == observation.k_world_ref_after
        assert observation.k_world_ref_before == context_world.content_hash
        assert type(observation.simulation_result_ref) is ArtifactRef
        n5_result = load_joint_simulation_result(
            observation.simulation_result_ref,
            store=service._artifact_store,
            expected_world_model_record_content_hash=context_world.content_hash,
            expected_selected_outcomes=(outcome_variable,),
        )
        assert n5_result.uncertainty_kind == "K_sim"
        assert n5_result.world_credal_state_before == n5_result.world_credal_state_after
        effects = [
            point.effect[outcome_variable]
            for trajectory in n5_result.trajectories
            for point in trajectory.points
            if outcome_variable in point.effect
        ]
        expected_quantity = model_declaration.outcome_per_target_unit * (
            input_record.materialization.value - target_baseline
        )
        assert expected_quantity == pytest.approx(
            model_declaration.outcome_per_target_unit
            * (profile.rule.maximum - model_declaration.target_baseline),
            abs=1e-12,
        )
        assert len(effects) == profile.n5.replications
        assert effects == pytest.approx(
            [expected_quantity] * profile.n5.replications,
            abs=0.02,
        )

        assert leaf_run.cycles[-1].selected_candidate_ref == candidate.candidate_id
        assert leaf_run.cycles[-1].simulation.status == "joint_simulated"
        assert leaf_run.cycles[-1].simulation.candidate_id == candidate.candidate_id
        assert leaf_run.value_port.status == "value_pending_n8"
        assert leaf_run.value_port.authority_blockers == ("candidate_scenario_n5_only",)
        assert leaf_run.promotion_port.status == "not_promoted"
        assert leaf_run.promotion_port.certified_candidate_ids == ()
        assert all(not summary.certified_by_n9 for summary in leaf_run.candidate_summaries)
        assert all(summary.front != "decision" for summary in leaf_run.candidate_summaries)

        compiled_ref = ArtifactID.model_validate(
            progress["compiled_recursive_generation_cycle_ref"]
        )
        compiled_artifact_ref = ArtifactRef.model_validate(
            progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        fixture = SimpleNamespace(
            service=service,
            job=completed,
            problem=problem,
            profile=profile,
            model_declaration=model_declaration,
            compiled_payload=service._artifact_store.get_bytes(compiled_artifact_ref),
            compiled_ref=str(compiled_ref),
            cycle_substrate_context_job_ref=progress["cycle_substrate_context_job_ref"],
            n5_port_observations=tuple(n5_port_observations),
        )
        service_transferred = True
        return fixture

    finally:
        if not service_transferred:
            service.close()


@pytest.mark.asyncio
async def test_explicit_per_cell_ncm_fixture_request_remains_refused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """An explicit unsupported per-cell NCM outcome remains a typed refusal."""
    with pytest.raises(
        ValueError,
        match=r"controlled_wmr_ncm_outcome_scope_not_supported:cells\.distress_score",
    ):
        await _run_controlled_simulate_only_job_fixture(
            monkeypatch,
            tmp_path,
            registered_ncm_outcome=False,
        )


def test_control_job_core_identity_is_unique_per_lease_attempt() -> None:
    from polisyos.runtime.http.services.adapters.core_run import (
        derive_control_job_core_run_id,
    )

    common = {"job_id": "job-safe", "control_run_id": "run-safe"}
    first = derive_control_job_core_run_id(**common, attempt=1)
    retry = derive_control_job_core_run_id(**common, attempt=2)
    assert first != retry
    assert first.startswith("control-") and retry.startswith("control-")
    assert "/" not in first and "\\" not in first
    with pytest.raises(ValueError, match="control_job_core_run_identity_invalid"):
        derive_control_job_core_run_id(**common, attempt=0)


@pytest.mark.asyncio
async def test_served_simulate_only_replays_source_bound_n4_candidate_into_joint_n5(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A source-bound N4 candidate reaches a joint N5 request under a synthetic profile.

    The persisted source resolves to the candidate N5 actually simulated; the
    fixture does not establish production profile, S8, N9, or publication authority.
    """
    fixture = await _run_controlled_simulate_only_job_fixture(monkeypatch, tmp_path)
    assert fixture.n5_port_observations
    assert fixture.n5_port_observations[0].observation.simulation_result_ref is not None
    fixture.service.close()


def test_n5_run_projection_preserves_actual_shared_seed_pair_and_residual_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The typed run projection carries producer-derived common-seed vectors."""
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import (
        RunCandidateSimulationN5Observation,
        RunGenericCycleSimulationN5Observation,
        RunN5InteractionEvidence,
    )
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.runtime.http.routes.runs import (
        _n5_interaction_evidence_projection,
        _n5_interaction_scope_fields,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from tests.unit.remediation.test_sim_03 import _request_with_atom_count

    request = _request_with_atom_count(3).model_copy(update={"replications": 4, "seed": 41})
    first_pair = frozenset(atom.intervention_id for atom in request.intervention_atoms[:2])
    first_pair_variables = frozenset(
        request.engine_plan[0].variable_map[atom.causal_do_expr.assignments[0].variable]
        for atom in request.intervention_atoms[:2]
    )
    all_variables = frozenset(
        request.engine_plan[0].variable_map[atom.causal_do_expr.assignments[0].variable]
        for atom in request.intervention_atoms
    )

    def paired_interactions(state, params):
        query = state["ncm_query_data"]
        active_variables = frozenset(query.interventions[0])
        seed = params["__seed__"]
        pair_effect = (
            {41: 1.0, 42: -1.0, 43: 1.0, 44: -1.0}[seed]
            if first_pair_variables <= active_variables
            else 0.0
        )
        residual = (
            {41: 1.0, 42: 1.0, 43: -1.0, 44: -1.0}[seed]
            if active_variables == all_variables
            else 0.0
        )
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": pair_effect + residual}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(paired_interactions))
    result = JointSimulationHorizonController().run(request)
    projection = _n5_interaction_evidence_projection(result)
    scope_fields = _n5_interaction_scope_fields(result)

    assert projection is not None
    assert projection["schema_version"] == "policyos.runtime.joint_simulation_horizon.v4"
    assert projection["numeric_interaction"] == "unsupported"
    assert projection["numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"
    assert projection["interaction_sampling_status"] == "estimated"
    typed_projection = RunN5InteractionEvidence.model_validate(projection)
    assert typed_projection.schema_version == projection["schema_version"]
    pair_projection = next(
        term
        for term in projection["interaction_terms"]
        if frozenset(term["atom_ids"]) == first_pair
    )
    pair_summary = pair_projection["replication_sampling_by_step"]["0"]
    assert pair_summary["seeds"] == [41, 42, 43, 44]
    expected_pair_values = [1.0, -1.0, 1.0, -1.0]
    assert [sample["value"] for sample in pair_summary["samples"]] == expected_pair_values
    assert pair_summary["mean"] == pytest.approx(0.0)
    assert pair_summary["standard_error"] == pytest.approx(0.5773502691896257)
    typed_pair_summary = next(
        term
        for term in typed_projection.interaction_terms
        if frozenset(term.atom_ids) == first_pair
    ).replication_sampling_by_step[0]
    assert typed_pair_summary.seeds == (41, 42, 43, 44)
    assert [sample.value for sample in typed_pair_summary.samples] == expected_pair_values
    residual_summary = projection["higher_order_residual_sampling"]["firm_survival"]["0"]
    expected_residual_values = [1.0, 1.0, -1.0, -1.0]
    assert residual_summary["seeds"] == [41, 42, 43, 44]
    assert [sample["value"] for sample in residual_summary["samples"]] == expected_residual_values
    assert residual_summary["mean"] == pytest.approx(0.0)
    assert residual_summary["standard_error"] == pytest.approx(0.5773502691896257)
    assert (
        sum(
            left * right
            for left, right in zip(expected_pair_values, expected_residual_values, strict=True)
        )
        / 3
        == 0.0
    )
    typed_residual = typed_projection.higher_order_residual_sampling["firm_survival"][0]
    assert typed_residual.seeds == (41, 42, 43, 44)
    assert [sample.value for sample in typed_residual.samples] == expected_residual_values
    assert scope_fields == {
        "executed_steps": tuple(result.horizon.steps()),
        "replication_seeds": (41, 42, 43, 44),
    }
    parent_observation = {
        "node_ref": "design-problem://candidate",
        "design_problem_ref": "sha256:" + "a" * 64,
        "atom_ids": tuple(result.atom_ids),
        "selected_outcomes": tuple(result.selected_outcomes),
        "status": "joint_simulated",
        "n5_interaction_evidence": projection,
        **scope_fields,
    }
    RunCandidateSimulationN5Observation.model_validate(parent_observation)

    from copy import deepcopy

    def change_pair_seeds(body: dict[str, object]) -> None:
        evidence = body["n5_interaction_evidence"]
        assert isinstance(evidence, dict)
        terms = evidence["interaction_terms"]
        assert isinstance(terms, list) and terms
        summaries = terms[0]["replication_sampling_by_step"]
        assert isinstance(summaries, dict)
        summary = summaries["0"]
        assert isinstance(summary, dict)
        samples = summary["samples"]
        assert isinstance(samples, list)
        summary["seeds"] = [42, 43, 44, 45]
        summary["samples"] = [
            {"seed": 42, "value": samples[0]["value"]},
            {"seed": 43, "value": samples[1]["value"]},
            {"seed": 44, "value": samples[2]["value"]},
            {"seed": 45, "value": samples[3]["value"]},
        ]

    malformed_cases = [
        (
            "pair_removed",
            lambda body: body["n5_interaction_evidence"]["interaction_terms"].pop(),
        ),
        (
            "foreign_pair_atoms",
            lambda body: body["n5_interaction_evidence"]["interaction_terms"][0].update(
                atom_ids=("atom-a", "foreign-atom")
            ),
        ),
        (
            "foreign_outcome",
            lambda body: body["n5_interaction_evidence"]["interaction_terms"][0].update(
                outcome="foreign-outcome"
            ),
        ),
        (
            "foreign_step",
            lambda body: body["n5_interaction_evidence"]["interaction_terms"][0].update(
                by_step={999: 0.0},
                replication_sampling_by_step={
                    "999": body["n5_interaction_evidence"]["interaction_terms"][0][
                        "replication_sampling_by_step"
                    ]["0"]
                },
            ),
        ),
        ("foreign_seeds", change_pair_seeds),
        (
            "residual_removed",
            lambda body: body["n5_interaction_evidence"].update(
                higher_order_residuals={}, higher_order_residual_sampling={}
            ),
        ),
        (
            "wrong_checked_orders",
            lambda body: body["n5_interaction_evidence"].update(checked_interaction_orders=(1, 2)),
        ),
        ("wrong_parent_outcome", lambda body: body.update(selected_outcomes=("other",))),
        ("wrong_parent_step", lambda body: body.update(executed_steps=(999,))),
        ("wrong_parent_seeds", lambda body: body.update(replication_seeds=(41, 42, 43, 45))),
    ]
    for _case, corrupt in malformed_cases:
        corrupted = deepcopy(parent_observation)
        corrupt(corrupted)
        with pytest.raises(ValidationError, match="run_n5_interaction_scope_"):
            RunCandidateSimulationN5Observation.model_validate(corrupted)

    missing_axis_context = deepcopy(parent_observation)
    missing_axis_context["executed_steps"] = ()
    with pytest.raises(
        ValidationError,
        match="run_n5_interaction_scope_parent_context_missing_or_invalid",
    ):
        RunCandidateSimulationN5Observation.model_validate(missing_axis_context)

    def artifact_ref(kind: str, suffix: str) -> dict[str, str]:
        return {
            "artifact_id": "sha256:" + suffix * 64,
            "kind": kind,
            "media_type": "application/json",
        }

    simulation_ref = artifact_ref("polisyos.runtime.joint_simulation_result", "5")
    generic_observation = {
        **parent_observation,
        "cycle_index": 0,
        "candidate_id": "candidate",
        "simulation_result_ref": simulation_ref,
        "simulation_result_body_status": "not_established",
        "simulation_result_body_limitation_code": (
            "generic_n5_result_body_selected_manifest_view_not_established"
        ),
        "n4_source_ref": artifact_ref("runtime.generation_source_handoff", "1"),
        "context_job_ref": artifact_ref("runtime.quality.cycle_substrate_context_job", "2"),
        "profile_ref": artifact_ref("runtime.quality.generic_cycle_simulation_profile", "3"),
        "n5_input_ref": artifact_ref("runtime.quality.generic_cycle_simulation_n5_input", "4"),
        "n5_execution_ref": artifact_ref(
            "runtime.quality.generic_cycle_simulation_n5_execution", "6"
        ),
        "n5_request_binding_status": "resolved",
        "n5_request_content_hash": "sha256:" + "7" * 64,
        "profile_selection_ref": "sha256:" + "8" * 64,
        "world_model_record_content_hash": result.world_model_record_content_hash,
        "authority_blockers": (),
        "n8_status": "value_conditional",
        "n8_lineage_status": "resolved",
        "n8_value_ref": simulation_ref["artifact_id"],
        "n8_authority_blockers": ("interaction_numeric_classification_unsupported",),
        "n8_limitation_code": None,
        "n8_numeric_interaction": projection["numeric_interaction"],
        "n8_numeric_interaction_basis": projection["numeric_interaction_basis"],
        "n8_interaction_sampling_status": projection["interaction_sampling_status"],
    }
    RunGenericCycleSimulationN5Observation.model_validate(generic_observation)
    corrupted_generic = deepcopy(generic_observation)
    corrupted_generic["n5_interaction_evidence"]["interaction_terms"].pop()
    with pytest.raises(ValidationError, match="run_n5_interaction_scope_pair_set_incomplete"):
        RunGenericCycleSimulationN5Observation.model_validate(corrupted_generic)

    legacy_observation = deepcopy(parent_observation)
    legacy_evidence = legacy_observation["n5_interaction_evidence"]
    legacy_evidence["schema_version"] = "policyos.runtime.joint_simulation_horizon.v3"
    legacy_evidence["numeric_interaction"] = "unsupported"
    legacy_evidence["numeric_interaction_basis"] = "not_established"
    legacy_evidence["interaction_sampling_status"] = "not_established"
    legacy_evidence["interaction_terms"] = ()
    legacy_evidence["higher_order_residual_sampling"] = {}
    legacy_observation["executed_steps"] = ()
    legacy_observation["replication_seeds"] = ()
    RunCandidateSimulationN5Observation.model_validate(legacy_observation)


def test_four_atom_n5_scope_composes_complete_pairs_under_permutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consumer derives every four-atom pair from the selected atom set."""
    from copy import deepcopy

    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import RunCandidateSimulationN5Observation
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.runtime.http.routes.runs import (
        _n5_interaction_evidence_projection,
        _n5_interaction_scope_fields,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from tests.unit.remediation.test_sim_03 import _request_with_atom_count

    def fixed_outcome(state, params):
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 0.0}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    base_request = _request_with_atom_count(4).model_copy(update={"replications": 2, "seed": 41})
    controller = JointSimulationHorizonController()
    for request in (
        base_request,
        base_request.model_copy(
            update={"intervention_atoms": tuple(reversed(base_request.intervention_atoms))}
        ),
    ):
        result = controller.run(request)
        evidence = _n5_interaction_evidence_projection(result)
        assert evidence is not None
        assert evidence["checked_interaction_orders"] == [1, 2]
        assert evidence["numeric_interaction"] == "unsupported"
        assert "aggregate_order_3_plus_not_identified" in (
            result.feedback_classification.limitations
        )
        assert set(evidence["higher_order_residuals"]) == set(result.selected_outcomes)
        observed_pairs = {frozenset(term["atom_ids"]) for term in evidence["interaction_terms"]}
        expected_pairs = {
            frozenset((left.intervention_id, right.intervention_id))
            for index, left in enumerate(request.intervention_atoms)
            for right in request.intervention_atoms[index + 1 :]
        }
        assert observed_pairs == expected_pairs
        assert len(evidence["interaction_terms"]) == len(expected_pairs) == 6
        assert result.diagnostics["replication_seeds"] == [41, 42]
        for term in evidence["interaction_terms"]:
            summary = term["replication_sampling_by_step"]["0"]
            assert summary["status"] == "estimated"
            assert summary["seeds"] == [41, 42]
            assert summary["samples"] == [
                {"seed": 41, "value": 0.0},
                {"seed": 42, "value": 0.0},
            ]
            assert summary["mean"] == 0.0
            assert summary["standard_error"] == 0.0
        residual = evidence["higher_order_residual_sampling"]["firm_survival"]["0"]
        assert residual["status"] == "estimated"
        assert residual["seeds"] == [41, 42]
        assert residual["samples"] == [
            {"seed": 41, "value": 0.0},
            {"seed": 42, "value": 0.0},
        ]
        assert residual["mean"] == 0.0
        assert residual["standard_error"] == 0.0
        observation = {
            "node_ref": "design-problem://four-atom",
            "design_problem_ref": "sha256:" + "a" * 64,
            "atom_ids": tuple(result.atom_ids),
            "selected_outcomes": tuple(result.selected_outcomes),
            "status": "joint_simulated",
            "n5_interaction_evidence": evidence,
            **_n5_interaction_scope_fields(result),
        }
        wire_observation = json.loads(json.dumps(observation))
        RunCandidateSimulationN5Observation.model_validate(wire_observation)

        removed_pair = deepcopy(observation)
        removed_pair["n5_interaction_evidence"]["interaction_terms"].pop()
        with pytest.raises(ValidationError, match="run_n5_interaction_scope_pair_set_incomplete"):
            RunCandidateSimulationN5Observation.model_validate(removed_pair)

        removed_residual_summary = deepcopy(observation)
        removed_residual_summary["n5_interaction_evidence"]["higher_order_residual_sampling"].pop(
            "firm_survival"
        )
        with pytest.raises(
            ValidationError,
            match="run_n5_residual_summary_step_missing",
        ):
            RunCandidateSimulationN5Observation.model_validate(removed_residual_summary)

        removed_residual_basis = deepcopy(observation)
        removed_residual_basis["n5_interaction_evidence"]["higher_order_residuals"].pop(
            "firm_survival"
        )
        removed_residual_basis["n5_interaction_evidence"]["higher_order_residual_sampling"].pop(
            "firm_survival"
        )
        with pytest.raises(
            ValidationError,
            match="run_n5_interaction_scope_residual_basis_incomplete",
        ):
            RunCandidateSimulationN5Observation.model_validate(removed_residual_basis)


def test_run_n5_observation_rejects_removed_pair_with_status_markers() -> None:
    """A complete selected three-atom basis cannot be represented by empty pair terms."""
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import RunCandidateSimulationN5Observation

    observation = {
        "node_ref": "design-problem://candidate",
        "design_problem_ref": "sha256:" + "a" * 64,
        "atom_ids": ("atom-a", "atom-b", "atom-c"),
        "selected_outcomes": ("outcome-a",),
        "executed_steps": (0,),
        "replication_seeds": (41, 42),
        "status": "joint_simulated",
        "n5_interaction_evidence": {
            "schema_version": "policyos.runtime.joint_simulation_horizon.v4",
            "numeric_interaction": "unsupported",
            "numeric_interaction_basis": "finite_checked_model_point_estimate_only",
            "interaction_sampling_status": "estimated",
            "interaction_terms": (),
            "higher_order_residuals": {"outcome-a": {0: 0}},
            "higher_order_residual_sampling": {
                "outcome-a": {
                    0: {
                        "status": "estimated",
                        "replicate_count": 2,
                        "seeds": (41, 42),
                        "samples": (
                            {"seed": 41, "value": 1},
                            {"seed": 42, "value": -1},
                        ),
                        "mean": 0,
                        "standard_error": 1,
                    }
                }
            },
            "checked_interaction_orders": (1, 2, 3),
        },
    }

    with pytest.raises(
        ValidationError,
        match="run_n5_interaction_scope_pair_set_incomplete",
    ):
        RunCandidateSimulationN5Observation.model_validate(observation)


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
@pytest.mark.asyncio
async def test_fresh_run_details_get_projects_the_persisted_candidate_simulation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A fresh authorized GET projects source-bound interaction scope from CAS."""
    from polisyos.runtime.http import dev_identity_middleware

    fixture = await _run_controlled_simulate_only_job_fixture(monkeypatch, tmp_path)
    core_run_id = str(fixture.job.progress["core_run_id"])
    monkeypatch.setattr(
        dev_identity_middleware,
        "build_fixture_identity_claims",
        _fixture_claims,
    )
    from polisyos.core.security.tenant_context import tenant_scope

    # Container-owned immutable artifacts share the fixture CAS; initialize the
    # fresh reader under the same declared tenant/cell owner as those writes.
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        app = create_runtime_api_app(
            cas_root=tmp_path / ".polisyos",
            core_runs_root=tmp_path / ".polisyos" / "runs",
            allow_fixture_identity=True,
        )
    _install_fixture_tenant_lifespan(app)
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/runs/{core_run_id}")
            assert response.status_code == 200, response.text
            run = response.json()["run"]
            compiled_refs = [
                ref
                for ref in run["root_artifacts"]
                if ref["kind"] == "runtime.compiled_recursive_generation_cycle"
            ]
            assert len(compiled_refs) == 1
            projection = run.get("candidate_simulation")
            assert projection is not None, (
                "fresh RunDetails GET dropped its persisted candidate result"
            )
            assert projection["artifact_status"] == "resolved"
            assert projection["run_id"] == core_run_id
            assert projection["n5_observations"]
            n5_observation = projection["n5_observations"][0]
            assert n5_observation["n5_interaction_evidence"]["schema_version"].endswith(".v4")

            # The actual selected historical L2 input is withheld. The public
            # reader must retain that source limitation and expose no derived
            # child profile bindings. The root candidate-scenario N5 below is a
            # separate candidate-only path and is not a recursive child result.
            compiled_json = json.loads(fixture.compiled_payload)
            from polisyos.core.artifacts.manifest import ArtifactRef
            from polisyos.core.artifacts.store import ArtifactOwnershipError
            from polisyos.runtime.quality.generation_source import GenerationSourceRepository

            recursive_source_ref = ArtifactRef.model_validate(
                compiled_json["n4_recursive_source_ref"]
            )
            recursive_source_scope = {
                "run_id": str(fixture.job.run_id),
                "expected_job_id": fixture.job.job_id,
                "expected_tenant_id": "tenant-fixture",
                "expected_cell_id": "cell-fixture",
            }
            recursive_repository = GenerationSourceRepository(fixture.service._artifact_store)
            recursive_source = recursive_repository.load(
                recursive_source_ref, **recursive_source_scope
            )
            assert recursive_source.generation_result.status == "generation_unavailable"
            foreign_scope_store = fixture.service._artifact_store.for_tenant(
                "tenant-foreign", "cell-foreign"
            )
            with pytest.raises(ArtifactOwnershipError):
                GenerationSourceRepository(foreign_scope_store).load(
                    recursive_source_ref, **recursive_source_scope
                )
            assert compiled_json["n4_recursive_source_result_status"] == "generation_unavailable"
            assert compiled_json["n4_child_profile_status"] == "not_established"
            assert compiled_json["n4_child_profile_limitation_code"] == (
                "n4_recursive_source_generation_not_complete"
            )
            assert compiled_json.get("n4_child_profile_bindings", []) == []
            assert projection["n4_recursive_source_ref"] == recursive_source_ref.model_dump(
                mode="json"
            )
            assert projection["n4_recursive_source_status"] == "resolved"
            assert projection["n4_recursive_source_result_status"] == "generation_unavailable"
            assert projection["n4_child_profile_status"] == "not_established"
            assert projection["n4_child_profile_limitation_code"] == (
                "n4_recursive_source_generation_not_complete"
            )
            assert projection.get("n4_child_profile_bindings", []) == []

            n5_input = fixture.n5_port_observations[0].input_record
            n4_source = GenerationSourceRepository(
                fixture.service._artifact_store
            ).load_candidate_scenario_source_for_n5(
                n5_input.n4_source_ref,
                expected_run_id=str(fixture.job.run_id),
                expected_job_id=fixture.job.job_id,
                expected_tenant_id="tenant-fixture",
                expected_cell_id="cell-fixture",
            )
            source_v1 = n4_source.source_record.source_record
            assert source_v1.authority_purpose == "candidate_scenario_n5_only"
            assert source_v1.k_ref_limitation_code in {
                "historical_l2_confidence_withheld",
                "full_credal_reference_not_established",
            }
            assert (source_v1.l2_confidence_vintage is not None) is (
                source_v1.k_ref_limitation_code == "historical_l2_confidence_withheld"
            )
            if source_v1.l2_confidence_vintage is not None:
                assert source_v1.l2_confidence_vintage.snapshot_sha256 == (
                    "583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967"
                )
            assert source_v1.l2_confidence_forwarded is False
            assert source_v1.credal_reference_payload is None
            assert projection["source_ref"] == compiled_refs[0]
            assert (
                projection["source_content_hash"]
                == json.loads(fixture.compiled_payload)["content_hash"]
            )
            assert projection["acquisition_history"] == []
            assert projection["acquisition_history_limitation_code"] == (
                "acquisition_action_history_integrity_not_established"
            )
            assert projection["n5_observations"], projection
            n5_observation = projection["n5_observations"][0]
            assert n5_observation["status"] == "joint_simulated"
            assert n5_observation["simulation_result_ref"]["kind"] == (
                "polisyos.runtime.joint_simulation_result"
            )
            assert (
                n5_observation["world_model_record_content_hash"]
                == n5_observation["k_world_ref_before"]
            )

            store = fixture.service._artifact_store
            from polisyos.core.artifacts.ids import ArtifactID
            from polisyos.core.artifacts.manifest import ArtifactRef
            from polisyos.runtime.quality.generation_cycle import (
                load_joint_simulation_result,
            )

            compiled_manifest = store.get_manifest(ArtifactRef.model_validate(compiled_refs[0]))
            assert compiled_manifest.tenant_context is not None
            assert compiled_manifest.tenant_context.tenant_id == "tenant-fixture"
            assert compiled_manifest.tenant_context.cell_id == "cell-fixture"
            fixture_n5_observation = fixture.n5_port_observations[0].observation
            assert fixture_n5_observation.simulation_result_ref is not None
            n5_ref = fixture_n5_observation.simulation_result_ref
            n5_manifest = store.get_manifest(n5_ref)
            assert n5_manifest.tenant_context is not None
            assert n5_manifest.tenant_context.tenant_id == "tenant-fixture"
            assert n5_manifest.tenant_context.cell_id == "cell-fixture"
            stored_n5_result = load_joint_simulation_result(
                n5_ref,
                store=store,
                expected_world_model_record_content_hash=(
                    n5_observation["world_model_record_content_hash"]
                ),
                expected_atom_ids=n5_observation["atom_ids"],
                expected_selected_outcomes=n5_observation["selected_outcomes"],
            )
            assert n5_observation["executed_steps"] == list(stored_n5_result.horizon.steps())
            assert n5_observation["replication_seeds"] == list(
                stored_n5_result.diagnostics["replication_seeds"]
            )

            from polisyos.runtime.http.routes import runs as runs_routes

            original_evidence_projection = runs_routes._n5_interaction_evidence_projection

            def omit_checked_orders(result: object) -> dict[str, object] | None:
                evidence = original_evidence_projection(result)
                if evidence is not None:
                    evidence["checked_interaction_orders"] = []
                return evidence

            monkeypatch.setattr(
                runs_routes,
                "_n5_interaction_evidence_projection",
                omit_checked_orders,
            )
            malformed_response = client.get(f"/api/v1/runs/{core_run_id}")
            assert malformed_response.status_code == 200, malformed_response.text
            malformed_projection = malformed_response.json()["run"]["candidate_simulation"]
            assert malformed_projection["n5_observations"] == []
            assert malformed_projection["limitation_code"] == (
                "n5_interaction_scope_not_established"
            )
            monkeypatch.setattr(
                runs_routes,
                "_n5_interaction_evidence_projection",
                original_evidence_projection,
            )

            n5_blob_path, _n5_manifest_path = store._paths(
                ArtifactID.model_validate(n5_ref.artifact_id)
            )
            n5_blob_path.write_bytes(b"corrupt")
            corrupt_response = client.get(f"/api/v1/runs/{core_run_id}")
        assert corrupt_response.status_code == 200, corrupt_response.text
        corrupt_projection = corrupt_response.json()["run"]["candidate_simulation"]
        assert corrupt_projection["artifact_status"] == "resolved"
        assert corrupt_projection["limitation_code"] == ("n5_result_reference_not_established")
        assert corrupt_projection["n5_observations"] == []
    finally:
        fixture.service.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
@pytest.mark.asyncio
async def test_fresh_run_details_get_keeps_local_n5_and_sibling_failure_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Serve the local N5/checkpoint mechanism witness through a fresh GET.

    This is bounded checkpoint-mechanism evidence, not an N4-derived-child
    source-positive or V6 completion.
    """
    from polisyos.runtime.http import dev_identity_middleware
    from polisyos.runtime.quality.generation_cycle import GENERATION_CYCLE_SCHEMA_VERSION
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RECURSIVE_GENERATION_CYCLE_PARTIAL_V3_SCHEMA_VERSION,
    )
    from tests.unit.runtime.quality.test_generation_cycle import REPO_ROOT

    fixture = await _run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
        local_sibling_mechanism_witness=True,
        source_repo_root=REPO_ROOT,
    )
    assert fixture.service._repo_root == REPO_ROOT.resolve()
    core_run_id = str(fixture.job.progress["core_run_id"])
    compiled_payload = canon.from_canonical_bytes(fixture.compiled_payload)
    recursive_payload = compiled_payload["recursive_run"]
    successful_node = next(
        node
        for node in recursive_payload["nodes"]
        if node["node_ref"].endswith("#local-mechanism-successful-sibling")
    )
    failed_node = next(
        node
        for node in recursive_payload["nodes"]
        if node["node_ref"].endswith("#local-mechanism-failed-sibling")
    )
    assert failed_node["failure"]["error_code"] == "controlled_second_sibling_failure"
    assert failed_node["failure"]["stage"] == "leaf_generation"
    assert (
        recursive_payload["schema_version"] == RECURSIVE_GENERATION_CYCLE_PARTIAL_V3_SCHEMA_VERSION
    )
    assert recursive_payload["terminal"] is None
    successful_cycle = successful_node["cycle_run"]
    assert successful_cycle["schema_version"] == GENERATION_CYCLE_SCHEMA_VERSION
    successful_simulation = successful_cycle["cycles"][0]["simulation"]
    assert successful_simulation["candidate_simulation_n4_source_ref"]["kind"] == (
        "runtime.quality.n4_candidate_scenario_source"
    )
    assert successful_simulation["candidate_simulation_context_job_ref"]["kind"] == (
        "runtime.quality.cycle_substrate_context_job"
    )
    assert successful_simulation["candidate_simulation_n5_input_ref"]["kind"] == (
        "runtime.quality.candidate_simulation_n5_input"
    )
    assert successful_simulation["candidate_simulation_profile_config_ref"].startswith(
        "runtime-config:candidate-simulation/"
    )
    assert successful_simulation["candidate_simulation_profile_selection_ref"].startswith("sha256:")
    from polisyos.runtime.quality.generation_cycle import (
        validate_generation_cycle_run_history,
    )

    missing_lineage = canon.from_canonical_bytes(
        canon.to_canonical_bytes(successful_cycle, canon.CanonSpec(forbid_floats=False))
    )
    del missing_lineage["cycles"][0]["simulation"]["candidate_simulation_context_job_ref"]
    missing_lineage_issues = validate_generation_cycle_run_history(missing_lineage)
    assert [issue["code"] for issue in missing_lineage_issues] == [
        "generation_cycle_historical_projection_invalid"
    ]
    assert "candidate_simulation_cycle_binding_incomplete" in missing_lineage_issues[0]["error"]

    monkeypatch.setattr(
        dev_identity_middleware,
        "build_fixture_identity_claims",
        _fixture_claims,
    )
    from polisyos.core.security.tenant_context import tenant_scope

    # Container-owned immutable artifacts share the fixture CAS; initialize the
    # fresh reader under the same declared tenant/cell owner as those writes.
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        app = create_runtime_api_app(
            cas_root=tmp_path / ".polisyos",
            core_runs_root=tmp_path / ".polisyos" / "runs",
            candidate_simulation_profiles=(fixture.profile,),
            candidate_simulation_model_declarations=(fixture.model_declaration,),
            repo_root=REPO_ROOT,
            allow_fixture_identity=True,
        )
    runtime_container = app.state.runtime_container
    assert runtime_container.config.repo_root == REPO_ROOT.resolve()
    assert runtime_container.config.candidate_simulation_profiles == (fixture.profile,)
    assert runtime_container.config.candidate_simulation_model_declarations == (
        fixture.model_declaration,
    )
    assert runtime_container.config.cas_root.resolve() == fixture.service._artifact_store.root
    profile_owner = runtime_container.candidate_simulation_context_admission_owner
    assert profile_owner is not None
    assert profile_owner._store is runtime_container.runtime_api_context.store
    assert (
        profile_owner.configured_profile_for_selection_ref(fixture.profile.profile_selection_ref)
        == fixture.profile
    )
    _install_fixture_tenant_lifespan(app)
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/runs/{core_run_id}")
            assert response.status_code == 200, response.text
            run = response.json()["run"]
            assert fixture.job.state == "completed"
            summaries_response = client.get("/api/v1/runs?limit=50")
            assert summaries_response.status_code == 200, summaries_response.text
            run_summary = next(
                summary
                for summary in summaries_response.json()["runs"]
                if summary["run_id"] == core_run_id
            )
            assert run_summary["run_terminality"] == "terminal"
            projection = run.get("candidate_simulation")
            assert projection is not None, "fresh GET dropped the persisted V3 checkpoint"
            assert projection["artifact_status"] == "resolved"
            assert projection["source_content_hash"] == compiled_payload["content_hash"]
            assert projection["limitation_code"] is None
            assert len(projection["n5_observations"]) == 1
            observation = projection["n5_observations"][0]
            source_n5_ref = successful_node["cycle_run"]["cycles"][0]["simulation"][
                "simulation_result_ref"
            ]
            assert observation["node_ref"] == successful_node["node_ref"]
            assert observation["status"] == "joint_simulated"
            assert observation["simulation_result_ref"] == source_n5_ref

            checkpoint = projection["recursive_cycle_checkpoint"]
            assert checkpoint["schema_version"] == "policyos.runtime.recursive_cycle_checkpoint.v2"
            assert checkpoint["completed_design_refs"] == [successful_node["node_ref"]]
            assert len(checkpoint["failed_branches"]) == 1
            failure = checkpoint["failed_branches"][0]
            assert failure == {
                "failed_branch_ref": failed_node["node_ref"],
                "origin_node_ref": failed_node["failure"]["origin_node_ref"],
                "stage": "leaf_generation",
                "exception_type": "GenerationCycleError",
                "error_code": "controlled_second_sibling_failure",
                "error_message": (
                    "controlled_second_sibling_failure: "
                    "later child failed after its earlier sibling completed"
                ),
            }

            from copy import deepcopy
            from dataclasses import replace

            from pydantic import ValidationError

            from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo
            from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
            from polisyos.runtime.http.services.control.generation_cycle import (
                CompiledRecursiveGenerationCycleRun,
            )

            grafted_compiled = deepcopy(compiled_payload)
            grafted_recursive = grafted_compiled["recursive_run"]
            blocked_nodes = [
                node
                for node in grafted_recursive["nodes"]
                if node.get("cycle_run") is not None
                and node["cycle_run"].get("terminal_status") == "blocked"
            ]
            assert len(blocked_nodes) == 1
            blocked_cycle = blocked_nodes[0]["cycle_run"]
            assert blocked_cycle["schema_version"] == GENERATION_CYCLE_SCHEMA_VERSION
            assert blocked_cycle["promotion_port"]["receipts"] == []
            blocked_cycle["promotion_port"]["receipts"] = [{"receipt": "adversarially-grafted"}]

            recursive_identity = gy_artifact_self_identity_projection(grafted_recursive)
            for derived_field in ("leaf_nodes", "pending_node_refs", "failed_node"):
                recursive_identity.pop(derived_field, None)
            grafted_recursive["content_hash"] = gy_content_hash(recursive_identity)
            compiled_identity = gy_artifact_self_identity_projection(grafted_compiled)
            compiled_recursive_identity = dict(compiled_identity["recursive_run"])
            compiled_recursive_identity.pop("leaf_nodes", None)
            compiled_identity["recursive_run"] = compiled_recursive_identity
            grafted_compiled["content_hash"] = gy_content_hash(compiled_identity)
            with pytest.raises(
                ValidationError,
                match="blocked_generation_cycle_n9_admission_mismatch",
            ):
                CompiledRecursiveGenerationCycleRun.model_validate(grafted_compiled)

            original_compiled_ref = ArtifactRef.model_validate(
                next(
                    ref
                    for ref in run["root_artifacts"]
                    if ref["kind"] == "runtime.compiled_recursive_generation_cycle"
                )
            )
            with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
                grafted_compiled_ref = fixture.service._put_json_artifact_ref(
                    grafted_compiled,
                    kind="runtime.compiled_recursive_generation_cycle",
                    schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                    tenant_context=ArtifactTenantContextInfo(
                        tenant_id="tenant-fixture",
                        cell_id="cell-fixture",
                    ),
                )

            run_index = app.state.runtime_api_ctx.run_index
            original_get_run = run_index.get_run

            def get_run_with_grafted_compiled(run_id_arg: str):
                indexed = original_get_run(run_id_arg)
                if run_id_arg != core_run_id or indexed is None:
                    return indexed
                root_artifacts = [
                    grafted_compiled_ref
                    if ref.artifact_id == original_compiled_ref.artifact_id
                    else ref
                    for ref in indexed.details.root_artifacts
                ]
                assert (
                    sum(
                        ref.artifact_id == grafted_compiled_ref.artifact_id
                        for ref in root_artifacts
                    )
                    == 1
                )
                return replace(
                    indexed,
                    details=indexed.details.model_copy(update={"root_artifacts": root_artifacts}),
                )

            with monkeypatch.context() as graft_index:
                graft_index.setattr(run_index, "get_run", get_run_with_grafted_compiled)
                graft_response = client.get(f"/api/v1/runs/{core_run_id}")
            assert graft_response.status_code == 200, graft_response.text
            graft_projection = graft_response.json()["run"]["candidate_simulation"]
            assert graft_projection["artifact_status"] == "not_established"
            assert graft_projection["limitation_code"] == "compiled_cycle_artifact_content_invalid"
            assert graft_projection["source_ref"]["artifact_id"] == str(
                grafted_compiled_ref.artifact_id
            )
            assert graft_projection["n5_observations"] == []

            from polisyos.core.artifacts.ids import ArtifactID
            from polisyos.core.artifacts.manifest import ArtifactRef

            n5_ref = ArtifactRef.model_validate(source_n5_ref)
            n5_blob_path, _n5_manifest_path = fixture.service._artifact_store._paths(
                ArtifactID.model_validate(n5_ref.artifact_id)
            )
            n5_blob_path.write_bytes(b"corrupt")
            corrupt_response = client.get(f"/api/v1/runs/{core_run_id}")
        assert corrupt_response.status_code == 200, corrupt_response.text
        corrupt_projection = corrupt_response.json()["run"]["candidate_simulation"]
        assert corrupt_projection["artifact_status"] == "resolved"
        assert corrupt_projection["limitation_code"] == ("n5_result_reference_not_established")
        assert corrupt_projection["n5_observations"] == []
        assert corrupt_projection["recursive_cycle_checkpoint"]["failed_branches"] == [failure]
    finally:
        fixture.service.close()


@pytest.mark.asyncio
async def test_served_owner_context_keeps_missing_n4_source_candidate_limited(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A started N4 attempt with no persisted source stays a limited candidate."""
    fixture = await _run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
        proposal_source_persistence_failure=True,
    )
    fixture.service.close()


@pytest.mark.asyncio
async def test_served_nl_job_projects_n4_gateway_unavailable_without_artifact_or_downstream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A real served candidate request records N4 unavailability as a typed limitation."""

    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _design_problem_tool_args,
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
        _intent_context,
    )
    from tests.unit.runtime.quality.test_design_generation import _recordings

    recording = _recordings()[0]
    model_id = str(recording["model_id"])
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap."
    )
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=_design_problem_tool_args(),
    )
    original_compiler = nl_pipeline.build_design_problem_from_nl_request
    owner_source_contexts: list[object] = []
    compiler_contexts: list[object] = []

    async def run_real_compiler(**kwargs):
        owner_source_contexts.append(kwargs.get("trusted_source_context"))
        compiler_contexts.append(kwargs.get("context"))
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    generation_factory_calls: list[str] = []

    def unavailable_generation_gateway(**kwargs):
        generation_factory_calls.append(str(kwargs.get("model_name")))
        return None

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        unavailable_generation_gateway,
    )

    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request=raw_request,
            llm_model=model_id,
            context=_intent_context(as_of="2026-05-12"),
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        def reject_downstream(**_kwargs):
            pytest.fail("unavailable proposal reached an N6/N8/N9/S8 consumer")

        monkeypatch.setattr(service, "resolve_generation_value_choices", reject_downstream)
        monkeypatch.setattr(service, "_publish_generation_run", reject_downstream)
        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            reject_downstream,
        )

        def reject_unavailable_proposal_persistence(*_args, **_kwargs):
            pytest.fail("unavailable N4 terminal reached proposal persistence")

        monkeypatch.setattr(
            GenerationSourceRepository,
            "persist_candidate_proposal",
            reject_unavailable_proposal_persistence,
        )
        dispatch_one_control_job(
            store=service._control_store,  # noqa: SLF001
            handler=service._process_control_job,  # noqa: SLF001
            expected_job_id=launch.job_id,
        )

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None
        assert completed.state == "completed"
        progress = completed.progress
        assert progress["status"] == "not_established"
        assert progress["execution_band"] == "candidate"
        assert progress["candidate_computation_status"] == "not_established"
        assert progress["proposal_persistence_status"] == "not_run"
        assert progress["limitation_code"] == "n4_generation_unavailable"
        assert progress["n4_status"] == "generation_unavailable"
        assert progress["candidate_proposal_ref"] is None
        assert progress["n5_status"] == "not_run"
        assert progress["n8_status"] == "not_run"
        assert progress["n9_status"] == "not_run"
        assert progress["s8_status"] == "not_run"
        assert progress["runtime_diagnostic_event_status"] == "persisted"
        assert generation_factory_calls == [model_id]
        assert compiler_gateway.generate_calls
        assert owner_source_contexts == [
            {
                "tenant_id": "tenant-fixture",
                "cell_id": "cell-fixture",
                "job_id": launch.job_id,
                "run_id": launch.run_id,
            }
        ]
        compiled_context = compiler_contexts[0]
        assert isinstance(compiled_context, dict)
        assert compiled_context["tenant_id"] == "tenant-fixture"
        assert compiled_context["cell_id"] == "cell-fixture"
        candidate_context = compiled_context["candidate_context"]
        assert isinstance(candidate_context, dict)
        assert "tenant_id" not in candidate_context
        assert "cell_id" not in candidate_context

        manifest_text = "\n".join(
            manifest.read_text(encoding="utf-8")
            for manifest in service._artifact_store.base.rglob("*.manifest.json")
        )
        assert "runtime.quality.n4_candidate_proposal" not in manifest_text
        assert "runtime.quality.compiled_recursive_generation_cycle" not in manifest_text
    finally:
        service.close()


def test_diagnostic_events_bind_authenticated_scope_and_declare_unknown_attribution(
    tmp_path,
) -> None:
    from polisyos.core.security.access_scope import AccessScope

    service = _build_control_service(tmp_path)

    class RecordingEventLog:
        def __init__(self) -> None:
            self.events = []

        def append(self, event, **_kwargs):
            self.events.append(event)
            return SimpleNamespace(event=event)

    log = RecordingEventLog()
    service._diagnostic_event_log = log
    unknown_scope = AccessScope.for_service(
        tenant_id="tenant-unknown",
        cell_id=None,
        spiffe_id="spiffe://runtime/unknown-scope-test",
    )
    try:
        omitted = service._emit_runtime_diagnostic_event(
            execution_scope=unknown_scope,
            job_id="job-no-scope",
            run_id="run-no-scope",
            execution_profile="dev",
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            payload={},
        )
        assert omitted is not None and omitted.scope_status == "not_established"
        assert len(log.events) == 1
        assert log.events[-1].tenant_id == "tenant-unknown"
        assert log.events[-1].cell_id == "cell-unknown"

        placeholder_scope_omitted = service._emit_runtime_diagnostic_event(
            execution_scope=unknown_scope,
            job_id="job-placeholder-scope",
            run_id="run-placeholder-scope",
            execution_profile="dev",
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            payload={"tenant_id": "tenant-real", "cell_id": "cell-real"},
        )
        assert placeholder_scope_omitted is not None
        assert placeholder_scope_omitted.scope_status == "not_established"
        assert len(log.events) == 2
        assert log.events[-1].tenant_id == "tenant-unknown"
        assert log.events[-1].cell_id == "cell-unknown"

        emitted = service._emit_runtime_diagnostic_event(
            execution_scope=AccessScope.for_service(
                tenant_id="tenant-real",
                cell_id="cell-real",
                spiffe_id="spiffe://runtime/diagnostic-owner",
            ),
            job_id="job-scoped",
            run_id="run-scoped",
            execution_profile="dev",
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            payload={"tenant_id": "payload-foreign", "cell_id": "payload-foreign"},
        )
        assert emitted is not None
        assert emitted.scope_status == "established"
        assert len(log.events) == 3
        assert log.events[-1].tenant_id == "tenant-real"
        assert log.events[-1].cell_id == "cell-real"
    finally:
        service.close()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"tenant_id": "  ", "cell_id": "cell-real"}, id="blank"),
        pytest.param(
            {"tenant_id": "tenant-unknown", "cell_id": "cell-real"},
            id="placeholder-marker",
        ),
        pytest.param({"tenant_id": 42, "cell_id": "cell-real"}, id="wrong-type"),
    ],
)
def test_eval_safety_closure_refuses_absent_tenant_instead_of_fabricating_one(
    tmp_path,
    payload: dict[str, object],
) -> None:
    from polisyos.runtime.http.services.control.workspace_loop_transition import (
        _WorkflowExecutionNonAuthorityError,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionScope,
    )

    service = _build_control_service(tmp_path)
    intake = SimpleNamespace(
        attempt_id="attempt-unknown-tenant",
        evaluation_input_refs=(),
        mode_resolution=SimpleNamespace(model_dump=lambda **_kwargs: {"mode": "field_pilot"}),
        requested_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    job = SimpleNamespace(
        job_id="job-unknown-tenant",
        run_id="run-unknown-tenant",
        requested_execution_profile="dev",
        effective_execution_profile="dev",
    )
    execution_scope = ControlJobExecutionScope(
        status="not_established",
        tenant_id=None,
        cell_id=None,
        actor_subject=None,
        actor_authenticated=False,
        actor_roles=(),
    )
    try:
        with pytest.raises(
            _WorkflowExecutionNonAuthorityError,
            match="evaluation_safety_tenant_scope_not_established",
        ) as raised:
            service._evaluation_safety_persistence_context(
                intake=intake,
                job=job,
                payload=payload,
                execution_scope=execution_scope,
            )
        assert raised.value.progress["status"] == "not_established"
        assert raised.value.progress["eval_safety_blocker_codes"] == [
            "evaluation_safety_tenant_scope_not_established"
        ]
    finally:
        service.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
@pytest.mark.asyncio
async def test_predictive_calibration_post_event_reopen_get_and_exact_intent_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    request: pytest.FixtureRequest,
) -> None:
    """The actual run form inputs persist through ForecastOwner, CAS, event, and reopened GET."""
    import hashlib
    from dataclasses import replace
    from typing import cast

    from polisyos.calibration.forecast_bridge import (
        REFERENCE_SOURCE_INPUT_ROLES,
        EmpiricalCalibrationEvidenceRef,
        load_empirical_calibration_evidence,
    )
    from polisyos.core.artifacts import (
        FileSystemCAS,
        PutOptions,
        artifact_manifest_profile_sha256,
    )
    from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
    from polisyos.core.contracts import DataSnapshot, DataSnapshotRef
    from polisyos.core.contracts.runtime import RunCandidateSimulationProjection
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api.catalog import default_acquisition_overlay_path
    from polisyos.ir import CanonSpec, InputRef, put_json_artifact
    from polisyos.ir.analytics.backtest import BacktestReportRef, load_backtest_report
    from polisyos.runtime.http import dev_identity_middleware
    from polisyos.runtime.http.routes import runs as runs_routes
    from polisyos.runtime.http.services import predictive_calibration as calibration_service
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationAssociation,
        PredictiveCalibrationRequest,
    )
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        catalog_serving_source_scope,
        current_catalog_serving_source,
        resolve_catalog_serving_source,
    )
    from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
    from tests.unit.remediation.test_frc_02_owner import _rule, _source, _spec

    def assert_persisted_evidence_identity(store: Any, stored_association: dict[str, Any]) -> None:
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            ir_store = _ensure_ir_artifact_store(store)
            report_ref = BacktestReportRef.model_validate(stored_association["backtest_report_ref"])
            report = load_backtest_report(ir_store, report_ref)
            evidence = load_empirical_calibration_evidence(
                ir_store,
                EmpiricalCalibrationEvidenceRef.model_validate(
                    stored_association["empirical_evidence_ref"]
                ),
            )
            reopened_association = PredictiveCalibrationAssociation.model_validate(
                stored_association
            )
            assert reopened_association.evidence_reason_codes == evidence.failure_codes

            assert len("run-bound candidate report ") + len(report.report_id) > 120
            assert evidence.evidence_origin == "run-bound candidate report"
            assert evidence.report_id == report.report_id
            assert evidence.report_ref == report_ref
            assert (
                evidence.report_ref.model_dump(mode="json")
                == stored_association["backtest_report_ref"]
            )
            assert evidence.report_ref.manifest_profile_sha256 is not None
            assert report.metadata["run_binding"]["run_id"] == core_run_id
            assert report.metadata["run_binding"]["intent_id"] == stored_association["intent_id"]
            assert report.metadata["n4_outcome_target_binding"] == {
                "status": "not_established",
                "reason_code": "n4_outcome_target_binding_not_established",
                "n4_target_variable": "government.balance",
                "n4_metric_id": fixture.problem.outcome_of_interest.metric_id,
                "observed_target_metric": report.metadata["target_metric"],
            }

            role_refs = (
                ("scope_binding", evidence.scope_binding_ref),
                ("calibration_threshold", evidence.calibration_threshold_ref),
                ("observed_outcome", evidence.observed_outcome_ref),
                ("prediction", evidence.prediction_ref),
                ("evaluation_design", evidence.evaluation_design_ref),
                ("credible_evaluation", evidence.credible_evaluation_evidence_ref),
                *(("source_lineage", ref) for ref in evidence.source_lineage_refs),
                *(("method_lineage", ref) for ref in evidence.method_lineage_refs),
            )
            parent_manifest = ir_store.get_manifest(report_ref)
            for role, source_roles in REFERENCE_SOURCE_INPUT_ROLES.items():
                selected_refs = [ref for candidate_role, ref in role_refs if candidate_role == role]
                assert len(selected_refs) == 1
                role_ref = selected_refs[0]
                assert role_ref is not None
                assert role_ref.manifest_profile_sha256 is not None
                role_manifest = ir_store.get_manifest_by_profile(
                    role_ref.artifact_id, role_ref.manifest_profile_sha256
                )
                selected_role_identity = ArtifactRef(
                    artifact_id=ArtifactID.model_validate(str(role_ref.artifact_id)),
                    kind=role_ref.kind,
                    media_type=role_ref.media_type,
                    manifest_profile_sha256=role_ref.manifest_profile_sha256,
                )
                resolved_role_identity = ArtifactRef(
                    artifact_id=role_manifest.artifact_id,
                    kind=role_manifest.kind,
                    media_type=role_manifest.media_type,
                    manifest_profile_sha256=artifact_manifest_profile_sha256(role_manifest),
                )
                assert resolved_role_identity == selected_role_identity
                assert role_manifest.artifact_schema == SchemaInfo(
                    name=role_ref.schema_name, version=role_ref.schema_version
                )
                actual_edges = tuple(
                    (str(item.artifact_id), item.role, item.manifest_profile_sha256)
                    for item in role_manifest.inputs
                )
                expected_edges = tuple(
                    (str(item.artifact_id), item.role, item.manifest_profile_sha256)
                    for item in parent_manifest.inputs
                    if item.role in source_roles
                )
                assert len(expected_edges) == len(source_roles)
                assert sorted(actual_edges) == sorted(expected_edges)

    cas_root = tmp_path / ".polisyos"
    shared_cas = FileSystemCAS(cas_root)
    from tests.integration.core_runtime.test_acquisition_world_growth_chain import (
        _admit_served_wdi_projection,
    )

    owner_admission = await _admit_served_wdi_projection(
        tmp_path / "profile-owner",
        monkeypatch,
        request,
        baseline_country_code="UKR",
        baseline_period_count=14,
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        revised_source=False,
        artifact_store=shared_cas,
    )
    owner_repo_root = owner_admission.served.case.authority.repo_root
    owner_overlay_path = owner_admission.served.case.call_args["overlay_path"]
    assert (
        owner_overlay_path.resolve() == default_acquisition_overlay_path(owner_repo_root).resolve()
    )
    selected_source = resolve_catalog_serving_source(
        owner_repo_root,
        selection=None,
        requested_profile="preflight_core",
    )
    tenant_cas = shared_cas.for_tenant("tenant-fixture", cell_id="cell-fixture")
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        with catalog_serving_source_scope(selected_source):
            value_profile = RealValueOwnerGateway(
                repo_root=owner_repo_root,
                catalog_serving_source=selected_source,
                catalog_overlay_path=owner_overlay_path,
                artifact_store=tenant_cas,
                activated_observation_projection=owner_admission.projection,
            ).load_value_data_profile(
                candidate=object(),
                problem=owner_admission.served.closure.design_problem_basis,
                world_record=object(),
            )
        profile_unit_id = value_profile.rows[0].unit_id
        profile_rows = tuple(
            sorted(
                (row for row in value_profile.rows if row.unit_id == profile_unit_id),
                key=lambda row: row.period_id,
            )
        )
        assert len(profile_rows) == 15
        assert len({row.period_id for row in profile_rows}) == len(profile_rows)
        profile_values = [row.outcome_value for row in profile_rows]
        ir_store = _ensure_ir_artifact_store(tenant_cas)
        projection_ref = put_json_artifact(
            ir_store,
            owner_admission.projection.model_dump(mode="json"),
            kind="runtime.value_owner_source_projection",
            schema_name="runtime.value_owner_source_projection.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        selected_profile_ref = ArtifactRef.model_validate(
            put_json_artifact(
                ir_store,
                value_profile.model_dump(mode="json"),
                kind="runtime.value_data_profile",
                schema_name="runtime.value_data_profile.v2",
                schema_version="2.0",
                inputs=(
                    InputRef(
                        artifact_id=projection_ref["artifact_id"],
                        role="activated_source_projection",
                        manifest_profile_sha256=projection_ref["manifest_profile_sha256"],
                    ),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )
        observed_data_ref = put_json_artifact(
            ir_store,
            {value_profile.outcome: profile_values},
            kind="test.forecast.profile_observed_data",
            schema_name="test.forecast.profile_observed_data.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        observed_snapshot = DataSnapshot(
            data_ref=ArtifactRef.model_validate(observed_data_ref),
            stats={"rows": len(profile_values), "source": "selected_owner_profile_fixture"},
        )
        selected_profile_observed_ref = DataSnapshotRef.model_validate(
            put_json_artifact(
                ir_store,
                observed_snapshot.model_dump(mode="json"),
                kind="fabric.data_snapshot",
                schema_name="polisyos.core.DataSnapshot",
                schema_version="0.2.0",
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )

    # Build a second real Data Forge owner projection whose source contains two
    # distinct declared condition groups for each unit-period. The candidate
    # aggregate below is content-bound to those owner rows, but the supported
    # serving producer refuses to aggregate them because no source rule grants
    # aggregation at one unit-period.
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.generation_cycle import (
        ValueDataProfile,
        _derived_value_data_modalities,
        _value_owner_row,
    )
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    local_source_rows = [
        {
            "country_code": "UA",
            "year": year,
            "balance": value,
            "condition_json": json.dumps({"series": series}, sort_keys=True, separators=(",", ":")),
        }
        for year, values in zip(
            (2021, 2022, 2023, 2024),
            ((-20.0, -18.0), (-19.0, -17.0), (-18.0, -16.0), (-17.0, -15.0)),
            strict=True,
        )
        for series, value in zip(("published", "revised"), values, strict=True)
    ]
    local_owner = make_native_multivariable_active_projections(
        tmp_path / "local-profile-owner",
        source_rows=local_source_rows,
        variable_specs=(
            {
                "target_variable": "government.balance",
                "raw_field": "balance",
                "raw_unit": "percent_gdp",
                "canonical_unit": "percent_gdp",
                "valid_min": -100.0,
                "valid_max": 100.0,
                "temporal_start": "2021",
                "temporal_end": "2024",
            },
        ),
        condition_units_by_raw_field={"balance": "percent_gdp"},
        artifact_store=tenant_cas,
    )
    local_projection = local_owner.projections["government.balance"]
    local_sources_by_period: dict[int, list[tuple[float, str, str, str]]] = {}
    for projected_row in local_projection.observations:
        observation = projected_row.observation
        assert observation.year is not None
        local_sources_by_period.setdefault(observation.year, []).append(
            (
                observation.value,
                observation.dataset_id,
                observation.observation_id,
                "percent_gdp",
            )
        )
    assert tuple(sorted(local_sources_by_period)) == (2021, 2022, 2023, 2024)
    assert all(len(rows) == 2 for rows in local_sources_by_period.values())
    local_profile_rows = tuple(
        _value_owner_row(
            outcome="government.balance",
            unit_id="UA",
            period_id=period_id,
            source_rows=tuple(source_rows),
        )
        for period_id, source_rows in sorted(local_sources_by_period.items())
    )
    local_rows_payload = tuple(row.model_dump(mode="json") for row in local_profile_rows)
    local_profile_payload = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "government.balance",
        "measurement_unit": "percent_gdp",
        "rows": local_rows_payload,
        "owner_row_count": len(local_profile_rows),
        "unit_count": 1,
        "period_count": 4,
        "available_data_modalities": _derived_value_data_modalities(local_profile_rows),
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "candidate://actual-local-lift-owner-row-aggregate",
        "owner_rows_content_hash": gy_content_hash(local_rows_payload),
    }
    local_aggregate_profile = ValueDataProfile.model_validate(
        {
            **local_profile_payload,
            "content_hash": gy_content_hash(local_profile_payload),
        }
    )
    assert all(len(row.source_row_content_hashes) == 2 for row in local_aggregate_profile.rows)
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        local_ir_store = _ensure_ir_artifact_store(tenant_cas)
        local_projection_ref = put_json_artifact(
            local_ir_store,
            local_projection.model_dump(mode="json"),
            kind="runtime.value_owner_source_projection",
            schema_name="runtime.value_owner_source_projection.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        local_profile_ref = ArtifactRef.model_validate(
            put_json_artifact(
                local_ir_store,
                local_aggregate_profile.model_dump(mode="json"),
                kind="runtime.value_data_profile",
                schema_name="runtime.value_data_profile.v2",
                schema_version="2.0",
                inputs=(
                    InputRef(
                        artifact_id=local_projection_ref["artifact_id"],
                        role="activated_source_projection",
                        manifest_profile_sha256=local_projection_ref["manifest_profile_sha256"],
                    ),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )
        local_observed_values = [row.outcome_value for row in local_aggregate_profile.rows]
        local_observed_data_ref = put_json_artifact(
            local_ir_store,
            {local_aggregate_profile.outcome: local_observed_values},
            kind="test.forecast.profile_observed_data",
            schema_name="test.forecast.profile_observed_data.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        local_observed_snapshot = DataSnapshot(
            data_ref=ArtifactRef.model_validate(local_observed_data_ref),
            stats={"rows": len(local_observed_values), "source": "candidate_local_owner_rows"},
        )
        local_observed_ref = DataSnapshotRef.model_validate(
            put_json_artifact(
                local_ir_store,
                local_observed_snapshot.model_dump(mode="json"),
                kind="fabric.data_snapshot",
                schema_name="polisyos.core.DataSnapshot",
                schema_version="0.2.0",
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )

    def selected_snapshot(repo_root, target_root):
        selected_database = target_root / "datasets" / "graph" / "dataset_catalog.duckdb"
        selected_database.parent.mkdir(parents=True, exist_ok=True)
        copyfile(repo_root / "catalog" / "catalog.duckdb", selected_database)
        return CatalogServingSourceSelection(
            snapshot_root=target_root,
            catalog_run_profile=selected_source.catalog_run_profile,
        )

    wdi_source_selection = selected_snapshot(owner_repo_root, tmp_path / "selected-wdi-source")
    local_source_selection = selected_snapshot(
        local_owner.repo_root, tmp_path / "selected-local-source"
    )

    captured_inputs: list[ArtifactRef] = []

    def attach_selected_inputs(context: Any) -> None:
        if not captured_inputs:
            training = [float(value) for value in range(10, 21)]
            observed = _source(
                context.store,
                training=training,
                holdout=[21.0, 22.0, 23.0, 24.0],
            )
            comparison_observed = _source(
                context.store,
                training=training,
                holdout=[1000.0, 1001.0, 1002.0, 1003.0],
            )
            model_default = _spec(
                context.store, kind="ir.model_spec", spec_id="forecast-model-fixture"
            )
            policy_default = _spec(
                context.store, kind="ir.policy_spec", spec_id="forecast-policy-fixture"
            )
            model_selected = context.store.put_bytes(
                context.store.get_bytes(model_default),
                PutOptions(
                    kind=model_default.kind,
                    media_type=model_default.media_type,
                    schema=SchemaInfo(
                        name="test.selected.forecast_model_spec", version="nondefault-view"
                    ),
                ),
                return_selected_profile=True,
            )
            policy_selected = context.store.put_bytes(
                context.store.get_bytes(policy_default),
                PutOptions(
                    kind=policy_default.kind,
                    media_type=policy_default.media_type,
                    schema=SchemaInfo(
                        name="test.selected.forecast_policy_spec", version="nondefault-view"
                    ),
                ),
                return_selected_profile=True,
            )
            assert model_selected.artifact_id == model_default.artifact_id
            assert policy_selected.artifact_id == policy_default.artifact_id
            assert model_selected.manifest_profile_sha256 != model_default.manifest_profile_sha256
            assert policy_selected.manifest_profile_sha256 != policy_default.manifest_profile_sha256
            captured_inputs.extend(
                [
                    ArtifactRef.model_validate(observed),
                    ArtifactRef.model_validate(comparison_observed),
                    model_default,
                    model_selected,
                    policy_default,
                    policy_selected,
                    _rule(context.store),
                    ArtifactRef.model_validate(local_profile_ref),
                    ArtifactRef.model_validate(local_observed_ref),
                ]
            )
            context.add_input(selected_profile_ref)
            context.add_input(ArtifactRef.model_validate(selected_profile_observed_ref))
            context.add_input(local_profile_ref)
            context.add_input(ArtifactRef.model_validate(local_observed_ref))
        existing = {
            (str(item.artifact_id), item.manifest_profile_sha256)
            for item in context.run_manifest.inputs
        }
        for ref in captured_inputs:
            identity = (str(ref.artifact_id), ref.manifest_profile_sha256)
            if identity not in existing:
                context.add_input(ref)
                existing.add(identity)

    fixture = await _run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
        root_input_factory=attach_selected_inputs,
    )
    request.addfinalizer(fixture.service.close)
    core_run_id = str(fixture.job.progress["core_run_id"])
    job_id = fixture.job.job_id
    assert fixture.profile.rule.operator_kind == "tax_relief_rate"
    assert fixture.profile.rule.parameter_id == "rate"
    assert fixture.profile.rule.target_world_slot == "global.tax_rate"
    assert fixture.profile.rule.unit_id == "ratio"
    assert fixture.model_declaration.outcome_variable == "government.balance"
    assert fixture.model_declaration.outcome_unit_id == "usd"
    fixture_control_store_path = fixture.service._control_store._sqlite_path
    # Fresh API services must read the same durable control store that produced
    # the completed job and its selected core-manifest reference.
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH",
        str(fixture_control_store_path),
    )
    core_runs_root = cas_root / "runs"
    monkeypatch.setattr(
        dev_identity_middleware,
        "build_fixture_identity_claims",
        _fixture_claims,
    )

    def new_reader_app(
        *,
        allow_candidate_run_predictive_calibration_surface: bool | None = None,
        source_repo_root=None,
        catalog_source_selection: CatalogServingSourceSelection | None = None,
    ):
        app_options: dict[str, Any] = {}
        if allow_candidate_run_predictive_calibration_surface is not None:
            app_options["allow_candidate_run_predictive_calibration_surface"] = (
                allow_candidate_run_predictive_calibration_surface
            )
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            app = create_runtime_api_app(
                cas_root=cas_root,
                core_runs_root=core_runs_root,
                allow_fixture_identity=True,
                repo_root=owner_repo_root if source_repo_root is None else source_repo_root,
                catalog_run_profile=(
                    selected_source.catalog_run_profile
                    if catalog_source_selection is None
                    else catalog_source_selection.catalog_run_profile
                ),
                catalog_source_selection=catalog_source_selection,
                **app_options,
            )
        _install_fixture_tenant_lifespan(app)
        control_service = app.state.runtime_container.control_service
        assert control_service is not None
        app_source = control_service.catalog_serving_source
        expected_repo_root = (
            owner_repo_root if source_repo_root is None else source_repo_root
        ).resolve()
        assert app_source.repo_root == expected_repo_root
        expected_profile = (
            selected_source.catalog_run_profile
            if catalog_source_selection is None
            else catalog_source_selection.catalog_run_profile
        )
        assert app_source.catalog_run_profile == expected_profile
        assert app_source.selection_basis == (
            "legacy_default_candidate_only"
            if catalog_source_selection is None
            else "explicit_path_candidate_only"
        )
        return app

    route_source_calls: list[tuple[str, object, object]] = []
    original_route_producer = runs_routes.produce_run_predictive_calibration
    original_route_reader = runs_routes.load_run_predictive_calibration

    def record_route_producer(*args: Any, **kwargs: Any) -> Any:
        route_source_calls.append(
            ("produce", current_catalog_serving_source(), kwargs.get("store"))
        )
        return original_route_producer(*args, **kwargs)

    def record_route_reader(*args: Any, **kwargs: Any) -> Any:
        route_source_calls.append(("read", current_catalog_serving_source(), kwargs.get("store")))
        return original_route_reader(*args, **kwargs)

    monkeypatch.setattr(runs_routes, "produce_run_predictive_calibration", record_route_producer)
    monkeypatch.setattr(runs_routes, "load_run_predictive_calibration", record_route_reader)

    unspecified_source = object()

    def assert_route_source_bound(
        reader_app: Any,
        operation: str,
        *,
        expected_source: object = unspecified_source,
    ) -> None:
        control_service = reader_app.state.runtime_container.control_service
        assert control_service is not None
        selected_source = (
            control_service.catalog_serving_source
            if expected_source is unspecified_source
            else expected_source
        )
        assert any(
            operation_name == operation
            and observed_store is reader_app.state.runtime_api_ctx.store
            and observed_source is selected_source
            for operation_name, observed_source, observed_store in route_source_calls
        ), f"{operation} did not observe this app's exact configured source object"

    # RuntimeContainer startup launches an embedded worker whose first custody
    # scan can persist a nonreceipt into this shared CAS. Observe completion of
    # the real maintenance callback before taking the endpoint's no-write baseline.
    startup_maintenance_condition = Condition()
    startup_maintenance_results: dict[int, Any] = {}
    original_startup_maintenance = ControlPlaneService.run_published_signature_custody_maintenance

    def record_startup_maintenance(service: ControlPlaneService) -> Any:
        result = original_startup_maintenance(service)
        with startup_maintenance_condition:
            startup_maintenance_results[id(service)] = result
            startup_maintenance_condition.notify_all()
        return result

    monkeypatch.setattr(
        ControlPlaneService,
        "run_published_signature_custody_maintenance",
        record_startup_maintenance,
    )

    def wait_for_startup_maintenance(reader_app: Any) -> None:
        control_service = reader_app.state.runtime_container.control_service
        assert control_service is not None
        assert control_service._control_store._sqlite_path == fixture_control_store_path
        if control_service._worker is None:
            return
        service_id = id(control_service)
        with startup_maintenance_condition:
            completed = startup_maintenance_condition.wait_for(
                lambda: service_id in startup_maintenance_results,
                timeout=15.0,
            )
        assert completed, "embedded runtime worker did not finish its startup maintenance"
        assert startup_maintenance_results[service_id].scan_receipt_ref is not None

    # The producer POST and later readers exercise the normal-root default.
    app = new_reader_app()
    with TestClient(app) as client:
        wait_for_startup_maintenance(app)
        assert app.state.runtime_api_ctx.allow_candidate_run_predictive_calibration_surface is True
        run_response = client.get(f"/api/v1/runs/{core_run_id}")
        assert run_response.status_code == 200, run_response.text
        run = run_response.json()["run"]
        assert run["manifest_ref"]["manifest_profile_sha256"].startswith("sha256:")
        candidate_refs = [
            observation["n4_source_ref"]
            for observation in run["candidate_simulation"]["n5_observations"]
            if observation["status"] == "joint_simulated"
            and observation["lineage_status"] == "resolved"
            and observation.get("n4_source_ref") is not None
        ]
        assert candidate_refs
        assert candidate_refs[0]["manifest_profile_sha256"].startswith("sha256:")
        input_refs = run["root_input_artifacts"]
        for expected_ref in captured_inputs:
            assert any(
                actual_ref["artifact_id"] == str(expected_ref.artifact_id)
                and actual_ref["kind"] == expected_ref.kind
                and actual_ref["media_type"] == expected_ref.media_type
                and actual_ref["manifest_profile_sha256"] == expected_ref.manifest_profile_sha256
                for actual_ref in input_refs
            )
        for expected_ref in (
            selected_profile_ref,
            ArtifactRef.model_validate(selected_profile_observed_ref),
            local_profile_ref,
            ArtifactRef.model_validate(local_observed_ref),
        ):
            assert any(
                actual_ref["artifact_id"] == str(expected_ref.artifact_id)
                and actual_ref["kind"] == expected_ref.kind
                and actual_ref["media_type"] == expected_ref.media_type
                and actual_ref["manifest_profile_sha256"] == expected_ref.manifest_profile_sha256
                for actual_ref in input_refs
            )
        selected_observed_sources = [
            expected_ref.model_dump(mode="json")
            for expected_ref in captured_inputs
            if expected_ref.kind == "fabric.data_snapshot"
        ]
        assert len(selected_observed_sources) == 2
        selected = {
            expected_ref.kind: expected_ref.model_dump(mode="json")
            for expected_ref in captured_inputs
            if expected_ref.kind != "fabric.data_snapshot"
        }
        body = {
            "intent_id": "ui-intent-r228-e2e-1",
            "candidate_source_ref": candidate_refs[0],
            "observed_source_ref": selected_observed_sources[0],
            "model_spec_ref": selected["ir.model_spec"],
            "policy_spec_ref": selected["ir.policy_spec"],
            "calibration_rule_ref": selected["ir.forecast_calibration_rule"],
            "calibration_threshold": 0.9,
            "split": {
                "train_start": 0,
                "train_end": 11,
                "holdout_start": 11,
                "holdout_end": 15,
                "horizon": 4,
            },
            "target_metric": "metric",
            "method_params": {"horizon": 4, "alpha": 0.3, "beta": 0.1},
            "temporal_roles": {
                "data_valid_time": "2026-01-01T00:00:00Z",
                "calibration_window_start": "2026-01-02T00:00:00Z",
                "calibration_window_end": "2026-01-03T00:00:00Z",
                "policy_effective_time": "2026-01-04T00:00:00Z",
                "prediction_time": "2026-01-05T00:00:00Z",
                "observation_time": "2026-01-06T00:00:00Z",
            },
            "seed": 0,
        }
        analyst_claims = _fixture_claims()
        viewer_claims = analyst_claims.model_copy(
            update={"roles": frozenset({PolicyOSRole.VIEWER})}
        )
        monkeypatch.setattr(
            dev_identity_middleware,
            "build_fixture_identity_claims",
            lambda: viewer_claims,
        )
        denied = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=body,
        )
        assert denied.status_code == 403, denied.text
        control_service = app.state.runtime_container.control_service
        assert control_service is not None
        event_log = control_service._diagnostic_event_log
        prewrite_events = event_log.list_events(run_id=core_run_id, job_id=job_id)
        assert not any(
            record.event.producer_component == "polisyos.runtime.http.predictive_calibration"
            for record in prewrite_events
        )

        monkeypatch.setattr(
            dev_identity_middleware,
            "build_fixture_identity_claims",
            lambda: analyst_claims,
        )
        context_store = cast("FileSystemCAS", app.state.runtime_api_ctx.store)

        def local_cas_byte_inventory() -> dict[str, str]:
            artifact_root = cas_root / "artifacts" / "sha256"
            return {
                path.relative_to(artifact_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(artifact_root.rglob("*"))
                if path.is_file()
            }

        def predictive_event_receipts():
            return tuple(
                (
                    record.event.event_id,
                    tuple(record.event.artifact_refs),
                    record.payload_sha256,
                )
                for record in event_log.list_events(run_id=core_run_id, job_id=job_id)
                if record.event.producer_component == "polisyos.runtime.http.predictive_calibration"
            )

        root_bound_roles = (
            ("observed_source_ref", "observed_source"),
            ("model_spec_ref", "model_spec"),
            ("policy_spec_ref", "policy_spec"),
            ("calibration_rule_ref", "calibration_rule"),
        )
        owner_calls_before_root_binding: list[Any] = []

        def reject_owner_before_root_binding(_self: ForecastOwner, owner_request: Any) -> None:
            owner_calls_before_root_binding.append(owner_request)
            raise AssertionError("unrooted input reached ForecastOwner")

        with monkeypatch.context() as source_root_probe:
            source_root_probe.setattr(
                ForecastOwner,
                "run",
                reject_owner_before_root_binding,
            )
            for role_field, error_role in root_bound_roles:
                selected_ref = ArtifactRef.model_validate(body[role_field])
                with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
                    sibling_profile_ref = context_store.put_bytes(
                        context_store.get_bytes(selected_ref),
                        PutOptions(
                            kind=selected_ref.kind,
                            media_type=selected_ref.media_type,
                            schema=SchemaInfo(
                                name=f"test.unrooted.{error_role}",
                                version="nondefault-view",
                            ),
                        ),
                        return_selected_profile=True,
                    )
                    assert context_store.verify(sibling_profile_ref).ok
                assert sibling_profile_ref.artifact_id == selected_ref.artifact_id
                assert sibling_profile_ref.kind == selected_ref.kind
                assert sibling_profile_ref.media_type == selected_ref.media_type
                assert sibling_profile_ref.manifest_profile_sha256 is not None
                assert (
                    sibling_profile_ref.manifest_profile_sha256
                    != selected_ref.manifest_profile_sha256
                )
                assert not any(
                    actual_ref["artifact_id"] == str(sibling_profile_ref.artifact_id)
                    and actual_ref["kind"] == sibling_profile_ref.kind
                    and actual_ref["media_type"] == sibling_profile_ref.media_type
                    and actual_ref["manifest_profile_sha256"]
                    == sibling_profile_ref.manifest_profile_sha256
                    for actual_ref in input_refs
                )

                rejected_body = {
                    **body,
                    role_field: sibling_profile_ref.model_dump(mode="json"),
                }
                typed_request = PredictiveCalibrationRequest.model_validate(rejected_body)
                intent_key = calibration_service.RuntimeOperationIntentKey(
                    purpose="run.predictive_calibration.v1",
                    tenant_id="tenant-fixture",
                    cell_id="cell-fixture",
                    actor_subject_sha256=hashlib.sha256(b"user-fixture").hexdigest(),
                    run_id=core_run_id,
                    intent_id=body["intent_id"],
                    body_sha256=calibration_service._operation_body_sha256(
                        request=typed_request,
                        run_id=core_run_id,
                        job_id=job_id,
                        tenant_id="tenant-fixture",
                        cell_id="cell-fixture",
                        run_manifest_ref=ArtifactRef.model_validate(run["manifest_ref"]),
                    ),
                )
                cas_before = local_cas_byte_inventory()
                events_before = predictive_event_receipts()
                rejected = client.post(
                    f"/api/v1/runs/{core_run_id}/predictive-calibration",
                    json=rejected_body,
                )
                assert rejected.status_code == 422, rejected.text
                assert rejected.json()["code"] == (
                    f"predictive_calibration_{error_role}_not_run_root"
                )
                assert local_cas_byte_inventory() == cas_before
                assert predictive_event_receipts() == events_before
                intent = event_log._store.get_runtime_operation_intent(intent_key)
                assert intent.status == "unknown"
                assert intent.record is None
        assert owner_calls_before_root_binding == []
        profileless_candidate_ref = dict(body["candidate_source_ref"])
        profileless_candidate_ref.pop("manifest_profile_sha256", None)
        profileless_response = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json={**body, "candidate_source_ref": profileless_candidate_ref},
        )
        assert profileless_response.status_code == 422, profileless_response.text
        assert (
            profileless_response.json()["code"]
            == "predictive_calibration_candidate_source_not_run_root"
        )
        prewrite_events = event_log.list_events(run_id=core_run_id, job_id=job_id)
        assert not any(
            record.event.producer_component == "polisyos.runtime.http.predictive_calibration"
            for record in prewrite_events
        )

        candidate_ref = ArtifactRef.model_validate(body["candidate_source_ref"])
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            alternate_profile_candidate_ref = context_store.put_bytes(
                context_store.get_bytes(candidate_ref),
                PutOptions(
                    kind=candidate_ref.kind,
                    media_type=candidate_ref.media_type,
                    schema=SchemaInfo(
                        name="test.alternate.candidate_source",
                        version="nondefault-view",
                    ),
                ),
                return_selected_profile=True,
            )
        assert alternate_profile_candidate_ref.artifact_id == candidate_ref.artifact_id
        assert (
            alternate_profile_candidate_ref.manifest_profile_sha256
            != candidate_ref.manifest_profile_sha256
        )
        alternate_profile_response = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json={
                **body,
                "candidate_source_ref": alternate_profile_candidate_ref.model_dump(mode="json"),
            },
        )
        assert alternate_profile_response.status_code == 422, alternate_profile_response.text
        assert (
            alternate_profile_response.json()["code"]
            == "predictive_calibration_candidate_source_not_run_root"
        )
        prewrite_events = event_log.list_events(run_id=core_run_id, job_id=job_id)
        assert not any(
            record.event.producer_component == "polisyos.runtime.http.predictive_calibration"
            for record in prewrite_events
        )

        # Scope the direct CAS fixture write; keep its HTTP request outside this scope.
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            unrooted_model_ref = _spec(
                context_store,
                kind="ir.model_spec",
                spec_id="unrooted-model-spec-fixture",
            )
        unrooted_response = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json={**body, "model_spec_ref": unrooted_model_ref.model_dump(mode="json")},
        )
        assert unrooted_response.status_code == 422, unrooted_response.text
        assert unrooted_response.json()["code"] == "predictive_calibration_model_spec_not_run_root"
        prewrite_events = event_log.list_events(run_id=core_run_id, job_id=job_id)
        assert not any(
            record.event.producer_component == "polisyos.runtime.http.predictive_calibration"
            for record in prewrite_events
        )

        disabled_app = new_reader_app(allow_candidate_run_predictive_calibration_surface=False)
        with TestClient(disabled_app) as disabled_client:
            wait_for_startup_maintenance(disabled_app)
            disabled_context = disabled_app.state.runtime_api_ctx
            assert disabled_context.allow_candidate_run_predictive_calibration_surface is False
            disabled_service = disabled_app.state.runtime_container.control_service
            assert disabled_service is not None
            disabled_event_log = disabled_service._diagnostic_event_log

            def event_receipts(records):
                return tuple(
                    (
                        record.event.event_id,
                        tuple(record.event.artifact_refs),
                        record.payload_sha256,
                    )
                    for record in records
                )

            def cas_byte_inventory():
                artifact_root = cas_root / "artifacts" / "sha256"
                return {
                    path.relative_to(artifact_root).as_posix(): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in sorted(artifact_root.rglob("*"))
                    if path.is_file()
                }

            disabled_events_before = disabled_event_log.list_events(
                run_id=core_run_id, job_id=job_id
            )
            disabled_cas_before = cas_byte_inventory()
            disabled_intent_key = calibration_service.RuntimeOperationIntentKey(
                purpose="run.predictive_calibration.v1",
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
                actor_subject_sha256=hashlib.sha256(b"user-fixture").hexdigest(),
                run_id=core_run_id,
                intent_id=body["intent_id"],
                body_sha256=calibration_service._operation_body_sha256(
                    request=PredictiveCalibrationRequest.model_validate(body),
                    run_id=core_run_id,
                    job_id=job_id,
                    tenant_id="tenant-fixture",
                    cell_id="cell-fixture",
                    run_manifest_ref=ArtifactRef.model_validate(run["manifest_ref"]),
                ),
            )
            disabled_owner_calls: list[Any] = []

            def reject_owner_when_disabled(_self, owner_request):
                disabled_owner_calls.append(owner_request)
                raise AssertionError("disabled run surface called ForecastOwner")

            with monkeypatch.context() as disabled_probe:
                disabled_probe.setattr(ForecastOwner, "run", reject_owner_when_disabled)
                disabled_response = disabled_client.post(
                    f"/api/v1/runs/{core_run_id}/predictive-calibration",
                    json=body,
                )
            assert disabled_response.status_code == 503, disabled_response.text
            assert (
                disabled_response.json()["code"]
                == "candidate_predictive_diagnostic_surface_disabled"
            )
            assert disabled_owner_calls == []
            assert event_receipts(
                disabled_event_log.list_events(run_id=core_run_id, job_id=job_id)
            ) == event_receipts(disabled_events_before)
            disabled_intent = disabled_event_log._store.get_runtime_operation_intent(
                disabled_intent_key
            )
            assert disabled_intent.status == "unknown"
            assert disabled_intent.record is None
            assert cas_byte_inventory() == disabled_cas_before

        s10_owner_supports: list[Any] = []
        original_produce_s10 = RealValueOwnerGateway.produce_forecast_inputs

        def capture_s10_owner_support(self, **kwargs):
            result = original_produce_s10(self, **kwargs)
            if kwargs.get("selected_method_fqn") == calibration_service._METHOD_FQN:
                support = result.get("forecast_support")
                if support is not None:
                    s10_owner_supports.append(support.model_copy(deep=True))
            return result

        monkeypatch.setattr(
            RealValueOwnerGateway,
            "produce_forecast_inputs",
            capture_s10_owner_support,
        )
        producer_started = Event()
        release_producer = Event()
        request_completion = Condition()
        owner_requests: list[Any] = []
        owner_results: list[Any] = []
        original_owner_run = ForecastOwner.run

        def hold_single_owner(self, owner_request):
            with request_completion:
                owner_requests.append(owner_request)
                producer_started.set()
                request_completion.notify_all()
            if not release_producer.wait(timeout=60):
                raise TimeoutError("test did not release the admitted forecast owner")
            owner_result = original_owner_run(self, owner_request)
            owner_results.append(owner_result)
            return owner_result

        def notify_owner_request_completion(_future: Any) -> None:
            with request_completion:
                request_completion.notify_all()

        monkeypatch.setattr(ForecastOwner, "run", hold_single_owner)
        second_app = new_reader_app()
        with TestClient(second_app) as follower_client:
            primary_event_store = event_log._store
            follower_service = second_app.state.runtime_container.control_service
            assert follower_service is not None
            follower_event_store = follower_service._diagnostic_event_log._store
            assert primary_event_store is not follower_event_store
            assert (
                primary_event_store._sqlite_path
                == follower_event_store._sqlite_path
                == fixture_control_store_path
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                owner_future = pool.submit(
                    client.post,
                    f"/api/v1/runs/{core_run_id}/predictive-calibration",
                    json=body,
                )
                owner_future.add_done_callback(notify_owner_request_completion)
                try:
                    with request_completion:
                        observed_first_boundary = request_completion.wait_for(
                            lambda: producer_started.is_set() or owner_future.done(),
                            timeout=60,
                        )
                    if not producer_started.is_set():
                        if owner_future.done():
                            try:
                                early_response = owner_future.result(timeout=0)
                            except BaseException as exc:
                                raise AssertionError(
                                    "owner POST raised before ForecastOwner.run: "
                                    f"{type(exc).__name__}: {exc!r}"
                                ) from exc
                            raise AssertionError(
                                "owner POST completed before ForecastOwner.run: "
                                f"status={early_response.status_code}; "
                                f"body={early_response.text!r}"
                            )
                        assert observed_first_boundary, (
                            "owner POST remained pending and ForecastOwner.run did not start "
                            "within 60s"
                        )
                    follower = follower_client.post(
                        f"/api/v1/runs/{core_run_id}/predictive-calibration",
                        json=body,
                    )
                    assert follower.status_code == 409, follower.text
                    assert follower.json()["code"] == "predictive_calibration_intent_in_progress"
                finally:
                    release_producer.set()
                created = owner_future.result(timeout=360)
        assert created.status_code == 201, created.text
        assert_route_source_bound(app, "produce")
        assert_route_source_bound(second_app, "produce")
        assert len(owner_requests) == 1
        assert owner_requests[0].model_spec_ref.model_dump(mode="json") == selected["ir.model_spec"]
        assert (
            owner_requests[0].policy_spec_ref.model_dump(mode="json") == selected["ir.policy_spec"]
        )
        assert (
            owner_requests[0].calibration_rule.artifact_ref.model_dump(mode="json")
            == selected["ir.forecast_calibration_rule"]
        )
        result = created.json()
        association = result["association"]
        assert association["profile_join_status"] == "profileless_legacy"
        assert association.get("value_data_profile_ref") is None
        assert association.get("forecast_profile_member_ref") is None
        assert association["evidence_reason_codes"] == []
        assert association["candidate_source_ref"] == body["candidate_source_ref"]
        assert association["assessment"] == "limited"
        assert association["authority_scope"] == "predictive_only"
        for field in (
            "issuer_status",
            "source_time_status",
            "population_scope_status",
            "counterfactual_credibility_status",
        ):
            assert association[field] == "not_established"
        assert association["s10"]["counterfactual_credibility"] == "not_established"
        assert association["s10"]["outcome_binding_status"] == "not_established"
        assert association["s10"]["forecast_tier"] == "blocked"
        assert (
            "s10://calibration/fail-closed/n4_outcome_target_binding_not_established"
            in association["s10"]["limitation_refs"]
        )
        assert len(s10_owner_supports) == 1
        actual_s10_support = s10_owner_supports[0]
        assert association["s10"]["authority_boundary"] == (
            actual_s10_support.authority_boundary.model_dump(mode="json")
        )
        assert tuple(association["s10"]["may_not_use_for"]) == tuple(
            actual_s10_support.may_not_use_for
        )
        assert association["may_not_use_for"] == association["s10"]["may_not_use_for"]
        assert "causal_effect_authority" in actual_s10_support.may_not_use_for
        assert "s10_authority" in actual_s10_support.may_not_use_for
        assert association["intent_id"] == body["intent_id"]
        assert association["run_manifest_ref"] == run["manifest_ref"]
        assert association["request_sha256"]
        association_ref = result["association_ref"]
        assert association["model_spec_ref"] == selected["ir.model_spec"]
        assert association["policy_spec_ref"] == selected["ir.policy_spec"]
        assert association["calibration_rule_ref"] == selected["ir.forecast_calibration_rule"]
        evidence_ref = association["empirical_evidence_ref"]
        assert set(evidence_ref) == {
            "artifact_id",
            "kind",
            "media_type",
            "manifest_profile_sha256",
        }
        assert evidence_ref["kind"] == "ir.empirical_calibration_evidence"
        assert evidence_ref["media_type"] == "application/json"
        assert evidence_ref["manifest_profile_sha256"]

        control_service = app.state.runtime_container.control_service
        assert control_service is not None
        event_log = control_service._diagnostic_event_log
        events = event_log.list_events(run_id=core_run_id, job_id=job_id)
        published = [
            record
            for record in events
            if record.event.event_type == "polisyos.runtime.diagnostic.ref_publication.v1"
            and record.event.producer_component == "polisyos.runtime.http.predictive_calibration"
        ]
        assert len(published) == 1
        assert str(association_ref["artifact_id"]) in published[0].event.artifact_refs
        assert published[0].payload_sha256 is not None
        operation_key = calibration_service.RuntimeOperationIntentKey(
            purpose="run.predictive_calibration.v1",
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            actor_subject_sha256=hashlib.sha256(b"user-fixture").hexdigest(),
            run_id=core_run_id,
            intent_id=body["intent_id"],
            body_sha256=calibration_service._operation_body_sha256(
                request=PredictiveCalibrationRequest.model_validate(body),
                run_id=core_run_id,
                job_id=job_id,
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
                run_manifest_ref=ArtifactRef.model_validate(run["manifest_ref"]),
            ),
        )
        completed_intent = event_log._store.get_runtime_operation_intent(operation_key)
        assert completed_intent.status == "completed"
        assert completed_intent.record is not None
        assert completed_intent.record.event_id == association["event_id"]
        assert json.loads(completed_intent.record.result_ref_json or "{}") == association_ref

    fresh_app = new_reader_app()
    with TestClient(fresh_app) as client:
        assert (
            fresh_app.state.runtime_api_ctx.allow_candidate_run_predictive_calibration_surface
            is True
        )
        foreign_projection = RunCandidateSimulationProjection.model_validate(
            run["candidate_simulation"]
        ).model_copy(update={"run_id": f"{core_run_id}-foreign"})
        with monkeypatch.context() as wrong_run_patch:
            wrong_run_patch.setattr(
                runs_routes,
                "_candidate_simulation_for_indexed_run",
                lambda *_args, **_kwargs: foreign_projection,
            )
            wrong_run_response = client.get(f"/api/v1/runs/{core_run_id}/predictive-calibration")
        assert wrong_run_response.status_code == 409, wrong_run_response.text
        assert (
            wrong_run_response.json()["code"]
            == "predictive_calibration_candidate_source_not_run_root"
        )
        reopened = client.get(f"/api/v1/runs/{core_run_id}/predictive-calibration")
        assert reopened.status_code == 200, reopened.text
        assert_route_source_bound(fresh_app, "read")
        reopened_result = reopened.json()
        assert reopened_result["association_ref"] == association_ref
        assert reopened_result["association"] == association
        assert reopened_result["association"]["run_manifest_ref"] == run["manifest_ref"]
        assert len(s10_owner_supports) == 2
        reopened_s10_support = s10_owner_supports[1]
        assert reopened_result["association"]["s10"]["authority_boundary"] == (
            reopened_s10_support.authority_boundary.model_dump(mode="json")
        )
        assert tuple(reopened_result["association"]["s10"]["may_not_use_for"]) == tuple(
            reopened_s10_support.may_not_use_for
        )
        assert_persisted_evidence_identity(
            fresh_app.state.runtime_api_ctx.store,
            reopened_result["association"],
        )

        replay = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=body,
        )
        assert replay.status_code == 201, replay.text
        assert len(owner_requests) == 1
        assert replay.json()["association_ref"] == association_ref
        assert replay.json()["association"] == association

        conflicting_body = {**body, "target_metric": "different-metric"}
        conflict_response = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=conflicting_body,
        )
        assert conflict_response.status_code == 409, conflict_response.text
        assert conflict_response.json()["code"] == "predictive_calibration_intent_conflict"

        control_service = fresh_app.state.runtime_container.control_service
        assert control_service is not None
        event_log = control_service._diagnostic_event_log
        original_list_events = event_log.list_events
        stored_events = original_list_events(run_id=core_run_id, job_id=job_id)
        selected_event = next(
            record for record in stored_events if record.event.event_id == association["event_id"]
        )
        tampered = replace(selected_event, payload_sha256="sha256:" + "0" * 64)

        def tampered_list_events(**kwargs):
            return [
                tampered if record.event.event_id == tampered.event.event_id else record
                for record in original_list_events(**kwargs)
            ]

        monkeypatch.setattr(event_log, "list_events", tampered_list_events)
        tampered_get = client.get(f"/api/v1/runs/{core_run_id}/predictive-calibration")
        assert tampered_get.status_code == 409, tampered_get.text
        assert (
            tampered_get.json()["code"] == "predictive_calibration_event_payload_integrity_failed"
        )

        legacy_body = {**body, "intent_id": "r228-legacy-intent-fixture"}
        legacy_request = PredictiveCalibrationRequest.model_validate(legacy_body)
        legacy_request_sha256 = calibration_service._request_sha256(legacy_request)
        legacy_event_id = calibration_service._legacy_intent_event_id(
            core_run_id, legacy_request.intent_id
        )
        legacy_association = PredictiveCalibrationAssociation.model_validate(
            association
        ).model_copy(
            update={
                "event_id": legacy_event_id,
                "intent_id": legacy_request.intent_id,
                "request_sha256": legacy_request_sha256,
            }
        )
        reopened_store = cast("FileSystemCAS", fresh_app.state.runtime_api_ctx.store)
        # Materialize legacy CAS/event state under the fixture owner only; the retry stays unscoped.
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            legacy_association_ref = calibration_service._persist_association(
                store=reopened_store,
                association=legacy_association,
                report_inputs=(),
            )
            calibration_service._append_association_event(
                event_log=event_log,
                association=legacy_association,
                association_ref=legacy_association_ref,
                request_sha256=legacy_request_sha256,
                refs=(
                    legacy_association.run_manifest_ref,
                    legacy_association.candidate_source_ref,
                    legacy_association.observed_source_ref,
                    legacy_association.model_spec_ref,
                    legacy_association.policy_spec_ref,
                    legacy_association.calibration_rule_ref,
                    legacy_association.backtest_report_ref,
                    legacy_association.empirical_evidence_ref,
                    legacy_association.uncertainty_bundle_ref,
                ),
            )
        legacy_retry = client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=legacy_body,
        )
        assert legacy_retry.status_code == 409, legacy_retry.text
        assert (
            legacy_retry.json()["code"] == "predictive_calibration_legacy_intent_scope_unverifiable"
        )
        legacy_key = calibration_service.RuntimeOperationIntentKey(
            purpose="run.predictive_calibration.v1",
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            actor_subject_sha256=hashlib.sha256(b"user-fixture").hexdigest(),
            run_id=core_run_id,
            intent_id=legacy_request.intent_id,
            body_sha256=calibration_service._operation_body_sha256(
                request=legacy_request,
                run_id=core_run_id,
                job_id=job_id,
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
                run_manifest_ref=ArtifactRef.model_validate(run["manifest_ref"]),
            ),
        )
        legacy_intent = event_log._store.get_runtime_operation_intent(legacy_key)
        assert legacy_intent.status == "unknown"
        assert legacy_intent.record is None
        assert len(owner_requests) == 1

    # Hold prediction inputs, interval geometry, and method/run context constant;
    # only the run-rooted held-out observations differ. The second default-app
    # POST persists the real owner's empirical grade, and a new default app must
    # reopen that same grade from the association/report/evidence chain.
    comparison_body = {
        **body,
        "intent_id": "ui-intent-r228-e2e-2",
        "observed_source_ref": selected_observed_sources[1],
    }
    comparison_app = new_reader_app()
    with TestClient(comparison_app) as comparison_client:
        assert (
            comparison_app.state.runtime_api_ctx.allow_candidate_run_predictive_calibration_surface
            is True
        )
        comparison_post = comparison_client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=comparison_body,
        )
        assert comparison_post.status_code == 201, comparison_post.text
        assert_route_source_bound(comparison_app, "produce")
        comparison_post_result = comparison_post.json()
        comparison_reopened_response = comparison_client.get(
            f"/api/v1/runs/{core_run_id}/predictive-calibration"
        )
        assert comparison_reopened_response.status_code == 200, comparison_reopened_response.text
        assert_route_source_bound(comparison_app, "read")
        comparison_reopened_result = comparison_reopened_response.json()
        assert comparison_reopened_result["association"] == comparison_post_result["association"]
        assert (
            "calibration_floor_not_met"
            in comparison_reopened_result["association"]["evidence_reason_codes"]
        )
        assert_persisted_evidence_identity(
            comparison_app.state.runtime_api_ctx.store,
            comparison_reopened_result["association"],
        )

    assert len(owner_requests) == 2
    assert len(owner_results) == 2
    first_owner, comparison_owner = owner_results
    assert first_owner.method_fqn == comparison_owner.method_fqn
    assert first_owner.point_forecast == comparison_owner.point_forecast
    assert first_owner.predictive_intervals == comparison_owner.predictive_intervals
    assert first_owner.coverage_denominator == comparison_owner.coverage_denominator == 4
    assert first_owner.coverage_numerator != comparison_owner.coverage_numerator
    assert first_owner.empirical_coverage != comparison_owner.empirical_coverage
    assert first_owner.empirical_suitability != comparison_owner.empirical_suitability
    assert first_owner.empirical_suitability == "supported"
    assert comparison_owner.empirical_suitability == "limited"
    first_request, comparison_request = owner_requests
    assert first_request.value_data_profile_ref is None
    assert first_request.value_data_unit_id is None
    assert first_request.forecast_profile_member is None
    assert comparison_request.value_data_profile_ref is None
    assert comparison_request.value_data_unit_id is None
    assert comparison_request.forecast_profile_member is None
    assert first_owner.value_data_profile_ref is None
    assert first_owner.forecast_profile_member_ref is None
    assert comparison_owner.value_data_profile_ref is None
    assert comparison_owner.forecast_profile_member_ref is None
    for field in (
        "method_fqn",
        "method_params",
        "split",
        "target_metric",
        "seed",
        "calibration_rule",
        "temporal_roles",
        "model_spec_ref",
        "policy_spec_ref",
    ):
        assert getattr(first_request, field) == getattr(comparison_request, field), field
    assert first_request.observed_source_ref != comparison_request.observed_source_ref

    comparison_association = comparison_post_result["association"]
    assert comparison_association["profile_join_status"] == "profileless_legacy"
    assert comparison_association.get("value_data_profile_ref") is None
    assert comparison_association.get("forecast_profile_member_ref") is None
    assert "calibration_floor_not_met" in comparison_association["evidence_reason_codes"]
    assert comparison_association["intent_id"] == comparison_body["intent_id"]
    assert comparison_association["request_sha256"] != association["request_sha256"]
    assert comparison_association["observed_source_ref"] == selected_observed_sources[1]
    assert association["observed_source_ref"] == selected_observed_sources[0]
    for field in (
        "run_manifest_ref",
        "candidate_source_ref",
        "model_spec_ref",
        "policy_spec_ref",
        "calibration_rule_ref",
    ):
        assert comparison_association[field] == association[field], field
    assert (
        comparison_association["backtest_report_ref"]["artifact_id"]
        != association["backtest_report_ref"]["artifact_id"]
    )
    assert (
        comparison_association["empirical_evidence_ref"]["artifact_id"]
        != association["empirical_evidence_ref"]["artifact_id"]
    )
    assert comparison_post_result["association_ref"] != association_ref
    for stored, owner_result in (
        (association, first_owner),
        (comparison_association, comparison_owner),
    ):
        assert stored["observed_numerator"] == owner_result.coverage_numerator
        assert stored["observed_denominator"] == owner_result.coverage_denominator == 4
        assert stored["owner_suitability"] == owner_result.empirical_suitability
        assert stored["s10"]["numerator"] == owner_result.coverage_numerator
        assert stored["s10"]["denominator"] == owner_result.coverage_denominator
        assert stored["s10"]["observed_pass_rate"] == owner_result.empirical_coverage
        assert stored["assessment"] == "limited"
        assert stored["authority_scope"] == "predictive_only"
        assert stored["s10"]["counterfactual_credibility"] == "not_established"
        for field in (
            "issuer_status",
            "source_time_status",
            "population_scope_status",
            "counterfactual_credibility_status",
        ):
            assert stored[field] == "not_established"
    assert association["owner_suitability"] != comparison_association["owner_suitability"]
    assert (
        association["s10"]["calibration_status"]
        != comparison_association["s10"]["calibration_status"]
    )
    assert association["s10"]["forecast_tier"] == "blocked"
    assert comparison_association["s10"]["forecast_tier"] == "blocked"
    assert (
        association["s10"]["calibration_status"]
        != (comparison_association["s10"]["calibration_status"])
    )
    assert (
        association["s10"]["limitation_refs"] == (comparison_association["s10"]["limitation_refs"])
    )

    comparison_reader = new_reader_app()
    with TestClient(comparison_reader) as comparison_read_client:
        reader_context = comparison_reader.state.runtime_api_ctx
        assert reader_context.allow_candidate_run_predictive_calibration_surface is True
        comparison_reopened = comparison_read_client.get(
            f"/api/v1/runs/{core_run_id}/predictive-calibration"
        )
        assert comparison_reopened.status_code == 200, comparison_reopened.text
        assert_route_source_bound(comparison_reader, "read")
        comparison_reopened_result = comparison_reopened.json()
        assert_persisted_evidence_identity(
            comparison_reader.state.runtime_api_ctx.store,
            comparison_reopened_result["association"],
        )
    assert (
        comparison_reopened_result["association_ref"] == comparison_post_result["association_ref"]
    )
    assert comparison_reopened_result["association"] == comparison_association
    assert comparison_reopened_result["association"]["s10"] == comparison_association["s10"]
    assert comparison_reopened_result["association"]["s10"] != reopened_result["association"]["s10"]

    # The selected EMP-01 route consumes a profile issued from the actual
    # Data Forge owner above. Its profile and aligned observed series were
    # attached through the run's ordinary root-input intake, then re-resolved
    # by a fresh app whose ControlPlaneService selects the same owner repo.
    profile_body = {
        **body,
        "intent_id": "ui-intent-r228-e2e-selected-profile",
        "observed_source_ref": selected_profile_observed_ref.model_dump(mode="json"),
        "target_metric": value_profile.outcome,
        "value_data_profile_ref": selected_profile_ref.model_dump(mode="json"),
        "value_data_unit_id": profile_unit_id,
    }
    profile_app = new_reader_app(catalog_source_selection=wdi_source_selection)
    with TestClient(profile_app) as profile_client:
        wait_for_startup_maintenance(profile_app)
        assert (
            profile_app.state.runtime_container.control_service.catalog_serving_source.selection_basis
            == "explicit_path_candidate_only"
        )
        profile_post = profile_client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=profile_body,
        )
        assert profile_post.status_code == 201, profile_post.text
        assert_route_source_bound(profile_app, "produce")
        profile_result = profile_post.json()
        profile_association = profile_result["association"]
        assert profile_association["profile_join_status"] == "joined_candidate"
        assert profile_association["value_data_profile_ref"] == (
            selected_profile_ref.model_dump(mode="json")
        )
        assert profile_association["forecast_profile_member_ref"] is not None
        assert profile_association["assessment"] == "limited"
        assert profile_association["authority_scope"] == "predictive_only"
        assert profile_association["source_time_status"] == "not_established"
        assert profile_association["population_scope_status"] == "not_established"

    profile_fresh_app = new_reader_app(catalog_source_selection=wdi_source_selection)
    with TestClient(profile_fresh_app) as profile_fresh_client:
        wait_for_startup_maintenance(profile_fresh_app)
        profile_get = profile_fresh_client.get(f"/api/v1/runs/{core_run_id}/predictive-calibration")
        assert profile_get.status_code == 200, profile_get.text
        assert_route_source_bound(profile_fresh_app, "read")
        profile_reopened = profile_get.json()
        assert profile_reopened["association_ref"] == profile_result["association_ref"]
        assert profile_reopened["association"] == profile_association
        assert_persisted_evidence_identity(
            profile_fresh_app.state.runtime_api_ctx.store,
            profile_reopened["association"],
        )

    # The profile is valid JSON/CAS/Core content and its source projection is
    # re-opened from the actual local owner, but its per-unit-period aggregate
    # is not producible under the selected owner's current identity rule.
    aggregate_body = {
        **body,
        "intent_id": "ui-intent-i4-owner-aggregate-refusal",
        "observed_source_ref": local_observed_ref.model_dump(mode="json"),
        "target_metric": local_aggregate_profile.outcome,
        "value_data_profile_ref": local_profile_ref.model_dump(mode="json"),
        "value_data_unit_id": "UA",
    }
    local_app = new_reader_app(
        source_repo_root=local_owner.repo_root,
        catalog_source_selection=local_source_selection,
    )
    with TestClient(local_app) as local_client:
        wait_for_startup_maintenance(local_app)
        local_service = local_app.state.runtime_container.control_service
        assert local_service is not None
        assert local_service.catalog_serving_source.selection_basis == (
            "explicit_path_candidate_only"
        )
        local_event_log = local_service._diagnostic_event_log
        local_events_before = local_event_log.list_events(run_id=core_run_id, job_id=job_id)
        local_cas_before = cas_byte_inventory()
        local_request = PredictiveCalibrationRequest.model_validate(aggregate_body)
        local_intent_key = calibration_service.RuntimeOperationIntentKey(
            purpose="run.predictive_calibration.v1",
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            actor_subject_sha256=hashlib.sha256(b"user-fixture").hexdigest(),
            run_id=core_run_id,
            intent_id=aggregate_body["intent_id"],
            body_sha256=calibration_service._operation_body_sha256(
                request=local_request,
                run_id=core_run_id,
                job_id=job_id,
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
                run_manifest_ref=ArtifactRef.model_validate(run["manifest_ref"]),
            ),
        )
        aggregate_refusal = local_client.post(
            f"/api/v1/runs/{core_run_id}/predictive-calibration",
            json=aggregate_body,
        )
        assert_route_source_bound(
            local_app,
            "produce",
            expected_source=local_service.catalog_serving_source,
        )
        assert aggregate_refusal.status_code == 422, aggregate_refusal.text
        assert aggregate_refusal.json()["code"] == "predictive_calibration_value_profile_invalid"
        assert cas_byte_inventory() == local_cas_before
        assert event_receipts(
            local_event_log.list_events(run_id=core_run_id, job_id=job_id)
        ) == event_receipts(local_events_before)
        refused_intent = local_event_log._store.get_runtime_operation_intent(local_intent_key)
        assert refused_intent.status == "unknown"
        assert refused_intent.record is None

        # Removal control: if the call-site shape predicate is omitted, the
        # same actual-source aggregate reaches the candidate consumer. All
        # profile, projection, run-root, source, and status markers remain.
        original_profile_binding = calibration_service.validate_profile_projection_binding

        def validate_without_canonical_shape(**kwargs: Any) -> Any:
            kwargs.pop("require_canonical_owner_profile_shape", None)
            return original_profile_binding(**kwargs)

        unguarded_body = {
            **aggregate_body,
            "intent_id": "ui-intent-i4-owner-aggregate-removal-control",
        }
        with monkeypatch.context() as removed_shape_probe:
            removed_shape_probe.setattr(
                calibration_service,
                "validate_profile_projection_binding",
                validate_without_canonical_shape,
            )
            unguarded_response = local_client.post(
                f"/api/v1/runs/{core_run_id}/predictive-calibration",
                json=unguarded_body,
            )
            assert_route_source_bound(
                local_app,
                "produce",
                expected_source=local_service.catalog_serving_source,
            )
        assert unguarded_response.status_code == 201, unguarded_response.text

    wrong_source = resolve_catalog_serving_source(
        tmp_path,
        selection=None,
        requested_profile=selected_source.catalog_run_profile,
    )
    source_bytes_before_refusals = cas_byte_inventory()
    source_events_before_refusals = event_receipts(
        event_log.list_events(run_id=core_run_id, job_id=job_id)
    )
    wrong_source_app = new_reader_app(catalog_source_selection=wdi_source_selection)
    with TestClient(wrong_source_app) as wrong_source_client:
        wrong_source_service = wrong_source_app.state.runtime_container.control_service
        assert wrong_source_service is not None
        restored_source = wrong_source_service.catalog_serving_source
        assert restored_source is not wrong_source
        with monkeypatch.context() as wrong_source_probe:
            wrong_source_probe.setattr(
                ControlPlaneService,
                "catalog_serving_source",
                property(lambda _self: wrong_source),
            )
            wrong_source_get = wrong_source_client.get(
                f"/api/v1/runs/{core_run_id}/predictive-calibration"
            )
            assert_route_source_bound(
                wrong_source_app,
                "read",
                expected_source=wrong_source,
            )
            assert wrong_source_get.status_code == 409, wrong_source_get.text
            assert wrong_source_get.json()["code"] == (
                "predictive_calibration_value_profile_invalid"
            )
        assert wrong_source_service.catalog_serving_source is restored_source

    missing_source_app = new_reader_app(catalog_source_selection=wdi_source_selection)
    with TestClient(missing_source_app) as missing_source_client:
        missing_source_service = missing_source_app.state.runtime_container.control_service
        assert missing_source_service is not None
        restored_source = missing_source_service.catalog_serving_source
        assert restored_source is not None
        with monkeypatch.context() as missing_source_probe:
            missing_source_probe.setattr(
                ControlPlaneService,
                "catalog_serving_source",
                property(lambda _self: None),
            )
            missing_source_get = missing_source_client.get(
                f"/api/v1/runs/{core_run_id}/predictive-calibration"
            )
            assert_route_source_bound(
                missing_source_app,
                "read",
                expected_source=None,
            )
            assert missing_source_get.status_code == 409, missing_source_get.text
            assert missing_source_get.json()["code"] == (
                "predictive_calibration_catalog_serving_source_context_missing"
            )
        assert missing_source_service.catalog_serving_source is restored_source
    assert cas_byte_inventory() == source_bytes_before_refusals
    assert event_receipts(event_log.list_events(run_id=core_run_id, job_id=job_id)) == (
        source_events_before_refusals
    )


def test_parent_joint_atom_binding_requires_full_source_owned_identity() -> None:
    """Parent N8 scope cannot erase atom id, content hash, or frame identity."""
    from polisyos.runtime.http.routes import runs
    from tests.unit.remediation.test_sim_03 import _request_with_atom_count

    parent_atom = _request_with_atom_count(3).intervention_atoms[0]
    match_source_atom = getattr(runs, "_parent_joint_atom_matches_child_source", lambda *_: False)

    assert match_source_atom(parent_atom, parent_atom)
    for field, foreign_value in (
        ("atom_id", "atom_ffffffffffffffff"),
        ("content_hash", "sha256:" + "f" * 64),
        ("problem_frame_ref", "sha256:" + "f" * 64),
    ):
        child_atom = parent_atom.model_copy(update={field: foreign_value})
        assert not match_source_atom(parent_atom, child_atom), field


def test_parent_joint_request_bridge_refuses_present_malformed_request() -> None:
    """Absent parent request remains absent; a present malformed one cannot vanish."""
    from polisyos.runtime.http.services.control import generation_cycle
    from tests.unit.remediation.test_sim_03 import _request_with_atom_count

    build_requests = getattr(
        generation_cycle,
        "_parent_joint_simulation_requests_by_node",
        lambda _root_ref, _problem: {},
    )
    request = _request_with_atom_count(3)
    problem = SimpleNamespace(
        runtime_hints={"joint_simulation_request": request.model_dump(mode="json")}
    )

    parsed = build_requests("design://root", problem)
    assert parsed["design://root"].model_dump(mode="json") == request.model_dump(mode="json")
    assert build_requests("design://root", SimpleNamespace(runtime_hints={})) == {}
    for supplied in (None, {"world_model_record_ref": "missing-required-fields"}):
        with pytest.raises(ValueError, match="recursive_parent_n5_request_invalid"):
            build_requests(
                "design://root",
                SimpleNamespace(runtime_hints={"joint_simulation_request": supplied}),
            )


def test_parent_joint_member_compiler_uses_one_exact_source_atom_per_child() -> None:
    """Compiler axes come from persisted parent N4 members, never caller tuples."""
    from polisyos.runtime.http.services.control import generation_cycle
    from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems
    from tests.unit.runtime.quality.test_generation_cycle import (
        _controlled_declared_n4_child_inputs,
    )

    problem, source_result = _controlled_declared_n4_child_inputs()
    children = derive_n4_candidate_child_problems(
        problem, source_result, model_id=source_result.model_id
    )
    compile_members = getattr(
        generation_cycle,
        "_compile_parent_joint_n4_atom_members",
        lambda **_kwargs: (),
    )

    atoms = compile_members(
        problem=problem,
        source_result=source_result,
        child_problems=children,
        model_id=source_result.model_id,
        world_model_record_ref=source_result.candidates[0].atom.world_model_record_ref,
    )

    assert len(atoms) == len(children) == 2
    assert tuple(atom.problem_frame_ref for atom in atoms) == (
        source_result.design_problem_ref,
    ) * len(children)
    assert {atom.content_hash for atom in atoms} == {
        atom_hash for child in children for atom_hash in child.source_atom_refs
    }


def test_parent_joint_member_compiler_refuses_ambiguous_group_selection() -> None:
    """A semantic child with multiple parent proposals has no implicit winner."""
    from polisyos.runtime.http.services.control import generation_cycle
    from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems
    from tests.unit.runtime.quality.test_generation_cycle import (
        _controlled_declared_n4_child_inputs,
    )

    problem, source_result = _controlled_declared_n4_child_inputs()
    children = derive_n4_candidate_child_problems(
        problem, source_result, model_id=source_result.model_id
    )
    first, *remaining = children
    duplicated_member = first.__class__(
        problem=first.problem,
        source_result_ref=first.source_result_ref,
        source_atom_refs=(*first.source_atom_refs, first.source_atom_refs[0]),
        semantic_ref=first.semantic_ref,
    )
    compile_members = getattr(
        generation_cycle,
        "_compile_parent_joint_n4_atom_members",
        lambda **_kwargs: (),
    )

    with pytest.raises(
        ValueError, match="recursive_parent_n5_source_member_selection_not_established"
    ):
        compile_members(
            problem=problem,
            source_result=source_result,
            child_problems=(duplicated_member, *remaining),
            model_id=source_result.model_id,
            world_model_record_ref=source_result.candidates[0].atom.world_model_record_ref,
        )


@pytest.mark.parametrize("atom_count", [3, 4])
def test_parent_n8_dto_consumes_complete_atom_source_bindings(
    monkeypatch: pytest.MonkeyPatch,
    atom_count: int,
) -> None:
    """Parent-scope markers cannot survive a missing or foreign child atom binding."""
    from copy import deepcopy
    from math import comb

    from pydantic import ValidationError

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.contracts.runtime import (
        RunCandidateSimulationN5Observation,
        RunCandidateSimulationN8ChildSourceBinding,
    )
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.routes.runs import (
        _n5_interaction_evidence_projection,
        _n5_interaction_scope_fields,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from tests.unit.remediation.test_sim_03 import _request_with_atom_count

    request = _request_with_atom_count(atom_count).model_copy(
        update={"replications": 3, "seed": 41}
    )

    def stable_step(state, params):
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, "firm_survival": {"mean": 0.25}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(stable_step))
    result = JointSimulationHorizonController().run(request)
    evidence = _n5_interaction_evidence_projection(result)
    assert evidence is not None
    assert evidence["numeric_interaction"] == "non_additive"
    assert evidence["numeric_interaction_basis"] == ("finite_checked_model_point_estimate_only")
    assert evidence["interaction_sampling_status"] == "estimated"
    assert evidence["checked_interaction_orders"] == ([1, 2, 3] if atom_count == 3 else [1, 2])
    if atom_count == 4:
        assert "aggregate_order_3_plus_not_identified" in (
            result.feedback_classification.limitations
        )
    scope = _n5_interaction_scope_fields(result)
    joint_effect = 0.25
    single_effect = joint_effect - request.baseline_state["firm_survival"]
    expected_pair_effect = joint_effect - 2 * single_effect
    expected_residual = (
        joint_effect
        - len(request.intervention_atoms) * single_effect
        - comb(len(request.intervention_atoms), 2) * expected_pair_effect
    )
    expected_seeds = [41, 42, 43]
    assert scope["replication_seeds"] == tuple(expected_seeds)
    expected_pairs = {
        frozenset((left.intervention_id, right.intervention_id))
        for index, left in enumerate(request.intervention_atoms)
        for right in request.intervention_atoms[index + 1 :]
    }
    assert len(evidence["interaction_terms"]) == len(expected_pairs)
    assert {frozenset(term["atom_ids"]) for term in evidence["interaction_terms"]} == expected_pairs
    for term in evidence["interaction_terms"]:
        summary = term["replication_sampling_by_step"]["0"]
        assert summary["status"] == "estimated"
        assert summary["seeds"] == expected_seeds
        assert summary["samples"] == [
            {"seed": seed, "value": expected_pair_effect} for seed in expected_seeds
        ]
        assert summary["mean"] == pytest.approx(expected_pair_effect)
        assert summary["standard_error"] == pytest.approx(0.0)
    residual_summary = evidence["higher_order_residual_sampling"][result.selected_outcomes[0]]["0"]
    assert residual_summary["status"] == "estimated"
    assert residual_summary["seeds"] == expected_seeds
    assert residual_summary["samples"] == [
        {"seed": seed, "value": expected_residual} for seed in expected_seeds
    ]
    assert residual_summary["mean"] == pytest.approx(expected_residual)
    assert residual_summary["standard_error"] == pytest.approx(0.0)
    parent_ref = request.intervention_atoms[0].problem_frame_ref

    def artifact_ref(kind: str, digit: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id="sha256:" + digit * 64,
            kind=kind,
            media_type="application/json",
        )

    child_refs = tuple(f"child://{index}" for index, _atom in enumerate(request.intervention_atoms))
    bindings = tuple(
        RunCandidateSimulationN8ChildSourceBinding(
            child_node_ref=child_ref,
            child_design_problem_ref=atom.problem_frame_ref,
            n4_source_ref=artifact_ref("runtime.quality.n4_candidate_scenario_source", "a"),
            context_job_ref=artifact_ref("runtime.quality.cycle_substrate_context_job", "b"),
            n5_input_ref=artifact_ref("runtime.quality.candidate_simulation_n5_input", "c"),
            n5_result_ref=artifact_ref("polisyos.runtime.joint_simulation_result", "d"),
            profile_config_ref="runtime-config:candidate-simulation/profile@sha256:" + "e" * 64,
            profile_selection_ref="sha256:" + "f" * 64,
            source_intervention_id=atom.intervention_id,
            source_atom_id=atom.atom_id,
            source_atom_content_hash=atom.content_hash,
            source_problem_frame_ref=atom.problem_frame_ref,
            parent_atom_id=atom.atom_id,
            parent_atom_content_hash=atom.content_hash,
        )
        for child_ref, atom in zip(child_refs, request.intervention_atoms, strict=True)
    )
    payload = {
        "node_ref": "design-problem://parent",
        "design_problem_ref": parent_ref,
        "atom_ids": tuple(result.atom_ids),
        "selected_outcomes": tuple(result.selected_outcomes),
        "status": "joint_simulated",
        "n5_interaction_evidence": evidence,
        **scope,
        "world_model_record_content_hash": result.world_model_record_content_hash,
        "n8_numeric_interaction": evidence["numeric_interaction"],
        "n8_numeric_interaction_basis": evidence["numeric_interaction_basis"],
        "n8_interaction_sampling_status": evidence["interaction_sampling_status"],
        "n8_status": "value_pending_n8",
        "n8_authority_blockers": ("joint_interaction_rule_not_established",),
        "n8_joint_request_content_hash": gy_content_hash(request.model_dump(mode="json")),
        "n8_joint_world_model_record_ref": request.world_model_record_ref,
        "n8_joint_outcome_units": dict.fromkeys(result.selected_outcomes, "synthetic_score"),
        "n8_joint_parent_atom_ids": tuple(atom.atom_id for atom in request.intervention_atoms),
        "n8_joint_parent_atom_content_hashes": tuple(
            atom.content_hash for atom in request.intervention_atoms
        ),
        "n8_parent_child_refs": child_refs,
        "n8_parent_child_source_bindings": bindings,
        "n8_joint_scope_status": "resolved",
        "n8_joint_value_limitation_code": "joint_interaction_rule_not_established",
    }
    typed = RunCandidateSimulationN5Observation.model_validate(payload)
    assert typed.n8_status == "value_pending_n8"
    assert typed.n8_numeric_interaction == evidence["numeric_interaction"]
    assert typed.n8_joint_value_limitation_code == "joint_interaction_rule_not_established"

    candidate_diagnostic = deepcopy(payload)
    candidate_diagnostic.update(
        {
            "n8_joint_scope_status": "not_established",
            "n8_joint_scope_limitation_code": "parent_joint_coupling_evidence_not_established",
            "n8_joint_value_limitation_code": None,
            "n8_authority_blockers": ("parent_joint_coupling_evidence_not_established",),
            "n8_candidate_joint_selection_status": "resolved",
            "n8_candidate_joint_selection_content_hash": gy_content_hash(
                {
                    "request_hash": gy_content_hash(request.model_dump(mode="json")),
                    "atom_hashes": [atom.content_hash for atom in request.intervention_atoms],
                }
            ),
            "n8_candidate_parent_atom_ids": tuple(
                atom.atom_id for atom in request.intervention_atoms
            ),
            "n8_candidate_parent_atom_content_hashes": tuple(
                atom.content_hash for atom in request.intervention_atoms
            ),
            "n8_candidate_parent_intervention_ids": tuple(result.atom_ids),
            "n8_candidate_parent_child_refs": child_refs,
            "n8_candidate_joint_selection_limitation_code": None,
            "n8_candidate_member_basis": "hypothetical_all_unique_n4_source_members",
            "n8_source_candidate_relationship": "alternatives",
            "n8_policy_composition_status": "not_established",
            "n8_policy_composition_limitation_code": (
                "n4_source_candidates_are_alternatives_not_authored_compound_design"
            ),
            "n8_child_to_parent_refinement_status": "not_established",
            "n8_child_to_parent_refinement_limitation_code": (
                "child_to_parent_refinement_rule_not_established"
            ),
        }
    )
    diagnostic = RunCandidateSimulationN5Observation.model_validate(candidate_diagnostic)
    assert diagnostic.n8_candidate_joint_selection_status == "resolved"
    assert diagnostic.n8_policy_composition_status == "not_established"
    assert diagnostic.n8_child_to_parent_refinement_status == "not_established"

    legacy_selection = deepcopy(candidate_diagnostic)
    legacy_selection.update(
        {
            "n8_candidate_member_basis": "not_established",
            "n8_source_candidate_relationship": "not_established",
            "n8_policy_composition_limitation_code": (
                "legacy_selection_receipt_has_no_composition_basis"
            ),
            "n8_child_to_parent_refinement_limitation_code": (
                "legacy_selection_receipt_has_no_refinement_basis"
            ),
        }
    )
    legacy_diagnostic = RunCandidateSimulationN5Observation.model_validate(legacy_selection)
    assert legacy_diagnostic.n8_candidate_joint_selection_status == "resolved"
    assert legacy_diagnostic.n8_candidate_member_basis == "not_established"
    assert legacy_diagnostic.n8_policy_composition_status == "not_established"

    missing_basis = deepcopy(candidate_diagnostic)
    missing_basis["n8_candidate_member_basis"] = None
    with pytest.raises(
        ValidationError,
        match="run_n8_candidate_joint_selection_binding_incomplete",
    ):
        RunCandidateSimulationN5Observation.model_validate(missing_basis)

    false_composition = deepcopy(candidate_diagnostic)
    false_composition["n8_policy_composition_status"] = "resolved"
    with pytest.raises(ValidationError):
        RunCandidateSimulationN5Observation.model_validate(false_composition)

    missing_binding = deepcopy(typed.model_dump(mode="json"))
    missing_binding["n8_parent_child_source_bindings"].pop()
    with pytest.raises(ValidationError, match="run_n8_joint_scope_binding_incomplete"):
        RunCandidateSimulationN5Observation.model_validate(missing_binding)

    foreign_source_atom = deepcopy(typed.model_dump(mode="json"))
    foreign_source_atom["n8_parent_child_source_bindings"][0]["source_atom_content_hash"] = (
        "sha256:" + "0" * 64
    )
    with pytest.raises(ValidationError, match="run_n8_joint_scope_binding_incomplete"):
        RunCandidateSimulationN5Observation.model_validate(foreign_source_atom)


def test_joint_interaction_candidate_intent_has_no_caller_axes() -> None:
    """The HTTP intent requests a candidate diagnostic without supplying its axes."""
    from pydantic import ValidationError

    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.runtime.http.services.control.generation_cycle import (
        _build_parent_joint_candidate_request,
    )
    from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest
    from tests.unit.remediation.test_sim_03 import _request_with_atom_count

    intent = "n4_unique_parent_source_members.v1"
    base_simulation_request = _request_with_atom_count(3)
    legacy_request_dump = base_simulation_request.model_dump(mode="json")
    assert "candidate_intent" not in legacy_request_dump
    candidate_scope = {
        "candidate_intent": intent,
        "member_basis": "hypothetical_all_unique_n4_source_members",
        "source_candidate_relationship": "alternatives",
        "composition_status": "not_established",
        "composition_limitation_code": (
            "n4_source_candidates_are_alternatives_not_authored_compound_design"
        ),
        "child_to_parent_refinement_status": "not_established",
        "child_to_parent_refinement_limitation_code": (
            "child_to_parent_refinement_rule_not_established"
        ),
    }
    scoped_request = JointSimulationRequest.model_validate(
        {
            **legacy_request_dump,
            **candidate_scope,
        }
    )
    assert {
        key: scoped_request.model_dump(mode="json")[key] for key in candidate_scope
    } == candidate_scope
    partial_scope = {
        **legacy_request_dump,
        "candidate_intent": intent,
    }
    with pytest.raises(
        ValidationError, match="joint_simulation_candidate_diagnostic_scope_invalid"
    ):
        JointSimulationRequest.model_validate(partial_scope)

    request = NaturalLanguageRunRequest(
        request="Evaluate the combined candidate intervention.",
        joint_interaction_candidate_intent=intent,
    )
    payload = request.model_dump(mode="json")
    assert payload["joint_interaction_candidate_intent"] == intent
    assert not {
        "atom_ids",
        "outcome_variable",
        "seed",
        "replications",
        "profile_ref",
    }.intersection(payload)

    with pytest.raises(
        DesignProblemAuthorityError,
        match="recursive_parent_joint_candidate_intent_not_established",
    ):
        _build_parent_joint_candidate_request(
            candidate_intent=None,
            problem=None,  # type: ignore[arg-type]
            source_result=None,
            source_ref=None,  # type: ignore[arg-type]
            child_problems=(),
            child_node_refs=(),
            model_id="",
            handoff=None,  # type: ignore[arg-type]
            admission_owner=None,  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        NaturalLanguageRunRequest.model_validate(
            {
                "request": "Evaluate the combined candidate intervention.",
                "joint_interaction_candidate_intent": "caller_supplied_axes",
                "selected_atom_ids": ["caller-created-axis"],
            }
        )
