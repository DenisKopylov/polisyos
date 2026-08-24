"""Typed runtime container and lifecycle helpers for the HTTP API surface."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.runtime.http.access_audit import RuntimeDataAccessAuditTrail
from polisyos.runtime.http.dependencies import RuntimeApiContext, build_runtime_api_context
from polisyos.runtime.http.mutation_policy import build_runtime_mutation_services
from polisyos.runtime.http.resilience import build_runtime_opa_async_guard
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import (
    ControlRegistryProviders,
    resolve_control_registry_providers,
)
from polisyos.runtime.http.services.review_collaboration import ReviewCollaborationHub
from polisyos.runtime.quality.chronology_custody import (
    build_production_epoch_anchor_custody_provider,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from polisyos.core import contracts as core_contracts
    from polisyos.runtime.http.execution_policy import ResolvedExecutionPolicy
    from polisyos.runtime.http.security import RuntimeSecurityConfig

LifecycleStatus = Literal["created", "starting", "ready", "stopping", "stopped", "failed"]


@dataclass(frozen=True)
class RuntimeContainerOverrides:
    """Optional dependency overrides used by tests or alternate embeddings."""

    runtime_api_context: RuntimeApiContext | None = None
    review_collaboration_hub: ReviewCollaborationHub | None = None
    control_service: ControlPlaneService | None = None
    runtime_metrics: Any | None = None
    runtime_tracer: Any | None = None
    runtime_access_audit: RuntimeDataAccessAuditTrail | None = None
    runtime_rate_limiter: Any | None = None
    runtime_idempotency_store: Any | None = None
    runtime_mutation_audit: Any | None = None
    runtime_review_opa_guard: Any | None = None
    control_registry_providers: ControlRegistryProviders | None = None


@dataclass(frozen=True)
class RuntimeContainerConfig:
    """Factory inputs required to assemble the runtime service graph."""

    cas_root: Path
    core_runs_root: Path
    max_preview_bytes: int = 64 * 1024
    lineage_max_depth: int = 64
    lineage_max_nodes: int = 2000
    allow_unscoped_artifacts: bool = False
    artifact_redaction_hooks: dict[str, Any] | None = None
    metrics_factory: Callable[[], Any] | None = None
    tracer_factory: Callable[[], Any] | None = None
    overrides: RuntimeContainerOverrides = field(default_factory=RuntimeContainerOverrides)


@dataclass
class RuntimeLifecycleState:
    """Mutable lifecycle and dependency-health snapshot for the runtime container."""

    status: LifecycleStatus = "created"
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_error: str | None = None

    def mark(self, status: LifecycleStatus, *, error: str | None = None) -> None:
        self.status = status
        if status == "ready":
            self.started_at = datetime.now(UTC)
            self.stopped_at = None
            self.last_error = None
            return
        if status in {"failed", "stopped"}:
            self.stopped_at = datetime.now(UTC)
        if error:
            self.last_error = error


@dataclass
class RuntimeServiceContainer:
    """Own runtime-scoped services and expose startup/shutdown/health hooks."""

    config: RuntimeContainerConfig
    deployment_policy: ResolvedExecutionPolicy
    runtime_security: RuntimeSecurityConfig
    runtime_metrics: Any
    runtime_tracer: Any
    runtime_api_context: RuntimeApiContext
    review_collaboration_hub: ReviewCollaborationHub
    runtime_access_audit: RuntimeDataAccessAuditTrail
    runtime_rate_limiter: Any
    runtime_idempotency_store: Any
    runtime_mutation_audit: Any
    runtime_review_opa_guard: Any
    epoch_anchor_custody_provider: core_contracts.EpochAnchorCustodyProvider
    control_registry_providers: ControlRegistryProviders
    control_service: ControlPlaneService | None = None
    lifecycle: RuntimeLifecycleState = field(default_factory=RuntimeLifecycleState)

    @classmethod
    def build(
        cls,
        *,
        config: RuntimeContainerConfig,
        deployment_policy: ResolvedExecutionPolicy,
        runtime_security: RuntimeSecurityConfig,
    ) -> RuntimeServiceContainer:
        """Construct a container with lazy startup for heavyweight services."""
        overrides = config.overrides
        runtime_metrics = overrides.runtime_metrics or (config.metrics_factory or get_metrics)()
        runtime_tracer = overrides.runtime_tracer or (config.tracer_factory or get_tracer)()
        runtime_api_context = overrides.runtime_api_context or build_runtime_api_context(
            cas_root=config.cas_root,
            core_runs_root=config.core_runs_root,
            max_preview_bytes=config.max_preview_bytes,
            lineage_max_depth=config.lineage_max_depth,
            lineage_max_nodes=config.lineage_max_nodes,
            allow_unscoped_artifacts=config.allow_unscoped_artifacts,
            artifact_redaction_hooks=config.artifact_redaction_hooks,
            metrics=runtime_metrics,
            tracer=runtime_tracer,
        )
        runtime_rate_limiter, runtime_idempotency_store, runtime_mutation_audit = (
            build_runtime_mutation_services(
                cas_root=config.cas_root,
                metrics=runtime_metrics,
            )
        )
        control_registry_providers = (
            overrides.control_registry_providers or _resolve_default_control_registry_providers()
        )
        return cls(
            config=config,
            deployment_policy=deployment_policy,
            runtime_security=runtime_security,
            runtime_metrics=runtime_metrics,
            runtime_tracer=runtime_tracer,
            runtime_api_context=runtime_api_context,
            review_collaboration_hub=(
                overrides.review_collaboration_hub or ReviewCollaborationHub()
            ),
            runtime_access_audit=(
                overrides.runtime_access_audit
                or RuntimeDataAccessAuditTrail(
                    path=config.cas_root / "runtime" / "audit" / "access.jsonl"
                )
            ),
            runtime_rate_limiter=overrides.runtime_rate_limiter or runtime_rate_limiter,
            runtime_idempotency_store=(
                overrides.runtime_idempotency_store or runtime_idempotency_store
            ),
            runtime_mutation_audit=(overrides.runtime_mutation_audit or runtime_mutation_audit),
            runtime_review_opa_guard=(
                overrides.runtime_review_opa_guard or build_runtime_opa_async_guard()
            ),
            epoch_anchor_custody_provider=(build_production_epoch_anchor_custody_provider()),
            control_registry_providers=control_registry_providers,
            control_service=overrides.control_service,
        )

    def install(self, app: Any) -> None:
        """Expose the container and legacy-compatible aliases on `app.state`."""
        app.state.runtime_container = self
        self._bind_legacy_state(app)

    async def startup(self, app: Any) -> None:
        """Transition the container to ready and initialize lazy services."""
        self.lifecycle.mark("starting")
        try:
            if self.control_service is None:
                self.control_service = ControlPlaneService(
                    cas_root=self.config.cas_root,
                    core_runs_root=self.config.core_runs_root,
                    metrics=self.runtime_metrics,
                    tracer=self.runtime_tracer,
                    artifact_store=self.runtime_api_context.store,
                    async_artifact_store=self.runtime_api_context.async_store,
                    registry_providers=self.control_registry_providers,
                )
            self._bind_legacy_state(app)
            self.lifecycle.mark("ready")
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            self.lifecycle.mark("failed", error=str(exc))
            raise

    async def shutdown(self, app: Any) -> None:
        """Close owned resources in dependency order."""
        self.lifecycle.mark("stopping")
        error: str | None = None
        try:
            await _close_maybe_async(self.review_collaboration_hub)
            runtime_store = getattr(self.runtime_api_context, "store", None)
            if runtime_store is not None and hasattr(runtime_store, "close"):
                runtime_store.close()
            if self.control_service is not None and hasattr(self.control_service, "close"):
                self.control_service.close()
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            error = str(exc)
            self.lifecycle.mark("failed", error=error)
            raise
        finally:
            self._bind_legacy_state(app)
            if error is None:
                self.lifecycle.mark("stopped")

    def health_payload(self) -> dict[str, Any]:
        """Return a serializable lifecycle/dependency snapshot for health endpoints."""
        dependencies = {
            "runtime_api_context": _resource_state(self.runtime_api_context),
            "review_collaboration_hub": _resource_state(self.review_collaboration_hub),
            "control_plane_service": _resource_state(self.control_service, pending_ok=True),
            "runtime_metrics": _resource_state(self.runtime_metrics),
            "runtime_tracer": _resource_state(self.runtime_tracer),
            "runtime_access_audit": _resource_state(self.runtime_access_audit),
            "runtime_rate_limiter": _resource_state(self.runtime_rate_limiter),
            "runtime_idempotency_store": _resource_state(self.runtime_idempotency_store),
            "runtime_mutation_audit": _resource_state(self.runtime_mutation_audit),
        }
        return {
            "status": self.lifecycle.status,
            "started_at": (
                self.lifecycle.started_at.isoformat()
                if self.lifecycle.started_at is not None
                else None
            ),
            "stopped_at": (
                self.lifecycle.stopped_at.isoformat()
                if self.lifecycle.stopped_at is not None
                else None
            ),
            "last_error": self.lifecycle.last_error,
            "dependency_graph": {
                "runtime_api_context": [
                    "artifact_store",
                    "run_index",
                    "timeline",
                    "debug",
                    "feedback",
                    "fabric",
                    "lineage",
                    "compare",
                    "temporal",
                    "scenarios",
                    "artifacts",
                    "analysis",
                ],
                "control_plane_service": ["runtime_metrics", "runtime_tracer"],
                "mutation_policy": [
                    "runtime_rate_limiter",
                    "runtime_idempotency_store",
                    "runtime_mutation_audit",
                ],
                "review_collaboration_hub": [],
                "runtime_access_audit": [],
            },
            "dependencies": dependencies,
        }

    def _bind_legacy_state(self, app: Any) -> None:
        if self.control_service is not None:
            self.runtime_api_context.scenarios.bind_scenario_head_store(
                self.control_service.scenario_head_store,
            )
        app.state.runtime_api_ctx = self.runtime_api_context
        app.state.review_collaboration_hub = self.review_collaboration_hub
        app.state.execution_policy = self.deployment_policy
        app.state.runtime_security = self.runtime_security
        app.state.allow_fixture_identity = self.runtime_security.allow_fixture_identity
        app.state.runtime_metrics = self.runtime_metrics
        app.state.runtime_tracer = self.runtime_tracer
        app.state.runtime_access_audit = self.runtime_access_audit
        app.state.runtime_rate_limiter = self.runtime_rate_limiter
        app.state.runtime_idempotency_store = self.runtime_idempotency_store
        app.state.runtime_mutation_audit = self.runtime_mutation_audit
        app.state.runtime_review_opa_guard = self.runtime_review_opa_guard
        app.state._control_service = self.control_service


def get_runtime_container(subject: Any) -> RuntimeServiceContainer | None:
    """Return the installed runtime container from a request/websocket/app."""
    app = getattr(subject, "app", subject)
    state = getattr(app, "state", None)
    container = getattr(state, "runtime_container", None)
    return container if isinstance(container, RuntimeServiceContainer) else None


def resolve_runtime_api_context(subject: Any) -> RuntimeApiContext | None:
    """Resolve the public runtime API context from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_api_context if container is not None else None


