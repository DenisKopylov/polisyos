"""Direct selected-profile verification for a scoped replay reader."""

from __future__ import annotations

from functools import wraps
from typing import Any

from ._integrity_ops import VerificationReport, verification_report_from_loaded_artifact
from .ids import ArtifactID
from .manifest import ArtifactRef, artifact_reference_parts
from .ownership import raise_artifact_read_access_error


class SelectedProfileVerificationReader:
    """Reopen a selected view and check its bytes without a boolean access probe.

    Other operations are delegated to the original owner. An explicit wrapped
    ownership or filesystem permission cause is preserved; typed unavailability
    and all unrelated exceptions retain their original meaning. A false report
    means the opened bytes and manifest failed integrity checks, never that
    access was denied. The facade adds no grant, attestation, or currentness claim.
    """

    def __init__(self, owner: Any) -> None:
        self._owner = owner

    def __getattr__(self, name: str) -> Any:
        try:
            value = getattr(self._owner, name)
        except Exception as exc:
            raise_artifact_read_access_error(exc)
            raise
        if not callable(value):
            return value

        @wraps(value)
        def invoke(*args: Any, **kwargs: Any) -> Any:
            try:
                return value(*args, **kwargs)
            except Exception as exc:
                # A backend/guard can wrap the actual owner refusal. Preserve
                # that explicit cause before any caller can classify it as
                # an unavailable or invalid artifact. All other errors retain
                # their original identity and traceback.
                raise_artifact_read_access_error(exc)
                raise

        return invoke

    def verify(self, selector: ArtifactID | ArtifactRef | str) -> VerificationReport:
        """Recompute the standard Core report after exact owner reads."""
        from polisyos.common.canonical_profile import CanonicalProfileRefusalError

        from .canonical_profile import artifact_ref_for_manifest, read_core_manifest_profile

        artifact_id, profile_sha256, ref = artifact_reference_parts(selector)
        media_type = ref.media_type.partition(";")[0].strip().casefold() if ref is not None else ""
        media_family, _, subtype = media_type.partition("/")
        # A raw media view can omit the JSON codec when all selectors are exact.
        allow_raw_profile = bool(
            ref is not None
            and profile_sha256 is not None
            and ref.kind.strip()
            and media_family
            and subtype
            and "json" not in subtype
        )
        manifest, _ = read_core_manifest_profile(
            self,
            ref if allow_raw_profile else selector,
            allow_profile_absent=allow_raw_profile,
        )
        selected_ref = artifact_ref_for_manifest(manifest)
        data = self.get_bytes(selected_ref)
        selected_manifest, _ = read_core_manifest_profile(
            self, selected_ref, allow_profile_absent=allow_raw_profile
        )
        if (
            artifact_ref_for_manifest(selected_manifest) != selected_ref
            or manifest.byte_size != selected_manifest.byte_size
            or manifest.integrity.sha256 != selected_manifest.integrity.sha256
        ):
            raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
        return verification_report_from_loaded_artifact(
            artifact_id, data=data, manifest=selected_manifest
        )
