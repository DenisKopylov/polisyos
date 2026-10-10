from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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


@pytest.mark.asyncio
async def test_runtime_container_exposes_one_decision_validity_owner(tmp_path) -> None:
    app = create_runtime_api_app(cas_root=tmp_path / ".polisyos" / "cas")

    await app.state.runtime_container.startup(app)
    try:
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
async def test_served_recursive_projection_rejects_grafted_receipt_for_blocked_n6(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The served projection gates receipts on owner N6 status before parsing them."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        PendingN8ValuePort,
    )
    from polisyos.runtime.quality.public_export import PublicExportRedactionError
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

    with pytest.raises(PublicExportRedactionError) as blocked_error:
        await compile_served_projection("blocked")
    assert blocked_error.value.code == ("generation_cycle_blocked_before_n9_cannot_supply_receipt")
    assert parsed_payloads == []
    assert projection_inputs == []

    compiled = await compile_served_projection("stop")
    assert isinstance(compiled, generation_cycle_service.CompiledRecursiveGenerationCycleRun)
    stop_cycle = compiled.recursive_run.leaf_nodes[0].cycle_run
    assert stop_cycle is not None
    assert stop_cycle.terminal_status == "completed"
    assert stop_cycle.cycles[-1].voi_decision.next_action == "stop"
    assert parsed_payloads == [grafted_payload]
    assert len(projection_inputs) == 1
    assert projection_inputs[0]["receipt"] is parsed_receipt
    n9_source = projection_inputs[0]["n9_source"]
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
    import json
    from types import SimpleNamespace

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.data_forge.domains.catalog.registry import (
        CatalogSourceRegistryEntry,
        CatalogSourceRegistrySpec,
    )
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.fabric.retrieval.service import RetrievalService

    curated = tmp_path / "curated"
    curated.mkdir()
    (curated / "data_contracts.json").write_text(
        json.dumps(
            {
                "contracts": [
                    {
                        "metric_id": "recorded_owner_metric",
                        "source_column": "value",
                        "jurisdiction": "UA",
                        "granularity": "annual",
                    }
                ]
            }
        )
    )
    (curated / "source_bindings.json").write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "metric_id": "recorded_owner_metric",
                        "connector_id": "static_csv",
                        "dataset_id": "recorded_owner.csv",
                        "trust": 0.9,
                    }
                ]
            }
        )
    )
    canonical = catalog_api.build_production_data_contract_catalog_graph(
        production_root=curated,
        graph_root=tmp_path / "canonical_catalog",
    )
    canonical.close()
    source_registry = CatalogSourceRegistrySpec(
        sources=(
            CatalogSourceRegistryEntry(
                source_id="static_csv",
                family="controlled_test_fixture",
                wave="T",
                endpoint="file://controlled-test-fixture",
                connector_id="static_csv",
                execution_tier="fetchable",
                run_lane="catalog",
            ),
        )
    )
    monkeypatch.setattr(
        catalog_api,
        "load_catalog_source_registry",
        lambda: source_registry,
    )
    hint_dir = tmp_path / "empty_curated_hints"
    hint_dir.mkdir()
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(hint_dir))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(
        "polisyos.runtime.quality.substrate_registry.default_substrate_catalog_paths",
        lambda _root: SimpleNamespace(l1_dcat_path=tmp_path / "canonical_catalog/catalog.duckdb"),
    )
    monkeypatch.setattr(
        catalog_api,
        "default_acquisition_overlay_path",
        lambda _root: tmp_path / "absent_overlay.duckdb",
    )
    graph = None
    retrieval = None
    if injected:
        graph = catalog_api.DatasetCatalogGraph(
            tmp_path / "canonical_catalog/catalog.duckdb",
            tmp_path / "canonical_catalog",
        )
        retrieval = RetrievalService(
            curated_dir=tmp_path / "catalog_only",
            cas_root=tmp_path / "cas",
            dataset_catalog=graph,
        )
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        artifact_store=FileSystemCAS(tmp_path / "cas"),
        retrieval_service=retrieval,
        registry_providers=resolve_control_registry_providers(),
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        ),
    )
    selected = service._retrieval._dataset_catalog
    assert isinstance(selected, catalog_api.DatasetCatalogGraph)
    if injected:
        assert selected is graph
        assert service._retrieval is retrieval
        assert service._retrieval_catalog is None
    else:
        assert selected is service._retrieval_catalog
        assert service._retrieval.artifact_store is service._artifact_store
    # The concrete catalog resolves the declared metric; this test exercises
    # service construction/lifetime, not the separate fetch-to-N9 falsifier.
    response = service.data_resolve(
        DataResolveRequest(
            data_needs=[DataNeed(metric="recorded_owner_metric")],
            mode="fastlane",
            allow_explore_fallback=False,
            catalog_run_profile="prod_full",
        )
    )
    assert response.fetch_plans
    with pytest.raises(RuntimeHTTPError) as unselected_profile:
        service.data_resolve(
            DataResolveRequest(
                data_needs=[DataNeed(metric="recorded_owner_metric")],
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

        def reject_publication(**_kwargs):
            pytest.fail("candidate-only N4 proposal reached generation publication")

        def reject_n6(**_kwargs):
            pytest.fail("candidate-only N4 proposal entered the recursive N6 owner")

        monkeypatch.setattr(service, "resolve_generation_value_choices", reject_s8)
        monkeypatch.setattr(service, "_publish_generation_run", reject_publication)
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
        assert "manifest_ref" not in completed.progress
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
        assert service._promotion_runtime.store is service._artifact_store
    finally:
        service.close()


async def _run_controlled_simulate_only_job_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    *,
    proposal_source_persistence_failure: bool = False,
    local_sibling_mechanism_witness: bool = False,
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
        _configured_procurement_profile,
        _controlled_procurement_recording,
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
    problem = _current_compiler_problem(recording)
    outcome_variable = problem.outcome_of_interest.target_variable
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
    profile, model_declaration = _configured_procurement_profile(
        recorded_problem=problem,
        artifact_store=store,
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
    )
    assert profile.profile_selection_ref == cycle_job_profile_selection_ref(problem)
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        service = _build_control_service(
            tmp_path,
            artifact_store=store,
            candidate_simulation_profiles=(profile,),
            candidate_simulation_model_declarations=(model_declaration,),
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
    verified_scope_observations = []
    n5_port_observations = []
    n5_engine_requests = []
    compiler_calls = []
    compiled_runs = []
    n4_organ_runs = []
    n4_port_attempts = []
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
        return context

    monkeypatch.setattr(RunContext, "start", classmethod(record_core_start))

    original_n4_port = N4GenerationPort.__call__

    async def record_n4_port(port, problem_for_cycle, *, cycle_index):
        execution_order.append(("N4_ENTER", ""))
        n4_port_attempts.append((problem_for_cycle, cycle_index))
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

    def record_resolve(owner, ref, *, problem, verified_nl_job_scope=None):
        assert owner._store is service._artifact_store
        assert get_current_access_scope_or_none() is None
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
                        verified_nl_job_scope=changed_scope,
                    )
        artifact = original_resolve(
            owner,
            ref,
            problem=problem,
            verified_nl_job_scope=verified_nl_job_scope,
        )
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
            assert len(n4_port_attempts) == 1

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
        # Child-owner replay now independently re-admits the exact profile
        # after resolving its issued job scope, so admission count may exceed
        # artifact replay count by the number of routed children.
        assert len(admission_observations) >= len(owner_replays) >= 2
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
        assert n4_port_attempts[0][0] is problem
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
            assert observed.input_record.materialization.value == 1
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
        assert selected_v1_source.k_ref_limitation_code == ("historical_l2_confidence_withheld")
        assert selected_v1_source.l2_confidence_vintage is not None
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
        assert selected_intervention.params == {profile.rule.parameter_id: 1}
        assert candidate.atom.target_world_slots == (profile.rule.target_world_slot,)
        assert candidate.atom.direct_effect_bundle.params == selected_intervention.params
        assert input_record.materialization.operator_kind == selected_intervention.kind
        assert input_record.materialization.parameter_id == profile.rule.parameter_id
        assert input_record.materialization.value == 1
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
        assert set(selected_ncm.endogenous_vars) == {
            model_declaration.target_world_slot,
            model_declaration.outcome_variable,
        }
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
        assert target_baseline == model_declaration.target_baseline == 0.0
        assert outcome_baseline == model_declaration.outcome_baseline == 0.0
        assert model_declaration.outcome_variable == outcome_variable
        assert model_declaration.outcome_unit_id == model_declaration.target_unit_id

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
        assert expected_quantity == pytest.approx(0.5, abs=1e-12)
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


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
@pytest.mark.asyncio
async def test_fresh_run_details_get_projects_the_persisted_candidate_simulation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A fresh authorized GET exposes the exact candidate result already persisted by CAS."""
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
            assert source_v1.k_ref_limitation_code == "historical_l2_confidence_withheld"
            assert source_v1.l2_confidence_vintage is not None
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

            compiled_manifest = store.get_manifest(ArtifactRef.model_validate(compiled_refs[0]))
            assert compiled_manifest.tenant_context is not None
            assert compiled_manifest.tenant_context.tenant_id == "tenant-fixture"
            assert compiled_manifest.tenant_context.cell_id == "cell-fixture"
            n5_ref = ArtifactRef.model_validate(n5_observation["simulation_result_ref"])
            n5_manifest = store.get_manifest(n5_ref)
            assert n5_manifest.tenant_context is not None
            assert n5_manifest.tenant_context.tenant_id == "tenant-fixture"
            assert n5_manifest.tenant_context.cell_id == "cell-fixture"

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

    fixture = await _run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
        local_sibling_mechanism_witness=True,
    )
    core_run_id = str(fixture.job.progress["core_run_id"])
    compiled_payload = json.loads(fixture.compiled_payload)
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
    successful_cycle = successful_node["cycle_run"]
    assert successful_cycle["schema_version"] == "policyos.runtime.generation_cycle_controller.v5"
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

    missing_lineage = json.loads(json.dumps(successful_cycle))
    del missing_lineage["cycles"][0]["simulation"]["candidate_simulation_context_job_ref"]
    assert validate_generation_cycle_run_history(missing_lineage)

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
