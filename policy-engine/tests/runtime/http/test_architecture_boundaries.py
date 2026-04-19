from __future__ import annotations

import ast
from pathlib import Path

import pytest
from polisyos_tests_runtime_http_conftest import build_runtime_api_env

from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
)
from polisyos.core.artifacts.backends.config import (
    build_artifact_store as real_build_artifact_store,
)

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / "src" / "polisyos" / "runtime"
FABRIC_BOUNDARY_SOURCES = (
    REPO_ROOT / "src" / "polisyos" / "fabric" / "catalog",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "retrieval",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "ingestion.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "ingestion_providers.py",
)
ALLOWED_PROVIDER_BOOTSTRAP_FILES = {
    REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "services" / "control_registry_providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "catalog" / "providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "ingestion_providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "retrieval" / "providers.py",
}
DEFAULT_HOOK_BOUNDARY_FILES = (
    REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "services" / "control_registry_providers.py",
    REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "services" / "control.py",
    REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "cell_router_middleware.py",
    REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "jwt_auth_middleware.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "catalog" / "providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "ingestion_providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "retrieval" / "providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "world" / "providers.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "_connector_bridge.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "__init__.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "federation" / "composer.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "data_plane" / "streaming.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "data_plane" / "modes.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "resilience" / "retry.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "llm" / "traced_client.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "observability" / "decorators.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "observability" / "tracer.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "security" / "identity.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "security" / "authz.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "security" / "tee_middleware.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "security" / "audit_sink.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "security" / "audit_verifier.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "security" / "sbom.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "artifacts" / "store.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "artifacts" / "backends" / "s3_store.py",
    REPO_ROOT / "src" / "polisyos" / "core" / "artifacts" / "backends" / "gcs_store.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "observability.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "resilience" / "fallback.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "resilience" / "circuit_breaker.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "resilience" / "rate_limiter.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "cache" / "_store_core.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "cache" / "prefetch.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "cache" / "proxy.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "types" / "_units_registry.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "types" / "dimensions.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "types" / "_units_base.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "quality" / "freshness.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "agent" / "informed_critic.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "agent" / "knowledge_base.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "engine" / "operational_monitoring.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "engine" / "metrics_otel.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "engine" / "metrics.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "error_semantics.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "governance" / "pipeline.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "llm" / "budget_enforcer.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "compute" / "runner.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "compute" / "advanced_methods.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "quality.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "components_bridge.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "_registry_lifecycle.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "transform" / "_common.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "connectors" / "transform" / "pipeline.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "nodes" / "builtins" / "simulate" / "run_simulation.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "agent" / "_drafter_passes.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "agent" / "_drafter_orchestrator.py",
    REPO_ROOT / "src" / "polisyos" / "scientist" / "search" / "controller.py",
    REPO_ROOT / "src" / "polisyos" / "scholar" / "freshness.py",
    REPO_ROOT / "src" / "polisyos" / "fabric" / "data_plane" / "quarantine.py",
)


