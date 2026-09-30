"""Artifact manifest lifecycle helpers for filesystem-backed CAS implementations."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING

from polisyos.common.serialization import fast_json_dumps_bytes

from .manifest import ArtifactManifest, IntegrityInfo, _coerce_input_ref

if TYPE_CHECKING:
    from pathlib import Path

    from .ids import ArtifactID
    from .write_contract import ArtifactWriteOptions


class ManifestLifecycle:
    """Build, serialize, and validate immutable artifact manifest sidecars."""

    @staticmethod
    def build(
        *,
        artifact_id: ArtifactID,
        data: bytes,
        sha: str,
        opts: ArtifactWriteOptions,
        created_at: datetime | None = None,
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
        if created_at is not None:
            manifest_payload["created_at"] = created_at
        # V3 versions the profile projection that binds all consumer-visible
        # integrity metadata while excluding the derived content digest.
        manifest_payload["manifest_schema_version"] = "v3"
        return ArtifactManifest.model_validate(manifest_payload)

    @classmethod
    def expected_for_write(
        cls,
        *,
        artifact_id: ArtifactID,
        data: bytes,
        opts: ArtifactWriteOptions,
        created_at: datetime,
    ) -> ArtifactManifest:
        """Reconstruct the exact current manifest a CAS write must emit.

        The current write path and readers checking a just-written artifact share
        this constructor so schema-version and metadata selection cannot drift.
        Historical sidecar replay uses its explicitly versioned projection instead.
        """
        sha = hashlib.sha256(data).hexdigest()
        if sha != artifact_id.hex:
            raise ValueError("expected manifest artifact ID does not match payload bytes")
        return cls.build(
            artifact_id=artifact_id,
            data=data,
            sha=sha,
            opts=opts,
            created_at=created_at,
        )

    @staticmethod
    def to_bytes(manifest: ArtifactManifest) -> bytes:
        return fast_json_dumps_bytes(
            manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
            sort_keys=True,
        )

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
        """Return the typed-view projection selected by its persisted schema version.

        Historical v1/v2 manifests keep the original projection, which omitted the
        complete integrity object. V3 binds consumer-visible optional integrity
        metadata while excluding only the content-derived SHA-256 value.
        """
        excluded: dict[str, object] = {
            "artifact_id": True,
            "byte_size": True,
            "created_at": True,
        }
        if manifest.manifest_schema_version in {"v1", "v2"}:
            excluded["integrity"] = True
        else:
            excluded["integrity"] = {"sha256"}
        return manifest.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude=excluded,
        )

    @classmethod
    def profile_sha256(cls, manifest: ArtifactManifest) -> str:
        """Compute the historical v1 or v3-projection v2 digest for a persisted view."""
        projection = cls.profile_projection(manifest)
        payload = fast_json_dumps_bytes(projection, sort_keys=True)
        profile_version = "v2" if manifest.manifest_schema_version == "v3" else "v1"
        domain = f"polisyos.cas.manifest-profile.{profile_version}\0".encode("ascii")
        digest = hashlib.sha256(domain + payload).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def read(path: Path) -> ArtifactManifest:
        return ArtifactManifest.model_validate_json(path.read_text("utf-8"))


__all__ = ["ManifestLifecycle"]