def resolve_control_service(subject: Any) -> ControlPlaneService | None:
    """Resolve the public control-plane service from the runtime container."""
    container = get_runtime_container(subject)
    if container is None:
        return None
    return (
        container.control_service
        if isinstance(container.control_service, ControlPlaneService)
        else None
    )


def resolve_review_collaboration_hub(subject: Any) -> ReviewCollaborationHub | None:
    """Resolve the review collaboration hub from the runtime container."""
    container = get_runtime_container(subject)
    return container.review_collaboration_hub if container is not None else None


def resolve_runtime_metrics(subject: Any) -> Any | None:
    """Resolve runtime metrics provider from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_metrics if container is not None else None


def resolve_runtime_tracer(subject: Any) -> Any | None:
    """Resolve runtime tracer provider from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_tracer if container is not None else None


def resolve_runtime_access_audit(subject: Any) -> RuntimeDataAccessAuditTrail | None:
    """Resolve the data-access audit trail from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_access_audit if container is not None else None


def resolve_runtime_security(subject: Any) -> RuntimeSecurityConfig | None:
    """Resolve runtime security config from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_security if container is not None else None


def resolve_runtime_rate_limiter(subject: Any) -> Any | None:
    """Resolve runtime mutation/live-stream rate limiter from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_rate_limiter if container is not None else None


def resolve_runtime_review_opa_guard(subject: Any) -> Any | None:
    """Resolve runtime OPA async guard from the runtime container."""
    container = get_runtime_container(subject)
    return container.runtime_review_opa_guard if container is not None else None


def _resolve_default_control_registry_providers() -> ControlRegistryProviders:
    return resolve_control_registry_providers()


async def _close_maybe_async(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        await result


def _resource_state(resource: Any, *, pending_ok: bool = False) -> dict[str, str]:
    if resource is None:
        return {"status": "pending" if pending_ok else "missing"}
    return {
        "status": "ready",
        "type": type(resource).__name__,
    }


__all__ = [
    "RuntimeContainerConfig",
    "RuntimeContainerOverrides",
    "RuntimeLifecycleState",
    "RuntimeServiceContainer",
    "get_runtime_container",
    "resolve_control_service",
    "resolve_review_collaboration_hub",
    "resolve_runtime_access_audit",
    "resolve_runtime_api_context",
    "resolve_runtime_metrics",
    "resolve_runtime_rate_limiter",
    "resolve_runtime_review_opa_guard",
    "resolve_runtime_security",
    "resolve_runtime_tracer",
]
