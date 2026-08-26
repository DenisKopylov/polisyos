from __future__ import annotations

import os
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
from polisyos.common.async_tools import get_shared_executor
from polisyos.core import canon
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import IngestRequest, NaturalLanguageRunRequest
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.tenant_context import (
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.execution_policy import (
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
)
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import (
    ControlRegistryProviders,
    resolve_control_registry_providers,
)
from polisyos.runtime.http.services.task_runner import TaskRunner
from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
from polisyos.runtime.quality.generation_cycle import N4GenerationPort
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    build_default_recursive_generation_cycle_controller,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService

try:  # pragma: no cover - optional runtime dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


class _NoOpRetrievalService:
    def list_promotion_candidates(self):
        return []


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


def _build_control_service(tmp_path) -> ControlPlaneService:
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    return ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=_build_registry_providers(),
    )


def test_runtime_api_defaults_core_runs_root_to_cas_runs(tmp_path) -> None:
    cas_root = tmp_path / ".polisyos" / "cas"

    app = create_runtime_api_app(cas_root=cas_root)

    assert app.state.runtime_api_ctx.core_runs_root == cas_root / "runs"
    assert app.state.runtime_container.config.core_runs_root == cas_root / "runs"
    cache_root = tmp_path / "runtime-http-cache"
    assert os.environ["POLISYOS_CACHE_HOME"] == cache_root.as_posix()
    catalog_graph = app.state.runtime_container.control_registry_providers.gy_catalog_graph
    assert catalog_graph is not None
    assert catalog_graph._store._db_path.is_relative_to(cache_root)


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
    store = FileSystemCAS(tmp_path / ".polisyos")
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
async def test_direct_recursive_http_and_replay_share_one_owner_context_ref(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _budget,
        _CgfGenerationPort,
        _problem,
    )

    app = create_runtime_api_app(cas_root=tmp_path / ".polisyos" / "cas")
    from polisyos.runtime.quality import promotion_sequence as promotion_sequence_module

    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = app.state.runtime_container.promotion_runtime
    problem = _problem(f"http_shared_open_world_context_{uuid4().hex}")
    recursive = build_default_recursive_generation_cycle_controller(promotion_runtime=runtime)
    assert recursive._promotion_runtime is runtime

    recursive_budget = RecursiveCycleBudget(
        max_depth=0,
        max_nodes=1,
        min_cycles_per_leaf=1,
        max_cycles_per_leaf=1,
    )

    async def compile_problem(**kwargs):
        del kwargs
        return problem

    class _CanonicalFixtureN4Port(N4GenerationPort):
        def __init__(self) -> None:
            super().__init__(model_id="fixture-model")
            self._delegate = _CgfGenerationPort()

        async def __call__(self, problem, *, cycle_index):
            return await self._delegate(problem, cycle_index=cycle_index)

    def build_controller(**kwargs):
        assert kwargs["promotion_runtime"] is runtime
        return recursive

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )
    monkeypatch.setattr(
        generation_cycle_service,
        "build_default_recursive_generation_cycle_controller",
        build_controller,
    )
    compiled = await generation_cycle_service.compile_and_run_recursive_generation_cycle(
        raw_request=problem.nl_provenance.raw_request,
        context={},
        model_name="fixture-model",
        compiler_gateway=object(),  # type: ignore[arg-type]
        budget_state=_budget(),
        recursive_budget=recursive_budget,
        root_n4_generation_port=_CanonicalFixtureN4Port(),
        promotion_runtime=runtime,
        repo_root=REPO_ROOT,
    )

    leaf = compiled.recursive_run.leaf_nodes[0]
    assert leaf.cycle_run is not None
    assert leaf.cycle_run.promotion_port.receipts == ()
    assert leaf.cycle_run.promotion_port.reason == (
        "epoch_validity_refused:policy_admission_missing"
    )

    subject_kind = "runtime.promotion.pre_n9_epoch_validity_subject"
    subject_ids = tuple(
        artifact_id
        for artifact_id in runtime.store.iter_artifact_ids()
        if runtime.store.get_manifest(artifact_id).kind == subject_kind
    )
    assert len(subject_ids) == 1
    subject = __import__(
        "polisyos.core.contracts.decision_validity",
        fromlist=["PreN9EpochValiditySubjectStatement"],
    ).PreN9EpochValiditySubjectStatement.model_validate_json(
        runtime.store.get_bytes(subject_ids[0])
    )
    member = runtime.context_repository.resolve_bound_member(
        bound_member_ref=subject.bound_member_ref
    )
    aggregate = runtime.context_repository.resolve_verified(
        context_ref=member.statement.aggregate_context_ref
    )
    assert aggregate.context_ref == subject.owner_query_context_ref
    replayed_epoch = runtime.resolve_verified_epoch_query(bound_member_ref=subject.bound_member_ref)
    assert replayed_epoch.candidate.occurrence_ref == subject.candidate_occurrence_ref
    assert replayed_epoch.qualification_failure_codes == ("policy_admission_missing",)


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
        launch = await service.launch_nl_run(
            NaturalLanguageRunRequest(
                request="Check tenant propagation",
                llm_model="simulated-qwen",
            ),
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        payload = service._load_payload_ref(str(record.payload_ref))

        assert payload["tenant_id"] == "tenant-fixture"
        assert payload["cell_id"] == "cell-fixture"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_process_nl_job_enters_persisted_tenant_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from polisyos.runtime.quality import promotion_sequence as promotion_sequence_module
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _budget,
        _CgfGenerationPort,
        _problem,
    )

    service = _build_control_service(tmp_path)
    try:
        monkeypatch.setattr(
            promotion_sequence_module,
            "_legacy_policy_promotion_callers",
            lambda repo_root: (),
        )
        problem = _problem(f"worker_epoch_strangle_{uuid4().hex}")

        async def compile_problem(**kwargs):
            del kwargs
            return problem

        class _CanonicalFixtureN4Port(N4GenerationPort):
            def __init__(self) -> None:
                super().__init__(model_id="fixture-model")
                self._delegate = _CgfGenerationPort()

            async def __call__(self, problem, *, cycle_index):
                return await self._delegate(problem, cycle_index=cycle_index)

        monkeypatch.setattr(
            generation_cycle_service,
            "build_design_problem_from_nl_request",
            compile_problem,
        )
        recursive_budget = RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        )
        compiled_fixture = (
            await generation_cycle_service.compile_and_run_recursive_generation_cycle(
                raw_request=problem.nl_provenance.raw_request,
                context={},
                model_name="fixture-model",
                compiler_gateway=object(),  # type: ignore[arg-type]
                budget_state=_budget(),
                recursive_budget=recursive_budget,
                root_n4_generation_port=_CanonicalFixtureN4Port(),
                promotion_runtime=service._promotion_runtime,
                repo_root=REPO_ROOT,
            )
        )

        launch = await service.launch_nl_run(
            NaturalLanguageRunRequest(
                request=problem.nl_provenance.raw_request,
                llm_model="simulated-qwen",
            ),
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        async def _compile_worker_request(**kwargs):
            assert get_current_tenant_id_or_none() == "tenant-fixture"
            assert get_current_cell_id() == "cell-fixture"
            assert kwargs["raw_request"] == problem.nl_provenance.raw_request
            assert kwargs["promotion_runtime"] is service._promotion_runtime
            assert service._promotion_runtime.store is service._artifact_store
            return compiled_fixture

        monkeypatch.setattr(
            generation_cycle_service,
            "compile_and_run_recursive_generation_cycle",
            _compile_worker_request,
        )

        service._process_control_job(record)

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None
        assert completed.state == "completed"
        assert completed.progress["promotion_refusal_reasons"] == [
            "epoch_validity_refused:policy_admission_missing"
        ]
        compiled_ref = ArtifactID.model_validate(
            completed.progress["compiled_recursive_generation_cycle_ref"]
        )
        assert service._artifact_store.get_manifest(compiled_ref).kind == (
            "runtime.compiled_recursive_generation_cycle"
        )
        persisted = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(service._artifact_store.get_bytes(compiled_ref))
        )
        leaf = persisted.recursive_run.leaf_nodes[0]
        assert leaf.cycle_run is not None
        assert leaf.cycle_run.promotion_port.reason == (
            "epoch_validity_refused:policy_admission_missing"
        )
    finally:
        service.close()


