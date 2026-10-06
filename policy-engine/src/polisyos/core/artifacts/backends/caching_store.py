"""Write-through caching store: local FileSystemCAS + remote ArtifactStore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.logger import get_logger
from polisyos.core.canon.canon_json import CanonSpec

from .._integrity_ops import ArtifactIntegrityError
from .._manifest_lifecycle import ManifestLifecycle
from ..ids import ArtifactID
from ..manifest import ArtifactManifest, ArtifactRef, artifact_reference_parts
from ..ownership import ArtifactOwnershipError
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

    * **Blob reads**: try local first, fall back to remote (download to local on miss).
    * **Manifest reads**: resolve selector-free defaults at the durable owner (remote for
      write-through stores, local for local-only stores); exact write-through views are
      admitted by the durable owner before a local cache hit.
    * **Writes**: publish at the durable owner, then populate the cache through
      the same exact-byte consumer as reads (if ``write_through``).
    * **Verify**: selector-free defaults use the durable owner; selected write-through views
      use a local hit only after durable-owner admission.
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
        if _is_selector_free_default(ref):
            return bool(self._default_manifest_owner().has(selected))
        if self._write_through:
            try:
                _owner_manifest, owner_selected_ref = self._resolve_write_through_view(selected)
            except (FileNotFoundError, KeyError):
                return False
            if _has_manifest_view(self._local, owner_selected_ref):
                return bool(self._local.has(owner_selected_ref))
            return bool(self._remote.has(owner_selected_ref))
        if self._local.has(selected):
            return True
        return bool(self._remote.has(selected))

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        artifact_label = _artifact_label(aid)
        owner_selected_ref: ArtifactRef | None = None
        owner_default_ref: ArtifactRef | ArtifactID | None = None
        if self._write_through:
            # Resolve and admit the durable-owner view before consulting local bytes.
            _owner_manifest, owner_selected_ref = self._resolve_write_through_view(selected)
            if _is_selector_free_default(ref):
                owner_default_ref = ref or aid
            selected = owner_selected_ref
        try:
            if owner_selected_ref is not None and not _has_manifest_view(
                self._local,
                owner_selected_ref,
            ):
                logger.debug(
                    "Local artifact cache miss for unadmitted manifest view %s",
                    artifact_label,
                )
            else:
                return bytes(self._local.get_bytes(selected))
        except (FileNotFoundError, KeyError):
            logger.debug("Local artifact cache miss for %s", artifact_label)
        except PermissionError:
            raise
        except OSError as exc:
            logger.warning(
                "Local artifact cache unavailable for %s; falling back to remote store: %s",
                artifact_label,
                exc,
            )
        data = self._remote.get_bytes(selected)
        return self._cache_remote_view(
            data,
            selected,
            owner_default_ref=owner_default_ref,
            owner_selected_ref=owner_selected_ref,
        )

    def _cache_remote_view(
        self,
        data: bytes,
        selected: ArtifactID | ArtifactRef | str,
        *,
        owner_default_ref: ArtifactRef | ArtifactID | None = None,
        owner_selected_ref: ArtifactRef | None = None,
    ) -> bytes:
        """Populate through the existing exact-byte consumer of durable-owner reads."""
        aid, _profile, ref = artifact_reference_parts(selected)
        artifact_label = _artifact_label(aid)
        # Cache locally for subsequent reads.  We need the original
        # ``PutOptions`` to write to the local store, but since CAS is
        # content-addressed the manifest already exists remotely.
        # Prefer the storage owner's exact-byte transfer seam when available;
        # simpler stores retain the typed put_bytes fallback below.
        try:
            raw_manifest_reader = getattr(self._remote, "get_manifest_bytes", None)
            exact_view_importer = getattr(self._local, "import_exact_view", None)
            raw_manifest_bytes = (
                raw_manifest_reader(selected) if callable(raw_manifest_reader) else None
            )
            if isinstance(raw_manifest_bytes, bytes) and callable(exact_view_importer):
                manifest = ArtifactManifest.model_validate_json(raw_manifest_bytes)
                if not self._manifest_input_views_match(manifest):
                    message = (
                        "Local CAS cannot admit one or more input views for this remote artifact"
                    )
                    if self._cache_population_failure_policy == "raise":
                        raise RuntimeError(message)
                    logger.warning(
                        "Skipping local cache population for %s: %s",
                        artifact_label,
                        message,
                    )
                    return bytes(data)
                signature_bytes: bytes | None = None
                signature_reader = getattr(self._remote, "get_signature_bytes", None)
                if callable(signature_reader):
                    try:
                        candidate_signature_bytes = signature_reader(selected)
                    except FileNotFoundError:
                        candidate_signature_bytes = None
                        default_manifest_reader = getattr(
                            self._remote,
                            "get_manifest_bytes",
                            None,
                        )
                        if (
                            owner_selected_ref is not None
                            and owner_default_ref is not None
                            and callable(default_manifest_reader)
                        ):
                            # Some owners sign the selector-free default and do
                            # not duplicate its sidecar under the exact profile
                            # selector. Reuse those exact signature bytes only
                            # while the durable default still resolves to the
                            # manifest bytes already pinned for this read. The
                            # importer independently checks the signature's
                            # manifest digest before persisting it.
                            try:
                                current_default_bytes = default_manifest_reader(owner_default_ref)
                            except (FileNotFoundError, KeyError):
                                current_default_bytes = None
                            if current_default_bytes == raw_manifest_bytes:
                                try:
                                    candidate_signature_bytes = signature_reader(owner_default_ref)
                                except FileNotFoundError:
                                    candidate_signature_bytes = None
                            else:
                                logger.warning(
                                    "Not copying a default signature for %s: "
                                    "the durable default no longer matches the pinned view",
                                    artifact_label,
                                )
                    if isinstance(candidate_signature_bytes, bytes):
                        signature_bytes = candidate_signature_bytes
                imported_ref = exact_view_importer(
                    data,
                    raw_manifest_bytes,
                    artifact_id=selected,
                    signature_bytes=signature_bytes,
                )
                if imported_ref.artifact_id != aid:
                    raise ArtifactIntegrityError(
                        "Local cache imported an exact manifest view for another artifact"
                    )
                if ref is not None and (
                    ref.manifest_profile_sha256 is not None
                    and imported_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
                ):
                    raise ArtifactIntegrityError(
                        "Local cache cannot reproduce the selected remote view"
                    )
                return bytes(data)

            manifest = self._remote.get_manifest(selected)
            if not self._manifest_input_views_match(manifest):
                message = "Local CAS cannot admit one or more input views for this remote artifact"
                if self._cache_population_failure_policy == "raise":
                    raise RuntimeError(message)
                logger.warning(
                    "Skipping local cache population for %s: %s",
                    artifact_label,
                    message,
                )
                return bytes(data)
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
            local_manifest = self._local.get_manifest(local_ref)
            if _manifest_view_identity(local_manifest) != _manifest_view_identity(manifest):
                raise ArtifactIntegrityError(
                    "Local cache persisted a different manifest profile than the remote view"
                )
        except PermissionError:
            raise
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

    def _manifest_input_views_match(self, manifest: ArtifactManifest) -> bool:
        """Check that local cache can resolve the lineage views named by a manifest.

        The durable owner defines selector-free input defaults. The local cache may
        mirror a child only when it can resolve the same default profile or the exact
        selected view. An absent or foreign-owned local input is a cache miss, not a
        reason to replace the remote owner's already-verified child read.
        """
        for input_ref in manifest.inputs:
            if input_ref.manifest_profile_sha256 is None:
                try:
                    remote_manifest = self._remote.get_manifest(input_ref.artifact_id)
                    local_manifest = self._local.get_manifest(input_ref.artifact_id)
                except (ArtifactOwnershipError, FileNotFoundError, KeyError):
                    return False
                if _manifest_view_identity(remote_manifest) != _manifest_view_identity(
                    local_manifest
                ):
                    return False
                continue

            remote_view_check = getattr(self._remote, "has_manifest_view", None)
            local_view_check = getattr(self._local, "has_manifest_view", None)
            if not callable(remote_view_check) or not callable(local_view_check):
                return False
            if not remote_view_check(
                input_ref.artifact_id,
                input_ref.manifest_profile_sha256,
            ):
                return False
            if not local_view_check(
                input_ref.artifact_id,
                input_ref.manifest_profile_sha256,
            ):
                return False
        return True

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        artifact_label = _artifact_label(aid)
        if _is_selector_free_default(ref):
            # A selector-free reference is a store-scoped alias. The owner that
            # receives the writes defines the composite default; a local-only
            # store must not ask its deliberately unused remote for the manifest.
            return self._default_manifest_owner().get_manifest(selected)
        if self._write_through:
            owner_manifest, owner_selected_ref = self._resolve_write_through_view(selected)
            if not _has_manifest_view(self._local, owner_selected_ref):
                return owner_manifest
            local_manifest = self._local.get_manifest(owner_selected_ref)
            if _manifest_view_identity(local_manifest) != _manifest_view_identity(owner_manifest):
                raise ArtifactIntegrityError(
                    "Local cache returned a different manifest view than the durable owner"
                )
            return local_manifest
        try:
            return self._local.get_manifest(selected)
        except (FileNotFoundError, KeyError):
            logger.debug("Local artifact manifest cache miss for %s", artifact_label)
        except PermissionError:
            raise
        except OSError as exc:
            logger.warning(
                "Local artifact manifest cache unavailable for %s; "
                "falling back to remote store: %s",
                artifact_label,
                exc,
            )
        return self._remote.get_manifest(selected)

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        if not self._write_through:
            return self._local.put_bytes(data, opts)
        remote_ref = self._remote.put_bytes(data, opts)
        # Local reconstruction would generate independent metadata (created_at
        # included). The existing read consumer transfers the owner's exact
        # selected bytes, preserving an unrelated immutable cache default.
        self._cache_remote_view(self._remote.get_bytes(remote_ref), remote_ref)
        return remote_ref

    def put_json(
        self,
        obj: Any,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        if not self._write_through:
            return self._local.put_json(obj, opts, canon_spec)
        remote_ref = self._remote.put_json(obj, opts, canon_spec)
        self._cache_remote_view(self._remote.get_bytes(remote_ref), remote_ref)
        return remote_ref

    def verify(self, artifact_id: ArtifactID | ArtifactRef | str) -> VerificationReport:
        _aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or artifact_id
        if _is_selector_free_default(ref):
            return self._default_manifest_owner().verify(selected)
        if self._write_through:
            _owner_manifest, owner_selected_ref = self._resolve_write_through_view(selected)
            if _has_manifest_view(self._local, owner_selected_ref):
                return self._local.verify(owner_selected_ref)
            return self._remote.verify(owner_selected_ref)
        if self._local.has(selected):
            return self._local.verify(selected)
        return self._remote.verify(selected)

    def _resolve_write_through_view(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> tuple[ArtifactManifest, ArtifactRef]:
        """Resolve an exact view through the durable owner before cache admission."""
        aid, _profile_sha256, requested_ref = artifact_reference_parts(artifact_id)
        owner_manifest = self._default_manifest_owner().get_manifest(artifact_id)
        owner_ref = _manifest_view_ref(owner_manifest)
        if owner_ref.artifact_id != aid or (
            requested_ref is not None
            and (
                requested_ref.kind != owner_ref.kind
                or requested_ref.media_type != owner_ref.media_type
                or (
                    requested_ref.manifest_profile_sha256 is not None
                    and requested_ref.manifest_profile_sha256 != owner_ref.manifest_profile_sha256
                )
            )
        ):
            raise ArtifactIntegrityError(
                "Durable owner resolved a different selected manifest view"
            )
        return owner_manifest, owner_ref

    def _default_manifest_owner(self) -> ArtifactStore:
        """Return the owner whose writes define selector-free defaults."""
        return self._remote if self._write_through else self._local

    def _same_manifest_view(
        self,
        local_ref: ArtifactRef,
        remote_ref: ArtifactRef,
    ) -> bool:
        """Compare owner-resolved profiles, independent of default selectors."""
        if local_ref.artifact_id != remote_ref.artifact_id:
            return False
        local_manifest = self._local.get_manifest(local_ref)
        remote_manifest = self._remote.get_manifest(remote_ref)
        return _manifest_view_identity(local_manifest) == _manifest_view_identity(remote_manifest)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """List IDs whose selector-free views belong to the configured write owner."""
        return self._default_manifest_owner().iter_artifact_ids()

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


def _is_selector_free_default(ref: ArtifactRef | None) -> bool:
    return ref is None or ref.manifest_profile_sha256 is None


def _manifest_view_identity(manifest: ArtifactManifest) -> tuple[str, str, str, str]:
    return (
        str(manifest.artifact_id),
        manifest.kind,
        manifest.media_type,
        ManifestLifecycle.profile_sha256(manifest),
    )


def _manifest_view_ref(manifest: ArtifactManifest) -> ArtifactRef:
    """Address one owner-resolved manifest profile without using its default alias."""
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
    )


def _has_manifest_view(store: ArtifactStore, ref: ArtifactRef) -> bool:
    """Return whether the local cache admits this exact selected manifest view."""
    profile_sha256 = ref.manifest_profile_sha256
    if profile_sha256 is None:
        return bool(store.has(ref))
    exact_view_probe = getattr(store, "has_manifest_view", None)
    if callable(exact_view_probe):
        return bool(exact_view_probe(ref.artifact_id, profile_sha256))
    return bool(store.has(ref))
