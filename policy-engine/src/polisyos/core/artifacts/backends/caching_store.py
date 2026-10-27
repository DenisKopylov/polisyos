"""Write-through caching store: local FileSystemCAS + remote ArtifactStore."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.canonical import _admit_canon_spec
from polisyos.common.logger import get_logger
from polisyos.core.canon.canon_json import CanonSpec, CanonViolation

from .._integrity_ops import ArtifactIntegrityError
from .._manifest_lifecycle import ManifestLifecycle
from ..ids import ArtifactID
from ..manifest import ArtifactManifest, ArtifactRef, artifact_reference_parts
from ..ownership import ArtifactOwnershipError
from ..protocol import (
    ArtifactStore,
    _require_return_selected_profile_writer,
    _validate_return_selected_profile,
)
from ..store import PutOptions, VerificationReport

logger = get_logger(__name__)

CacheDegradationPolicy = Literal["warn", "raise"]


class _CachePopulationUnavailableError(RuntimeError):
    """Exact local cache population is unavailable without changing owner data."""


if TYPE_CHECKING:
    from .._integrity_ops import ArtifactBoundedManifestRead
    from ..protocol import CoreJSONArtifactBoundedMemberAttempt
    from .config import ArtifactStoreConfig


def _artifact_label(artifact_id: ArtifactID) -> str:
    return str(getattr(artifact_id, "hex", artifact_id))


class CachingArtifactStore:
    """Composes a local CAS (fast) with a remote store (durable).

    * **Blob reads**: try local first, fall back to remote (download to local on miss).
    * **Manifest reads**: resolve selector-free defaults at the durable owner (remote for
      write-through stores, local for local-only stores); exact write-through views are
      admitted by the durable owner before a local cache hit.
    * **Writes**: publish at the durable remote owner first, then cache its exact
      selected view locally when write-through is enabled.
    * **Verify**: selector-free defaults use the durable owner; selected write-through views
      use a local hit only after durable-owner admission.
    * **Strict bounded reads**: the exact selected ref is forwarded only to the
      manifest owner. A local cache hit never substitutes for that owner's bounded receipt.
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
        cache_import_ref = selected
        artifact_label = _artifact_label(aid)
        owner_manifest: ArtifactManifest | None = None
        owner_selected_ref: ArtifactRef | None = None
        owner_default_ref: ArtifactRef | ArtifactID | None = None
        if _is_selector_free_default(ref):
            owner_default_ref = ref or aid
        if self._write_through:
            # Resolve and admit the durable-owner view before consulting local bytes.
            owner_manifest, owner_selected_ref = self._resolve_write_through_view(selected)
            selected = owner_selected_ref
            cache_import_ref = owner_selected_ref
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
        try:
            raw_reader, exact_importer = self._exact_cache_copy_capabilities()
            if owner_manifest is None:
                owner_manifest = self._remote.get_manifest(selected)
                owner_selected_ref = _manifest_view_ref(owner_manifest)
            if owner_selected_ref is None:
                raise ArtifactIntegrityError(
                    "Durable owner did not resolve a selected manifest view"
                )
            self._copy_exact_owner_view_to_local_cache(
                bytes(data),
                owner_manifest,
                owner_selected_ref,
                import_artifact_id=cache_import_ref,
                raw_manifest_reader=raw_reader,
                exact_view_importer=exact_importer,
                owner_default_ref=owner_default_ref,
            )
        except PermissionError:
            raise
        except (OSError, KeyError, RuntimeError) as exc:
            self._handle_cache_population_failure(artifact_label, exc)
        return bytes(data)

    def _exact_cache_copy_capabilities(
        self,
    ) -> tuple[Callable[..., Any], Callable[..., ArtifactRef]]:
        """Return the owner-export and local-import methods needed for exact copying."""
        raw_manifest_reader = getattr(self._remote, "get_manifest_bytes", None)
        if not callable(raw_manifest_reader):
            raise _CachePopulationUnavailableError(
                "Durable owner cannot export its exact selected manifest bytes"
            )
        exact_view_importer = getattr(self._local, "import_exact_view", None)
        if not callable(exact_view_importer):
            raise _CachePopulationUnavailableError(
                "Local cache cannot import an exact selected manifest view"
            )
        return raw_manifest_reader, exact_view_importer

    def _copy_exact_owner_view_to_local_cache(
        self,
        data: bytes,
        owner_manifest: ArtifactManifest,
        owner_selected_ref: ArtifactRef,
        *,
        import_artifact_id: ArtifactID | ArtifactRef | str,
        raw_manifest_reader: Callable[..., bytes],
        exact_view_importer: Callable[..., ArtifactRef],
        owner_default_ref: ArtifactRef | ArtifactID | None,
    ) -> None:
        """Copy the durable owner's complete selected record into the local cache."""
        raw_manifest_bytes = raw_manifest_reader(owner_selected_ref)
        if not isinstance(raw_manifest_bytes, bytes):
            raise TypeError("Artifact owner get_manifest_bytes() must return bytes")
        manifest = ArtifactManifest.model_validate_json(raw_manifest_bytes)
        if manifest != owner_manifest:
            raise ArtifactIntegrityError(
                "Durable owner raw manifest differs from its selected typed view"
            )
        if (
            owner_selected_ref.artifact_id != manifest.artifact_id
            or owner_selected_ref.kind != manifest.kind
            or owner_selected_ref.media_type != manifest.media_type
            or owner_selected_ref.manifest_profile_sha256
            != ManifestLifecycle.profile_sha256(manifest)
        ):
            raise ArtifactIntegrityError(
                "Durable owner raw manifest does not match its selected reference"
            )
        if not self._manifest_input_views_match(manifest):
            raise _CachePopulationUnavailableError(
                "Local CAS cannot admit one or more input views for this remote artifact"
            )

        signature_bytes: bytes | None = None
        signature_reader = getattr(self._remote, "get_signature_bytes", None)
        if callable(signature_reader):
            try:
                candidate_signature_bytes = signature_reader(owner_selected_ref)
            except (FileNotFoundError, KeyError):
                candidate_signature_bytes = None
                default_manifest_reader = getattr(self._remote, "get_manifest_bytes", None)
                if owner_default_ref is not None and callable(default_manifest_reader):
                    try:
                        current_default_bytes = default_manifest_reader(owner_default_ref)
                    except (FileNotFoundError, KeyError):
                        current_default_bytes = None
                    if current_default_bytes == raw_manifest_bytes:
                        try:
                            candidate_signature_bytes = signature_reader(owner_default_ref)
                        except (FileNotFoundError, KeyError):
                            candidate_signature_bytes = None
            if candidate_signature_bytes is not None:
                if not isinstance(candidate_signature_bytes, bytes):
                    raise TypeError("Artifact owner get_signature_bytes() must return bytes")
                signature_bytes = candidate_signature_bytes

        imported_ref = exact_view_importer(
            data,
            raw_manifest_bytes,
            artifact_id=import_artifact_id,
            signature_bytes=signature_bytes,
        )
        _aid, requested_profile, _ref = artifact_reference_parts(import_artifact_id)
        owner_profile = owner_selected_ref.manifest_profile_sha256
        if (
            not isinstance(imported_ref, ArtifactRef)
            or imported_ref.artifact_id != owner_selected_ref.artifact_id
            or imported_ref.kind != owner_selected_ref.kind
            or imported_ref.media_type != owner_selected_ref.media_type
            or (
                imported_ref.manifest_profile_sha256 is not None
                and imported_ref.manifest_profile_sha256 != owner_profile
            )
            or (
                requested_profile is not None
                and imported_ref.manifest_profile_sha256 != owner_profile
            )
        ):
            raise ArtifactIntegrityError(
                "Local cache cannot reproduce the durable owner's selected view"
            )
        local_raw_reader = getattr(self._local, "get_manifest_bytes", None)
        if callable(local_raw_reader):
            local_manifest_bytes = local_raw_reader(owner_selected_ref)
            if not isinstance(local_manifest_bytes, bytes):
                raise TypeError("Local cache get_manifest_bytes() must return bytes")
            if local_manifest_bytes != raw_manifest_bytes:
                raise ArtifactIntegrityError(
                    "Local cache did not preserve the durable owner's raw manifest bytes"
                )
        elif not _has_manifest_view(self._local, owner_selected_ref):
            raise ArtifactIntegrityError(
                "Local cache cannot prove admission of the durable owner's selected view"
            )

    def _handle_cache_population_failure(
        self,
        artifact_label: str,
        failure: OSError | KeyError | RuntimeError,
    ) -> None:
        """Apply cache degradation policy after an owner write or successful read."""
        logger.warning(
            "Local artifact cache population failed for %s under policy=%s: %s",
            artifact_label,
            self._cache_population_failure_policy,
            failure,
        )
        if self._cache_population_failure_policy == "raise":
            raise failure

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
            # The profile projection excludes creation time, while the typed
            # manifest still exposes the durable owner's actual creation time.
            return local_manifest if local_manifest == owner_manifest else owner_manifest
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

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read the owner's exact raw sidecar without using a typed cache projection."""
        aid, selected_profile, ref = artifact_reference_parts(artifact_id)
        if manifest_profile_sha256 is not None:
            if re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None:
                raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
            if selected_profile is not None and selected_profile != manifest_profile_sha256:
                raise ValueError("conflicting manifest profile selectors")
            selected_profile = manifest_profile_sha256
        selected = ref or aid
        owners = (
            (self._default_manifest_owner(),)
            if self._write_through
            else (self._local, self._remote)
        )
        for index, owner in enumerate(owners):
            reader = getattr(owner, "get_raw_manifest_bytes", None)
            if not callable(reader):
                raise TypeError("Artifact owner must expose get_raw_manifest_bytes")
            try:
                raw = reader(
                    selected,
                    **(
                        {"manifest_profile_sha256": selected_profile}
                        if selected_profile is not None
                        else {}
                    ),
                )
            except (FileNotFoundError, KeyError):
                if index + 1 < len(owners):
                    continue
                raise
            if not isinstance(raw, bytes):
                raise TypeError("Artifact owner get_raw_manifest_bytes() must return bytes")
            return raw
        raise FileNotFoundError(str(aid))

    def get_manifest_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Return raw manifest bytes from the owner that defines this view.

        Raw profile consumers must observe the owner's exact sidecar bytes. A
        typed local cache hit is insufficient because model validation can fill
        omitted defaults before a reader checks profile completeness.
        """
        if self._write_through:
            owners = (self._default_manifest_owner(),)
        else:
            owners = (self._local, self._remote)
        for index, owner in enumerate(owners):
            reader = getattr(owner, "get_manifest_bytes", None)
            if not callable(reader):
                if index + 1 == len(owners):
                    raise TypeError("Artifact owner must expose get_manifest_bytes")
                continue
            try:
                manifest_bytes = reader(artifact_id)
            except (FileNotFoundError, KeyError):
                if index + 1 < len(owners):
                    continue
                raise
            if not isinstance(manifest_bytes, bytes):
                raise TypeError("Artifact owner get_manifest_bytes() must return bytes")
            return manifest_bytes
        raise TypeError("Artifact owner must expose get_manifest_bytes")

    def get_manifest_by_profile(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> ArtifactManifest:
        """Resolve a selected sidecar by its profile digest across cache owners."""
        aid = ArtifactID.model_validate(artifact_id)
        if re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None:
            raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
        owners = (
            (self._default_manifest_owner(),)
            if self._write_through
            else (
                self._local,
                self._remote,
            )
        )
        for index, owner in enumerate(owners):
            resolver = getattr(owner, "get_manifest_by_profile", None)
            try:
                if callable(resolver):
                    manifest = resolver(aid, manifest_profile_sha256)
                else:
                    manifest = owner.get_manifest(aid)
                    if ManifestLifecycle.profile_sha256(manifest) != manifest_profile_sha256:
                        raise TypeError(
                            "Artifact owner cannot resolve a non-default manifest profile"
                        )
            except (FileNotFoundError, KeyError):
                if index + 1 < len(owners):
                    continue
                raise
            if (
                manifest.artifact_id != aid
                or ManifestLifecycle.profile_sha256(manifest) != manifest_profile_sha256
            ):
                raise ArtifactIntegrityError("Artifact owner returned a different manifest profile")
            return manifest

        raise FileNotFoundError(f"Selected manifest profile not found for {aid}")

    def _populate_local_cache_after_write(
        self,
        remote_ref: ArtifactRef,
        data: bytes | None,
        *,
        return_selected_profile: bool,
    ) -> None:
        """Populate the local cache from the durable owner's selected view."""
        del return_selected_profile  # Exact import preserves the selected owner view directly.
        aid, _profile_sha256, requested_ref = artifact_reference_parts(remote_ref)
        owner_default_ref: ArtifactRef | ArtifactID | None = None
        if _is_selector_free_default(requested_ref):
            owner_default_ref = requested_ref or aid
        artifact_label = _artifact_label(aid)

        try:
            raw_reader, exact_importer = self._exact_cache_copy_capabilities()
            owner_manifest, owner_selected_ref = self._resolve_write_through_view(remote_ref)
            payload = data if data is not None else self._remote.get_bytes(owner_selected_ref)
            self._copy_exact_owner_view_to_local_cache(
                bytes(payload),
                owner_manifest,
                owner_selected_ref,
                import_artifact_id=remote_ref,
                raw_manifest_reader=raw_reader,
                exact_view_importer=exact_importer,
                owner_default_ref=owner_default_ref,
            )
        except PermissionError:
            raise
        except (OSError, KeyError, RuntimeError) as exc:
            self._handle_cache_population_failure(artifact_label, exc)

    def put_bytes(
        self,
        data: bytes,
        opts: PutOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        _validate_return_selected_profile(return_selected_profile)
        if not self._write_through:
            if return_selected_profile:
                _require_return_selected_profile_writer(self._local, "put_bytes")
                ref = self._local.put_bytes(data, opts, return_selected_profile=True)
                _require_selected_profile_ref(ref)
                return ref
            return self._local.put_bytes(data, opts)

        if return_selected_profile:
            # Keep preflight before the durable write so the selected-ref
            # contract is known to both configured owners.
            _require_return_selected_profile_writer(self._local, "put_bytes")
            _require_return_selected_profile_writer(self._remote, "put_bytes")
            remote_ref = self._remote.put_bytes(data, opts, return_selected_profile=True)
            _require_selected_profile_ref(remote_ref)
        else:
            remote_ref = self._remote.put_bytes(data, opts)

        # Cache the supplied bytes against the durable owner's exact manifest.
        self._populate_local_cache_after_write(
            remote_ref,
            data,
            return_selected_profile=return_selected_profile,
        )
        return remote_ref

    def put_json(
        self,
        obj: Any,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        _validate_return_selected_profile(return_selected_profile)
        canon_spec = _admit_canon_spec(
            canon_spec, CanonSpec, violation_type=CanonViolation, artifact_writer=True
        )
        if not self._write_through:
            if return_selected_profile:
                _require_return_selected_profile_writer(self._local, "put_json")
                ref = self._local.put_json(
                    obj,
                    opts,
                    canon_spec,
                    return_selected_profile=True,
                )
                _require_selected_profile_ref(ref)
                return ref
            return self._local.put_json(obj, opts, canon_spec)

        if return_selected_profile:
            # Keep preflight before the durable write so the selected-ref
            # contract is known to both configured owners.
            _require_return_selected_profile_writer(self._local, "put_json")
            _require_return_selected_profile_writer(self._remote, "put_json")
            remote_ref = self._remote.put_json(
                obj,
                opts,
                canon_spec,
                return_selected_profile=True,
            )
            _require_selected_profile_ref(remote_ref)
        else:
            remote_ref = self._remote.put_json(obj, opts, canon_spec)

        # Fetch the owner's serialized blob, then use its exact selected
        # manifest instead of serializing a second local record.
        self._populate_local_cache_after_write(
            remote_ref,
            None,
            return_selected_profile=return_selected_profile,
        )
        return remote_ref

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        """Read a default or exact manifest only through the durable view owner.

        A selector-free ArtifactID forwards the durable owner's default view. A supplied
        profile selects exactly that sidecar. The local cache never supplies this receipt,
        and unsupported durable owners refuse without calling an unbounded API.
        """
        if type(artifact_id) is ArtifactRef:
            if (
                type(artifact_id.manifest_profile_sha256) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_id.manifest_profile_sha256) is None
            ):
                raise ValueError("bounded_manifest_read_requires_profile_qualified_ref")
            if (
                manifest_profile_sha256 is not None
                and manifest_profile_sha256 != artifact_id.manifest_profile_sha256
            ):
                raise ValueError("conflicting manifest profile selectors")
            selected_profile = None
        elif type(artifact_id) is ArtifactID:
            selected_profile = manifest_profile_sha256
            if selected_profile is not None and (
                type(selected_profile) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", selected_profile) is None
            ):
                raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
        else:
            raise ValueError("bounded_manifest_read_requires_artifact_id_or_ref")
        if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
            raise ValueError("max_manifest_bytes must be a positive integer")

        owner = self._default_manifest_owner()
        reader = getattr(owner, "read_raw_manifest_bytes_bounded", None)
        if not callable(reader):
            raise NotImplementedError("cache_manifest_owner_bounded_receipt_unavailable")
        if selected_profile is None:
            return reader(artifact_id, max_manifest_bytes=max_manifest_bytes)
        if type(artifact_id) is ArtifactRef:
            return reader(artifact_id, max_manifest_bytes=max_manifest_bytes)
        return reader(
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=selected_profile,
        )

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> CoreJSONArtifactBoundedMemberAttempt:
        """Open the exact selected member only through its manifest owner.

        This strict path preserves cache selection policy. It does not serve
        bytes from the local cache when the durable owner lacks the bounded
        member contract, and it never falls back to ``get_bytes``.
        """
        if (
            type(artifact_id) is not ArtifactRef
            or type(artifact_id.manifest_profile_sha256) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_id.manifest_profile_sha256) is None
        ):
            raise ValueError("bounded_member_read_requires_profile_qualified_ref")
        if member != "blob":
            raise ValueError("bounded_member_name_invalid")
        if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
            raise ValueError("max_manifest_bytes must be a positive integer")
        if type(max_member_bytes) is not int or max_member_bytes < 1:
            raise ValueError("max_member_bytes must be a positive integer")
        if (
            type(expected_manifest_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is None
        ):
            raise ValueError("expected_manifest_sha256_invalid")
        owner = self._default_manifest_owner()
        reader = getattr(owner, "open_member_bounded", None)
        if not callable(reader):
            raise NotImplementedError("cache_manifest_owner_bounded_member_unavailable")
        return reader(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

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


def _require_selected_profile_ref(ref: ArtifactRef) -> None:
    """Reject a writer that accepted the option but returned only a legacy selector."""
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ArtifactIntegrityError("artifact_write_selected_profile_missing")


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
