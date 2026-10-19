"""Tenant-scoped CAS wrapper with namespace isolation and storage quota checks."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts import CanonInfo
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
)
from polisyos.core.canon import CanonSpec, CanonViolation
from polisyos.core.security import TenantQuotaRegistry, validate_tenant_id
from polisyos.core.security.quota_enforcer import QuotaAccountingError

_TENANT_STORAGE_LOCKS: dict[str, threading.RLock] = {}
_TENANT_STORAGE_LOCKS_GUARD = threading.Lock()


def _tenant_storage_lock(root: Path) -> threading.RLock:
    """Return the in-process lock paired with one tenant CAS root file lock."""
    key = str(root.resolve())
    with _TENANT_STORAGE_LOCKS_GUARD:
        return _TENANT_STORAGE_LOCKS.setdefault(key, threading.RLock())


class _TenantQuotaAdmission:
    """Count exact absent final CAS members against one locked root snapshot."""

    def __init__(self, root: Path, quota: QuotaEnforcer) -> None:
        self._root = root
        self._quota = quota

    def admit(self, members: Sequence[_CASStorageMember]) -> None:
        unique: dict[str, tuple[str, int]] = {}
        for member in members:
            relative = member.relative_path
            if (
                not isinstance(relative, PurePosixPath)
                or relative.is_absolute()
                or ".." in relative.parts
                or relative.parts[:2] != ("artifacts", "sha256")
                or len(relative.parts) < 5
            ):
                raise QuotaAccountingError("CAS quota plan contains an unsafe member path")
            digest = member.sha256.removeprefix("sha256:")
            if (
                type(member.byte_size) is not int
                or member.byte_size < 0
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise QuotaAccountingError("CAS quota plan contains invalid content metadata")
            name = relative.as_posix()
            identity = (digest, member.byte_size)
            previous = unique.get(name)
            if previous is not None and previous != identity:
                raise QuotaAccountingError("CAS quota plan has conflicting duplicate members")
            unique[name] = identity

        delta = 0
        for name, (expected_digest, expected_size) in unique.items():
            relative = PurePosixPath(name)
            path = self._root.joinpath(*relative.parts)
            current = self._root
            for component in relative.parts[:-1]:
                current = current / component
                if current.is_symlink():
                    raise QuotaAccountingError("CAS quota target crosses a symlink")
                if current.exists() and not current.is_dir():
                    raise QuotaAccountingError("CAS quota target parent is not a directory")
            if path.is_symlink():
                raise QuotaAccountingError("CAS quota target is a symlink")
            try:
                details = path.lstat()
            except FileNotFoundError:
                delta += expected_size
                continue
            if not stat.S_ISREG(details.st_mode):
                raise QuotaAccountingError("CAS quota target is not a regular file")
            if details.st_size != expected_size or self._file_sha256(path) != expected_digest:
                raise QuotaAccountingError("CAS quota target conflicts with its content-bound plan")

        if delta:
            self._quota.check_storage_delta(delta)

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from polisyos.core.artifacts import ExportReport, ImportReport
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore, _CASStorageMember
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.core.security import TenantQuotaLimits
    from polisyos.core.security.quota_enforcer import QuotaEnforcer


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


@dataclass(frozen=True, slots=True)
class TenantSidecarScope:
    """Bind an artifact-store root to the explicit tenant sidecar location.

    ``base_root`` is always the exact root expected by the artifact-store
    factory. Sidecar locality follows the explicit tenant identity and root
    mode; no tenant identity is inferred from filesystem path components.
    """

    base_root: Path
    tenant_id: str | None
    store_root_is_tenant_scoped: bool = False

    def __post_init__(self) -> None:
        base_root = Path(self.base_root)
        object.__setattr__(self, "base_root", base_root)
        if self.tenant_id is not None:
            validate_tenant_id(self.tenant_id)
        if not isinstance(self.store_root_is_tenant_scoped, bool):
            raise ValueError("tenant_sidecar_root_mode_invalid")
        if self.store_root_is_tenant_scoped and self.tenant_id is None:
            raise ValueError("tenant_scoped_store_requires_tenant_id")

    @classmethod
    def for_base_root(
        cls,
        base_root: str | Path,
        tenant_id: str | None,
    ) -> TenantSidecarScope:
        """Build sidecar paths from a known unscoped base root and tenant."""
        return cls(base_root=Path(base_root), tenant_id=tenant_id)

    @classmethod
    def from_current_context(cls, base_root: str | Path) -> TenantSidecarScope:
        """Bind a base root to the authenticated tenant in the current context."""
        from polisyos.core.security import get_current_tenant_id_or_none

        return cls.for_base_root(base_root, get_current_tenant_id_or_none())

    @classmethod
    def for_pre_scoped_store_root(
        cls,
        store_root: str | Path,
        tenant_id: str,
    ) -> TenantSidecarScope:
        """Bind a root explicitly configured as tenant-local already.

        This supports existing callers that deliberately pass a root produced
        by ``tenant_scoped_cas_root``. The caller supplies the identity; the
        helper never attempts to recover it from the path.
        """
        root = Path(store_root)
        return cls(
            base_root=root,
            tenant_id=tenant_id,
            store_root_is_tenant_scoped=True,
        )

    @property
    def sidecar_root(self) -> Path:
        """Return this invocation's cursor/cache sidecar root."""
        if self.tenant_id is None or self.store_root_is_tenant_scoped:
            return self.base_root
        return tenant_scoped_cas_root(self.base_root, self.tenant_id)

    @property
    def cursor_index_root(self) -> Path:
        """Return the exact local root for cursor SQLite indices."""
        return self.sidecar_root

    def cache_namespace(self, logical_namespace: str) -> str:
        """Return a validated connector-cache namespace under this scope."""
        namespace = Path(logical_namespace)
        if (
            namespace.is_absolute()
            or ".." in namespace.parts
            or not namespace.parts
            or namespace.parts[0] == "tenants"
        ):
            raise ValueError("ingestion_cache_namespace_invalid")
        prefix = self.sidecar_root.relative_to(self.base_root)
        return (prefix / namespace).as_posix() if prefix.parts else namespace.as_posix()


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
        self._quota.reconcile_storage_usage(self._directory_size(self.root))

    def artifact_store_config(self) -> ArtifactStoreConfig:
        """Export declarative config so worker/bootstrap paths can rebuild this store."""
        return self._config.model_copy(deep=True)

    @contextmanager
    def _storage_mutation(self) -> Iterator[None]:
        """Serialize quota admission across threads and processes for this root."""
        lock = _tenant_storage_lock(self.root)
        lock_path = self.root / "artifacts" / "ownership" / "transactions" / "tenant-quota.lock"
        with lock:
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(lock_path, flags, 0o600)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise QuotaAccountingError("tenant quota lock is not a regular file")
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                self._quota.reconcile_storage_usage(self._directory_size(self.root))
                cas = cast("Any", self._cas)
                cas._storage_admission = _TenantQuotaAdmission(self.root, self._quota)
                try:
                    yield
                finally:
                    cas._storage_admission = None
                    self._quota.reconcile_storage_usage(self._directory_size(self.root))
            finally:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

    def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Persist bytes with quota admission before any final CAS member is visible."""
        if type(return_selected_profile) is not bool:
            raise TypeError("return_selected_profile must be a bool")
        if return_selected_profile:
            from polisyos.core.artifacts.protocol import _require_return_selected_profile_writer

            _require_return_selected_profile_writer(self._cas, "put_bytes")
        with self._storage_mutation():
            return (
                self._cas.put_bytes(data, opts, return_selected_profile=True)
                if return_selected_profile
                else self._cas.put_bytes(data, opts)
            )

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Persist canonical JSON under the same exact-member admission boundary."""
        if type(return_selected_profile) is not bool:
            raise TypeError("return_selected_profile must be a bool")
        if return_selected_profile:
            from polisyos.core.artifacts.protocol import _require_return_selected_profile_writer

            _require_return_selected_profile_writer(self._cas, "put_json")
        spec = canon_spec or CanonSpec()
        if opts.canon is not None and opts.canon != CanonInfo.from_spec(spec):
            raise CanonViolation(
                "canon metadata must match the canonicalization spec used for encoding"
            )
        with self._storage_mutation():
            return (
                self._cas.put_json(obj, opts=opts, canon_spec=spec, return_selected_profile=True)
                if return_selected_profile
                else self._cas.put_json(obj, opts=opts, canon_spec=spec)
            )

    def has(self, artifact_id: ArtifactID) -> bool:
        return bool(self._cas.has(artifact_id))

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        return bytes(self._cas.get_bytes(artifact_id))

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        return self._cas.get_manifest(artifact_id)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        return self._cas.iter_artifact_ids()

    def export_subgraph(self, artifact_ids: list[ArtifactID], output_path: Path) -> ExportReport:
        return cast(
            "ExportReport",
            cast("Any", self._cas).export_subgraph(artifact_ids, output_path),
        )

    def import_subgraph(self, archive_path: Path, *, verify_integrity: bool = True) -> ImportReport:
        """Import a complete staged generation under one aggregate quota admission."""
        with self._storage_mutation():
            return cast(
                "ImportReport",
                cast("Any", self._cas).import_subgraph(
                    archive_path,
                    verify_integrity=verify_integrity,
                ),
            )

    @staticmethod
    def _directory_size(root: Path) -> int:
        """Measure regular materialized blob, manifest, and signature members only."""
        cas_root = root / "artifacts" / "sha256"
        for component in (root, root / "artifacts", cas_root):
            if component.is_symlink():
                raise QuotaAccountingError("CAS storage census crosses a symlink")
        if not cas_root.exists():
            return 0
        if not cas_root.is_dir():
            raise QuotaAccountingError("CAS storage census root is not a directory")
        total = 0
        for path in cas_root.rglob("*"):
            details = path.lstat()
            if stat.S_ISLNK(details.st_mode):
                raise QuotaAccountingError("CAS storage census found a symlink")
            if stat.S_ISDIR(details.st_mode):
                continue
            if not stat.S_ISREG(details.st_mode):
                raise QuotaAccountingError("CAS storage census found a special file")
            total += details.st_size
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
        return build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(Path(root))),
            metrics=metrics,
            tracer=tracer,
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
    "TenantSidecarScope",
    "infer_tenant_id_from_cas_root",
    "resolve_cas_store",
    "tenant_scoped_cas_root",
]