def _build_registry_providers() -> ControlRegistryProviders:
    source_profile = SimpleNamespace(
        profile_id="fixture_profile",
        display_name="Fixture Profile",
        description="fixture source profile",
        connector_family="fixture.family",
        base_url="https://example.test/api",
        auth_policy="none",
        tags=("fixture",),
        source_organization="Fixture Org",
        estimated_datasets=1,
    )
    binding_profile = SimpleNamespace(
        profile_id="fixture_binding",
        display_name="Fixture Binding",
        description="fixture binding profile",
        schema_family="time_series",
        strategy="strict",
        rules=[{"name": "metric"}],
        expected_columns=["metric"],
        tags=("fixture",),
    )
    model_profile = SimpleNamespace(
        profile_id="fixture_model",
        display_name="Fixture Model",
        description="fixture llm profile",
        provider="openai",
        model_id="gpt-5-mini",
        base_url="https://api.example.test/v1",
        tags=("fixture",),
        capabilities=["chat"],
        input_cost_per_mtoken_usd=0.1,
        output_cost_per_mtoken_usd=0.2,
        enabled=True,
    )
    connector_entry = SimpleNamespace(
        metadata=SimpleNamespace(
            fully_qualified_id="fixture.family.connector",
            namespace="fixture.family",
            version="1.0.0",
            observed_latency_ms=12,
        ),
        known_datasets={"fixture.dataset"},
        loaded=True,
        last_health_check=datetime.now(UTC),
        short_id="fixture.family.connector",
    )

    return ControlRegistryProviders(
        connectors=SimpleNamespace(query_entries=lambda *args, **kwargs: [connector_entry]),
        source_profiles=SimpleNamespace(
            get=lambda profile_id: source_profile if profile_id == "fixture_profile" else None,
            list_all=lambda: [source_profile],
            list_by_family=lambda connector_family: (
                [source_profile] if connector_family == "fixture.family" else []
            ),
        ),
        binding_profiles=SimpleNamespace(
            get=lambda profile_id: binding_profile if profile_id == "fixture_binding" else None,
            list_all=lambda: [binding_profile],
        ),
        model_profiles=SimpleNamespace(list_all=lambda: [model_profile]),
    )


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
    from polisyos.scientist.orchestration.llm.profiles.registry import ModelProfileRegistry

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
        def __init__(self, *, curated_dir, cas_root, providers=None, **kwargs) -> None:
            del curated_dir, cas_root, kwargs
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

    retrieval_providers = seen["providers"]
    assert retrieval_providers.registry is providers.connectors
    assert retrieval_providers.profiles is providers.source_profiles
    assert retrieval_providers.tracer is service._tracer
    assert retrieval_providers.metrics is service._metrics
    service.close()


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
        assert app.state._control_service._registry_providers is providers