def _iter_runtime_sources() -> list[Path]:
    return sorted(path for path in RUNTIME_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _iter_fabric_provider_boundary_sources() -> list[Path]:
    paths: set[Path] = set()
    for source in FABRIC_BOUNDARY_SOURCES:
        if source.is_dir():
            paths.update(
                path for path in source.rglob("*.py") if "__pycache__" not in path.parts
            )
        elif source.is_file():
            paths.add(source)
    return sorted(paths)


def _default_hook_violations(path: Path) -> list[str]:
    relative_path = path.relative_to(REPO_ROOT).as_posix()

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.function_stack: list[str] = []
            self.violations: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            hook_name: str | None = None
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get_instance":
                hook_name = "get_instance"
            elif isinstance(func, ast.Name) and func.id in {"get_tracer", "get_metrics"}:
                hook_name = func.id
            if hook_name is not None:
                owner = self.function_stack[-1] if self.function_stack else "<module>"
                if not owner.startswith("_default_"):
                    self.violations.append(
                        f"{relative_path}:{node.lineno}: {hook_name} used in {owner}"
                    )
            self.generic_visit(node)

    visitor = _Visitor()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return visitor.violations


def test_runtime_never_imports_concrete_cas_write_implementation() -> None:
    violations: list[str] = []

    for path in _iter_runtime_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "polisyos.core.artifacts.store":
                imported = {alias.name for alias in node.names}
                if "FileSystemCAS" in imported:
                    violations.append(f"{relative_path}:{node.lineno}: import FileSystemCAS")
                if "PutOptions" in imported:
                    violations.append(f"{relative_path}:{node.lineno}: import PutOptions")
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "FileSystemCAS":
                violations.append(f"{relative_path}:{node.lineno}: construct FileSystemCAS(...)")
            elif isinstance(func, ast.Attribute) and func.attr == "FileSystemCAS":
                violations.append(f"{relative_path}:{node.lineno}: construct *.FileSystemCAS(...)")

    assert not violations, (
        "runtime must depend on artifact store/write protocols, not concrete CAS "
        "implementation details:\n" + "\n".join(violations)
    )


def test_runtime_routes_do_not_reach_legacy_container_state_directly() -> None:
    violations: list[str] = []
    forbidden_fragments = {
        "state.runtime_api_ctx": "use container resolver helpers for runtime API context",
        'getattr(request.app.state, "runtime_api_ctx"': (
            "use container resolver helpers for runtime API context"
        ),
        'getattr(websocket.app.state, "runtime_api_ctx"': (
            "use container resolver helpers for runtime API context"
        ),
        "state._control_service": "use container resolver helpers for control service",
        'getattr(request.app.state, "_control_service"': (
            "use container resolver helpers for control service"
        ),
        'getattr(request.app.state, "runtime_metrics"': (
            "use container resolver helpers for runtime observability dependencies"
        ),
        'getattr(websocket.app.state, "runtime_rate_limiter"': (
            "use container resolver helpers for runtime mutation/live-stream guards"
        ),
        'getattr(websocket.app.state, "runtime_review_opa_guard"': (
            "use container resolver helpers for runtime OPA guards"
        ),
        'getattr(request.app.state, "allow_fixture_identity"': (
            "use container resolver helpers for runtime security settings"
        ),
        'getattr(websocket.app.state, "allow_fixture_identity"': (
            "use container resolver helpers for runtime security settings"
        ),
        'getattr(websocket.app.state, "runtime_security"': (
            "use container resolver helpers for runtime security settings"
        ),
    }

    for path in _iter_runtime_sources():
        if path.name == "container.py":
            continue
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        for fragment, guidance in forbidden_fragments.items():
            if fragment in text:
                violations.append(f"{relative_path}: {fragment} ({guidance})")

    assert not violations, (
        "runtime sources should consume public lifecycle providers rather than "
        "legacy app.state aliases:\n" + "\n".join(violations)
    )


def test_runtime_control_paths_do_not_resolve_registry_singletons_inline() -> None:
    violations: list[str] = []
    forbidden_fragments = {
        "SourceProfileRegistry.get_instance(": (
            "inject ControlRegistryProviders instead of inline source-profile singleton access"
        ),
        "BindingProfileRegistry.get_instance(": (
            "inject ControlRegistryProviders instead of inline binding-profile singleton access"
        ),
        "ConnectorRegistry.get_instance(": (
            "inject ControlRegistryProviders instead of inline connector-registry singleton access"
        ),
        "ModelProfileRegistry.get_instance(": (
            "inject ControlRegistryProviders instead of inline model-profile singleton access"
        ),
    }

    for path in _iter_runtime_sources():
        if path.name in {"container.py", "control_registry_providers.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        for fragment, guidance in forbidden_fragments.items():
            if fragment in text:
                violations.append(f"{relative_path}: {fragment} ({guidance})")

    assert not violations, (
        "runtime control paths should depend on injectable registry providers "
        "rather than inline singleton access:\n" + "\n".join(violations)
    )


def test_fabric_provider_boundaries_limit_singleton_and_observability_defaults() -> None:
    violations: list[str] = []
    forbidden_fragments = {
        "ConnectorRegistry.get_instance(": (
            "use provider bundles or explicit bootstrap helpers instead of inline connector singletons"
        ),
        "SourceProfileRegistry.get_instance(": (
            "use provider bundles or explicit bootstrap helpers instead of inline source-profile singletons"
        ),
        "get_tracer()": (
            "use provider bundles or explicit bootstrap helpers instead of inline tracer defaults"
        ),
        "get_metrics()": (
            "use provider bundles or explicit bootstrap helpers instead of inline metrics defaults"
        ),
    }

    for path in _iter_fabric_provider_boundary_sources():
        if path in ALLOWED_PROVIDER_BOOTSTRAP_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        for fragment, guidance in forbidden_fragments.items():
            if fragment in text:
                violations.append(f"{relative_path}: {fragment} ({guidance})")

    assert not violations, (
        "fabric catalog/retrieval/ingestion boundaries should consume injected providers "
        "and keep singleton or observability defaults isolated to bootstrap-only provider "
        "modules:\n" + "\n".join(violations)
    )


def test_boundary_default_hooks_remain_isolated_to_default_helpers() -> None:
    violations: list[str] = []

    for path in DEFAULT_HOOK_BOUNDARY_FILES:
        violations.extend(_default_hook_violations(path))

    assert not violations, (
        "singleton and observability bootstrap hooks should only appear inside "
        "_default_* helper functions in boundary modules:\n" + "\n".join(violations)
    )


def test_runtime_control_hot_path_uses_shared_executor_bridge_not_asyncio_to_thread() -> None:
    control_source = (
        REPO_ROOT
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "control.py"
    ).read_text(encoding="utf-8")

    assert "asyncio.to_thread(" not in control_source, (
        "runtime control hot paths should reuse run_blocking_async/shared executor "
        "rather than ad hoc asyncio.to_thread offloads"
    )


def test_runtime_container_lifecycle_keeps_legacy_state_bindings_consistent(tmp_path) -> None:
    if TestClient is None:  # pragma: no cover
        pytest.skip("fastapi test client is not installed")

    env = build_runtime_api_env(tmp_path, include_test_client=False)
    app = env["app"]
    container = app.state.runtime_container

    assert app.state.runtime_api_ctx is container.runtime_api_context
    assert app.state.review_collaboration_hub is container.review_collaboration_hub
    assert app.state._control_service is container.control_service

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        lifecycle = response.json()["lifecycle"]

        assert lifecycle["status"] == "ready"
        assert lifecycle["dependencies"]["control_plane_service"]["status"] == "ready"
        assert "control_plane_service" in lifecycle["dependency_graph"]
        assert container.lifecycle.status == "ready"
        assert container.control_service is not None
        assert app.state._control_service is container.control_service
        assert app.state.runtime_api_ctx is container.runtime_api_context
        assert app.state.review_collaboration_hub is container.review_collaboration_hub

    assert container.lifecycle.status == "stopped"


def test_runtime_container_and_control_service_share_artifact_store(tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    app = env["app"]
    container = app.state.runtime_container
    control_service = app.state._control_service

    assert control_service is not None
    assert control_service._artifact_store is container.runtime_api_context.store
    assert control_service._owns_artifact_store is False


def test_runtime_api_context_passes_explicit_providers_into_artifact_store_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http import dependencies

    captured: list[tuple[object | None, object | None]] = []
    metrics = object()
    tracer = object()

    def _capturing_factory(
        config: ArtifactStoreConfig,
        *,
        metrics=None,
        tracer=None,
    ):
        captured.append((metrics, tracer))
        return real_build_artifact_store(config, metrics=metrics, tracer=tracer)

    monkeypatch.setattr(dependencies, "build_artifact_store", _capturing_factory)
    context = dependencies.build_runtime_api_context(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / "runs",
        metrics=metrics,
        tracer=tracer,
    )

    assert captured == [(metrics, tracer)]
    store = context.store
    close = getattr(store, "close", None)
    if callable(close):
        close()
