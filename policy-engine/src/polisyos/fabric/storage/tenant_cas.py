"""Tenant-scoped CAS wrapper with namespace isolation and storage quota checks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.security.db_backend import validate_tenant_id
from polisyos.core.security.quota_registry import TenantQuotaRegistry

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.artifacts.store import ExportReport, ImportReport
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.core.security.tenant_quota import TenantQuotaLimits


def tenant_scoped_cas_root(root: str | Path, tenant_id: str) -> Path:
    """Resolve the isolated CAS root for one tenant."""
    validate_tenant_id(tenant_id)
    return Path(root) / "tenants" / tenant_id


def infer_tenant_id_from_cas_root(root: str | Path) -> str | None:
    """Infer tenant_id from a CAS root path if it is already tenant-scoped."""
    parts = Path(root).parts
    for index, part in enumerate(parts[:-1]):
        if part != "tenants":
            continue
        candidate = parts[index + 1]
        try:
            validate_tenant_id(candidate)
        except ValueError:
            continue
        return candidate
    return None


class TenantScopedCAS:
    """Small compatibility wrapper around ``ArtifactStore`` for one tenant namespace."""

    def __init__(
        self,
        root: str | Path,
        *,
        tenant_id: str,
        quota_registry: TenantQuotaRegistry | None = None,
        quota_limits: TenantQuotaLimits | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.root = tenant_scoped_cas_root(root, tenant_id)
        self._config = ArtifactStoreConfig(backend="filesystem", root=str(self.root))
        self._cas = build_artifact_store(self._config, metrics=metrics, tracer=tracer)
        self._quota_registry = quota_registry or TenantQuotaRegistry()
        if quota_limits is not None:
            self._quota_registry.set_limits(tenant_id, quota_limits)
        self._quota = self._quota_registry.get_enforcer(tenant_id)
        self._quota.state.storage_bytes_used = self._directory_size(self.root)

    def artifact_store_config(self) -> ArtifactStoreConfig:
        """Export declarative config so worker/bootstrap paths can rebuild this store."""
        return self._config.model_copy(deep=True)

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef:
        """Persist bytes inside the tenant namespace with quota enforcement."""
        estimated_delta = len(data) + 4_096
        self._quota.check_storage_delta(estimated_delta)
        before_size = self._directory_size(self.root)
        ref = self._cas.put_bytes(data, opts)
        after_size = self._directory_size(self.root)
        delta = max(0, after_size - before_size)
        if delta > 0:
            self._quota.record_storage_delta(delta)
        return ref

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Persist canonical JSON payload inside the tenant namespace."""
        spec = canon_spec or CanonSpec()
        payload = to_canonical_bytes(obj, spec)
        estimated_delta = len(payload) + 4_096
        self._quota.check_storage_delta(estimated_delta)
        before_size = self._directory_size(self.root)
        ref = self._cas.put_json(obj, opts=opts, canon_spec=spec)
        after_size = self._directory_size(self.root)
        delta = max(0, after_size - before_size)
        if delta > 0:
            self._quota.record_storage_delta(delta)
        return ref

    def has(self, artifact_id: ArtifactID) -> bool:
        return bool(self._cas.has(artifact_id))

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        return bytes(self._cas.get_bytes(artifact_id))

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        return self._cas.get_manifest(artifact_id)

    def get_paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        return cast("tuple[Path, Path]", cast("Any", self._cas).get_paths(artifact_id))

    def iter_artifact_ids(self) -> list[ArtifactID]:
        return cast("list[ArtifactID]", self._cas.iter_artifact_ids())

    def export_subgraph(self, artifact_ids: list[ArtifactID], output_path: Path) -> ExportReport:
        return cast(
            "ExportReport",
            cast("Any", self._cas).export_subgraph(artifact_ids, output_path),
        )

    def import_subgraph(self, archive_path: Path, *, verify_integrity: bool = True) -> ImportReport:
        before_size = self._directory_size(self.root)
        report = cast(
            "ImportReport",
            cast("Any", self._cas).import_subgraph(
                archive_path,
                verify_integrity=verify_integrity,
            ),
        )
        after_size = self._directory_size(self.root)
        delta = max(0, after_size - before_size)
        if delta > 0:
            self._quota.check_storage_delta(delta)
            self._quota.record_storage_delta(delta)
        return report

    @staticmethod
    def _directory_size(root: Path) -> int:
        if not root.exists():
            return 0
        total = 0
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
        return total


def resolve_cas_store(
    root: str | Path,
    *,
    tenant_id: str | None = None,
    quota_registry: TenantQuotaRegistry | None = None,
    quota_limits: TenantQuotaLimits | None = None,
    metrics: MetricsRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
) -> ArtifactStore | TenantScopedCAS:
    """Resolve either the shared CAS or an isolated tenant-specific namespace."""
    if tenant_id is None:
        return cast(
            "ArtifactStore",
            build_artifact_store(
                ArtifactStoreConfig(backend="filesystem", root=str(Path(root))),
                metrics=metrics,
                tracer=tracer,
            ),
        )
    return TenantScopedCAS(
        root,
        tenant_id=tenant_id,
        quota_registry=quota_registry,
        quota_limits=quota_limits,
        metrics=metrics,
        tracer=tracer,
    )


__all__ = [
    "TenantScopedCAS",
    "infer_tenant_id_from_cas_root",
    "resolve_cas_store",
    "tenant_scoped_cas_root",
]
