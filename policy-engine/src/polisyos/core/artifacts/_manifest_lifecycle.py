"""Artifact manifest lifecycle helpers for filesystem-backed CAS implementations."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from polisyos.common.serialization import fast_json_dumps_bytes

from .manifest import ArtifactManifest, IntegrityInfo, _coerce_input_ref

if TYPE_CHECKING:
    from pathlib import Path

    from ._atomic_write import AtomicFileWriter
    from .ids import ArtifactID
    from .write_contract import ArtifactWriteOptions


class ManifestLifecycle:
    """Build, serialize, and validate immutable artifact manifest sidecars."""

    def __init__(self, files: AtomicFileWriter) -> None:
        self._files = files

    @staticmethod
    def build(
        *,
        artifact_id: ArtifactID,
        data: bytes,
        sha: str,
        opts: ArtifactWriteOptions,
    ) -> ArtifactManifest:
        input_refs = [_coerce_input_ref(input_ref) for input_ref in opts.inputs or []]
        manifest_payload = {
            "artifact_id": artifact_id,
            "kind": opts.kind,
            "media_type": opts.media_type,
            "byte_size": len(data),
            "schema": opts.schema,
            "canon": opts.canon,
            "inputs": input_refs,
            "producer": opts.producer,
            "env": opts.env,
            "governance": getattr(opts, "governance", None),
            "tenant_context": getattr(opts, "tenant_context", None),
            "same_input_closure": getattr(opts, "same_input_closure", None),
            "authority": getattr(opts, "authority", None),
            "integrity": IntegrityInfo(sha256=sha),
            "warnings": list(opts.warnings or []),
        }
        # v1 omits the version marker and remains byte-compatible with historical
        # manifests. The selector is a hashed-model extension only when an input
        # explicitly names a selected manifest view, so bump that projection alone.
        # Set the marker before model validation so v1 cannot accept new hashed bytes.
        if any(input_ref.manifest_profile_sha256 is not None for input_ref in input_refs):
            manifest_payload["manifest_schema_version"] = "v2"
        return ArtifactManifest.model_validate(manifest_payload)

    @staticmethod
    def to_bytes(manifest: ArtifactManifest) -> bytes:
        return fast_json_dumps_bytes(
            manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
            sort_keys=True,
        )

    def write_once(self, path: Path, manifest: ArtifactManifest) -> bool:
        return self._files.write_once(path, self.to_bytes(manifest))

    @staticmethod
    def profile_mismatches(
        manifest: ArtifactManifest,
        *,
        data_size: int,
        opts: ArtifactWriteOptions,
    ) -> tuple[str, ...]:
        """Return persisted manifest fields that disagree with write options.

        A content-addressed blob may be shared only when its complete persisted
        write profile is the same.  The creation timestamp and content identity
        are deliberately excluded: they describe the already-persisted object,
        rather than the caller's requested profile.
        """
        expected = {
            "kind": opts.kind,
            "media_type": opts.media_type,
            "byte_size": data_size,
            "artifact_schema": opts.schema,
            "canon": opts.canon,
            "inputs": [_coerce_input_ref(input_ref) for input_ref in opts.inputs or []],
            "producer": opts.producer,
            "env": opts.env,
            "governance": getattr(opts, "governance", None),
            "tenant_context": getattr(opts, "tenant_context", None),
            "same_input_closure": getattr(opts, "same_input_closure", None),
            "authority": getattr(opts, "authority", None),
            "warnings": list(opts.warnings or []),
        }
        return tuple(
            field
            for field, expected_value in expected.items()
            if getattr(manifest, field) != expected_value
        )

    @classmethod
    def validate_profile(
        cls,
        manifest: ArtifactManifest,
        *,
        data_size: int,
        opts: ArtifactWriteOptions,
    ) -> None:
        """Fail closed when reuse would return a profile absent from storage."""
        mismatches = cls.profile_mismatches(manifest, data_size=data_size, opts=opts)
        if mismatches:
            fields = ", ".join(mismatches)
            raise ValueError(f"Existing artifact manifest profile conflict: {fields}")

    @staticmethod
    def profile_projection(manifest: ArtifactManifest) -> dict[str, object]:
        """Return every immutable typed-view field, including warning evidence."""
        return manifest.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude={
                "artifact_id",
                "byte_size",
                "created_at",
                "integrity",
            },
        )

    @classmethod
    def profile_sha256(cls, manifest: ArtifactManifest) -> str:
        """Compute a domain-separated digest for one complete persisted view."""
        projection = cls.profile_projection(manifest)
        payload = fast_json_dumps_bytes(projection, sort_keys=True)
        digest = hashlib.sha256(b"polisyos.cas.manifest-profile.v1\0" + payload).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def read(path: Path) -> ArtifactManifest:
        return ArtifactManifest.model_validate_json(path.read_text("utf-8"))


__all__ = ["ManifestLifecycle"]
