"""Write-through caching store: local FileSystemCAS + remote ArtifactStore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.logger import get_logger
from polisyos.core.canon.canon_json import CanonSpec

from .._integrity_ops import ArtifactIntegrityError
from .._manifest_lifecycle import ManifestLifecycle
from ..ids import ArtifactID
from ..manifest import ArtifactManifest, ArtifactRef, artifact_reference_parts
from ..protocol import ArtifactStore
from ..store import PutOptions, VerificationReport

logger = get_logger(__name__)

CacheDegradationPolicy = Literal["warn", "raise"]

if TYPE_CHECKING:
    from .config import ArtifactStoreConfig


def _artifact_label(artifact_id: ArtifactID) -> str:
    return str(getattr(artifact_id, "hex", artifact_id))


class CachingArtifactStore:
    """Composes a local CAS (fast) with a remote store (durable).

    * **Reads**: try local first, fall back to remote (download to local on miss).
    * **Writes**: write to local, then replicate to remote (if ``write_through``).
    * **Verify**: delegates to local if present, otherwise remote.
    """

    def __init__(
        self,
        *,
        remote: ArtifactStore,
        local: ArtifactStore,
        write_through: bool = True,
        cache_population_failure_policy: CacheDegradationPolicy = "warn",
    ) -> None:
        self._remote = remote
        self._local = local
        self._write_through = write_through
        if cache_population_failure_policy not in {"warn", "raise"}:
            raise ValueError("cache_population_failure_policy must be 'warn' or 'raise'")
        self._cache_population_failure_policy = cache_population_failure_policy

    # -- ArtifactStore protocol ----------------------------------------

    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        _aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        if self._local.has(selected):
            return True
        return bool(self._remote.has(selected))

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        artifact_label = _artifact_label(aid)
        try:
            return bytes(self._local.get_bytes(selected))
        except (FileNotFoundError, KeyError):
            logger.debug("Local artifact cache miss for %s", artifact_label)
        except OSError as exc:
            logger.warning(
                "Local artifact cache unavailable for %s; falling back to remote store: %s",
                artifact_label,
                exc,
            )
        data = self._remote.get_bytes(selected)
        # Cache locally for subsequent reads.  We need the original
        # ``PutOptions`` to write to the local store, but since CAS is
        # content-addressed the manifest already exists remotely.
        # Write raw blob + manifest via the local store's put_bytes with
        # a generic kind — the manifest will be overwritten below.
        try:
            manifest = self._remote.get_manifest(selected)
            opts = PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                producer=manifest.producer,
                env=manifest.env,
                inputs=manifest.inputs,
                canon=manifest.canon,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                same_input_closure=manifest.same_input_closure,
                authority=manifest.authority,
                warnings=manifest.warnings,
            )
            local_ref = self._local.put_bytes(data, opts)
            if (
                local_ref.manifest_profile_sha256
                != ManifestLifecycle.profile_sha256(manifest)
            ):
                raise ArtifactIntegrityError(
                    "Local cache persisted a different manifest profile than the remote view"
                )
            if ref is not None and local_ref.manifest_profile_sha256 != ref.manifest_profile_sha256:
                raise ArtifactIntegrityError(
                    "Local cache cannot reproduce the selected remote view"
                )
        except (FileNotFoundError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "Local artifact cache population failed for %s under policy=%s: %s",
                artifact_label,
                self._cache_population_failure_policy,
                exc,
            )
            if self._cache_population_failure_policy == "raise":
                raise
        return bytes(data)

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        artifact_label = _artifact_label(aid)
        try:
            return self._local.get_manifest(selected)
        except (FileNotFoundError, KeyError):
            logger.debug("Local artifact manifest cache miss for %s", artifact_label)
        except OSError as exc:
            logger.warning(
                "Local artifact manifest cache unavailable for %s; "
                "falling back to remote store: %s",
                artifact_label,
                exc,
            )
        return self._remote.get_manifest(selected)

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        ref = self._local.put_bytes(data, opts)
        if self._write_through:
            remote_ref = self._remote.put_bytes(data, opts)
            if (
                remote_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
                or remote_ref.kind != ref.kind
                or remote_ref.media_type != ref.media_type
            ):
                raise ArtifactIntegrityError(
                    "Local and remote CAS owners returned different manifest views"
                )
            return remote_ref
        return ref

    def put_json(
        self,
        obj: Any,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        ref = self._local.put_json(obj, opts, canon_spec)
        if self._write_through:
            remote_ref = self._remote.put_json(obj, opts, canon_spec)
            if (
                remote_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
                or remote_ref.kind != ref.kind
                or remote_ref.media_type != ref.media_type
            ):
                raise ArtifactIntegrityError(
                    "Local and remote CAS owners returned different manifest views"
                )
            return remote_ref
        return ref

    def verify(self, artifact_id: ArtifactID | ArtifactRef | str) -> VerificationReport:
        _aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        if self._local.has(selected):
            return self._local.verify(selected)
        return self._remote.verify(selected)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        local_ids = set(self._local.iter_artifact_ids())
        remote_ids = set(self._remote.iter_artifact_ids())
        return sorted(local_ids | remote_ids, key=lambda a: a.hex)

    def artifact_store_config(self) -> ArtifactStoreConfig | None:
        """Return declarative config needed to rebuild this cached store."""
        from .config import ArtifactStoreConfig, infer_artifact_store_config

        local_config = infer_artifact_store_config(self._local)
        remote_config = infer_artifact_store_config(self._remote)
        if local_config is None or remote_config is None:
            return None
        if local_config.backend != "filesystem":
            return None
        if remote_config.backend == "s3":
            return ArtifactStoreConfig(
                backend="cached_s3",
                root=local_config.root,
                bucket=remote_config.bucket,
                prefix=remote_config.prefix,
                region=remote_config.region,
                local_cache_dir=local_config.root,
            )
        if remote_config.backend == "gcs":
            return ArtifactStoreConfig(
                backend="cached_gcs",
                root=local_config.root,
                bucket=remote_config.bucket,
                prefix=remote_config.prefix,
                region=remote_config.region,
                local_cache_dir=local_config.root,
            )
        return None
